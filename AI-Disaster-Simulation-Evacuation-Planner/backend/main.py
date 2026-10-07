"""FastAPI entrypoint. Thin API layer: logic lives in backend/services and src/."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable no matter where this is started from
# (e.g. `cd backend` then `uvicorn main:app`, which otherwise fails with "No module named 'backend'").
_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api import (disaster_routes, evacuation_routes, scenario_routes, session_routes,
                         simulation_routes)
from backend.services.scenario_service import NotFound
from backend.services.session_store import InvalidSessionId
from backend.services.simulation_service import Conflict
from config.settings import FRONTEND_DIR, configure_logging

configure_logging()
app = FastAPI(title="AI Disaster Simulation & Evacuation Planner (prototype, synthetic data)")
for r in (scenario_routes, disaster_routes, evacuation_routes, simulation_routes, session_routes):
    app.include_router(r.router)
app.include_router(scenario_routes.meta_router)


@app.exception_handler(NotFound)
async def _nf(_: Request, exc: NotFound):
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.exception_handler(Conflict)
async def _cf(_: Request, exc: Conflict):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(InvalidSessionId)      # must stay more specific than ValueError below
async def _bad_sid(_: Request, exc: InvalidSessionId):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(ValueError)
async def _ve(_: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=422)


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":          # `python backend/main.py` works too
    from run import main
    main()