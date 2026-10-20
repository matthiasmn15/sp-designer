"""User settings stored in the user data directory."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Settings(BaseModel):
    price_provider: Literal["umicore", "none"] = "umicore"
    price_max_age_days: int = Field(default=30, ge=1, le=3650)


class SettingsStore:
    def __init__(self, user_dir: Path) -> None:
        self.file = user_dir / "settings.yaml"
        data = yaml.safe_load(self.file.read_text(encoding="utf-8")) if self.file.exists() else None
        self.settings = Settings(**(data or {}))

    def update(self, settings: Settings) -> Settings:
        self.settings = settings
        self.file.write_text(yaml.safe_dump(settings.model_dump(), sort_keys=False), encoding="utf-8")
        return settings
