self.AG_STAMPS=self.AG_STAMPS||{};self.AG_STAMPS['app.js']='0.6.2'; /* numéro écrit par verifications/sync_version.py : ne pas modifier à la main */
/* Agenda : écrans et comportements. Étape 2 : personnes et fiche. Aucune donnée dans ce fichier, aucune bibliothèque, aucune adresse internet.
   Les données passent par db.js (AG). Présentation, textes et règles repris de la maquette. */
(function () {
'use strict';

/* ========= petits outils ========= */
function $(s, r) { return (r || document).querySelector(s); }
function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
var APP_VERSION = self.APP_VERSION || '?';
var AG = self.AG, AGR = self.AGR, AGF = self.AGF;
/* la garde (garde.js) : journal des erreurs, contrôle des versions, message d'affichage ; si elle manque, on continue sans elle */
var AGG = self.AGG || { pending: [], sink: null, log: function () {}, caught: function () {}, problem: function () {}, unmasked: function () {}, displayed: function () {}, reload: function () { location.reload(); } };
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
var ctx = { sig: null, pid: null, person: null, mode: 'sem', jours: [], du: '', au: '', dates: {}, dm: { y: 0, m: 0 }, leaving: false, noted: 0, planned: 0, calPid: null, calY: 0, calM: 0, calFrom: 'fiche', calReveal: false };
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
  if (TABS.indexOf(id) >= 0) tab = id; else tab = id === 'fiche' ? 'personnes' : (id === 'calendrier' ? (ctx.calFrom === 'bilan' ? 'bilan' : 'personnes') : 'bilan');   /* sous-pages : l'onglet d'origine reste allumé */
  $$('.screen').forEach(function (s) { s.classList.toggle('on', s.id === 's-' + id); });
  $$('.nav button.t').forEach(function (b) {
    var on = b.dataset.t === tab; b.classList.toggle('on', on);
    if (on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  if (id === 'reglages') { refreshReglages(); refreshLog(); }
  if (id === 'sauvegarde') renderSave();
  if (prev === 'sauvegarde' && id !== 'sauvegarde') bkReset();
  if (id === 'personnes') renderPers();
  if (id === 'aujourdhui') { if (prev !== 'aujourdhui') openKey = null; renderAuj(); }
  if (prev === 'bilan' && id !== 'bilan') bil.reveal = false;          /* les montants se recachent en quittant le Bilan */
  if (id === 'bilan') renderBilan();
  if (id === 'essence') renderEssence();
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
  if (cur === 'calendrier') { if (ctx.calFrom === 'bilan') go('bilan'); else openFiche(ctx.calPid); return; }      /* retour là d'où l'on vient */
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
  if (kind === 'restore' || kind === 'undorestore') {                  /* sauvegarde : pas de fiche concernée */
    confirmCtx = { kind: kind, pid: null, target: null };
    $('#confirm-title').textContent = kind === 'restore' ? 'Restaurer cette sauvegarde ?' : 'Annuler la restauration ?';
    $('#confirm-text').textContent = kind === 'restore' ? 'Cela remplace tout ce qui est sur ce téléphone. Une copie de sécurité est gardée ' + BK_SAFETY_DAYS + ' jours : vous pourrez annuler la restauration.' : 'Les données d’avant la restauration reviennent. Ce qui a été noté depuis sera perdu.';
    $('#confirm-ok').textContent = kind === 'restore' ? 'Remplacer tout' : 'Annuler la restauration';
    $('#confirm-cancel').textContent = 'Garder tel quel';
    $('#confirm').classList.add('on'); return;
  }
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
  if (cc.kind === 'restore') { bkDoRestore(); return; }
  if (cc.kind === 'undorestore') { bkDoUndo(); return; }
  if (cc.kind === 'fuel') { fuelDelete(cc.id); return; }
  if (cc.kind === 'leave' && cc.target && cc.target.fuel) { if (cc.target.fuel === 'back') fuelBack(); else sheetClose(); return; }
  if (cc.kind === 'leave') { ctx.leaving = true; if (cc.target && cc.target.cal) openCalendar(cc.target.cal, 'fiche'); else if (cc.target) go(cc.target); else go('personnes'); ctx.leaving = false; return; }
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
function sheetClose() { dsh = null; fsh = null; $('#daysheet').classList.remove('on'); }
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
function openCalendar(pid, from, y, m) {
  var t = today(); ctx.calPid = pid; ctx.calFrom = from || 'fiche'; ctx.calReveal = false;
  ctx.calY = y == null ? t.getFullYear() : y; ctx.calM = m == null ? t.getMonth() : m;
  history.pushState({ app: 1 }, ''); renderCal(); go('calendrier'); $('#s-calendrier .content').scrollTop = 0;
}
/* résumé du mois affiché : mêmes règles que « Totaux » (seulement les courses faites, jamais un 0 inventé, montant masqué tant qu'on ne touche pas) */
function calSummaryHTML(p, y, m) {
  var pre = y + '-' + pad(m + 1) + '-', t = AGR.totals([p], rides.filter(function (r) { return r.person_id === p.id && r.date.indexOf(pre) === 0; })).total;
  var eur = ctx.calReveal ? totalTxt(t.cents, t.noPrice, t.count, fmtEuros) : '•••• €';
  var kmv = totalTxt(t.meters, t.noKm, t.count, function (v) { return fmtKm2(v) + ' km'; }), notes = [];
  if (t.noPrice > 0) notes.push('+ ' + coursesSans(t.noPrice, 'prix') + ' (total partiel)');
  if (t.noKm > 0) notes.push('+ ' + coursesSans(t.noKm, 'km') + ' (total partiel)');
  return '<div class="card calsum" id="cal-sum"><div class="calsum-g"><div><div class="v" id="cal-count">' + t.count + '</div><div class="l">' + (t.count > 1 ? 'courses faites' : 'course faite') + '</div></div>' +
    '<button class="calsum-b" data-a="calreveal" aria-label="Afficher ou masquer le montant"><div class="v" id="cal-eur">' + esc(eur) + '</div><div class="l">' + (ctx.calReveal ? 'toucher pour masquer' : 'toucher pour afficher') + '</div></button>' +
    '<div><div class="v" id="cal-km">' + esc(kmv) + '</div><div class="l">km</div></div></div>' +
    (notes.length ? '<p class="note" id="cal-notes">' + esc(notes.join(' · ')) + '</p>' : '') + '</div>';
}
function renderCal() {
  var p = personById(ctx.calPid); if (!p) return;
  var y = ctx.calY, m = ctx.calM, first = new Date(y, m, 1), off = wd(first) - 1, L = ['L', 'M', 'M', 'J', 'V', 'S', 'D'], n = new Date(y, m + 1, 0).getDate(), T = todayISO();
  var cnt = { t: 0, p: 0, a: 0, b: 0 }, cells = '';
  for (var i = 0; i < off; i++) cells += '<div class="blank"></div>';
  for (var d = 1; d <= n; d++) {
    var is = y + '-' + pad(m + 1) + '-' + pad(d), v = AGR.state(p, rides, is, T);
    if (v === 't') cnt.t++; else if (v === 'p') cnt.p++; else if (v === 'a') cnt.a++; else if (v === 'n') cnt.b++;     /* « sans note » : seulement un jour PASSÉ prévu (ou avec une course) où rien n'a été noté ; jamais un jour sans course */
    cells += '<button class="cell ' + v + (is === T ? ' today' : '') + '" data-a="calday" data-iso="' + is + '" aria-label="' + esc(cap(fmtDay.format(parseISO(is)))) + ' : ' + (v === 't' ? 'transportée' : (v === 'p' ? 'pas transportée' : (v === 'a' ? 'à faire' : (v === 'n' ? 'pas noté' : 'pas de course')))) + '"><span>' + d + '</span>' + (v === 't' ? I('check') : (v === 'p' ? I('x') : (v === 'a' ? I('ring') : ''))) + '</button>';
  }
  var h = '<header class="top"><div class="backrow"><button class="back" data-a="back">' + I('left') + 'Retour</button>' + tools() + '</div><h1 style="margin-top:6px">Calendrier et courses</h1><div class="sub">' + esc(fullName(p)) + '</div>' +
    '<div class="monthnav"><button class="chev" data-a="month" data-d="-1" aria-label="Mois précédent">' + I('left') + '</button><div class="lbl">' + esc(cap(fmtMonth.format(first))) + '</div><button class="chev" data-a="month" data-d="1" aria-label="Mois suivant">' + I('right') + '</button></div></header>' +
    '<div class="content">' + calSummaryHTML(p, y, m) + '<div class="card" style="padding:4px"><div class="calgrid">' + L.map(function (l) { return '<div class="dow">' + l + '</div>'; }).join('') + cells + '</div></div>' +
    '<p class="summary" id="cal-summary">' + cnt.t + ' transportée, ' + cnt.p + ' pas transportée, ' + (cnt.a ? cnt.a + ' à faire, ' : '') + plural(cnt.b, 'jour', 'jours') + ' sans note</p>' +
    '<div class="legend"><span><i class="sw t">' + I('check') + '</i>Transportée</span><span><i class="sw p">' + I('x') + '</i>Pas transportée</span><span><i class="sw a">' + I('ring') + '</i>À faire</span><span><i class="sw n"></i>Pas noté</span></div></div>';
  mount('s-calendrier', h);
}

/* ========= Journal de mise à jour (les 20 derniers évènements, gardés dans la base) ========= */
var evlog = AGG.pending.splice(0);      /* lignes déjà notées par la garde avant que ce fichier démarre */
AGG.sink = function (text) { return logEvt(text); };
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

/* ========= Bilan : « Totaux » et « Jour par jour » =========
   Le père ne reçoit RIEN de l'appli (ni bouton de copie, ni envoi, ni partage) : Pascal lit l'écran à voix haute.
   Le mois choisi est calculé à partir de l'INDEX des courses par date (on ne relit pas tout). */
var JJ = ['dim', 'lun', 'mar', 'mer', 'jeu', 'ven', 'sam'];
var bil = { view: 'tot', ref: new Date(today().getFullYear(), today().getMonth(), 1), reveal: false, ms: 0 }, bilTok = 0;
function fmtEuros(c) { return Math.floor(c / 100) + ',' + pad(c % 100) + ' €'; }
/* kilomètres d'un total : au plus 2 décimales (8400 m = « 8,4 »), plus facile à lire à voix haute */
function fmtKm2(m) { return (Math.floor(m / 10 + 0.5) / 100).toFixed(2).replace(/0+$/, '').replace(/\.$/, '').replace('.', ','); }
function coursesSans(n, what) { return n + ' ' + (n > 1 ? 'courses' : 'course') + ' sans ' + what; }
/* total d'une colonne : jamais un 0 inventé. Si TOUTES les courses faites ont cette valeur inconnue : « inconnu ». */
function totalTxt(sum, unknown, count, fmt) { return (count > 0 && unknown === count) ? 'inconnu' : fmt(sum); }
function bilanHeader() {
  return '<header class="top"><div class="hrow"><div><h1>Bilan</h1></div>' + tools() + '</div></header>';
}
function bilanControls() {
  var ref = bil.ref;
  return '<div class="toggle" role="group" aria-label="Vue du Bilan"><button data-a="bview" data-v="tot" class="' + (bil.view === 'tot' ? 'on' : '') + '" aria-pressed="' + (bil.view === 'tot') + '">Totaux</button><button data-a="bview" data-v="jj" class="' + (bil.view === 'jj' ? 'on' : '') + '" aria-pressed="' + (bil.view === 'jj') + '">Jour par jour</button></div>' +
    '<div class="period"><button class="chev" data-a="bmonth" data-d="-1" aria-label="Mois précédent">' + I('left') + '</button><div class="lbl" id="bil-month">' + esc(cap(fmtMonth.format(ref))) + '</div><button class="chev" data-a="bmonth" data-d="1" aria-label="Mois suivant">' + I('right') + '</button></div>';
}
function bilanTotauxHTML(rs) {
  var T = AGR.totals(people, rs), t = T.total, h;
  var eur = bil.reveal ? totalTxt(t.cents, t.noPrice, t.count, fmtEuros) : '•••• €';
  var eurNote = t.noPrice > 0 ? '+ ' + coursesSans(t.noPrice, 'prix') + ' (total partiel)' : 'total du mois';
  var kmv = totalTxt(t.meters, t.noKm, t.count, function (m) { return fmtKm2(m) + ' km'; });
  var kmNote = t.noKm > 0 ? '+ ' + coursesSans(t.noKm, 'km') + ' (total partiel)' : 'total du mois';
  h = '<div class="card tile"><div class="v" id="bil-count">' + t.count + '</div><div class="l">' + (t.count > 1 ? 'courses faites' : 'course faite') + '</div></div>' +
    '<button class="card tile" data-a="reveal" aria-label="Afficher ou masquer les montants"><div class="v" id="bil-eur">' + eur + '</div><div class="l" id="bil-eur-note">' + esc(eurNote) + '</div><div class="hint">' + I('eye') + (bil.reveal ? 'Toucher pour masquer' : 'Toucher pour afficher') + '</div></button>' +
    '<div class="card tile"><div class="v" id="bil-km">' + esc(kmv) + '</div><div class="l" id="bil-km-note">' + esc(kmNote) + '</div></div>' +
    '<h2>Par personne</h2><div class="card" style="padding-top:2px;padding-bottom:2px" id="bil-persons">';
  if (!T.persons.length) h += '<div class="empty">Rien de fait ce mois-ci.</div>';
  T.persons.forEach(function (q) {
    var pe = bil.reveal ? totalTxt(q.cents, q.noPrice, q.count, fmtEuros) : '•••• €', pk = totalTxt(q.meters, q.noKm, q.count, function (m) { return fmtKm2(m) + ' km'; });
    var notes = [];
    if (q.noPrice > 0) notes.push('+ ' + coursesSans(q.noPrice, 'prix'));
    if (q.noKm > 0) notes.push('+ ' + coursesSans(q.noKm, 'km'));
    h += '<button class="pp" data-a="bperson" data-pid="' + esc(q.p.id) + '" aria-label="Ouvrir le calendrier de ' + esc(fullName(q.p)) + '"><span class="head"><span class="name">' + nameHTML(q.p) + '<small>' + plural(q.count, 'course faite', 'courses faites') + '</small></span><span class="amount">' + esc(pe) + '</span>' + I('right') + '</span>' +
      '<span class="l3">' + esc(pk) + (notes.length ? ' · ' + esc(notes.join(' · ')) : '') + '</span></button>';
  });
  return h + '</div>';
}
function bilanJourHTML(rs, y, m) {
  var O = AGR.overview(people, rs, y, m, todayISO()), T = todayISO();
  var h = '<p class="jjsum" id="jj-sum">' + plural(O.noNote, 'jour', 'jours') + ' sans note</p><div class="card jjcard" style="padding-top:2px;padding-bottom:2px" id="jj-list">';
  if (!O.days.length) h += '<div class="empty">Rien à afficher ce mois-ci.</div>';
  O.days.forEach(function (d) {
    var dt = parseISO(d.iso);
    /* la date une seule fois, puis UNE LIGNE PAR PERSONNE : nom complet (même présentation que « Par personne »), « oui » / « non » / « pas noté » / « à faire » à droite */
    h += '<button class="jjrow" data-a="bday" data-iso="' + d.iso + '" aria-label="Ouvrir le ' + esc(fmtDay.format(dt)) + ' dans Aujourd’hui"><span class="jjday">' + JJ[dt.getDay()] + ' ' + dt.getDate() + '</span><span class="jjppl">' +
      d.items.map(function (it) {
        var st = it.status === 'done' ? 't' : (it.status === 'not_done' ? 'p' : 'n'), word = st === 't' ? 'oui' : (st === 'p' ? 'non' : (d.iso === T ? 'à faire' : 'pas noté'));
        return '<span class="jjp ' + st + '"><span class="name">' + nameHTML(it.p) + '</span><span class="jjr"><span class="jjw">' + word + '</span>' + (st === 't' ? I('check') : (st === 'p' ? I('x') : '<i class="jjring" aria-hidden="true"></i>')) + '</span></span>';
      }).join('') + '</span></button>';
  });
  return h + '</div>';
}
function renderBilan() {
  var tok = ++bilTok, t0 = performance.now(), y = bil.ref.getFullYear(), m = bil.ref.getMonth();
  var from = y + '-' + pad(m + 1) + '-01', to = y + '-' + pad(m + 1) + '-' + pad(new Date(y, m + 1, 0).getDate());
  (AG.db ? AG.ridesInRange(from, to) : Promise.resolve([])).then(function (rs) {
    if (tok !== bilTok || cur !== 'bilan') return;
    mount('s-bilan', bilanHeader() + '<div class="content">' + bilanControls() + (bil.view === 'tot' ? bilanTotauxHTML(rs) : bilanJourHTML(rs, y, m)) +
      exportReminderHTML() + '<div class="card" style="padding-top:2px;padding-bottom:2px"><button class="list-item" data-a="reglages"><span>Réglages</span>' + I('right') + '</button></div></div>');
    bil.ms = Math.round(performance.now() - t0);
  }, function () { /* base fermée : rien à calculer */ });
}

/* ========= Essence : les pleins d'essence (même présentation et mêmes règles que la maquette) =========
   Un plein = prix au litre, litres, montant : Pascal en remplit DEUX, le troisième se calcule (repère « calculé »).
   Valeurs rangées en entiers (millilitres, millièmes d'euro, centimes) ; vide = inconnu, jamais 0 ; « supprimer » = corbeille. */
var fuelM = { y: today().getFullYear(), m: today().getMonth() }, fsh = null, fuelList = [], fuelTok = 0;
var fmtShortD = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' });
function pleinsSans(n, what) { return n + ' ' + (n > 1 ? 'pleins' : 'plein') + ' sans ' + what; }
function fuelOfDay(is) { return fuelList.filter(function (x) { return x.date === is; }); }
function fuelDesc(x) {   /* « 38,5 L, 68,88 € » (valeurs inconnues dites comme telles) */
  return (x.liters_ml == null ? 'litres inconnus' : AGF.fmtL(x.liters_ml) + ' L') + ', ' + (x.total_cents == null ? 'montant inconnu' : fmtEuros(x.total_cents));
}
function renderEssence() {
  var tok = ++fuelTok, y = fuelM.y, m = fuelM.m, from = y + '-' + pad(m + 1) + '-01', to = y + '-' + pad(m + 1) + '-' + pad(new Date(y, m + 1, 0).getDate());
  (AG.db ? AG.fuelInRange(from, to) : Promise.resolve([])).then(function (list) {
    if (tok !== fuelTok || cur !== 'essence') return;
    fuelList = list.filter(function (x) { return !x.deleted_at; });
    mountEssence(y, m);
  }, function () { /* base fermée */ });
}
function mountEssence(y, m) {
  var first = new Date(y, m, 1), n = new Date(y, m + 1, 0).getDate(), off = wd(first) - 1, L = ['L', 'M', 'M', 'J', 'V', 'S', 'D'], T = todayISO(), days = {};
  fuelList.forEach(function (x) { days[x.date] = (days[x.date] || 0) + 1; });
  var t = AGF.totals(fuelList);
  var h = '<header class="top"><div class="hrow"><div><h1>Essence</h1><div class="sub">Pleins du mois</div></div>' + tools() + '</div>' +
    '<div class="monthnav"><button class="chev" data-a="emonth" data-d="-1" aria-label="Mois précédent">' + I('left') + '</button><div class="lbl" id="fu-month">' + esc(cap(fmtMonth.format(first))) + '</div><button class="chev" data-a="emonth" data-d="1" aria-label="Mois suivant">' + I('right') + '</button></div></header>' +
    '<div class="content"><div class="card" style="padding:4px"><div class="calgrid">' + L.map(function (l) { return '<div class="dow">' + l + '</div>'; }).join('');
  for (var i = 0; i < off; i++) h += '<div class="blank"></div>';
  for (var d = 1; d <= n; d++) {
    var is = y + '-' + pad(m + 1) + '-' + pad(d), c = days[is] || 0;
    h += '<button class="cell' + (c ? ' f' : '') + (is === T ? ' today' : '') + '" data-a="eday" data-iso="' + is + '" aria-label="' + esc(cap(fmtDay.format(parseISO(is)))) + ' : ' + (c ? plural(c, 'plein', 'pleins') : 'pas de plein') + '"><span>' + d + '</span>' + (c ? I('fuel') : '') + '</button>';
  }
  var lit = (t.count > 0 && t.noLiters === t.count) ? 'inconnu' : AGF.fmtLtot(t.ml), eur = (t.count > 0 && t.noAmount === t.count) ? 'inconnu' : fmtEuros(t.cents), notes = [];
  if (t.noLiters > 0) notes.push('+ ' + pleinsSans(t.noLiters, 'litres') + ' (total partiel)');
  if (t.noAmount > 0) notes.push('+ ' + pleinsSans(t.noAmount, 'montant') + ' (total partiel)');
  h += '</div></div><h2>Total du mois</h2><div class="card fuelsum" id="fu-total"><div><div class="v" id="fu-count">' + t.count + '</div><div class="l">' + (t.count > 1 ? 'pleins' : 'plein') + '</div></div>' +
    '<div><div class="v" id="fu-lit">' + esc(lit) + '</div><div class="l">litres</div></div><div><div class="v" id="fu-eur">' + esc(eur) + '</div><div class="l">montant</div></div></div>' +
    (notes.length ? '<p class="note" id="fu-notes">' + esc(notes.join(' · ')) + '</p>' : '') +
    '<h2>Pleins du mois</h2><div class="card" style="padding-top:2px;padding-bottom:2px" id="fu-list">';
  if (!fuelList.length) h += '<div class="empty">Aucun plein noté ce mois-ci.</div>';
  fuelList.slice().sort(function (a, b) { return a.date < b.date ? 1 : (a.date > b.date ? -1 : (a.created_at < b.created_at ? 1 : (a.created_at > b.created_at ? -1 : 0))); }).forEach(function (x) {
    var dd = parseISO(x.date);
    h += '<button class="fuelrow" data-a="eedit" data-id="' + esc(x.id) + '"><span class="d">' + esc(JJ[dd.getDay()] + ' ' + dd.getDate()) + '</span><span class="q">' + esc(x.liters_ml == null ? 'litres inconnus' : AGF.fmtL(x.liters_ml) + ' L') + '</span><span class="a">' + esc(x.total_cents == null ? 'montant inconnu' : fmtEuros(x.total_cents)) + '</span></button>';
  });
  h += '</div></div>';
  mount('s-essence', h);
}
/* panneau d'un jour (même feuille du bas que le calendrier d'une personne) */
function fuelSheetHTML() {
  var is = fsh.iso, title = cap(fmtDay.format(parseISO(is))), h;
  if (fsh.mode === 'list') {
    h = '<p class="t" id="ds-title">' + esc(title) + '</p>';
    fuelOfDay(is).forEach(function (x) {
      h += '<button class="fuelrow" data-a="eedit" data-id="' + esc(x.id) + '"><span class="q">' + esc(x.liters_ml == null ? 'litres inconnus' : AGF.fmtL(x.liters_ml) + ' L') + (x.price_milli == null ? '' : ' · ' + esc(AGF.fmtP(x.price_milli)) + ' €/L') + '</span><span class="a">' + esc(x.total_cents == null ? 'montant inconnu' : fmtEuros(x.total_cents)) + '</span></button>';
    });
    return h + '<button class="btn line full" data-a="eadd">Ajouter un plein</button><button class="btn line full" data-a="dsclose">Fermer</button>';
  }
  var fs = fsh.fs, ed = !!fsh.id, tag = function (k) { return '<span class="hab" id="fu-tag-' + k + '"' + (fs.calc === k ? '' : ' hidden') + '>calculé</span>'; };
  return '<p class="t" id="ds-title">' + (ed ? 'Modifier ce plein' : 'Ajouter un plein') + '</p><p class="note" style="padding:0">' + esc(title) + ' · remplis deux chiffres, le troisième se calcule</p>' +
    '<div class="field"><label for="fu-p">Prix au litre (€/L)' + tag('p') + '</label><input class="input" id="fu-p" inputmode="decimal" value="' + esc(fs.p) + '" autocomplete="off"></div>' +
    '<div class="field"><label for="fu-l">Litres' + tag('l') + '</label><input class="input" id="fu-l" inputmode="decimal" value="' + esc(fs.l) + '" autocomplete="off"></div>' +
    '<div class="field"><label for="fu-m">Montant (€)' + tag('m') + '</label><input class="input" id="fu-m" inputmode="decimal" value="' + esc(fs.m) + '" autocomplete="off"></div>' +
    '<div class="warnbox" id="fu-err" role="alert" hidden></div>' +
    '<button class="btn strong full" data-a="esave">Enregistrer</button>' +
    (ed ? '<button class="btn line full" data-a="edelask">Supprimer ce plein</button>' : '') +
    '<button class="btn line full" data-a="eback">Annuler</button>';
}
function renderFuelSheet() { $('#ds-panel').innerHTML = fuelSheetHTML(); }
function openFuelSheet(is) {
  if (is > todayISO()) { toast('Ce jour n’est pas encore arrivé'); return; }
  dsh = null; fsh = { iso: is, mode: 'list', id: null, fs: { p: '', l: '', m: '', calc: null }, sig: '' };
  if (!fuelOfDay(is).length) { fsh.mode = 'form'; fsh.sig = JSON.stringify(['', '', '']); }
  renderFuelSheet(); $('#daysheet').classList.add('on');
}
function fuelForm(id) {
  var x = null; fuelList.forEach(function (o) { if (o.id === id) x = o; });
  fsh.mode = 'form'; fsh.id = id || null; fsh.fs = x ? AGF.toForm(x) : { p: '', l: '', m: '', calc: null };
  fsh.sig = JSON.stringify([fsh.fs.p, fsh.fs.l, fsh.fs.m]); renderFuelSheet();
}
/* le formulaire a-t-il changé depuis son ouverture ? (pour « Quitter sans enregistrer ? ») */
function fuelDirty() { return !!(fsh && fsh.mode === 'form' && JSON.stringify([fsh.fs.p, fsh.fs.l, fsh.fs.m]) !== fsh.sig); }
function fuelBack() {
  if (!fsh) return;
  if (fuelOfDay(fsh.iso).length) { fsh.mode = 'list'; fsh.id = null; renderFuelSheet(); } else sheetClose();
}
function fuelRecalc(changed) {   /* après une frappe : si deux chiffres sont remplis par Pascal, le troisième se calcule */
  var fs = fsh.fs, F = ['p', 'l', 'm'], users, third;
  if (fs.calc === changed) fs.calc = null;                                   /* Pascal reprend la main sur ce champ */
  users = F.filter(function (f) { return fs[f] !== '' && f !== fs.calc; });
  if (fs.calc && users.length !== 2) { fs[fs.calc] = ''; fs.calc = null; users = F.filter(function (f) { return fs[f] !== ''; }); }
  if (users.length === 2) {
    third = F.filter(function (f) { return users.indexOf(f) < 0; })[0];
    var v = AGF.calc(fs, third); fs[third] = v; fs.calc = v ? third : null;
  }
  F.forEach(function (f) {
    var i = document.getElementById('fu-' + f), t = document.getElementById('fu-tag-' + f);
    if (i && (f !== changed || fs.calc === f)) i.value = fs[f];
    if (t) t.hidden = fs.calc !== f;
  });
}
function fuelErr(msg, focusId) { var e = document.getElementById('fu-err'); e.textContent = msg; e.hidden = false; if (focusId) { var i = document.getElementById(focusId); i.setAttribute('aria-invalid', 'true'); i.focus(); } }
function fuelSave() {
  var fs = fsh.fs, F = [['p', 'fu-p', 3, 'Prix au litre', '1,789'], ['l', 'fu-l', 2, 'Litres', '38,5'], ['m', 'fu-m', 2, 'Montant', '68,87']], out = {}, bad = false;
  document.getElementById('fu-err').hidden = true; F.forEach(function (x) { document.getElementById(x[1]).removeAttribute('aria-invalid'); });
  F.forEach(function (x) {
    if (bad) return; var r = AGF.parse(fs[x[0]], x[2]);
    if (r.err === 'zero') { fuelErr('Un zéro n’est pas possible : laisse la case vide si tu ne sais pas.', x[1]); bad = true; }
    else if (r.err) { fuelErr(x[3] + ' : écris un nombre comme ' + x[4] + ', ou laisse vide.', x[1]); bad = true; }
    else out[x[0]] = r.v;
  });
  if (bad) return;
  var filled = F.filter(function (x) { return out[x[0]] !== ''; }).length;
  if (filled < 2) { fuelErr('Remplis deux des trois chiffres : le troisième se calcule.'); return; }
  var nl = parseFloat(out.l.replace(',', '.')), np = parseFloat(out.p.replace(',', '.')), nm = parseFloat(out.m.replace(',', '.'));
  if (filled === 3 && Math.abs(Math.round((nl * np + 1e-9) * 100) / 100 - nm) > 0.01 + 1e-9) { fuelErr('Les trois chiffres ne correspondent pas. Garde-en deux.'); return; }   /* rien n'est enregistré */
  var rec = AGF.toRecord(out), now = nowIso(), o = null;
  fuelList.forEach(function (x) { if (x.id === fsh.id) o = x; });
  o = o ? Object.assign({}, o) : { id: AG.uuid(), date: fsh.iso, created_at: now, deleted_at: null };
  Object.assign(o, rec, { calc: AGF.calcName(fs.calc), updated_at: now });
  var add = !fsh.id;
  AG.putFuel(o).then(function () { sheetClose(); renderEssence(); toast(add ? 'Plein ajouté' : 'Plein modifié'); }, function () { toast('Enregistrement impossible : réessaie'); });
}
function openConfirmFuel(id) {
  var o = null; fuelList.forEach(function (x) { if (x.id === id) o = x; }); if (!o) return;
  confirmCtx = { kind: 'fuel', id: id };
  $('#confirm-title').textContent = 'Supprimer ce plein ?'; $('#confirm-text').textContent = 'Plein du ' + fmtShortD.format(parseISO(o.date)) + ' : ' + fuelDesc(o) + '.';
  $('#confirm-ok').textContent = 'Supprimer'; $('#confirm-cancel').textContent = 'Annuler'; $('#confirm').classList.add('on');
}
/* « supprimer » = corbeille (jamais effacé pour de bon) ; « Annuler » pendant 5 secondes */
function fuelDelete(id) {
  var o = null; fuelList.forEach(function (x) { if (x.id === id) o = x; }); if (!o) return;
  var gone = Object.assign({}, o, { deleted_at: nowIso(), updated_at: nowIso() });
  AG.putFuel(gone).then(function () {
    sheetClose(); renderEssence();
    toast('Plein supprimé', function () { AG.putFuel(Object.assign({}, gone, { deleted_at: null, updated_at: nowIso() })).then(function () { if (cur === 'essence') renderEssence(); }); });
  }, function () { toast('Suppression impossible : réessaie'); });
}

/* ========= Sauvegarde : export chiffré, vérification, restauration =========
   Les données restent NON chiffrées sur le téléphone (la protection est le verrou d'Android) ; seul le FICHIER est chiffré (sauvegarde.js).
   La phrase de 10 mots n'existe qu'en mémoire, le temps de l'afficher et de la confirmer, puis elle est effacée. Au masquage de l'écran, tout ce qui est lisible
   (phrase, résumés, noms de fichiers) est effacé de la page et ne revient pas : on recommence l'étape. */
var BK_SAFETY_DAYS = 7, BK_REMIND_DAYS = 7;
var lastExport = null;            /* { at, date } du dernier export (ou du fichier restauré), ou null */
var BK_PHRASE_MS = 600000;      /* la phrase affichée reste en mémoire 10 minutes au plus */
var bk = { reveal: false, step: 'home', phrase: null, until: 0, renew: false, hasKey: false, ask: null, text: null, header: null, mode: null, opened: null, msg: '', msgKind: '', safety: null, tok: 0 };
var fmtFull = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
var fmtShort = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long' });

/* nombre de jours CALENDAIRES depuis le dernier export (le changement d'heure ne décale rien) */
function daysSinceExport() {
  if (!lastExport) return null;
  return Math.max(0, Math.round((today().getTime() - parseISO(lastExport.date).getTime()) / 86400000));
}
function lastExportText() {
  var n = daysSinceExport();
  if (n == null) return 'jamais';
  return n === 0 ? 'aujourd’hui' : (n === 1 ? 'il y a 1 jour' : 'il y a ' + n + ' jours');
}
function hasData() { return people.length > 0 || rides.length > 0; }
/* ligne discrète du Bilan : jamais bloquante */
function exportReminderHTML() {
  var n = daysSinceExport();
  if (n == null) return hasData() ? '<p class="note" id="bil-export">Pas encore d’export</p>' : '';
  return n > BK_REMIND_DAYS ? '<p class="note" id="bil-export">Pas d’export depuis ' + n + ' jours</p>' : '';
}
function bkInit() {
  return Promise.all([AG.getMeta('last_export'), AG.getSafety(), AG.getMeta('backup_key')]).then(function (r) {
    lastExport = r[0] || null; bk.safety = r[1] || null; bk.hasKey = !!r[2];
    if (bk.safety && Date.parse(bk.safety.expires_at) < Date.now()) { bk.safety = null; return AG.deleteSafety(); }      /* au-delà de 7 jours : la copie de sécurité disparaît */
  });
}
function bkReset(msg, kind) {
  bk.tok++; bk.reveal = false; bk.step = 'home'; bk.phrase = null; bk.until = 0; bk.renew = false; bk.ask = null; bk.text = null; bk.header = null; bk.mode = null; bk.opened = null; bk.msg = msg || ''; bk.msgKind = kind || '';
}
function bkErr(er) {
  var c = er && er.code, m = {
    notbackup: 'Ce fichier n’est pas une sauvegarde Agenda.',
    damaged: 'Le fichier est abîmé ou incomplet : il ne peut pas être lu. Rien n’a été modifié.',
    newformat: 'Cette sauvegarde vient d’une version plus récente d’Agenda. Mettez l’appli à jour, puis réessayez. Rien n’a été modifié.',
    newschema: 'Cette sauvegarde a une structure de données plus récente que cette appli. Mettez l’appli à jour, puis réessayez. Rien n’a été modifié.',
    phrase: 'Les 10 mots sont valides, mais ce n’est pas la phrase de ce fichier. Elle vient peut-être d’un autre essai d’export.',
    words: 'J’ai lu ' + plural(er && er.extra || 0, 'mot', 'mots') + ' : il en faut exactement 10.',
    unknownword: 'Le mot n° ' + (er && er.extra) + ' ne figure pas dans la liste. Vérifiez son orthographe.'
  };
  return m[c] || 'Impossible de lire cette sauvegarde. Rien n’a été modifié.';
}
function countsText(c) { return plural(c.persons, 'personne', 'personnes') + ', ' + plural(c.rides, 'course', 'courses') + ', ' + plural(c.fuel, 'plein', 'pleins'); }
function bkHead() {
  return '<header class="top"><div class="backrow"><button class="back" data-a="back">' + I('left') + 'Retour</button>' + tools() + '</div><h1 style="margin-top:6px">Sauvegarde</h1></header>';
}
function bkBtn(cls, a, label) { return '<button class="btn ' + cls + ' full" data-a="' + a + '">' + label + '</button>'; }
function bkBox() { return bk.msg ? '<div class="warnbox" id="bk-msg" role="status">' + esc(bk.msg) + '</div>' : ''; }
function bkPhraseField() {
  return '<div class="field"><label for="bk-phrase">Phrase de récupération (10 mots)</label><input class="input secret' + (bk.reveal ? ' show' : '') + '" id="bk-phrase" type="text" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" enterkeyhint="done"></div>' + bkRevealBtn();
}
/* « Afficher ce que je tape » : masqué par défaut (points), s'efface au masquage de l'écran ; basculer ne vide jamais le champ */
function bkRevealBtn() {
  return '<button class="btn line full" data-a="bk-reveal" id="bk-reveal" aria-pressed="' + (bk.reveal ? 'true' : 'false') + '">' + I(bk.reveal ? 'eyeoff' : 'eye') + '<span>' + (bk.reveal ? 'Cacher ce que je tape' : 'Afficher ce que je tape') + '</span></button>';
}
function bkToggleReveal() {
  bk.reveal = !bk.reveal;
  document.querySelectorAll('#s-sauvegarde .secret').forEach(function (e) { e.classList.toggle('show', bk.reveal); });
  var b = $('#bk-reveal'); if (b) { b.setAttribute('aria-pressed', bk.reveal ? 'true' : 'false'); b.innerHTML = I(bk.reveal ? 'eyeoff' : 'eye') + '<span>' + (bk.reveal ? 'Cacher ce que je tape' : 'Afficher ce que je tape') + '</span>'; }
}
function bkBody() {
  var s = bk.step, h = '';
  if (s === 'home') {
    h = bkBox() +
      '<div class="card" style="padding-top:2px;padding-bottom:2px"><div class="list-item"><span>Dernier export</span><span class="val" id="bk-last">' + esc(lastExportText()) + '</span></div></div>';
    if (bk.safety) {
      h += '<div class="card" id="bk-safety"><p class="note" style="padding:0">Restauration du ' + esc(fmtShort.format(new Date(bk.safety.at))) + ' : vous pouvez l’annuler jusqu’au ' + esc(fmtShort.format(new Date(bk.safety.expires_at))) + '. Une copie de ce qu’il y avait avant est gardée sur ce téléphone.</p>' +
        bkBtn('strong', 'bk-undo', 'Annuler la restauration') + bkBtn('line', 'bk-keep', 'Garder définitivement') + '</div>';
    }
    if (!bk.hasKey) h += '<p class="note" id="bk-paper">Avant de commencer : prenez un papier et un stylo. Vous avez 10 minutes.</p>';
    h += bkBtn('main', 'bk-export', 'Exporter vers mon PC') + bkBtn('soft', 'bk-verify', 'Vérifier une sauvegarde') + bkBtn('soft', 'bk-restore', 'Restaurer depuis une sauvegarde') + (bk.hasKey ? bkBtn('line', 'bk-renew', 'Créer une nouvelle phrase') : '') +
      '<p class="note">Le fichier de sauvegarde est chiffré : seul quelqu’un qui a la phrase de récupération peut l’ouvrir. Il est rangé dans le dossier Téléchargements du téléphone. Copiez-le sur le PC par câble, puis effacez-le du téléphone.</p>';
  } else if (s === 'explain') {
    h = bkBox() + '<h2>' + (bk.renew ? 'Nouvelle phrase de récupération' : 'Votre phrase de récupération') + '</h2>';
    if (bk.renew) {
      h += '<div class="card"><p class="note" style="padding:0">Agenda va créer une nouvelle phrase de 10 mots.</p>' +
        '<p class="note" style="padding:0;margin-top:8px">L’ancienne phrase ne servira plus qu’à ouvrir les fichiers déjà exportés avec elle.</p>' +
        '<p class="note" style="padding:0;margin-top:8px">Les prochains exports utiliseront la nouvelle phrase.</p>' +
        '<p class="note" style="padding:0;margin-top:8px">Il vaut mieux faire un export tout de suite après.</p>' +
        '<p class="note" style="padding:0;margin-top:8px"><b>Elle ne s’affiche qu’une seule fois.</b> Écrivez-la sur papier, dans l’ordre.</p></div>';
    } else {
      h += '<div class="card"><p class="note" style="padding:0">Pour protéger vos sauvegardes, Agenda va créer une phrase de 10 mots.</p>' +
        '<p class="note" style="padding:0;margin-top:8px">Elle sert à ouvrir un fichier de sauvegarde, sur le PC ou sur un autre téléphone.</p>' +
        '<p class="note" style="padding:0;margin-top:8px"><b>Elle ne s’affiche qu’une seule fois.</b> Écrivez-la sur papier, dans l’ordre. Ne la photographiez pas, ne l’enregistrez pas dans le téléphone.</p>' +
        '<p class="note" style="padding:0;margin-top:8px">Si vous perdez la phrase ET le téléphone, les sauvegardes ne pourront plus être ouvertes.</p></div>';
    }
    h += '<p class="note" id="bk-paper"><b>Avant de commencer : prenez un papier et un stylo. Vous avez 10 minutes.</b></p>' +
      bkBtn('main', 'bk-show', 'Afficher la phrase') + bkBtn('line', 'bk-cancel', 'Annuler');
  } else if (s === 'phrase') {
    h = bkBox() + '<h2>Votre phrase</h2><div class="card"><ol class="words" id="bk-words">' + bk.phrase.map(function (w, i) { return '<li><span class="n">' + (i + 1) + '</span><span class="w">' + esc(w) + '</span></li>'; }).join('') + '</ol></div>' +
      '<p class="note">Écrivez les 10 mots sur papier, dans l’ordre, sans vous presser. Si vous changez d’application puis revenez, la même phrase est là. L’œil l’efface pour de bon.</p>' + bkCountHTML() +
      bkBtn('main', 'bk-written', 'J’ai tout écrit') + bkBtn('line', 'bk-cancel', 'Annuler');
  } else if (s === 'confirm') {
    h = '<h2>Vérification</h2><p class="note">Recopiez depuis votre papier les deux mots demandés.</p><div class="card">' +
      '<div class="field"><label for="bk-w1">Mot n° ' + bk.ask[0] + '</label><input class="input secret' + (bk.reveal ? ' show' : '') + '" id="bk-w1" type="text" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false"></div>' +
      '<div class="field"><label for="bk-w2">Mot n° ' + bk.ask[1] + '</label><input class="input secret' + (bk.reveal ? ' show' : '') + '" id="bk-w2" type="text" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false"></div>' + bkRevealBtn() + '</div>' +
      bkCountHTML() + bkBtn('main', 'bk-confirm', 'Continuer') + bkBtn('line', 'bk-review', 'Revoir la phrase');
  } else if (s === 'renewed') {
    h = bkBox() + bkBtn('main', 'bk-export', 'Exporter maintenant') + bkBtn('line', 'bk-cancel', 'Plus tard');
  } else if (s === 'busy') {
    h = '<div class="card empty" role="status" id="bk-busy">Un instant…</div>';
  } else if (s === 'pick') {
    h = bkBox() + '<h2>' + (bk.mode === 'restore' ? 'Restaurer une sauvegarde' : 'Vérifier une sauvegarde') + '</h2><div class="card"><p class="note" style="padding:0">' +
      (bk.mode === 'restore' ? 'Choisissez le fichier .agenda. Vous aurez ensuite besoin de la phrase de récupération.' : 'Choisissez le fichier .agenda. Rien ne sera modifié sur ce téléphone.') + '</p></div>' +
      '<label class="btn main full" for="bk-file" role="button" tabindex="0">Choisir le fichier</label><input type="file" id="bk-file" class="vh" tabindex="-1">' + bkBtn('line', 'bk-cancel', 'Annuler');
  } else if (s === 'phrasein') {
    h = bkBox() + '<h2>' + (bk.mode === 'restore' ? 'Restaurer une sauvegarde' : 'Vérifier une sauvegarde') + '</h2><p class="note">Sauvegarde du ' + esc(fmtFull.format(new Date(bk.header.exported_at))) + '. Tapez la phrase de récupération.</p><div class="card">' + bkPhraseField() + '</div>' +
      bkBtn('main', 'bk-open', bk.mode === 'restore' ? 'Continuer' : 'Vérifier') + bkBtn('line', 'bk-cancel', 'Annuler');
  } else if (s === 'result') {
    var o = bk.opened;
    h = '<div class="warnbox" id="bk-valid" role="status">Sauvegarde valide : export du ' + esc(fmtFull.format(new Date(o.header.exported_at))) + ', ' + esc(countsText(o.counts)) + '</div>' +
      '<p class="note">Rien n’a été modifié sur ce téléphone.</p>' + bkBtn('main', 'bk-cancel', 'Terminé');
  } else if (s === 'summary') {
    var f = bk.opened;
    h = '<h2>Restaurer cette sauvegarde</h2><div class="card" style="padding-top:2px;padding-bottom:2px">' +
      '<div class="list-item"><span>Dans le fichier<small>export du ' + esc(fmtFull.format(new Date(f.header.exported_at))) + '</small></span><span class="val" id="bk-sum-file">' + esc(countsText(f.counts)) + '</span></div>' +
      '<div class="list-item"><span>Sur ce téléphone<small>maintenant</small></span><span class="val" id="bk-sum-now">' + esc(countsText(bk.now)) + '</span></div></div>' +
      '<div class="warnbox">Cela remplace tout ce qui est sur ce téléphone. Une copie de sécurité est gardée ' + BK_SAFETY_DAYS + ' jours : vous pourrez annuler la restauration.</div>' +
      bkBtn('strong', 'bk-replace', 'Restaurer') + bkBtn('line', 'bk-cancel', 'Annuler');
  }
  return h;
}
function renderSave() {
  if (veilOn || cur !== 'sauvegarde') return;
  mount('s-sauvegarde', bkHead() + '<div class="content">' + bkBody() + '</div>');
  var f = $('#bk-phrase') || $('#bk-w1'); if (f && bk.step !== 'busy') f.focus({ preventScroll: true });
}
function bkOpenScreen() { history.pushState({ app: 1 }, ''); bkReset(); go('sauvegarde'); }
function bkBack() {
  if (bk.step !== 'home') { bkReset(); renderSave(); } else { bkReset(); go('reglages'); }
}
/* masquage : on efface la page. La phrase affichée ne revient JAMAIS ; un résultat déchiffré non plus. Un fichier choisi (chiffré) ou l'étape de saisie sont gardés. */
function bkOnMask(eye) {
  var s = bk.step; bk.reveal = false;
  if (!eye && bkPhraseLive() && bk.until - Date.now() > 0) {      /* masquage automatique ou retour d'une autre appli : la phrase reste en mémoire, l'écran est vidé */
    bk.msg = ''; if (cur === 'sauvegarde') $('#s-sauvegarde').innerHTML = ''; return;
  }
  if (confirmCtx && (confirmCtx.kind === 'restore' || confirmCtx.kind === 'undorestore')) closeConfirm();
  if (s === 'explain' || s === 'phrase' || s === 'confirm') {
    bkReset('Le masquage a interrompu la création de la phrase. Rien n’a été enregistré : recommencez.', 'info');
  } else if (s === 'result' || s === 'summary') {
    bkReset('Le masquage a fermé l’affichage de la sauvegarde. Rien n’a été modifié.', 'info');
  } else { bk.msg = ''; }                      /* saisie, choix du fichier, accueil : on garde l'étape (le champ de la phrase est vidé avec la page) */
  bk.phrase = null; bk.until = 0;
  if (cur === 'sauvegarde') $('#s-sauvegarde').innerHTML = '';
}
/* La phrase affichée : en mémoire de la page seulement, 10 minutes au plus (comparaison d'horodatages). */
function bkPhraseLive() { return !!bk.phrase && (bk.step === 'phrase' || bk.step === 'confirm'); }
function bkMinLeft() { return Math.max(1, Math.ceil((bk.until - Date.now()) / 60000)); }
function bkCountText() { return 'Cette phrase reste affichée encore ' + bkMinLeft() + ' min'; }
function bkCountHTML() { return '<p class="note" id="bk-count">' + bkCountText() + '</p>'; }
/* appelé chaque seconde (même écran masqué) : au-delà de 10 minutes (ou si l'horloge a reculé), la phrase est effacée */
function bkExpire() {
  if (!bkPhraseLive()) return;
  var d = bk.until - Date.now();
  if (d > 0 && d <= BK_PHRASE_MS + 2000) {
    var c = $('#bk-count'); if (c && !veilOn) { var tx = bkCountText(); if (c.textContent !== tx) c.textContent = tx; }
    return;
  }
  var renew = bk.renew;
  bkReset('Pour votre sécurité, la phrase a été effacée. Une nouvelle phrase va être créée.', 'info');
  bk.step = 'explain'; bk.renew = renew; lastTouch = Date.now();
  renderSave();
}
function bkPickAsk() {
  var a = new Uint8Array(2); crypto.getRandomValues(a);
  var i = a[0] % 10, j = (i + 1 + (a[1] % 9)) % 10;
  return [Math.min(i, j) + 1, Math.max(i, j) + 1];
}
function bkDownload(name, text) {
  var url = URL.createObjectURL(new Blob([text], { type: 'application/octet-stream' })), a = document.createElement('a');
  a.href = url; a.download = name; a.style.display = 'none'; document.body.appendChild(a); a.click();
  setTimeout(function () { document.body.removeChild(a); URL.revokeObjectURL(url); }, 4000);
}
function bkStart(label) { bk.step = 'busy'; bk.msg = ''; renderSave(); return ++bk.tok; }
/* produit le fichier avec le trousseau du téléphone ; « Dernier export » n'est mis à jour qu'APRÈS avoir lancé le téléchargement */
function bkRunExport(bundle) {
  var now = nowDate();
  return AG.snapshotAll().then(function (snap) {
    return AGB.buildFile(bundle, snap, AG.schemaTarget, APP_VERSION, now);
  }).then(function (text) {
    var name = AGB.fileName(now); bkDownload(name, text);
    lastExport = { at: now.toISOString(), date: iso(now) };
    return AG.putMeta('last_export', lastExport).then(function () { return name; });
  });
}
function bkExportClick() {
  AG.getMeta('backup_key').then(function (bundle) {
    if (!bundle) { bk.step = 'explain'; bk.msg = ''; renderSave(); return; }       /* premier export : la phrase d'abord */
    var t = bkStart();
    return bkRunExport(bundle).then(function (name) {
      if (t !== bk.tok) return;
      bkReset('Fichier « ' + name + ' » envoyé dans Téléchargements. Copiez-le sur le PC par câble, puis effacez-le du téléphone.', 'ok'); renderSave();
    });
  }).catch(function () { bkReset('L’export a échoué : réessayez. Rien n’a été modifié.', 'err'); renderSave(); });
}
function bkConfirm() {
  var w1 = $('#bk-w1').value, w2 = $('#bk-w2').value, ph = bk.phrase;
  if (!ph) { bkReset(); renderSave(); return; }
  if (AGB.normWord(w1) !== AGB.normWord(ph[bk.ask[0] - 1]) || AGB.normWord(w2) !== AGB.normWord(ph[bk.ask[1] - 1]) || !AGB.normWord(w1)) {
    bk.step = 'phrase'; bk.ask = bkPickAsk(); bk.msg = 'Ce n’est pas bon. Regardez bien la phrase, recopiez-la sur papier, puis confirmez à nouveau. Rien n’a été créé.'; bk.msgKind = 'err'; renderSave(); return;
  }
  var t = bkStart(), phrase = ph.join(' ');
  var renew = bk.renew;
  bk.phrase = null; bk.until = 0;                                                /* confirmée : elle n'a plus rien à faire dans la page */
  AGB.createKeyBundle(phrase).then(function (bundle) {
    return AG.putMeta('backup_key', bundle).then(function () {
      bk.hasKey = true;
      if (renew) { logEvt('Phrase de récupération renouvelée'); return null; }
      return bkRunExport(bundle);
    });
  }).then(function (name) {
    if (renew) { bkReset('Nouvelle phrase confirmée. Gardez le nouveau papier en lieu sûr : l’ancien ne sert plus que pour les anciens fichiers. Faites un export maintenant.', 'ok'); bk.step = 'renewed'; renderSave(); return; }
    bkReset('Phrase confirmée. Fichier « ' + name + ' » envoyé dans Téléchargements. Copiez-le sur le PC par câble, puis effacez-le du téléphone. Gardez le papier en lieu sûr.', 'ok'); renderSave();
  }, function () { bkReset('La création a échoué : réessayez. Rien n’a été modifié.', 'err'); renderSave(); });
}
function bkFilePicked(file) {
  if (!file) return;
  var t = bk.tok;
  file.text().then(function (text) {
    if (t !== bk.tok) return;
    var h; try { h = AGB.parseHeader(text, AG.schemaTarget); } catch (er) { bk.msg = bkErr(er); bk.msgKind = 'err'; renderSave(); return; }
    bk.text = text; bk.header = h; bk.step = 'phrasein'; bk.msg = ''; renderSave();
  }, function () { bk.msg = bkErr(null); bk.msgKind = 'err'; renderSave(); });
}
function bkOpen() {
  var ph = $('#bk-phrase').value, t = bk.tok;
  var chk = AGB.checkPhrase(ph);
  if (!chk.ok) { bk.msg = bkErr(chk.count !== AGB.PHRASE_WORDS ? { code: 'words', extra: chk.count } : { code: 'unknownword', extra: chk.unknown }); bk.msgKind = 'err'; renderSave(); return; }
  var text = bk.text; bkStart();
  AGB.openFile(text, ph, AG.schemaTarget).then(function (o) {
    if (bk.tok !== t + 1) return;
    if (bk.mode === 'verify') { bk.opened = o; bk.step = 'result'; renderSave(); return; }
    return AG.snapshotAll().then(function (s) {
      if (bk.tok !== t + 1) return;
      bk.opened = o; bk.now = AGB.countsOf(s); bk.step = 'summary'; renderSave();
    });
  }, function (er) {
    if (bk.tok !== t + 1) return;
    bk.step = 'phrasein'; bk.text = text; bk.msg = bkErr(er); bk.msgKind = 'err';
    if (er && er.code !== 'phrase' && er.code !== 'words' && er.code !== 'unknownword') { bk.step = 'pick'; bk.text = null; bk.header = null; }       /* fichier abîmé : on repart du choix du fichier */
    renderSave();
  });
}
/* état en mémoire relu depuis la base (après une restauration ou son annulation) */
function bkReloadState() {
  return Promise.all([AG.allPersons(), AG.allRides(), AG.getSetting('idle_sec'), AG.getMeta('last_export'), AG.getSafety(), AG.getMeta('backup_key')]).then(function (r) {
    people = r[0]; rides = r[1]; if (typeof r[2] === 'number') idleSec = r[2]; lastExport = r[3] || null; bk.safety = r[4] || null; bk.hasKey = !!r[5];
    day = today(); openKey = null; showArch = false; query = '';
  });
}
function bkDoRestore() {
  var o = bk.opened; if (!o) return;
  var t = bkStart(), now = nowDate();
  Promise.all([AG.snapshotAll(), AG.getMeta('last_export'), AG.getMeta('backup_key')]).then(function (r) {
    var safety = { key: 'current', at: now.toISOString(), expires_at: new Date(now.getTime() + BK_SAFETY_DAYS * 86400000).toISOString(), data: r[0], meta: { last_export: r[1] || null, backup_key: r[2] || null } };
    var data = AGB.migrateData(o.data, AG.schemaTarget);
    var metaPuts = { last_export: { at: o.header.exported_at, date: iso(new Date(o.header.exported_at)) }, backup_key: { key: o.key, kdf: o.kdf, wrapped: o.wrapped, created_at: now.toISOString() } };
    return AG.replaceAll(data, metaPuts, { safetyPut: safety });            /* une seule transaction : tout ou rien */
  }).then(bkReloadState).then(function () {
    var c = o.counts;
    logEvt('Sauvegarde restaurée');
    bkReset('Sauvegarde restaurée : ' + countsText(c) + '. Vous pouvez l’annuler pendant ' + BK_SAFETY_DAYS + ' jours.', 'ok'); renderSave();
  }, function () { bkReset('La restauration a échoué : rien n’a été modifié sur ce téléphone.', 'err'); renderSave(); });
}
function bkDoUndo() {
  bkStart();
  AG.getSafety().then(function (s) {
    if (!s) throw new Error('none');
    return AG.replaceAll(s.data, { last_export: s.meta.last_export || undefined, backup_key: s.meta.backup_key || undefined }, { safetyDelete: true });
  }).then(bkReloadState).then(function () {
    logEvt('Restauration annulée');
    bkReset('Restauration annulée : les données d’avant sont revenues.', 'ok'); renderSave();
  }, function () { bkReset('Impossible d’annuler la restauration. Rien n’a été modifié.', 'err'); renderSave(); });
}
document.addEventListener('change', function (e) { if (e.target && e.target.id === 'bk-file') bkFilePicked(e.target.files && e.target.files[0]); });
document.addEventListener('keydown', function (e) { if (e.key === 'Enter' && e.target && e.target.id === 'bk-phrase') { e.preventDefault(); bkOpen(); } });
function bkAction(a) {
  switch (a) {
    case 'opensave': bkOpenScreen(); break;
    case 'bk-export': bkExportClick(); break;
    case 'bk-show': bk.phrase = AGB.drawPhrase(); bk.until = Date.now() + BK_PHRASE_MS; lastTouch = Date.now(); bk.ask = bkPickAsk(); bk.step = 'phrase'; bk.msg = ''; renderSave(); break;
    case 'bk-renew': bkReset(); bk.renew = true; bk.step = 'explain'; renderSave(); break;
    case 'bk-reveal': bkToggleReveal(); break;
    case 'bk-written': bk.step = 'confirm'; bk.msg = ''; renderSave(); break;
    case 'bk-review': bk.step = 'phrase'; renderSave(); break;
    case 'bk-confirm': bkConfirm(); break;
    case 'bk-cancel': bkReset(); renderSave(); break;
    case 'bk-verify': bkReset(); bk.mode = 'verify'; bk.step = 'pick'; renderSave(); break;
    case 'bk-restore': bkReset(); bk.mode = 'restore'; bk.step = 'pick'; renderSave(); break;
    case 'bk-open': bkOpen(); break;
    case 'bk-replace': openConfirm('restore'); break;
    case 'bk-undo': openConfirm('undorestore'); break;
    case 'bk-keep': AG.deleteSafety().then(function () { bk.safety = null; bk.msg = 'Restauration gardée définitivement : la copie de sécurité est effacée.'; bk.msgKind = 'ok'; renderSave(); }); break;
  }
}

/* ========= Réglages ========= */
function refreshReglages() {
  $('#rg-lastexport').textContent = lastExportText();
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
var swReg = null, updateReady = false, userAsked = false, reloading = false, swActive = false, swControls = false, verifying = false;
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
    swControls = true; maybeReload();
  });
}
/* On ne recharge que lorsque : Pascal a touché « Mettre à jour » ET le nouveau service worker est actif ET il contrôle cette page ET sa réserve
   est vérifiée COMPLÈTE (il répond lui-même à la question). Jamais avant. */
function maybeReload() {
  if (!userAsked || reloading || verifying || !swActive || !swControls) return;
  verifying = true;
  verifyCache().then(function (r) {
    if (r === null) { logEvt('Réserve non vérifiée (pas de réponse en 4 s) : rechargement quand même'); reloadOnce(); }
    else if (r.ok) { logEvt('Réserve complète (version ' + r.version + ')'); reloadOnce(); }
    else if (!reloading) { reloading = true; logEvt('Réserve incomplète (' + String(r.missing).slice(0, 60) + ') : rechargement en contournant les réserves'); AGG.reload(true); }
  });
}
function verifyCache() {
  return new Promise(function (resolve) {
    var c = navigator.serviceWorker.controller, done = false;
    var end = function (v) { if (!done) { done = true; resolve(v); } };
    setTimeout(function () { end(null); }, 4000);
    if (!c || !self.MessageChannel) { end(null); return; }
    var ch = new MessageChannel(); ch.port1.onmessage = function (e) { end(e.data || null); };
    c.postMessage({ type: 'VERIFY' }, [ch.port2]);
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
  w.addEventListener('statechange', function () { if (w.state === 'activated') { logEvt('Nouveau service worker actif'); swActive = true; maybeReload(); } });
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
function mask(eye) {
  if (veilOn) { if (eye === 'eye') bkOnMask(true); return; }
  bkOnMask(eye === 'eye');                                                                                                  /* phrase, résumés, noms de fichiers : effacés de la page */
  clearTimeout(toastTimer); toastEl.hidden = true; undoFn = null;      /* un message ne doit rien montrer sous l'écran neutre */
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();      /* valide un champ en cours de saisie */
  ctx.calReveal = false; if (cur === 'calendrier') renderCal();
  bil.reveal = false; if (cur === 'bilan') renderBilan();                                        /* les montants se recachent */
  if (fsh) { sheetClose(); $('#ds-panel').innerHTML = ''; }                                                                         /* un plein en cours de saisie est abandonné : rien de lisible derrière l'écran neutre */
  if (cur === 'essence') { fuelTok++; fuelList = []; $('#s-essence').innerHTML = ''; }          /* page Essence vidée, remise au retour */
  openKey = null; if (cur === 'aujourdhui') renderAuj();                                          /* au retour, les cartes sont repliées : montants et adresses retirés de l'écran */
  veilEl.innerHTML = '<span class="vword">Agenda</span>';
  veilEl.setAttribute('role', 'button'); veilEl.setAttribute('tabindex', '0'); veilEl.setAttribute('aria-label', 'Agenda masqué. Toucher pour rouvrir');
  veilOn = true; veilEl.classList.add('on'); setInert(true);
}
function unmask() { if (cur === 'essence') renderEssence(); veilOn = false; veilEl.classList.remove('on'); veilEl.innerHTML = ''; setInert(false); lastTouch = Date.now(); if (cur === 'sauvegarde') renderSave(); AGG.unmasked(); }
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
  bkExpire();
  if (veilOn) return;
  var now = Date.now();
  if (now < lastTouch - 2000) { mask(); return; }                      /* l'horloge a reculé : par prudence on masque */
  if (bkPhraseLive() && cur === 'sauvegarde') return;                  /* écran de la phrase ouvert : masquage automatique en pause (10 minutes au plus) */
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
  if (a === 'opensave' || a.indexOf('bk-') === 0) { bkAction(a); return; }
  switch (a) {
    case 'tab': if (ficheDirty()) { openConfirm('leave', null, b.dataset.t); break; } go(b.dataset.t); break;
    case 'reglages': history.pushState({ app: 1 }, ''); go('reglages'); break;
    case 'back': if (cur === 'fiche' || cur === 'calendrier') back(); else if (cur === 'sauvegarde') bkBack(); else go('bilan'); break;
    case 'hide': mask('eye'); break;
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
    case 'calfiche': if (ficheDirty()) { openConfirm('leave', null, { cal: id }); break; } openCalendar(id, 'fiche'); break;
    case 'bperson': openCalendar(b.dataset.pid, 'bilan', bil.ref.getFullYear(), bil.ref.getMonth()); break;       /* depuis « Par personne » : directement sur le mois du Bilan */
    case 'calreveal': ctx.calReveal = !ctx.calReveal; renderCal(); break;
    case 'month': var mm = new Date(ctx.calY, ctx.calM + (+b.dataset.d), 1); ctx.calY = mm.getFullYear(); ctx.calM = mm.getMonth(); ctx.calReveal = false; renderCal(); break;
    case 'calday': sheetOpen({ pid: ctx.calPid, iso: b.dataset.iso, mode: 'menu', direct: false }); break;
    case 'dsclose': if (fsh && fuelDirty()) { openConfirm('leave', null, { fuel: 'close' }); break; } sheetClose(); break;
    case 'emonth': fuelM = new Date(fuelM.y, fuelM.m + (+b.dataset.d), 1); fuelM = { y: fuelM.getFullYear(), m: fuelM.getMonth() }; renderEssence(); break;
    case 'eday': openFuelSheet(b.dataset.iso); break;
    case 'eedit':
      var ex = null; fuelList.forEach(function (x) { if (x.id === id) ex = x; }); if (!ex) break;
      if (!fsh) { dsh = null; fsh = { iso: ex.date, mode: 'list', id: null, fs: { p: '', l: '', m: '', calc: null }, sig: '' }; $('#daysheet').classList.add('on'); }
      fuelForm(id); break;
    case 'eadd': if (fsh) fuelForm(null); break;
    case 'eback': if (!fsh) break; if (fuelDirty()) { openConfirm('leave', null, { fuel: 'back' }); break; } fuelBack(); break;
    case 'esave': if (fsh) fuelSave(); break;
    case 'edelask': if (fsh && fsh.id) openConfirmFuel(fsh.id); break;
    case 'dspick': if (dsh) { dsh = { pid: id, iso: dsh.iso, mode: 'form', add: true, direct: true }; renderSheet(); } break;
    case 'dschg': case 'dsdel': case 'dsadd': case 'dsback': case 'dssave': case 'dscomme': case 'dspas': case 'dsfait':
      if (!dsh) {      /* depuis la carte ouverte d'Aujourd'hui */
        var di = findItem(b.dataset.key, iso(day)); if (!di) break;
        if (a === 'dschg') sheetOpen({ pid: di.pid, iso: iso(day), mode: 'form', add: false, direct: true });
        else if (a === 'dsdel') { sheetOpen({ pid: di.pid, iso: iso(day), mode: 'menu', direct: true }); sheetAction('dsdel'); }
        break;
      }
      sheetAction(a); break;
    case 'bview': bil.view = b.dataset.v; bil.reveal = false; renderBilan(); break;
    case 'bmonth': bil.ref = new Date(bil.ref.getFullYear(), bil.ref.getMonth() + (+b.dataset.d), 1); bil.reveal = false; renderBilan(); break;
    case 'reveal': bil.reveal = !bil.reveal; renderBilan(); break;
    case 'bday': day = parseISO(b.dataset.iso); openKey = null; go('aujourdhui'); break;       /* ouvre ce jour dans Aujourd'hui */
    case 'confirmcancel': closeConfirm(); break;
    case 'confirmok': confirmOk(); break;
  }
});
$('#q').addEventListener('input', function () { query = this.value; renderPers(); });
document.addEventListener('input', function (e) {
  var t = e.target, id = t.id, v, fm = /^fu-([plm])$/.exec(t.id);
  if (fm && fsh) { v = t.value.replace(/[^0-9.,]/g, ''); if (v !== t.value) t.value = v; fsh.fs[fm[1]] = v; fuelRecalc(fm[1]); return; }
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
    if (dsh || fsh) { if (fsh && fuelDirty()) openConfirm('leave', null, { fuel: 'close' }); else sheetClose(); history.pushState({ app: 1 }, ''); return; }
    if (cur === 'fiche' || cur === 'calendrier') { back(); history.pushState({ app: 1 }, ''); }
    else if (cur === 'sauvegarde') { bkBack(); history.pushState({ app: 1 }, ''); }
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
  rides = rs;
  [['renderPers', renderPers], ['renderAuj', renderAuj]].forEach(function (s) { try { s[1](); } catch (er) { AGG.caught(er, s[0]); } });      /* une partie qui échoue n'empêche pas le reste de s'afficher */
  setTimeout(function () { AGG.displayed(); }, 60);
  return startupLog();
}).then(function () {
  return bkInit();
}).then(function () {
  return firstLaunchStorage();
}).then(function () { isReady = true; hideBlocked(); refreshReglages(); }, function (er) {
  isReady = true; hideBlocked();
  var dbError = er && (er.code || er.name === 'VersionError' || (self.DOMException && er instanceof DOMException));
  if (!dbError) { AGG.caught(er, 'démarrage'); AGG.problem(); }       /* erreur de code (pas de stockage) : message simple avec bouton « Recharger » */
  else if (er && er.code === 'newer') fatal('Données plus récentes que l’appli', 'Les données de ce téléphone ont été écrites par une version plus récente d’Agenda. Rien n’a été effacé. Ferme l’appli, rouvre-la avec internet pour la mettre à jour, puis réessaie.');
  else fatal('Stockage indisponible', 'Agenda ne peut pas ouvrir son stockage sur ce téléphone. Rien n’a été effacé. Ferme et rouvre l’appli ; si le message revient, ne saisis rien et préviens celui qui t’aide.');
});

try { go('aujourdhui'); } catch (er) { AGG.caught(er, 'go'); }
startWorker();

/* lecture seule, pour les contrôles automatiques */
window.__ag = {
  get cur() { return cur; }, get tab() { return tab; }, get masked() { return veilOn; }, get idle() { return idleSec; },
  get ready() { return ready; }, get lastExport() { return lastExport; }, get bk() { return { reveal: bk.reveal, until: bk.until, renew: bk.renew, hasKey: bk.hasKey, step: bk.step, hasPhrase: !!bk.phrase, phrase: bk.phrase ? bk.phrase.slice() : null, ask: bk.ask, msg: bk.msg, safety: !!bk.safety }; }, get updateReady() { return updateReady; }, get people() { return people.slice(); }, get rides() { return rides.slice(); }, get day() { return iso(day); }, get bilanMs() { return bil.ms; }, get fuelMonth() { return fuelM.y + '-' + pad(fuelM.m + 1); }, get calFrom() { return ctx.calFrom; }, get bilan() { return { view: bil.view, month: iso(bil.ref), reveal: bil.reveal }; },
  version: APP_VERSION, dbName: AG.DB_NAME, openDatabase: AG.openDatabase, dbGet: AG.dbGet, dbPut: AG.dbPut,
  migrations: AG.MIGRATIONS, schemaTarget: AG.schemaTarget
};
})();
