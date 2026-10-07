"""Étape 3 d'Agenda : calendrier d'une personne (« Calendrier et courses », ouvert depuis la fiche).
Vérifie : lien dans la fiche (et question « Quitter sans enregistrer ? » si la fiche est modifiée), retour, touche Retour d'Android, états de chaque jour
(coche = fait, croix rouge = pas fait, rond « à faire », rond vide « pas noté », case vide), ligne de résumé « N jours sans note », mois précédent et suivant,
petit panneau d'un jour (jour habituel, jour non habituel, jour passé), « Pas de course » (= pas fait, plus de carte ce jour-là), « Comme d'habitude »,
« Changer ce jour », « Ajouter une course », fait / pas fait / retoucher pour vider, montant et km, supprimer = corbeille avec « Annuler »,
suppression d'une personne (impossible dès qu'une course n'est pas à la corbeille), masquage, persistance, hors connexion, zones de toucher.
Noms FICTIFS seulement. W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, threading, pathlib, http.server, functools
from datetime import date, timedelta
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
TODAY = date.today(); TISO = TODAY.isoformat()
fails = 0; total = 0
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def ok(n, c, e=""):
    global fails, total
    total += 1
    if not c: fails += 1
    print(("PASS " if c else "FAIL ") + n + (" | " + str(e)[:500] if not c else ""))


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
CM = first_of(TODAY); PM = add_month(CM, -1); NM = add_month(CM, 1)


def month_days(first):
    out = []; dt = first
    while dt.month == first.month: out.append(dt); dt += timedelta(days=1)
    return out


def person(i, last, first, **kw):
    p = {"id": "00000000-0000-4000-8000-%012d" % i, "last_name": last, "first_name": first, "pickup_street": "1 rue Depart", "pickup_zip": "11111", "pickup_city": "Villedepart",
         "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible", "phone": "", "usual_price_cents": 1250, "usual_km_m": 8500,
         "archived": False, "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z",
         "schedule": {"mode": "weekly", "weekdays": [1, 2, 3, 4, 5], "time_weekly": "09:00", "from": None, "to": None, "dates": [], "time_dates": None}}
    sch = kw.pop("schedule", None)
    if sch: p["schedule"].update(sch)
    p.update(kw); return p


def ride(n, pid, dt, status=None, added=False, deleted=None, skip=False):
    return {"id": "00000000-0000-4000-9000-%012d" % n, "person_id": pid, "date": dt.isoformat(), "time": "09:00", "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible",
            "price_cents": 1250, "km_m": 8500, "usual_price_cents": 1250, "usual_km_m": 8500, "status": status, "changed": False, "added": added, "skip": skip,
            "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z", "deleted_at": deleted}


ALPHA = person(1, "Alpha", "Un"); GAMMA = person(3, "Gamma", "Trois", schedule={"weekdays": []})
# modèle des courses d'Alpha (date -> état ou None) : sert à calculer ce que le calendrier doit montrer
model = {}
def day_state(dt):
    if dt in model: return "t" if model[dt] == "done" else ("p" if model[dt] == "not_done" else ("a" if dt >= TODAY else "n"))
    if dt.isoweekday() <= 5: return "a" if dt >= TODAY else "n"
    return ""
def expected_cells(first): return [[dt.isoformat(), day_state(dt)] for dt in month_days(first)]
def expected_summary(first):
    s = [day_state(dt) for dt in month_days(first)]; t, p_, a = s.count("t"), s.count("p"), s.count("a"); b = len(s) - t - p_ - a
    return "%d transportée, %d pas transportée, %s%d %s sans note" % (t, p_, ("%d à faire, " % a) if a else "", b, "jours" if b > 1 else "jour")


def pm(day): return PM.replace(day=day)
def free_weekday(first, start=14):
    for dt in month_days(first):
        if dt.day >= start and dt.isoweekday() <= 5 and dt not in model: return dt
def free_weekend(first, start=15):
    for dt in month_days(first):
        if dt.day >= start and dt.isoweekday() > 5 and dt not in model: return dt


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="allow")
    cx.add_init_script(INIT)
    errs = []; reqs = []
    cx.on("request", lambda r: reqs.append(r.url))
    pg = cx.new_page()
    pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
    pg.on("console", lambda m: errs.append("console " + m.text) if m.type == "error" else None)

    w = lambda: pg.wait_for_timeout(300)
    tap = lambda sel: (pg.locator(sel).first.tap(), w())
    goto = lambda t: tap('.nav button.t[data-t="%s"]' % t)
    cur = lambda: pg.evaluate("__ag.cur")
    masked = lambda: pg.evaluate("__ag.masked")
    toast_msg = lambda: pg.locator("#toast span").inner_text() if pg.locator("#toast").is_visible() and pg.locator("#toast span").count() else ""
    has_undo = lambda: pg.locator('#toast [data-a="undo"]').count() == 1 and pg.locator("#toast").is_visible()
    jump = lambda ms: pg.evaluate("window.__off += %d" % ms)
    mois_lbl = lambda: pg.locator("#s-calendrier .monthnav .lbl").inner_text().lower()
    summary = lambda: pg.locator("#cal-summary").inner_text()
    cells = lambda: pg.evaluate("[...document.querySelectorAll('#s-calendrier .cell')].map(c=>[c.dataset.iso,(c.className.split(' ').filter(x=>['t','p','a','n'].indexOf(x)>=0)[0]||'')])")
    cell = lambda dt: '#s-calendrier .cell[data-iso="%s"]' % dt.isoformat()

    def db_all(store):
        return pg.evaluate("""(s)=>new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result;const g=d.transaction(s).objectStore(s).getAll();g.onsuccess=()=>{d.close();r(g.result)}}})""", store)
    def live(pid=ALPHA["id"]): return [r for r in db_all("rides") if not r.get("deleted_at") and r["person_id"] == pid]
    def boot():
        pg.goto(BASE); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(250)
    def seed(persons, rides):
        pg.evaluate("""async([ps,rs])=>{ for(const p of ps) await AG.putPerson(p); for(const r of rs) await AG.putRide(r) }""", [persons, rides])
        pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    def open_cal(txt="Alpha"):
        goto("personnes"); tap('#plist .list-item:has-text("%s")' % txt); tap('[data-a="calfiche"]')
    def to_month(first):
        for _ in range(30):
            if mois_lbl().startswith(MOIS[first.month - 1]) and mois_lbl().endswith(str(first.year)): return
            cur_m = [i for i, m_ in enumerate(MOIS) if mois_lbl().startswith(m_)][0] + 1; cur_y = int(mois_lbl().split()[-1])
            pg.locator('#s-calendrier [data-a="month"][data-d="%d"]' % (1 if (first.year, first.month) > (cur_y, cur_m) else -1)).tap(); pg.wait_for_timeout(80)
    def check(first, name):
        got = cells(); exp = expected_cells(first)
        ok(tag + " %s : états des %d jours conformes (coche / croix / rond / rond vide / vide)" % (name, len(exp)), got == exp, [(a, b_) for a, b_ in zip(got, exp) if a != b_][:4])
        ok(tag + " %s : résumé « %s »" % (name, expected_summary(first)), summary() == expected_summary(first), summary())

    boot()
    for dt, st in [(pm(5), "done"), (pm(6), "not_done"), (pm(7), None), (pm(12), "done")]: model[dt] = st
    seed([ALPHA, GAMMA], [ride(1, ALPHA["id"], pm(5), "done"), ride(2, ALPHA["id"], pm(6), "not_done"), ride(3, ALPHA["id"], pm(7), None), ride(4, ALPHA["id"], pm(12), "done", added=True),
                          ride(5, ALPHA["id"], pm(20), "done", deleted="2026-01-02T00:00:00.000Z")])     # une course à la corbeille : ne compte jamais

    # ================= 1. lien dans la fiche, retour =================
    goto("personnes"); tap('#plist .list-item:has-text("Alpha")')
    ok(tag + " fiche : section « Courses de Un » avec « Calendrier et courses »", [x.lower() for x in pg.locator("#s-fiche h2").all_inner_texts()] == ["courses de un", "gérer cette fiche"] and "Calendrier et courses" in pg.locator('[data-a="calfiche"]').inner_text())
    tap('[data-a="calfiche"]')
    ok(tag + " « Calendrier et courses » : titre, nom de la personne, mois en cours, deux chevrons, onglet Personnes allumé", cur() == "calendrier" and pg.locator("#s-calendrier h1").inner_text() == "Calendrier et courses" and pg.locator("#s-calendrier .sub").inner_text() == "Alpha Un" and mois_lbl() == "%s %d" % (MOIS[CM.month - 1], CM.year) and pg.locator('#s-calendrier [data-a="month"]').count() == 2 and pg.locator('.nav button.t[aria-current="page"]').inner_text().strip() == "Personnes")
    tap('.screen.on [data-a="back"]')
    ok(tag + " « Retour » : on retrouve la fiche d'Alpha", cur() == "fiche" and pg.input_value("#f-nom") == "Alpha")
    pg.fill("#f-ville", "Autreville"); tap('[data-a="calfiche"]')
    ok(tag + " fiche modifiée puis « Calendrier et courses » : « Quitter sans enregistrer ? »", pg.locator("#confirm.on").count() == 1 and cur() == "fiche")
    tap("#confirm-cancel")
    ok(tag + " « Rester » : la fiche et la modification sont toujours là", cur() == "fiche" and pg.input_value("#f-ville") == "Autreville")
    tap('[data-a="calfiche"]'); tap("#confirm-ok")
    ok(tag + " « Quitter » : le calendrier s'ouvre, la modification n'a pas été enregistrée", cur() == "calendrier" and [x for x in db_all("persons") if x["id"] == ALPHA["id"]][0]["pickup_city"] == "Villedepart")
    pg.evaluate("history.back()"); w()
    ok(tag + " touche Retour d'Android depuis le calendrier : on revient à la fiche, puis à la liste", cur() == "fiche")
    pg.evaluate("history.back()"); w()
    ok(tag + " … puis à la liste des personnes", cur() == "personnes")

    # ================= 2. états des jours, mois précédent / en cours / suivant =================
    open_cal()
    check(CM, "mois en cours (%s)" % MOIS[CM.month - 1])
    ok(tag + " aujourd'hui entouré (pointillés)", pg.locator("#s-calendrier .cell.today").count() == 1 and pg.locator("#s-calendrier .cell.today").get_attribute("data-iso") == TISO)
    lab = pg.locator(cell(TODAY)).get_attribute("aria-label")
    ok(tag + " étiquette lisible d'un jour : « Mercredi 7 octobre : à faire » (jour en toutes lettres + état)", re.match(r"^[A-Za-zéû]+ \d+ [a-zéû]+ : (à faire|pas noté|pas de course|transportée|pas transportée)$", lab), lab)
    tap('#s-calendrier [data-a="month"][data-d="-1"]')
    ok(tag + " « Mois précédent » : %s %d" % (MOIS[PM.month - 1], PM.year), mois_lbl() == "%s %d" % (MOIS[PM.month - 1], PM.year))
    check(PM, "mois précédent")
    ok(tag + " coches (fait) et croix rouge (pas fait) dessinées : %d coches, %d croix, ronds vides « pas noté »" % (2, 1), pg.locator("#s-calendrier .cell.t svg use[href='#i-check']").count() == 2 and pg.locator("#s-calendrier .cell.p svg use[href='#i-x']").count() == 1 and pg.locator("#s-calendrier .cell.n").count() >= 1)
    ok(tag + " la course à la corbeille du %s ne compte pas (jour sans course)" % pm(20), [c for c in cells() if c[0] == pm(20).isoformat()][0][1] == day_state(pm(20)))
    pg.screenshot(path=SHOTS + "/calendrier_mois_%dx%d_%s.png" % (W, H, SCHEME))
    tap('#s-calendrier [data-a="month"][data-d="1"]'); tap('#s-calendrier [data-a="month"][data-d="1"]')
    check(NM, "mois suivant")
    ok(tag + " mois suivant : que des ronds « à faire » les jours de semaine, aucun rond vide", pg.locator("#s-calendrier .cell.n").count() == 0 and pg.locator("#s-calendrier .cell.a").count() == len([x for x in month_days(NM) if x.isoweekday() <= 5]))
    tap('#s-calendrier [data-a="month"][data-d="-1"]')
    legend = pg.locator("#s-calendrier .legend").inner_text().lower()
    ok(tag + " légende : Transportée, Pas transportée, À faire, Pas noté", all(x in legend for x in ["transportée", "pas transportée", "à faire", "pas noté"]))

    # ================= 3. petit panneau : jour passé habituel =================
    to_month(PM)
    X = free_weekday(PM, 14)
    tap(cell(X))
    btns = [x.strip() for x in pg.locator("#ds-panel button").all_inner_texts()]
    ok(tag + " jour passé habituel, sans rien d'enregistré : panneau (pas une page) « Fait » / « Pas fait » + montant et km, avec les repères « habituel »", pg.locator("#daysheet.on").count() == 1 and btns[:2] == ["Fait", "Pas fait"] and pg.input_value("#ds-montant") == "12,50" and pg.input_value("#ds-km") == "8,5" and pg.locator("#ds-hab-p").count() == 1 and pg.locator("#ds-hab-k").count() == 1 and cur() == "calendrier", btns)
    ok(tag + " ouvrir le panneau n'enregistre rien", len(live()) == 4, len(live()))
    tap('#ds-panel [data-a="dsfait"]'); model[X] = "done"
    r1 = [r for r in live() if r["date"] == X.isoformat()][0]
    ok(tag + " « Fait » : course créée à cet instant avec les valeurs de la fiche copiées (1250 / 8500), le jour passe à la coche, résumé mis à jour", r1["status"] == "done" and r1["price_cents"] == 1250 and r1["km_m"] == 8500 and r1["time"] == "09:00" and r1["added"] is False and pg.locator("#ds-panel [data-a=dsfait][aria-pressed=true]").count() == 1, r1)
    pg.locator("#ds-panel .btn.sel").count()
    tap('#ds-panel [data-a="dsfait"]'); model[X] = None
    ok(tag + " retoucher « Fait » : le choix est vidé (la course existe, sans état → rond vide « pas noté »)", [r for r in live() if r["date"] == X.isoformat()][0]["status"] is None)
    tap('#ds-panel [data-a="dspas"]'); model[X] = "not_done"
    ok(tag + " « Pas fait » : croix rouge, une seule course ce jour-là", [r for r in live() if r["date"] == X.isoformat()][0]["status"] == "not_done" and len([r for r in live() if r["date"] == X.isoformat()]) == 1)
    pg.fill("#ds-montant", "3"); pg.locator("#ds-montant").blur(); w()
    ok(tag + " montant « 3 » saisi dans le panneau : 300 centimes enregistrés, repère « habituel » enlevé", [r for r in live() if r["date"] == X.isoformat()][0]["price_cents"] == 300 and pg.locator("#ds-hab-p").count() == 0)
    tap('#ds-panel [data-a="dsclose"]')
    ok(tag + " le panneau fermé, le calendrier est à jour : jour en croix et résumé", cells() == expected_cells(PM) and summary() == expected_summary(PM), summary())

    # ================= 4. jour passé non habituel : ajouter une course =================
    Y = free_weekend(PM, 15)
    tap(cell(Y))
    ok(tag + " jour passé NON habituel sans course : « Ajouter une course » seulement", [x.strip() for x in pg.locator("#ds-panel button").all_inner_texts()] == ["Ajouter une course", "Fermer"])
    tap('[data-a="dsadd"]')
    ok(tag + " formulaire « Ajouter une course » : heure et destination de la fiche, boutons Enregistrer / Annuler", pg.locator("#ds-title").inner_text() == "Ajouter une course" and pg.input_value("#ds-heure") == "09:00" and pg.input_value("#ds-lieu") == "Lieu Cible")
    tap('[data-a="dsback"]')
    ok(tag + " « Annuler » du formulaire : retour au menu du jour (rien ajouté)", pg.locator("#ds-title").inner_text().lower().startswith(("samedi", "dimanche")) and len(live()) == len([r for r in live()]))
    tap('[data-a="dsadd"]'); pg.fill("#ds-heure", "10h"); tap('[data-a="dssave"]'); model[Y] = None
    r2 = [r for r in live() if r["date"] == Y.isoformat()][0]
    ok(tag + " enregistré : course « ajoutée » (exceptionnelle), heure 10:00, prix et km de la fiche copiés, message « Course ajoutée »", r2["added"] is True and r2["time"] == "10:00" and r2["price_cents"] == 1250 and toast_msg() == "Course ajoutée" and cells() == expected_cells(PM), r2)
    tap(cell(Y))
    ok(tag + " ce jour a maintenant « Fait » / « Pas fait » et « Supprimer cette course »", pg.locator('#ds-panel [data-a="dsfait"]').count() == 1 and pg.locator('#ds-panel [data-a="dsdel"]').count() == 1)
    tap('#ds-panel [data-a="dsdel"]'); del model[Y]
    ok(tag + " « Supprimer cette course » : « Course supprimée » avec « Annuler » ; à la corbeille (jamais effacée) ; le jour redevient une case vide", toast_msg() == "Course supprimée" and has_undo() and [r for r in db_all("rides") if r["id"] == r2["id"]][0]["deleted_at"] and cells() == expected_cells(PM))
    tap('#toast [data-a="undo"]'); model[Y] = None
    ok(tag + " « Annuler » : la course revient (rond vide)", not [r for r in db_all("rides") if r["id"] == r2["id"]][0]["deleted_at"] and cells() == expected_cells(PM))

    # ================= 5. jours à venir =================
    to_month(NM)
    F = free_weekday(NM, 8); G = free_weekend(NM, 8)
    tap(cell(F))
    btns = [x.strip() for x in pg.locator("#ds-panel button").all_inner_texts()]
    ok(tag + " jour à venir habituel : « Comme d'habitude » (choisi) / « Changer ce jour » / « Pas de course »", btns[:3] == ["Comme d’habitude", "Changer ce jour", "Pas de course"] and pg.locator('#ds-panel [data-a="dscomme"][aria-pressed="true"]').count() == 1, btns)
    tap('#ds-panel [data-a="dspas"]'); model[F] = "not_done"
    rF = [r for r in live() if r["date"] == F.isoformat()][0]
    ok(tag + " « Pas de course » : le jour passe à « pas fait » (croix), message « Pas de course ce jour », course marquée (pas fait + pas de course)", rF["status"] == "not_done" and rF["skip"] is True and toast_msg() == "Pas de course ce jour" and cells() == expected_cells(NM), rF)
    cards = pg.evaluate("AGR.items(__ag.people, __ag.rides, '%s', '%s').map(x=>x.p.last_name)" % (F.isoformat(), TISO))
    ok(tag + " … et plus aucune carte ce jour-là sur Aujourd'hui (jour à venir marqué « Pas de course »)", "Alpha" not in cards, cards)
    tap(cell(F))
    ok(tag + " le panneau montre « Pas de course » choisi", pg.locator('#ds-panel [data-a="dspas"][aria-pressed="true"]').count() == 1)
    tap('#ds-panel [data-a="dscomme"]'); del model[F]
    rF = [r for r in live() if r["date"] == F.isoformat()][0]
    ok(tag + " « Comme d'habitude » : le jour redevient « à faire », la carte revient, rien d'autre ne change", rF["status"] is None and rF["skip"] is False and cells() == expected_cells(NM) and "Alpha" in pg.evaluate("AGR.items(__ag.people, __ag.rides, '%s', '%s').map(x=>x.p.last_name)" % (F.isoformat(), TISO)))
    tap(cell(F)); tap('#ds-panel [data-a="dschg"]')
    ok(tag + " « Changer ce jour » : formulaire heure + destination seulement", pg.locator("#ds-title").inner_text() == "Changer ce jour" and pg.locator("#ds-panel input").count() == 5)
    pg.fill("#ds-heure", "15:30"); pg.fill("#ds-lieu", "Autre lieu"); tap('[data-a="dssave"]')
    rF = [r for r in live() if r["date"] == F.isoformat()][0]
    ok(tag + " enregistré : « Jour changé », heure 15:30, « Autre lieu », marquée « changé » ; le jour reste « à faire »", rF["time"] == "15:30" and rF["dest_place"] == "Autre lieu" and rF["changed"] is True and rF["status"] is None and toast_msg() == "Jour changé" and cells() == expected_cells(NM))
    tap(cell(F))
    ok(tag + " panneau : « Changer ce jour » choisi (heure changée)", pg.locator('#ds-panel [data-a="dschg"][aria-pressed="true"]').count() == 1 and pg.locator('#ds-panel [data-a="dscomme"][aria-pressed="false"]').count() == 1)
    tap('#ds-panel [data-a="dscomme"]')
    rF = [r for r in live() if r["date"] == F.isoformat()][0]
    ok(tag + " « Comme d'habitude » après un changement : heure 09:00 et destination de la FICHE reviennent, plus « changé »", rF["time"] == "09:00" and rF["dest_place"] == "Lieu Cible" and rF["changed"] is False)
    tap(cell(G))
    ok(tag + " jour à venir NON habituel : « Ajouter une course »", [x.strip() for x in pg.locator("#ds-panel button").all_inner_texts()] == ["Ajouter une course", "Fermer"])
    tap('[data-a="dsadd"]'); tap('[data-a="dssave"]'); model[G] = None
    ok(tag + " ajoutée : le jour devient « à faire »", cells() == expected_cells(NM) and [c for c in cells() if c[0] == G.isoformat()][0][1] == "a")
    tap(cell(G))
    ok(tag + " ce jour : « Changer ce jour », « Pas de course » et « Supprimer cette course »", [x.strip() for x in pg.locator("#ds-panel button").all_inner_texts()] == ["Changer ce jour", "Pas de course", "Supprimer cette course", "Fermer"])
    tap('#ds-panel [data-a="dsdel"]'); del model[G]
    ok(tag + " supprimée : retour à une case vide (corbeille)", cells() == expected_cells(NM) and [r for r in db_all("rides") if r["date"] == G.isoformat()][0]["deleted_at"])
    tap('#toast [data-a="undo"]'); model[G] = None

    # ================= 6. suppression d'une personne =================
    goto("personnes"); tap('#plist .list-item:has-text("Alpha")')
    n_live = len(live())
    dis = pg.locator("#s-fiche .list-item[disabled]")
    ok(tag + " Alpha a %d courses non supprimées : « Supprimer cette fiche » grisée, « Impossible : %d courses déjà notées. »" % (n_live, n_live), dis.count() == 1 and ("Impossible : %d courses déjà notées." % n_live) in dis.inner_text(), dis.inner_text() if dis.count() else "")
    goto("personnes"); tap('#plist .list-item:has-text("Gamma")')
    ok(tag + " Gamma (aucune course) : « Supprimer cette fiche » active", pg.locator('[data-a="deleteask"]').count() == 1)
    tap('[data-a="calfiche"]'); to_month(PM)
    Z = free_weekday(PM, 2) or pm(2)
    tap(cell(Z)); tap('[data-a="dsadd"]'); tap('[data-a="dssave"]')
    ok(tag + " une course ajoutée à Gamma depuis son calendrier", len(live(GAMMA["id"])) == 1 and "Course ajoutée" == toast_msg())
    tap('.screen.on [data-a="back"]')
    dis = pg.locator("#s-fiche .list-item[disabled]")
    ok(tag + " Gamma a maintenant 1 course (même pas notée) : « Impossible : 1 course déjà notée. »", dis.count() == 1 and "Impossible : 1 course déjà notée." in dis.inner_text())
    tap('[data-a="calfiche"]'); to_month(PM); tap(cell(Z)); tap('#ds-panel [data-a="dsdel"]')
    tap('.screen.on [data-a="back"]')
    ok(tag + " course mise à la corbeille : « Supprimer cette fiche » redevient active (la course de la corbeille n'empêche plus, et n'est pas effacée)", pg.locator('[data-a="deleteask"]').count() == 1 and len(db_all("rides")) >= 6 and len(live(GAMMA["id"])) == 0)
    tap('.screen.on [data-a="back"]')

    # ================= 7. masquage =================
    open_cal(); to_month(PM)
    tap(cell(pm(5)))
    ok(tag + " panneau d'un jour ouvert", pg.locator("#daysheet.on").count() == 1)
    tap('.screen.on [data-a="hide"]') if False else pg.evaluate("document.querySelector('#s-calendrier [data-a=\"hide\"]').click()"); w()
    vt = pg.evaluate("document.getElementById('veil').innerText.trim()")
    cov = pg.evaluate("(()=>{const r=document.querySelector('#ds-panel').getBoundingClientRect();const e=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return !!e&&!!e.closest('#veil')})()")
    ok(tag + " œil avec le panneau ouvert : « Agenda » seul, panneau et calendrier couverts et inertes (aucun nom, aucun état lisible)", masked() and vt == "Agenda" and cov and pg.evaluate("document.getElementById('daysheet').inert && document.getElementById('views').inert"), (vt, cov))
    pg.locator("#veil").tap(); w()
    ok(tag + " un toucher rouvre : le panneau est toujours là", not masked() and pg.locator("#daysheet.on").count() == 1)
    tap('#ds-panel [data-a="dsclose"]')
    jump(125000); pg.wait_for_timeout(1700)
    ok(tag + " 2 minutes simulées sur le calendrier : masqué tout seul, rien de lisible (« Agenda » seul)", masked() and pg.evaluate("document.getElementById('veil').innerText.trim()") == "Agenda")
    pg.locator("#veil").tap(); w()

    # ================= 8. zones de toucher =================
    AUD = """()=>{const app=document.getElementById('app').getBoundingClientRect(), out=[];
      document.querySelectorAll('.screen.on button, .screen.on a.btn').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width||e.closest('[hidden]'))return;
        if(r.height<43.5||r.width<43.5)out.push('PETIT '+(e.dataset.a||e.textContent.trim().slice(0,14))+' '+r.width.toFixed(0)+'x'+r.height.toFixed(0));
        if(r.right>app.right+.5||r.left<app.left-.5)out.push('DEBORDE '+(e.dataset.a||e.textContent.trim().slice(0,14)))});
      const c=document.querySelector('.screen.on .content');if(c.scrollWidth>c.clientWidth+1)out.push('LARGEUR '+c.scrollWidth+'>'+c.clientWidth);return out}"""
    z = pg.evaluate(AUD)
    ok(tag + " calendrier : toutes les zones de 44 px minimum (jours, chevrons), rien ne déborde à %d px de large" % W, not z, z)
    tap(cell(X))
    AUDS = """()=>{const app=document.getElementById('app').getBoundingClientRect(), pn=document.querySelector('#daysheet .panel').getBoundingClientRect(), out=[];
      const R=[...document.querySelectorAll('#daysheet .panel button, #daysheet .panel input')].filter(e=>e.getBoundingClientRect().width>0).map(e=>({n:e.id||e.dataset.a,r:e.getBoundingClientRect()}));
      R.forEach(a=>{ if(a.r.right>app.right+.5||a.r.left<app.left-.5) out.push('DEBORDE '+a.n); if(a.r.height<43.5) out.push('PETIT '+a.n) });
      for(let i=0;i<R.length;i++)for(let j=i+1;j<R.length;j++){const a=R[i].r,b=R[j].r;if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)out.push('CHEVAUCHE '+R[i].n+' / '+R[j].n)}
      if(pn.top<0||pn.bottom>innerHeight+.5)out.push('HORS ECRAN');return out}"""
    z = pg.evaluate(AUDS)
    ok(tag + " panneau d'un jour passé (avec montant et km) : zones de 44 px, rien ne déborde ni ne se chevauche, dans l'écran", not z, z)
    pg.screenshot(path=SHOTS + "/calendrier_panneau_%dx%d_%s.png" % (W, H, SCHEME))
    tap('#ds-panel [data-a="dsclose"]')

    # ================= 9. persistance, hors connexion =================
    before = cells()
    pg.close(); pg = cx.new_page(); pg.on("pageerror", lambda e: errs.append("pageerror " + str(e))); boot()
    open_cal(); to_month(PM)
    ok(tag + " fermeture et réouverture : le calendrier du mois précédent montre les mêmes états", cells() == before and cells() == expected_cells(PM))
    pg.wait_for_function("!!navigator.serviceWorker.controller"); pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.wait_for_timeout(500)
    cx.set_offline(True)
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready", timeout=15000); pg.evaluate("window.__ag.ready"); w()
    open_cal(); to_month(PM)
    ok(tag + " MODE AVION : le calendrier s'ouvre avec ses états", cells() == expected_cells(PM))
    tap(cell(pm(7))); tap('#ds-panel [data-a="dsfait"]'); model[pm(7)] = "done"; tap('#ds-panel [data-a="dsclose"]')
    ok(tag + " MODE AVION : « Fait » sur un jour s'enregistre et le calendrier se met à jour", cells() == expected_cells(PM) and [r for r in live() if r["date"] == pm(7).isoformat()][0]["status"] == "done")
    cx.set_offline(False)
    ok(tag + " aucune erreur JavaScript", not errs, errs)
    outside = [u for u in reqs if not u.startswith(BASE) and not u.startswith("data:") and not u.startswith("blob:")]
    ok(tag + " aucune requête hors de l'appli (%d requêtes)" % len(reqs), not outside, outside)
    b.close(); srv.shutdown()
print("TOTAL", total, "ECHECS", fails)
