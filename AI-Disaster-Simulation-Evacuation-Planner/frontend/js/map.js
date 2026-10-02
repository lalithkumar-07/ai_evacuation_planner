/* Map view: draws static layers once, then updates colours/positions from simulation state. */
const MapView = (() => {
  const ROAD = {OPEN:'#8fa3a0', CONGESTED:'#d9a400', RESTRICTED:'#e6c84a', DANGEROUS:'#e8742a', BLOCKED:'#c62828'};
  const AGENT = {AT_HOME:'#607d8b', TRAVELING:'#1565c0', REROUTING:'#00838f', WAITING:'#8e24aa', TRAPPED:'#000', AT_SHELTER:'#2e7d32', SAFE:'#b0bec5'};
  const SHELTER = {ACTIVE:'#2e7d32', FULL:'#f9a825', UNSAFE:'#c62828'};
  const RISK = ['#2e7d32', '#e6c84a', '#e8742a', '#c62828'];   // low, medium, high, critical
  let map, L_ = {}, roads = [], nodes = [], dots = [], shelters = [], hazard = null, originMark = null, levels, onPick = () => {};

  function init(pickHandler) {
    onPick = pickHandler;
    map = L.map('map', {preferCanvas: true}).setView([17.385, 78.4867], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {attribution: '© OpenStreetMap (base map only; overlays are synthetic)', opacity: .45}).addTo(map);
    ['hazard', 'risk', 'roads', 'population', 'shelters', 'agents', 'routes'].forEach(k => L_[k] = L.layerGroup().addTo(map));
    L.control.layers(null, {'Disaster zone': L_.hazard, 'Risk map': L_.risk, 'Roads': L_.roads, 'Population': L_.population,
      'Shelters': L_.shelters, 'Evacuees': L_.agents, 'Routes': L_.routes}, {collapsed: false}).addTo(map);
    map.on('click', e => onPick(e.latlng));
    document.getElementById('legend').innerHTML =
      '<b>Risk</b> <span style="color:#2e7d32">●</span> low <span style="color:#b58900">●</span> medium <span style="color:#e8742a">●</span> high <span style="color:#c62828">●</span> critical<br>' +
      '<b>Road</b> <span style="color:#8fa3a0">━</span> open <span style="color:#d9a400">━</span> congested <span style="color:#e8742a">━</span> dangerous <span style="color:#c62828">╍</span> blocked<br>' +
      '<b>Routes</b> <span style="color:#8e24aa">╍</span> baseline <span style="color:#f2b600">━</span> proposed &nbsp; <b>Shelter</b> ◯';
  }

  const riskColor = r => RISK[r >= levels.critical ? 3 : r >= levels.high ? 2 : r >= levels.medium ? 1 : 0];

  function drawStatic(layers) {
    Object.values(L_).forEach(l => l.clearLayers());
    roads = []; nodes = []; dots = []; shelters = []; hazard = null; originMark = null; levels = layers.risk_levels;
    roads = layers.roads.map(r => L.polyline([r.a, r.b], {weight: r.arterial ? 4 : 2, color: ROAD.OPEN}).addTo(L_.roads));
    nodes = layers.nodes.map(p => L.circleMarker(p, {radius: 6, weight: 0, fillOpacity: .15, fillColor: RISK[0]}).addTo(L_.risk));
    layers.population.forEach(z => L.circleMarker(z.latlon, {radius: Math.min(11, 2 + Math.sqrt(z.people) / 4), weight: 1,
      color: '#1565c0', fillColor: '#42a5f5', fillOpacity: z.ordered ? .45 : .2}).bindTooltip(`${z.people} people${z.ordered ? '' : ' (not ordered to evacuate)'}`).addTo(L_.population));
    map.fitBounds(L.latLngBounds(layers.roads.flatMap(r => [r.a, r.b])).pad(.05));
  }

  function render(st) {
    st.roads.forEach(([s], i) => roads[i].setStyle({color: ROAD[s], dashArray: s === 'BLOCKED' ? '4 4' : null}));
    st.node_risk.forEach((r, i) => nodes[i].setStyle({fillColor: riskColor(r), fillOpacity: r > 0.02 ? .55 : .12}));
    if (st.disaster) {
      if (!hazard) hazard = L.circle(st.disaster.center, {color: '#c62828', fillColor: '#c62828', fillOpacity: .1, weight: 1}).addTo(L_.hazard);
      hazard.setRadius(st.disaster.radius_m);
    }
    st.shelters.forEach((s, i) => {
      if (!shelters[i]) shelters[i] = L.circleMarker(s.latlon, {radius: 11, weight: 4, fillColor: '#fff', fillOpacity: .95}).addTo(L_.shelters);
      shelters[i].setStyle({color: SHELTER[s.status]}).unbindTooltip().bindTooltip(
        `<b>Shelter ${s.id}</b><br>Capacity ${s.capacity}<br>Occupancy ${s.occupancy}<br>Available ${s.available}<br>Risk ${s.risk_level} (${s.risk})<br>${s.status}`);
    });
    st.agents.forEach(([lat, lon, status], i) => {
      if (!dots[i]) dots[i] = L.circleMarker([lat, lon], {radius: 3, weight: 0, fillOpacity: .9}).addTo(L_.agents);
      dots[i].setLatLng([lat, lon]).setStyle({fillColor: AGENT[status]});
    });
  }

  function drawRoutes(plan) {
    L_.routes.clearLayers();
    if (originMark) map.removeLayer(originMark);
    originMark = L.marker(plan.origin.latlon).addTo(map).bindTooltip('Evacuation origin');
    if (plan.baseline) L.polyline(plan.baseline.path, {color: '#8e24aa', weight: 5, dashArray: '8 8', opacity: .9}).bindTooltip('Baseline: shortest path to nearest shelter').addTo(L_.routes);
    if (plan.proposed) L.polyline(plan.proposed.path, {color: '#f2b600', weight: 6, opacity: .95}).bindTooltip('Proposed: risk-aware route').addTo(L_.routes);
  }

  return {init, drawStatic, render, drawRoutes};
})();
