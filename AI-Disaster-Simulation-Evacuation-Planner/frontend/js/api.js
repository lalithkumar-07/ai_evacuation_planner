/* Transport layer. Every request carries X-Session-Id so the server keeps THIS tab's simulation separate.
   The id lives in sessionStorage: reloading keeps it, a new tab gets a new one. */
const SessionId = (() => {
  const KEY = 'evac.sessionId';
  const make = () => (window.crypto && crypto.randomUUID)
    ? crypto.randomUUID()
    : Array.from({length: 24}, () => Math.floor(Math.random() * 16).toString(16)).join('') + Date.now().toString(36);
  let id = null;
  try { id = sessionStorage.getItem(KEY); } catch (e) { /* storage blocked: in-memory id */ }
  if (!id) { id = make(); try { sessionStorage.setItem(KEY, id); } catch (e) { /* ignore */ } }
  return id;
})();

const API = (() => {
  const text = d => Array.isArray(d) ? d.map(x => ((x.loc || []).slice(-1)[0] || 'value') + ': ' + x.msg).join('; ')
                  : typeof d === 'string' ? d : JSON.stringify(d);
  async function call(path, opts = {}) {
    let r;
    try {
      r = await fetch('/api' + path, {...opts, headers: {'X-Session-Id': SessionId, ...(opts.body ? {'Content-Type': 'application/json'} : {})}});
    } catch (e) {
      const err = new Error('Cannot reach the planner backend. Is it running?'); err.network = true; throw err;
    }
    if (!r.ok) {
      let m = r.statusText;
      try { m = text((await r.json()).detail) || m; } catch (e) { /* not JSON */ }
      const err = new Error(m); err.status = r.status; throw err;
    }
    return r.json();
  }
  return {
    sessionId: SessionId,
    get: p => call(p),
    post: (p, b) => call(p, {method: 'POST', body: JSON.stringify(b || {})}),
    del: p => call(p, {method: 'DELETE'}),
  };
})();