"""Price store. All prices are stored in USD per troy ounce with a date and source."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from ..config import PACKAGE_DATA_DIR

TROY_OUNCE_G = 31.1034768

PriceOrigin = Literal["seed", "manual", "auto"]
_ORIGIN_RANK = {"manual": 3, "auto": 2, "seed": 1}


class PriceEntry(BaseModel):
    metal: str
    value: float  # USD per troy ounce
    date: str  # ISO date
    source: str | None = None
    origin: PriceOrigin = "manual"

    @property
    def usd_per_gram(self) -> float:
        return self.value / TROY_OUNCE_G


class PriceStore:
    def __init__(self, user_dir: Path, seed_file: Path | None = None) -> None:
        self.user_file = user_dir / "prices.yaml"
        self.seed_file = seed_file or PACKAGE_DATA_DIR / "prices" / "seed.yaml"
        self._seed = [PriceEntry(**e, origin="seed") for e in _read_list(self.seed_file)]
        self._user = [PriceEntry(**e) for e in _read_list(self.user_file)]

    # -- queries ---------------------------------------------------------------
    def entries(self) -> list[PriceEntry]:
        return [*self._seed, *self._user]

    def metals(self) -> list[str]:
        return sorted({e.metal for e in self.entries()})

    def latest(self, metal: str) -> PriceEntry | None:
        candidates = [e for e in self.entries() if e.metal == metal]
        if not candidates:
            return None
        return max(candidates, key=lambda e: (e.date, _ORIGIN_RANK[e.origin]))

    def history(self, metal: str) -> list[PriceEntry]:
        return sorted((e for e in self.entries() if e.metal == metal), key=lambda e: e.date)

    # -- updates ---------------------------------------------------------------
    def add(self, entry: PriceEntry) -> None:
        date.fromisoformat(entry.date)  # validate
        # one entry per metal, date and origin
        self._user = [
            e for e in self._user
            if not (e.metal == entry.metal and e.date == entry.date and e.origin == entry.origin)
        ]
        self._user.append(entry)
        self._save()

    def delete(self, metal: str, entry_date: str, origin: PriceOrigin) -> bool:
        before = len(self._user)
        self._user = [
            e for e in self._user
            if not (e.metal == metal and e.date == entry_date and e.origin == origin)
        ]
        changed = len(self._user) != before
        if changed:
            self._save()
        return changed

    def _save(self) -> None:
        data = [e.model_dump() for e in sorted(self._user, key=lambda e: (e.metal, e.date))]
        self.user_file.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _read_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return list(data)
