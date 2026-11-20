
/* Five URL-addressable views share one simulation, one Leaflet map and one chart controller.
   Navigation never reloads the document or generates a new backend session. */
const Pages = (() => {
  const ROUTES = {
    dashboard: ['Dashboard', 'Overall disaster simulation status'],
    disaster: ['Disaster & Risk Monitoring', 'Disaster progression and hazard zones'],
    roads: ['Road Network & Traffic', 'Road access and live congestion'],
    evacuation: ['Evacuation Management', 'Population, routes and shelters'],
    analytics: ['Analytics & Data Sources', 'Performance and data provenance'],
  };
  const MAP_SLOTS = {disaster: 'mapSlotDisaster', roads: 'mapSlotRoads', evacuation: 'mapSlotEvacuation'};
  const ROAD_COLORS = {OPEN: '#2e9e5b', CONGESTED: '#d9a400', RESTRICTED: '#e6c84a', DANGEROUS: '#e8742a', BLOCKED: '#c62828'};
  const RISK_COLORS = {LOW: '#2e9e5b', MEDIUM: '#e3b505', HIGH: '#ec7a1c', CRITICAL: '#cf2f2f'};
  let current = null, latest = null, network = null, roadChart = null, mapWasVisible = false;
  let lastHotspots = 0, lastRisk = 0, loadingHotspots = false, loadingRisk = false;
  let requestedHotspot = null;
  let hotspotVersion = 0, riskVersion = 0;

  const stat = (label, value) => el('div', {class: 'stat-card'}, el('span', {}, label), el('b', {}, String(value ?? '—')));
  const fact = (label, value) => el('div', {}, el('dt', {}, label), el('dd', {}, String(value ?? 'Not provided')));
  const cap = name => name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const labelNum = n => Number.isFinite(n) ? fmtNum(n) : '—';
  const clockOrDash = n => n == null ? '—' : fmtClock(n);

  function openNav(open) {
    document.body.classList.toggle('nav-open', open);
    $('navBackdrop').hidden = !open;
    $('bMenu').setAttribute('aria-expanded', String(open));
  }

  function nav() {
    const hash = location.hash.replace(/^#\/?/, '').replace(/\/$/, '');
    const view = ROUTES[hash] ? hash : 'dashboard';
    if (location.hash !== '#/' + view) history.replaceState(null, '', '#/' + view);
    const previous = current;
    current = view;
    document.body.dataset.page = view;
    Object.keys(ROUTES).forEach(key => $('page-' + key).classList.toggle('hidden', key !== view));
    qsa('[data-page-link]').forEach(a => {
      if (a.dataset.pageLink === view) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
    $('pageTitle').textContent = ROUTES[view][0];
    $('pageSubtitle').textContent = ROUTES[view][1];
    document.title = ROUTES[view][0] + ' · Evacuation Planner';
    openNav(false);
    if (previous !== view) $('pageContainer').scrollTop = 0;
    if (MAP_SLOTS[view]) {
      $(MAP_SLOTS[view]).append($('viewMap'));
      MapView.setProfile(view);
      requestAnimationFrame(() => {
        MapView.invalidate();
        if (!mapWasVisible) { MapView.fitAll(false); mapWasVisible = true; }
        setTimeout(MapView.invalidate, 120);
      });
    }
    if (view === 'roads') { loadNetwork(); refreshHotspots(true); }
    if (view === 'disaster') refreshRisk(true);
    if (typeof Charts !== 'undefined') setTimeout(() => Charts.resize(), 60);
    if (roadChart && view === 'roads') setTimeout(() => roadChart.resize(), 100);
  }

  function qsa(sel) { return [...document.querySelectorAll(sel)]; }

  function init() {
    $('mapSlotDisaster').append($('viewMap'));
    $('bMenu').onclick = () => openNav(!document.body.classList.contains('nav-open'));
    $('bCloseNav').onclick = () => openNav(false);
    $('navBackdrop').onclick = () => openNav(false);
    window.addEventListener('hashchange', nav);
    $('hotspotBy').addEventListener('change', () => refreshHotspots(true));
    $('bRefreshRoads').onclick = () => { loadNetwork(true); refreshHotspots(true); };
  }

  function goto(page) {
    if (ROUTES[page]) {
      if (location.hash === '#/' + page) nav();
      else location.hash = '#/' + page;
    }
  }

  function updateState(st) {
    latest = st;
    const m = st.metrics, d = st.disaster;
    $('dashDisaster').textContent = d ? cap(d.kind) : 'Disabled';
    $('dashRadius').textContent = d ? labelNum(d.radius_m) + ' m' : 'No active hazard';
    $('dashTime').textContent = fmtClock(st.time_s);
    $('dashStrategy').textContent = cap(st.strategy);
    $('simRibbonStatus').textContent = st.finished ? 'Simulation finished' : (st.time_s ? 'Simulation active' : 'Scenario ready');
    $('simRibbonDisaster').textContent = d ? cap(d.kind) + ' · ' + labelNum(d.radius_m) + ' m radius' : 'No active disaster';

    $('disasterType').textContent = d ? cap(d.kind) : 'Disabled';
    $('disasterCenter').textContent = d ? d.center.map(v => Number(v).toFixed(4)).join(', ') : '—';
    $('disasterIntensity').textContent = d ? Number(d.intensity).toFixed(2) : '—';
    $('disasterRadius').textContent = d ? labelNum(d.radius_m) + ' m' : '—';
    $('riskAffected').textContent = labelNum(m.affected);
    $('riskAtRisk').textContent = labelNum(m.at_risk);

    const moving = m.traveling, waiting = m.waiting;
    $('evacKpis').replaceChildren(
      stat('Ordered to evacuate', labelNum(m.ordered)),
      stat('Sheltered', labelNum(m.evacuated)),
      stat('On the move', labelNum(moving)),
      stat('Waiting', labelNum(waiting)),
      stat('At risk now', labelNum(m.at_risk)),
      stat('Remaining', labelNum(m.remaining)),
      stat('Reroutes', labelNum(m.reroutes)),
      stat('Evacuation complete', m.ordered ? Math.round(m.evacuated / m.ordered * 100) + '%' : '0%'),
    );
    $('analyticsMetrics').replaceChildren(
      stat('Evacuated', labelNum(m.evacuated)),
      stat('Evacuation progress', m.ordered ? (100 * m.evacuated / m.ordered).toFixed(1) + '%' : '0%'),
      stat('Cumulative exposure', labelNum(m.exposure / 60) + ' person-hazard-min'),
      stat('Mean congestion', Number(m.congestion_mean).toFixed(2)),
      stat('Peak congestion', Number(m.congestion_peak).toFixed(2)),
      stat('Roads blocked', labelNum(m.blocked_roads)),
      stat('Route failures', labelNum(m.route_failures)),
      stat('Reroutes', labelNum(m.reroutes)),
    );
    drawRoadStatus(st.roads);
    if (current === 'roads') refreshHotspots();
    if (current === 'disaster') refreshRisk();
  }

  function drawRoadStatus(roads) {
    const total = roads.length;
    const counts = Object.fromEntries(Object.keys(ROAD_COLORS).map(k => [k, 0]));
    roads.forEach(([status]) => { if (Object.hasOwn(counts, status)) counts[status]++; });
    $('roadStatus').replaceChildren(...Object.entries(counts).map(([k, v]) =>
      el('div', {class:'status-row'}, el('span', {}, cap(k)),
        el('div', {class:'bar'}, el('i', {style: `width:${total ? v * 100 / total : 0}%;background:${ROAD_COLORS[k]}`})),
        el('strong', {}, labelNum(v)))));
  }

  async function loadNetwork(force = false) {
    if (network && !force) { drawNetwork(); return; }
    try { network = await API.get('/network/summary'); drawNetwork(); }
    catch (e) { $('networkKpis').replaceChildren(el('p', {class:'muted'}, 'Road summary unavailable: ' + e.message)); }
  }

  function drawNetwork() {
    if (!network) return;
    const n = network;
    $('roadDataSet').textContent = n.dataset || 'Current dataset';
    $('networkKpis').replaceChildren(
      stat('Road segments', labelNum(n.roads)), stat('Road network', n.total_km + ' km'),
      stat('Road nodes', labelNum(n.nodes)), stat('One-way roads', labelNum(n.oneway_roads)),
      stat('Two-way roads', labelNum(n.two_way_roads)), stat('Directed connections', labelNum(n.directed_edges)),
      stat('Lane capacity (people)', labelNum(n.lane_capacity_people)),
      stat('Speed range', n.speed_kph ? `${n.speed_kph.min}–${n.speed_kph.max} km/h` : '—'));
    const groups = Object.entries(n.by_class || {});
    $('networkClasses').replaceChildren(...groups.map(([k,v]) => el('div', {},
      el('span', {}, cap(k)), el('b', {}, `${fmtNum(v.roads)} roads · ${v.km} km · ${v.lanes_per_direction} lane(s) · ${v.speed_kph} km/h`))));
    const target = $('roadClassChart');
    if (roadChart) roadChart.destroy();
    roadChart = new Chart(target, {type: 'bar', data: {
      labels: groups.map(([k]) => cap(k)), datasets: [{label: 'Road segments',
        data: groups.map(([,v]) => v.roads), backgroundColor: '#0b6e99', borderRadius: 4}]},
      options: {responsive:true,maintainAspectRatio:false,animation:false,
        plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true,ticks:{precision:0}}}}});
  }

  async function refreshHotspots(force = false) {
    if (!latest || current !== 'roads') return;
    if (loadingHotspots) { requestedHotspot = $('hotspotBy').value; return; }
    if (!force && Date.now() - lastHotspots < 3500) return;
    loadingHotspots = true; lastHotspots = Date.now();
    const version = ++hotspotVersion;
    const by = $('hotspotBy').value;
    $('hotspotMetricHead').textContent = cap(by) + (by === 'exposure' ? ' (person-hazard-min)' : '');
    try {
      const entries = await API.get('/network/hotspots?by=' + encodeURIComponent(by) + '&limit=10');
      if (version !== hotspotVersion || by !== $('hotspotBy').value) return;
      $('hotspotRows').replaceChildren(...entries.map(r => {
        const td = (v) => el('td', {}, String(v));
        const tr = el('tr', {tabindex:0, title:'Locate this road segment on the map'},
          td(cap(r.road_class) + ' · ' + cap(r.status)), td(r.length_m + ' m'), td(r.speed_kph + ' km/h'),
          td(r.lanes), td(r.oneway ? 'Yes' : 'No'), td(`${r.value} ${r.unit}`));
        const focus = () => MapView.focusRoad(r.from, r.to);
        tr.addEventListener('click', focus);
        tr.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); focus(); } });
        return tr;
      }));
      $('hotspotEmpty').classList.toggle('hidden', !!entries.length);
      $('hotspotEmpty').textContent = by === 'exposure' ? 'No accumulated road exposure yet. Advance the simulation to populate hotspots.' : 'No positive ' + by + ' hotspots in the current simulation.';
    } catch(e) { $('hotspotEmpty').classList.remove('hidden'); $('hotspotEmpty').textContent = 'Cannot retrieve hotspots: ' + e.message; }
    finally {
      loadingHotspots = false;
      if (requestedHotspot !== null && current === 'roads') { requestedHotspot = null; refreshHotspots(true); }
    }
  }

  async function refreshRisk(force = false) {
    if (!latest || current !== 'disaster' || loadingRisk) return;
    if (!force && Date.now() - lastRisk < 3500) return;
    loadingRisk = true; lastRisk = Date.now();
    const version = ++riskVersion;
    try {
      const out = await API.get('/disaster/risk-map');
      if (version !== riskVersion) return;
      const counts = {LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0};
      out.nodes.forEach(n => { if (Object.hasOwn(counts, n.level)) counts[n.level]++; });
      const total = out.nodes.length;
      $('riskBreakdown').classList.remove('muted');
      $('riskBreakdown').replaceChildren(...Object.entries(counts).map(([k,v]) => el('div', {class: 'risk-row'},
        el('span', {}, cap(k)), el('div', {class:'bar'},
          el('i', {style:`width:${total ? v * 100 / total : 0}%;background:${RISK_COLORS[k]}`})),
        el('strong', {}, `${fmtNum(v)} (${total ? (v * 100 / total).toFixed(0) : 0}%)`))));
    } catch(e) { $('riskBreakdown').textContent = 'Cannot retrieve the risk map: ' + e.message; }
    finally { loadingRisk = false; }
  }

  function setDataset(d) {
    const badge = $('datasetBadge');
    badge.textContent = cap(d.kind) + ' dataset';
    const facts = [fact('Dataset name', d.name), fact('Dataset type', cap(d.kind)),
      fact('Manifest / checksum', 'Not supplied by the dataset API'),
      fact('Validation', d.warnings?.length ? 'Loaded · with warnings' : 'Loaded · no warnings reported'),
      fact('Population', labelNum(d.stats?.population)), fact('Road nodes', labelNum(d.stats?.nodes)),
      fact('Road edges', labelNum(d.stats?.edges)), fact('Shelters', labelNum(d.stats?.shelters)),
      fact('Shelter capacity', labelNum(d.stats?.shelter_capacity))];
    const layers = Object.entries(d.layers || {}).map(([name, info]) =>
      el('div', {class:'data-layer'}, el('strong', {}, name + ' · ' + cap(info.source)),
        ...Object.entries(info).filter(([k]) => k !== 'source').map(([k,v]) => el('small', {}, cap(k) + ': ' + (typeof v === 'object' ? JSON.stringify(v) : String(v))))));
    const sourceInfo = el('div', {}, el('h3', {}, 'Source layers'), el('div', {class:'data-layer-list'}, layers));
    const assumptions = el('div', {}, el('h3', {}, 'Data assumptions'),
      ...(d.assumptions?.length ? d.assumptions.map(a => el('p', {class:'provenance-meta'}, a)) : [el('p', {class:'provenance-meta'}, 'No assumptions provided by the dataset.')])) ;
    const warnings = el('div', {}, el('h3', {}, 'Validation warnings'),
      ...(d.warnings?.length ? d.warnings.map(w => el('p', {class:'dataset-warning'}, w)) : [el('p', {class:'muted small'}, 'No validation warnings reported.')])) ;
    const frame = d.frame ? el('p', {class:'provenance-meta'}, 'Geographic frame: ' + JSON.stringify(d.frame)) : null;
    const provenanceNote = el('p', {class:'muted small'},
      d.kind === 'synthetic' ? 'All reported source layers are synthetic. This demonstration dataset is not a real-world emergency feed.' :
      d.kind === 'mixed' ? 'This dataset mixes synthetic and non-synthetic layers; verify each layer’s provenance before interpreting results.' :
      'The dataset metadata reports non-synthetic sources. This does not constitute verification of live emergency conditions.');
    $('datasetDetail').classList.remove('muted');
    $('datasetDetail').replaceChildren(provenanceNote, ...(d.description ? [el('p', {class:'muted small'}, d.description)] : []),
      el('dl', {class:'dataset-facts'}, facts), sourceInfo, assumptions, warnings, ...(frame ? [frame] : []));
  }

  function onTheme() {
    if (roadChart) {
      roadChart.options.scales.x.ticks.color = cssVar('--muted');
      roadChart.options.scales.y.ticks.color = cssVar('--muted');
      roadChart.update('none');
    }
  }

  return {init, nav, goto, updateState, setDataset, loadNetwork, onTheme, current: () => current};
})();
