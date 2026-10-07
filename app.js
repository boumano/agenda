/* Agenda : écrans et comportements. Étape 2 : personnes et fiche. Aucune donnée dans ce fichier, aucune bibliothèque, aucune adresse internet.
   Les données passent par db.js (AG). Présentation, textes et règles repris de la maquette. */
(function () {
'use strict';

/* ========= petits outils ========= */
function $(s, r) { return (r || document).querySelector(s); }
function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
var APP_VERSION = self.APP_VERSION || '?';
var AG = self.AG;
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
var schemaVersion = null, people = [];
var cur = 'aujourdhui', tab = 'aujourdhui';
var idleSec = 120;                       /* réglable : 0 (jamais), 60, 120, 600 */
var veilEl = $('#veil'), veilOn = false, lastTouch = Date.now(), swallowClick = false;
var toastEl = $('#toast'), toastTimer = null, undoFn = null;
var showArch = false, query = '';
var ctx = { pid: null, person: null, mode: 'sem', jours: [], du: '', au: '', dates: {}, dm: { y: 0, m: 0 }, leaving: false, noted: 0, planned: 0 };
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
  cur = id;
  if (TABS.indexOf(id) >= 0) tab = id; else tab = id === 'fiche' ? 'personnes' : 'bilan';   /* sous-pages : l'onglet d'origine reste allumé */
  $$('.screen').forEach(function (s) { s.classList.toggle('on', s.id === 's-' + id); });
  $$('.nav button.t').forEach(function (b) {
    var on = b.dataset.t === tab; b.classList.toggle('on', on);
    if (on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  if (id === 'reglages') refreshReglages();
  if (id === 'personnes') renderPers();
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
    history.pushState({ app: 1 }, ''); renderFiche(); go('fiche'); $('#s-fiche .content').scrollTop = 0;
  });
}
function openNew() {
  var t = today();
  ctx.pid = null; ctx.person = null; ctx.jours = []; ctx.mode = 'sem'; ctx.du = iso(t); ctx.au = ''; ctx.dates = {}; ctx.dm = { y: t.getFullYear(), m: t.getMonth() }; ctx.noted = 0; ctx.planned = 0;
  history.pushState({ app: 1 }, ''); renderFiche(); go('fiche'); $('#s-fiche .content').scrollTop = 0;
}
function readFiche() {
  var g = function (i) { return document.getElementById(i).value.trim(); };
  return { nom: g('f-nom'), pre: g('f-pre'), rue: g('f-rue'), cp: g('f-cp'), ville: g('f-ville'), lieu: g('f-lieu'), lrue: g('f-lrue'), lcp: g('f-lcp'), lville: g('f-lville'), tel: g('f-tel'), heure: g('f-heure'), heureD: g('f-heured'), du: g('f-du'), au: g('f-au'), prix: g('f-prix'), km: g('f-km') };
}
/* « Quitter sans enregistrer ? » : seulement pour une nouvelle personne dont on a déjà rempli quelque chose (comme la maquette) */
function ficheDirty() {
  if (cur !== 'fiche' || ctx.pid || ctx.leaving || !document.getElementById('f-nom')) return false;
  var v = readFiche(); for (var k in v) if (v[k] && !(k === 'du' && v[k] === todayISO())) return true;
  return ctx.jours.length > 0 || Object.keys(ctx.dates).some(function (d) { return ctx.dates[d]; });
}
function dupMsg() {
  var n = norm(document.getElementById('f-nom').value.trim()), r = norm(document.getElementById('f-pre').value.trim()), hit = null;
  if (n && r) people.some(function (p) { if (norm(p.last_name) === n && norm(p.first_name) === r) { hit = p; return true; } return false; });
  return hit ? ('Une fiche « ' + hit.last_name + ' ' + hit.first_name + ' » existe déjà' + (hit.archived ? ' (archivée)' : '') + '. Tu peux quand même enregistrer.') : '';
}
function back() {
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
  if (cc.kind === 'leave') { ctx.leaving = true; if (cc.target) go(cc.target); else go('personnes'); ctx.leaving = false; return; }
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
    if (swReg.installing || swReg.waiting) toast('Nouvelle version trouvée, préparation…', null, 4000);   /* le message « Nouvelle version disponible » suit */
    else toast('Cette version est la plus récente');
  }, function () { toast('Pas de connexion : réessaie plus tard'); });
}

/* ========= œil et masquage automatique (par comparaison d'heure, pas par minuterie) ========= */
function setInert(on) {
  ['#views', '#toast', '#update', '#confirm', '.nav'].forEach(function (s) {
    var e = $(s); if (!e) return; e.inert = on;
    if (on) e.setAttribute('aria-hidden', 'true'); else e.removeAttribute('aria-hidden');
  });
}
function mask() {
  if (veilOn) return;
  clearTimeout(toastTimer); toastEl.hidden = true; undoFn = null;      /* un message ne doit rien montrer sous l'écran neutre */
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
var suppress = false;
document.addEventListener('click', function (e) {
  var b = e.target.closest('[data-a]'); if (!b) return;
  var a = b.dataset.a, id = b.dataset.id;
  switch (a) {
    case 'tab': if (ficheDirty()) { openConfirm('leave', null, b.dataset.t); break; } go(b.dataset.t); break;
    case 'reglages': history.pushState({ app: 1 }, ''); go('reglages'); break;
    case 'back': if (cur === 'fiche') back(); else go('bilan'); break;
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
    case 'confirmcancel': closeConfirm(); break;
    case 'confirmok': confirmOk(); break;
  }
});
$('#q').addEventListener('input', function () { query = this.value; renderPers(); });
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
    if (cur === 'fiche') { back(); history.pushState({ app: 1 }, ''); }
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

/* ========= démarrage ========= */
var ready = AG.init().then(function () {
  return AG.getMeta('schema_version').then(function (v) { schemaVersion = v; });
}).then(function () {
  return AG.getSetting('idle_sec');
}).then(function (n) {
  if (typeof n === 'number') idleSec = n;
  return AG.allPersons();
}).then(function (list) {
  people = list; renderPers();
  return firstLaunchStorage();
}).then(function () { refreshReglages(); }, function (er) {
  if (er && er.code === 'newer') fatal('Données plus récentes que l’appli', 'Les données de ce téléphone ont été écrites par une version plus récente d’Agenda. Rien n’a été effacé. Ferme l’appli, rouvre-la avec internet pour la mettre à jour, puis réessaie.');
  else fatal('Stockage indisponible', 'Agenda ne peut pas ouvrir son stockage sur ce téléphone. Rien n’a été effacé. Ferme et rouvre l’appli ; si le message revient, ne saisis rien et préviens celui qui t’aide.');
});

go('aujourdhui');
renderPers();
startWorker();

/* lecture seule, pour les contrôles automatiques */
window.__ag = {
  get cur() { return cur; }, get tab() { return tab; }, get masked() { return veilOn; }, get idle() { return idleSec; },
  get ready() { return ready; }, get updateReady() { return updateReady; }, get people() { return people.slice(); },
  version: APP_VERSION, dbName: AG.DB_NAME, openDatabase: AG.openDatabase, dbGet: AG.dbGet, dbPut: AG.dbPut,
  migrations: AG.MIGRATIONS, schemaTarget: AG.schemaTarget
};
})();
