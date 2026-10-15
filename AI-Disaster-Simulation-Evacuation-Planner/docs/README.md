# Data pipeline (Phase 3)

    data/raw/*  ──►  scripts/build_dataset.py  ──►  data/processed/<name>.json (+ .manifest.json)  ──►  PLANNER_DATASET  ──►  app
    (as downloaded)   importers + validation          one file, one contract                              (validated on load)

Synthetic and real data share one **contract** and are kept apart by **provenance**.

## The dataset file
    meta        name, frame?, provenance?, assumptions?, description?
    nodes       [{id, x, y}]                 metres east / north of the south-west corner of the frame
    edges       [{u, v, distance, arterial, road_class?}]    undirected; distance in metres > 0
    population  [{id, node, size, mobility, vulnerability?, warning_delay_s?}]   mobility: walking | vehicle
    shelters    [{id, node, capacity, occupancy?, name?}]    ids must be 0, 1, 2, ... in order

`meta.frame = {lat0, lon0, cos_lat, width_m, height_m}` places the metre coordinates on the globe (equirectangular
projection from the south-west corner). Files without a frame (the original synthetic grid) are centred on
PLANNER_ORIGIN_LAT/LON as before.

`meta.provenance` has one entry per layer (`roads`, `population`, `shelters`):
`{source: synthetic | real | derived, origin, sha256, license, notes}`. The dataset's kind is `synthetic` if every
layer is synthetic, `real` if none is, otherwise `mixed`. The UI shows this next to the title.

## Rules the validator enforces (src/data/schema.py)
Errors stop the app from loading the file: missing keys, duplicate ids, edges to unknown nodes or with distance <= 0,
population or shelters pointing at unknown nodes, capacity <= 0, occupancy > capacity, bad mobility, invalid frame,
shelter ids not 0..n-1, invalid provenance. Warnings are logged and shown at `GET /api/dataset`: disconnected road
parts, people or shelters outside the main network, capacity below the population, more than 5,000 nodes (slow).

## What the importer does and assumes
* Roads: vertices closer than `--snap-m` (1 m) become one node. Only the largest connected network is kept, and the
  frame is computed from the part that is kept. Arterial = `highway` in motorway, trunk, primary, secondary (+ links).
* Population and shelters are snapped to the nearest road node; points farther than `--max-snap-distance` (500 m) are dropped.
* **Assumed, because the inputs do not contain it:** walking share (`--walking-fraction`), warning delays
  (`--max-warning-delay`), group size, and road capacity/speed (from arterial vs local only). These are written into
  `meta.assumptions` and shown in the UI tooltip. Real values should replace them when available.
* Everything dropped is counted in `<name>.manifest.json`, together with SHA-256 checksums of the inputs and output.
  The same inputs and seed always give the same output file.

## Known limits
* Defaults (disaster radii of 600-2,500 m, evacuation radius 2,500 m) are sized for the 6 km demo grid. On a small
  area, lower them (or the whole map is inside the hazard).
* Routing is recomputed every step: networks above a few thousand nodes are slow (Phase 4/performance work).
* Road capacity and speed are still two classes (arterial / local); richer road attributes belong to Phase 4.
* One active dataset per server process (PLANNER_DATASET); choosing a dataset per user is not built yet.