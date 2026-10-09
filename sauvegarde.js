self.AG_STAMPS=self.AG_STAMPS||{};self.AG_STAMPS['sauvegarde.js']='0.6.1'; /* numéro écrit par verifications/sync_version.py : ne pas modifier à la main */
/* Agenda : sauvegarde chiffrée (export, vérification, lecture pour la restauration). Aucune donnée dans ce fichier, aucun accès à la base : seulement
   WebCrypto (intégré à Chrome), la liste de mots (mots.js) et le format du fichier. Tout fonctionne hors connexion.

   Schéma (expliqué en phrases simples dans NOTES_AGENDA.md) :
   - le téléphone garde une CLÉ DE DONNÉES (AES-256-GCM, 32 octets au hasard) sous forme de clé WebCrypto NON extractible : le code ne peut plus la relire ;
   - la PHRASE de 10 mots (jamais gardée) sert à fabriquer une clé d'enveloppe (PBKDF2-SHA256, 600 000 tours, sel au hasard) qui chiffre la clé de données :
     c'est cette « clé enveloppée » qui est gardée sur le téléphone ET recopiée dans chaque fichier ;
   - chaque export chiffre le contenu avec la clé de données (AES-GCM, nouveau vecteur d'initialisation à chaque fois) : aucune phrase à retaper ;
   - pour restaurer n'importe où : phrase -> clé d'enveloppe -> clé de données -> contenu.
   Format du fichier .agenda : un texte JSON (voir NOTES_AGENDA.md), nombres en base 64. */
(function () {
'use strict';

var FORMAT = 'agenda-export', FORMAT_VERSION = 1, ITER = 600000, PHRASE_WORDS = 10;
var enc = new TextEncoder(), dec = new TextDecoder('utf-8', { fatal: true });
var WORDS = self.AG_WORDS || [];

/* ----- base 64 ----- */
function b64(bytes) {
  var s = '', u = new Uint8Array(bytes);
  for (var i = 0; i < u.length; i += 8192) s += String.fromCharCode.apply(null, u.subarray(i, i + 8192));
  return btoa(s);
}
function unb64(t) {
  if (typeof t !== 'string' || t.length % 4 || !/^[A-Za-z0-9+/]*={0,2}$/.test(t)) throw bad('damaged');
  var s = atob(t), u = new Uint8Array(s.length);
  for (var i = 0; i < s.length; i++) u[i] = s.charCodeAt(i);
  return u;
}
function hex(buf) { return Array.prototype.map.call(new Uint8Array(buf), function (x) { return (x + 256).toString(16).slice(1); }).join(''); }
function sha256Hex(text) { return crypto.subtle.digest('SHA-256', enc.encode(text)).then(hex); }
function bad(code, extra) { var e = new Error(code); e.code = code; if (extra) e.extra = extra; return e; }

/* ----- phrase de récupération ----- */
/* 2048 mots = 11 bits : on prend 16 bits au hasard et on garde les 11 derniers. 65536 est un multiple de 2048, donc chaque mot a EXACTEMENT la même chance (aucun biais). */
function drawIndex(u16) { return u16 & 2047; }
function drawPhrase() {
  var a = new Uint16Array(PHRASE_WORDS); crypto.getRandomValues(a);
  return Array.prototype.map.call(a, function (u) { return WORDS[drawIndex(u)]; });
}
/* tolérant : majuscules, accents, espaces en trop ne comptent pas */
function normWord(w) { return String(w || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim(); }
function normPhrase(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().split(/\s+/).filter(Boolean).join(' '); }
function phraseOk(s) { return normPhrase(s).split(' ').length === PHRASE_WORDS; }

/* ----- clés ----- */
function deriveKek(phrase, salt, iterations) {
  return crypto.subtle.importKey('raw', enc.encode(normPhrase(phrase)), 'PBKDF2', false, ['deriveKey']).then(function (base) {
    return crypto.subtle.deriveKey({ name: 'PBKDF2', hash: 'SHA-256', salt: salt, iterations: iterations }, base, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
  });
}
var KEY_AAD = enc.encode('agenda-key|1');
function rnd(n) { var a = new Uint8Array(n); crypto.getRandomValues(a); return a; }
/* Fabrique le « trousseau » du téléphone à partir de la phrase : { key (non extractible), kdf, wrapped, created_at }. Rien n'est enregistré ici. */
function createKeyBundle(phrase) {
  var salt = rnd(16), iv = rnd(12), raw = rnd(32);
  return deriveKek(phrase, salt, ITER).then(function (kek) {
    return crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv, additionalData: KEY_AAD }, kek, raw);
  }).then(function (ct) {
    return crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['encrypt', 'decrypt']).then(function (key) {
      raw.fill(0);
      return { key: key, kdf: { name: 'PBKDF2-SHA256', iterations: ITER, salt: b64(salt) }, wrapped: { iv: b64(iv), ct: b64(ct) }, created_at: new Date(Date.now()).toISOString() };
    });
  });
}
/* Ouvre la clé enveloppée d'un fichier avec la phrase : renvoie la clé de données (non extractible) ou refuse (mauvaise phrase). */
function unwrapKey(phrase, hdr) {
  var k = hdr.kdf, w = hdr.wrapped_key;
  if (!k || k.name !== 'PBKDF2-SHA256' || !(k.iterations >= 100000 && k.iterations <= 5000000) || !w) throw bad('damaged');
  var salt = unb64(k.salt), iv = unb64(w.iv), ct = unb64(w.ct);
  if (salt.length !== 16 || iv.length !== 12 || ct.length !== 48) throw bad('damaged');
  return deriveKek(phrase, salt, k.iterations).then(function (kek) {
    return crypto.subtle.decrypt({ name: 'AES-GCM', iv: iv, additionalData: KEY_AAD }, kek, ct).then(function (raw) {
      return crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['encrypt', 'decrypt']);
    }, function () { throw bad('phrase'); });
  });
}

