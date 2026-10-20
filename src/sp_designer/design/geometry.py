"""Geometry and precious-metal calculations for electrode designs.

Wear area rule: if the facing areas of centre and ground electrode differ, the smallest common
(overlapping) area is used for wear calculations. Pads are assumed to be aligned (centred) on a
common axis.
"""

from __future__ import annotations

import math

from ..materials.database import MaterialDatabase
from .models import Design, DesignResult, Electrode, ElectrodeResult


def pad_area(e: Electrode, shape: str) -> float:
    return math.pi / 4 * e.diameter ** 2 if shape == "round" else e.width * e.height


def overlap_area(a: Electrode, shape_a: str, b: Electrode, shape_b: str) -> float:
    """Overlap of two centred, coaxial pad faces."""
    if shape_a == "rect" and shape_b == "rect":
        return min(a.width, b.width) * min(a.height, b.height)
    if shape_a == "round" and shape_b == "round":
        return math.pi / 4 * min(a.diameter, b.diameter) ** 2
    disc, rect = (a, b) if shape_a == "round" else (b, a)
    return disc_rect_overlap(disc.diameter / 2, rect.width, rect.height)


def disc_rect_overlap(r: float, w: float, h: float) -> float:
    """Exact area of a disc of radius r intersected with a centred w × h rectangle."""
    a, b = w / 2, h / 2

    def strip(x: float) -> float:
        # integral of min(sqrt(r² − t²), b) dt from 0 to x (x ≤ r)
        xc = math.sqrt(max(r * r - b * b, 0.0))  # where the circle drops below b
        def circ(t: float) -> float:
            return 0.5 * (t * math.sqrt(max(r * r - t * t, 0.0)) + r * r * math.asin(min(t / r, 1.0)))
        if b >= r:
            return circ(x)
        if x <= xc:
            return b * x
        return b * xc + circ(x) - circ(xc)

    return 4 * strip(min(a, r))


def evaluate(design: Design, db: MaterialDatabase) -> DesignResult:
    warnings: list[str] = []
    c, g = design.center, design.ground

    if design.type == "multi_pad":
        n = design.n_ground
        face_c, face_g = pad_area(c, "rect"), pad_area(g, "rect")
        common = overlap_area(c, "rect", g, "rect")
        vol_c, vol_g = n * face_c * c.thickness, n * face_g * g.thickness
        inner_d = None
    elif design.type == "j_gap":
        n = 1
        face_c, face_g = pad_area(c, c.shape), pad_area(g, g.shape)
        common = overlap_area(c, c.shape, g, g.shape)
        vol_c, vol_g = face_c * c.thickness, face_g * g.thickness
        inner_d = None
    else:  # annular
        n = 1
        inner_d = c.diameter + 2 * design.gap
        overlap_len = min(c.length, g.length)
        face_c = math.pi * c.diameter * c.length
        face_g = math.pi * inner_d * g.length
        common = math.pi * c.diameter * overlap_len  # the centre surface is the smaller one
        vol_c = math.pi / 4 * (c.diameter ** 2 - (c.diameter - 2 * c.thickness) ** 2) * c.length
        vol_g = math.pi / 4 * ((inner_d + 2 * g.thickness) ** 2 - inner_d ** 2) * g.length
        if c.length != g.length:
            warnings.append("Axial lengths differ: only the overlapping length counts for wear.")

    if design.type != "annular" and abs(face_c - face_g) > 1e-9:
        smaller = "centre" if face_c < face_g else "ground"
        warnings.append(f"Facing areas differ: the {smaller} pad defines the common wear area.")

    res_c = _electrode_result(c, face_c, vol_c, common * c.thickness * n, db, "centre", warnings)
    res_g = _electrode_result(g, face_g, vol_g, common * g.thickness * n, db, "ground", warnings)

    def total(a: float | None, b: float | None) -> float | None:
        return None if a is None or b is None else a + b

    return DesignResult(
        n_gaps=n, common_area=common, total_wear_area=common * n, ground_inner_diameter=inner_d,
        center=res_c, ground=res_g, pm_volume=vol_c + vol_g,
        pm_mass=total(res_c.pm_mass, res_g.pm_mass), pm_cost=total(res_c.pm_cost, res_g.pm_cost),
        warnings=warnings,
    )


def _electrode_result(e: Electrode, face: float, volume: float, wearable: float, db: MaterialDatabase,
                      label: str, warnings: list[str]) -> ElectrodeResult:
    try:
        mat = db.get(e.material_id)
    except KeyError:
        warnings.append(f"Unknown {label} material '{e.material_id}'.")
        mat = None
    density = price = None
    price_date = None
    if mat is not None:
        if "precious" not in mat.categories:
            warnings.append(f"{label.capitalize()} pad material {mat.name} is not a precious metal.")
        d = mat.properties.get("density")
        p = mat.properties.get("price")
        density = d.value if d else None
        price, price_date = (p.value, p.date) if p else (None, None)
        if density is None:
            warnings.append(f"No density for {mat.name}: mass and cost not available.")
        elif price is None:
            warnings.append(f"No price for {mat.name}: cost not available.")
    if e.carrier_id:
        try:
            db.get(e.carrier_id)
        except KeyError:
            warnings.append(f"Unknown {label} carrier material '{e.carrier_id}'.")
    mass = volume * density * 1e-3 if density is not None else None  # mm³ · kg/m³ → mg
    cost = mass * 1e-3 * price if mass is not None and price is not None else None  # mg → g
    return ElectrodeResult(face_area=face, pm_volume=volume, wearable_volume=wearable, pm_mass=mass,
                           pm_cost=cost, density=density, price=price, price_date=price_date)
