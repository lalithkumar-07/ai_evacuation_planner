/* Analytics charts (Chart.js). */
const Charts = (() => {
  let live = null, cmp = null;
  const opts = (x, y) => ({animation: false, parsing: false, scales: {x: {type: 'linear', title: {display: true, text: x}}, y: {title: {display: true, text: y}}}});

  function resetLive() {
    if (live) live.destroy();
    live = new Chart(document.getElementById('chart'), {type: 'line', options: opts('minutes', 'people'),
      data: {datasets: [{label: 'Evacuated', data: [], borderColor: '#2e7d32', pointRadius: 0},
                        {label: 'Remaining', data: [], borderColor: '#c62828', pointRadius: 0},
                        {label: 'At risk now', data: [], borderColor: '#e8742a', pointRadius: 0}]}});
  }
  function pushLive(m) {
    const x = m.t / 60, ds = live.data.datasets;
    if (ds[0].data.length && ds[0].data.at(-1).x === x) return;
    ds[0].data.push({x, y: m.evacuated}); ds[1].data.push({x, y: m.remaining}); ds[2].data.push({x, y: m.at_risk});
    live.update();
  }
  function drawComparison(r) {
    if (cmp) cmp.destroy();
    const s = a => a.map(m => ({x: m.t / 60, y: m.evacuated}));
    cmp = new Chart(document.getElementById('cmpChart'), {type: 'line', options: opts('minutes', 'people evacuated'),
      data: {datasets: [{label: 'Baseline', data: s(r.baseline.series), borderColor: '#8e24aa', pointRadius: 0},
                        {label: 'Proposed', data: s(r.proposed.series), borderColor: '#0f6b6f', pointRadius: 0}]}});
  }
  return {resetLive, pushLive, drawComparison};
})();
