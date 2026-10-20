"""Design data model. All lengths in mm.

Spark plug types
----------------
``multi_pad``  Several rectangular precious-metal pads facing each other: one centre pad per gap and
               one ground pad per ground electrode (``n_ground`` gaps).
``j_gap``      One electrode pair; each pad round (``diameter``) or rectangular (``width`` × ``height``).
``annular``    Circular electrodes whose cylindrical surfaces face each other (radial gap): a
               precious-metal sleeve on the centre electrode (outer ``diameter``, axial ``length``,
               radial ``thickness``) inside a precious-metal ring on the ground electrode
               (inner diameter = centre diameter + 2 · gap, axial ``length``, radial ``thickness``).
               The ground ring may be split into ``ground_segments`` segments that together cover
               ``ground_coverage`` percent of the circumference.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

PlugType = Literal["multi_pad", "j_gap", "annular"]
PadShape = Literal["rect", "round"]

PLUG_TYPE_LABELS: dict[str, str] = {
    "multi_pad": "Multi-pad (rectangular pads)",
    "j_gap": "J-gap (one electrode pair)",
    "annular": "Annular (cylindrical faces)",
}

_pos = {"gt": 0, "le": 100}


class Electrode(BaseModel):
    material_id: str = "Ir"  # precious metal pad / sleeve
    shape: PadShape = "rect"  # j_gap only; multi_pad is always rect, annular is cylindrical
    width: float = Field(1.5, **_pos)  # rect pad: dimension 1 of the facing surface
    height: float = Field(1.5, **_pos)  # rect pad: dimension 2 of the facing surface
    diameter: float = Field(1.5, **_pos)  # round pad diameter; annular: outer diameter of centre sleeve
    length: float = Field(2.0, **_pos)  # annular: axial length of sleeve / ring
    thickness: float = Field(0.6, **_pos)  # precious metal thickness (radial for annular)
    carrier_id: str | None = "Alloy-600"
    cu_core: bool = False


class Design(BaseModel):
    id: str | None = None
    name: str = Field("Design", min_length=1, max_length=80)
    type: PlugType = "j_gap"
    gap: float = Field(0.3, gt=0, le=5)  # initial electrode gap
    n_ground: int = Field(4, ge=1, le=12)  # multi_pad only
    ground_segments: int = Field(1, ge=1, le=24)  # annular only: 1 = closed ring
    ground_coverage: float = Field(100.0, gt=0, le=100)  # annular only: % of circumference covered
    center: Electrode = Field(default_factory=Electrode)
    ground: Electrode = Field(default_factory=Electrode)
    notes: str | None = None

    @model_validator(mode="after")
    def _check(self) -> "Design":
        if self.type == "annular" and self.center.thickness * 2 >= self.center.diameter:
            raise ValueError("annular: centre sleeve thickness must be smaller than half the diameter")
        return self


class ElectrodeResult(BaseModel):
    face_area: float  # mm², facing surface per gap
    pm_volume: float  # mm³, total over all pads of this electrode
    wearable_volume: float  # mm³, precious metal within the common wear area (all gaps)
    pm_mass: float | None  # mg
    pm_cost: float | None  # USD
    density: float | None
    price: float | None  # USD/g
    price_date: str | None


class DesignResult(BaseModel):
    n_gaps: int
    common_area: float  # mm² per gap = smallest common facing area (used for wear)
    total_wear_area: float  # mm², common area × number of gaps
    ground_inner_diameter: float | None  # annular only
    ground_coverage: float | None = None  # annular only, %
    center: ElectrodeResult
    ground: ElectrodeResult
    pm_volume: float
    pm_mass: float | None
    pm_cost: float | None
    warnings: list[str] = Field(default_factory=list)
