/* Agenda : la couche d'accès aux données. TOUT ce qui lit ou écrit dans IndexedDB passe par ici (un seul endroit).
   IndexedDB = la base de données intégrée à Chrome. Aucune donnée dans ce fichier : seulement la façon de les ranger.

   Règles de données (plan, section 3) :
   - identifiant unique aléatoire par personne et par course ;
   - montants en CENTIMES (entiers), distances en MÈTRES (entiers), dates « AAAA-MM-JJ », heures « HH:MM » ;
   - « inconnu » = null (jamais 0) ;
   - archiver plutôt que supprimer : seule une personne « vide » (aucune course notée) peut être effacée pour de bon. */
(function () {
'use strict';

var DB_NAME = 'agenda';

/* Numéro de structure = numéro de la dernière entrée. On n'ajoute QUE de nouvelles entrées à la fin ;
   on ne modifie jamais une entrée déjà publiée ; une migration n'efface rien. */
var MIGRATIONS = [
  { version: 1, up: function (db, tx) {
    db.createObjectStore('meta', { keyPath: 'key' });       /* informations techniques (numéro de structure, premier lancement…) */
    db.createObjectStore('settings', { keyPath: 'key' });   /* réglages (durée avant masquage…) */
    tx.objectStore('meta').put({ key: 'created_at', value: new Date().toISOString() });
  } },
  { version: 2, up: function (db, tx) {
    db.createObjectStore('persons', { keyPath: 'id' });     /* une fiche par personne (actives et archivées) */
    var rides = db.createObjectStore('rides', { keyPath: 'id' });   /* les courses : vide pour l'instant, utilisé à l'étape 3 */
    rides.createIndex('person_id', 'person_id', { unique: false });
  } },
  { version: 3, up: function (db, tx) {
    /* courses : on ajoute l'index par date (les personnes, les réglages et les courses déjà là ne bougent pas) */
    tx.objectStore('rides').createIndex('date', 'date', { unique: false });
  } }
];
function latest(migrations) { return migrations[migrations.length - 1].version; }

/* Ouvre (et met à niveau si besoin) une base. `migrations` est paramétrable pour pouvoir essayer le mécanisme sur une base jetable. */
function openDatabase(name, migrations, hooks) {
  return new Promise(function (resolve, reject) {
    var target = latest(migrations), req;
    try { req = indexedDB.open(name, target); } catch (e) { reject({ code: 'error', error: e }); return; }
    req.onupgradeneeded = function (ev) {
      var db = req.result, tx = req.transaction, from = ev.oldVersion;
      migrations.forEach(function (m) { if (m.version > from && m.version <= target) m.up(db, tx); });
      tx.objectStore('meta').put({ key: 'schema_version', value: target });
      tx.objectStore('meta').put({ key: 'last_upgrade', value: { from: from, to: target, at: new Date(Date.now()).toISOString() } });   /* pour le journal de mise à jour */
    };
    req.onsuccess = function () { resolve(req.result); };
    req.onerror = function () { var er = req.error; reject({ code: er && er.name === 'VersionError' ? 'newer' : 'error', error: er }); };
    /* « bloqué » : une autre page (ancienne version) garde sa connexion ouverte. L'ouverture reste en attente et se termine toute seule
       dès que cette connexion se ferme ; en attendant, la page prévient (hooks.onBlocked) au lieu de rester muette. */
    req.onblocked = function () { if (hooks && hooks.onBlocked) hooks.onBlocked(); };
  });
}

var db = null, onClosed = null;
function init(hooks) {
  return openDatabase(DB_NAME, MIGRATIONS, hooks).then(function (d) {
    db = d;
    /* une autre page demande une nouvelle structure : on lâche NOTRE connexion tout de suite, sinon elle bloquerait la mise à niveau */
    d.onversionchange = function () {
      try { appendLogOn(d, [{ t: new Date(Date.now()).toISOString(), e: 'Base fermée : une autre page demande une nouvelle structure', v: self.APP_VERSION }]); } catch (e) { /* le journal ne doit jamais gêner */ }
      d.close(); db = null; if (onClosed) onClosed();     /* close() attend la fin de l'écriture en cours */
    };
    return d;
  });
}

/* Referme la connexion (avant un rechargement voulu, pour ne jamais bloquer la page suivante). */
function closeDb() { if (db) { db.close(); db = null; } }

/* ----- petits outils sur une base ouverte ----- */
function dbGet(d, store, key) {
  return new Promise(function (resolve, reject) {
    var r = d.transaction(store).objectStore(store).get(key);
    r.onsuccess = function () { resolve(r.result ? r.result.value : undefined); };
    r.onerror = function () { reject(r.error); };
  });
}
function dbPut(d, store, key, value) {
  return new Promise(function (resolve, reject) {
    var tx = d.transaction(store, 'readwrite');
    tx.objectStore(store).put({ key: key, value: value });
    tx.oncomplete = function () { resolve(); };
    tx.onerror = function () { reject(tx.error); };
  });
}
function req2p(r) { return new Promise(function (resolve, reject) { r.onsuccess = function () { resolve(r.result); }; r.onerror = function () { reject(r.error); }; }); }
function done(tx) { return new Promise(function (resolve, reject) { tx.oncomplete = function () { resolve(); }; tx.onerror = tx.onabort = function () { reject(tx.error); }; }); }

/* ----- identifiants ----- */
function uuid() {
  if (self.crypto && self.crypto.randomUUID) return self.crypto.randomUUID();
  var b = new Uint8Array(16); self.crypto.getRandomValues(b);
  b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
  var h = Array.prototype.map.call(b, function (x) { return (x + 256).toString(16).slice(1); }).join('');
  return h.slice(0, 8) + '-' + h.slice(8, 12) + '-' + h.slice(12, 16) + '-' + h.slice(16, 20) + '-' + h.slice(20);
}

/* ----- réglages et infos techniques ----- */
function getMeta(key) { return dbGet(db, 'meta', key); }
function putMeta(key, value) { return dbPut(db, 'meta', key, value); }
function getSetting(key) { return dbGet(db, 'settings', key); }
function putSetting(key, value) { return dbPut(db, 'settings', key, value); }

/* ----- personnes ----- */
function allPersons() { return req2p(db.transaction('persons').objectStore('persons').getAll()); }
function putPerson(p) {
  var tx = db.transaction('persons', 'readwrite'); tx.objectStore('persons').put(p); return done(tx);
}
/* ----- courses -----
   Une course n'est JAMAIS effacée pour de bon : « supprimer » = la mettre à la corbeille (champ deleted_at). */
function ridesOf(personId) { return req2p(db.transaction('rides').objectStore('rides').index('person_id').getAll(personId)); }
function allRides() { return req2p(db.transaction('rides').objectStore('rides').getAll()); }
/* Les courses d'une période, lues par l'INDEX des dates (on ne relit pas tout). */
var lastRange = 0;
function ridesInRange(from, to) {
  return req2p(db.transaction('rides').objectStore('rides').index('date').getAll(IDBKeyRange.bound(from, to))).then(function (list) { lastRange = list.length; return list; });
}
function putRide(r) { var tx = db.transaction('rides', 'readwrite'); tx.objectStore('rides').put(r); return done(tx); }
/* courses non supprimées d'une personne (faites, pas faites, ou créées mais pas notées) : elles empêchent de supprimer la fiche */
function countRides(personId) {
  return ridesOf(personId).then(function (list) {
    return { noted: list.filter(function (r) { return !r.deleted_at; }).length, planned: 0 };
  });
}
/* Efface une personne pour de bon, SEULEMENT s'il n'existe aucune course non supprimée.
   Les courses déjà à la corbeille ne sont pas touchées. Renvoie la fiche effacée (pour « Annuler » pendant quelques secondes),
   ou { refused: n } s'il y a des courses. */
function deletePerson(id) {
  return new Promise(function (resolve, reject) {
    var tx = db.transaction(['persons', 'rides'], 'readwrite'), ps = tx.objectStore('persons'), rs = tx.objectStore('rides'), out = { person: null, rides: [] }, refused = 0;
    ps.get(id).onsuccess = function (e) {
      out.person = e.target.result || null;
      rs.index('person_id').getAll(id).onsuccess = function (e2) {
        var list = e2.target.result || [];
        refused = list.filter(function (r) { return !r.deleted_at; }).length;
        if (refused) { tx.abort(); return; }
        ps.delete(id);
      };
    };
    tx.oncomplete = function () { resolve(out); };
    tx.onabort = function () { if (refused) resolve({ refused: refused }); else reject(tx.error); };
    tx.onerror = function () { /* l'abandon volontaire passe par onabort */ };
  });
}
/* Annuler une suppression de fiche : on remet exactement ce qui a été effacé. */
function restoreDeleted(out) {
  var tx = db.transaction(['persons', 'rides'], 'readwrite');
  if (out.person) tx.objectStore('persons').put(out.person);
  out.rides.forEach(function (r) { tx.objectStore('rides').put(r); });
  return done(tx);
}

/* ----- journal de mise à jour : les 20 derniers évènements, gardés dans la base ----- */
var LOG_MAX = 20;
function getLog() { return getMeta('update_log').then(function (v) { return v || []; }); }
function appendLog(entries) { return appendLogOn(db, entries); }
function appendLogOn(d, entries) {
  return new Promise(function (resolve, reject) {
    var tx = d.transaction('meta', 'readwrite'), st = tx.objectStore('meta');
    st.get('update_log').onsuccess = function (e) {
      var arr = (e.target.result && e.target.result.value) || [];
      arr = arr.concat(entries).slice(-LOG_MAX);
      st.put({ key: 'update_log', value: arr });
    };
    tx.oncomplete = function () { resolve(); };
    tx.onerror = tx.onabort = function () { reject(tx.error); };
  });
}

self.AG = {
  DB_NAME: DB_NAME, MIGRATIONS: MIGRATIONS, latest: latest, openDatabase: openDatabase, init: init, closeDb: closeDb,
  dbGet: dbGet, dbPut: dbPut, getMeta: getMeta, putMeta: putMeta, getSetting: getSetting, putSetting: putSetting,
  uuid: uuid, allPersons: allPersons, putPerson: putPerson, allRides: allRides, ridesInRange: ridesInRange, get lastRangeCount() { return lastRange; }, putRide: putRide, getLog: getLog, appendLog: appendLog, LOG_MAX: LOG_MAX, countRides: countRides, deletePerson: deletePerson, restoreDeleted: restoreDeleted,
  get db() { return db; }, set onClosed(f) { onClosed = f; }, get schemaTarget() { return latest(MIGRATIONS); }
};
})();
