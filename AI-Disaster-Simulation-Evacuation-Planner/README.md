# AI Disaster Simulation & Evacuation Planner (review MVP)

Flow: **select disaster -> show affected area -> population / shelters / roads -> baseline vs risk-aware route -> run simulation -> metrics.**

> **Prototype.** All roads, population and shelters are **synthetic**. No ML model is trained
> (*Model training not yet performed*). Results show behaviour of the simulation, not real disasters.

## Run
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python scripts/generate_sample_data.py     # writes data/sample/demo_scenario.json (synthetic)
    python run.py                              # http://127.0.0.1:8000
    pytest                                     # tests
    python scripts/run_simulation.py combined  # headless baseline vs proposed table

## Demo script (5 minutes)
1. Pick **Flood**, intensity 0.9, preset *Expanding disaster*, click **Generate scenario**.
2. Show the risk map (green -> red points), disaster circle, population (blue), shelters, blocked roads.
3. Read the **route plan table**: the proposed route is longer but passes through less hazard. Click elsewhere on the map to try other origins.
4. **Start evacuation**: watch time, evacuated, at-risk, blocked roads and reroutes change.
5. **Compare baseline and proposed** for the full-run metrics. Try the *Shelter failure* and *Combined* presets.

## Layout
See `docs/architecture.md`. Not implemented yet: ML predictors, real datasets, database, Docker, notebooks.
