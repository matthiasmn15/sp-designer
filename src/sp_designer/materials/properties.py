"""Property definitions (single source of truth for units, groups and ranking direction)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Direction = Literal["higher", "lower", "none"]


class PropertyDef(BaseModel):
    key: str
    label: str
    unit: str
    group: str
    description: str
    direction: Direction = "none"  # which direction is better for material selection
    default_weight: float = 0.0
    kind: Literal["number", "rating"] = "number"
    editable: bool = True  # derived and price properties are computed
    decimals: int = 2


PROPERTIES: list[PropertyDef] = [
    # Physical
    PropertyDef(key="density", label="Density", unit="kg/m³", group="Physical", decimals=0,
                description="Mass density at room temperature. Converts electrode volume to precious metal mass."),
    PropertyDef(key="work_function", label="Work function", unit="eV", group="Physical",
                description="Electron work function. Influences cathode fall voltage and electron emission."),
    # Thermal
    PropertyDef(key="melting_point", label="Melting point", unit="°C", group="Thermal", decimals=0,
                direction="higher", default_weight=2,
                description="Melting point (solidus for alloys). Higher melting point reduces melt erosion per spark."),
    PropertyDef(key="thermal_conductivity", label="Thermal conductivity", unit="W/(m·K)", group="Thermal",
                decimals=1, direction="higher", default_weight=1,
                description="Thermal conductivity at room temperature. Higher values lower the electrode tip temperature."),
    PropertyDef(key="specific_heat", label="Specific heat", unit="J/(kg·K)", group="Thermal", decimals=0,
                description="Specific heat capacity at room temperature."),
    PropertyDef(key="fusion_heat", label="Heat of fusion", unit="kJ/kg", group="Thermal", decimals=1,
                description="Latent heat of melting per unit mass."),
    PropertyDef(key="thermal_expansion", label="Thermal expansion", unit="10⁻⁶/K", group="Thermal", decimals=1,
                description="Linear thermal expansion coefficient. A large mismatch between pad and carrier stresses the joint."),
    # Spark behaviour
    PropertyDef(key="melt_energy_density", label="Melt energy density", unit="J/mm³", group="Spark behaviour",
                direction="higher", default_weight=3, editable=False,
                description="Derived: ρ·(c_p·(T_m − 25 °C) + h_f). Energy needed to melt 1 mm³ from room temperature; "
                            "indicator for melt-erosion resistance in the energy-based erosion model. "
                            "Uses room-temperature c_p and ignores oxidation."),
    PropertyDef(key="wear_center", label="Wear per cycle – centre electrode", unit="µm³/cycle",
                group="Spark behaviour", direction="lower", decimals=1,
                description="Volume loss per ignition cycle (one spark per cycle) when the material is used on the "
                            "centre electrode. Manual input from endurance tests for now; to be calculated by the "
                            "wear model later. Used by the lifetime calculation."),
    PropertyDef(key="wear_ground", label="Wear per cycle – ground electrode", unit="µm³/cycle",
                group="Spark behaviour", direction="lower", decimals=1,
                description="Volume loss per ignition cycle (one spark per cycle) when the material is used on the "
                            "ground electrode. Differs from the centre electrode because of polarity. Manual input "
                            "for now; to be calculated by the wear model later."),
    PropertyDef(key="erosion_coefficient", label="Erosion coefficient K", unit="–", group="Spark behaviour",
                direction="lower", decimals=6,
                description="Calibrated material factor of the energy-based erosion model "
                            "(volume loss = K · E / (ρ · Δh_melt)). Reserved for the later calculated wear model."),
    PropertyDef(key="oxidation_resistance", label="Oxidation resistance", unit="1–5", group="Spark behaviour",
                kind="rating", direction="higher", default_weight=2, decimals=0,
                description="Qualitative rating at electrode operating temperature (1 = poor, 5 = excellent)."),
    PropertyDef(key="bead_tendency", label="Bead building tendency", unit="1–5", group="Spark behaviour",
                kind="rating", direction="lower", default_weight=1, decimals=0,
                description="Tendency to form metal beads that bridge the gap (1 = low, 5 = high)."),
    # Economics
    PropertyDef(key="price", label="Price", unit="USD/g", group="Economics", editable=False,
                description="Metal price per gram from the price module. Alloys: mass-weighted from constituents."),
    PropertyDef(key="cost_per_volume", label="Cost per volume", unit="USD/cm³", group="Economics",
                direction="lower", default_weight=2, editable=False,
                description="Derived: price · density. Electrode volume is fixed by geometry, so cost per volume "
                            "is the relevant cost figure for material selection."),
]

PROPERTY_MAP: dict[str, PropertyDef] = {p.key: p for p in PROPERTIES}
EDITABLE_KEYS = [p.key for p in PROPERTIES if p.editable]
