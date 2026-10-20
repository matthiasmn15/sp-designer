"""Data models for materials and property values."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Precedence (highest first): user > manual > auto > estimated. derived/price are computed.
Origin = Literal["user", "manual", "auto", "estimated", "derived", "price"]
ORIGIN_PRECEDENCE: dict[str, int] = {"user": 4, "manual": 3, "auto": 2, "estimated": 1}

Category = Literal["precious", "carrier", "core", "alloying"]


class PropertyValue(BaseModel):
    value: float | None = None
    origin: Origin = "manual"
    source: str | None = None
    date: str | None = None
    note: str | None = None


class PropertyInput(BaseModel):
    """Value as entered in a YAML file or by the user (origin is assigned by the loader)."""

    value: float | None = None
    source: str | None = None
    date: str | None = None
    note: str | None = None


class MaterialDef(BaseModel):
    id: str
    name: str
    kind: Literal["element", "alloy"]
    categories: list[Category]
    symbol: str | None = None
    composition: dict[str, float] = Field(default_factory=dict)  # mass fractions, alloys only
    description: str | None = None
    properties: dict[str, PropertyInput] = Field(default_factory=dict)

    @field_validator("composition")
    @classmethod
    def _normalise(cls, comp: dict[str, float]) -> dict[str, float]:
        total = sum(comp.values())
        if comp and total <= 0:
            raise ValueError("composition must have positive fractions")
        return {k: v / total for k, v in comp.items()} if comp else comp


class Material(BaseModel):
    """Material with resolved property values, as delivered to the UI."""

    id: str
    name: str
    kind: Literal["element", "alloy"]
    categories: list[Category]
    symbol: str | None = None
    composition: dict[str, float] = Field(default_factory=dict)
    description: str | None = None
    user_defined: bool = False
    has_overrides: bool = False
    properties: dict[str, PropertyValue]
