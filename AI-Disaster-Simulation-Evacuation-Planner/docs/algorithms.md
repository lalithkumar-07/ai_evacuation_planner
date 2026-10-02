# Algorithms

**Baseline route:** Dijkstra (or A* with Euclidean heuristic) on `distance`.

**Proposed edge cost** (`src/routing/risk_aware_route.py`):
`w_distance*km + w_time*min + w_risk*risk*(m/100) + w_congestion*min(load/cap,3)*km + w_accessibility*(1-accessibility)*km`;
blocked edges are removed. Weights live in `config/simulation_config.yaml`.

**Shelter choice** (`src/routing/shelter_assignment.py`): among reachable, non-UNSAFE shelters with room
(`capacity - occupancy - reservations >= group size`) minimise `route_cost + w_shelter_risk*shelter_risk + w_shelter_fill*fill`.

**Rerouting** (`src/simulation/evacuation.py`): each step every active route is checked; if a road ahead is BLOCKED or the shelter is unusable
the failure is counted, and for the proposed strategy the agent replans at its next junction (DANGEROUS roads also trigger replanning).
