/* Small DOM + formatting helpers shared by every module. */
const $ = id => document.getElementById(id);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v;
    else if (k === 'html') e.innerHTML = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
  }
  kids.flat().forEach(c => e.append(c != null && c.nodeType ? c : document.createTextNode(c ?? '')));
  return e;
};
const icon = name => {
  const NS = 'http://www.w3.org/2000/svg', s = document.createElementNS(NS, 'svg'), u = document.createElementNS(NS, 'use');
  s.setAttribute('class', 'ic'); u.setAttribute('href', '#' + name); s.append(u); return s;
};
const fmtNum = n => Math.round(n ?? 0).toLocaleString();
const fmtClock = s => { const m = Math.floor((s || 0) / 60); return String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); };
const fmtMin = s => s == null ? '–' : (s / 60).toFixed(1);
const pct = v => v == null ? '–' : (v * 100).toFixed(1) + '%';
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const cssVar = n => getComputedStyle(document.body).getPropertyValue(n).trim();
const reduceMotion = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

/* Count a number up/down inside a node. */
function animateNumber(node, to, ms = 380) {
  to = Math.round(to ?? 0);
  const from = node._v ?? 0;
  node._v = to;
  if (reduceMotion || from === to || ms <= 0) { node.textContent = to.toLocaleString(); return; }
  const t0 = performance.now();
  cancelAnimationFrame(node._raf);
  const tick = now => {
    const k = Math.min(1, (now - t0) / ms), e = 1 - Math.pow(1 - k, 3);
    node.textContent = Math.round(from + (to - from) * e).toLocaleString();
    if (k < 1) node._raf = requestAnimationFrame(tick);
  };
  node._raf = requestAnimationFrame(tick);
}

function toast(msg, kind = 'info', ms = 3600) {
  const t = el('div', {class: 'toast ' + kind, role: 'status'}, msg);
  $('toasts').append(t);
  setTimeout(() => { t.style.opacity = 0; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 320); }, ms);
}

/* Segmented control: buttons[role=radio][data-v]. */
function bindSeg(seg, onChange) {
  seg.addEventListener('click', e => {
    const b = e.target.closest('button[data-v]');
    if (!b) return;
    setSeg(seg, b.dataset.v);
    onChange(b.dataset.v);
  });
}
function setSeg(seg, value) {
  seg.querySelectorAll('button[data-v]').forEach(b => b.setAttribute('aria-checked', String(b.dataset.v === String(value))));
}