"""FastAPI application: REST API + static web UI."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .config import user_data_dir
from .design.geometry import evaluate as evaluate_design
from .design.library import DesignLibrary
from .design.models import PLUG_TYPE_LABELS, Design, DesignResult
from .export import design_rows, rows_to_csv, rows_to_xlsx, to_csv, to_xlsx
from .materials.database import MaterialDatabase, make_id
from .materials.models import Category, Material, MaterialDef, PropertyInput
from .materials.properties import PROPERTIES, PropertyDef
from .materials.ranking import RankEntry, rank_materials
from .prices.providers import PROVIDERS
from .prices.store import TROY_OUNCE_G, PriceEntry, PriceStore
from .settings import Settings, SettingsStore

WEB_DIR = Path(__file__).parent / "web"


class NewMaterial(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["element", "alloy"] = "alloy"
    categories: list[Category] = Field(min_length=1)
    composition: dict[str, float] = Field(default_factory=dict)  # mass fractions or percent
    description: str | None = None
    properties: dict[str, PropertyInput] = Field(default_factory=dict)


class RankRequest(BaseModel):
    weights: dict[str, float]
    category: Category | Literal["all"] = "precious"
    ids: list[str] | None = None


class ManualPrice(BaseModel):
    metal: str
    value: float = Field(gt=0)
    unit: Literal["USD/ozt", "USD/g"] = "USD/ozt"
    date: str | None = None
    source: str | None = None


class EvaluatedDesign(BaseModel):
    design: Design
    result: DesignResult


class DesignExport(BaseModel):
    designs: list[Design] = Field(min_length=1, max_length=8)
    format: Literal["csv", "xlsx"] = "csv"


class PriceRow(BaseModel):
    metal: str
    usd_per_ozt: float
    usd_per_g: float
    date: str
    source: str | None
    origin: str
    age_days: int
    stale: bool


def create_app(data_dir: Path | None = None) -> FastAPI:
    data_dir = data_dir or user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    prices = PriceStore(data_dir)
    settings = SettingsStore(data_dir)
    state = {"db": MaterialDatabase(data_dir, prices)}
    designs = DesignLibrary(data_dir)

    def db() -> MaterialDatabase:
        return state["db"]

    def reload() -> None:
        state["db"] = MaterialDatabase(data_dir, prices)

    app = FastAPI(title="Spark Plug Designer", version=__version__)

    @app.get("/api/info")
    def info() -> dict:
        return {"version": __version__, "data_dir": str(data_dir)}

    # -- materials -----------------------------------------------------------
    @app.get("/api/properties", response_model=list[PropertyDef])
    def properties() -> list[PropertyDef]:
        return PROPERTIES

    @app.get("/api/materials", response_model=list[Material])
    def materials(category: str | None = None) -> list[Material]:
        mats = db().all()
        if category and category != "all":
            mats = [m for m in mats if category in m.categories]
        return mats

    @app.get("/api/materials/{material_id}", response_model=Material)
    def material(material_id: str) -> Material:
        try:
            return db().get(material_id)
        except KeyError:
            raise HTTPException(404, f"unknown material '{material_id}'") from None

    @app.post("/api/materials", response_model=Material, status_code=201)
    def add_material(body: NewMaterial) -> Material:
        comp = body.composition
        if comp and sum(comp.values()) > 1.5:  # given in percent
            comp = {k: v / 100.0 for k, v in comp.items()}
        try:
            mdef = MaterialDef(
                id=make_id(body.name), name=body.name, kind=body.kind, categories=body.categories,
                composition={k: v for k, v in comp.items() if v > 0}, description=body.description,
                properties={k: v for k, v in body.properties.items() if v.value is not None},
            )
            return db().add_material(mdef)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.delete("/api/materials/{material_id}", status_code=204)
    def delete_material(material_id: str) -> Response:
        try:
            db().delete_material(material_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return Response(status_code=204)

    @app.put("/api/materials/{material_id}/properties", response_model=Material)
    def set_properties(material_id: str, body: dict[str, PropertyInput | None]) -> Material:
        try:
            return db().set_overrides(material_id, body)
        except KeyError:
            raise HTTPException(404, f"unknown material '{material_id}'") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.delete("/api/materials/{material_id}/properties", response_model=Material)
    def clear_properties(material_id: str) -> Material:
        db().clear_overrides(material_id)
        return db().get(material_id)

    @app.post("/api/ranking", response_model=list[RankEntry])
    def ranking(body: RankRequest) -> list[RankEntry]:
        mats = db().all()
        if body.ids:
            mats = [m for m in mats if m.id in body.ids]
        elif body.category != "all":
            mats = [m for m in mats if body.category in m.categories]
        return rank_materials(mats, body.weights)

    @app.get("/api/export")
    def export(ids: str = Query(..., description="comma-separated material ids"),
               format: Literal["csv", "xlsx"] = "csv") -> Response:
        try:
            mats = [db().get(i) for i in ids.split(",") if i]
        except KeyError as exc:
            raise HTTPException(404, f"unknown material {exc}") from None
        stamp = date.today().isoformat()
        if format == "csv":
            return Response(to_csv(mats), media_type="text/csv; charset=utf-8", headers={
                "Content-Disposition": f'attachment; filename="material-comparison-{stamp}.csv"'})
        return Response(to_xlsx(mats), headers={
            "Content-Disposition": f'attachment; filename="material-comparison-{stamp}.xlsx"'},
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # -- prices --------------------------------------------------------------
    def price_row(entry: PriceEntry) -> PriceRow:
        age = (date.today() - date.fromisoformat(entry.date)).days
        return PriceRow(metal=entry.metal, usd_per_ozt=entry.value, usd_per_g=entry.usd_per_gram,
                        date=entry.date, source=entry.source, origin=entry.origin, age_days=age,
                        stale=age > settings.settings.price_max_age_days)

    @app.get("/api/prices", response_model=list[PriceRow])
    def list_prices() -> list[PriceRow]:
        return [price_row(prices.latest(m)) for m in prices.metals()]

    @app.get("/api/prices/{metal}/history", response_model=list[PriceRow])
    def price_history(metal: str) -> list[PriceRow]:
        return [price_row(e) for e in prices.history(metal)]

    @app.post("/api/prices", response_model=PriceRow, status_code=201)
    def add_price(body: ManualPrice) -> PriceRow:
        if body.metal not in db().definitions() or db().definitions()[body.metal].kind != "element":
            raise HTTPException(400, f"'{body.metal}' is not an element in the database")
        value = body.value * TROY_OUNCE_G if body.unit == "USD/g" else body.value
        entry = PriceEntry(metal=body.metal, value=value, date=body.date or date.today().isoformat(),
                           source=body.source or "manual entry", origin="manual")
        try:
            prices.add(entry)
        except ValueError as exc:
            raise HTTPException(400, f"invalid date: {exc}") from None
        reload()
        return price_row(entry)

    @app.delete("/api/prices/{metal}/{entry_date}", status_code=204)
    def delete_price(metal: str, entry_date: str, origin: Literal["manual", "auto"] = "manual") -> Response:
        if not prices.delete(metal, entry_date, origin):
            raise HTTPException(404, "price entry not found")
        reload()
        return Response(status_code=204)

    @app.post("/api/prices/refresh")
    def refresh_prices() -> dict:
        name = settings.settings.price_provider
        if name == "none":
            raise HTTPException(400, "automatic price provider is switched off in the settings")
        result = PROVIDERS[name]().fetch()
        for entry in result.entries:
            prices.add(entry)
        reload()
        return {"provider": name, "updated": [e.metal for e in result.entries], "errors": result.errors}

    # -- electrode designs ---------------------------------------------------
    @app.get("/api/design-types")
    def design_types() -> dict[str, str]:
        return PLUG_TYPE_LABELS

    @app.post("/api/designs/evaluate", response_model=list[EvaluatedDesign])
    def evaluate_designs(body: list[Design]) -> list[EvaluatedDesign]:
        return [EvaluatedDesign(design=d, result=evaluate_design(d, db())) for d in body]

    @app.get("/api/designs", response_model=list[Design])
    def list_designs() -> list[Design]:
        return designs.all()

    @app.post("/api/designs", response_model=Design, status_code=201)
    def save_design(body: Design) -> Design:
        return designs.save(body)

    @app.delete("/api/designs/{design_id}", status_code=204)
    def delete_design(design_id: str) -> Response:
        try:
            designs.delete(design_id)
        except KeyError:
            raise HTTPException(404, f"unknown design '{design_id}'") from None
        return Response(status_code=204)

    @app.post("/api/designs/export")
    def export_designs(body: DesignExport) -> Response:
        results = [evaluate_design(d, db()) for d in body.designs]
        rows = design_rows(body.designs, results)
        stamp = date.today().isoformat()
        if body.format == "csv":
            return Response(rows_to_csv(rows), media_type="text/csv; charset=utf-8", headers={
                "Content-Disposition": f'attachment; filename="electrode-designs-{stamp}.csv"'})
        return Response(rows_to_xlsx(rows, "Designs"), headers={
            "Content-Disposition": f'attachment; filename="electrode-designs-{stamp}.xlsx"'},
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # -- settings ------------------------------------------------------------
    @app.get("/api/settings", response_model=Settings)
    def get_settings() -> Settings:
        return settings.settings

    @app.put("/api/settings", response_model=Settings)
    def put_settings(body: Settings) -> Settings:
        return settings.update(body)

    @app.get("/api/providers")
    def providers() -> list[dict]:
        return [{"name": k, "label": v.label} for k, v in PROVIDERS.items()]

    # -- web UI --------------------------------------------------------------
    @app.get("/vendor/plotly.min.js", include_in_schema=False)
    def plotly_js() -> Response:
        """Serve Plotly from the installed Python package so charts work offline."""
        try:
            import plotly
        except ImportError:
            raise HTTPException(404, "plotly not installed") from None
        path = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
        if not path.exists():
            raise HTTPException(404, "plotly.min.js not found")
        return FileResponse(path, media_type="application/javascript")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app
