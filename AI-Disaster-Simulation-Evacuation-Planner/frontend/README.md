# Frontend navigation — five views

The existing project keeps a **single FastAPI-served HTML entry point** (`frontend/index.html`). Its five distinct **client-side pages** have dedicated hash URLs and a persistent sidebar, while a shared runtime keeps the current simulation, browser tab session ID, charts, and single Leaflet instance alive when the user navigates.

| Page | URL | Existing content / endpoints |
|---|---|---|
| Dashboard | `/#/dashboard` | Live evacuation progress, population, affected/at-risk counts, blocked roads, shelter availability, event log, trends. Data from `/api/disaster/start` and `/api/simulation/step`. |
| Disaster & Risk Monitoring | `/#/disaster` | Existing disaster configuration form, editable epicentre, hazard/risk layers, live radius, risk distribution (`/api/disaster/risk-map`). |
| Road Network & Traffic | `/#/roads` | Map with road access/risk layers, road classifications and network metrics (`/api/network/summary`), ranked congestion, risk and exposure hotspots (`/api/network/hotspots`). |
| Evacuation Management | `/#/evacuation` | Existing route planner, baseline vs risk-aware route cards, shelter utilization and selection, moving agents, reroute controls (`/api/evacuation/*`). |
| Analytics & Data Sources | `/#/analytics` | Existing baseline-vs-risk-aware report (`/api/analytics`), live performance metrics and dataset-source information (`/api/dataset`). |

No frontend framework, backend calculation, backend endpoint, or routing algorithm has been introduced or replaced.

## Run

From the project root:

```bash
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:8000/`. Visit the five routes through the left sidebar or link directly to a `/#/slug` URL. Changing pages does **not** reset simulation time or change the X-Session-Id header. The session identifier persists for the current tab using the existing `sessionStorage` transport in `js/api.js`.

The site still uses the original CDN-delivered Leaflet and Chart.js, and OSM map tiles; live internet access is necessary for those resources. A plain map basemap is available when tiles do not load.

## Implementation notes

- `js/pages.js` owns the five-view router, page state summaries, road/risk summaries and dataset detail rendering.
- `js/app.js` continues to coordinate simulation state, generation, playback, route plans, comparison and shared keyboard controls; it updates `Pages` from the **same** state response used by the original widgets.
- `js/map.js` continues to create **one** Leaflet map. The router moves its DOM container between three map slots and calls `invalidateSize()` after each move. Layer profiles are page-specific; layer controls still work.
- `js/charts.js`, `js/panels.js` and `js/scenario.js` remain the existing chart, route, KPI, shelter and scenario controllers.
- `css/pages.css` supplements, rather than replaces, the original styles in `css/style.css` and `css/dashboard.css`.
- `js/provenance.js` still fetches `/api/dataset`, updates the header badge and supplies the detailed provenance view.

Some requested data does not exist in the current backend contract. In particular, it does not expose a standalone `SAFE` risk level, a per-road travel-time/capacity field in its hotspot response, or a manifest checksum via `/api/dataset`. The UI explicitly labels these as unavailable instead of inventing values.

## Checks

```bash
python scripts/check_frontend.py
node scripts/check_navigation.js
python scripts/check_five_page_api.py
pytest -q
pytest -q tests/data_pipeline.py
```

`check_navigation.js` is a dependency-free URL-and-navigation logic smoke test, **not** a substitute for visual/browser interaction testing. Validate desktop and mobile layout and browser console after deployment in a browser with network access to the existing CDN scripts.