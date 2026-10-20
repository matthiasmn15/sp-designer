# Research: material property and metal price sources

Status: initial survey, 2026-10-20.

## 1. Material properties

| Source | Coverage | Access | Fit |
|---|---|---|---|
| **mendeleev** (Python package, MIT, v1.3.0) | Pure elements: melting point, density, thermal conductivity, specific heat, heat of fusion, … (no work function) | Offline, bundled database | Good for **pure elements** (Ir, Pt, Ru, Rh, Ni, Cu, …) |
| Materials Project API | Computed (DFT) crystal properties | Free API key | Limited: not engineering properties of real alloys |
| CINDAS TPMD and similar | Measured thermophysical data incl. alloys | Commercial licence | Good quality, licence needed |
| Manufacturer datasheets (e.g. Inconel 600/601, Ir-Rh, Pt-Ni) | Engineering alloys | Manual | Required for alloys |
| Literature | Work function, oxidation, erosion | Manual | Required |

**Findings**
- No free online database covers **engineering alloys** (Ir-Rh, Pt-Ni, Inconel) together with spark-specific properties.
- **Spark erosion rate** and **bead building tendency** are not available in any database → curated values / calibration.

**Recommendation**
- Local material database (YAML/JSON in the repo for public data) with fields `value`, `unit`, `source`, `date`, `origin` (`auto` / `manual` / `calibrated`).
- Auto-import of pure-element data from **mendeleev**; alloys and spark properties as manual entries with references; manual values override automatic ones.
- Importer interface designed so that further databases (e.g. a licensed one) can be plugged in later.

## 2. Metal prices

| Source | Pt | Pd | Rh | Ir | Ru | Ni | Notes |
|---|---|---|---|---|---|---|---|
| Metal Sentinel (via RapidAPI) | ✓ | ✓ | ✓ | – | – | ✓ | Free plan 7,500 requests/month |
| Metals.Dev | ✓ | ✓ | ? | – | – | ? | Free plan 100 requests/month |
| MetalpriceAPI | ✓ | ✓ | ? | ? | ? | ? | Free tier, limits not stated |
| Metals-API | ✓ | ✓ | ✓* | ? | ✓* | ✓ (LME) | *advertised; needs verification with the symbols list |
| Johnson Matthey | – | – | – | – | – | – | Publishes supply/demand data, not a price feed |
| **Umicore PMM** | ✓ | ✓ | ✓ | ✓ | ✓ | – | Indicative daily prices; CSV export per metal (`/api/chart/export/csv/{code}/{from}/{to}/AMUS/`); terms of use to be checked |

**Findings**
- Pt, Pd, Rh and Ni prices are readily available via free APIs.
- **Ir and Ru** are thinly traded; free API coverage is uncertain → manual input will likely be needed.
- Prices are in USD per troy ounce; conversion to €/g (or user-chosen currency) is needed.

**Recommendation**
- Price provider interface with a configurable API provider (API key stored locally, never committed) and **manual entry with date stamp** as fallback per metal.
- Show price age in the UI; warn when a price is older than a configurable threshold.
- **Implemented (milestone 1):** Umicore PMM provider for Pt, Pd, Rh, Ir, Ru (can be switched off); manual dated entries for all other metals (e.g. Ni, Cu). The CSV parser is format-tolerant because the export format could not be verified from the development environment.

## Sources
- mendeleev on PyPI: https://pypi.org/project/mendeleev
- Materials Project documentation: https://docs.materialsproject.org/downloading-data/how-do-i-download-the-materials-project-database
- CINDAS TPMD: https://cindasdata.com/products/docs/tpmd/EnglishTPMD_brochure2018.pdf
- Metal Sentinel: https://metal-sentinel.com/
- Metals.Dev: https://metals.dev/
- MetalpriceAPI: https://metalpriceapi.com/
- Metals-API documentation: https://metals-api.com/documentation
- Umicore PMM prices: https://pmm.umicore.com/en/prices/
- Johnson Matthey PGM market data: https://matthey.com/products-and-markets/pgms-and-circularity/pgm-market-data
