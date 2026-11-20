"""Five-page frontend API contract smoke test; no backend changes required.

Run from project root: python scripts/check_five_page_api.py
Checks the existing API responses used by dashboard, risk, roads, evacuation and analytics,
with a single session id shared by all calls. Does not require a running HTTP server.
"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from backend.main import app


def main() -> None:
    sid = str(uuid4())
    client = TestClient(app, headers={"X-Session-Id": sid})

    def get(path: str):
        response = client.get('/api' + path)
        assert response.status_code == 200, (path, response.status_code, response.text[:200])
        return response.json()

    def post(path: str, body: dict):
        response = client.post('/api' + path, json=body)
        assert response.status_code == 200, (path, response.status_code, response.text[:200])
        return response.json()

    html = client.get('/').text
    for slug in ('dashboard', 'disaster', 'roads', 'evacuation', 'analytics'):
        assert f'id="page-{slug}"' in html
        assert f'href="#/{slug}"' in html
    print('5 page sections and URL links: OK')

    meta, scenarios, dataset = get('/meta'), get('/scenarios'), get('/dataset')
    assert meta['bounds'] and scenarios and dataset['layers']
    generated = post('/disaster/start', {'scenario_id': 'expanding', 'strategy': 'proposed',
                                         'disaster_type': 'flood', 'intensity': 0.9, 'duration_s': 600})
    assert {'layers', 'state', 'plan'} <= generated.keys()
    assert generated['state']['metrics']['total_population'] > 0
    assert get('/session')['session_id'] == sid
    print('Dashboard and session data: OK')

    risk, affected = get('/disaster/risk-map'), get('/disaster/affected')
    assert risk['nodes'] and {'risk', 'level', 'latlon'} <= risk['nodes'][0].keys()
    assert {'affected', 'at_risk', 'risk_level'} <= affected.keys()
    print('Disaster and risk APIs: OK')

    summary, hotspots = get('/network/summary'), get('/network/hotspots?by=congestion&limit=10')
    assert summary['roads'] and 'by_class' in summary
    assert isinstance(hotspots, list)
    print('Road network and hotspot APIs: OK')

    plan, shelters = post('/evacuation/plan', {}), get('/evacuation/shelters')
    assert 'origin' in plan and 'proposed' in plan and shelters
    st = post('/simulation/step', {'steps': 1})
    assert st['time_s'] > 0 and len(st['roads']) > 0
    assert get('/simulation/status')['time_s'] == st['time_s']
    print('Evacuation routing, shelter and step APIs: OK')

    metrics, compare = get('/metrics'), get('/analytics')
    assert 'success_rate' in metrics
    assert 'baseline' in compare and 'proposed' in compare
    assert 'series' in compare['proposed']
    print('Analytics and dataset APIs: OK')
    print('Five-page API contract smoke test: PASS')


if __name__ == '__main__':
    main()