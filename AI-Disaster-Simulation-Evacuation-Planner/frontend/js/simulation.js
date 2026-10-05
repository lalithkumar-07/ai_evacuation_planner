/* API client + simulation playback loop. */

/* Session id: one random id per browser TAB (sessionStorage), sent on every request as X-Session-Id so the
   server keeps this tab's simulation separate from everyone else's. Reloading keeps it; a new tab gets a new one. */
const SessionId = (() => {
  const KEY = 'evac.sessionId';
  const make = () => (window.crypto && crypto.randomUUID)
    ? crypto.randomUUID()
    : Array.from({length: 24}, () => Math.floor(Math.random() * 16).toString(16)).join('') + Date.now().toString(36);
  let id = null;
  try { id = sessionStorage.getItem(KEY); } catch (e) { /* storage blocked: fall back to an in-memory id */ }
  if (!id) { id = make(); try { sessionStorage.setItem(KEY, id); } catch (e) { /* ignore */ } }
  return id;
})();

const API = (() => {
  const h = async r => { if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (e) {} throw new Error(typeof m === 'string' ? m : JSON.stringify(m)); } return r.json(); };
  const headers = extra => ({'X-Session-Id': SessionId, ...extra});
  return {sessionId: SessionId,
          get: p => fetch('/api' + p, {headers: headers()}).then(h),
          post: (p, b) => fetch('/api' + p, {method: 'POST', headers: headers({'Content-Type': 'application/json'}), body: JSON.stringify(b || {})}).then(h),
          del: p => fetch('/api' + p, {method: 'DELETE', headers: headers()}).then(h)};
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