/* Shows where the data comes from: the pill in the header and the map's attribution follow the active dataset
   (GET /api/dataset), so a real dataset is never labelled "synthetic" and a synthetic one is never labelled real. */
(() => {
  const LABEL = {synthetic: 'Synthetic data', real: 'Real data', mixed: 'Mixed data'};

  async function show() {
    try {
      const d = await API.get('/dataset');
      if (typeof Pages !== 'undefined') Pages.setDataset(d);
      const pill = document.querySelector('.topbar .pill');
      if (pill) {
        const layers = Object.entries(d.layers).map(([k, v]) => `${k}: ${v.source}${v.origin ? ' (' + v.origin + ')' : ''}`).join(' · ');
        pill.textContent = LABEL[d.kind] || 'Data';
        pill.title = `Dataset "${d.name}". ${layers}.` + (d.assumptions.length ? ' Assumptions: ' + d.assumptions.join(' ') : '');
        if (d.kind === 'real') { pill.style.background = '#d8f1e2'; pill.style.color = '#14532d'; }
      }
      if (typeof MapView !== 'undefined' && MapView.setOverlayNote) {      // top-level const is not on window
        MapView.setOverlayNote(d.kind === 'synthetic' ? 'overlays: synthetic data' : `data: ${d.name} (${d.kind})`);
      }
    } catch (e) {
      const detail = $('datasetDetail');
      if (detail) detail.textContent = 'Could not retrieve dataset provenance: ' + e.message;
    }
  }
  document.addEventListener('DOMContentLoaded', show);
})();