"""Automatic import of pure-element properties from the mendeleev package."""

from __future__ import annotations

from functools import lru_cache

from .models import PropertyValue

SOURCE = "mendeleev {version} (bundled element database)"


@lru_cache(maxsize=None)
def element_properties(symbol: str) -> dict[str, PropertyValue]:
    """Return SI-converted element properties, or an empty dict if mendeleev is unavailable."""
    try:
        import mendeleev
        from mendeleev import element
    except ImportError:  # pragma: no cover - mendeleev is a hard dependency, but stay robust
        return {}
    try:
        el = element(symbol)
    except Exception:  # noqa: BLE001 - unknown symbol
        return {}
    source = SOURCE.format(version=getattr(mendeleev, "__version__", "?"))
    values: dict[str, float | None] = {
        "melting_point": None if el.melting_point is None else el.melting_point - 273.15,  # K -> °C
        "density": None if el.density is None else el.density * 1000.0,  # g/cm³ -> kg/m³
        "thermal_conductivity": el.thermal_conductivity,  # W/(m·K)
        "specific_heat": None if el.specific_heat_capacity is None else el.specific_heat_capacity * 1000.0,  # J/(g·K) -> J/(kg·K)
        # kJ/mol -> kJ/kg
        "fusion_heat": None if el.fusion_heat is None else el.fusion_heat / el.atomic_weight * 1000.0,
    }
    return {
        key: PropertyValue(value=round(val, 6), origin="auto", source=source)
        for key, val in values.items() if val is not None
    }
