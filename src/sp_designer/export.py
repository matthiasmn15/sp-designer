"""CSV and Excel export of material comparisons."""

from __future__ import annotations

import csv
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .materials.models import Material
from .materials.properties import PROPERTIES


def comparison_rows(materials: list[Material]) -> list[list]:
    header = ["Group", "Property", "Unit", *[m.name for m in materials]]
    rows: list[list] = [header]
    for p in PROPERTIES:
        values = []
        for m in materials:
            pv = m.properties.get(p.key)
            values.append(None if pv is None or pv.value is None else round(pv.value, max(p.decimals, 3)))
        rows.append([p.group, p.label, p.unit, *values])
    return rows


def source_rows(materials: list[Material]) -> list[list]:
    rows: list[list] = [["Material", "Property", "Value", "Unit", "Origin", "Source", "Date", "Note"]]
    for m in materials:
        for p in PROPERTIES:
            pv = m.properties.get(p.key)
            if pv is None or pv.value is None:
                continue
            rows.append([m.name, p.label, pv.value, p.unit, pv.origin, pv.source, pv.date, pv.note])
    return rows


def to_csv(materials: list[Material]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")  # semicolon: opens correctly in German-locale Excel
    writer.writerows(comparison_rows(materials))
    return buf.getvalue()


def to_xlsx(materials: list[Material]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Comparison"
    _write(ws, comparison_rows(materials))
    _write(wb.create_sheet("Sources"), source_rows(materials))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _write(ws, rows: list[list]) -> None:
    for row in rows:
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="5B4FC4")
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"
    for idx, column in enumerate(ws.columns, start=1):
        width = max(len(str(c.value)) if c.value is not None else 0 for c in column)
        ws.column_dimensions[get_column_letter(idx)].width = min(max(width + 2, 10), 60)


# ---------------------------------------------------------------- electrode designs
def design_rows(designs: list, results: list) -> list[list]:
    """Wide table: one column per design variant."""
    from .design.models import PLUG_TYPE_LABELS

    def r(v, digits=3):
        return None if v is None else round(v, digits)

    def el(d, side, key):
        e = getattr(d, side)
        relevant = {
            "multi_pad": {"width", "height", "thickness"},
            "j_gap": {"width", "height", "thickness"} if e.shape == "rect" else {"diameter", "thickness"},
            "annular": ({"diameter", "length", "thickness"} if side == "center" else {"length", "thickness"}),
        }[d.type]
        return getattr(e, key) if key in relevant else None

    rows: list[list] = [["Group", "Parameter", "Unit", *[d.name for d in designs]]]
    spec = [
        ("General", "Spark plug type", "", lambda d, x: PLUG_TYPE_LABELS[d.type]),
        ("General", "Initial gap", "mm", lambda d, x: d.gap),
        ("General", "Number of gaps", "–", lambda d, x: x.n_gaps),
    ]
    for side, label in (("center", "Centre electrode"), ("ground", "Ground electrode")):
        spec += [
            (label, "Precious metal", "", lambda d, x, s=side: getattr(d, s).material_id),
            (label, "Pad shape", "", lambda d, x, s=side: getattr(d, s).shape if d.type == "j_gap" else
             ("rect" if d.type == "multi_pad" else "cylindrical")),
            (label, "Width", "mm", lambda d, x, s=side: el(d, s, "width")),
            (label, "Height", "mm", lambda d, x, s=side: el(d, s, "height")),
            (label, "Diameter", "mm", lambda d, x, s=side: el(d, s, "diameter")),
            (label, "Axial length", "mm", lambda d, x, s=side: el(d, s, "length")),
            (label, "Precious metal thickness", "mm", lambda d, x, s=side: el(d, s, "thickness")),
            (label, "Carrier", "", lambda d, x, s=side: getattr(d, s).carrier_id),
            (label, "Cu core", "", lambda d, x, s=side: "yes" if getattr(d, s).cu_core else "no"),
            (label, "Facing area per gap", "mm²", lambda d, x, s=side: r(getattr(x, s).face_area)),
            (label, "Precious metal volume", "mm³", lambda d, x, s=side: r(getattr(x, s).pm_volume)),
            (label, "Wearable volume", "mm³", lambda d, x, s=side: r(getattr(x, s).wearable_volume)),
            (label, "Precious metal mass", "mg", lambda d, x, s=side: r(getattr(x, s).pm_mass, 2)),
            (label, "Precious metal cost", "USD", lambda d, x, s=side: r(getattr(x, s).pm_cost, 2)),
        ]
    spec += [
        ("Results", "Common (wear) area per gap", "mm²", lambda d, x: r(x.common_area)),
        ("Results", "Total wear area", "mm²", lambda d, x: r(x.total_wear_area)),
        ("Results", "Ground ring inner diameter", "mm", lambda d, x: r(x.ground_inner_diameter)),
        ("Results", "Precious metal volume (plug)", "mm³", lambda d, x: r(x.pm_volume)),
        ("Results", "Precious metal mass (plug)", "mg", lambda d, x: r(x.pm_mass, 2)),
        ("Results", "Precious metal cost (plug)", "USD", lambda d, x: r(x.pm_cost, 2)),
        ("Results", "Warnings", "", lambda d, x: " | ".join(x.warnings) or None),
    ]
    for group, label, unit, fn in spec:
        rows.append([group, label, unit, *[fn(d, x) for d, x in zip(designs, results)]])
    return rows


def rows_to_csv(rows: list[list]) -> str:
    buf = io.StringIO()
    csv.writer(buf, delimiter=";").writerows(rows)
    return buf.getvalue()


def rows_to_xlsx(rows: list[list], title: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title
    _write(ws, rows)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
