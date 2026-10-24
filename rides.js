self.AG_STAMPS=self.AG_STAMPS||{};self.AG_STAMPS['rides.js']='0.8.1'; /* numéro écrit par verifications/sync_version.py : ne pas modifier à la main */
/* Agenda : la logique des courses (sans écran, sans stockage). Aucune donnée dans ce fichier.
   Règles (plan, section 3) :
   - une « carte prévue » est CALCULÉE à partir des fiches (mode « Chaque semaine » avec « Du » / « Au », ou « Dates choisies ») ; elle n'est pas enregistrée ;
   - une course n'est CRÉÉE qu'à la première action de Pascal (fait, pas fait, changer, corriger prix ou km, ajouter) ;
   - à la création, le prix, les km, l'heure et la destination sont COPIÉS de la fiche : changer la fiche plus tard ne réécrit jamais une course ;
   - une course supprimée va à la « corbeille » (champ deleted_at) : elle n'est jamais effacée pour de bon ;
   - dates en texte « AAAA-MM-JJ » (jamais des moments précis) : le changement d'heure ne décale aucun jour. */
(function () {
'use strict';

function pad(n) { return (n < 10 ? '0' : '') + n; }
function iso(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
function parseISO(s) { var a = s.split('-'); return new Date(+a[0], +a[1] - 1, +a[2]); }
function wd(d) { return d.getDay() || 7; }      /* 1 = lundi … 7 = dimanche */
function norm(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
function nowIso() { return new Date(Date.now()).toISOString(); }

var AGR = {};

/* heure habituelle d'une personne : celle du mode choisi */
AGR.timeFor = function (p) { var s = p.schedule || {}; return (s.mode === 'dates' ? s.time_dates : s.time_weekly) || null; };

/* la personne est-elle prévue ce jour-là ? (personne archivée : jamais) */
AGR.isScheduled = function (p, is) {
  if (!p || p.archived) return false;
  var s = p.schedule || {};
  if (s.mode === 'dates') return (s.dates || []).indexOf(is) >= 0;
  return (s.weekdays || []).indexOf(wd(parseISO(is))) >= 0 && (!s.from || is >= s.from) && (!s.to || is <= s.to);
};

AGR.destOf = function (p) { return { place: p.dest_place || '', street: p.dest_street || '', zip: p.dest_zip || '', city: p.dest_city || '' }; };
AGR.pickOf = function (p) { return { street: p.pickup_street || '', zip: p.pickup_zip || '', city: p.pickup_city || '' }; };

/* Crée (en mémoire) la course d'une personne pour un jour : valeurs de la fiche COPIÉES, repère « habituel » gardé par usual_*. */
AGR.newRide = function (p, is, o) {
  o = o || {};
  var d = o.dest || AGR.destOf(p), t = nowIso();
  return {
    id: self.AG.uuid(), person_id: p.id, date: is,
    time: o.time !== undefined ? o.time : AGR.timeFor(p),
    dest_place: d.place || '', dest_street: d.street || '', dest_zip: d.zip || '', dest_city: d.city || '',
    price_cents: p.usual_price_cents == null ? null : p.usual_price_cents, km_m: p.usual_km_m == null ? null : p.usual_km_m,
    usual_price_cents: p.usual_price_cents == null ? null : p.usual_price_cents, usual_km_m: p.usual_km_m == null ? null : p.usual_km_m,
    status: null,            /* null = pas noté ; 'done' = fait ; 'not_done' = pas fait */
    changed: !!o.changed,    /* heure ou destination changée pour CE jour */
    added: !!o.added,        /* course exceptionnelle (jour non prévu) */
    skip: false,             /* « Pas de course » */
    retour: true,            /* false = le retour n'est pas fait (la personne revient avec quelqu'un d'autre) : prix et km divisés par 2 */
    created_at: t, updated_at: t, deleted_at: null
  };
};

AGR.live = function (rides) { return rides.filter(function (r) { return !r.deleted_at; }); };
AGR.rideOf = function (rides, pid, is) {   /* la course (non supprimée) d'une personne ce jour-là */
  for (var i = 0; i < rides.length; i++) { var r = rides[i]; if (!r.deleted_at && r.person_id === pid && r.date === is) return r; }
  return null;
};
function byId(people) { var m = {}; people.forEach(function (p) { m[p.id] = p; }); return m; }

AGR.rideItem = function (p, r, is) {
  return { key: r.id, virt: false, date: is, p: p, r: r, pid: p.id, time: r.time || null, dest: { place: r.dest_place, street: r.dest_street, zip: r.dest_zip, city: r.dest_city },
    price: r.price_cents, km: r.km_m, upr: r.usual_price_cents, ukm: r.usual_km_m, status: r.status, changed: !!r.changed, added: !!r.added, skip: !!r.skip, retour: r.retour !== false };
};
AGR.virtItem = function (p, is) {    /* carte prévue calculée : rien n'est enregistré */
  var up = p.usual_price_cents == null ? null : p.usual_price_cents, uk = p.usual_km_m == null ? null : p.usual_km_m;
  return { key: 'v|' + p.id, virt: true, date: is, p: p, r: null, pid: p.id, time: AGR.timeFor(p), dest: { place: p.dest_place || '', street: p.dest_street || '', zip: p.dest_zip || '', city: p.dest_city || '' },
    price: up, km: uk, upr: up, ukm: uk, status: null, changed: false, added: false, skip: false, retour: true };
};
/* la carte d'une personne pour un jour (course enregistrée, même cachée, ou carte prévue), ou null */
AGR.itemFor = function (people, rides, pid, is) {
  var p = byId(people)[pid]; if (!p) return null;
  var r = AGR.rideOf(rides, pid, is); if (r) return AGR.rideItem(p, r, is);
  return AGR.isScheduled(p, is) ? AGR.virtItem(p, is) : null;
};

/* Les cartes d'un jour : courses enregistrées + cartes prévues calculées, triées par heure.
   - une course enregistrée l'emporte sur la carte prévue (jamais de doublon), « Pas de course » comprise ;
   - « Pas de course » sur un jour À VENIR : plus de carte ;
   - personne archivée : plus de carte prévue ; ses courses déjà notées (ou passées) restent. */
AGR.items = function (people, rides, is, todayIso) {
  var P = byId(people), out = [];
  rides.forEach(function (r) {
    if (r.deleted_at || r.date !== is) return;
    var p = P[r.person_id]; if (!p) return;
    if (r.skip && is > todayIso && r.status === 'not_done') return;
    if (p.archived && !r.status && is >= todayIso) return;
    out.push(AGR.rideItem(p, r, is));
  });
  people.forEach(function (p) {
    if (!AGR.isScheduled(p, is) || AGR.rideOf(rides, p.id, is)) return;
    out.push(AGR.virtItem(p, is));
  });
  return out.map(function (it, i) { return { it: it, i: i, k: it.time ? it.time : '99:99', n: norm(it.p.last_name + ' ' + it.p.first_name) }; })
    .sort(function (a, b) { return a.k < b.k ? -1 : (a.k > b.k ? 1 : (a.n < b.n ? -1 : (a.n > b.n ? 1 : a.i - b.i))); })
    .map(function (x) { return x.it; });
};

/* État d'un jour pour une personne (calendrier) :
   t = fait, p = pas fait, a = à faire (jour à venir ou du jour), n = pas noté (jour passé), '' = rien ce jour-là */
AGR.state = function (p, rides, is, todayIso) {
  var mine = rides.filter(function (r) { return !r.deleted_at && r.person_id === p.id && r.date === is; });
  if (mine.length) {
    if (mine.some(function (r) { return r.status === 'done'; })) return 't';
    if (mine.some(function (r) { return r.status === 'not_done'; })) return 'p';
    return is >= todayIso ? 'a' : 'n';
  }
  if (AGR.isScheduled(p, is)) return is >= todayIso ? 'a' : 'n';
  return '';
};

/* Totaux d'un mois : seulement les courses « fait » non supprimées. Une course sans prix (ou sans km) est comptée comme faite mais JAMAIS comme 0 :
   elle est comptée à part (noPrice, noKm). Les cartes prévues jamais touchées ne sont pas des courses : elles ne comptent pas ici. */
AGR.totals = function (people, rides) {
  var P = byId(people), per = {}, tot = { count: 0, cents: 0, noPrice: 0, meters: 0, noKm: 0 };
  rides.forEach(function (r) {
    if (r.deleted_at || r.status !== 'done') return;
    var p = P[r.person_id]; if (!p) return;
    var q = per[p.id] || (per[p.id] = { p: p, count: 0, cents: 0, noPrice: 0, meters: 0, noKm: 0 });
    [q, tot].forEach(function (a) {
      a.count++;
      if (r.price_cents == null) a.noPrice++; else a.cents += r.price_cents;
      if (r.km_m == null) a.noKm++; else a.meters += r.km_m;
    });
  });
  var list = Object.keys(per).map(function (k) { return per[k]; }).sort(function (a, b) {
    var x = norm(a.p.last_name + ' ' + a.p.first_name), y = norm(b.p.last_name + ' ' + b.p.first_name); return x < y ? -1 : (x > y ? 1 : 0);
  });
  return { total: tot, persons: list };
};

/* Jour par jour : les jours du mois jusqu'à aujourd'hui, pour chacun les personnes concernées (courses enregistrées + cartes prévues non touchées).
   « sans note » = un jour PASSÉ où une course était prévue (ou créée) et où rien n'a été noté. Aujourd'hui n'est pas encore passé : jamais compté.
   `rides` = les courses du mois (suffit : chaque jour ne regarde que ses propres courses). */
AGR.overview = function (people, rides, y, m, todayIso) {
  var days = [], noNote = 0, n = new Date(y, m + 1, 0).getDate();
  for (var d = 1; d <= n; d++) {
    var is = y + '-' + pad(m + 1) + '-' + pad(d); if (is > todayIso) break;
    var items = AGR.items(people, rides, is, todayIso); if (!items.length) continue;
    var noted = items.some(function (it) { return it.status === 'done' || it.status === 'not_done'; });
    if (!noted && is < todayIso) noNote++;
    days.push({ iso: is, items: items, noted: noted });
  }
  return { days: days, noNote: noNote };
};

/* ---------- Lieux (calendrier d'une personne) ----------
   Le « lieu » d'une course = nom du lieu, sinon rue, sinon ville ; la comparaison ignore majuscules, accents et espaces en trop.
   Le lieu HABITUEL = la destination de la fiche. Une course est « hors habituel » si sa destination est différente de celle de la fiche. */
function squash(s) { return norm(s).replace(/[^a-z0-9]+/g, ' ').trim(); }
AGR.placeLabel = function (d) { d = d || {}; return String(d.place || d.street || d.city || '').trim(); };
AGR.placeKey = function (d) { d = d || {}; return [d.place, d.street, d.zip, d.city].map(squash).join('|'); };
AGR.PLACE_COLORS = 6;
/* Pour une personne : { usual: {label, key}, others: [{key, label, idx, letter, color}] }.
   L'ordre (donc la lettre et la couleur) est calculé sur TOUTES ses courses non supprimées, triées par nom : stable d'un mois à l'autre. */
AGR.placeInfo = function (p, rides) {
  var uk = AGR.placeKey(AGR.destOf(p)), seen = {}, list = [];
  rides.forEach(function (r) {
    if (r.deleted_at || r.person_id !== p.id) return;
    var d = { place: r.dest_place, street: r.dest_street, zip: r.dest_zip, city: r.dest_city }, k = AGR.placeKey(d);
    if (k === uk || seen[k]) return;
    seen[k] = true; list.push({ key: k, label: AGR.placeLabel(d) });
  });
  list.sort(function (a, b) { var x = squash(a.label), y = squash(b.label); return x < y ? -1 : (x > y ? 1 : (a.key < b.key ? -1 : (a.key > b.key ? 1 : 0))); });
  list.forEach(function (o, i) { o.idx = i; o.letter = String.fromCharCode(65 + (i % 26)); o.color = i % AGR.PLACE_COLORS; });
  return { usual: { label: AGR.placeLabel(AGR.destOf(p)), key: uk }, others: list };
};
/* le lieu « hors habituel » d'une course ce jour-là, ou null (course absente, carte prévue, ou lieu habituel) */
AGR.otherPlace = function (info, ride) {
  if (!ride || ride.deleted_at) return null;
  var k = AGR.placeKey({ place: ride.dest_place, street: ride.dest_street, zip: ride.dest_zip, city: ride.dest_city });
  if (k === info.usual.key) return null;
  for (var i = 0; i < info.others.length; i++) if (info.others[i].key === k) return info.others[i];
  return null;
};

/* ----- courses composées (structure 6) -----
   Une course composée = une suite ordonnée d'arrêts + UN prix commun + les km par tronçon.
   stops : [{ kind: 'pick' | 'pass' | 'drop', person_id (si personne), place: {name, street, zip, city} }]
   Les km se notent par tronçon : km_legs[i] = distance entre l'arrêt i et l'arrêt i+1 (null = inconnu) ; le retour aux domiciles est return_km_m.
   Le prix est UNIQUE pour la course (couple lié, même trajet) : price_cents (null = inconnu). */
AGR.JOINT_KINDS = ['pick', 'pass', 'drop'];

/* Vérifie une course composée avant enregistrement. Renvoie un message clair, ou null si tout va. */
AGR.checkJoint = function (j) {
  if (!j.stops || j.stops.length < 2) return 'Une course composée a au moins deux arrêts.';
  for (var i = 0; i < j.stops.length; i++) {
    var st = j.stops[i];
    if (AGR.JOINT_KINDS.indexOf(st.kind) < 0) return 'Type d\'arrêt inconnu.';
    if (st.kind !== 'pass' && !st.person_id) return 'Une prise en charge ou une dépose doit désigner une personne.';
  }
  if (j.price_cents !== null && j.price_cents !== undefined && (!Number.isInteger(j.price_cents) || j.price_cents < 0)) return 'Prix refusé : un nombre positif, en euros.';
  if (j.price_cents === 0) return 'Un prix de 0 n\'est pas accepté : laisse vide si tu ne le connais pas.';
  return null;
};

/* Crée (en mémoire) une course composée. Les arrêts sont COPIÉS : changer une fiche plus tard ne réécrit jamais la course. */
AGR.newJoint = function (date, stops, price_cents, returnKm) {
  var t = nowIso();
  var j = {
    id: self.AG.uuid(), date: date,
    stops: stops.map(function (st, i) { return { order: i + 1, kind: st.kind, person_id: st.person_id || null, place: st.place || null }; }),
    price_cents: price_cents === undefined ? null : price_cents,
    km_legs: stops.slice(1).map(function () { return null; }),      /* un tronçon entre deux arrêts consécutifs */
    return_km_m: returnKm === undefined ? null : returnKm,
    status: null, deleted_at: null, created_at: t, updated_at: t
  };
  return j;
};

/* Totaux des courses composées faites (status « done ») : prix une fois par course, km = somme des tronçons connus + retour.
   Une course avec un km manquant compte dans « km inconnus » (total partiel), comme les autres courses. */
AGR.jointTotals = function (list) {
  var tot = { count: 0, cents: 0, noPrice: 0, meters: 0, noKm: 0 };
  (list || []).forEach(function (j) {
    if (j.deleted_at || j.status !== 'done') return;
    tot.count++;
    if (j.price_cents == null) tot.noPrice++; else tot.cents += j.price_cents;
    var legs = (j.km_legs || []).concat([j.return_km_m]), miss = false;
    legs.forEach(function (m) { if (m == null) miss = true; else tot.meters += m; });
    if (miss) tot.noKm++;
  });
  return tot;
};
AGR.addTotals = function (a, b) {
  return { count: a.count + b.count, cents: a.cents + b.cents, noPrice: a.noPrice + b.noPrice, meters: a.meters + b.meters, noKm: a.noKm + b.noKm };
};

self.AGR = AGR;
})();
