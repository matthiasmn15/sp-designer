# Research: 0-D / 1-D spark simulation

Status: initial survey, 2026-10-20.

## 1. Goal

Find out which reduced-order (0-D / 1-D) spark models exist and which are realistic to implement, so that they can feed the erosion and voltage-demand models (ignition voltage, current, energy per phase, electrode impact, flow effects).

## 2. What a spark discharge model has to cover

| Phase | Duration | Relevance for Spark Plug Designer |
|---|---|---|
| Breakdown | ns | Sets **voltage demand**; high-power phase that contributes strongly to erosion |
| Arc | µs | High current, cathode spot – erosion |
| Glow | ms | Most of the energy in inductive systems; channel stretched by flow |
| Restrikes / short circuits / blow-out | during glow | Additional breakdowns → extra erosion; depend on flow velocity |

## 3. Model levels found

### 3.1 0-D: secondary circuit + energy balance (recommended first step)

- **Secondary circuit:** coil primary energy (from primary inductance and peak current) → transfer to secondary with an efficiency factor (≈60 % typical) → secondary current from stored energy and secondary inductance; glow phase decays with secondary resistance and the voltage drop across the gap. This is the structure used e.g. in the ANSYS Forte arc channel model documentation.
- **Gap voltage during glow:** sum of cathode fall, anode fall and a column term that depends on channel length and pressure (correlations from Kim et al.; cathode fall depends on electrode material via work function/secondary emission coefficient).
- **Energy split:** stored coil energy is split between the gap, the plug's internal resistor and residual coil energy (Tambasco et al. 2021 measured this; electrical-to-thermal conversion rises with cross-flow, up to about 80 %).
- **Outputs:** voltage/current traces, spark duration, energy in gap, energy per phase.
- **Effort:** low; pure ODE system, fast enough for parameter studies inside the tool.

### 3.2 Breakdown voltage (needed in any case)

- **Paschen-type correlations** in pressure × gap (or density × gap), e.g. Pashley et al. (function of pressure, temperature, gap; used in ANSYS Forte for the restrike criterion) and Huang et al. (up to 40 bar).
- Measurements on 18 mm natural-gas J-gap and 4-ground-strap plugs (Tambasco, Hall, Matthews, SAE 2022-01-0437) show: linear rise at low pressure, flattening above ≈10 bar; air needs considerably higher voltage than N₂ (up to ~2×); methane addition changes voltage by tens of percent. → **Gas composition must be an input**, and the correlation must be calibrated at engine-relevant pressures.
- Erosion increases breakdown voltage over time, fastest early in life as sharp edges round off (Tambasco et al., SAE 2024-01-2100). → The model needs an **electrode-shape factor** (sharp → rounded), not just gap distance.

### 3.3 1-D / Lagrangian channel models (research track)

- The spark channel is represented as a chain of particles convected by the local gas velocity; channel length → column voltage → restrike when gap voltage exceeds breakdown voltage; short circuit when the channel touches the electrode.
- Examples: arc and kernel tracking (AKTIM-type) models; ANSYS Forte arc channel tracking; Argonne **LESI** model with secondary circuit, short-circuit, blow-out and restrike sub-models (Kazmouz, Scarcelli et al., Combustion and Flame 2023). LESI is coupled to CONVERGE via UDFs and available after registration – not open source.
- **Standalone use:** these models can be run without CFD by prescribing a velocity at the gap (uniform cross-flow, or a value from engine CFD/measurement). This gives restrike frequency and spark duration vs. flow velocity – the main flow impact relevant to erosion.
- Experimental trends to reproduce: restrike frequency rises with flow; time to first restrike drops sharply up to ~5–10 m/s and then levels off; arc resistance ≈2 kΩ/mm of stretched length (Tambasco et al. 2021).

### 3.4 Multi-dimensional plasma (not built in)

- Thermal plasma solvers (e.g. VizSpark) resolve plasma temperature, electrode heat flux and crater formation. Breden, Karpatne, Suzuki, Raja (KIT proceedings) simulated spark plug erosion with an energy-based erosion model: mass removed ∝ input energy / (density × melting enthalpy) × material factor K (K ≈ 2.1·10⁻⁵ fitted across W, Ir, Ni, Pt, Ag); found cross-flow increases erosion and shifts it downwind, and breakdown removes more mass than the arc phase.
- Cost: days on many cores for a handful of pulses → only suitable for generating correlations offline, not inside the tool.
- **Plasma temperature** is only meaningfully available from this level; in 0-D/1-D it would be an assumed value.

## 4. Erosion model link

The surveyed literature supports this structure for the tool:

```
volume loss per spark = Σ_phases  K_material,phase · E_electrode,phase / (ρ · Δh_melt)
```

- `E_electrode,phase` from the 0-D/1-D spark model (or from user-entered spark energy split)
- `K_material` calibrated with confidential endurance data (per material, polarity, electrode position)
- Correction factors for electrode temperature / oxidation (oxidation-dominated wear is a separate mechanism, see Rager et al. 2005 on oxidation damage of electrodes)
- Pt-based plugs erode significantly more than Ir-based plugs under identical conditions (Tambasco et al. 2024) – a good plausibility check for the first calibration.

## 5. Recommendation

1. **Milestone 4:** implement the 0-D secondary-circuit model + Paschen/Pashley-type breakdown correlation with calibration coefficients. Inputs come from the ignition system section of the configurator.
2. **Research track:** add a 1-D Lagrangian channel with prescribed gap velocity for restrike/stretching effects; validate against published trends first, then own measurements.
3. Treat plasma temperature and detailed electrode heat flux as **out of scope** for the tool; if needed, import results from external plasma/CFD tools as correlations.
4. No suitable open-source reduced-order spark model was found → implement own models in Python (SciPy ODE solvers), based on the published formulations above.

## Sources

- ANSYS Forte theory manual – Arc channel tracking model: https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/forte_th/ch07s02.html
- Kazmouz, Scarcelli et al. (2023), comprehensive electrical discharge and spark channel model (LESI), Combustion and Flame: https://www.anl.gov/argonne-scientific-publications/pub/180193
- Argonne LESI model: https://www.anl.gov/taps/lesi-model
- Tambasco, Li, Hall, Matthews (2021), SAE 2021-01-1157, spark discharge under quiescent and convective flows: https://par.nsf.gov/servlets/purl/10318411
- Tambasco, Hall, Matthews (2022), SAE 2022-01-0437, discharge characteristics vs. geometry and gas composition: https://par.nsf.gov/servlets/purl/10398255
- Tambasco, Hall, Matthews (2024), SAE 2024-01-2100, operating conditions vs. electrode erosion: https://saemobilus.sae.org/papers/effects-spark-plug-operating-conditions-electrode-erosion-surface-deformation-2024-01-2100
- Breden, Karpatne, Suzuki, Raja – High-fidelity numerical modelling of spark plug erosion (KIT): https://publikationen.bibliothek.kit.edu/1000088318/20138236
- Rager et al. (2005), Oxidation damage of spark plug electrodes: https://onlinelibrary.wiley.com/doi/pdf/10.1002/adem.200500025
- Field-service erosion and failure in natural gas engines: https://www.researchgate.net/publication/228417855_Characterization_of_erosion_and_failure_processes_of_spark_plugs_after_field_service_in_natural_gas_engines
- Effect of electrode erosion on required ignition voltage, CNG engine: https://www.researchgate.net/publication/358190355_Effect_of_electrode_erosion_on_the_required_ignition_voltage_of_spark_plug_in_CNG_spark_ignition_engine
