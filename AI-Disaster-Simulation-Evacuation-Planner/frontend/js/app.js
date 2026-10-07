/* Application wiring: select disaster -> generate -> inspect routes -> simulate -> compare. */
const App = (() => {
  let generated = false, dirty = false, busy = false, again = false, lastState = null, lastOrigin = null, duration = 10800, first = true;

  /* ---- theme / layout ------------------------------------------------------------------------------------- */
  function applyTheme(t) {
    document.body.dataset.theme = t;
    $('themeIcon').setAttribute('href', t === 'dark' ? '#i-sun' : '#i-moon');
    try { localStorage.setItem('evac.theme', t); } catch (e) { /* ignore */ }
  }
  function initTheme() {
    let t = null; try { t = localStorage.getItem('evac.theme'); } catch (e) { /* ignore */ }
    applyTheme(t || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  }
  const setView = v => { document.body.dataset.view = v; qsa('.tabbar button').forEach(b => b.toggleAttribute('aria-current', b.dataset.view === v)); if (v === 'map') setTimeout(MapView.invalidate, 50); };
  const qsa = s => [...document.querySelectorAll(s)];
  function setTab(name) {
    qsa('.tabs button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === name)));
    ['live', 'routes', 'compare'].forEach(n => $('tab-' + n).classList.toggle('hidden', n !== name));
  }
  const showApiError = e => { $('apiErrorText').textContent = e.message; $('apiError').classList.remove('hidden'); };

  /* ---- generate ------------------------------------------------------------------------------------------- */
  function updateButtons() {
    const run = Sim.isRunning(), g = $('bGenerate');
    g.disabled = busy; g.classList.toggle('dirty', dirty && !busy); g.classList.toggle('busy', busy);
    g.textContent = busy ? 'Generating' : generated ? 'Regenerate' : 'Generate';
    ['bPlay', 'bStep', 'bReset', 'bRecalc', 'bReroute', 'bCompare', 'bApplyLive'].forEach(id => $(id).disabled = !generated || (id === 'bStep' && run));
    $('bReroute').disabled = !generated || Scenario.strategy() !== 'proposed';
    $('playIcon').setAttribute('href', run ? '#i-pause' : '#i-play');
    $('bPlay').setAttribute('aria-label', run ? 'Pause' : 'Play');
  }

  async function generate() {
    if (busy) { again = true; return; }
    busy = true; Sim.pause(); updateButtons();
    try {
      const r = await API.post('/disaster/start', Scenario.payload());
      duration = r.layers.scenario.duration_s;
      Panels.setLevels(r.layers.risk_levels); MapView.drawStatic(r.layers, first); first = false;
      MapView.setPreview(Scenario.preview());
      Charts.reset(); Panels.reset(); onState(r.state);
      lastOrigin = null; Panels.setPlan(r.plan); MapView.drawRoutes(r.plan, false);
      generated = true; dirty = false;
    } catch (e) { toast(e.message, 'error', 5000); if (e.network) showApiError(e); }
    busy = false; updateButtons();
    if (again) { again = false; generate(); }
  }
  const autoGenerate = debounce(() => { if ($('autoUpdate').checked && !Sim.isRunning()) generate(); }, 650);

  function onFormChange() {
    dirty = true; MapView.setPreview(Scenario.preview()); updateButtons();
    if (generated) autoGenerate();
  }

  /* ---- simulation ---------------------------------------------------------------------------------------- */
  function onState(st) {
    lastState = st; MapView.render(st); Panels.update(st); Charts.push(st.metrics);
    $('clock').textContent = fmtClock(st.time_s); $('clockOf').textContent = 'of ' + fmtClock(duration);
    $('trackFill').style.width = Math.min(100, 100 * st.time_s / duration) + '%';
  }
  async function resetSim() {
    Sim.pause(); Charts.reset(); Panels.reset(); onState(await API.post('/simulation/reset')); updateButtons();
  }
  async function togglePlay() {
    if (!generated) return;
    if (Sim.isRunning()) { Sim.pause(); return; }
    if (dirty) await generate(); else if (lastState && lastState.finished) await resetSim();
    Sim.play();
  }
  async function step() {
    if (!generated || Sim.isRunning()) return;
    if (dirty) await generate(); else if (lastState && lastState.finished) await resetSim();
    await Sim.step();
  }

  /* ---- routes / compare / live adjust ------------------------------------------------------------------- */
  async function plan(ll) {
    try {
      lastOrigin = ll || null;
      const p = await API.post('/evacuation/plan', ll ? {lat: ll.lat, lon: ll.lng} : {});
      Panels.setPlan(p); MapView.drawRoutes(p, !!ll); setTab('routes'); if (ll) toast('Routes updated for this origin. See Insights > Routes.', 'info', 2600);
    } catch (e) { toast(e.message, 'error'); }
  }
  async function compare() {
    const b = $('bCompare'); b.classList.add('busy'); b.disabled = true;
    try { if (dirty) await generate(); Panels.setCompare(await API.get('/analytics')); }
    catch (e) { toast('Comparison failed: ' + e.message, 'error', 5000); }
    b.classList.remove('busy'); updateButtons();
  }
  async function applyLive() {
    try { onState(await API.post('/disaster/update', Scenario.liveParams())); toast('Applied to the running simulation', 'good'); }
    catch (e) { toast(e.message, 'error'); }
  }

  /* ---- boot ------------------------------------------------------------------------------------------------ */
  function wire() {
    $('bTheme').onclick = () => { const t = document.body.dataset.theme === 'dark' ? 'light' : 'dark'; applyTheme(t); MapView.setTheme(t); Charts.restyle(); };
    $('bHelp').onclick = () => $('helpDlg').showModal();
    $('bRetry').onclick = () => { $('apiError').classList.add('hidden'); boot(); };
    $('bGenerate').onclick = generate; $('bApplyLive').onclick = applyLive;
    $('bPlay').onclick = togglePlay; $('bStep').onclick = step; $('bReset').onclick = () => resetSim().catch(e => toast(e.message, 'error'));
    $('bRecalc').onclick = () => plan(lastOrigin);
    $('bReroute').onclick = async () => { try { const r = await API.post('/evacuation/reroute'); toast(`${r.flagged} group(s) will re-plan at their next junction`, 'good'); } catch (e) { toast(e.message, 'error'); } };
    $('bCompare').onclick = compare;
    $('bLegend').onclick = e => { const o = $('legend').classList.toggle('hidden'); e.currentTarget.setAttribute('aria-expanded', String(!o)); };
    bindSeg($('speedSeg'), v => { Sim.setSpeed(v); $('bSpeed').textContent = v + '×'; });
    $('bSpeed').onclick = () => { const order = ['1', '2', '5', '10'], cur = $('bSpeed').textContent.replace('×', ''), next = order[(order.indexOf(cur) + 1) % order.length];
      Sim.setSpeed(next); setSeg($('speedSeg'), next); $('bSpeed').textContent = next + '×'; }; bindSeg($('chartMode'), v => Charts.setMode(v)); bindSeg($('cmpMode'), v => Charts.setCmpMode(v));
    qsa('.tabs button').forEach(b => b.onclick = () => setTab(b.dataset.tab));
    qsa('.tabbar button').forEach(b => b.onclick = () => setView(b.dataset.view));
    Sim.bind({state: onState, change: updateButtons,
      finished: st => { toast('Evacuation finished: ' + fmtNum(st.metrics.evacuated) + ' of ' + fmtNum(st.metrics.ordered) + ' people reached a shelter', 'good', 5000); Panels.addEvent('Simulation finished', 'info', st.time_s); },
      error: e => { toast(e.message, 'error'); if (e.network) showApiError(e); }});
    document.addEventListener('keydown', e => {
      if (e.target.closest('input, select, textarea, dialog') || e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === ' ') { if (e.target.closest('button, summary, a, [role=radio]')) return; e.preventDefault(); togglePlay(); }
      else if (k === 'arrowright') step();
      else if (k === 'r') resetSim().catch(() => {});
      else if (k === 'g') generate();
      else if (k === 'p') MapView.setPick(true);
      else if (k === 'escape') MapView.setPick(false);
      else if (k === '?') $('helpDlg').showModal();
      else if (['1', '2', '3'].includes(k)) setTab(['live', 'routes', 'compare'][+k - 1]);
    });
  }

  async function boot() {
    try {
      const [meta, list] = await Promise.all([API.get('/meta'), API.get('/scenarios')]);
      MapView.setBounds(meta.bounds); MapView.fitAll(false);
      Scenario.init(meta, list, {change: onFormChange, pick: () => MapView.setPick(true),
        center: (lat, lon) => MapView.setPreview(Scenario.preview())});
      updateButtons();
      await generate();
    } catch (e) { showApiError(e); $('scenarioForm').replaceChildren(el('p', {class: 'muted'}, 'The options appear once the backend is reachable.')); }
  }

  function start() {
    initTheme();
    MapView.init({
      onOrigin: ll => plan(ll),
      onShelter: () => {},
      onEpicentre: (ll, final) => Scenario.setCenter(ll.lat, ll.lng, final),
    });
    Panels.bind({onShelter: id => { MapView.openShelter(id); if (document.body.dataset.view === 'insights') setView('map'); }});
    Charts.init(); wire(); setView('map'); updateButtons(); boot();
  }
  return {start};
})();
document.addEventListener('DOMContentLoaded', App.start);