/* ----- le fichier ----- */
function aad(schema, at) { return enc.encode(FORMAT + '|' + FORMAT_VERSION + '|' + schema + '|' + at); }
function two(n) { return (n < 10 ? '0' : '') + n; }
function fileName(d) { return 'agenda-' + d.getFullYear() + '-' + two(d.getMonth() + 1) + '-' + two(d.getDate()) + '-' + two(d.getHours()) + two(d.getMinutes()) + '.agenda'; }
function countsOf(data) { return { persons: data.persons.length, rides: data.rides.length, fuel: (data.fuel || []).length }; }

/* Construit le texte du fichier. bundle = trousseau du téléphone ; data = { persons, rides, fuel, settings } ; opts.schema / opts.appVersion pour les essais. */
function buildFile(bundle, data, schema, appVersion, now) {
  var at = now.toISOString(), full = Object.assign({ schema: schema }, data), json = JSON.stringify(full), iv = rnd(12);
  return sha256Hex(json).then(function (h) {
    var plain = JSON.stringify({ counts: countsOf(full), sha256: h, data: json });
    return crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv, additionalData: aad(schema, at) }, bundle.key, enc.encode(plain));
  }).then(function (ct) {
    return JSON.stringify({
      format: FORMAT, format_version: FORMAT_VERSION, app_version: appVersion, schema: schema, exported_at: at,
      kdf: bundle.kdf, wrapped_key: bundle.wrapped, cipher: 'AES-256-GCM', iv: b64(iv), ct: b64(ct)
    });
  });
}

/* Lit l'en-tête (sans phrase) : refuse ce qui n'est pas un fichier Agenda, ou d'un format / d'une structure plus récents que l'appli. */
function parseHeader(text, appSchema) {
  var h;
  try { h = JSON.parse(text); } catch (e) { throw bad('damaged'); }
  if (!h || typeof h !== 'object' || h.format !== FORMAT) throw bad('notbackup');
  if (!(h.format_version >= 1) || !(h.schema >= 1) || typeof h.exported_at !== 'string' || isNaN(Date.parse(h.exported_at))) throw bad('damaged');
  if (h.format_version > FORMAT_VERSION) throw bad('newformat');
  if (h.schema > appSchema) throw bad('newschema', h.schema);
  if (h.cipher !== 'AES-256-GCM' || typeof h.iv !== 'string' || typeof h.ct !== 'string') throw bad('damaged');
  return h;
}

/* Ouvre un fichier avec la phrase : renvoie { header, counts, data (objet), key (clé de données non extractible, pour la reprendre après une restauration) }.
   Erreurs (code) : damaged, notbackup, newformat, newschema, phrase (mauvaise phrase), words (pas 10 mots). */
function openFile(text, phrase, appSchema) {
  var h = parseHeader(text, appSchema);
  if (!phraseOk(phrase)) return Promise.reject(bad('words'));
  var dk;
  return unwrapKey(phrase, h).then(function (key) {
    dk = key;
    var iv = unb64(h.iv), ct = unb64(h.ct);
    if (iv.length !== 12 || ct.length < 16) throw bad('damaged');
    return crypto.subtle.decrypt({ name: 'AES-GCM', iv: iv, additionalData: aad(h.schema, h.exported_at) }, key, ct).then(function (p) { return p; }, function () { throw bad('damaged'); });
  }).then(function (plain) {
    var p, data;
    try { p = JSON.parse(dec.decode(plain)); data = JSON.parse(p.data); } catch (e) { throw bad('damaged'); }
    return sha256Hex(p.data).then(function (hh) {
      if (hh !== p.sha256) throw bad('damaged');
      if (!data || !Array.isArray(data.persons) || !Array.isArray(data.rides) || !(data.fuel === undefined || Array.isArray(data.fuel)) || data.schema !== h.schema) throw bad('damaged');
      if (data.fuel === undefined) data.fuel = [];                 /* fichier d'avant les pleins d'essence (structure 3) */
      var c = countsOf(data);
      if (!p.counts || p.counts.persons !== c.persons || p.counts.rides !== c.rides || p.counts.fuel !== c.fuel) throw bad('damaged');
      return { header: h, counts: c, data: data, key: dk, kdf: h.kdf, wrapped: h.wrapped_key };
    });
  });
}

/* Remet des données d'une structure plus ancienne à la structure actuelle. Une étape par numéro ; aucune n'efface quoi que ce soit. */
function migrateData(data, appSchema) {
  var d = Object.assign({}, data), s = d.schema;
  if (s < 4) { d.fuel = d.fuel || []; s = 4; }                      /* 3 -> 4 : pleins d'essence (aucun avant) */
  if (s < 5) { s = 5; }                                             /* 4 -> 5 : copie de sécurité et trousseau (ne concernent pas les données exportées) */
  d.schema = appSchema;
  d.settings = d.settings || [];
  return d;
}

self.AGB = {
  FORMAT: FORMAT, FORMAT_VERSION: FORMAT_VERSION, ITER: ITER, PHRASE_WORDS: PHRASE_WORDS, get WORDS() { return WORDS; },
  drawIndex: drawIndex, drawPhrase: drawPhrase, normWord: normWord, normPhrase: normPhrase, phraseOk: phraseOk,
  createKeyBundle: createKeyBundle, buildFile: buildFile, parseHeader: parseHeader, openFile: openFile, migrateData: migrateData,
  fileName: fileName, countsOf: countsOf, b64: b64, unb64: unb64
};
})();
