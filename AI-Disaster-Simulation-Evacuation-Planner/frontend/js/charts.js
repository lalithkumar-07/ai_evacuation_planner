/* Chart.js wrappers: live trends (3 modes) and the baseline-vs-proposed curves. */
const Charts = (() => {
  let live = null, cmp = null, series = [], mode = 'evac', cmpData = null, cmpMode = 'evac';

  function theme() {
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.font.size = 11;
    Chart.defaults.color = cssVar('--muted');
    Chart.defaults.borderColor = cssVar('--line');
  }
  const opts = (yTitle, y2) => ({
    animation: false, parsing: false, responsive: true, maintainAspectRatio: false,
    interaction: {mode: 'index', intersect: false},
    plugins: {legend: {position: 'bottom', labels: {boxWidth: 10, boxHeight: 10, usePointStyle: true}},
              tooltip: {callbacks: {title: i => i.length ? 'Minute ' + i[0].parsed.x.toFixed(0) : ''}}},
    scales: {x: {type: 'linear', min: 0, title: {display: true, text: 'minutes'}, ticks: {maxTicksLimit: 7}},
             y: {beginAtZero: true, title: {display: !!yTitle, text: yTitle}, ticks: {maxTicksLimit: 5}},
             ...(y2 ? {y2: {position: 'right', beginAtZero: true, grid: {drawOnChartArea: false}, title: {display: true, text: y2}}} : {})},
  });
  const line = (label, color, data, extra = {}) => ({label, data, borderColor: color, backgroundColor: color + '22', borderWidth: 2, pointRadius: 0, tension: .25, ...extra});

  const MODES = {
    evac: () => ({o: opts('people'), ds: [
      line('Evacuated', cssVar('--ok'), series.map(m => ({x: m.t / 60, y: m.evacuated})), {fill: true}),
      line('Remaining', cssVar('--crit'), series.map(m => ({x: m.t / 60, y: m.remaining}))),
      line('At risk now', cssVar('--high'), series.map(m => ({x: m.t / 60, y: m.at_risk})))]}),
    cong: () => ({o: opts('load / capacity'), ds: [
      line('Mean congestion', cssVar('--brand'), series.map(m => ({x: m.t / 60, y: +m.congestion_mean.toFixed(3)}))),
      line('Peak congestion', cssVar('--warn'), series.map(m => ({x: m.t / 60, y: +m.congestion_peak.toFixed(3)})))]}),
    expo: () => ({o: opts('person-hazard-min', 'reroutes'), ds: [
      line('Cumulative exposure', cssVar('--high'), series.map(m => ({x: m.t / 60, y: +(m.exposure / 60).toFixed(1)})), {fill: true}),
      line('Reroutes', cssVar('--brand'), series.map(m => ({x: m.t / 60, y: m.reroutes})), {yAxisID: 'y2', stepped: true})]}),
  };

  function init() { theme(); build(); }
  function build() {
    if (live) live.destroy();
    const m = MODES[mode]();
    live = new Chart($('liveChart'), {type: 'line', data: {datasets: m.ds}, options: m.o});
  }
  function refresh() { const m = MODES[mode](); live.data.datasets = m.ds; live.update('none'); }

  return {
    init,
    reset() { series = []; refresh(); },
    push(m) { if (series.length && series.at(-1).t === m.t) return; series.push(m); refresh(); },
    setMode(v) { mode = v; build(); },
    restyle() { theme(); build(); if (cmp) drawComparison(cmpData); },
    setCmpMode(v) { cmpMode = v; if (cmpData) drawComparison(cmpData); },
    drawComparison,
  };

  function drawComparison(r) {
    cmpData = r;
    if (cmp) cmp.destroy();
    const f = s => s.map(m => ({x: m.t / 60, y: cmpMode === 'evac' ? m.evacuated : +(m.exposure / 60).toFixed(1)}));
    cmp = new Chart($('cmpChart'), {type: 'line', options: opts(cmpMode === 'evac' ? 'people evacuated' : 'person-hazard-min'),
      data: {datasets: [line('Baseline', cssVar('--route-base'), f(r.baseline.series), {borderDash: [6, 4]}),
                        line('Proposed', cssVar('--route-new'), f(r.proposed.series))]}});
  }
})();