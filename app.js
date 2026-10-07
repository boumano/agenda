/* Agenda : coquille installable (étape 1). Aucune donnée de personne, aucune bibliothèque, aucune adresse internet. */
(function () {
'use strict';

/* ========= petits outils ========= */
function $(s, r) { return (r || document).querySelector(s); }
function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
var APP_VERSION = self.APP_VERSION || '?';

/* ========= stockage : IndexedDB avec numéro de structure et migrations =========
   IndexedDB = la base de données intégrée à Chrome. Le numéro de structure (« schema ») est celui de la dernière entrée de MIGRATIONS.
   Règle : on n'ajoute QUE de nouvelles entrées à la fin (version suivante) ; on ne modifie jamais une entrée déjà publiée ; une migration n'efface rien. */
var DB_NAME = 'agenda';
var MIGRATIONS = [
  { version: 1, up: function (db, tx) {
    db.createObjectStore('meta', { keyPath: 'key' });       /* informations techniques (numéro de structure, premier lancement…) */
    db.createObjectStore('settings', { keyPath: 'key' });   /* réglages de Pascal (durée avant masquage…) */
    tx.objectStore('meta').put({ key: 'created_at', value: new Date().toISOString() });
  } }
];
function latest(migrations) { return migrations[migrations.length - 1].version; }

/* Ouvre (et met à niveau si besoin) une base. `migrations` est paramétrable pour pouvoir essayer le mécanisme sur une base jetable. */
function openDatabase(name, migrations) {
  return new Promise(function (resolve, reject) {
    var target = latest(migrations), req;
    try { req = indexedDB.open(name, target); } catch (e) { reject({ code: 'error', error: e }); return; }
    req.onupgradeneeded = function (ev) {
      var db = req.result, tx = req.transaction, from = ev.oldVersion;
      migrations.forEach(function (m) { if (m.version > from && m.version <= target) m.up(db, tx); });
      tx.objectStore('meta').put({ key: 'schema_version', value: target });
    };
    req.onsuccess = function () { resolve(req.result); };
    req.onerror = function () { var er = req.error; reject({ code: er && er.name === 'VersionError' ? 'newer' : 'error', error: er }); };
    req.onblocked = function () { /* un autre onglet garde l'ancienne structure ouverte : on attend */ };
  });
}
function dbGet(db, store, key) {
  return new Promise(function (resolve, reject) {
    var r = db.transaction(store).objectStore(store).get(key);
    r.onsuccess = function () { resolve(r.result ? r.result.value : undefined); };
    r.onerror = function () { reject(r.error); };
  });
}
function dbPut(db, store, key, value) {
  return new Promise(function (resolve, reject) {
    var tx = db.transaction(store, 'readwrite');
    tx.objectStore(store).put({ key: key, value: value });
    tx.oncomplete = function () { resolve(); };
    tx.onerror = function () { reject(tx.error); };
  });
}

/* ========= état de l'interface ========= */
var db = null, schemaVersion = null;
var cur = 'aujourdhui', tab = 'aujourdhui';
var idleSec = 120;                       /* réglable : 0 (jamais), 60, 120, 600 */
var veilEl = $('#veil'), veilOn = false, lastTouch = Date.now(), swallowClick = false;
var toastEl = $('#toast'), toastTimer = null;

function toast(text, ms) {
  clearTimeout(toastTimer);
  toastEl.textContent = text; toastEl.hidden = false;
  toastTimer = setTimeout(function () { toastEl.hidden = true; }, ms || 3000);
}

/* ========= écrans et barre du bas ========= */
var TABS = ['aujourdhui', 'personnes', 'bilan', 'essence'];
function go(id) {
  cur = id;
  if (TABS.indexOf(id) >= 0) tab = id; else tab = 'bilan';          /* Réglages s'ouvre depuis le Bilan : le Bilan reste allumé */
  $$('.screen').forEach(function (s) { s.classList.toggle('on', s.id === 's-' + id); });
  $$('.nav button.t').forEach(function (b) {
    var on = b.dataset.t === tab; b.classList.toggle('on', on);
    if (on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  if (id === 'reglages') refreshReglages();
}

/* ========= Réglages ========= */
function refreshReglages() {
  $('#rg-version').textContent = APP_VERSION;
  $('#rg-schema').textContent = schemaVersion == null ? '…' : String(schemaVersion);
  $$('[data-a="idle"]').forEach(function (b) {
    var on = +b.dataset.n === idleSec; b.classList.toggle('sel', on); b.setAttribute('aria-pressed', on);
  });
  $('#rg-update-txt').textContent = updateReady ? 'Une nouvelle version est disponible.' : 'Cette version est la plus récente.';
  refreshPersist();
}
function refreshPersist() {
  var el = $('#rg-persist'), btn = $('#rg-persist-btn'), card = $('#rg-card-stock');
  if (!(navigator.storage && navigator.storage.persisted)) { el.textContent = 'indisponible'; btn.hidden = true; card.classList.add('nobtn'); return Promise.resolve(); }
  return navigator.storage.persisted().then(function (p) {
    el.textContent = p ? 'accordé' : 'non accordé';
    btn.hidden = !!p; card.classList.toggle('nobtn', !!p);
  }, function () { el.textContent = 'indisponible'; btn.hidden = true; card.classList.add('nobtn'); });
}
/* demande de stockage persistant : au tout premier lancement, puis seulement si Pascal touche « Redemander » */
function askPersist() {
  if (!(navigator.storage && navigator.storage.persist)) return Promise.resolve();
  var already = navigator.storage.persisted ? navigator.storage.persisted() : Promise.resolve(false);
  return already.then(function (p) { return p ? true : navigator.storage.persist(); }).catch(function () { return false; });
}
function firstLaunchStorage() {
  return dbGet(db, 'meta', 'persist_asked').then(function (asked) {
    if (asked) return refreshPersist();
    return askPersist().then(function () { return dbPut(db, 'meta', 'persist_asked', new Date().toISOString()); }).then(refreshPersist);
  });
}
function setIdle(n) {
  idleSec = n; lastTouch = Date.now(); refreshReglages();
  if (db) dbPut(db, 'settings', 'idle_sec', n).catch(function () {});
}

/* ========= mises à jour (service worker) : jamais de rechargement automatique ========= */
var swReg = null, updateReady = false, userAsked = false, reloading = false;
function showUpdate() { updateReady = true; $('#update').hidden = false; if (cur === 'reglages') refreshReglages(); }
function watchWorker(reg) {
  swReg = reg;
  if (reg.waiting && navigator.serviceWorker.controller) showUpdate();
  reg.addEventListener('updatefound', function () {
    var w = reg.installing; if (!w) return;
    w.addEventListener('statechange', function () { if (w.state === 'installed' && navigator.serviceWorker.controller) showUpdate(); });
  });
}
function startWorker() {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('sw.js', { updateViaCache: 'none' }).then(function (reg) {
    watchWorker(reg); reg.update().catch(function () {});
  }).catch(function () {});
  navigator.serviceWorker.addEventListener('controllerchange', function () {
    if (userAsked && !reloading) { reloading = true; location.reload(); }   /* seulement après « Mettre à jour » */
  });
}
function applyUpdate() {
  if (!(swReg && swReg.waiting)) return;
  userAsked = true; swReg.waiting.postMessage({ type: 'SKIP_WAITING' });
}
function checkUpdate() {
  if (!swReg) { toast('Mise à jour impossible ici'); return; }
  swReg.update().then(function () {
    if (updateReady) return;
    if (swReg.installing || swReg.waiting) toast('Nouvelle version trouvée, préparation…', 4000);   /* le message « Nouvelle version disponible » suit */
    else toast('Cette version est la plus récente');
  }, function () { toast('Pas de connexion : réessaie plus tard'); });
}

/* ========= œil et masquage automatique (par comparaison d'heure, pas par minuterie) ========= */
function setInert(on) {
  ['#views', '#toast', '#update', '.nav'].forEach(function (s) {
    var e = $(s); if (!e) return; e.inert = on;
    if (on) e.setAttribute('aria-hidden', 'true'); else e.removeAttribute('aria-hidden');
  });
}
function mask() {
  if (veilOn) return;
  clearTimeout(toastTimer); toastEl.hidden = true;                    /* un message ne doit rien montrer sous l'écran neutre */
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
  veilEl.innerHTML = '<span class="vword">Agenda</span>';
  veilEl.setAttribute('role', 'button'); veilEl.setAttribute('tabindex', '0'); veilEl.setAttribute('aria-label', 'Agenda masqué. Toucher pour rouvrir');
  veilOn = true; veilEl.classList.add('on'); setInert(true);
}
function unmask() { veilOn = false; veilEl.classList.remove('on'); veilEl.innerHTML = ''; setInert(false); lastTouch = Date.now(); }
function tick() {
  if (veilOn) return;
  var now = Date.now();
  if (now < lastTouch - 2000) { mask(); return; }                      /* l'horloge a reculé : par prudence on masque */
  if (idleSec > 0 && now - lastTouch >= idleSec * 1000) mask();
}
setInterval(tick, 1000);
function onAct(e) {   /* chaque toucher, défilement ou frappe : on vérifie l'heure d'abord, puis on remet le compteur à zéro */
  if (e.type === 'pointerdown') swallowClick = false;
  var was = veilOn; tick();
  if (!was && veilOn) {          /* le délai était dépassé : le geste ne doit rien faire dessous */
    if (e.type === 'pointerdown') swallowClick = true;
    if (e.type === 'pointerdown' || e.type === 'keydown' || e.type === 'click') { e.stopPropagation(); if (e.cancelable && e.type === 'keydown') e.preventDefault(); }
    return;
  }
  lastTouch = Date.now();
}
['pointerdown', 'click', 'input', 'wheel', 'touchmove', 'pointermove', 'scroll'].forEach(function (t) { document.addEventListener(t, onAct, { capture: true, passive: true }); });
document.addEventListener('keydown', onAct, { capture: true });
veilEl.addEventListener('click', function () { if (swallowClick) { swallowClick = false; return; } tick(); if (veilOn) unmask(); });
veilEl.addEventListener('keydown', function (e) { if (veilOn && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); tick(); if (veilOn) unmask(); } });
function bgMask() { if (!veilOn) mask(); }                           /* appli en arrière-plan : écran neutre tout de suite */
document.addEventListener('visibilitychange', function () {
  if (document.hidden) bgMask(); else { tick(); if (swReg) swReg.update().catch(function () {}); }
});
window.addEventListener('pagehide', bgMask);
window.addEventListener('pageshow', tick);
window.addEventListener('focus', tick);

/* ========= actions ========= */
document.addEventListener('click', function (e) {
  var b = e.target.closest('[data-a]'); if (!b) return;
  switch (b.dataset.a) {
    case 'tab': go(b.dataset.t); break;
    case 'reglages': history.pushState({ app: 1 }, ''); go('reglages'); break;
    case 'back': go('bilan'); break;
    case 'hide': mask(); break;
    case 'idle': setIdle(+b.dataset.n); break;
    case 'persist': askPersist().then(refreshPersist); break;
    case 'checkupdate': checkUpdate(); break;
    case 'applyupdate': applyUpdate(); break;
  }
});

/* touche Retour d'Android : revient en arrière dans l'appli */
try {
  history.replaceState({ app: 1 }, ''); history.pushState({ app: 1 }, '');
  window.addEventListener('popstate', function () {
    if (veilOn) { history.pushState({ app: 1 }, ''); return; }
    if (cur === 'reglages') { go('bilan'); history.pushState({ app: 1 }, ''); }
    else if (tab !== 'aujourdhui') { go('aujourdhui'); history.pushState({ app: 1 }, ''); }
  });
} catch (e) { /* sans historique : rien à faire */ }

/* ========= erreurs graves : on explique, on n'efface jamais rien ========= */
function fatal(title, text) {
  $('#fatal-title').textContent = title; $('#fatal-text').textContent = text; $('#fatal').classList.add('on');
}

/* ========= démarrage ========= */
var ready = openDatabase(DB_NAME, MIGRATIONS).then(function (d) {
  db = d;
  return dbGet(db, 'meta', 'schema_version').then(function (v) { schemaVersion = v; });
}).then(function () {
  return dbGet(db, 'settings', 'idle_sec');
}).then(function (n) {
  if (typeof n === 'number') idleSec = n;
  return firstLaunchStorage();
}).then(function () { refreshReglages(); }, function (er) {
  if (er && er.code === 'newer') fatal('Données plus récentes que l’appli', 'Les données de ce téléphone ont été écrites par une version plus récente d’Agenda. Rien n’a été effacé. Ferme l’appli, rouvre-la avec internet pour la mettre à jour, puis réessaie.');
  else fatal('Stockage indisponible', 'Agenda ne peut pas ouvrir son stockage sur ce téléphone. Rien n’a été effacé. Ferme et rouvre l’appli ; si le message revient, ne saisis rien et préviens celui qui t’aide.');
});

go('aujourdhui');
startWorker();

/* lecture seule, pour les contrôles automatiques */
window.__ag = {
  get cur() { return cur; }, get tab() { return tab; }, get masked() { return veilOn; }, get idle() { return idleSec; },
  get ready() { return ready; }, get updateReady() { return updateReady; },
  version: APP_VERSION, dbName: DB_NAME, openDatabase: openDatabase, dbGet: dbGet, dbPut: dbPut,
  schemaTarget: latest(MIGRATIONS)
};
})();
