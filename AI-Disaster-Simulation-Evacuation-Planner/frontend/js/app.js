/* Wires the UI: select disaster -> generate -> show routes -> simulate -> analytics. */
const $ = id => document.getElementById(id);
const hhmm = s => { const m = Math.floor(s / 60); return String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); };
const say = t => $('msg').textContent = t;
let presets = {}, generated = false;

function setButtons() {
  const run = Sim.isRunning();
  $('bStart').disabled = !generated || run; $('bPause').disabled = !run; $('bResume').disabled = !generated || run;
  $('bStep').disabled = !generated || run; $('bReset').disabled = !generated; $('bCompare').disabled = !generated;
}

function renderCards(st) {
  const m = st.metrics, n = v => v.toLocaleString();
  $('cTime').textContent = hhmm(st.time_s); $('cTotal').textContent = n(m.total_population);
  $('cAffected').textContent = n(m.affected); $('cAtRisk').textContent = n(m.at_risk);
  $('cEvac').textContent = n(m.evacuated); $('cRem').textContent = n(m.remaining);
  $('cShel').textContent = m.shelters_active; $('cBlock').textContent = m.blocked_roads; $('cRer').textContent = m.reroutes;
  $('cRisk').textContent = m.risk_level; $('cRisk').className = 'lvl ' + m.risk_level;
}

function onState(st) { MapView.render(st); renderCards(st); Charts.pushLive(st.metrics); }

function showPlan(p) {
  MapView.drawRoutes(p);
  const b = p.baseline, q = p.proposed;
  if (!b || !q) { $('routeTable').textContent = 'No route available from this origin under current conditions.'; return; }
  const f = (s, k, fn) => fn(s.stats[k]);
  const rows = [['Destination', s => 'Shelter ' + s.shelter_id], ['Distance (km)', s => (s.stats.distance_m / 1000).toFixed(2)],
    ['Est. travel time (min)', s => (s.stats.time_s / 60).toFixed(1)], ['Average risk on route', s => s.stats.avg_risk.toFixed(2)],
    ['Highest risk on route', s => s.stats.max_risk.toFixed(2)], ['Roads in hazard', s => s.stats.hazardous_roads], ['Blocked roads on route', s => s.stats.blocked_roads]];
  $('routeTable').innerHTML = '<table><tr><th>t = ' + hhmm(p.time_s) + '</th><th style="color:#8e24aa">Baseline</th><th style="color:#a57c00">Proposed</th></tr>' +
    rows.map(([l, fn]) => `<tr><td>${l}</td><td>${fn(b)}</td><td>${fn(q)}</td></tr>`).join('') + '</table>';
}

async function generate() {
  Sim.stop(); say('Generating scenario…'); $('bGenerate').disabled = true;
  try {
    const r = await API.post('/disaster/start', {disaster_type: $('disaster').value, intensity: +$('intensity').value,
      scenario_id: $('preset').value, strategy: $('strategy').value});
    MapView.drawStatic(r.layers); Charts.resetLive(); onState(r.state); showPlan(r.plan);
    generated = true; say('Scenario ready. Click the map to choose another origin, or start the evacuation.');
  } catch (e) { say('Could not generate: ' + e.message); }
  $('bGenerate').disabled = false; setButtons();
}

async function pickOrigin(latlng) {
  if (!generated) return;
  try { showPlan(await API.post('/evacuation/plan', {lat: latlng.lat, lon: latlng.lng})); } catch (e) { say(e.message); }
}

const ROWS = [['Evacuation time (min)', 'evacuation_time_s', v => v == null ? 'not completed' : (v / 60).toFixed(1)],
  ['Time to 90% evacuated (min)', 'time_to_90pct_s', v => v == null ? 'not reached' : (v / 60).toFixed(1)],
  ['Avg trip time, arrived only (min)', 'avg_trip_time_s', v => v == null ? '-' : (v / 60).toFixed(1)],
  ['Max trip time, arrived only (min)', 'max_trip_time_s', v => v == null ? '-' : (v / 60).toFixed(1)],
  ['Exposure (person-min in hazard)', 'person_minutes_in_hazard', v => Math.round(v).toLocaleString()],
  ['Success rate', 'success_rate', v => v == null ? '-' : (v * 100).toFixed(1) + '%'],
  ['Shelter utilization', 'shelter_utilization', v => (v * 100).toFixed(1) + '%'],
  ['Peak congestion (load/capacity)', 'congestion_peak', v => v.toFixed(2)],
  ['Route failures', 'route_failures', v => v], ['Reroutes', 'rerouting_count', v => v],
  ['Unserved population', 'unserved_population', v => v.toLocaleString()]];

async function compare() {
  $('bCompare').disabled = true; say('Running baseline and proposed on the same scenario…');
  try {
    const r = await API.get('/analytics'), b = r.baseline.summary, p = r.proposed.summary;
    $('cmp').classList.remove('hidden');
    $('cmpTable').innerHTML = '<table><tr><th>Metric</th><th>Baseline</th><th>Proposed</th></tr>' +
      ROWS.map(([l, k, f]) => `<tr><td>${l}</td><td>${f(b[k])}</td><td>${f(p[k])}</td></tr>`).join('') + '</table>' +
      '<p class="muted">Values come from the two simulation runs just executed. Trip-time rows count only evacuees who reached a shelter.</p>';
    Charts.drawComparison(r); say('');
  } catch (e) { say('Comparison failed: ' + e.message); }
  setButtons();
}

$('intensity').oninput = () => $('intensityVal').textContent = (+$('intensity').value).toFixed(2);
$('speed').oninput = () => $('speedVal').textContent = $('speed').value;
$('preset').onchange = () => $('presetDesc').textContent = presets[$('preset').value].description;
$('bGenerate').onclick = generate;
$('bStart').onclick = async () => { await API.post('/simulation/resume'); Sim.play(); setButtons(); say('Evacuation running.'); };
$('bPause').onclick = async () => { await API.post('/simulation/pause'); Sim.stop(); setButtons(); };
$('bResume').onclick = async () => { await API.post('/simulation/resume'); Sim.play(); setButtons(); };
$('bStep').onclick = async () => { await API.post('/simulation/resume'); await Sim.tick(1); await API.post('/simulation/pause'); };
$('bReset').onclick = async () => { Sim.stop(); Charts.resetLive(); onState(await API.post('/simulation/reset')); setButtons(); say('Reset.'); };
$('bCompare').onclick = compare;
Sim.bind(onState, () => { setButtons(); say('Evacuation finished. Use "Compare" for baseline vs proposed.'); });
MapView.init(pickOrigin); Charts.resetLive();
API.get('/scenarios').then(list => {
  presets = Object.fromEntries(list.map(s => [s.id, s]));
  $('preset').innerHTML = list.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
  $('preset').value = 'expanding'; $('presetDesc').textContent = presets.expanding.description;
});
setInterval(setButtons, 600);
