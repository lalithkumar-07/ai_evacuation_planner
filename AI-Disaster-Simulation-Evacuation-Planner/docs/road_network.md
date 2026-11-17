# Road network (Phase 4)

The graph the simulation runs on is built from the dataset's `edges` by `src/graph/road_graph.py`.

## Edge fields
    u, v           node ids
    distance       metres (> 0)
    road_class     OSM `highway` value or "arterial"/"local" (optional)
    lanes          TOTAL lanes as tagged, 1-12 (optional)
    maxspeed_kph   posted speed limit, 0-200 (optional)
    oneway         true = traffic only from u to v (optional; absent = two-way)
    arterial       legacy flag, used when there is no road_class (optional)

A two-way road becomes two directed edges, a one-way road one. Hazard, risk and congestion are tracked per directed edge.

## Where speed, lanes and capacity come from (highest priority first)
1. the tag on the road (`maxspeed_kph`, `lanes`)
2. its road class (`src/graph/road_classes.py`, overridable under `road_classes:` in `config/simulation_config.yaml`)
3. for files without classes: arterial (50 km/h, 2 lanes) or local (30 km/h, 1 lane), exactly as before Phase 4

Lanes in a class are **per direction**. The OSM `lanes` tag counts all lanes, so a two-way road with `lanes=4` has 2 per
direction; a one-way road keeps all of them. **Capacity** = lanes per direction x capacity_per_lane_m x length, in people.

**The class defaults are generic assumptions, not measurements.** Real roads need local calibration (speeds, lane
capacity, how people actually move in an evacuation). The tags in your data win over the defaults, so tagged data is better.

## Importer (`scripts/build_dataset.py`)
Reads `highway`, `maxspeed`, `lanes`, `oneway` and `junction` from the GeoJSON. Skips roads cars cannot use (footway, path,
pedestrian, steps, cycleway, ...); unknown `highway` values become `unclassified`; `maxspeed` accepts "50", "50 km/h",
"30 mph"; `oneway=-1` is flipped; roundabouts are one-way. Keeps only the largest **strongly** connected network (every
node can reach every other one following one-way directions). All of it is counted in `<name>.manifest.json`.

## Validation
Besides the Phase 3 checks: lanes must be an integer 1-12, `maxspeed_kph` in (0, 200], `oneway` a boolean; unknown classes
warn; and the validator checks **reachability along one-way directions**: it warns when some groups cannot reach any shelter
and refuses the dataset when none can.

## Analytics
* `GET /api/network/summary`: roads, km, lanes, speeds, one-way share, per road class (active dataset).
* `GET /api/network/hotspots?by=exposure|congestion|risk&limit=10`: the worst roads in YOUR simulation. Exposure is cumulative
  person-hazard-minutes of people travelling on that road.
* The map tooltip on a road shows its class, lanes per direction, speed limit and "one-way".

## Performance
The hazard field is recomputed only when it changed (a static disaster is computed once), and each two-way road is evaluated
once instead of twice. Measured on the same machine, best of 3, on a 3,600-node synthetic network:

| | before | after |
|---|---|---|
| hazard update alone | 74 ms | 33 ms |
| whole step, static disaster | 157 ms | 80 ms |
| whole step, growing flood | 151 ms | 141 ms |

A whole step with a growing flood barely changes because most of the step is route computation (Dijkstra from each
evacuee's position), which this phase does not touch. That is the next performance target (Phase 8).

## Limits
Not modelled: turn restrictions, traffic signals, bridges, elevation, road width, vehicle types, walking-only paths.
Presets shrink on datasets smaller than the 6 km demo grid (radii and spread speed, never enlarged); values you type are never scaled.