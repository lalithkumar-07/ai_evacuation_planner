/* Dependency-free five-page navigation smoke test using a minimal DOM mock.
   Run: node scripts/check_navigation.js
   For layout, Leaflet and actual browser integration, use a real browser. */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const FRONT = path.resolve(__dirname, '../frontend');
const html = fs.readFileSync(path.join(FRONT, 'index.html'), 'utf8');
const views = ['dashboard','disaster','roads','evacuation','analytics'];
for(const page of views) {
  assert(html.includes(`id="page-${page}"`), `Missing ${page} page`);
  assert(html.includes(`href="#/${page}"`), `Missing ${page} link`);
}
assert.strictEqual((html.match(/data-page-link=/g) || []).length, 5, 'There must be five navigation links');
assert.strictEqual((html.match(/id="viewMap"/g) || []).length, 1, 'The Leaflet map must not be duplicated');
const items = new Map();
function node(id) {
  if (items.has(id)) return items.get(id);
  const classes = new Set();
  const el = {id, textContent:'', dataset:{}, children:[], attributes:{}, hidden:false,
    classList:{toggle:(name,on)=>{if(on)classes.add(name);else classes.delete(name)},
      contains:(name)=>classes.has(name)},
    get parentNode(){return this._parent},
    append(child){this.children.push(child);child._parent=this},
    setAttribute(k,v){this.attributes[k]=v}, removeAttribute(k){delete this.attributes[k]},
    getAttribute(k){return this.attributes[k]},
    addEventListener(){}, replaceChildren(...kids){this.children=kids},
  };
  items.set(id,el);return el;
}
const links = views.map(v => {const a=node('link-'+v);a.dataset.pageLink=v;return a});
const document = {body:{dataset:{},classList:{toggle(){}}},getElementById:node,
  querySelectorAll(sel){return sel==='[data-page-link]' ? links : []}};
const map = node('viewMap');
let mapProfiles=[];
const scope = {document, window:{addEventListener(){}}, $:node, location:{hash:''},history:{replaceState(a,b,hash){scope.location.hash=hash}},
  MapView:{setProfile(v){mapProfiles.push(v)},invalidate(){},fitAll(){}},
  Charts:{resize(){}},
  Chart:class {resize(){} destroy(){}},
  API:{get(){return Promise.resolve({dataset:'demo',by_class:{}})}},
  requestAnimationFrame(fn){fn()},setTimeout(fn){/* Don't run delayed browser layout in DOM mock */},
  fmtClock:x=>''+x,fmtNum:x=>''+x,el:()=>node('x'),console};
vm.createContext(scope);
vm.runInContext(fs.readFileSync(path.join(FRONT,'js/pages.js'),'utf8'),scope);
const Pages = vm.runInContext('Pages',scope);
Pages.init();
for(const slug of views) {
  scope.location.hash='#/'+slug;
  Pages.nav();
  assert.strictEqual(document.body.dataset.page,slug);
  assert.strictEqual(node('pageTitle').textContent,{
    dashboard:'Dashboard',disaster:'Disaster & Risk Monitoring',roads:'Road Network & Traffic',
    evacuation:'Evacuation Management',analytics:'Analytics & Data Sources'}[slug]);
  assert.strictEqual(views.filter(v=>!node('page-'+v).classList.contains('hidden')).length,1);
  assert.strictEqual(links.filter(a=>a.getAttribute('aria-current')==='page').length,1);
  assert.strictEqual(links.find(a=>a.getAttribute('aria-current')==='page').dataset.pageLink,slug);
  if (['disaster','roads','evacuation'].includes(slug)) {
    assert.strictEqual(map.parentNode.id, {disaster:'mapSlotDisaster',roads:'mapSlotRoads',evacuation:'mapSlotEvacuation'}[slug]);
  }
}
assert.deepStrictEqual(mapProfiles,['disaster','roads','evacuation']);
console.log('Five-page navigation smoke check: PASS (5 routes, 5 active states, 1 relocated map)');