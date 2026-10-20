# Spark Plug Designer

Design and comparison tool for spark plugs for stationary gas engines: electrode geometry, precious metal and carrier material selection, re-gap interval, lifetime, cost and end-of-life precious metal.

See `docs/` for requirements and research.

## Status

| Milestone | State |
|---|---|
| 1. Material database + selection aid | ✅ first version |
| 2. Electrode design (multi-pad, J-gap, annular) with precious metal selection and thickness | next |
| 3. Lifetime and re-gap estimation | planned |
| 4. 0-D spark model | planned |

## Run locally

Requires Python ≥ 3.11.

```bash
pip install -e ".[dev]"
sp-designer            # or: python -m sp_designer
```

The app opens at <http://127.0.0.1:8765/>. Options: `--port`, `--host`, `--no-browser`.

Run the tests with `pytest`.

## Material module

- **Compare**: up to four materials (A–D) side by side; differences-only view; click a value to override it.
- **Ranking**: weighted, min–max-normalised scoring within a candidate set (precious, carrier, core, all), with coverage of missing data.
- **Charts**: bar chart per property and a selection map (e.g. melt energy density vs. cost per volume).
- **Database**: add own elements/alloys (composition in mass %), override reference values.
- **Prices**: automatic indicative prices (Umicore PMM: Pt, Pd, Rh, Ir, Ru) or manual entries with date; warning for stale prices.
- **Export**: comparison as CSV (semicolon-separated) or Excel (comparison + sources sheet).

### Where values come from

Every value carries an origin, source and date. Precedence (highest first):

1. `user` – your overrides and own materials
2. `manual` – reference data shipped in `src/sp_designer/data/materials/*.yaml` (datasheets, CRC Handbook)
3. `auto` – pure-element data from the bundled [mendeleev](https://pypi.org/project/mendeleev/) database
4. `estimated` – alloy properties estimated from composition (density: inverse rule of mixtures; c_p, h_f, melting point: mass-weighted; CTE: volume-weighted). Thermal conductivity and work function are not estimated.

Computed values: `derived` (melt energy density ρ·(c_p·(T_m − 25 °C) + h_f), cost per volume) and `price`.

Ratings (oxidation resistance, bead building tendency) and the erosion coefficient are intentionally empty – enter them from your own experience or calibration.

### User data and confidentiality

Overrides, own materials, fetched prices and settings are stored in `~/.sp-designer/` (change with the `SPD_DATA_DIR` environment variable) – **outside the repository**, so confidential values are never committed.
