/* Playback loop: calls POST /api/simulation/step on a timer and hands each state to the UI. */
const Sim = (() => {
  let timer = null, running = false, busy = false, speed = 2;
  const cb = {state() {}, finished() {}, change() {}, error() {}};

  async function tick(n = speed) {
    if (busy) return;
    busy = true;
    try {
      const st = await API.post('/simulation/step', {steps: n});
      cb.state(st);
      if (st.finished) { pause(); cb.finished(st); }
    } catch (e) { pause(); cb.error(e); }
    finally { busy = false; }
  }
  function play() { if (running) return; running = true; timer = setInterval(() => tick(), 450); cb.change(); }
  function pause() { clearInterval(timer); timer = null; const was = running; running = false; if (was) cb.change(); }

  return {
    bind: c => Object.assign(cb, c),
    play, pause, tick,
    step: async () => { pause(); await tick(1); },
    setSpeed: v => { speed = +v; },
    isRunning: () => running,
  };
})();