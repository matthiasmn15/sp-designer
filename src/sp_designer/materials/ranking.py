"""Weighted multi-criteria ranking for material selection."""

from __future__ import annotations

from pydantic import BaseModel

from .models import Material
from .properties import PROPERTY_MAP


class RankEntry(BaseModel):
    id: str
    name: str
    score: float | None  # 0..1, weighted mean of normalised criteria
    coverage: float  # share of total weight for which the material has a value
    contributions: dict[str, float]  # criterion -> normalised value 0..1
    rank: int | None = None


def rank_materials(materials: list[Material], weights: dict[str, float]) -> list[RankEntry]:
    """Rank materials by min-max normalised, weighted criteria within the candidate set.

    Criteria without a value for a material are skipped for that material; ``coverage`` shows how much
    of the total weight could be evaluated, so incomplete data stays visible instead of being hidden.
    """
    criteria = {
        k: w for k, w in weights.items()
        if w > 0 and k in PROPERTY_MAP and PROPERTY_MAP[k].direction != "none"
    }
    total_weight = sum(criteria.values())
    ranges: dict[str, tuple[float, float]] = {}
    for key in criteria:
        vals = [m.properties[key].value for m in materials
                if key in m.properties and m.properties[key].value is not None]
        if vals:
            ranges[key] = (min(vals), max(vals))

    entries: list[RankEntry] = []
    for m in materials:
        contributions: dict[str, float] = {}
        for key in criteria:
            pv = m.properties.get(key)
            if pv is None or pv.value is None or key not in ranges:
                continue
            lo, hi = ranges[key]
            norm = 1.0 if hi == lo else (pv.value - lo) / (hi - lo)
            if PROPERTY_MAP[key].direction == "lower":
                norm = 1.0 - norm
            contributions[key] = norm
        used = sum(criteria[k] for k in contributions)
        score = sum(criteria[k] * contributions[k] for k in contributions) / used if used else None
        coverage = used / total_weight if total_weight else 0.0
        entries.append(RankEntry(id=m.id, name=m.name, score=score, coverage=coverage,
                                 contributions=contributions))

    entries.sort(key=lambda e: (e.score is None, -(e.score or 0.0), e.name))
    for i, e in enumerate(entries, start=1):
        e.rank = i if e.score is not None else None
    return entries
