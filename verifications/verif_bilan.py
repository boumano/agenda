"""Étape 4 d'Agenda : écran Bilan, « Totaux » et « Jour par jour » (le père ne reçoit RIEN : Pascal lit l'écran à voix haute).
Vérifie : choix du mois, totaux (courses faites, euros, km) et détail par personne ; seules les courses « fait » non supprimées comptent ; « pas fait », corbeille et
cartes prévues jamais touchées ne comptent pas ; prix ou km inconnus = jamais un 0 (« N courses sans prix », total partiel, « inconnu ») ; montants masqués tant qu'on
ne touche pas ; courses « changé » avec leurs valeurs propres ; personne archivée ; « Jour par jour » (oui / non / pas noté / à faire, « N jours sans note », toucher un jour
ouvre ce jour dans Aujourd'hui, prénoms en double) ; jours autour du 25 octobre 2026 ; masquage ; persistance ; hors connexion ; plusieurs milliers de courses (lecture par
l'index des dates, temps d'affichage) ; aucun bouton d'envoi, de copie ni de partage.
Noms FICTIFS seulement. W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, time, threading, pathlib, http.server, functools
from datetime import date, datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
TODAY = date.today(); TISO = TODAY.isoformat()
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
JJ = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
fails = 0; total = 0


def ok(n, c, e=""):
    global fails, total
    total += 1
    if not c: fails += 1
    print(("PASS " if c else "FAIL ") + n + (" | " + str(e)[:600] if not c else ""))


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "max-age=600")
        super().end_headers()
    def log_message(self, *a): pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % srv.server_address[1]
INIT = """window.__off=0; window.__freeze=false; (function(){ var n=Date.now.bind(Date); Date.now=function(){ return n()+window.__off; }; var si=window.setInterval.bind(window); window.setInterval=function(f,t){ return si(function(){ if(!window.__freeze) f(); },t); }; })();"""


def first_of(dt): return dt.replace(day=1)
def add_month(dt, n):
    y, m = dt.year, dt.month - 1 + n
    return date(y + m // 12, m % 12 + 1, 1)
CM = first_of(TODAY); PM = add_month(CM, -1); PM2 = add_month(CM, -2); NM = add_month(CM, 1)
def md(first, day): return first.replace(day=day)
def month_days(first):
    out = []; dt = first
    while dt.month == first.month: out.append(dt); dt += timedelta(days=1)
    return out


def person(i, last, first, weekdays=(), time="09:00", archived=False):
    return {"id": "00000000-0000-4000-8000-%012d" % i, "last_name": last, "first_name": first, "pickup_street": "1 rue Depart", "pickup_zip": "11111", "pickup_city": "Villedepart",
            "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible", "phone": "", "usual_price_cents": 1250, "usual_km_m": 8500,
            "archived": archived, "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z",
            "schedule": {"mode": "weekly", "weekdays": list(weekdays), "time_weekly": time, "from": None, "to": None, "dates": [], "time_dates": None}}


_n = [0]
def ride(pid, dt, status, price, km, deleted=None, changed=False, time="09:00"):
    _n[0] += 1
    return {"id": "00000000-0000-4000-9000-%012d" % _n[0], "person_id": pid, "date": dt.isoformat(), "time": time, "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible",
            "price_cents": price, "km_m": km, "usual_price_cents": 1250, "usual_km_m": 8500, "status": status, "changed": changed, "added": False, "skip": False,
            "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z", "deleted_at": deleted}


A = person(1, "Alpha", "Un", [1, 2, 3, 4, 5], "09:00"); B = person(2, "Beta", "Deux"); C = person(3, "Gamma", "Trois", archived=True)
D = person(4, "Delta", "Quatre", [1, 2, 3, 4, 5], "10:00"); E = person(5, "Epsilon", "Cinq"); F = person(6, "Zeta", "Un")
PEOPLE = [A, B, C, D, E, F]
DONE, NOT = "done", "not_done"


def euros(c): return "%d,%02d €" % (c // 100, c % 100)
def km2(m):
    v = int(m / 10 + 0.5) / 100
    return ("%.2f" % v).rstrip("0").rstrip(".").replace(".", ",") + " km"
def sans(n, what): return "%d %s sans %s" % (n, "courses" if n > 1 else "course", what)


def expected_totals(rides, first, persons=PEOPLE):
    pre = first.isoformat()[:7]; P = {p["id"]: p for p in persons}; per = {}; tot = [0, 0, 0, 0, 0]
    for r in rides:
        if r["deleted_at"] or r["status"] != DONE or not r["date"].startswith(pre) or r["person_id"] not in P: continue
        q = per.setdefault(r["person_id"], [0, 0, 0, 0, 0])
        for a in (q, tot):
            a[0] += 1
            if r["price_cents"] is None: a[2] += 1
            else: a[1] += r["price_cents"]
            if r["km_m"] is None: a[4] += 1
            else: a[3] += r["km_m"]
    return tot, per   # [count, cents, noPrice, meters, noKm]


def model_days(rides, first, today, persons=PEOPLE):
    """ce que « Jour par jour » doit montrer : liste de (iso, [(prénom, mot)]) et nombre de jours sans note"""
    P = {p["id"]: p for p in persons}; pre = first.isoformat()[:7]; rows = []; nonote = 0; names = {}
    def norm(s): return s.lower()
    per_day = []
    for dt in month_days(first):
        if dt > today: break
        its = []
        live = [r for r in rides if not r["deleted_at"] and r["date"] == dt.isoformat() and r["person_id"] in P]
        for r in live:
            p = P[r["person_id"]]
            if p["archived"] and not r["status"] and dt >= today: continue
            its.append((r["time"] or "99:99", norm(p["last_name"] + " " + p["first_name"]), p, r["status"]))
        for p in persons:
            if p["archived"] or dt.isoweekday() not in p["schedule"]["weekdays"]: continue
            if any(r["person_id"] == p["id"] for r in live): continue
            its.append((p["schedule"]["time_weekly"] or "99:99", norm(p["last_name"] + " " + p["first_name"]), p, None))
        its.sort(key=lambda x: (x[0], x[1]))
        if not its: continue
        per_day.append((dt, its))
        for t, n_, p, st in its: names.setdefault(norm(p["first_name"] or p["last_name"]), set()).add(p["id"])
    for dt, its in per_day:
        noted = any(x[3] in (DONE, NOT) for x in its)
        if not noted and dt < today: nonote += 1
        row = []
        for t, n_, p, st in its:
            nm = p["last_name"] + " " + p["first_name"]       # nom complet, comme « Par personne »
            pass
            row.append((nm, "oui" if st == DONE else ("non" if st == NOT else ("à faire" if dt == today else "pas noté"))))
        rows.append((dt.isoformat(), "%s %d" % (JJ[dt.weekday()], dt.day), row))
    return rows, nonote


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="allow")
    cx.add_init_script(INIT)
    errs = []; reqs = []
    cx.on("request", lambda r: reqs.append(r.url))
    pg = cx.new_page()
    pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
    pg.on("console", lambda m: errs.append("console " + m.text) if m.type == "error" else None)

    w = lambda: pg.wait_for_timeout(350)
    tap = lambda sel: (pg.locator(sel).first.tap(), w())
    goto = lambda t: tap('.nav button.t[data-t="%s"]' % t)
    cur = lambda: pg.evaluate("__ag.cur")
    masked = lambda: pg.evaluate("__ag.masked")
    jump = lambda ms: pg.evaluate("window.__off += %d" % ms)
    txt = lambda sel: pg.locator(sel).inner_text().strip()
    mois = lambda: txt("#bil-month").lower()
    pers_rows = lambda: pg.evaluate("[...document.querySelectorAll('#bil-persons .pp')].map(r=>[r.querySelector('.nom').textContent.trim(),r.querySelector('small').textContent.trim(),r.querySelector('.amount').textContent.trim(),r.querySelector('.l3').textContent.trim()])")
    jj_rows = lambda: pg.evaluate("[...document.querySelectorAll('#jj-list .jjrow')].map(r=>[r.dataset.iso,r.querySelector('.jjday').textContent.trim(),[...r.querySelectorAll('.jjp')].map(s=>[s.querySelector('.name').textContent.trim(),s.querySelector('.jjw').textContent.trim()])])")

    def db_all(store):
        return pg.evaluate("""(s)=>new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result;const g=d.transaction(s).objectStore(s).getAll();g.onsuccess=()=>{d.close();r(g.result)}}})""", store)
    def boot():
        pg.goto(BASE); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(250)
    def seed(persons, rides):
        pg.evaluate("""async([ps,rs])=>{ for(const p of ps) await AG.putPerson(p); await new Promise(f=>{const t=AG.db.transaction('rides','readwrite');rs.forEach(r=>t.objectStore('rides').put(r));t.oncomplete=f}) }""", [persons, rides])
        pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    def bilan(view="tot", first=None):
        goto("bilan")
        if pg.locator('[data-a="bview"][data-v="%s"].on' % view).count() == 0: tap('[data-a="bview"][data-v="%s"]' % view)
        for _ in range(40):
            if first is None or mois() == "%s %d" % (MOIS[first.month - 1], first.year): break
            cm = [i for i, m_ in enumerate(MOIS) if mois().startswith(m_)][0] + 1; cy = int(mois().split()[-1])
            tap('[data-a="bmonth"][data-d="%d"]' % (1 if (first.year, first.month) > (cy, cm) else -1))

    boot()
    # ---------- données : mois précédent (PM), avant-dernier mois (PM2), mois en cours ----------
    RIDES = [
        ride(A["id"], md(PM, 5), DONE, 1250, 8500), ride(A["id"], md(PM, 6), DONE, 1000, 5000), ride(A["id"], md(PM, 7), DONE, None, 3000), ride(A["id"], md(PM, 8), DONE, 500, None),
        ride(A["id"], md(PM, 9), NOT, 2000, 9000), ride(A["id"], md(PM, 10), DONE, 9999, 99999, deleted="2026-02-01T00:00:00.000Z"), ride(A["id"], md(PM, 11), DONE, 777, 1234, changed=True),
        ride(B["id"], md(PM, 12), DONE, 300, 1000), ride(B["id"], md(PM, 13), DONE, None, None), ride(C["id"], md(PM, 14), DONE, 700, 2000), ride(F["id"], md(PM, 5), DONE, 400, 1500),
        ride(E["id"], md(PM2, 3), DONE, None, None), ride(E["id"], md(PM2, 4), DONE, None, None),
        ride(A["id"], TODAY, DONE, 1250, 8500),
    ]
    seed(PEOPLE, RIDES)
    tot, per = expected_totals(RIDES, PM)

    # ================= 1. Totaux du mois précédent =================
    bilan("tot", PM)
    ok(tag + " Bilan : titre, choix « Totaux » (choisi) / « Jour par jour », mois précédent affiché avec deux chevrons, ligne « Réglages » en bas", cur() == "bilan" and txt("#s-bilan h1") == "Bilan" and pg.locator('[data-a="bview"][data-v="tot"].on').count() == 1 and mois() == "%s %d" % (MOIS[PM.month - 1], PM.year) and pg.locator('[data-a="bmonth"]').count() == 2 and pg.locator('[data-a="reglages"]').count() == 1)
    ok(tag + " courses FAITES : %d (« pas fait », corbeille et cartes prévues jamais touchées ne comptent pas)" % tot[0], txt("#bil-count") == str(tot[0]) and "courses faites" in pg.locator("#s-bilan .tile .l").first.inner_text(), txt("#bil-count"))
    ok(tag + " euros MASQUÉS tant qu'on ne touche pas : « •••• € », aucun chiffre", txt("#bil-eur") == "•••• €" and "Toucher pour afficher" in pg.locator('[data-a="reveal"]').inner_text() and not re.search(r"\d", txt("#bil-eur")))
    ok(tag + " la note « + 2 courses sans prix (total partiel) » est visible même masquée (elle ne dévoile aucun montant)", txt("#bil-eur-note") == "+ %s (total partiel)" % sans(tot[2], "prix"), txt("#bil-eur-note"))
    tap('[data-a="reveal"]')
    ok(tag + " touché : total en euros = somme des PRIX CONNUS seulement (%s), jamais de 0 inventé pour les %d courses sans prix" % (euros(tot[1]), tot[2]), txt("#bil-eur") == euros(tot[1]) and "Toucher pour masquer" in pg.locator('[data-a="reveal"]').inner_text(), txt("#bil-eur"))
    ok(tag + " km : %s (somme des km connus), note « + %s (total partiel) »" % (km2(tot[3]), sans(tot[4], "km")), txt("#bil-km") == km2(tot[3]) and txt("#bil-km-note") == "+ %s (total partiel)" % sans(tot[4], "km"), (txt("#bil-km"), txt("#bil-km-note")))
    pg.screenshot(path=SHOTS + "/bilan_totaux_%dx%d_%s.png" % (W, H, SCHEME))
    rows = pers_rows(); exp_rows = []
    for pid in [A["id"], B["id"], C["id"], F["id"]]:
        q = per[pid]; pp = [x for x in PEOPLE if x["id"] == pid][0]
        notes = []
        if q[2]: notes.append("+ " + sans(q[2], "prix"))
        if q[4]: notes.append("+ " + sans(q[4], "km"))
        exp_rows.append([pp["last_name"], "%d %s" % (q[0], "courses faites" if q[0] > 1 else "course faite"), euros(q[1]), km2(q[3]) + ((" · " + " · ".join(notes)) if notes else "")])
    ok(tag + " détail par personne (ordre alphabétique des noms) : courses faites, euros, km, notes « sans prix » / « sans km » ; la personne ARCHIVÉE (Gamma) y est", [[r[0], r[1], r[2], r[3]] for r in rows] == exp_rows, rows)
    ok(tag + " Alpha : 5 courses faites dont une « changée » (777 centimes, 1234 m) comptée avec ses valeurs propres", [r for r in rows if r[0] == "Alpha"][0][2] == euros(per[A["id"]][1]) and per[A["id"]][1] == 3527)
    ok(tag + " Epsilon (aucune course ce mois-ci) absente de la liste du mois", "Epsilon" not in [r[0] for r in rows])
    tap('[data-a="reveal"]')
    ok(tag + " retoucher : les montants se recachent (liste comprise)", txt("#bil-eur") == "•••• €" and all(r[2] == "•••• €" for r in pers_rows()))

    # ================= 2. prix et km inconnus : jamais 0 =================
    tap('[data-a="bmonth"][data-d="-1"]')
    ok(tag + " mois d'avant : %s %d" % (MOIS[PM2.month - 1], PM2.year), mois() == "%s %d" % (MOIS[PM2.month - 1], PM2.year))
    ok(tag + " 2 courses faites, toutes sans prix ni km : « 2 courses faites », note « + 2 courses sans prix (total partiel) »", txt("#bil-count") == "2" and txt("#bil-eur-note") == "+ 2 courses sans prix (total partiel)" and txt("#bil-km-note") == "+ 2 courses sans km (total partiel)")
    tap('[data-a="reveal"]')
    ok(tag + " total en euros : « inconnu » (pas « 0,00 € »), km : « inconnu » (pas « 0 km ») ; la personne : même chose", txt("#bil-eur") == "inconnu" and txt("#bil-km") == "inconnu" and pers_rows()[0][2] == "inconnu" and pers_rows()[0][3].startswith("inconnu") and "0,00" not in pg.locator("#s-bilan").inner_text() and not re.search(r"(^|\s)0 km", pg.locator("#s-bilan").inner_text()), (txt("#bil-eur"), pers_rows()))
    tap('[data-a="bmonth"][data-d="1"]')
    ok(tag + " changer de mois recache les montants", txt("#bil-eur") == "•••• €")
    tap('[data-a="bmonth"][data-d="1"]')
    ok(tag + " mois en cours (%s) : la course d'aujourd'hui faite est comptée, les cartes prévues des jours d'avant non (1 course)" % MOIS[CM.month - 1], mois() == "%s %d" % (MOIS[CM.month - 1], CM.year) and txt("#bil-count") == "1" and txt("#bil-eur-note") == "total du mois", (txt("#bil-count"), mois()))
    tap('[data-a="bmonth"][data-d="1"]')
    ok(tag + " mois suivant (à venir) : 0 course faite, « Rien de fait ce mois-ci. », « 0 km », jamais d'erreur", mois() == "%s %d" % (MOIS[NM.month - 1], NM.year) and txt("#bil-count") == "0" and "Rien de fait ce mois-ci." in pg.locator("#bil-persons").inner_text() and txt("#bil-km") == "0 km")

    # ================= 2b. « Par personne » touchable : calendrier de CETTE personne =================
    cal_lbl = lambda: txt("#s-calendrier .monthnav .lbl").lower()
    lit = lambda: pg.locator(".nav button.t.on").inner_text().strip()
    bilan("tot", PM)
    hts = pg.evaluate("[...document.querySelectorAll('#bil-persons button.pp')].map(b=>Math.round(b.getBoundingClientRect().height))")
    ok(tag + " lignes « Par personne » : ce sont des boutons avec la flèche à droite (comme les autres lignes touchables), 52 px de haut au moins", pg.locator("#bil-persons button.pp").count() == 4 and pg.locator('#bil-persons button.pp svg use[href="#i-right"]').count() == 4 and all(x >= 52 for x in hts), hts)
    tap('#bil-persons .pp[data-pid="%s"]' % A["id"])
    ok(tag + " toucher « Alpha Un » ouvre SON calendrier, directement sur le mois du Bilan (%s %d), l'onglet Bilan reste allumé" % (MOIS[PM.month - 1], PM.year), cur() == "calendrier" and txt("#s-calendrier h1") == "Calendrier et courses" and txt("#s-calendrier .sub") == "Alpha Un" and cal_lbl() == "%s %d" % (MOIS[PM.month - 1], PM.year) and lit() == "Bilan" and pg.evaluate("__ag.calFrom") == "bilan" and pg.locator("#s-calendrier .cell").count() == len(month_days(PM)), (cur(), cal_lbl(), lit()))
    pg.screenshot(path=SHOTS + "/bilan_calendrier_%dx%d_%s.png" % (W, H, SCHEME))
    qa = per[A["id"]]
    ok(tag + " résumé du mois en haut : %d courses faites, euros masqués « •••• € », km %s, notes « sans prix / sans km » visibles" % (qa[0], km2(qa[3])), txt("#cal-count") == str(qa[0]) and txt("#cal-eur") == "•••• €" and txt("#cal-km") == km2(qa[3]) and txt("#cal-notes") == "+ %s (total partiel) · + %s (total partiel)" % (sans(qa[2], "prix"), sans(qa[4], "km")), (txt("#cal-count"), txt("#cal-eur"), txt("#cal-km"), txt("#cal-notes")))
    tap('[data-a="calreveal"]')
    ok(tag + " toucher le montant : %s (somme des prix connus, jamais de 0 inventé)" % euros(qa[1]), txt("#cal-eur") == euros(qa[1]) and "toucher pour masquer" in pg.locator('[data-a="calreveal"]').inner_text())
    tap('#s-calendrier [data-a="month"][data-d="-1"]')
    ok(tag + " mois d'avant DANS le calendrier : le résumé suit (0 course, montant de nouveau masqué)", cal_lbl() == "%s %d" % (MOIS[PM2.month - 1], PM2.year) and txt("#cal-count") == "0" and txt("#cal-eur") == "•••• €" and pg.locator("#cal-notes").count() == 0, (cal_lbl(), txt("#cal-count"), txt("#cal-eur")))
    tap('[data-a="calreveal"]')
    ok(tag + " aucune course ce mois-là : « 0,00 € » et « 0 km » (vrai zéro : aucune course faite), pas « inconnu »", txt("#cal-eur") == "0,00 €" and txt("#cal-km") == "0 km")
    tap('#s-calendrier [data-a="month"][data-d="1"]')
    ok(tag + " retour au mois du Bilan : le résumé d'Alpha est revenu", txt("#cal-count") == str(qa[0]) and txt("#cal-eur") == "•••• €")
    tap('.screen.on [data-a="back"]')
    ok(tag + " « Retour » depuis ce calendrier : on revient au BILAN (pas à la fiche), vue « Totaux », même mois %s %d, montants masqués" % (MOIS[PM.month - 1], PM.year), cur() == "bilan" and pg.locator('[data-a="bview"][data-v="tot"].on').count() == 1 and mois() == "%s %d" % (MOIS[PM.month - 1], PM.year) and txt("#bil-eur") == "•••• €" and lit() == "Bilan", (cur(), mois()))
    tap('#bil-persons .pp[data-pid="%s"]' % C["id"])
    ok(tag + " personne ARCHIVÉE (Gamma Trois) : son calendrier s'ouvre aussi, résumé 1 course faite", cur() == "calendrier" and txt("#s-calendrier .sub") == "Gamma Trois" and txt("#cal-count") == "1")
    pg.evaluate("history.back()"); w()
    ok(tag + " touche Retour d'Android depuis ce calendrier : retour au Bilan", cur() == "bilan" and mois() == "%s %d" % (MOIS[PM.month - 1], PM.year))
    bilan("tot", PM2); tap('#bil-persons .pp[data-pid="%s"]' % E["id"]); tap('[data-a="calreveal"]')
    ok(tag + " Epsilon Cinq (2 courses sans prix ni km) : résumé « inconnu » / « inconnu » et « + 2 courses sans prix… »", cal_lbl() == "%s %d" % (MOIS[PM2.month - 1], PM2.year) and txt("#cal-eur") == "inconnu" and txt("#cal-km") == "inconnu" and "+ 2 courses sans prix (total partiel)" in txt("#cal-notes") and "+ 2 courses sans km (total partiel)" in txt("#cal-notes"), (txt("#cal-eur"), txt("#cal-notes")))
    tap('.screen.on [data-a="back"]')
    ok(tag + " « Retour » : Bilan sur le mois d'où l'on vient (%s %d)" % (MOIS[PM2.month - 1], PM2.year), cur() == "bilan" and mois() == "%s %d" % (MOIS[PM2.month - 1], PM2.year))
    bilan("tot", PM); tap('#bil-persons .pp[data-pid="%s"]' % B["id"]); tap('[data-a="calreveal"]')
    qb = per[B["id"]]
    ok(tag + " Beta Deux : %s, %s, notes « + 1 course sans prix… · + 1 course sans km… »" % (euros(qb[1]), km2(qb[3])), txt("#cal-eur") == euros(qb[1]) and txt("#cal-km") == km2(qb[3]) and txt("#cal-notes") == "+ %s (total partiel) · + %s (total partiel)" % (sans(qb[2], "prix"), sans(qb[4], "km")), (txt("#cal-eur"), txt("#cal-notes")))
    pg.evaluate("document.querySelector('#s-calendrier [data-a=\"hide\"]').click()"); w()
    ok(tag + " œil sur ce calendrier (montant affiché) : « Agenda » seul, rien de lisible", masked() and pg.evaluate("document.getElementById('veil').innerText.trim()") == "Agenda")
    pg.locator("#veil").tap(); w()
    ok(tag + " un toucher rouvre : le montant du résumé est de nouveau masqué (« •••• € »)", txt("#cal-eur") == "•••• €")
    tap('.screen.on [data-a="back"]')
    goto("personnes"); tap('#plist .list-item:has-text("Alpha")'); tap('[data-a="calfiche"]')
    ok(tag + " calendrier ouvert depuis la FICHE : le résumé est aussi en haut (mois en cours), origine « fiche », onglet Personnes allumé", cur() == "calendrier" and pg.evaluate("__ag.calFrom") == "fiche" and pg.locator("#cal-sum").count() == 1 and cal_lbl() == "%s %d" % (MOIS[CM.month - 1], CM.year) and lit() == "Personnes")
    tap('.screen.on [data-a="back"]')
    ok(tag + " « Retour » depuis la fiche : on revient à la FICHE d'Alpha (pas au Bilan)", cur() == "fiche" and pg.input_value("#f-nom") == "Alpha")
    bilan("tot", PM)

    # ================= 3. Jour par jour : mois précédent =================
    bilan("jj", PM)
    rows_exp, nonote_exp = model_days(RIDES, PM, TODAY)
    got = jj_rows()
    ok(tag + " Jour par jour : une ligne par jour AVEC des personnes concernées (%d jours), « mar 6 » puis « prénom oui / non / pas noté »" % len(rows_exp), [[g[0], g[1], [tuple(x) for x in g[2]]] for g in got] == [[r[0], r[1], r[2]] for r in rows_exp], [(g, r) for g, r in zip(got, rows_exp) if [g[0], g[1], [tuple(x) for x in g[2]]] != [r[0], r[1], r[2]]][:2])
    ok(tag + " « %d jours sans note » (jours passés où une course était prévue et où rien n'a été noté)" % nonote_exp, txt("#jj-sum") == "%d %s sans note" % (nonote_exp, "jours" if nonote_exp > 1 else "jour"), txt("#jj-sum"))
    ok(tag + " jours sans course prévue ni notée (week-ends) : pas de ligne", all(datetime.fromisoformat(g[0]).isoweekday() <= 5 or g[0] in {r["date"] for r in RIDES} for g in got))
    d5 = [g for g in got if g[0] == md(PM, 5).isoformat()][0]
    ok(tag + " plusieurs personnes le même jour (le %s) : NOM COMPLET « Alpha Un » et « Zeta Un » (nom puis prénom, comme « Par personne »), aucun prénom seul" % md(PM, 5), sorted(x[0] for x in d5[2] if x[0].endswith(" Un")) == ["Alpha Un", "Zeta Un"] and all(" " in x[0] for g in got for x in g[2]), d5)
    lay = pg.evaluate("""(iso)=>{const r=document.querySelector('#jj-list .jjrow[data-iso="'+iso+'"]'),ps=[...r.querySelectorAll('.jjp')],b=ps.map(e=>e.getBoundingClientRect()),n=ps.map(e=>e.querySelector('.name').getBoundingClientRect()),w=ps.map(e=>e.querySelector('.jjr').getBoundingClientRect());
      const f=document.querySelector('#bil-persons') ? 0 : 0; return {days:r.querySelectorAll('.jjday').length,n:ps.length,stack:b.every((x,i)=>i===0||x.top>b[i-1].top+10),right:w.every((x,i)=>x.left>n[i].left+20&&Math.abs(x.right-b[i].right)<3),nom:ps.every(e=>e.querySelector('.name .nom')&&e.querySelector('.name .pre')),
      fs:getComputedStyle(ps[0].querySelector('.name .nom')).fontSize+'/'+getComputedStyle(ps[0].querySelector('.name .pre')).fontSize}}""", md(PM, 5).isoformat())
    ok(tag + " mise en page : la date UNE seule fois, UNE LIGNE PAR PERSONNE (l'une sous l'autre), « oui » / « non » / « pas noté » à DROITE de chaque nom", lay["days"] == 1 and lay["n"] >= 2 and lay["stack"] and lay["right"] and lay["nom"], lay)
    d9 = [g for g in got if g[0] == md(PM, 9).isoformat()][0]
    ok(tag + " « pas fait » = « non » (lisible à voix haute) ; la personne archivée garde sa course passée (« Gamma Trois oui »)", ("Alpha Un", "non") in [tuple(x) for x in d9[2]] and ("Gamma Trois", "oui") in [tuple(x) for g in got if g[0] == md(PM, 14).isoformat() for x in g[2]])
    d10 = [g for g in got if g[0] == md(PM, 10).isoformat()]
    ok(tag + " la course à la corbeille (le %s) n'existe plus : « Alpha Un » y est « pas noté » (carte prévue)" % md(PM, 10), (not d10) or ("Alpha Un", "pas noté") in [tuple(x) for x in d10[0][2]])
    pg.screenshot(path=SHOTS + "/bilan_jour_%dx%d_%s.png" % (W, H, SCHEME))
    ok(tag + " mots affichés en toutes lettres (« oui », « non », « pas noté »), pas seulement des icônes", all(x[1] in ("oui", "non", "pas noté", "à faire") for g in got for x in g[2]))
    day_iso = md(PM, 9).isoformat()
    tap('#jj-list .jjrow[data-iso="%s"]' % day_iso)
    ok(tag + " toucher un jour ouvre CE jour dans Aujourd'hui (le %s)" % day_iso, cur() == "aujourdhui" and pg.evaluate("__ag.day") == day_iso and "Un" in pg.locator("#s-aujourdhui").inner_text(), (cur(), pg.evaluate("__ag.day")))
    ok(tag + " … avec la course notée « pas fait » d'Alpha ce jour-là", pg.locator('#s-aujourdhui .frow:has(.nom:text-is("Alpha")) .rnd.ko.on').count() == 1)
    bilan("jj", None)
    ok(tag + " retour au Bilan : on retrouve « Jour par jour » et le même mois", mois() == "%s %d" % (MOIS[PM.month - 1], PM.year) and pg.locator('[data-a="bview"][data-v="jj"].on').count() == 1)

    # ================= 4. Jour par jour : mois en cours (aujourd'hui) =================
    bilan("jj", CM)
    rows_exp, nonote_exp = model_days(RIDES, CM, TODAY)
    got = jj_rows()
    ok(tag + " mois en cours : lignes conformes (aujourd'hui compris : « oui » pour la course faite, « à faire » pour les cartes pas encore notées), aucun jour à venir", [[g[0], g[1], [tuple(x) for x in g[2]]] for g in got] == [[r[0], r[1], r[2]] for r in rows_exp] and all(g[0] <= TISO for g in got), [(g, r) for g, r in zip(got, rows_exp) if [g[0], g[1], [tuple(x) for x in g[2]]] != [r[0], r[1], r[2]]][:2])
    ok(tag + " « %d jours sans note » : aujourd'hui n'est jamais compté (la journée n'est pas finie)" % nonote_exp, txt("#jj-sum") == "%d %s sans note" % (nonote_exp, "jours" if nonote_exp > 1 else "jour"), txt("#jj-sum"))
    bilan("jj", NM)
    ok(tag + " mois à venir : « Rien à afficher ce mois-ci. » et « 0 jour sans note »", "Rien à afficher ce mois-ci." in pg.locator("#jj-list").inner_text() and txt("#jj-sum") == "0 jour sans note")
    bilan("tot", CM)

    # ================= 5. Réglages inchangé, rien pour le père =================
    tap('[data-a="reglages"]')
    ok(tag + " la ligne « Réglages » du Bilan ouvre toujours Réglages ; « Retour » revient au Bilan", cur() == "reglages")
    tap('.screen.on [data-a="back"]')
    ok(tag + " … retour au Bilan (même vue et même mois)", cur() == "bilan" and mois() == "%s %d" % (MOIS[CM.month - 1], CM.year))
    bt = pg.evaluate("document.getElementById('s-bilan').innerText.toLowerCase()")
    ok(tag + " aucun bouton ni mot « père », « copier », « envoyer », « partager », « WhatsApp » sur le Bilan", not re.search(r"père|copier|envoyer|partager|whatsapp|sms|mail", bt), bt[:200])
    app = (ROOT / "app.js").read_text(encoding="utf-8")
    i0 = app.index("/* ========= Bilan :"); i1 = app.index("/* ========= Réglages =========")
    ok(tag + " code du Bilan : ni copie dans le presse-papiers, ni partage, ni envoi (clipboard, share, mailto, sms:, whatsapp, fetch)", not re.search(r"clipboard|copyText|navigator\.share|mailto:|sms:|whatsapp|fetch\(|XMLHttpRequest|sendBeacon", app[i0:i1], re.I))

    # ================= 6. masquage =================
    bilan("tot", PM); tap('[data-a="reveal"]')
    ok(tag + " montants affichés avant masquage", re.search(r"\d", txt("#bil-eur")) is not None)
    tap('.screen.on [data-a="hide"]')
    vt = pg.evaluate("document.getElementById('veil').innerText.trim()")
    pts = pg.evaluate("""()=>{let n=0,c=0;for(let x=10;x<innerWidth;x+=Math.floor(innerWidth/6))for(let y=10;y<innerHeight;y+=Math.floor(innerHeight/8)){n++;const e=document.elementFromPoint(x,y);if(e&&e.closest('#veil'))c++}return [n,c]}""")
    ok(tag + " œil sur le Bilan (Totaux, montants affichés) : « Agenda » seul, plein écran, Bilan inerte", masked() and vt == "Agenda" and pts[0] == pts[1] and pg.evaluate("document.getElementById('views').inert"), (vt, pts))
    ok(tag + " … et les montants se sont recachés dessous (aucun chiffre d'euros dans la page)", txt("#bil-eur") == "•••• €" and all(r[2] == "•••• €" for r in pers_rows()))
    pg.locator("#veil").tap(); w()
    ok(tag + " un toucher rouvre : montants toujours masqués", not masked() and txt("#bil-eur") == "•••• €")
    tap('[data-a="bview"][data-v="jj"]')
    tap('.screen.on [data-a="hide"]')
    vt = pg.evaluate("document.getElementById('veil').innerText.trim()")
    ok(tag + " œil sur « Jour par jour » : « Agenda » seul, aucun nom lisible", masked() and vt == "Agenda" and not re.search(r"Alpha|Beta|Gamma|Delta|Zeta|Un|Deux|Trois|Quatre", vt))
    pg.locator("#veil").tap(); w()
    jump(125000); pg.wait_for_timeout(1700)
    ok(tag + " 2 minutes simulées sur le Bilan : masqué tout seul, rien de lisible", masked() and pg.evaluate("document.getElementById('veil').innerText.trim()") == "Agenda")
    pg.locator("#veil").tap(); w()

    # ================= 7. zones de toucher =================
    AUD = """()=>{const app=document.getElementById('app').getBoundingClientRect(), out=[];
      document.querySelectorAll('.screen.on button').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width||e.closest('[hidden]'))return;
        const tool=e.classList.contains('tool')&&e.closest('.tools.row');
        if(r.height<(tool?27.5:43.5)||r.width<43.5)out.push('PETIT '+(e.dataset.a||e.textContent.trim().slice(0,14))+' '+r.width.toFixed(0)+'x'+r.height.toFixed(0));
        if(r.right>app.right+.5||r.left<app.left-.5)out.push('DEBORDE '+(e.dataset.a||e.textContent.trim().slice(0,14)))});
      const c=document.querySelector('.screen.on .content');if(c.scrollWidth>c.clientWidth+1)out.push('LARGEUR '+c.scrollWidth+'>'+c.clientWidth);return out}"""
    bilan("jj", PM); z = pg.evaluate(AUD)
    ok(tag + " Jour par jour : zones de 44 px (chaque ligne de jour se touche), rien qui déborde à %d px" % W, not z, z)
    bilan("tot", PM); tap('[data-a="reveal"]'); z = pg.evaluate(AUD)
    ok(tag + " Totaux : zones de 44 px, rien qui déborde", not z, z)
    tap('[data-a="reveal"]')

    # ================= 8. persistance et hors connexion =================
    before = (txt("#bil-count"), mois())
    pg.close(); pg = cx.new_page(); pg.on("pageerror", lambda e: errs.append("pageerror " + str(e))); boot()
    bilan("tot", PM)
    ok(tag + " fermeture et réouverture : mêmes totaux (%s courses)" % before[0], txt("#bil-count") == before[0] == str(tot[0]))
    pg.wait_for_function("!!navigator.serviceWorker.controller"); pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.wait_for_timeout(500)
    cx.set_offline(True)
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready", timeout=15000); pg.evaluate("window.__ag.ready"); w()
    bilan("tot", PM); tap('[data-a="reveal"]')
    ok(tag + " MODE AVION : le Bilan se calcule (total %s)" % euros(tot[1]), txt("#bil-count") == str(tot[0]) and txt("#bil-eur") == euros(tot[1]))
    cx.set_offline(False)
    ok(tag + " aucune erreur JavaScript", not errs, errs)
    outside = [u for u in reqs if not u.startswith(BASE) and not u.startswith("data:") and not u.startswith("blob:")]
    ok(tag + " aucune requête hors de l'appli (%d requêtes)" % len(reqs), not outside, outside)
    b.close()

    # ================= 9. jours autour du 25 octobre 2026 (changement d'heure) =================
    b = p.chromium.launch(channel="msedge", headless=True)
    target = datetime(2026, 10, 27, 11, 0, tzinfo=timezone.utc).timestamp() * 1000      # mardi 27 octobre 2026, 12 h à Bruxelles (heure d'hiver)
    cx3 = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, color_scheme=SCHEME, timezone_id="Europe/Brussels", locale="fr-FR")
    cx3.add_init_script("window.__off=%d-Date.now(); window.__freeze=false; (function(){ var n=Date.now.bind(Date); Date.now=function(){ return n()+window.__off; }; })();" % int(target))
    pd = cx3.new_page(); derrs = []
    pd.on("pageerror", lambda e: derrs.append(str(e)))
    pd.goto(BASE); pd.wait_for_function("window.__ag && window.__ag.ready"); pd.evaluate("window.__ag.ready")
    OCT = date(2026, 10, 1); DIM = person(11, "Dimanche", "Seul", [7], "08:00"); TOUS = person(12, "Quotidien", "Tous", [1, 2, 3, 4, 5, 6, 7], "15:00")
    R3 = [ride(TOUS["id"], date(2026, 10, d), DONE, 500, 1000) for d in (24, 25, 26)] + [ride(DIM["id"], date(2026, 10, 25), DONE, 300, 2000, time="08:00")]
    pd.evaluate("""async([ps,rs])=>{ for(const p of ps) await AG.putPerson(p); await AG.putSetting('idle_sec',0); await new Promise(f=>{const t=AG.db.transaction('rides','readwrite');rs.forEach(r=>t.objectStore('rides').put(r));t.oncomplete=f}) }""", [[DIM, TOUS], R3])
    pd.reload(); pd.wait_for_function("window.__ag && window.__ag.ready"); pd.evaluate("window.__ag.ready"); pd.wait_for_timeout(400)
    pd.locator('.nav button.t[data-t="bilan"]').tap(); pd.wait_for_timeout(400)
    ok(tag + " horloge simulée au mardi 27 octobre 2026 : le Bilan s'ouvre sur « octobre 2026 »", pd.locator("#bil-month").inner_text().lower() == "octobre 2026" and pd.evaluate("__ag.bilan.month") == "2026-10-01")
    pd.locator('[data-a="bview"][data-v="jj"]').tap(); pd.wait_for_timeout(400)
    got = pd.evaluate("[...document.querySelectorAll('#jj-list .jjrow')].map(r=>[r.dataset.iso,r.querySelector('.jjday').textContent.trim(),[...r.querySelectorAll('.jjp')].map(s=>[s.querySelector('.name').textContent.trim(),s.querySelector('.jjw').textContent.trim()])])")
    byd = {g[0]: g for g in got}
    ok(tag + " octobre 2026 : les jours 24, 25 et 26 ont chacun UNE ligne, « sam 24 », « dim 25 », « lun 26 » (rien de sauté ni compté deux fois)", [byd[k][1] for k in ("2026-10-24", "2026-10-25", "2026-10-26")] == ["sam 24", "dim 25", "lun 26"] and len([g for g in got if g[0] in ("2026-10-24", "2026-10-25", "2026-10-26")]) == 3, [(g[0], g[1]) for g in got if "10-2" in g[0]])
    ok(tag + " dimanche 25 : « Dimanche Seul oui » (course faite, 8 h) puis « Quotidien Tous oui » (15 h) ; lundi 26 : « Quotidien Tous oui » seulement (« Dimanche Seul » n'est prévu que le dimanche)", [tuple(x) for x in byd["2026-10-25"][2]] == [("Dimanche Seul", "oui"), ("Quotidien Tous", "oui")] and [tuple(x) for x in byd["2026-10-26"][2]] == [("Quotidien Tous", "oui")], (byd["2026-10-25"], byd["2026-10-26"]))
    ok(tag + " mardi 27 (jour courant) : « à faire » pour les cartes pas encore notées, pas compté dans « jours sans note »", byd["2026-10-27"][1] == "mar 27" and ("Quotidien Tous", "à faire") in [tuple(x) for x in byd["2026-10-27"][2]])
    pd.locator('[data-a="bview"][data-v="tot"]').tap(); pd.wait_for_timeout(400)
    ok(tag + " Totaux d'octobre : 4 courses faites (3 de « Quotidien » + 1 de « Dimanche »), 5 km (3 x 1 + 2)", pd.locator("#bil-count").inner_text() == "4" and pd.locator("#bil-km").inner_text() == "5 km", (pd.locator("#bil-count").inner_text(), pd.locator("#bil-km").inner_text()))
    ok(tag + " aucune erreur JavaScript (changement d'heure)", not derrs, derrs)
    b.close()

    # ================= 10. plusieurs milliers de courses =================
    b = p.chromium.launch(channel="msedge", headless=True)
    cx4 = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, color_scheme=SCHEME, service_workers="allow")
    cx4.add_init_script(INIT)
    pb = cx4.new_page(); berrs = []
    pb.on("pageerror", lambda e: berrs.append(str(e)))
    pb.goto(BASE); pb.wait_for_function("window.__ag && window.__ag.ready"); pb.evaluate("window.__ag.ready")
    PP = [person(21 + k, "Nom%d" % k, "Prenom%d" % k, [[1, 2, 3, 4, 5], [1, 3, 5], [2, 4]][k % 3]) for k in range(9)]
    BIG = []; N0 = 5000000
    start = add_month(CM, -24)
    for mi in range(24):
        first = add_month(start, mi)
        for d in range(1, 29):
            for k, pp in enumerate(PP):
                st = DONE if (d + k + mi) % 5 != 0 else NOT
                price = None if (d + k) % 11 == 0 else 1000 + (d * 13 + k * 7 + mi) % 500
                km = None if (d * (k + 1)) % 13 == 0 else 5000 + (d * 17 + k * 3) % 4000
                dele = "2026-02-01T00:00:00.000Z" if (d + mi) % 17 == 0 else None
                r = ride(pp["id"], first.replace(day=d), st, price, km, deleted=dele); r["id"] = "00000000-0000-4000-9000-%012d" % (N0 + len(BIG)); BIG.append(r)
    pb.evaluate("""async([ps,rs])=>{ for(const p of ps) await AG.putPerson(p); await new Promise(f=>{const t=AG.db.transaction('rides','readwrite');rs.forEach(r=>t.objectStore('rides').put(r));t.oncomplete=f}) }""", [PP, BIG])
    t0 = time.time(); pb.reload(); pb.wait_for_function("window.__ag && window.__ag.ready"); pb.evaluate("window.__ag.ready"); pb.wait_for_timeout(200)
    t_ready = time.time() - t0
    n_all = pb.evaluate("""new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const g=q.result.transaction('rides').objectStore('rides').count();g.onsuccess=()=>{q.result.close();r(g.result)}}})""")
    ok(tag + " %d courses fictives sur 24 mois en base ; l'appli s'ouvre (base prête) en %.1f s" % (n_all, t_ready), n_all == len(BIG) and len(BIG) > 5000 and t_ready < 10, (n_all, t_ready))
    pb.locator('.nav button.t[data-t="bilan"]').tap(); pb.wait_for_timeout(500)
    worst = 0; badtot = []; badrange = []
    for mi in (3, 11, 17, 22):
        target_first = add_month(start, mi)
        for _ in range(40):
            if pb.evaluate("__ag.bilan.month") == target_first.isoformat(): break
            pb.locator('[data-a="bmonth"][data-d="%d"]' % (1 if pb.evaluate("__ag.bilan.month") < target_first.isoformat() else -1)).tap(); pb.wait_for_timeout(120)
        pb.wait_for_timeout(250)
        ms = pb.evaluate("__ag.bilanMs"); worst = max(worst, ms)
        n_month = len([r for r in BIG if r["date"].startswith(target_first.isoformat()[:7])])
        rng = pb.evaluate("AG.lastRangeCount")
        if rng != n_month or rng > 400: badrange.append((target_first.isoformat(), rng, n_month))
        tt, _pp = expected_totals(BIG, target_first, PP)
        got = pb.evaluate("[document.getElementById('bil-count').textContent, document.getElementById('bil-km').textContent, document.getElementById('bil-eur-note').textContent, document.getElementById('bil-km-note').textContent]")
        exp = [str(tt[0]), km2(tt[3]), "+ %s (total partiel)" % sans(tt[2], "prix"), "+ %s (total partiel)" % sans(tt[4], "km")]
        if got != exp: badtot.append((target_first.isoformat(), got, exp))
        pb.locator('[data-a="reveal"]').tap(); pb.wait_for_timeout(250)
        if pb.locator("#bil-eur").inner_text().strip() != euros(tt[1]): badtot.append((target_first.isoformat(), "euros", pb.locator("#bil-eur").inner_text(), euros(tt[1])))
        pb.locator('[data-a="reveal"]').tap(); pb.wait_for_timeout(150)
    ok(tag + " 4 mois pris au hasard sur 24 : courses faites, km, notes « sans prix / sans km » et euros EXACTEMENT ceux calculés à part sur les %d courses" % len(BIG), not badtot, badtot[:2])
    ok(tag + " lecture par l'INDEX des dates : seules les courses du mois choisi sont lues (~%d sur %d), jamais toute la base" % (n_month, len(BIG)), not badrange, badrange[:2])
    ok(tag + " temps d'affichage du Bilan pour un mois : au pire %d ms (limite 500 ms)" % worst, worst < 500, worst)
    pb.locator('[data-a="bview"][data-v="jj"]').tap(); pb.wait_for_timeout(400)
    ms2 = pb.evaluate("__ag.bilanMs")
    ok(tag + " « Jour par jour » d'un mois chargé : %d ms (limite 500 ms), %d lignes" % (ms2, pb.locator("#jj-list .jjrow").count()), ms2 < 500 and pb.locator("#jj-list .jjrow").count() >= 20, ms2)
    ok(tag + " aucune erreur JavaScript (beaucoup de courses)", not berrs, berrs)
    b.close()
    srv.shutdown()
print("TOTAL", total, "ECHECS", fails)
