self.AG_STAMPS=self.AG_STAMPS||{};self.AG_STAMPS['fuel.js']='0.6.3'; /* numéro écrit par verifications/sync_version.py : ne pas modifier à la main */
/* Agenda : la logique des pleins d'essence (sans écran, sans stockage). Aucune donnée dans ce fichier.
   Règles (plan, section 3, et maquette) :
   - un plein = prix au litre, litres, montant : Pascal en remplit DEUX, le troisième se calcule (repère « calculé ») ;
   - litres en MILLILITRES, prix au litre en MILLIÈMES d'euro, montant en CENTIMES : tout entier ; vide = inconnu (null), jamais 0 ;
   - jamais de valeur inventée : on ne calcule le troisième chiffre que si les deux autres sont connus ;
   - un total du mois ne compte jamais une valeur inconnue comme 0 : « + N pleins sans montant (total partiel) ». */
(function () {
'use strict';

function fnum(t) { return parseFloat(String(t).replace(',', '.')); }
function fix(n, d) { var t = n.toFixed(d); if (t.indexOf('.') >= 0) t = t.replace(/0+$/, '').replace(/\.$/, ''); return t.replace('.', ','); }   /* sans zéros inutiles : 25 · 1,5 · 68,88 */
function r2(x) { return Math.round((x + 1e-9) * 100) / 100; }

var AGF = {};

/* « third » (m, l ou p) calculé à partir des deux autres (chaînes saisies, virgule ou point) ; '' si impossible */
AGF.calc = function (fs, third) {
  var l = fnum(fs.l), p = fnum(fs.p), m = fnum(fs.m);
  if (third === 'm') return (l > 0 && p > 0) ? fix(r2(l * p), 2) : '';                                        /* montant = litres × prix, au centime */
  if (third === 'l') return (m > 0 && p > 0) ? fix(r2(m / p), 2) : '';                                        /* litres = montant ÷ prix, 2 décimales */
  return (m > 0 && l > 0) ? fix(Math.round((m / l + 1e-9) * 1000) / 1000, 3) : '';                              /* prix = montant ÷ litres, 3 décimales */
};

/* virgule ou point ; vide = inconnu ; 0 refusé ; trop de décimales refusé */
AGF.parse = function (s, dec) {
  s = String(s || '').replace(/\s/g, ''); if (!s) return { v: '' };
  if (!new RegExp('^\\d{1,6}([.,]\\d{1,' + dec + '})?$').test(s)) return { err: 'format' };
  if (!(fnum(s) > 0)) return { err: 'zero' };
  return { v: s.replace('.', ',') };
};

/* trois chiffres saisis (ou calculés) → les valeurs rangées dans la base (entiers, null = inconnu) */
AGF.toRecord = function (out) {
  return {
    liters_ml: out.l === '' ? null : Math.round(fnum(out.l) * 1000),
    price_milli: out.p === '' ? null : Math.round(fnum(out.p) * 1000),
    total_cents: out.m === '' ? null : Math.round(fnum(out.m) * 100)
  };
};
var CALC = { p: 'price', l: 'liters', m: 'total' }, CALC_BACK = { price: 'p', liters: 'l', total: 'm' };
AGF.calcName = function (letter) { return letter ? CALC[letter] : null; };
AGF.calcLetter = function (name) { return name ? CALC_BACK[name] || null : null; };

/* affichage (virgule française) */
function trim(s) { return s.replace(/0+$/, '').replace(/\.$/, ''); }
AGF.fmtL = function (ml) { return ml == null ? '' : trim((ml / 1000).toFixed(2)).replace('.', ','); };                     /* 38500 → 38,5 */
AGF.fmtP = function (milli) { if (milli == null) return ''; var s = (milli / 1000).toFixed(3); if (s.slice(-1) === '0') s = s.slice(0, -1); return s.replace('.', ','); };   /* 1789 → 1,789 ; 1800 → 1,80 */
AGF.fmtM = function (c) { if (c == null) return ''; var e = Math.floor(c / 100), r = c % 100; return r ? e + ',' + (r < 10 ? '0' : '') + r : String(e); };   /* 6888 → 68,88 ; 7200 → 72 */
AGF.fmtLtot = function (ml) { return (ml / 1000).toFixed(2).replace('.', ',') + ' L'; };                                    /* total : toujours 2 décimales */
AGF.toForm = function (rec) { return { p: AGF.fmtP(rec.price_milli), l: AGF.fmtL(rec.liters_ml), m: AGF.fmtM(rec.total_cents), calc: AGF.calcLetter(rec.calc) }; };

/* Totaux d'une liste de pleins (les pleins à la corbeille ne comptent jamais) */
AGF.totals = function (list) {
  var t = { count: 0, ml: 0, noLiters: 0, cents: 0, noAmount: 0 };
  list.forEach(function (x) {
    if (x.deleted_at) return;
    t.count++;
    if (x.liters_ml == null) t.noLiters++; else t.ml += x.liters_ml;
    if (x.total_cents == null) t.noAmount++; else t.cents += x.total_cents;
  });
  return t;
};

self.AGF = AGF;
})();
