self.AG_STAMPS=self.AG_STAMPS||{};self.AG_STAMPS['rides.js']='0.5.2'; /* numéro écrit par verifications/sync_version.py : ne pas modifier à la main */
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
    price: r.price_cents, km: r.km_m, upr: r.usual_price_cents, ukm: r.usual_km_m, status: r.status, changed: !!r.changed, added: !!r.added, skip: !!r.skip };
};
AGR.virtItem = function (p, is) {    /* carte prévue calculée : rien n'est enregistré */
  var up = p.usual_price_cents == null ? null : p.usual_price_cents, uk = p.usual_km_m == null ? null : p.usual_km_m;
  return { key: 'v|' + p.id, virt: true, date: is, p: p, r: null, pid: p.id, time: AGR.timeFor(p), dest: { place: p.dest_place || '', street: p.dest_street || '', zip: p.dest_zip || '', city: p.dest_city || '' },
    price: up, km: uk, upr: up, ukm: uk, status: null, changed: false, added: false, skip: false };
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

self.AGR = AGR;
})();
