/* API client + simulation playback loop. */
const API = (() => {
  const h = async r => { if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (e) {} throw new Error(typeof m === 'string' ? m : JSON.stringify(m)); } return r.json(); };
  return {get: p => fetch('/api' + p).then(h),
          post: (p, b) => fetch('/api' + p, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b || {})}).then(h)};
})();

const Sim = (() => {
  let timer = null, running = false, onState = () => {}, onFinish = () => {};
  const speed = () => +document.getElementById('speed').value;
  async function tick(n) {
    try { const st = await API.post('/simulation/step', {steps: n}); onState(st); if (st.finished) { stop(); onFinish(st); } }
    catch (e) { stop(); }
  }
  function play() { running = true; timer = setInterval(() => tick(speed()), 500); }
  function stop() { clearInterval(timer); timer = null; running = false; }
  return {
    bind(stateCb, finishCb) { onState = stateCb; onFinish = finishCb; },
    play, stop, tick, isRunning: () => running,
  };
})();
