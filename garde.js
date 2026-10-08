self.AG_STAMPS=self.AG_STAMPS||{};self.AG_STAMPS['garde.js']='0.5.2'; /* numéro écrit par verifications/sync_version.py : ne pas modifier à la main */
/* Agenda : la « garde ». Chargée AVANT le reste, elle ne dépend de rien d'autre.
   Elle sert à ne jamais laisser un écran figé sans explication :
   - elle note dans le journal de mise à jour (Réglages) toute erreur JavaScript non attrapée et toute promesse rejetée ;
   - elle vérifie que tous les fichiers de la page sont de la MÊME version (chacun porte son numéro) ; sinon elle se recharge UNE fois
     en contournant les réserves, puis, si le problème reste, affiche un message simple avec un bouton ;
   - elle affiche ce message aussi quand le premier affichage échoue ou n'arrive pas.
   Elle n'affiche jamais rien de lisible quand l'écran est masqué (le message attend le retour de l'écran). Aucune donnée de personne ici. */
(function () {
'use strict';
var V = self.APP_VERSION || '?';
var FILES = ['./', 'index.html', 'garde.js', 'db.js', 'rides.js', 'fuel.js', 'app.js', 'style.css', 'version.js', 'manifest.json', 'icon-192.png', 'icon-512.png'];
var G = self.AGG = { pending: [], sink: null, shown: false, deferred: false, problemOn: false };

/* ----- journal : avant que app.js soit prêt, les lignes attendent ici ; ensuite elles passent par app.js (logEvt) ----- */
G.log = function (text) {
  if (G.sink) return G.sink(text);
  G.pending.push({ t: new Date(Date.now()).toISOString(), e: text, v: V });
  return Promise.resolve();
};
function shortMsg(m) { return String(m == null ? '' : m).replace(/\s+/g, ' ').slice(0, 100); }
function fileOf(s) { return s ? String(s).split('?')[0].split('/').pop() : ''; }
var errCount = 0;
G.caught = function (er, where, src, line) {
  var msg = er && er.message !== undefined ? er.message : er;
  if (errCount++ < 3) G.log('Erreur : ' + shortMsg(msg) + (where ? ' [' + where + ']' : '') + (src ? ' (' + fileOf(src) + (line ? ':' + line : '') + ')' : ''));
  if (!G.shown) G.problem();
};
window.addEventListener('error', function (ev) {
  var t = ev.target;
  if (t && t !== window && (t.tagName === 'SCRIPT' || t.tagName === 'LINK')) {          /* un fichier de la page n'a pas pu être chargé */
    G.log('Erreur : fichier non chargé ' + fileOf(t.src || t.href)); if (!G.shown) G.problem(); return;
  }
  G.caught(ev.error || ev.message, '', ev.filename, ev.lineno);
}, true);
window.addEventListener('unhandledrejection', function (ev) {
  var r = ev.reason; G.caught(r && r.message !== undefined ? r : (r && r.name) || r || 'promesse rejetée', 'promesse');
});

/* ----- message simple « Un problème est survenu à l'affichage » (jamais sous l'écran neutre) ----- */
function masked() { var v = document.getElementById('veil'); return !!(v && v.classList.contains('on')); }
function showProblem() {
  var f = document.getElementById('fatal'); if (!f || f.classList.contains('on')) return;       /* un autre message déjà affiché reste en place */
  document.getElementById('fatal-title').textContent = 'Un problème est survenu à l’affichage';
  document.getElementById('fatal-text').textContent = 'Touchez pour recharger. Rien n’a été effacé.';
  var b = document.getElementById('fatal-btn'); if (b) { b.hidden = false; b.textContent = 'Recharger'; b.onclick = function () { G.reload(true); }; }
  f.classList.add('on'); G.problemOn = true;
}
G.problem = function () {
  if (G.problemOn || G.deferred) return;
  var run = function () { if (masked()) { G.deferred = true; return; } showProblem(); };
  if (document.getElementById('fatal')) run(); else document.addEventListener('DOMContentLoaded', run);
};
G.unmasked = function () { if (G.deferred) { G.deferred = false; if (!G.shown) showProblem(); } };

/* ----- rechargement ; avec bypass = on vide les réserves de l'appli et on redemande tous les fichiers au site ----- */
G.reload = function (bypass) {
  var go = function () { try { if (self.AG && self.AG.closeDb) self.AG.closeDb(); } catch (e) { /* rien */ } location.reload(); };
  if (!bypass) { go(); return; }
  var done = false, end = function () { if (!done) { done = true; go(); } };
  setTimeout(end, 6000);                                                                         /* jamais bloqué si une étape traîne */
  /* hors connexion on ne vide RIEN (sinon l'appli ne s'ouvrirait plus) : « ag_net » = le service worker laisse passer vers le site */
  var probe = fetch('version.js?ag_net=' + Date.now(), { cache: 'no-store' }).then(function (r) { return r.ok; }, function () { return false; });
  probe.then(function (online) { if (!online) { end(); return; } clean(); });
  function clean() {
  var step = Promise.resolve();
  try { step = step.then(function () { return caches.keys(); }).then(function (ks) { return Promise.all(ks.filter(function (k) { return k.indexOf('agenda-') === 0; }).map(function (k) { return caches.delete(k); })); }); } catch (e) { /* pas de réserves */ }
  try { step = step.then(function () { return navigator.serviceWorker.getRegistrations(); }).then(function (rs) { return Promise.all(rs.map(function (r) { return r.unregister(); })); }); } catch (e) { /* pas de service worker */ }
  step.catch(function () {}).then(function () { return Promise.all(FILES.map(function (n) { return fetch(n, { cache: 'reload' }).catch(function () {}); })); }).then(end, end);
  }
};

/* ----- tous les fichiers sont-ils de la même version ? ----- */
function cssStamp() { try { return getComputedStyle(document.documentElement).getPropertyValue('--ag-version').replace(/["'\s]/g, ''); } catch (e) { return ''; } }
function metaStamp() { var m = document.querySelector('meta[name="ag-version"]'); return m ? m.getAttribute('content') : ''; }
G.mismatches = function () {
  var S = self.AG_STAMPS || {}, bad = [];
  ['garde.js', 'db.js', 'rides.js', 'fuel.js', 'app.js'].forEach(function (n) { if (S[n] !== V) bad.push(n + ' ' + (S[n] || 'sans numéro')); });
  var c = cssStamp(); if (c !== V) bad.push('style.css ' + (c || 'sans numéro'));
  var m = metaStamp(); if (m !== V) bad.push('index.html ' + (m || 'sans numéro'));
  return bad;
};
function flagGet() { try { return sessionStorage.getItem('ag_mix_reload'); } catch (e) { return 'indisponible'; } }
function flagSet(v) { try { if (v) sessionStorage.setItem('ag_mix_reload', v); else sessionStorage.removeItem('ag_mix_reload'); return true; } catch (e) { return false; } }
G.checkVersions = function () {
  var bad = G.mismatches();
  if (!bad.length) { if (flagGet() && flagGet() !== 'indisponible') flagSet(null); return true; }
  var msg = 'Fichiers de versions différentes : ' + bad.join(', ') + ' (version.js ' + V + ')';
  if (flagGet()) { G.log(msg + ' : le problème reste après un rechargement'); G.problem(); return false; }
  if (!flagSet('1')) { G.log(msg); G.problem(); return false; }
  Promise.race([Promise.resolve(G.log(msg + ' : rechargement unique en contournant les réserves')), new Promise(function (r) { setTimeout(r, 1500); })]).then(function () { G.reload(true); });
  return false;
};
window.addEventListener('load', function () { G.checkVersions(); });

/* ----- premier affichage : réussi, vide, ou jamais arrivé ----- */
/* ----- mise en page : le bas du menu doit rester dans la zone visible ----- */
/* #app est collé aux 4 bords de la fenêtre (CSS : position fixed, inset 0, aucune hauteur écrite). Filet de sécurité : si malgré tout le menu dépasse la zone
   visible (Chrome Android peut garder une hauteur trop grande juste après un rechargement), on fixe la hauteur sur la zone visible et on la suit ensuite. */
var fixedH = false, fixLogged = false;
function visibleH() { return Math.round(window.visualViewport ? window.visualViewport.height : window.innerHeight); }
function metrics() { var n = document.querySelector('.nav'); return { H: Math.round(window.innerHeight), V: visibleH(), B: n ? Math.round(n.getBoundingClientRect().bottom) : 0 }; }
G.layoutText = function () { var m = metrics(); return 'fenêtre ' + m.H + ', visible ' + m.V + ', bas du menu ' + m.B; };
G.layout = function () {
  var app = document.getElementById('app'), n = document.querySelector('.nav'); if (!app || !n) return;
  var a = document.activeElement, typing = a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName);        /* clavier ouvert : on laisse faire */
  var m = metrics();
  if (!fixedH && !typing && m.B > m.V + 1) {
    fixedH = true;
    if (!fixLogged) { fixLogged = true; G.log('Mise en page corrigée : ' + G.layoutText()); }
  }
  if (fixedH && !typing) app.style.setProperty('height', m.V + 'px', 'important');
};
['resize', 'orientationchange', 'pageshow', 'visibilitychange'].forEach(function (ev) { window.addEventListener(ev, function () { G.layout(); }); });
if (window.visualViewport) window.visualViewport.addEventListener('resize', function () { G.layout(); });
document.addEventListener('DOMContentLoaded', function () { G.layout(); [300, 1000, 2000].forEach(function (ms) { setTimeout(G.layout, ms); }); });

G.displayed = function () {
  var nav = document.querySelectorAll('.nav button.t').length, s = document.getElementById('s-aujourdhui'), r = document.querySelector('.nav');
  var okNav = nav === 4 && r && r.getBoundingClientRect().height > 10 && getComputedStyle(r).display !== 'none';
  if (okNav && s && s.children.length > 0) { if (!G.shown) { G.shown = true; G.log('Écran affiché (menu prêt)'); G.log('Mise en page : ' + G.layoutText()); } return true; }
  G.log('Écran pas affiché correctement : ' + (okNav ? 'écran vide' : 'menu du bas absent'));
  G.problem(); return false;
};
setTimeout(function () { if (!G.shown) { G.log('Écran pas affiché après 8 secondes'); G.problem(); } }, 8000);
})();
