# Methodology (prototype)

* **Data:** synthetic 16x16 road grid (400 m spacing), 240 population groups (25 people each), 5 shelters. Labelled synthetic everywhere.
* **Hazard:** radial field `intensity * (1 - d/r(t)) ** falloff`; radius grows at a type-specific speed (flood, wildfire) or is fixed (earthquake).
* **Risk:** `(0.6*hazard + 0.4*forecast_hazard) * (1 + 0.25*exposure)`, clipped to [0,1]. Levels: LOW < 0.25 <= MEDIUM < 0.5 <= HIGH < 0.75 <= CRITICAL.
  The forecast is an oracle extrapolation of the simulator (not a trained model) - results are an upper bound for forecast-driven routing.
* **Road status:** hazard >= 0.6 BLOCKED, >= 0.4 DANGEROUS, >= 0.2 RESTRICTED; load/capacity > 1 CONGESTED. Blocked roads are impassable.
* **Baseline:** nearest shelter by distance, shortest path, no rerouting, ignores capacity/hazard.
* **Proposed:** weighted multi-factor cost, safe + capacity-aware shelter choice with reservations, rerouting on blocked/dangerous routes or unusable shelter.
* **Metrics:** computed from the executed run. Trip-time metrics count only evacuees who arrived.

## Known limitations
* People whose roads are already blocked before they leave cannot leave (counted as unserved/trapped for both strategies).
* Shelter occupants are not relocated if a shelter later becomes unsafe.
* No casualty model; exposure is hazard-weighted time.
* Baseline never reassigns people from full shelters (as specified); a capacity-aware baseline would be a fairer comparison.
