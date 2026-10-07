/* Scenario options panel. Builds every control from /api/meta, keeps the values in one object (S),
   and turns them into the POST /api/disaster/start payload. */
const Scenario = (() => {
  const ICON = {flood: 'i-flood', wildfire: 'i-fire', earthquake: 'i-quake'};
  const severity = v => v < .4 ? 'Low' : v < .6 ? 'Moderate' : v < .8 ? 'Severe' : 'Extreme';
  let meta, presets = [], S = {}, cb = {}, refreshers = [], openState = {disaster: true, people: true, failures: false, run: false}, activePreset = 'expanding';

  function init(m, list, callbacks) { meta = m; presets = list; cb = callbacks; S = {strategy: 'proposed'}; fromConfig(m.defaults); render(); }

  function fromConfig(c) {
    Object.assign(S, {
      disaster_enabled: c.disaster_enabled, disaster_type: c.disaster_type, intensity: c.intensity,
      center_lat: c.center_lat, center_lon: c.center_lon, initial_radius_m: c.initial_radius_m, max_radius_m: c.max_radius_m,
      spread_speed_mps: c.spread_speed_mps, evacuation_radius_m: c.evacuation_radius_m, population_scale: c.population_scale,
      n_shelters: c.n_shelters, shelter_capacity: Math.round(c.shelter_capacity_scale * meta.base_shelter_capacity),
      road_closure_count: c.road_closure_count, road_closure_min: Math.round(c.road_closure_time_s / 60),
      failures: (c.shelter_failures || []).map(([id, t]) => ({id: +id, min: Math.round(t / 60)})), duration_min: Math.round(c.duration_s / 60)});
  }

  const changed = (structural = false) => { refreshAll(); cb.change(structural); };
  const refreshAll = () => refreshers.forEach(f => f());

  /* ---- building blocks ----------------------------------------------------------------------------- */
  function slider({key, label, min, max, step, fmt, hint, after}) {
    const out = el('output'), hintEl = el('div', {class: 'hint'});
    const input = el('input', {type: 'range', min, max, step, 'aria-label': label});
    const sync = () => {
      const v = Math.min(max, Math.max(min, S[key]));
      input.value = v; out.textContent = fmt(S[key]);
      input.style.setProperty('--p', ((v - min) / (max - min) * 100) + '%');
      if (hint) { const t = hint(); hintEl.textContent = t || ''; hintEl.style.display = t ? '' : 'none'; }
    };
    input.addEventListener('input', () => { S[key] = +input.value; if (after) after(); changed(); });
    refreshers.push(sync); sync();
    return el('div', {class: 'field'}, el('label', {}, label, out), input, hintEl);
  }
  const iconSvg = n => icon(n);
  function seg(label, key, options, onPick, extraClass = '') {
    const s = el('div', {class: 'seg ' + extraClass, role: 'radiogroup', 'aria-label': label},
      options.map(([v, text, ic]) => el('button', {type: 'button', role: 'radio', 'data-v': v, 'aria-checked': String(S[key] === v)},
        ic ? iconSvg(ic) : null, text)));
    bindSeg(s, v => { S[key] = v; onPick && onPick(v); });
    return s;
  }
  const section = (id, title, summary, ...kids) => {
    const sumEl = el('span', {class: 'sum'}, summary());
    refreshers.push(() => { sumEl.textContent = summary(); });
    const d = el('details', {class: 'sec'}, el('summary', {}, title, sumEl), ...kids);
    d.open = !!openState[id];
    d.addEventListener('toggle', () => openState[id] = d.open);
    return d;
  };

  function render() {
    refreshers = [];
    const root = $('scenarioForm'), top = root.scrollTop;
    root.replaceChildren();

    /* presets */
    root.append(el('div', {class: 'field'}, el('div', {class: 'lbl'}, 'Start from a preset'),
      el('div', {class: 'chips'}, presets.map(p => el('button', {class: 'chip', type: 'button', title: p.description, 'aria-pressed': String(p.id === activePreset),
        onclick: () => { activePreset = p.id; const keep = S.strategy; fromConfig(p.config); S.strategy = keep; render(); cb.change(true); }}, p.name.replace(/^\d+\.\s*/, ''))))));

    /* disaster */
    const dBody = el('div');
    const typeBlurb = el('div', {class: 'hint'});
    const setBlurb = () => typeBlurb.textContent = (meta.disaster_types[S.disaster_type] || {}).blurb || '';
    const coords = el('code'), syncCoords = () => coords.textContent = `${S.center_lat.toFixed(4)}, ${S.center_lon.toFixed(4)}`;
    refreshers.push(setBlurb, syncCoords); setBlurb(); syncCoords();
    const enabled = el('label', {class: 'switch'}, el('input', {type: 'checkbox', checked: S.disaster_enabled, 'aria-label': 'Disaster enabled'}), el('span'), 'Disaster active');
    enabled.querySelector('input').addEventListener('change', e => { S.disaster_enabled = e.target.checked; dBody.toggleAttribute('inert', !S.disaster_enabled); dBody.style.opacity = S.disaster_enabled ? '' : '.45'; changed(); });
    dBody.toggleAttribute('inert', !S.disaster_enabled); dBody.style.opacity = S.disaster_enabled ? '' : '.45';

    dBody.append(
      el('div', {class: 'field'}, el('div', {class: 'lbl'}, 'Disaster type'),
        seg('Disaster type', 'disaster_type', Object.entries(meta.disaster_types).map(([k, v]) => [k, v.label, ICON[k]]), t => {
          const p = meta.disaster_types[t]; Object.assign(S, {initial_radius_m: p.initial_radius_m, max_radius_m: p.max_radius_m, spread_speed_mps: p.spread_speed_mps});
          render(); cb.change(true); }, 'types'), typeBlurb),
      slider({key: 'intensity', label: 'Intensity', min: .2, max: 1, step: .05, fmt: v => `${v.toFixed(2)} · ${severity(v)}`,
        hint: () => S.intensity < .6 ? 'Below 0.6 no road is fully blocked, only slowed.' : ''}),
      el('div', {class: 'field'}, el('div', {class: 'lbl'}, 'Epicentre'),
        el('div', {class: 'epi-row'}, el('button', {class: 'btn', type: 'button', onclick: () => cb.pick()}, icon('i-target'), ' Pick on map'),
          el('button', {class: 'btn', type: 'button', onclick: () => { const c = meta.defaults; setCenter(c.center_lat, c.center_lon, true); }}, 'Centre'), coords),
        el('div', {class: 'hint'}, 'Or drag the red marker on the map.')),
      slider({key: 'initial_radius_m', label: 'Starting radius', min: 200, max: 2500, step: 50, fmt: v => `${fmtNum(v)} m`,
        after: () => { if (S.max_radius_m < S.initial_radius_m) S.max_radius_m = S.initial_radius_m; }}),
      slider({key: 'max_radius_m', label: 'Maximum radius', min: 500, max: 4000, step: 100, fmt: v => `${fmtNum(v)} m`,
        after: () => { if (S.initial_radius_m > S.max_radius_m) S.initial_radius_m = S.max_radius_m; }}),
      slider({key: 'spread_speed_mps', label: 'Spread speed', min: 0, max: 4, step: .1, fmt: v => v === 0 ? 'static' : `${v.toFixed(1)} m/s`,
        hint: () => S.spread_speed_mps > 0 ? `Reaches full size in about ${Math.round((S.max_radius_m - S.initial_radius_m) / S.spread_speed_mps / 60)} min.` : 'The zone never grows.'}),
      slider({key: 'evacuation_radius_m', label: 'Evacuation order radius', min: 500, max: 4000, step: 100, fmt: v => `${fmtNum(v)} m`,
        hint: () => 'People living inside this radius are told to leave.'}));
    root.append(section('disaster', 'Disaster', () => S.disaster_enabled ? S.disaster_type : 'off', enabled, dBody));

    /* people & shelters */
    root.append(section('people', 'People and shelters', () => `${fmtNum(meta.base_population * S.population_scale)} people · ${S.n_shelters} shelters`,
      slider({key: 'population_scale', label: 'Population', min: .25, max: 4, step: .05, fmt: v => `${fmtNum(meta.base_population * v)} people`}),
      slider({key: 'n_shelters', label: 'Open shelters', min: 1, max: meta.n_shelters_max, step: 1, fmt: v => String(v), after: () => { S.failures = S.failures.filter(f => f.id < S.n_shelters); }}),
      slider({key: 'shelter_capacity', label: 'Capacity per shelter', min: 300, max: 6000, step: 100, fmt: v => fmtNum(v),
        hint: () => { const cap = S.n_shelters * S.shelter_capacity, pop = meta.base_population * S.population_scale; const r = cap / pop;
          return `Total room for ${fmtNum(cap)}: ${Math.round(r * 100)}% of the population` + (r < 1 ? ' (some people cannot be sheltered)' : ''); }})));

    /* failures */
    const list = el('div', {class: 'chips'}), pickId = el('select', {'aria-label': 'Shelter that fails'}), pickMin = el('input', {type: 'number', min: 0, max: 600, value: 15, 'aria-label': 'Failure time in minutes'});
    const fillShelters = () => { const keep = pickId.value; pickId.replaceChildren(...Array.from({length: S.n_shelters}, (_, i) => el('option', {value: i}, 'Shelter ' + (i + 1)))); if (keep !== '' && +keep < S.n_shelters) pickId.value = keep; };
    const drawFailures = () => { fillShelters(); list.replaceChildren(...S.failures.map((f, i) => el('button', {class: 'chip on', type: 'button', title: 'Remove',
      onclick: () => { S.failures.splice(i, 1); drawFailures(); changed(true); }}, `Shelter ${f.id + 1} fails at ${f.min} min`, el('span', {class: 'x'}, '×')))); };
    refreshers.push(drawFailures); drawFailures();
    root.append(section('failures', 'Failures', () => `${S.road_closure_count} roads · ${S.failures.length} shelters`,
      slider({key: 'road_closure_count', label: 'Roads closed', min: 0, max: 40, step: 1, fmt: v => String(v)}),
      slider({key: 'road_closure_min', label: 'Roads close at', min: 0, max: 60, step: 1, fmt: v => `${v} min`}),
      el('div', {class: 'field'}, el('div', {class: 'lbl'}, 'Shelter failures'),
        el('div', {class: 'fail-add'}, pickId, pickMin, el('button', {class: 'btn', type: 'button', onclick: () => {
          const f = {id: +pickId.value, min: Math.max(0, Math.min(600, +pickMin.value || 0))};
          if (!S.failures.some(x => x.id === f.id)) S.failures.push(f); else S.failures.find(x => x.id === f.id).min = f.min;
          drawFailures(); changed(true); }}, 'Add')), list,
        el('div', {class: 'hint'}, 'A failed shelter turns unsafe and stops accepting people.'))));

    /* run */
    const dur = el('select', {'aria-label': 'Simulation length'}, [...new Set([60, 120, 180, 240, 360, S.duration_min])].sort((a, b) => a - b).map(m => el('option', {value: m, selected: m === S.duration_min}, `${m / 60} h`)));
    dur.addEventListener('change', () => { S.duration_min = +dur.value; changed(); });
    root.append(section('run', 'Strategy and length', () => S.strategy,
      el('div', {class: 'field'}, el('div', {class: 'lbl'}, 'Evacuation strategy'),
        seg('Strategy', 'strategy', [['proposed', 'Risk-aware'], ['baseline', 'Baseline']], () => changed()),
        el('div', {class: 'hint'}, 'Baseline = nearest shelter by distance. Risk-aware = avoids hazard and full shelters, reroutes.')),
      el('div', {class: 'field'}, el('label', {}, 'Simulation length'), dur)));
    root.scrollTop = top;
  }

  /* ---- public ------------------------------------------------------------------------------------------- */
  function setCenter(lat, lon, emit) { S.center_lat = lat; S.center_lon = lon; refreshAll(); if (emit) { cb.center(lat, lon); cb.change(false); } }
  const preview = () => ({enabled: S.disaster_enabled, center: [S.center_lat, S.center_lon], r0: S.initial_radius_m, rmax: S.max_radius_m});
  const payload = () => ({
    scenario_id: 'expanding', strategy: S.strategy, disaster_type: S.disaster_type, intensity: S.intensity, disaster_enabled: S.disaster_enabled,
    center_lat: S.center_lat, center_lon: S.center_lon, initial_radius_m: S.initial_radius_m, max_radius_m: S.max_radius_m,
    spread_speed_mps: S.spread_speed_mps, evacuation_radius_m: S.evacuation_radius_m, population_scale: S.population_scale,
    shelter_capacity_scale: S.shelter_capacity / meta.base_shelter_capacity, n_shelters: S.n_shelters,
    road_closure_count: S.road_closure_count, road_closure_time_s: S.road_closure_min * 60,
    shelter_failures: S.failures.filter(f => f.id < S.n_shelters).map(f => [f.id, f.min * 60]), duration_s: S.duration_min * 60});
  const liveParams = () => ({intensity: S.intensity, spread_speed: S.spread_speed_mps, max_radius: S.max_radius_m});

  return {init, payload, preview, liveParams, setCenter, strategy: () => S.strategy};
})();