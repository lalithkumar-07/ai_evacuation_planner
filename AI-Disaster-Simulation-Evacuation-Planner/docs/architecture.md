# Architecture

    Frontend (Leaflet + Chart.js)  ->  FastAPI routes  ->  services  ->  src/ (pure Python, no web code)

| Layer | Folder | Role |
|---|---|---|
| Config | `config/` | env vars, `simulation_config.yaml` (weights, thresholds), scenario dataclass |
| Data | `src/data/` | dataset JSON loader; synthetic generator (`preprocessing.py`) |
| Disaster | `src/disaster/` | hazard field, risk score/levels, `DisasterManager` (hazard over time, closures) |
| Graph | `src/graph/` | road graph with dynamic edge state (status, congestion, travel time) |
| Routing | `src/routing/` | baseline (distance) vs risk-aware cost; shelter assignment |
| Simulation | `src/simulation/` | agents, evacuation controller (movement, failure detection, rerouting), time loop, metrics |
| AI | `src/ai/` | predictor interface (currently a deterministic oracle, NOT trained) |
| API | `backend/` | schemas (validation), services (session, scenarios, route planning), routes |

Dynamic loop per step: hazard -> risk -> road status/traffic -> flag broken routes -> start/move agents
(reroute if strategy is dynamic) -> loads -> metrics.

To use real data: write a converter that outputs the same JSON as `demo_scenario.json`
(`nodes`, `edges`, `population`, `shelters`, `meta`) and point `PLANNER_DATA_DIR` / `DEMO_SCENARIO_PATH` at it.
To plug in ML: implement `RiskPredictor.predict_hazard` and pass it to `Simulation(predictor=...)`.
