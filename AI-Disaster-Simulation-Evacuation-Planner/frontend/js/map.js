/* Leaflet map: static layers drawn once per scenario, colours/positions updated from each simulation state. */
const MapView = (() => {
  const ROAD = {OPEN: '#8fa3a0', CONGESTED: '#d9a400', RESTRICTED: '#e6c84a', DANGEROUS: '#e8742a', BLOCKED: '#c62828'};
  const AGENT = {AT_HOME: '#607d8b', TRAVELING: '#1565c0', REROUTING: '#00838f', WAITING: '#8e24aa', TRAPPED: '#111', AT_SHELTER: '#2e9e5b', SAFE: '#b0bec5'};
  const RISK = ['#2e9e5b', '#e3b505', '#ec7a1c', '#cf2f2f'];                    // low, medium, high, critical
  const TILES = {light: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                 dark: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'};
  const LAYERS = [['hazard', 'Disaster zone', '#cf2f2f'], ['risk', 'Risk map', '#ec7a1c'], ['roads', 'Roads', '#8fa3a0'],
                  ['population', 'People', '#42a5f5'], ['shelters', 'Shelters', '#2e9e5b'], ['agents', 'Evacuees', '#0b6e99'], ['routes', 'Routes', '#e8a400']];
  let map, tile, groups = {}, roads = [], nodes = [], dots = [], shelterMarks = [], hazardRings = [], levels = {medium: .25, high: .5, critical: .75};
  let epi = null, preview = [], originMark = null, routeLines = {}, pick = false, bounds = null, h = {};

  function init(handlers) {
    h = handlers;
    map = L.map('map', {preferCanvas: true, zoomControl: false, attributionControl: false}).setView([17.385, 78.4867], 13);
    L.control.zoom({position: 'topright'}).addTo(map);
    L.control.attribution({prefix: false, position: 'bottomleft'}).addTo(map);
    tile = L.tileLayer(TILES[document.body.dataset.theme] || TILES.light,
      {attribution: '© OpenStreetMap · © CARTO · overlays are synthetic', maxZoom: 19}).addTo(map);
    [...LAYERS.map(l => l[0]), 'preview'].forEach(k => groups[k] = L.layerGroup().addTo(map));

    const chips = $('layerChips');
    LAYERS.forEach(([key, label, color]) => {
      const b = el('button', {class: 'chip', 'aria-pressed': 'true', type: 'button', title: 'Show or hide ' + label.toLowerCase()},
                   el('i', {style: 'background:' + color}), label);
      b.onclick = () => { const on = b.getAttribute('aria-pressed') !== 'true'; b.setAttribute('aria-pressed', String(on)); on ? groups[key].addTo(map) : map.removeLayer(groups[key]); };
      chips.append(b);
    });
    $('legend').innerHTML =
      '<b>Risk</b><div>' + ['low', 'medium', 'high', 'critical'].map((t, i) => `<span class="sw" style="background:${RISK[i]}"></span>${t} `).join('') + '</div>' +
      '<b>Roads</b><div>' + Object.entries(ROAD).map(([k, c]) => `<span class="ln" style="border-color:${c}${k === 'BLOCKED' ? ';border-top-style:dashed' : ''}"></span>${k.toLowerCase()} `).join('') + '</div>' +
      '<b>Routes</b><div><span class="ln" style="border-color:var(--route-base);border-top-style:dashed"></span>baseline <span class="ln" style="border-color:var(--route-new)"></span>proposed</div>' +
      '<b>Evacuees</b><div>' + ['TRAVELING', 'REROUTING', 'WAITING', 'TRAPPED', 'AT_SHELTER'].map(k => `<span class="sw" style="background:${AGENT[k]}"></span>${k.toLowerCase().replace('_', ' ')} `).join('') + '</div>';

    map.on('click', e => { if (pick) { placeEpicentre(e.latlng, true); setPick(false); } else h.onOrigin(e.latlng); });
    new ResizeObserver(() => map.invalidateSize()).observe($('map'));
  }

  const riskColor = r => RISK[r >= levels.critical ? 3 : r >= levels.high ? 2 : r >= levels.medium ? 1 : 0];
  const clamp = ll => bounds ? L.latLng(Math.min(bounds.getNorth(), Math.max(bounds.getSouth(), ll.lat)),
                                        Math.min(bounds.getEast(), Math.max(bounds.getWest(), ll.lng))) : ll;

  function setBounds(b) { bounds = L.latLngBounds(b); }
  function fitAll(animate) { if (bounds) map.fitBounds(bounds.pad(.04), {animate: !!animate}); }

  function drawStatic(layers, fit) {
    ['hazard', 'risk', 'roads', 'population', 'shelters', 'agents', 'routes'].forEach(k => groups[k].clearLayers());
    roads = []; nodes = []; dots = []; shelterMarks = []; hazardRings = []; routeLines = {}; originMark = null;
    levels = layers.risk_levels; setBounds(layers.bounds);
    roads = layers.roads.map(r => {
      const l = L.polyline([r.a, r.b], {weight: r.arterial ? 3.5 : 1.8, color: ROAD.OPEN, opacity: .75}).addTo(groups.roads);
      l._s = 'OPEN'; l._r = 0;
      l.bindTooltip(() => `Road · ${l._s.toLowerCase()} · risk ${l._r.toFixed(2)}`, {sticky: true});
      return l;
    });
    nodes = layers.nodes.map(p => L.circleMarker(p, {radius: 7, weight: 0, fillOpacity: 0, fillColor: RISK[0], interactive: false}).addTo(groups.risk));
    layers.population.forEach(z => L.circleMarker(z.latlon, {radius: Math.min(9, 2 + Math.sqrt(z.people) / 5), weight: 1, color: '#1e88e5',
      fillColor: '#64b5f6', fillOpacity: z.ordered ? .38 : .12, opacity: z.ordered ? .7 : .3}).bindTooltip(`${fmtNum(z.people)} people${z.ordered ? '' : ' · not ordered to evacuate'}`).addTo(groups.population));
    if (fit) fitAll(false);
  }

  function render(st) {
    st.roads.forEach(([s, r], i) => { const l = roads[i]; if (!l) return; l._s = s; l._r = r;
      l.setStyle({color: ROAD[s], dashArray: s === 'BLOCKED' ? '5 5' : null, weight: (l.options.weight > 3 ? 3.5 : 1.8) + (s === 'BLOCKED' ? 1.2 : 0), opacity: s === 'OPEN' ? .75 : .95}); });
    st.node_risk.forEach((r, i) => nodes[i] && nodes[i].setStyle({fillColor: riskColor(r), fillOpacity: r > .02 ? .45 : 0}));
    if (st.disaster) {
      if (!hazardRings.length) hazardRings = [[1, .07], [.66, .09], [.33, .13]].map(([k, o]) =>
        L.circle(st.disaster.center, {radius: 1, color: '#cf2f2f', weight: k === 1 ? 1.5 : 0, fillColor: '#cf2f2f', fillOpacity: o, interactive: false}).addTo(groups.hazard));
      [1, .66, .33].forEach((k, i) => hazardRings[i].setRadius(Math.max(1, st.disaster.radius_m * k)));
    } else { groups.hazard.clearLayers(); hazardRings = []; }
    st.shelters.forEach((s, i) => {
      let m = shelterMarks[i];
      if (!m) {
        m = shelterMarks[i] = L.marker(s.latlon, {icon: shelterIcon(s), title: 'Shelter ' + (s.id + 1), riseOnHover: true}).addTo(groups.shelters);
        m._status = s.status;
        m.bindPopup(() => shelterPopup(m._d), {closeButton: false}); m.on('click', () => h.onShelter && h.onShelter(m._d.id));
      }
      m._d = s;
      if (m._status !== s.status) { m._status = s.status; m.setIcon(shelterIcon(s)); }
      if (m.isPopupOpen()) m.getPopup().setContent(shelterPopup(s));
    });
    st.agents.forEach(([lat, lon, status, size], i) => {
      if (!dots[i]) dots[i] = L.circleMarker([lat, lon], {radius: 3.2 + Math.min(3, size / 80), weight: 1.2, color: '#ffffff', opacity: .95, fillOpacity: 1, interactive: false}).addTo(groups.agents);
      dots[i].setLatLng([lat, lon]).setStyle({fillColor: AGENT[status]});
    });
  }

  const shelterIcon = s => L.divIcon({className: 'sh-wrap', iconSize: [30, 30], iconAnchor: [15, 15], html: `<div class="sh ${s.status}">${s.id + 1}</div>`});

  function shelterPopup(s) {
    const used = Math.min(100, 100 * s.occupancy / s.capacity);
    return `<b>Shelter ${s.id + 1}</b> · ${s.status.toLowerCase()}<div class="pop-bar"><i style="width:${used}%"></i></div>` +
           `${fmtNum(s.occupancy)} of ${fmtNum(s.capacity)} used · ${fmtNum(s.available)} free<br>Risk ${s.risk_level.toLowerCase()} (${s.risk})`;
  }

  /* ---- epicentre editing --------------------------------------------------------------------------- */
  function setPreview({enabled, center, r0, rmax}) {
    groups.preview.clearLayers(); preview = [];
    if (!enabled) { if (epi) { map.removeLayer(epi); epi = null; } return; }
    const c = L.latLng(center);
    if (!epi) {
      epi = L.marker(c, {draggable: true, title: 'Disaster epicentre: drag to move', icon: L.divIcon({className: 'epi', html: '<div class="epi-dot"></div>', iconSize: [26, 26], iconAnchor: [13, 13]})}).addTo(map);
      epi.on('drag', () => { const p = clamp(epi.getLatLng()); preview.forEach(r => r.setLatLng(p)); h.onEpicentre(p, false); });
      epi.on('dragend', () => { const p = clamp(epi.getLatLng()); epi.setLatLng(p); preview.forEach(r => r.setLatLng(p)); h.onEpicentre(p, true); });
    } else epi.setLatLng(c);
    preview = [L.circle(c, {radius: r0, color: '#cf2f2f', weight: 1.5, dashArray: '2 5', fill: false, interactive: false}).addTo(groups.preview),
               L.circle(c, {radius: rmax, color: '#cf2f2f', weight: 1.5, dashArray: '8 8', opacity: .6, fill: false, interactive: false}).addTo(groups.preview)];
  }
  function placeEpicentre(ll, final) { const p = clamp(ll); preview.forEach(r => r.setLatLng(p)); if (epi) epi.setLatLng(p); h.onEpicentre(p, final); }
  function setPick(on) { pick = on; $('map').classList.toggle('picking', on); $('pickHint').classList.toggle('hidden', !on); }

  /* ---- routes ---------------------------------------------------------------------------------------- */
  function drawRoutes(plan, fit) {
    groups.routes.clearLayers(); routeLines = {};
    originMark = L.marker(plan.origin.latlon, {icon: L.divIcon({className: 'origin', html: '<i></i>', iconSize: [18, 18], iconAnchor: [9, 18]}), title: 'Evacuation origin', interactive: false}).addTo(groups.routes);
    const all = [plan.origin.latlon];
    if (plan.baseline) { routeLines.baseline = [L.polyline(plan.baseline.path, {color: cssVar('--route-base'), weight: 5, dashArray: '9 8', opacity: .95}).addTo(groups.routes)]; all.push(...plan.baseline.path); }
    if (plan.proposed) {
      routeLines.proposed = [L.polyline(plan.proposed.path, {color: '#fff', weight: 10, opacity: .85}).addTo(groups.routes),
                             L.polyline(plan.proposed.path, {color: cssVar('--route-new'), weight: 6, opacity: 1}).addTo(groups.routes)];
      all.push(...plan.proposed.path);
    }
    if (fit && all.length > 1) map.fitBounds(L.latLngBounds(all).pad(.25), {maxZoom: 16});
  }
  function highlight(which) {
    Object.entries(routeLines).forEach(([k, ls]) => ls.forEach(l => l.setStyle({opacity: !which || which === k ? (l.options.color === '#fff' ? .85 : 1) : .18})));
    if (which && routeLines[which]) routeLines[which].forEach(l => l.bringToFront());
  }

  return {
    init, drawStatic, render, setBounds, fitAll, setPreview, placeEpicentre, setPick, drawRoutes, highlight,
    isPicking: () => pick,
    flyTo: (ll, z = 15) => map.flyTo(ll, z, {duration: .6}),
    openShelter: id => { const m = shelterMarks[id]; if (m) { map.flyTo(m.getLatLng(), Math.max(map.getZoom(), 15), {duration: .6}); m.openPopup(); } },
    setTheme: t => tile.setUrl(TILES[t]),
    invalidate: () => map.invalidateSize(),
  };
})();