/* Agenda : écrans et comportements. Étape 2 : personnes et fiche. Aucune donnée dans ce fichier, aucune bibliothèque, aucune adresse internet.
   Les données passent par db.js (AG). Présentation, textes et règles repris de la maquette. */
(function () {
'use strict';

/* ========= petits outils ========= */
function $(s, r) { return (r || document).querySelector(s); }
function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
var APP_VERSION = self.APP_VERSION || '?';
var AG = self.AG, AGR = self.AGR;
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
function I(n, c) { return '<svg class="i ' + (c || '') + '" aria-hidden="true"><use href="#i-' + n + '"/></svg>'; }
function norm(s) { return String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
function plural(n, one, many) { return n + ' ' + (n > 1 ? many : one); }
function pad(n) { return (n < 10 ? '0' : '') + n; }
function nowDate() { return new Date(Date.now()); }
function today() { var d = nowDate(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
function iso(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
function parseISO(s) { var a = s.split('-'); return new Date(+a[0], +a[1] - 1, +a[2]); }
function wd(d) { return d.getDay() || 7; }      /* 1 = lundi … 7 = dimanche */
function todayISO() { return iso(today()); }
var fmtDay = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
var fmtMonth = new Intl.DateTimeFormat('fr-FR', { month: 'long', year: 'numeric' });
function telHref(t) { return 'tel:' + String(t).replace(/[^\d+]/g, ''); }

/* ----- nombres : virgule ET point acceptés ; vide = inconnu (jamais 0) ; 0 refusé ; prix en centimes, km en mètres ----- */
function parseDecimal(s, maxDec) {
  s = String(s || '').replace(/\s/g, ''); if (!s) return { v: null };
  if (!new RegExp('^\\d{1,6}([.,]\\d{1,' + maxDec + '})?$').test(s)) return { err: 'format' };
  var n = parseFloat(s.replace(',', '.')); if (!(n > 0)) return { err: 'zero' };
  return { v: n };
}
function fmtPrice(c) { if (c == null) return ''; var e = Math.floor(c / 100), r = c % 100; return r ? e + ',' + pad(r) : String(e); }
function fmtKm(m) { if (m == null) return ''; return (m / 1000).toFixed(3).replace(/0+$/, '').replace(/\.$/, '').replace('.', ','); }
/* heure : « 13:00 », « 1300 », « 13h », « 13h30 » → « 13:00 » ; vide = inconnue ; 25:00 refusé */
function parseTime(v) {
  v = String(v || '').trim().toLowerCase(); if (!v) return { v: null };
  var m = /^(\d{1,2})\s*[h:]\s*(\d{0,2})$/.exec(v), hh, mm;
  if (m) { hh = m[1]; mm = m[2]; }
  else {
    var d = v.replace(/\D/g, '').slice(0, 4); if (!d) return { err: true };
    if (d.length <= 2) { hh = d; mm = ''; } else if (d.length === 3) { hh = d.slice(0, 1); mm = d.slice(1); } else { hh = d.slice(0, 2); mm = d.slice(2); }
  }
  if (mm.length === 1) mm = mm + '0';
  var H = +hh, M = +(mm || 0);
  if (!(H >= 0 && H <= 23 && M >= 0 && M <= 59)) return { err: true };
  return { v: pad(H) + ':' + pad(M) };
}

/* ========= état de l'interface ========= */
var schemaVersion = null, people = [], rides = [];
var cur = 'aujourdhui', tab = 'aujourdhui';
var idleSec = 120;                       /* réglable : 0 (jamais), 60, 120, 600 */
var veilEl = $('#veil'), veilOn = false, lastTouch = Date.now(), swallowClick = false;
var toastEl = $('#toast'), toastTimer = null, undoFn = null;
var showArch = false, query = '';
var ctx = { sig: null, pid: null, person: null, mode: 'sem', jours: [], du: '', au: '', dates: {}, dm: { y: 0, m: 0 }, leaving: false, noted: 0, planned: 0, calPid: null, calY: 0, calM: 0 };
var confirmCtx = null;

function toast(text, undo, ms) {
  clearTimeout(toastTimer); undoFn = undo || null;
  toastEl.innerHTML = '<span>' + esc(text) + '</span>' + (undo ? '<button data-a="undo">Annuler</button>' : '');
  toastEl.hidden = false;
  toastTimer = setTimeout(function () { toastEl.hidden = true; undoFn = null; }, ms || (undo ? 5000 : 3000));
}
function tools() {
  return '<span class="tools"><button class="tool" data-a="hide" aria-label="Masquer l’écran">' + I('eyeoff') + '</button></span>';
}

/* ========= écrans et barre du bas ========= */
var TABS = ['aujourdhui', 'personnes', 'bilan', 'essence'];
function go(id) {
  var prev = cur;
  cur = id;
  if (TABS.indexOf(id) >= 0) tab = id; else tab = (id === 'fiche' || id === 'calendrier') ? 'personnes' : 'bilan';   /* sous-pages : l'onglet d'origine reste allumé */
  $$('.screen').forEach(function (s) { s.classList.toggle('on', s.id === 's-' + id); });
  $$('.nav button.t').forEach(function (b) {
    var on = b.dataset.t === tab; b.classList.toggle('on', on);
    if (on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  if (id === 'reglages') { refreshReglages(); refreshLog(); }
  if (id === 'personnes') renderPers();
  if (id === 'aujourdhui') { if (prev !== 'aujourdhui') openKey = null; renderAuj(); }
}

/* ========= Personnes : liste, recherche, archivées sur la même page ========= */
function activePeople() { return people.filter(function (p) { return !p.archived; }); }
function archivedPeople() { return people.filter(function (p) { return p.archived; }); }
function sortPeople(list) {
  return list.slice().sort(function (a, b) {
    var x = norm(a.last_name + ' ' + a.first_name), y = norm(b.last_name + ' ' + b.first_name);
    return x < y ? -1 : (x > y ? 1 : 0);
  });
}
function nameHTML(p) { return '<span class="nom">' + esc(p.last_name) + '</span> <span class="pre">' + esc(p.first_name) + '</span>'; }
function fullName(p) { return (p.last_name + ' ' + p.first_name).trim(); }
function renderPers() {
  var na = archivedPeople().length;
  $('#s-personnes').classList.toggle('arch', showArch);
  $('#pcount').textContent = showArch ? plural(na, 'archivée', 'archivées') : plural(activePeople().length, 'personne', 'personnes');
  if (showArch) {
    $('#plist').innerHTML = na
      ? '<div class="card" style="padding-top:2px;padding-bottom:2px">' + sortPeople(archivedPeople()).map(function (p) {
          return '<div class="list-item"><span class="name">' + nameHTML(p) + '</span><button class="btn quiet" data-a="restore" data-id="' + esc(p.id) + '">Restaurer</button></div>';
        }).join('') + '</div>'
      : '<div class="card empty">Aucune personne archivée.</div>';
    $('#archwrap').innerHTML = '<p class="note">Une personne restaurée réapparaît partout, avec son historique.</p><button class="archline" data-a="archhide">' + I('left') + 'Personnes actives</button>';
    return;
  }
  var q = norm(query.trim()), out = '';
  var list = sortPeople(activePeople().filter(function (p) { return !q || norm(p.last_name).indexOf(q) >= 0 || norm(p.first_name).indexOf(q) >= 0; }));
  function hl(s) {
    if (!q) return esc(s);
    var ns = norm(s), i = ns.indexOf(q);
    if (i < 0 || ns.length !== s.length) return esc(s);
    return esc(s.slice(0, i)) + '<mark>' + esc(s.slice(i, i + q.length)) + '</mark>' + esc(s.slice(i + q.length));
  }
  list.forEach(function (p) {
    out += '<button class="list-item" data-a="fiche" data-id="' + esc(p.id) + '"><span class="name"><span class="nom">' + hl(p.last_name) + '</span> <span class="pre">' + hl(p.first_name) + '</span></span>' + I('right') + '</button>';
  });
  var emptyMsg = activePeople().length ? 'Personne ne correspond.' : 'Aucune personne pour l’instant. Touche « Nouvelle personne ».';
  $('#plist').innerHTML = list.length ? '<div class="card" style="padding-top:2px;padding-bottom:2px">' + out + '</div>' : '<div class="card empty">' + emptyMsg + '</div>';
  $('#archwrap').innerHTML = na >= 1 ? '<button class="archline" data-a="archshow">Archivées (' + na + ')' + I('right') + '</button>' : '';
  $('#qnote').textContent = q ? plural(list.length, 'résultat', 'résultats') + ' pour « ' + query.trim() + ' »' : 'Recherche par nom et par prénom';
}

/* ========= Fiche (même page pour créer et modifier) ========= */
function personToForm(p) {
  var s = p && p.schedule || {};
  return p ? { nom: p.last_name, pre: p.first_name, rue: p.pickup_street, cp: p.pickup_zip, ville: p.pickup_city, lieu: p.dest_place, lrue: p.dest_street, lcp: p.dest_zip, lville: p.dest_city,
               tel: p.phone, prix: fmtPrice(p.usual_price_cents), km: fmtKm(p.usual_km_m), heure: s.time_weekly || '', heureD: s.time_dates || '' }
           : { nom: '', pre: '', rue: '', cp: '', ville: '', lieu: '', lrue: '', lcp: '', lville: '', tel: '', prix: '', km: '', heure: '', heureD: '' };
}
function backBar(title) {
  return '<header class="top"><div class="backrow"><button class="back" data-a="back">' + I('left') + 'Retour</button>' + tools() + '</div><h1 style="margin-top:6px">' + title + '</h1></header>';
}
function fdatesHTML() {
  var y = ctx.dm.y, m = ctx.dm.m, first = new Date(y, m, 1), off = wd(first) - 1, n = new Date(y, m + 1, 0).getDate(), L = ['L', 'M', 'M', 'J', 'V', 'S', 'D'];
  var cnt = Object.keys(ctx.dates).filter(function (k) { return ctx.dates[k]; }).length, T = todayISO();
  var h = '<div class="monthnav" style="padding:0 4px 6px"><button class="chev" data-a="fmonth" data-d="-1" aria-label="Mois précédent">' + I('left') + '</button><div class="lbl">' + esc(cap(fmtMonth.format(first))) + '</div><button class="chev" data-a="fmonth" data-d="1" aria-label="Mois suivant">' + I('right') + '</button></div><div class="calgrid">' + L.map(function (l) { return '<div class="dow">' + l + '</div>'; }).join('');
  for (var i = 0; i < off; i++) h += '<div class="blank"></div>';
  for (var d = 1; d <= n; d++) {
    var is = y + '-' + pad(m + 1) + '-' + pad(d), on = !!ctx.dates[is], past = is < T;
    h += '<button class="cell' + (on ? ' sel' : '') + (is === T ? ' today' : '') + '" data-a="fdate" data-iso="' + is + '" aria-pressed="' + on + '"' + (past ? ' disabled' : '') + ' aria-label="' + esc(cap(fmtDay.format(parseISO(is)))) + (past ? ' (passée)' : '') + '"><span>' + d + '</span></button>';
  }
  h += '</div><div class="days" style="margin-top:8px">' + L.map(function (l, i) {
    var ds = datesOfDay(i + 1), all = ds.length > 0 && ds.every(function (x) { return ctx.dates[x]; });
    return '<button data-a="fshort" data-j="' + (i + 1) + '" class="' + (all ? 'on' : '') + '" aria-pressed="' + all + '" aria-label="Chaque ' + ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'][i] + ' du mois">' + l + '</button>';
  }).join('') + '</div>' +
    '<button class="btn soft full" style="margin-top:8px" data-a="fshort" data-j="0">Lun à ven</button>' +
    '<p class="note" id="f-count" style="padding:8px 8px 0">' + plural(cnt, 'jour choisi', 'jours choisis') + '</p>';
  return h;
}
function datesOfDay(j) {   /* dates du mois affiché, à partir d'aujourd'hui, pour la lettre j (0 = lundi à vendredi) */
  var y = ctx.dm.y, m = ctx.dm.m, n = new Date(y, m + 1, 0).getDate(), out = [], T = todayISO();
  for (var d = 1; d <= n; d++) { var dt = new Date(y, m, d), is = iso(dt), w = wd(dt); if (is >= T && (j ? w === j : w <= 5)) out.push(is); }
  return out;
}
function quandHTML(d) {
  var L = ['L', 'M', 'M', 'J', 'V', 'S', 'D'], sem = ctx.mode !== 'dat';
  return '<div class="card daycard"><div class="field"><label>Quand</label><div class="seg two" role="group" aria-label="Quand">' +
    '<button data-a="fmode" data-m="sem" class="' + (sem ? 'sel' : '') + '" aria-pressed="' + sem + '">Chaque semaine</button><button data-a="fmode" data-m="dat" class="' + (sem ? '' : 'sel') + '" aria-pressed="' + (!sem) + '">Dates choisies</button></div></div>' +
    '<div class="field" id="q-sem"' + (sem ? '' : ' hidden') + ' style="margin-top:8px"><label>Jours habituels</label><div class="days">' + L.map(function (l, i) { var on = ctx.jours.indexOf(i + 1) >= 0; return '<button data-a="jour" data-j="' + (i + 1) + '" class="' + (on ? 'on' : '') + '" aria-pressed="' + on + '">' + l + '</button>'; }).join('') + '</div>' +
      '<label for="f-heure" style="margin-top:4px">Heure habituelle</label><input class="input" id="f-heure" value="' + esc(d.heure) + '" placeholder="inconnue" inputmode="numeric" autocomplete="off" maxlength="5"><div class="warnbox" id="f-h-err" role="alert" hidden></div>' +
      '<div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;margin-top:4px"><div class="field"><label for="f-du">Du</label><input class="input" id="f-du" type="date" value="' + esc(ctx.du) + '"></div><div class="field"><label for="f-au">Au (facultatif)</label><input class="input" id="f-au" type="date" value="' + esc(ctx.au) + '"></div></div>' +
      '<p class="note" style="padding:2px 8px 0">« Du » vide : depuis toujours. « Au » vide : pas de fin.</p><div class="warnbox" id="f-q-err" role="alert" hidden></div></div>' +
    '<div class="field" id="q-dat"' + (sem ? ' hidden' : '') + ' style="margin-top:8px"><label for="f-heured">Heure pour toutes les dates</label><input class="input" id="f-heured" value="' + esc(d.heureD) + '" placeholder="inconnue" inputmode="numeric" autocomplete="off" maxlength="5"><div class="warnbox" id="f-hd-err" role="alert" hidden></div>' +
      '<p class="note" style="padding:2px 8px 0">Touche les jours pour les cocher.</p><div id="f-dates">' + fdatesHTML() + '</div></div></div>';
}
function hasSchedule(p) { var s = p.schedule || {}; return (s.weekdays && s.weekdays.length > 0) || (s.dates && s.dates.length > 0); }
function gererHTML(p) {
  var n = ctx.noted, del = n > 0
    ? '<button class="list-item" disabled aria-disabled="true"><span class="name">Supprimer cette fiche<small>Impossible : ' + n + (n > 1 ? ' courses déjà notées.' : ' course déjà notée.') + '</small></span></button>'
    : '<button class="list-item" data-a="deleteask" data-id="' + esc(p.id) + '"><span class="name">Supprimer cette fiche<small>Ses jours habituels et ses courses prévues seront supprimés.</small></span></button>';
  return '<h2 style="margin-top:20px">Gérer cette fiche</h2><div class="card" style="padding-top:2px;padding-bottom:2px"><button class="list-item" data-a="archiveask" data-id="' + esc(p.id) + '"><span class="name">Archiver cette personne<small>Elle disparaît des listes, son historique reste.</small></span></button>' + del + '</div>';
}
function renderFiche() {
  var p = ctx.person, d = personToForm(p), el = $('#s-fiche'), sc = $('.content', el), st = sc ? sc.scrollTop : 0;
  var h = backBar(p ? nameHTML(p) : 'Nouvelle personne') + '<div class="content">' +
    '<div class="card"><div class="field"><label for="f-nom">Nom</label><input class="input" id="f-nom" value="' + esc(d.nom) + '" autocomplete="off" autocapitalize="words"><label for="f-pre" style="margin-top:4px">Prénom</label><input class="input" id="f-pre" value="' + esc(d.pre) + '" autocomplete="off" autocapitalize="words">' + (p ? '' : '<div class="warnbox" id="dup-warn" role="status" hidden></div>') + '</div></div>' +
    '<div class="card"><div class="field"><label for="f-rue">Prise en charge (et retour)</label><input class="input" id="f-rue" value="' + esc(d.rue) + '" placeholder="Rue et numéro" autocomplete="off"><div class="zip-city"><input class="input" id="f-cp" value="' + esc(d.cp) + '" placeholder="Code postal" inputmode="numeric" pattern="[0-9]*" maxlength="5" aria-label="Code postal" autocomplete="off"><input class="input" id="f-ville" value="' + esc(d.ville) + '" placeholder="Ville" aria-label="Ville" autocomplete="off" autocapitalize="words"></div></div></div>' +
    '<div class="card"><div class="field"><label for="f-lieu">Destination habituelle</label><input class="input" id="f-lieu" value="' + esc(d.lieu) + '" placeholder="Nom du lieu" autocomplete="off" autocapitalize="words"><input class="input" id="f-lrue" value="' + esc(d.lrue) + '" placeholder="Rue et numéro" aria-label="Rue et numéro" autocomplete="off"><div class="zip-city"><input class="input" id="f-lcp" value="' + esc(d.lcp) + '" placeholder="Code postal" inputmode="numeric" pattern="[0-9]*" maxlength="5" aria-label="Code postal" autocomplete="off"><input class="input" id="f-lville" value="' + esc(d.lville) + '" placeholder="Ville" aria-label="Ville" autocomplete="off" autocapitalize="words"></div></div></div>' +
    '<div class="card"><div class="field"><label>Prix et km habituels (facultatif)</label></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><div class="field"><label for="f-prix">Prix de la course (€)</label><input class="input" id="f-prix" value="' + esc(d.prix) + '" placeholder="inconnu" inputmode="decimal" autocomplete="off"></div><div class="field"><label for="f-km">Km de la course</label><input class="input" id="f-km" value="' + esc(d.km) + '" placeholder="inconnu" inputmode="decimal" autocomplete="off"></div></div><div class="warnbox" id="f-pk-err" role="alert" hidden></div><p class="note" style="padding:6px 0 0">Repris sur les nouvelles courses créées. Les courses déjà créées ne changent pas.</p></div>' +
    '<div class="card"><div class="field"><label for="f-tel">Téléphone (facultatif)</label><div class="call-row"><input class="input" id="f-tel" type="tel" inputmode="tel" value="' + esc(d.tel) + '" placeholder="inconnu" autocomplete="off"><a class="btn soft" id="f-call" data-a="callfiche"' + (d.tel ? ' href="' + esc(telHref(d.tel)) + '"' : '') + '>' + I('phone') + 'Appeler</a></div></div></div>' +
    quandHTML(d) +
    '<button class="btn strong full" data-a="savefiche">Enregistrer</button>' +
    (p ? '<h2>Courses de ' + esc(p.first_name || p.last_name) + '</h2><div class="card" style="padding-top:2px;padding-bottom:2px"><button class="list-item" data-a="calfiche" data-id="' + esc(p.id) + '"><span class="name">Calendrier et courses<small>voir le mois, noter une course</small></span>' + I('right') + '</button></div>' : '') +
    (p ? gererHTML(p) : '') + '</div>';
  el.innerHTML = h; var n = $('.content', el); if (n) n.scrollTop = st;
}
function openFiche(id) {
  var p = null; people.forEach(function (x) { if (x.id === id) p = x; });
  if (!p) return;
  var s = p.schedule || {};
  ctx.pid = id; ctx.person = p; ctx.jours = (s.weekdays || []).slice(); ctx.mode = s.mode === 'dates' ? 'dat' : 'sem';
  ctx.du = s.from || ''; ctx.au = s.to || ''; ctx.dates = {}; (s.dates || []).forEach(function (d) { ctx.dates[d] = true; });
  var t = today(); ctx.dm = { y: t.getFullYear(), m: t.getMonth() };
  AG.countRides(id).then(function (c) { ctx.noted = c.noted; ctx.planned = c.planned; }, function () { ctx.noted = 0; ctx.planned = 0; }).then(function () {
    history.pushState({ app: 1 }, ''); renderFiche(); ctx.sig = ficheSig(); go('fiche'); $('#s-fiche .content').scrollTop = 0;
  });
}
function openNew() {
  var t = today();
  ctx.pid = null; ctx.person = null; ctx.jours = []; ctx.mode = 'sem'; ctx.du = iso(t); ctx.au = ''; ctx.dates = {}; ctx.dm = { y: t.getFullYear(), m: t.getMonth() }; ctx.noted = 0; ctx.planned = 0;
  history.pushState({ app: 1 }, ''); renderFiche(); ctx.sig = ficheSig(); go('fiche'); $('#s-fiche .content').scrollTop = 0;
}
function readFiche() {
  var g = function (i) { return document.getElementById(i).value.trim(); };
  return { nom: g('f-nom'), pre: g('f-pre'), rue: g('f-rue'), cp: g('f-cp'), ville: g('f-ville'), lieu: g('f-lieu'), lrue: g('f-lrue'), lcp: g('f-lcp'), lville: g('f-lville'), tel: g('f-tel'), heure: g('f-heure'), heureD: g('f-heured'), du: g('f-du'), au: g('f-au'), prix: g('f-prix'), km: g('f-km') };
}
/* « Quitter sans enregistrer ? » : seulement pour une nouvelle personne dont on a déjà rempli quelque chose (comme la maquette) */
/* « signature » de la fiche : tout ce qui peut être modifié. Elle est notée à l'ouverture ; si elle a changé, on demande avant de quitter. */
function ficheSig() {
  return JSON.stringify({ v: readFiche(), mode: ctx.mode, jours: ctx.jours.slice().sort(), dates: Object.keys(ctx.dates).filter(function (d) { return ctx.dates[d]; }).sort() });
}
function ficheDirty() {
  if (cur !== 'fiche' || ctx.leaving || !document.getElementById('f-nom') || ctx.sig == null) return false;
  return ficheSig() !== ctx.sig;
}
function dupMsg() {
  var n = norm(document.getElementById('f-nom').value.trim()), r = norm(document.getElementById('f-pre').value.trim()), hit = null;
  if (n && r) people.some(function (p) { if (norm(p.last_name) === n && norm(p.first_name) === r) { hit = p; return true; } return false; });
  return hit ? ('Une fiche « ' + hit.last_name + ' ' + hit.first_name + ' » existe déjà' + (hit.archived ? ' (archivée)' : '') + '. Tu peux quand même enregistrer.') : '';
}
function back() {
  if (cur === 'calendrier') { openFiche(ctx.calPid); return; }
  if (ficheDirty()) { openConfirm('leave', null, null); return; }
  go('personnes');
}

/* ----- enregistrer ----- */
function showErr(id, msg, focusId) {
  var e = document.getElementById(id); e.textContent = msg; e.hidden = false;
  if (focusId) { var f = document.getElementById(focusId); f.setAttribute('aria-invalid', 'true'); f.focus(); }
}
function saveFiche() {
  var v = readFiche(), q0 = ctx.person;
  ['f-pk-err', 'f-h-err', 'f-hd-err', 'f-q-err'].forEach(function (i) { var e = document.getElementById(i); if (e) { e.hidden = true; e.textContent = ''; } });
  $$('#s-fiche [aria-invalid]').forEach(function (e) { e.removeAttribute('aria-invalid'); });
  if (!v.nom && q0) { toast('Indique au moins un nom'); return; }
  if (!q0 && !v.nom && !v.pre) { toast('Indique au moins un nom'); return; }
  var npx = parseDecimal(v.prix, 2), nkm = parseDecimal(v.km, 2);
  if (npx.err || nkm.err) {
    var which = npx.err ? 'Prix' : 'Km', e1 = npx.err || nkm.err;
    showErr('f-pk-err', e1 === 'zero' ? which + ' : un zéro n’est pas possible. Laisse la case vide si tu ne sais pas.' : (npx.err ? 'Prix invalide : écris un nombre comme 12,50, ou laisse vide.' : 'Km invalides : écris un nombre comme 8,5, ou laisse vide.'), npx.err ? 'f-prix' : 'f-km');
    return;
  }
  var th = parseTime(v.heure);
  if (th.err) { showErr('f-h-err', 'Heure invalide : écris par exemple 13:00, ou laisse vide.', 'f-heure'); return; }
  var td = parseTime(v.heureD);
  if (td.err) { showErr('f-hd-err', 'Heure invalide : écris par exemple 13:00, ou laisse vide.', 'f-heured'); return; }
  if (v.du && v.au && v.au < v.du) { showErr('f-q-err', 'La date de fin (« Au ») est avant la date de début (« Du ») : corrige l’une des deux.', 'f-au'); return; }
  var nowIso = nowDate().toISOString();
  var p = q0 ? Object.assign({}, q0) : { id: AG.uuid(), archived: false, created_at: nowIso };
  Object.assign(p, {
    last_name: v.nom, first_name: v.pre,
    pickup_street: v.rue, pickup_zip: v.cp, pickup_city: v.ville,
    dest_place: v.lieu, dest_street: v.lrue, dest_zip: v.lcp, dest_city: v.lville,
    phone: v.tel,
    usual_price_cents: npx.v == null ? null : Math.round(npx.v * 100),
    usual_km_m: nkm.v == null ? null : Math.round(nkm.v * 1000),
    schedule: {
      mode: ctx.mode === 'dat' ? 'dates' : 'weekly',
      weekdays: ctx.jours.slice().sort(), time_weekly: th.v, from: v.du || null, to: v.au || null,
      dates: Object.keys(ctx.dates).filter(function (k) { return ctx.dates[k]; }).sort(), time_dates: td.v
    },
    updated_at: nowIso
  });
  AG.putPerson(p).then(function () {
    if (q0) people[people.indexOf(q0)] = p; else people.push(p);
    ctx.leaving = true; go('personnes'); ctx.leaving = false;
    if (q0) toast('Fiche enregistrée');
    else toast(fullName(p) + ' ajouté', function () {
      AG.deletePerson(p.id).then(function (out) {
        if (out.refused) return;
        people = people.filter(function (x) { return x.id !== p.id; }); if (cur === 'personnes') renderPers();
      });
    });
  }, function () { toast('Enregistrement impossible : réessaie'); });
}

/* ----- confirmations ----- */
function deleteText(p) {
  var n = ctx.planned, j = hasSchedule(p);
  if (!j && !n) return 'Elle est vide, rien d’autre n’est perdu.';
  if (!n) return 'Ses jours habituels seront supprimés.';
  if (!j) return n > 1 ? ('Ses ' + n + ' courses prévues seront supprimées.') : 'Sa course prévue sera supprimée.';
  return 'Ses jours habituels et ' + (n > 1 ? ('ses ' + n + ' courses prévues') : 'sa course prévue') + ' seront supprimés.';
}
function openConfirm(kind, pid, target) {
  var p = ctx.person; if (kind !== 'leave' && !p) return;
  confirmCtx = { kind: kind, pid: pid, target: target || null };
  var lv = kind === 'leave', arch = kind === 'archive';
  $('#confirm-title').textContent = lv ? 'Quitter sans enregistrer ?' : (arch ? ('Archiver ' + fullName(p) + ' ?') : ('Supprimer ' + fullName(p) + ' ?'));
  $('#confirm-text').textContent = lv ? 'Ce que tu as saisi sera perdu.' : (arch ? 'Il ne s’affichera plus dans les listes. Son historique reste.' : deleteText(p));
  $('#confirm-ok').textContent = lv ? 'Quitter' : (arch ? 'Archiver' : 'Supprimer');
  $('#confirm-cancel').textContent = lv ? 'Rester' : 'Annuler';
  $('#confirm').classList.add('on');
}
function closeConfirm() { $('#confirm').classList.remove('on'); confirmCtx = null; }
function setArchived(p, flag) {
  var q = Object.assign({}, p, { archived: flag, archived_at: flag ? nowDate().toISOString() : null, updated_at: nowDate().toISOString() });
  return AG.putPerson(q).then(function () { people[people.indexOf(p)] = q; return q; });
}
function confirmOk() {
  var cc = confirmCtx; closeConfirm(); if (!cc) return;
  if (cc.kind === 'leave') { ctx.leaving = true; if (cc.target && cc.target.cal) openCalendar(cc.target.cal); else if (cc.target) go(cc.target); else go('personnes'); ctx.leaving = false; return; }
  var p = ctx.person; if (!p) return;
  if (cc.kind === 'archive') {
    setArchived(p, true).then(function (q) {
      go('personnes');
      toast(fullName(q) + ' archivé', function () { setArchived(q, false).then(function () { if (cur === 'personnes') renderPers(); }); });
    });
  } else {
    AG.deletePerson(p.id).then(function (out) {
      if (out.refused) { toast('Impossible : ' + plural(out.refused, 'course déjà notée', 'courses déjà notées') + '.'); return; }
      people = people.filter(function (x) { return x.id !== p.id; });
      go('personnes');
      toast(fullName(p) + ' supprimée', function () {
        AG.restoreDeleted(out).then(function () { people.push(out.person); if (cur === 'personnes') renderPers(); });
      });
    });
  }
}

/* ========= Courses : outils communs ========= */
function addDays(d, n) { return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n); }
function fmtH(t) { var m = /^(\d{2}):(\d{2})$/.exec(t || ''); if (!m) return t || ''; return (+m[1]) + 'h' + (m[2] === '00' ? '' : m[2]); }   /* 09:30 → 9h30 */
function personById(id) { for (var i = 0; i < people.length; i++) if (people[i].id === id) return people[i]; return null; }
function dayItems(is) { return AGR.items(people, rides, is, todayISO()); }
function itemFor(p, is) { return AGR.itemFor(people, rides, p.id, is); }
function findItem(key, is) {
  var l = dayItems(is);
  for (var i = 0; i < l.length; i++) if (l[i].key === key) return l[i];
  var m = /^v\|(.+)$/.exec(key || '');    /* la carte prévue est devenue une course entre-temps : on retrouve la course */
  if (m) { var p = personById(m[1]); if (p) { var r = AGR.rideOf(rides, p.id, is); if (r) return AGR.rideItem(p, r, is); } }
  return null;
}
function nowIso() { return new Date(Date.now()).toISOString(); }
/* première action sur une carte prévue : la course est CRÉÉE ici (valeurs de la fiche copiées) */
function ensureRide(it, is) {
  if (it.r) return Promise.resolve(it.r);
  var again = AGR.rideOf(rides, it.p.id, is); if (again) return Promise.resolve(again);
  var r = AGR.newRide(it.p, is); rides.push(r);
  return AG.putRide(r).then(function () { return r; }, function (e) { rides.splice(rides.indexOf(r), 1); throw e; });
}
function saveRide(r) { r.updated_at = nowIso(); return AG.putRide(r); }
function refreshUnder() { if (cur === 'aujourdhui') renderAuj(); else if (cur === 'calendrier') renderCal(); }
function hasAddr(a) { return !!(a.street || a.zip || a.city); }
function addrHTML2(a) {
  var h = esc(a.street || '');
  if (a.street && (a.zip || a.city)) h += ', ';
  if (a.zip || a.city) h += '<span class="cpv"><span class="cp">' + esc(a.zip) + '</span> <span class="ville">' + esc(a.city) + '</span></span>';
  return h;
}
function addrPlain(a) { return [a.street, ((a.zip || '') + ' ' + (a.city || '')).trim()].filter(Boolean).join(', '); }
function block(it, kind) {
  var a = kind === 'pick' ? AGR.pickOf(it.p) : it.dest, lieu = kind === 'dest' ? it.dest.place : '', known = hasAddr(a);
  var ico = kind === 'pick' ? '<span class="ico dot" aria-hidden="true"></span>' : '<span class="ico">' + I('pin') + '</span>';
  var head = '<div class="ahead">' + ico + '<span class="lbl">' + (kind === 'pick' ? 'Prise en charge' : 'Destination') + '</span>' + (lieu ? '<span class="sep">·</span><span class="lieu">' + esc(lieu) + '</span>' : '') + '</div>';
  if (!known) return '<div class="ablk ' + kind + '">' + head + '<div class="atxt unk">' + (lieu ? 'adresse inconnue' : 'inconnue') + '</div></div>';
  return '<div class="ablk ' + kind + '">' + head + '<div class="atxt">' + addrHTML2(a) + '</div>' +
    '<div class="afoot"><button class="copy" data-a="copyitem" data-key="' + esc(it.key) + '" data-kind="' + kind + '" aria-label="Copier l’adresse de ' + (kind === 'pick' ? 'prise en charge' : 'destination') + '">' + I('copy') + 'Copier</button></div></div>';
}
function copyText(t, cb) {
  function done(good) { toast(good ? 'Adresse copiée' : 'Copie impossible ici'); if (cb) cb(good); }
  function fallback() {
    try { var ta = document.createElement('textarea'); ta.value = t; ta.style.cssText = 'position:fixed;opacity:0;left:0;top:0'; document.body.appendChild(ta); ta.focus(); ta.select(); var r = document.execCommand('copy'); document.body.removeChild(ta); done(r); } catch (e) { done(false); }
  }
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(function () { done(true); }, fallback); else fallback();
}
function flashCopied(btn, good) {
  if (!btn) return;
  if (btn.dataset.orig === undefined) btn.dataset.orig = btn.innerHTML;
  btn.classList.add('done'); btn.innerHTML = I('check') + (good ? 'Copiée' : 'Copie impossible');
  clearTimeout(btn._t);
  btn._t = setTimeout(function () { btn.classList.remove('done'); btn.innerHTML = btn.dataset.orig; delete btn.dataset.orig; }, 2000);
}
/* montant et km du jour : valeur copiée de la fiche à la création, repère « habituel » tant qu'on n'y touche pas */
function moneyHTML(it, pf) {
  var hp = it.upr != null && it.price === it.upr, hk = it.ukm != null && it.km === it.ukm;
  return '<div class="money"><div class="field"><label for="' + pf + 'montant">Montant du jour (€)' + (hp ? '<span class="hab" id="' + pf + 'hab-p">habituel</span>' : '') + '</label><input class="input" id="' + pf + 'montant" inputmode="decimal" value="' + esc(fmtPrice(it.price)) + '" placeholder="inconnu" autocomplete="off"></div>' +
    '<div class="field"><label for="' + pf + 'km">Kilomètres' + (hk ? '<span class="hab" id="' + pf + 'hab-k">habituel</span>' : '') + '</label><input class="input" id="' + pf + 'km" inputmode="decimal" value="' + esc(fmtKm(it.km)) + '" placeholder="inconnu" autocomplete="off"></div>' +
    '<div class="warnbox" id="' + pf + 'err" role="alert" hidden style="grid-column:1 / -1"></div></div>';
}
function setTag(pf, kind, on) {
  var id = pf + 'hab-' + (kind === 'montant' ? 'p' : 'k'), el = document.getElementById(id);
  if (on && !el) { var lab = document.querySelector('label[for="' + pf + kind + '"]'); if (lab) { var s = document.createElement('span'); s.className = 'hab'; s.id = id; s.textContent = 'habituel'; lab.appendChild(s); } }
  else if (!on && el) el.remove();
}
/* un champ « montant » ou « km » vient d'être validé (on quitte le champ ou « Entrée ») */
function saveMoney(pf, kind) {
  var is, it;
  if (pf === 'm-') { is = iso(day); it = findItem(openKey, is); } else { if (!dsh) return; is = dsh.iso; var p0 = personById(dsh.pid); it = p0 && itemFor(p0, is); }
  if (!it) return;
  var inp = document.getElementById(pf + kind), err = document.getElementById(pf + 'err'), r = parseDecimal(inp.value, 2);
  err.hidden = true; err.textContent = ''; inp.removeAttribute('aria-invalid');
  if (r.err) {
    err.textContent = r.err === 'zero' ? (kind === 'montant' ? 'Montant' : 'Km') + ' : un zéro n’est pas possible. Laisse la case vide si tu ne sais pas.' : (kind === 'montant' ? 'Montant invalide : écris un nombre comme 12,50, ou laisse vide.' : 'Km invalides : écris un nombre comme 8,5, ou laisse vide.');
    err.hidden = false; inp.setAttribute('aria-invalid', 'true'); return;
  }
  var val = r.v == null ? null : Math.round(r.v * (kind === 'montant' ? 100 : 1000)), cur0 = kind === 'montant' ? it.price : it.km;
  if (val === cur0) { inp.value = kind === 'montant' ? fmtPrice(val) : fmtKm(val); return; }       /* rien n'a changé : on ne crée rien */
  ensureRide(it, is).then(function (ride) {
    var oldKey = it.key;
    if (kind === 'montant') ride.price_cents = val; else ride.km_m = val;
    if (it.virt && pf === 'm-') { openKey = ride.id; $$('#s-aujourdhui [data-key="' + oldKey + '"]').forEach(function (el) { el.dataset.key = ride.id; }); }
    return saveRide(ride).then(function () {
      inp.value = kind === 'montant' ? fmtPrice(val) : fmtKm(val);
      setTag(pf, kind, kind === 'montant' ? (ride.usual_price_cents != null && ride.price_cents === ride.usual_price_cents) : (ride.usual_km_m != null && ride.km_m === ride.usual_km_m));
    });
  }, function () { toast('Enregistrement impossible : réessaie'); });
}

/* ========= Aujourd'hui ========= */
var day = today(), openKey = null, openDay = '';
function mount(id, html) {
  var el = document.getElementById(id), sc = el.querySelector('.content'), st = sc ? sc.scrollTop : 0;
  el.innerHTML = html; var n = el.querySelector('.content'); if (n) n.scrollTop = st;
}
function toolsRow() { return '<span class="tools row"><button class="tool" data-a="hide" aria-label="Masquer l’écran">' + I('eyeoff') + '</button></span>'; }
function stateWord(v) { return v === 'done' ? 'Fait' : (v === 'not_done' ? 'Pas fait' : 'À faire'); }
function rndButtons(it, v) {
  var who = esc(it.p.first_name || it.p.last_name);
  var ok = '<button class="rnd ok' + (v === 'done' ? ' on' : '') + '" data-a="aset" data-v="done" data-key="' + esc(it.key) + '" aria-pressed="' + (v === 'done') + '" aria-label="' + (v === 'done' ? 'Fait, toucher pour remettre à faire : ' : 'Fait : ') + who + '"><i>' + I('check') + '</i></button>';
  var ko = '<button class="rnd ko' + (v === 'not_done' ? ' on' : '') + '" data-a="aset" data-v="not_done" data-key="' + esc(it.key) + '" aria-pressed="' + (v === 'not_done') + '" aria-label="' + (v === 'not_done' ? 'Pas fait, toucher pour remettre à faire : ' : 'Pas fait : ') + who + '"><i>' + I('x') + '</i></button>';
  return { ok: ok, ko: ko };
}
function rowHTML(it) {
  var v = it.status, b = rndButtons(it, v), rdv = it.time ? 'Rendez-vous ' + esc(fmtH(it.time)) : 'Rendez-vous à saisir', who = esc(it.p.first_name || it.p.last_name);
  return '<div class="frow" data-key="' + esc(it.key) + '"><button class="fmain" data-a="aopen" data-key="' + esc(it.key) + '" aria-expanded="false"><span class="fl"><span class="name">' + nameHTML(it.p) + '</span><span class="l2' + (it.time ? '' : ' none') + '">' + rdv + (it.changed ? '<span class="chg">changé</span>' : '') + '</span></span><span class="vh">' + stateWord(v) + '</span></button>' +
    '<span class="fr">' + (v === 'done' ? b.ok : (v === 'not_done' ? b.ko : b.ok + b.ko)) + '<button class="fchev" data-a="aopen" data-key="' + esc(it.key) + '" aria-expanded="false" aria-label="Ouvrir : ' + who + '">' + I('down') + '</button></span></div>';
}
function openCardHTML(it) {
  var v = it.status, b = rndButtons(it, v), rdvtxt = it.time ? 'Rendez-vous ' + esc(fmtH(it.time)) : 'Rendez-vous à saisir';
  var meta = it.p.phone ? '<div class="meta"><span>' + esc(it.p.phone) + '</span><a class="call" href="' + esc(telHref(it.p.phone)) + '">' + I('phone') + 'Appeler</a></div>' : '';
  return '<article class="card person open" data-key="' + esc(it.key) + '">' +
    '<button class="who" data-a="afold" data-key="' + esc(it.key) + '" aria-expanded="true"><span class="name">' + nameHTML(it.p) + '</span></button>' +
    '<div class="rdv' + (it.time ? '' : ' none') + '">' + rdvtxt + (it.changed ? '<span class="chg">changé</span>' : '') + '</div>' +
    meta +
    '<div class="states"><div class="pair">' + b.ok + b.ko + '</div><span class="lab">' + stateWord(v) + '</span></div>' +
    block(it, 'pick') + block(it, 'dest') + moneyHTML(it, 'm-') +
    '<div class="cardact"><button class="btn quiet full" data-a="dschg" data-key="' + esc(it.key) + '">Changer ce jour</button>' +
    (it.added && it.r ? '<button class="btn line full" data-a="dsdel" data-key="' + esc(it.key) + '">Supprimer cette course</button>' : '') + '</div>' +
    '<button class="foldbtn" data-a="afold" data-key="' + esc(it.key) + '" aria-expanded="true" aria-label="Refermer la carte">' + I('up') + '</button></article>';
}
function renderAuj() {
  var is = iso(day), list = dayItems(is), T = todayISO();
  if (openDay !== is || (openKey !== null && !list.some(function (x) { return x.key === openKey; }))) { openKey = null; openDay = is; }   /* à l'arrivée et à chaque changement de jour : tout est replié */
  var f = 0, n = 0; list.forEach(function (it) { if (it.status === 'done') f++; else if (it.status === 'not_done') n++; });
  var summary = plural(list.length, 'course', 'courses') + ' · ' + plural(f, 'faite', 'faites') + ' · ' + plural(n, 'pas faite', 'pas faites');
  var h = '<header class="top"><h1 class="vh">Aujourd’hui</h1>' + toolsRow() + '<div class="daynav">' +
    '<button class="arrow" data-a="day" data-d="-1" aria-label="Jour précédent">' + I('left') + '</button>' +
    '<div class="day"><div id="day-label">' + esc(cap(fmtDay.format(day))) + '</div><small id="day-summary">' + summary + '</small></div>' +
    '<button class="arrow" data-a="day" data-d="1" aria-label="Jour suivant">' + I('right') + '</button></div>' +
    (is === T ? '' : '<button class="today-btn" data-a="today">' + I('undo') + 'Revenir à aujourd’hui</button>') + '</header>';
  var body = '<div class="content">';
  if (!list.length) body += '<div class="card empty">Aucune course prévue ce jour.</div>';
  list.forEach(function (it) { body += it.key !== openKey ? rowHTML(it) : openCardHTML(it); });
  body += '<button class="btn line full" data-a="aadd">Ajouter une course</button></div>';
  mount('s-aujourdhui', h + body);
}
function setStatus(key, v) {
  var is = iso(day), it = findItem(key, is); if (!it) return;
  var nv = it.status === v ? null : v, who = it.p.first_name || it.p.last_name;
  ensureRide(it, is).then(function (ride) {
    var prev = { status: ride.status, skip: ride.skip }, created = it.virt;
    ride.status = nv; ride.skip = false;
    return saveRide(ride).then(function () {
      renderAuj();
      toast(who + ' : ' + (nv === 'done' ? 'fait' : (nv === 'not_done' ? 'pas fait' : 'remis à faire')) + '.', function () {
        if (created) ride.deleted_at = nowIso(); else { ride.status = prev.status; ride.skip = prev.skip; }   /* annuler une création = corbeille, jamais d'effacement */
        saveRide(ride).then(refreshUnder);
      });
    });
  }, function () { toast('Enregistrement impossible : réessaie'); });
}

/* ========= petit panneau d'un jour (Aujourd'hui et calendrier d'une personne) ========= */
var dsh = null;    /* {pid, iso, mode: 'menu'|'form'|'pick', add: bool, direct: bool} */
function sheetOpen(o) { dsh = o; renderSheet(); $('#daysheet').classList.add('on'); }
function sheetClose() { dsh = null; $('#daysheet').classList.remove('on'); }
function sheetHTML() {
  var is = dsh.iso, title = cap(fmtDay.format(parseISO(is))), T = todayISO(), h;
  if (dsh.mode === 'pick') {
    var avail = sortPeople(activePeople().filter(function (p) { return !itemFor(p, is); }));
    h = '<p class="t" id="ds-title">Ajouter une course</p><p class="note" style="padding:0">' + esc(title) + ' · choisis la personne</p>';
    if (!avail.length) h += '<p class="note" style="padding:0">Toutes les personnes ont déjà une course ce jour-là.</p>';
    else h += '<div class="card" style="padding-top:2px;padding-bottom:2px">' + avail.map(function (p) { return '<button class="list-item" data-a="dspick" data-id="' + esc(p.id) + '"><span class="name">' + nameHTML(p) + '</span>' + I('right') + '</button>'; }).join('') + '</div>';
    return h + '<button class="btn line full" data-a="dsclose">Fermer</button>';
  }
  var p = personById(dsh.pid), who = esc(fullName(p)), it = itemFor(p, is), r = it && it.r, hab = AGR.isScheduled(p, is), st = it ? it.status : null;
  if (dsh.mode === 'form') {
    var d = it ? it.dest : AGR.destOf(p), tv = it ? it.time : AGR.timeFor(p);
    return '<p class="t" id="ds-title">' + (dsh.add ? 'Ajouter une course' : 'Changer ce jour') + '</p><p class="note" style="padding:0">' + esc(title) + ' · ' + who + '</p>' +
      '<div class="field"><label for="ds-heure">Heure</label><input class="input" id="ds-heure" value="' + esc(tv || '') + '" placeholder="13:00" inputmode="numeric" autocomplete="off" maxlength="5"></div>' +
      '<div class="field"><label for="ds-lieu">Destination</label><input class="input" id="ds-lieu" value="' + esc(d.place) + '" placeholder="Nom du lieu" autocomplete="off" autocapitalize="words"><input class="input" id="ds-rue" value="' + esc(d.street) + '" placeholder="Rue et numéro" aria-label="Rue et numéro" autocomplete="off"><div class="zip-city"><input class="input" id="ds-cp" value="' + esc(d.zip) + '" placeholder="Code postal" aria-label="Code postal" inputmode="numeric" maxlength="5" autocomplete="off"><input class="input" id="ds-ville" value="' + esc(d.city) + '" placeholder="Ville" aria-label="Ville" autocomplete="off" autocapitalize="words"></div></div>' +
      '<div class="warnbox" id="ds-err" role="alert" hidden></div>' +
      '<button class="btn strong full" data-a="dssave">Enregistrer</button><button class="btn line full" data-a="dsback">Annuler</button>';
  }
  var btn = function (a, label, on) { return '<button class="btn line full' + (on ? ' sel' : '') + '" data-a="' + a + '" aria-pressed="' + (!!on) + '">' + label + '</button>'; };
  h = '<p class="t" id="ds-title">' + esc(title) + '</p><p class="note" style="padding:0">' + who + (it && it.time ? ' · ' + esc(fmtH(it.time)) : '') + (it && it.changed ? ' · changé' : '') + '</p>';
  if (is < T) {
    if (it || hab) h += btn('dsfait', 'Fait', st === 'done') + btn('dspas', 'Pas fait', st === 'not_done') + moneyHTML(it || AGR.virtItem(p, is), 'ds-');
    else h += btn('dsadd', 'Ajouter une course', false);
  } else if (hab) {
    h += btn('dscomme', 'Comme d’habitude', st !== 'not_done' && !(it && it.changed)) + btn('dschg', 'Changer ce jour', !!(it && it.changed) && st !== 'not_done') + btn('dspas', 'Pas de course', st === 'not_done');
  } else if (it) {
    h += btn('dschg', 'Changer ce jour', st !== 'not_done') + btn('dspas', 'Pas de course', st === 'not_done');
  } else h += btn('dsadd', 'Ajouter une course', false);
  if (r && r.added) h += '<button class="btn line full" data-a="dsdel">Supprimer cette course</button>';
  return h + '<button class="btn line full" data-a="dsclose">Fermer</button>';
}
function renderSheet() { $('#ds-panel').innerHTML = sheetHTML(); }
function sheetSave() {
  var p = personById(dsh.pid), is = dsh.iso, g = function (i) { return document.getElementById(i).value.trim(); }, er = document.getElementById('ds-err');
  var t = parseTime(g('ds-heure'));
  if (t.err) { er.textContent = 'Heure invalide : écris par exemple 13:00, ou laisse vide.'; er.hidden = false; document.getElementById('ds-heure').focus(); return; }
  var dest = { place: g('ds-lieu'), street: g('ds-rue'), zip: g('ds-cp'), city: g('ds-ville') }, add = dsh.add;
  var it = itemFor(p, is), run;
  if (add) { var nr = AGR.newRide(p, is, { time: t.v, dest: dest, added: true, changed: false }); rides.push(nr); run = AG.putRide(nr).then(function () { return nr; }, function (e) { rides.splice(rides.indexOf(nr), 1); throw e; }); }
  else run = ensureRide(it, is).then(function (ride) {
    ride.time = t.v; ride.dest_place = dest.place; ride.dest_street = dest.street; ride.dest_zip = dest.zip; ride.dest_city = dest.city;
    ride.changed = true; ride.skip = false; if (ride.status === 'not_done') ride.status = null;
    return saveRide(ride).then(function () { return ride; });
  });
  run.then(function () { sheetClose(); refreshUnder(); toast(add ? 'Course ajoutée' : 'Jour changé'); }, function () { toast('Enregistrement impossible : réessaie'); });
}
function sheetAction(a) {
  var p = dsh.pid ? personById(dsh.pid) : null, is = dsh.iso;
  if (a === 'dschg') { dsh.mode = 'form'; dsh.add = false; renderSheet(); return; }
  if (a === 'dsadd') { dsh.mode = 'form'; dsh.add = true; renderSheet(); return; }
  if (a === 'dsback') { if (dsh.direct) sheetClose(); else { dsh.mode = 'menu'; renderSheet(); } return; }
  if (a === 'dssave') { sheetSave(); return; }
  if (a === 'dsdel') {
    var r0 = AGR.rideOf(rides, p.id, is); if (!r0) return;
    r0.deleted_at = nowIso();
    saveRide(r0).then(function () { sheetClose(); refreshUnder(); toast('Course supprimée', function () { r0.deleted_at = null; saveRide(r0).then(refreshUnder); }); });
    return;
  }
  var it = itemFor(p, is);
  if (a === 'dscomme') {     /* annule un changement : heure et destination de la fiche, jour remis à faire ; prix et km gardés */
    var r1 = it && it.r;
    if (r1) {
      var d = AGR.destOf(p); r1.time = AGR.timeFor(p); r1.dest_place = d.place; r1.dest_street = d.street; r1.dest_zip = d.zip; r1.dest_city = d.city; r1.changed = false; r1.skip = false;
      if (r1.status === 'not_done') r1.status = null;
      saveRide(r1).then(function () { sheetClose(); refreshUnder(); toast('Comme d’habitude'); });
    } else { sheetClose(); refreshUnder(); toast('Comme d’habitude'); }
    return;
  }
  if (a === 'dspas' && is >= todayISO()) {      /* « Pas de course » = le jour passe à « pas fait » (un seul état) */
    ensureRide(it, is).then(function (ride) {
      var prev = { status: ride.status, skip: ride.skip }, created = it.virt;
      ride.status = 'not_done'; ride.skip = true;
      return saveRide(ride).then(function () {
        sheetClose(); refreshUnder();
        toast('Pas de course ce jour', function () { if (created) ride.deleted_at = nowIso(); else { ride.status = prev.status; ride.skip = prev.skip; } saveRide(ride).then(refreshUnder); });
      });
    }, function () { toast('Enregistrement impossible : réessaie'); });
    return;
  }
  /* jour passé : corriger fait / pas fait (retoucher le choix actuel le vide) */
  var v = a === 'dsfait' ? 'done' : 'not_done';
  ensureRide(it, is).then(function (ride) { ride.status = ride.status === v ? null : v; ride.skip = false; return saveRide(ride); }).then(function () { renderSheet(); refreshUnder(); }, function () { toast('Enregistrement impossible : réessaie'); });
}

/* ========= Calendrier d'une personne ========= */
function openCalendar(pid) {
  var t = today(); ctx.calPid = pid; ctx.calY = t.getFullYear(); ctx.calM = t.getMonth();
  history.pushState({ app: 1 }, ''); renderCal(); go('calendrier'); $('#s-calendrier .content').scrollTop = 0;
}
function renderCal() {
  var p = personById(ctx.calPid); if (!p) return;
  var y = ctx.calY, m = ctx.calM, first = new Date(y, m, 1), off = wd(first) - 1, L = ['L', 'M', 'M', 'J', 'V', 'S', 'D'], n = new Date(y, m + 1, 0).getDate(), T = todayISO();
  var cnt = { t: 0, p: 0, a: 0, b: 0 }, cells = '';
  for (var i = 0; i < off; i++) cells += '<div class="blank"></div>';
  for (var d = 1; d <= n; d++) {
    var is = y + '-' + pad(m + 1) + '-' + pad(d), v = AGR.state(p, rides, is, T);
    if (v === 't') cnt.t++; else if (v === 'p') cnt.p++; else if (v === 'a') cnt.a++; else cnt.b++;
    cells += '<button class="cell ' + v + (is === T ? ' today' : '') + '" data-a="calday" data-iso="' + is + '" aria-label="' + esc(cap(fmtDay.format(parseISO(is)))) + ' : ' + (v === 't' ? 'transportée' : (v === 'p' ? 'pas transportée' : (v === 'a' ? 'à faire' : (v === 'n' ? 'pas noté' : 'pas de course')))) + '"><span>' + d + '</span>' + (v === 't' ? I('check') : (v === 'p' ? I('x') : (v === 'a' ? I('ring') : ''))) + '</button>';
  }
  var h = '<header class="top"><div class="backrow"><button class="back" data-a="back">' + I('left') + 'Retour</button>' + tools() + '</div><h1 style="margin-top:6px">Calendrier et courses</h1><div class="sub">' + esc(fullName(p)) + '</div>' +
    '<div class="monthnav"><button class="chev" data-a="month" data-d="-1" aria-label="Mois précédent">' + I('left') + '</button><div class="lbl">' + esc(cap(fmtMonth.format(first))) + '</div><button class="chev" data-a="month" data-d="1" aria-label="Mois suivant">' + I('right') + '</button></div></header>' +
    '<div class="content"><div class="card" style="padding:4px"><div class="calgrid">' + L.map(function (l) { return '<div class="dow">' + l + '</div>'; }).join('') + cells + '</div></div>' +
    '<p class="summary" id="cal-summary">' + cnt.t + ' transportée, ' + cnt.p + ' pas transportée, ' + (cnt.a ? cnt.a + ' à faire, ' : '') + plural(cnt.b, 'jour', 'jours') + ' sans note</p>' +
    '<div class="legend"><span><i class="sw t">' + I('check') + '</i>Transportée</span><span><i class="sw p">' + I('x') + '</i>Pas transportée</span><span><i class="sw a">' + I('ring') + '</i>À faire</span><span><i class="sw n"></i>Pas noté</span></div></div>';
  mount('s-calendrier', h);
}

/* ========= Journal de mise à jour (les 20 derniers évènements, gardés dans la base) ========= */
var evlog = [];
function logEvt(text, at) {
  evlog.push({ t: at || nowIso(), e: text, v: APP_VERSION });
  return flushLog();
}
function flushLog() {
  if (!AG.db || !evlog.length) return Promise.resolve();
  var batch = evlog.splice(0);
  return AG.appendLog(batch).then(refreshLog, function () { evlog = batch.concat(evlog); });
}
function fmtStamp(t) { var d = new Date(t); return pad(d.getDate()) + '/' + pad(d.getMonth() + 1) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()); }
function refreshLog() {
  if (cur !== 'reglages' || !AG.db) return Promise.resolve();
  return AG.getLog().then(function (list) {
    $('#rg-log').innerHTML = list.slice().reverse().map(function (x) { return '<li><time>' + esc(fmtStamp(x.t)) + '</time><span>' + esc(x.e) + '</span><span class="v">' + esc(x.v || '') + '</span></li>'; }).join('');
    $('#rg-log-empty').hidden = list.length > 0;
  });
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
  return AG.getMeta('persist_asked').then(function (asked) {
    if (asked) return refreshPersist();
    return askPersist().then(function () { return AG.putMeta('persist_asked', new Date().toISOString()); }).then(refreshPersist);
  });
}
function setIdle(n) {
  idleSec = n; lastTouch = Date.now(); refreshReglages();
  if (AG.db) AG.putSetting('idle_sec', n).catch(function () {});
}

/* ========= mises à jour (service worker) : jamais de rechargement automatique ========= */
var swReg = null, updateReady = false, userAsked = false, reloading = false;
function showUpdate() { if (!updateReady) logEvt('Nouvelle version prête (en attente du toucher sur « Mettre à jour »)'); updateReady = true; $('#update').hidden = false; if (cur === 'reglages') refreshReglages(); }
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
    /* le nouveau service worker vient de prendre la main : on attend qu'il soit « activé » (voir applyUpdate) ; filet de sécurité de 3 s */
    logEvt('Changement de service worker (le nouveau prend la main)');
    if (userAsked && !reloading) setTimeout(reloadOnce, 3000);
  });
}
/* Un seul rechargement, jamais de boucle, et seulement après « Mettre à jour » ET quand le nouveau service worker est actif.
   Avant de recharger, la page LÂCHE sa connexion à la base : sinon elle pourrait bloquer la mise à niveau de la page suivante. */
function reloadOnce() {
  if (reloading || !userAsked) return;
  reloading = true;
  logEvt('Rechargement de la page').then(function () { AG.closeDb(); setTimeout(function () { location.reload(); }, 150); });   /* le journal est écrit AVANT de lâcher la base */
}
function applyUpdate() {
  var w = swReg && swReg.waiting; if (!w) return;
  userAsked = true; logEvt('Bouton « Mettre à jour » touché');
  w.addEventListener('statechange', function () { if (w.state === 'activated') { logEvt('Nouveau service worker actif'); reloadOnce(); } });
  w.postMessage({ type: 'SKIP_WAITING' });
}
function checkUpdate() {
  if (!swReg) { toast('Mise à jour impossible ici'); return; }
  swReg.update().then(function () {
    if (updateReady) return;
    if (swReg.installing || swReg.waiting) toast('Nouvelle version trouvée, préparation…', null, 4000);   /* le message « Nouvelle version disponible » suit */
    else toast('Cette version est la plus récente');
  }, function () { toast('Pas de connexion : réessaie plus tard'); });
}

/* ========= œil et masquage automatique (par comparaison d'heure, pas par minuterie) ========= */
function setInert(on) {
  ['#views', '#toast', '#update', '#confirm', '#daysheet', '.nav'].forEach(function (s) {
    var e = $(s); if (!e) return; e.inert = on;
    if (on) e.setAttribute('aria-hidden', 'true'); else e.removeAttribute('aria-hidden');
  });
}
function mask() {
  if (veilOn) return;
  clearTimeout(toastTimer); toastEl.hidden = true; undoFn = null;      /* un message ne doit rien montrer sous l'écran neutre */
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();      /* valide un champ en cours de saisie */
  openKey = null; if (cur === 'aujourdhui') renderAuj();                                          /* au retour, les cartes sont repliées : montants et adresses retirés de l'écran */
  veilEl.innerHTML = '<span class="vword">Agenda</span>';
  veilEl.setAttribute('role', 'button'); veilEl.setAttribute('tabindex', '0'); veilEl.setAttribute('aria-label', 'Agenda masqué. Toucher pour rouvrir');
  veilOn = true; veilEl.classList.add('on'); setInert(true);
}
function unmask() { veilOn = false; veilEl.classList.remove('on'); veilEl.innerHTML = ''; setInert(false); lastTouch = Date.now(); }
/* minuit passé : « Aujourd'hui » suit le calendrier (si on regardait le jour courant, on passe au nouveau jour) */
var lastToday = todayISO();
function dayRollover() {
  var t = todayISO(); if (t === lastToday) return;
  var wasToday = iso(day) === lastToday; lastToday = t;
  if (wasToday) day = today();
  if (cur === 'aujourdhui') renderAuj();
}
function tick() {
  dayRollover();
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
var suppress = false;
document.addEventListener('click', function (e) {
  var b = e.target.closest('[data-a]'); if (!b) return;
  var a = b.dataset.a, id = b.dataset.id;
  switch (a) {
    case 'tab': if (ficheDirty()) { openConfirm('leave', null, b.dataset.t); break; } go(b.dataset.t); break;
    case 'reglages': history.pushState({ app: 1 }, ''); go('reglages'); break;
    case 'back': if (cur === 'fiche' || cur === 'calendrier') back(); else go('bilan'); break;
    case 'hide': mask(); break;
    case 'idle': setIdle(+b.dataset.n); break;
    case 'persist': askPersist().then(refreshPersist); break;
    case 'checkupdate': checkUpdate(); break;
    case 'applyupdate': applyUpdate(); break;
    case 'undo': if (undoFn) { var f = undoFn; undoFn = null; toastEl.hidden = true; clearTimeout(toastTimer); f(); } break;
    case 'newperson': openNew(); break;
    case 'fiche': openFiche(id); break;
    case 'archshow': showArch = true; renderPers(); break;
    case 'archhide': showArch = false; renderPers(); break;
    case 'restore':
      var rp = null; people.forEach(function (x) { if (x.id === id) rp = x; }); if (!rp) break;
      setArchived(rp, false).then(function (q) {
        renderPers(); toast(fullName(q) + ' de nouveau dans les listes.', function () { setArchived(q, true).then(function () { if (cur === 'personnes') renderPers(); }); });
      });
      break;
    case 'callfiche': if (!document.getElementById('f-tel').value.trim()) { e.preventDefault(); toast('Téléphone inconnu'); } break;
    case 'fmode':
      ctx.mode = b.dataset.m; document.getElementById('q-sem').hidden = ctx.mode === 'dat'; document.getElementById('q-dat').hidden = ctx.mode !== 'dat';
      $$('[data-a="fmode"]').forEach(function (x) { var on = x.dataset.m === ctx.mode; x.classList.toggle('sel', on); x.setAttribute('aria-pressed', on); });
      break;
    case 'fmonth': var fm = new Date(ctx.dm.y, ctx.dm.m + (+b.dataset.d), 1); ctx.dm = { y: fm.getFullYear(), m: fm.getMonth() }; document.getElementById('f-dates').innerHTML = fdatesHTML(); break;
    case 'fdate': if (b.dataset.iso < todayISO()) break; ctx.dates[b.dataset.iso] = !ctx.dates[b.dataset.iso]; document.getElementById('f-dates').innerHTML = fdatesHTML(); break;
    case 'fshort':
      var fl = datesOfDay(+b.dataset.j), fall = fl.length > 0 && fl.every(function (x) { return ctx.dates[x]; });
      fl.forEach(function (x) { ctx.dates[x] = !fall; }); document.getElementById('f-dates').innerHTML = fdatesHTML(); break;
    case 'jour': var j = +b.dataset.j, k = ctx.jours.indexOf(j); if (k >= 0) ctx.jours.splice(k, 1); else ctx.jours.push(j); b.classList.toggle('on'); b.setAttribute('aria-pressed', k < 0); break;
    case 'savefiche': saveFiche(); break;
    case 'archiveask': openConfirm('archive', id); break;
    case 'deleteask': openConfirm('delete', id); break;
    case 'day': day = addDays(day, +b.dataset.d); renderAuj(); break;
    case 'today': if (iso(day) === todayISO()) toast('C’est déjà aujourd’hui'); else { day = today(); renderAuj(); } break;
    case 'aopen':
      openKey = b.dataset.key; openDay = iso(day); renderAuj();
      var oc = document.querySelector('#s-aujourdhui .person[data-key="' + openKey + '"]');
      if (oc) { oc.scrollIntoView({ block: 'nearest' }); var ow = oc.querySelector('.who'); if (ow) ow.focus({ preventScroll: true }); }
      break;
    case 'afold': var fk = openKey; openKey = null; renderAuj(); var fr = document.querySelector('#s-aujourdhui .frow[data-key="' + fk + '"] .fmain'); if (fr) fr.focus({ preventScroll: true }); break;
    case 'aset': setStatus(b.dataset.key, b.dataset.v); break;
    case 'copyitem': var ci = findItem(b.dataset.key, iso(day)); if (ci) copyText(addrPlain(b.dataset.kind === 'dest' ? ci.dest : AGR.pickOf(ci.p)), function (good) { flashCopied(b, good); }); break;
    case 'aadd': sheetOpen({ iso: iso(day), mode: 'pick', direct: true }); break;
    case 'calfiche': if (ficheDirty()) { openConfirm('leave', null, { cal: id }); break; } openCalendar(id); break;
    case 'month': var mm = new Date(ctx.calY, ctx.calM + (+b.dataset.d), 1); ctx.calY = mm.getFullYear(); ctx.calM = mm.getMonth(); renderCal(); break;
    case 'calday': sheetOpen({ pid: ctx.calPid, iso: b.dataset.iso, mode: 'menu', direct: false }); break;
    case 'dsclose': sheetClose(); break;
    case 'dspick': if (dsh) { dsh = { pid: id, iso: dsh.iso, mode: 'form', add: true, direct: true }; renderSheet(); } break;
    case 'dschg': case 'dsdel': case 'dsadd': case 'dsback': case 'dssave': case 'dscomme': case 'dspas': case 'dsfait':
      if (!dsh) {      /* depuis la carte ouverte d'Aujourd'hui */
        var di = findItem(b.dataset.key, iso(day)); if (!di) break;
        if (a === 'dschg') sheetOpen({ pid: di.pid, iso: iso(day), mode: 'form', add: false, direct: true });
        else if (a === 'dsdel') { sheetOpen({ pid: di.pid, iso: iso(day), mode: 'menu', direct: true }); sheetAction('dsdel'); }
        break;
      }
      sheetAction(a); break;
    case 'confirmcancel': closeConfirm(); break;
    case 'confirmok': confirmOk(); break;
  }
});
$('#q').addEventListener('input', function () { query = this.value; renderPers(); });
document.addEventListener('input', function (e) {
  var t = e.target, id = t.id, v;
  if (/^(m|ds)-(montant|km)$/.test(id)) { v = t.value.replace(/[^0-9.,]/g, ''); if (v !== t.value) t.value = v; }
  if (id === 'ds-cp') { v = t.value.replace(/\D/g, '').slice(0, 5); if (v !== t.value) t.value = v; }
  if (id === 'ds-heure') { v = t.value.replace(/[^0-9h:]/gi, '').slice(0, 5); if (v !== t.value) t.value = v; }
});
document.addEventListener('change', function (e) { var m = /^(m-|ds-)(montant|km)$/.exec(e.target.id); if (m) saveMoney(m[1], m[2]); });
document.addEventListener('keydown', function (e) { if (e.key === 'Enter' && /^(m|ds)-(montant|km)$/.test(e.target.id)) e.target.blur(); });
$('#s-fiche').addEventListener('input', function (e) {
  var t = e.target, id = t.id, v;
  if (id === 'f-cp' || id === 'f-lcp') { v = t.value.replace(/\D/g, '').slice(0, 5); if (v !== t.value) t.value = v; }
  if (id === 'f-prix' || id === 'f-km') { v = t.value.replace(/[^0-9.,]/g, ''); if (v !== t.value) t.value = v; }
  if (id === 'f-heure' || id === 'f-heured') { v = t.value.replace(/[^0-9h:]/gi, '').slice(0, 5); if (v !== t.value) t.value = v; }
  if (!ctx.pid && (id === 'f-nom' || id === 'f-pre')) { var dw = document.getElementById('dup-warn'), tx = dupMsg(); dw.textContent = tx; dw.hidden = !tx; }
  if (id === 'f-tel') { var a = document.getElementById('f-call'), tv = t.value.trim(); if (tv) a.setAttribute('href', telHref(tv)); else a.removeAttribute('href'); }
});

/* touche Retour d'Android : revient en arrière dans l'appli */
try {
  history.replaceState({ app: 1 }, ''); history.pushState({ app: 1 }, '');
  window.addEventListener('popstate', function () {
    if (veilOn) { history.pushState({ app: 1 }, ''); return; }
    if ($('#confirm').classList.contains('on')) { closeConfirm(); history.pushState({ app: 1 }, ''); return; }
    if (dsh) { sheetClose(); history.pushState({ app: 1 }, ''); return; }
    if (cur === 'fiche' || cur === 'calendrier') { back(); history.pushState({ app: 1 }, ''); }
    else if (cur === 'reglages') { go('bilan'); history.pushState({ app: 1 }, ''); }
    else if (tab !== 'aujourdhui') { go('aujourdhui'); history.pushState({ app: 1 }, ''); }
  });
} catch (e) { /* sans historique : rien à faire */ }

/* ========= erreurs graves : on explique, on n'efface jamais rien ========= */
function fatal(title, text) {
  $('#fatal-title').textContent = title; $('#fatal-text').textContent = text; $('#fatal').classList.add('on');
}
AG.onClosed = function () {
  fatal('Agenda a été mis à jour dans une autre fenêtre', 'Ferme cette fenêtre et rouvre Agenda. Rien n’a été effacé.');
};
/* Mise à niveau des données retenue par une ancienne page encore ouverte : message simple au lieu d'un écran muet.
   Il disparaît tout seul si le blocage se lève. */
var blockedShown = false, isReady = false;
function showBlocked() {
  if (isReady || blockedShown) return;
  blockedShown = true; logEvt('Ouverture de la base bloquée : une autre page garde l’ancienne structure ouverte');
  fatal('Fermez et rouvrez l’appli pour finir la mise à jour', 'Rien n’a été effacé. Si ce message reste, fermez complètement Agenda (balayez-le dans les applis récentes), puis rouvrez-le.');
}
function hideBlocked() { if (blockedShown) { blockedShown = false; $('#fatal').classList.remove('on'); } }
setTimeout(function () { if (!isReady) logEvt('Base pas prête après 5 secondes'); showBlocked(); }, 5000);   /* base pas prête après 5 secondes : même message, pas d'écran figé */

/* ========= démarrage ========= */
/* évènements du démarrage dans le journal : mise à niveau de la structure faite par cette page, changement de version, base ouverte */
function startupLog() {
  return AG.getMeta('last_upgrade').then(function (u) {
    return AG.getMeta('logged_upgrade_at').then(function (seen) {
      if (u && u.at !== seen) { if (u.from > 0) logEvt('Structure des données mise à niveau : ' + u.from + ' → ' + u.to, u.at); return AG.putMeta('logged_upgrade_at', u.at); }
    });
  }).then(function () { return AG.getMeta('last_version'); }).then(function (lv) {
    if (lv && lv !== APP_VERSION) logEvt('Version de l’appli passée de ' + lv + ' à ' + APP_VERSION);
    else if (!lv) logEvt('Version précédente non notée (première ouverture, ou ancienne version sans journal)');
    return AG.putMeta('last_version', APP_VERSION);
  }).then(function () { return logEvt('Base ouverte (structure ' + schemaVersion + ')'); });
}
logEvt('Démarrage de la version ' + APP_VERSION);
var ready = AG.init({ onBlocked: showBlocked }).then(function () {
  return AG.getMeta('schema_version').then(function (v) { schemaVersion = v; });
}).then(function () {
  return AG.getSetting('idle_sec');
}).then(function (n) {
  if (typeof n === 'number') idleSec = n;
  return AG.allPersons();
}).then(function (list) {
  people = list; return AG.allRides();
}).then(function (rs) {
  rides = rs; renderPers(); renderAuj();
  return startupLog();
}).then(function () {
  return firstLaunchStorage();
}).then(function () { isReady = true; hideBlocked(); refreshReglages(); }, function (er) {
  isReady = true; hideBlocked();
  if (er && er.code === 'newer') fatal('Données plus récentes que l’appli', 'Les données de ce téléphone ont été écrites par une version plus récente d’Agenda. Rien n’a été effacé. Ferme l’appli, rouvre-la avec internet pour la mettre à jour, puis réessaie.');
  else fatal('Stockage indisponible', 'Agenda ne peut pas ouvrir son stockage sur ce téléphone. Rien n’a été effacé. Ferme et rouvre l’appli ; si le message revient, ne saisis rien et préviens celui qui t’aide.');
});

go('aujourdhui');
startWorker();

/* lecture seule, pour les contrôles automatiques */
window.__ag = {
  get cur() { return cur; }, get tab() { return tab; }, get masked() { return veilOn; }, get idle() { return idleSec; },
  get ready() { return ready; }, get updateReady() { return updateReady; }, get people() { return people.slice(); }, get rides() { return rides.slice(); }, get day() { return iso(day); },
  version: APP_VERSION, dbName: AG.DB_NAME, openDatabase: AG.openDatabase, dbGet: AG.dbGet, dbPut: AG.dbPut,
  migrations: AG.MIGRATIONS, schemaTarget: AG.schemaTarget
};
})();
