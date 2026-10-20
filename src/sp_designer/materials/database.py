"""Material database: seed data + automatic element data + estimates + user overrides."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml

from ..config import PACKAGE_DATA_DIR
from ..prices.store import PriceStore
from .models import ORIGIN_PRECEDENCE, Material, MaterialDef, PropertyInput, PropertyValue
from .properties import EDITABLE_KEYS
from .sources import element_properties

ROOM_TEMPERATURE_C = 25.0


class MaterialDatabase:
    def __init__(self, user_dir: Path, prices: PriceStore, seed_dir: Path | None = None) -> None:
        self.seed_dir = seed_dir or PACKAGE_DATA_DIR / "materials"
        self.user_file = user_dir / "materials.yaml"
        self.prices = prices
        self._seed: dict[str, MaterialDef] = {}
        for name in ("elements.yaml", "alloys.yaml"):
            for raw in _read_list(self.seed_dir / name):
                mat = MaterialDef(**raw)
                self._seed[mat.id] = mat
        user = _read_dict(self.user_file)
        self._user_materials: dict[str, MaterialDef] = {
            m["id"]: MaterialDef(**m) for m in user.get("materials", [])
        }
        self._overrides: dict[str, dict[str, PropertyInput]] = {
            mid: {k: PropertyInput(**v) for k, v in props.items()}
            for mid, props in (user.get("overrides") or {}).items()
        }

    # -- definitions -----------------------------------------------------------
    def definitions(self) -> dict[str, MaterialDef]:
        return {**self._seed, **self._user_materials}

    def ids(self) -> list[str]:
        return list(self.definitions())

    # -- resolution ------------------------------------------------------------
    def get(self, material_id: str) -> Material:
        return self._resolve(material_id, {})

    def all(self) -> list[Material]:
        cache: dict[str, Material] = {}
        return [self._resolve(mid, cache) for mid in self.definitions()]

    def _resolve(self, material_id: str, cache: dict[str, Material], depth: int = 0) -> Material:
        if material_id in cache:
            return cache[material_id]
        defs = self.definitions()
        if material_id not in defs:
            raise KeyError(material_id)
        if depth > 5:
            raise ValueError(f"composition nesting too deep for {material_id}")
        mdef = defs[material_id]
        props: dict[str, PropertyValue] = {}

        def offer(key: str, value: PropertyValue) -> None:
            if value.value is None:
                return
            current = props.get(key)
            if current is None or ORIGIN_PRECEDENCE[value.origin] > ORIGIN_PRECEDENCE[current.origin]:
                props[key] = value

        # auto (pure elements)
        if mdef.kind == "element" and mdef.symbol:
            for key, val in element_properties(mdef.symbol).items():
                offer(key, val)
        # estimated (alloys)
        if mdef.kind == "alloy" and mdef.composition:
            parts = {c: self._resolve(c, cache, depth + 1) for c in mdef.composition if c in defs}
            if len(parts) == len(mdef.composition):
                for key, val in _estimate_alloy(mdef.composition, parts).items():
                    offer(key, val)
        # manual (seed / user material definition)
        origin = "user" if material_id in self._user_materials else "manual"
        for key, inp in mdef.properties.items():
            offer(key, PropertyValue(origin=origin, **inp.model_dump()))
        # user overrides
        for key, inp in self._overrides.get(material_id, {}).items():
            offer(key, PropertyValue(origin="user", **inp.model_dump()))

        self._add_price(mdef, props, cache, depth)
        _add_derived(props)

        material = Material(
            id=mdef.id, name=mdef.name, kind=mdef.kind, categories=mdef.categories,
            symbol=mdef.symbol, composition=mdef.composition, description=mdef.description,
            user_defined=material_id in self._user_materials,
            has_overrides=bool(self._overrides.get(material_id)),
            properties=props,
        )
        cache[material_id] = material
        return material

    def _add_price(self, mdef: MaterialDef, props: dict[str, PropertyValue],
                   cache: dict[str, Material], depth: int) -> None:
        if mdef.kind == "element":
            entry = self.prices.latest(mdef.id)
            if entry:
                props["price"] = PropertyValue(value=entry.usd_per_gram, origin="price",
                                               source=entry.source, date=entry.date)
            return
        defs = self.definitions()
        total, dates, ignored = 0.0, [], []
        for comp, frac in mdef.composition.items():
            part = self._resolve(comp, cache, depth + 1) if comp in defs else None
            price = part.properties.get("price") if part else None
            if price is None or price.value is None:
                # Base metals without a price are negligible next to precious metals; precious ones are not.
                if part is None or "precious" in part.categories or "precious" not in mdef.categories:
                    return
                ignored.append(comp)
                continue
            total += frac * price.value
            if price.date:
                dates.append(price.date)
        note = "raw material value, no fabrication premium"
        if ignored:
            note += f"; excl. {', '.join(ignored)} (no price, negligible)"
        props["price"] = PropertyValue(
            value=total, origin="price", date=min(dates) if dates else None,
            source="mass-weighted from constituent prices", note=note,
        )

    # -- user changes ----------------------------------------------------------
    def set_overrides(self, material_id: str, values: dict[str, PropertyInput | None]) -> Material:
        if material_id not in self.definitions():
            raise KeyError(material_id)
        current = self._overrides.setdefault(material_id, {})
        for key, val in values.items():
            if key not in EDITABLE_KEYS:
                raise ValueError(f"property '{key}' is not editable")
            if val is None or val.value is None:
                current.pop(key, None)
            else:
                current[key] = val if val.date else val.model_copy(update={"date": date.today().isoformat()})
        if not current:
            self._overrides.pop(material_id, None)
        self._save()
        return self.get(material_id)

    def clear_overrides(self, material_id: str) -> None:
        self._overrides.pop(material_id, None)
        self._save()

    def add_material(self, mdef: MaterialDef) -> Material:
        if mdef.id in self.definitions():
            raise ValueError(f"material id '{mdef.id}' already exists")
        if mdef.kind == "alloy":
            unknown = [c for c in mdef.composition if c not in self.definitions()]
            if unknown:
                raise ValueError(f"unknown constituents: {', '.join(unknown)}")
            if not mdef.composition:
                raise ValueError("alloys need a composition")
        bad = [k for k in mdef.properties if k not in EDITABLE_KEYS]
        if bad:
            raise ValueError(f"properties not editable: {', '.join(bad)}")
        self._user_materials[mdef.id] = mdef
        self._save()
        return self.get(mdef.id)

    def delete_material(self, material_id: str) -> None:
        if material_id not in self._user_materials:
            raise ValueError("only user-defined materials can be deleted")
        used_by = [m.id for m in self.definitions().values() if material_id in m.composition]
        if used_by:
            raise ValueError(f"material is used in: {', '.join(used_by)}")
        del self._user_materials[material_id]
        self._overrides.pop(material_id, None)
        self._save()

    def _save(self) -> None:
        data = {
            "materials": [m.model_dump(exclude_none=True) for m in self._user_materials.values()],
            "overrides": {
                mid: {k: v.model_dump(exclude_none=True) for k, v in props.items()}
                for mid, props in self._overrides.items()
            },
        }
        self.user_file.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def make_id(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")
    return slug or "material"


def _estimate_alloy(comp: dict[str, float], parts: dict[str, Material]) -> dict[str, PropertyValue]:
    def values(key: str) -> dict[str, float] | None:
        out = {}
        for c in comp:
            pv = parts[c].properties.get(key)
            if pv is None or pv.value is None:
                return None
            out[c] = pv.value
        return out

    est: dict[str, PropertyValue] = {}
    density = values("density")
    if density:
        rho = 1.0 / sum(comp[c] / density[c] for c in comp)
        est["density"] = _est(rho, "inverse rule of mixtures")
    for key, label in (("specific_heat", "mass-weighted"), ("fusion_heat", "mass-weighted"),
                       ("melting_point", "mass-weighted; rough – replace with datasheet solidus")):
        vals = values(key)
        if vals:
            est[key] = _est(sum(comp[c] * vals[c] for c in comp), label)
    cte = values("thermal_expansion")
    if density and cte:
        vol = {c: comp[c] / density[c] for c in comp}
        total = sum(vol.values())
        est["thermal_expansion"] = _est(sum(vol[c] / total * cte[c] for c in comp), "volume-weighted")
    return est


def _est(value: float, method: str) -> PropertyValue:
    return PropertyValue(value=value, origin="estimated", source="estimated from composition", note=method)


def _add_derived(props: dict[str, PropertyValue]) -> None:
    def v(key: str) -> float | None:
        pv = props.get(key)
        return None if pv is None else pv.value

    rho, cp, tm, hf = v("density"), v("specific_heat"), v("melting_point"), v("fusion_heat")
    if None not in (rho, cp, tm, hf):
        energy = rho * (cp * (tm - ROOM_TEMPERATURE_C) + hf * 1000.0)  # J/m³
        props["melt_energy_density"] = PropertyValue(
            value=energy * 1e-9, origin="derived", source="ρ·(c_p·(T_m − 25 °C) + h_f)",
        )
    price = v("price")
    if price is not None and rho is not None:
        props["cost_per_volume"] = PropertyValue(
            value=price * rho / 1000.0, origin="derived", source="price · density",
            date=props["price"].date,
        )


def _read_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return list(yaml.safe_load(path.read_text(encoding="utf-8")) or [])


def _read_dict(path: Path) -> dict:
    if not path.exists():
        return {}
    return dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
