# Spark Plug Designer – Requirements

Status: draft v0.1 (2026-10-20) – agreed scope from the initial requirements discussion.

## 1. Purpose

Spark Plug Designer helps design engineers create and compare spark plug design variants for **stationary gas engines**. Users define electrode geometry, precious metal and carrier materials, and engine and ignition operating conditions. The tool estimates electrode erosion, gap growth, voltage demand, re-gap interval and lifetime, plus cost and recoverable precious metal at end of life.

## 2. Users and outputs

| Item | Decision |
|---|---|
| Target application | Stationary gas engines |
| Primary users | Design engineers |
| Key output | Side-by-side comparison of design variants |
| Export | CSV and Excel (.xlsx) |
| Uncertainty | Single values for now (ranges may be added later) |
| Units | SI only |
| Deployment | Local only (single user, no login) |
| Platform | Python backend + web UI (browser on localhost) |

## 3. Inputs

### 3.1 Spark plug design
- Electrode configuration – three types in the first version (extensible later):
  1. **Multi-pad:** several rectangular precious-metal pads facing each other (centre electrode vs. several ground electrodes)
  2. **J-gap:** one electrode pair; pads round (disc) or rectangular
  3. **Annular / cylindrical:** circular electrodes whose cylindrical surfaces face each other (radial gap)
- Precious metal per pad: material and **thickness** (pad dimensions per type)
- **Wear area rule:** if the facing areas of ground and centre electrode differ, the **smallest common (overlapping) area** is used for wear calculations
- Centre and ground electrode geometry: pad/tip diameter, length, thickness, shape
- Electrode gap (initial)
- Precious metal per electrode (pad/tip material)
- Carrier (base) material per electrode, incl. optional Cu core
- Joining method (e.g. laser welding, resistance welding) – for information and later failure models

### 3.2 Engine operating conditions
- Pressure at ignition timing
- BMEP
- Engine speed → spark rate
- Air-fuel ratio λ
- Gas type / composition (natural gas, biogas, H₂ blends, …)
- Temperatures (charge temperature at ignition, electrode temperature if known)

### 3.3 Ignition system
- Available secondary voltage
- Spark energy and spark duration
- Polarity (centre electrode negative/positive, AC)
- Current profile (where available)
- Required voltage reserve

## 4. Calculations

### 4.1 Core physics chain

```
erosion per spark (material, energy, polarity, temperature, flow)
   → electrode volume loss and gap growth over operating hours
   → required breakdown voltage (gap, pressure/density at ignition, gas)
   → compare with available voltage minus reserve
   → re-gap interval  (voltage-limited)
   → lifetime         (wear-limited: minimum remaining electrode volume)
```

### 4.2 Lifetime definitions
- **Re-gappable plugs:** the re-gap interval is defined by the **voltage limit** (required voltage reaches available voltage minus reserve). The **lifetime** is limited by **wear** (minimum remaining electrode/precious-metal volume), across all re-gap cycles.
- **Non-re-gappable plugs:** lifetime is the earlier of the voltage limit and the wear limit.

### 4.2a Lifetime page (first version)
- Evaluates **combinations** of electrode designs and materials side by side.
- Wear input: **wear per cycle per material**, entered separately for use on the **centre** and the **ground** electrode (polarity effect). Manual values first; later calculated by the wear model (§4.4, §6).
- Wear volume is applied to the **smallest common facing area** of centre and ground electrode (§3.1) to obtain gap growth.
- Ignition voltage vs. gap: **manual table** for now; later replaced by the Paschen-type breakdown model.
- Result: gap and ignition voltage over operating hours, re-gap interval (voltage limit), lifetime (wear limit), remaining precious metal and cost per operating hour.

### 4.3 Economics
- Precious metal mass per plug (from geometry and density)
- Spark plug material cost (precious metal + carrier) using current metal prices
- Recoverable precious metal at end of life (initial minus eroded volume) and its value
- Cost per operating hour (plug cost / lifetime) for variant comparison

### 4.4 Modelling approach
- **Hybrid:** physics-based structure (breakdown voltage, spark energy, energy-based erosion) with empirical coefficients calibrated to endurance-test and field data.
- Calibration data is **confidential** and must never be committed to the repository (see §7).

## 5. Material module

### 5.1 Materials in scope
- Precious metals: Ir, Pt, Ru, Rh and their alloys (e.g. Ir-Rh, Pt-Ni, Pt-Ir)
- Carrier metals: Ni alloys (e.g. Inconel 600/601-type), with or without Cu core
- Material list must be extensible (new elements and alloys without code changes)

### 5.2 Properties
- Melting point, density, thermal conductivity, specific heat, heat of fusion
- Thermal expansion (mismatch between pad and carrier is critical for joint integrity)
- Oxidation resistance
- Work function
- Wear per cycle, separately for centre and ground electrode (manual now, calculated later)
- Spark erosion coefficient K (for the later calculated wear model)
- **Bead building tendency** = metal bead formation that bridges the gap; qualitative rating 1–5
- Price (with date stamp and source)

### 5.3 Data sources
- Online material databases are used automatically where available; manual entries are possible if not.
- Every value carries a source and date so that origin and age are traceable.
- Metal prices: automatic price feed where possible, otherwise manual input with date stamp.

See `docs/research/material-and-price-data.md` for the source evaluation.

## 6. Spark simulation (research track)

- Scope: 0-D and 1-D models of the spark discharge: breakdown voltage, voltage and current traces, energy split between breakdown/arc/glow phases, channel stretching by flow, restrikes, energy delivered to the electrodes.
- Main purpose: provide better inputs (spark energy per phase, electrode energy) to the erosion model and voltage-demand prediction.
- 2-D/3-D CFD is out of scope as a built-in feature; interfaces to external tools may be considered later.

See `docs/research/spark-simulation.md` for the model survey and recommendation.

## 7. Confidential data handling
- Calibration and test data live outside version control (e.g. `data/confidential/`, git-ignored, or a user-configured path).
- The repository contains only code, public reference data and synthetic example data.

## 8. Application structure and milestones

Main pages of the web UI:

| Page | Sub-pages / content |
|---|---|
| 1 Materials | Compare, Ranking, Charts, Database, Prices |
| 2 Electrode design | Spark plug type, precious metal and thickness per electrode, variant comparison |
| 3 Lifetime | Design/material combinations, wear per cycle, voltage vs. gap, gap and voltage over hours |
| 4 Spark simulation | 0-D / 1-D spark models (research) |

Milestones:

1. **Material database + selection aid** – element/alloy data, automatic import with manual override, price feed, comparison and ranking view.
2. **Design configurator** – geometry and materials, precious metal mass, cost.
3. **Lifetime and re-gap estimation** – energy-based erosion + breakdown voltage model, calibratable.
4. **0-D spark model** – feeds spark energy per phase into milestone 3.
5. **Research track** – 1-D channel model (stretching, restrike), optional CFD coupling.

## 9. Open items
- Format of confidential calibration data (to define the import interface)
- Umicore price feed: verify CSV format and terms of use on a local machine
- Unit of wear per cycle (µm³/cycle assumed) and whether wear depends on operating point
