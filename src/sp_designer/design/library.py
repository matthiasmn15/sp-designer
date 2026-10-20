"""Design library stored in the user data directory (designs may be confidential)."""

from __future__ import annotations

from pathlib import Path

import yaml

from ..materials.database import make_id
from .models import Design


class DesignLibrary:
    def __init__(self, user_dir: Path) -> None:
        self.file = user_dir / "designs.yaml"
        raw = yaml.safe_load(self.file.read_text(encoding="utf-8")) if self.file.exists() else None
        self._designs: dict[str, Design] = {d["id"]: Design(**d) for d in (raw or [])}

    def all(self) -> list[Design]:
        return sorted(self._designs.values(), key=lambda d: d.name.lower())

    def get(self, design_id: str) -> Design:
        return self._designs[design_id]

    def save(self, design: Design) -> Design:
        """Create (no id) or update (existing id) a design."""
        if design.id and design.id in self._designs:
            stored = design
        else:
            base = make_id(design.name)
            new_id, i = base, 2
            while new_id in self._designs:
                new_id, i = f"{base}-{i}", i + 1
            stored = design.model_copy(update={"id": new_id})
        self._designs[stored.id] = stored
        self._write()
        return stored

    def delete(self, design_id: str) -> None:
        del self._designs[design_id]
        self._write()

    def _write(self) -> None:
        data = [d.model_dump() for d in self.all()]
        self.file.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
