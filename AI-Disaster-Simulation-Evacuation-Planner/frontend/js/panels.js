/* Right-hand insights: live KPIs, shelters, event log, route cards and the comparison table. */
const Panels = (() => {
  const LEVEL = {LOW: 'Risk low', MEDIUM: 'Risk medium', HIGH: 'Risk high', CRITICAL: 'Risk critical'};
  const RING = 326.7;
  let prev = null, prevShelters = [], levels = {medium: .25, high: .5, critical: .75}, shelterCount = -1, handlers = {};

  const kpi = (id, v) => animateNumber($(id), v);

  function bind(h) { handlers = h; }
  function setLevels(l) { levels = l; }

  function reset() { prev = null; prevShelters = []; shelterCount = -1; $('eventLog').replaceChildren(el('li', {class: 'muted'}, 'Events appear as the evacuation runs.')); }

  function update(st) {
    const m = st.metrics, share = m.ordered ? m.evacuated / m.ordered : 0;
    $('ringFg').style.strokeDashoffset = RING * (1 - share);
    $('hPct').textContent = Math.round(share * 100) + '%';
    kpi('hEvac', m.evacuated); kpi('hOrdered', m.ordered);
    kpi('kTotal', m.total_population); kpi('kAffected', m.affected); kpi('kAtRisk', m.at_risk); kpi('kRem', m.remaining);
    kpi('kBlock', m.blocked_roads); kpi('kRer', m.reroutes); kpi('kShel', m.shelters_active); kpi('kCap', m.shelter_capacity_left);
    const b = $('riskBadge'); b.textContent = LEVEL[m.risk_level]; b.className = 'badge ' + m.risk_level;
    shelters(st.shelters);
    events(m, st);
    prev = m; prevShelters = st.shelters.map(s => s.status);
  }

  function shelters(list) {
    const ul = $('shelterList');
    if (shelterCount !== list.length) {
      shelterCount = list.length;
      ul.replaceChildren(...list.map(s => el('li', {'data-id': s.id, tabindex: 0, title: 'Show on map',
        onclick: () => handlers.onShelter(s.id), onkeydown: e => { if (e.key === 'Enter') handlers.onShelter(s.id); }},
        el('span', {class: 'dot'}), el('span', {}, el('b', {}, 'Shelter ' + (s.id + 1)), ' ', el('small', {})), el('span', {class: 'cnt'}), el('div', {class: 'bar'}, el('i')))));
    }
    list.forEach((s, i) => {
      const li = ul.children[i];
      li.className = s.status;
      li.querySelector('small').textContent = `${s.status.toLowerCase()} · risk ${s.risk_level.toLowerCase()}`;
      li.querySelector('.cnt').textContent = `${fmtNum(s.occupancy)} / ${fmtNum(s.capacity)}`;
      li.querySelector('.bar i').style.width = Math.min(100, 100 * s.occupancy / s.capacity) + '%';
    });
  }

  function addEvent(text, kind, t) {
    const log = $('eventLog');
    if (log.firstChild && log.firstChild.classList.contains('muted')) log.replaceChildren();
    log.prepend(el('li', {class: kind}, el('time', {}, fmtClock(t)), text));
    while (log.children.length > 60) log.lastChild.remove();
  }

  function events(c, st) {
    const t = c.t;
    if (!prev) { addEvent('Scenario ready · ' + fmtNum(c.ordered) + ' people ordered to evacuate', 'info', t); return; }
    if (c.blocked_roads > prev.blocked_roads) addEvent(`${c.blocked_roads - prev.blocked_roads} more road(s) blocked · ${c.blocked_roads} in total`, 'warn', t);
    if (c.route_failures > prev.route_failures) addEvent(`${c.route_failures - prev.route_failures} evacuation route(s) became unusable`, 'bad', t);
    if (c.reroutes > prev.reroutes) addEvent(`${c.reroutes - prev.reroutes} group(s) rerouted`, 'info', t);
    if (c.trapped > prev.trapped) addEvent(`${fmtNum(c.trapped - prev.trapped)} people are trapped`, 'bad', t);
    if (prev.evacuated === 0 && c.evacuated > 0) addEvent('First evacuees reached a shelter', 'good', t);
    const a = prev.ordered ? prev.evacuated / prev.ordered : 0, b = c.ordered ? c.evacuated / c.ordered : 0;
    [.25, .5, .75, .9, 1].forEach(k => { if (a < k && b >= k) addEvent(`${Math.round(k * 100)}% of ordered people evacuated`, 'good', t); });
    if (prev.risk_level !== c.risk_level) addEvent(`Peak risk is now ${c.risk_level.toLowerCase()}`, c.risk_level === 'CRITICAL' || c.risk_level === 'HIGH' ? 'warn' : 'info', t);
    st.shelters.forEach((s, i) => { if (prevShelters[i] && prevShelters[i] !== s.status) addEvent(`Shelter ${s.id + 1} is now ${s.status.toLowerCase()}`, s.status === 'UNSAFE' ? 'bad' : s.status === 'FULL' ? 'warn' : 'info', t); });
  }

  /* ---- routes ------------------------------------------------------------------------------------------- */
  const riskColor = r => r >= levels.critical ? 'var(--crit)' : r >= levels.high ? 'var(--high)' : r >= levels.medium ? 'var(--warn)' : 'var(--ok)';

  function setPlan(p) {
    const box = $('routeCards');
    const card = (kind, title, r) => {
      if (!r) return el('div', {class: 'rcard ' + kind}, el('h4', {}, title), el('p', {class: 'muted'}, 'No route from here: every road leaving this point is blocked.'));
      const s = r.stats, c = el('div', {class: 'rcard ' + kind, tabindex: 0},
        el('h4', {}, title, el('span', {class: 'muted'}, 'Shelter ' + (r.shelter_id + 1))),
        el('dl', {},
          el('dt', {}, 'Distance'), el('dd', {}, (s.distance_m / 1000).toFixed(2) + ' km'),
          el('dt', {}, 'Travel time now'), el('dd', {}, (s.time_s / 60).toFixed(1) + ' min'),
          el('dt', {}, 'Roads in hazard'), el('dd', {}, String(s.hazardous_roads)),
          el('dt', {}, 'Blocked roads on route'), el('dd', {}, String(s.blocked_roads)),
          el('dt', {}, 'Average risk ' + s.avg_risk.toFixed(2)), el('dd', {}, 'peak ' + s.max_risk.toFixed(2)),
          el('div', {class: 'meter'}, el('i', {style: `width:${Math.min(100, s.avg_risk * 100)}%;background:${riskColor(s.avg_risk)}`}))));
      const which = kind === 'base' ? 'baseline' : 'proposed';
      c.addEventListener('mouseenter', () => MapView.highlight(which)); c.addEventListener('mouseleave', () => MapView.highlight(null));
      c.addEventListener('focus', () => MapView.highlight(which)); c.addEventListener('blur', () => MapView.highlight(null));
      return c;
    };
    const out = [el('p', {class: 'muted small'}, `Origin ${p.origin.latlon[0].toFixed(4)}, ${p.origin.latlon[1].toFixed(4)} · at ${fmtClock(p.time_s)}`),
                 card('base', 'Baseline: shortest path', p.baseline), card('new', 'Proposed: risk-aware', p.proposed)];
    if (p.baseline && p.proposed) {
      const dKm = (p.proposed.stats.distance_m - p.baseline.stats.distance_m) / 1000, dH = p.baseline.stats.hazardous_roads - p.proposed.stats.hazardous_roads;
      out.push(el('p', {class: 'summary'}, `Proposed is ${Math.abs(dKm).toFixed(2)} km ${dKm >= 0 ? 'longer' : 'shorter'} and passes ` +
        (dH > 0 ? `${dH} fewer hazardous road(s).` : dH < 0 ? `${-dH} more hazardous road(s).` : 'the same number of hazardous roads.')));
    }
    box.replaceChildren(...out);
  }

  /* ---- comparison -------------------------------------------------------------------------------------- */
  const ROWS = [
    ['Evacuation time, min', 'evacuation_time_s', v => v == null ? 'not completed' : fmtMin(v), 'low', v => v / 60],
    ['90% evacuated, min', 'time_to_90pct_s', v => v == null ? 'not reached' : fmtMin(v), 'low', v => v / 60],
    ['Avg trip, min *', 'avg_trip_time_s', fmtMin, null, v => v / 60],
    ['Max trip, min *', 'max_trip_time_s', fmtMin, null, v => v / 60],
    ['Time in hazard, person-min', 'person_minutes_in_hazard', v => fmtNum(v), 'low', v => v],
    ['Success rate', 'success_rate', pct, 'high', v => v * 100],
    ['Shelter use', 'shelter_utilization', pct, null, v => v * 100],
    ['Peak congestion', 'congestion_peak', v => v.toFixed(2), 'low', v => v],
    ['Route failures', 'route_failures', v => String(v), 'low', v => v],
    ['Reroutes', 'rerouting_count', v => String(v), null, v => v],
    ['Unserved people', 'unserved_population', v => fmtNum(v), 'low', v => v]];

  function setCompare(r) {
    const b = r.baseline.summary, p = r.proposed.summary;
    const rows = ROWS.map(([label, k, f, better, num]) => {
      let d = '–', cls = 'neutral';
      if (b[k] != null && p[k] != null) {
        const x = num(p[k]) - num(b[k]);
        d = (x > 0 ? '+' : '') + (Math.abs(x) >= 100 ? Math.round(x).toLocaleString() : x.toFixed(1).replace(/\.0$/, ''));
        if (better && Math.abs(x) > 1e-9) cls = (better === 'low') === (x < 0) ? 'good' : 'bad';
      }
      return el('tr', {}, el('td', {}, label), el('td', {}, f(b[k])), el('td', {}, f(p[k])), el('td', {class: 'd ' + cls}, d));
    });
    $('cmpTable').replaceChildren(el('thead', {}, el('tr', {}, ['Metric', 'Baseline', 'Proposed', 'Change'].map(t => el('th', {}, t)))), el('tbody', {}, rows));
    const parts = [`Proposed evacuated ${pct(p.success_rate)} of ordered people, baseline ${pct(b.success_rate)}.`];
    if (b.person_minutes_in_hazard > 0) {
      const cut = 1 - p.person_minutes_in_hazard / b.person_minutes_in_hazard;
      parts.push(`Time spent in hazard was ${Math.abs(Math.round(cut * 100))}% ${cut >= 0 ? 'lower' : 'higher'}.`);
    }
    $('cmpSummary').textContent = parts.join(' ');
    $('cmpOut').classList.remove('hidden');
    Charts.drawComparison(r);
  }

  return {bind, setLevels, reset, update, setPlan, setCompare, addEvent};
})();