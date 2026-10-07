"""Étape 3 d'Agenda : écran Aujourd'hui (cartes prévues, courses, fait / pas fait, changer ce jour, ajouter une course).
Vérifie : cartes calculées à partir des fiches (« Chaque semaine » avec jours et « Du » / « Au », « Dates choisies »), tri par heure, personne archivée absente,
AUCUNE course enregistrée avant la première action, création à la première action (fait, pas fait, changer, ajouter, corriger montant ou km),
prix, km, heure et destination COPIÉS de la fiche (« habituel »), fait / pas fait / remis à faire, « Annuler » = corbeille (jamais d'effacement),
changer ce jour, course exceptionnelle, supprimer = corbeille, une modification de la fiche ne réécrit jamais une course déjà enregistrée,
archivage, persistance, hors connexion, masquage, jours autour du changement d'heure du 25 octobre 2026.
Noms FICTIFS seulement. W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, threading, pathlib, http.server, functools
from datetime import date, datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
TODAY = date.today(); TISO = TODAY.isoformat()
fails = 0; total = 0
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


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


def d(n): return TODAY + timedelta(days=n)


def person(i, last, first, **kw):
    p = {"id": "00000000-0000-4000-8000-%012d" % i, "last_name": last, "first_name": first, "pickup_street": "1 rue Depart", "pickup_zip": "11111", "pickup_city": "Villedepart",
         "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible", "phone": "0123456789", "usual_price_cents": 1250, "usual_km_m": 8500,
         "archived": False, "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z",
         "schedule": {"mode": "weekly", "weekdays": [1, 2, 3, 4, 5, 6, 7], "time_weekly": "09:30", "from": None, "to": None, "dates": [], "time_dates": None}}
    sch = kw.pop("schedule", None)
    if sch: p["schedule"].update(sch)
    p.update(kw); return p


ALPHA = person(1, "Alpha", "Un")
BETA = person(2, "Beta", "Deux", schedule={"weekdays": [TODAY.isoweekday()], "time_weekly": "08:00"}, usual_price_cents=None, usual_km_m=None)
GAMMA = person(3, "Gamma", "Trois", schedule={"from": d(2).isoformat(), "to": d(4).isoformat(), "time_weekly": "10:00"}, usual_price_cents=None, usual_km_m=None, dest_place="", dest_street="", dest_zip="", dest_city="")
DELTA = person(4, "Delta", "Quatre", usual_price_cents=1000, usual_km_m=5000,
               schedule={"mode": "dates", "dates": [TISO, d(3).isoformat()], "time_dates": "11:15", "weekdays": [1, 2, 3, 4, 5, 6, 7], "time_weekly": "07:00"})
EPSILON = person(5, "Epsilon", "Cinq", archived=True)


def expected_names(i):
    day = d(i); out = [("09:30", "Alpha")]
    if day.isoweekday() == TODAY.isoweekday(): out.append(("08:00", "Beta"))
    if 2 <= i <= 4: out.append(("10:00", "Gamma"))
    if i in (0, 3): out.append(("11:15", "Delta"))
    return [n for t, n in sorted(out)]


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="allow", permissions=["clipboard-read", "clipboard-write"])
    cx.add_init_script(INIT)
    errs = []; reqs = []
    cx.on("request", lambda r: reqs.append(r.url))
    pg = cx.new_page()
    pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
    pg.on("console", lambda m: errs.append("console " + m.text) if m.type == "error" else None)

    def boot(page=None):
        page = page or pg
        page.goto(BASE); page.wait_for_function("window.__ag && window.__ag.ready"); page.evaluate("window.__ag.ready"); page.wait_for_timeout(250)

    w = lambda: pg.wait_for_timeout(300)
    tap = lambda sel: (pg.locator(sel).first.tap(), w())
    goto = lambda t: tap('.nav button.t[data-t="%s"]' % t)
    cur = lambda: pg.evaluate("__ag.cur")
    masked = lambda: pg.evaluate("__ag.masked")
    toast_msg = lambda: pg.locator("#toast span").inner_text() if pg.locator("#toast").is_visible() and pg.locator("#toast span").count() else ""
    has_undo = lambda: pg.locator('#toast [data-a="undo"]').count() == 1 and pg.locator("#toast").is_visible()
    jump = lambda ms: pg.evaluate("window.__off += %d" % ms)
    nom = lambda: [x.strip() for x in pg.locator("#s-aujourdhui .frow .nom, #s-aujourdhui .person .nom").all_inner_texts()]
    label = lambda: pg.locator("#day-label").inner_text()
    summary = lambda: pg.locator("#day-summary").inner_text()
    row = lambda who: pg.locator('#s-aujourdhui .frow:has(.nom:text-is("%s"))' % who)

    def db_all(store, page=None):
        return (page or pg).evaluate("""(s)=>new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result;const g=d.transaction(s).objectStore(s).getAll();g.onsuccess=()=>{d.close();r(g.result)}}})""", store)

    def live(): return [r for r in db_all("rides") if not r.get("deleted_at")]
    def seed(persons=(), rides=()):
        pg.evaluate("""async([ps,rs])=>{ for(const p of ps) await AG.putPerson(p); for(const r of rs) await AG.putRide(r) }""", [list(persons), list(rides)])
        pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    def to_day(i):
        goto("aujourdhui")
        if pg.locator('[data-a="today"]').count(): tap('[data-a="today"]')
        for _ in range(abs(i)): pg.locator('[data-a="day"][data-d="%d"]' % (1 if i > 0 else -1)).tap(); pg.wait_for_timeout(70)
        pg.wait_for_timeout(150)
    def day_names(): return nom()

    boot()
    # ================= 1. cartes prévues du jour =================
    seed([ALPHA, BETA, GAMMA, DELTA, EPSILON])
    goto("aujourdhui")
    ok(tag + " aujourd'hui (%s) : cartes triées par heure : Beta 8h, Alpha 9h30, Delta 11h15 (Gamma pas encore, Epsilon archivée absente)" % TISO, nom() == ["Beta", "Alpha", "Delta"], nom())
    l2 = [x.strip() for x in pg.locator("#s-aujourdhui .frow .l2").all_inner_texts()]
    ok(tag + " heures affichées comme dans la maquette : « Rendez-vous 8h », « 9h30 », « 11h15 »", l2 == ["Rendez-vous 8h", "Rendez-vous 9h30", "Rendez-vous 11h15"], l2)
    ok(tag + " résumé du jour « 3 courses · 0 faite · 0 pas faite », jour en toutes lettres", summary() == "3 courses · 0 faite · 0 pas faite" and label().lower().startswith(["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][TODAY.weekday()]), (summary(), label()))
    ok(tag + " cartes prévues = calculées : AUCUNE course n'est enregistrée tant que Pascal n'a rien touché", db_all("rides") == [])
    tap('#s-aujourdhui .frow:has(.nom:text-is("Alpha")) .fmain')
    ok(tag + " ouvrir une carte (voir son détail) n'enregistre rien", pg.locator(".person.open").count() == 1 and db_all("rides") == [])
    pg.screenshot(path=SHOTS + "/courses_carte_ouverte_%dx%d_%s.png" % (W, H, SCHEME))
    txt = pg.locator(".person.open").inner_text()
    ok(tag + " carte ouverte : nom, heure, téléphone + « Appeler », prise en charge, destination (nom du lieu, adresse), montant et km avec « habituel »", all(x.lower() in txt.lower() for x in ["Alpha", "Un", "Rendez-vous 9h30", "0123456789", "Appeler", "Prise en charge", "1 rue Depart", "Destination", "Lieu Cible", "2 rue Cible", "Montant du jour", "Kilomètres", "Changer ce jour"]) and pg.input_value("#m-montant") == "12,50" and pg.input_value("#m-km") == "8,5" and pg.locator("#m-hab-p").count() == 1 and pg.locator("#m-hab-k").count() == 1 and pg.locator("a.call").get_attribute("href") == "tel:0123456789", txt)
    tap('.person.open [data-a="copyitem"][data-kind="dest"]')
    clip = pg.evaluate("navigator.clipboard.readText()")
    ok(tag + " « Copier » l'adresse de destination : « 2 rue Cible, 22222 Villecible » (message « Adresse copiée »)", clip == "2 rue Cible, 22222 Villecible" and toast_msg() == "Adresse copiée", clip)
    tap('.person.open [data-a="afold"] >> nth=0')
    ok(tag + " carte refermée", pg.locator(".person.open").count() == 0)

    # ================= 2. jours qui défilent : les deux modes de « Quand », « Du » / « Au » =================
    bad = []
    to_day(0)
    for i in range(0, 14):
        if nom() != expected_names(i): bad.append((i, d(i).isoformat(), nom(), expected_names(i)))
        pg.locator('[data-a="day"][data-d="1"]').tap(); pg.wait_for_timeout(70)
    ok(tag + " 14 jours avec les flèches : Alpha (tous les jours), Beta (même jour de la semaine), Gamma (« Du » +2 « Au » +4 : 3 jours), Delta (dates choisies : aujourd'hui et +3)", not bad, bad[:2])
    to_day(-1)
    ok(tag + " jour passé (hier) : la carte d'Alpha s'affiche, ronds vides « pas noté » (aucun rempli), et rien d'enregistré", "Alpha" in nom() and pg.locator("#s-aujourdhui .frow:has(.nom:text-is('Alpha')) .rnd.on").count() == 0 and pg.locator("#s-aujourdhui .frow:has(.nom:text-is('Alpha')) .rnd").count() == 2 and db_all("rides") == [])
    ok(tag + " bouton « Revenir à aujourd'hui » visible hors d'aujourd'hui, et il ramène au bon jour", pg.locator('[data-a="today"]').count() == 1 and (tap('[data-a="today"]') or True) and pg.evaluate("__ag.day") == TISO and pg.locator('[data-a="today"]').count() == 0)

    # ================= 3. première action = création de la course =================
    to_day(0)
    tap('#s-aujourdhui .frow:has(.nom:text-is("Alpha")) .rnd.ok')
    rr = db_all("rides"); r0 = rr[0] if rr else {}
    ok(tag + " « Fait » sur Alpha : UNE course créée (les autres cartes restent calculées)", len(rr) == 1 and r0.get("person_id") == ALPHA["id"] and r0.get("date") == TISO and r0.get("status") == "done", rr)
    ok(tag + " la course : identifiant unique, date en texte, heure « 09:30 », destination copiée de la fiche", UUID.match(r0.get("id", "")) and r0["time"] == "09:30" and r0["dest_place"] == "Lieu Cible" and r0["dest_street"] == "2 rue Cible" and r0["dest_zip"] == "22222" and r0["dest_city"] == "Villecible" and r0["created_at"].endswith("Z") and r0["deleted_at"] is None, r0)
    ok(tag + " prix et km COPIÉS de la fiche : 1250 centimes, 8500 mètres (entiers), repères « habituel » gardés dans la course", r0["price_cents"] == 1250 and r0["km_m"] == 8500 and r0["usual_price_cents"] == 1250 and r0["usual_km_m"] == 8500, r0)
    ok(tag + " message « Un : fait. » avec « Annuler », rond « fait » rempli, résumé « 3 courses · 1 faite · 0 pas faite »", toast_msg() == "Un : fait." and has_undo() and pg.locator("#s-aujourdhui .frow:has(.nom:text-is('Alpha')) .rnd.ok.on").count() == 1 and summary() == "3 courses · 1 faite · 0 pas faite", (toast_msg(), summary()))
    tap('#toast [data-a="undo"]')
    rr = db_all("rides")
    ok(tag + " « Annuler » : la course créée va à la CORBEILLE (jamais effacée), la carte redevient « à faire »", len(rr) == 1 and rr[0]["deleted_at"] and live() == [] and pg.locator("#s-aujourdhui .frow:has(.nom:text-is('Alpha')) .rnd.on").count() == 0, rr)
    tap('#s-aujourdhui .frow:has(.nom:text-is("Beta")) .rnd.ko')
    ok(tag + " « Pas fait » sur Beta : course « pas fait », résumé « … 1 pas faite », prix et km inconnus restent vides (null, jamais 0)", [x for x in live() if x["person_id"] == BETA["id"]][0]["status"] == "not_done" and [x for x in live() if x["person_id"] == BETA["id"]][0]["price_cents"] is None and [x for x in live() if x["person_id"] == BETA["id"]][0]["km_m"] is None and "1 pas faite" in summary(), summary())
    tap('#s-aujourdhui .frow:has(.nom:text-is("Beta")) .rnd.ko')
    bb = [x for x in live() if x["person_id"] == BETA["id"]]
    ok(tag + " retoucher le rond « pas fait » le vide : « Deux : remis à faire. », la course existe encore, sans état", toast_msg() == "Deux : remis à faire." and len(bb) == 1 and bb[0]["status"] is None and pg.locator("#s-aujourdhui .frow:has(.nom:text-is('Beta')) .rnd").count() == 2, toast_msg())
    tap('#s-aujourdhui .frow:has(.nom:text-is("Beta")) .rnd.ok'); tap('#s-aujourdhui .frow:has(.nom:text-is("Beta")) .rnd.ok')
    tap('#s-aujourdhui .frow:has(.nom:text-is("Beta")) .rnd.ko')
    ok(tag + " fait → remis à faire → pas fait : toujours UNE seule course pour Beta aujourd'hui", len([x for x in live() if x["person_id"] == BETA["id"]]) == 1 and [x for x in live() if x["person_id"] == BETA["id"]][0]["status"] == "not_done")
    tap('#toast [data-a="undo"]')
    ok(tag + " « Annuler » sur un changement d'état d'une course existante : l'état d'avant revient, la course reste", [x for x in live() if x["person_id"] == BETA["id"]][0]["status"] is None)

    # ================= 4. montant et km du jour =================
    tap('#s-aujourdhui .frow:has(.nom:text-is("Delta")) .fmain')
    ok(tag + " carte de Delta (jamais touchée) : montant « 10 » et km « 5 » de la fiche, deux repères « habituel »", pg.input_value("#m-montant") == "10" and pg.input_value("#m-km") == "5" and pg.locator("#m-hab-p").count() == 1 and pg.locator("#m-hab-k").count() == 1)
    pg.fill("#m-montant", "0"); pg.locator("#m-montant").blur(); w()
    ok(tag + " montant « 0 » : refusé (« un zéro n'est pas possible »), champ marqué, aucune course créée pour Delta", "zéro" in pg.locator("#m-err").inner_text() and pg.locator("#m-montant").get_attribute("aria-invalid") == "true" and not [x for x in db_all("rides") if x["person_id"] == DELTA["id"]], pg.locator("#m-err").inner_text())
    pg.fill("#m-montant", "20.5"); pg.locator("#m-montant").blur(); w()
    dd = [x for x in live() if x["person_id"] == DELTA["id"]]
    ok(tag + " montant « 20.5 » (point) : la course de Delta est créée à ce moment (2050 centimes), km copié de la fiche (5000 m), repère « habituel » du prix disparu, celui des km reste, champ « 20,50 »", len(dd) == 1 and dd[0]["price_cents"] == 2050 and dd[0]["km_m"] == 5000 and dd[0]["usual_price_cents"] == 1000 and dd[0]["status"] is None and pg.locator("#m-hab-p").count() == 0 and pg.locator("#m-hab-k").count() == 1 and pg.input_value("#m-montant") == "20,50", dd)
    pg.fill("#m-km", "7,25"); pg.locator("#m-km").blur(); w()
    ok(tag + " km « 7,25 » (virgule) : 7250 mètres, les deux repères « habituel » ont disparu", [x for x in live() if x["person_id"] == DELTA["id"]][0]["km_m"] == 7250 and pg.locator("#m-hab-k").count() == 0)
    pg.fill("#m-km", "5"); pg.locator("#m-km").blur(); w()
    ok(tag + " retaper la valeur habituelle (5) : le repère « habituel » des km revient", pg.locator("#m-hab-k").count() == 1)
    pg.fill("#m-montant", ""); pg.locator("#m-montant").blur(); w()
    ok(tag + " montant effacé : « inconnu » (null), jamais 0", [x for x in live() if x["person_id"] == DELTA["id"]][0]["price_cents"] is None)
    tap('.person.open [data-a="afold"] >> nth=0')

    # ================= 5. changer ce jour =================
    tap('#s-aujourdhui .frow:has(.nom:text-is("Alpha")) .fmain'); tap('.person.open [data-a="dschg"]')
    ok(tag + " « Changer ce jour » : petit panneau (pas une page) avec heure et destination SEULEMENT, préremplis (09:30, Lieu Cible…)", pg.locator("#daysheet.on").count() == 1 and pg.locator("#ds-title").inner_text() == "Changer ce jour" and pg.input_value("#ds-heure") == "09:30" and pg.input_value("#ds-lieu") == "Lieu Cible" and pg.input_value("#ds-rue") == "2 rue Cible" and pg.input_value("#ds-cp") == "22222" and pg.input_value("#ds-ville") == "Villecible" and pg.locator("#ds-panel input").count() == 5)
    pg.fill("#ds-heure", "25:00"); tap('[data-a="dssave"]')
    ok(tag + " heure « 25:00 » : « Heure invalide : écris par exemple 13:00, ou laisse vide. », rien enregistré", pg.locator("#ds-err").inner_text() == "Heure invalide : écris par exemple 13:00, ou laisse vide." and not [x for x in db_all("rides") if x["person_id"] == ALPHA["id"] and not x["deleted_at"]])
    pg.fill("#ds-heure", "1400"); pg.fill("#ds-lieu", "Autre lieu"); pg.fill("#ds-rue", "9 rue Autre"); tap('[data-a="dssave"]')
    aa = [x for x in live() if x["person_id"] == ALPHA["id"]]
    ok(tag + " enregistré : course d'Alpha créée avec heure « 14:00 » et destination « Autre lieu », marquée « changé », prix et km toujours copiés de la fiche", len(aa) == 1 and aa[0]["time"] == "14:00" and aa[0]["dest_place"] == "Autre lieu" and aa[0]["dest_street"] == "9 rue Autre" and aa[0]["changed"] is True and aa[0]["price_cents"] == 1250 and toast_msg() == "Jour changé", aa)
    ok(tag + " la carte : « Rendez-vous 14h » avec la mention « changé », triée après Delta (11h15)", nom() == ["Beta", "Delta", "Alpha"] and "changé" in pg.locator("#s-aujourdhui .frow:has(.nom:text-is('Alpha')) .l2").inner_text(), nom())
    ok(tag + " la fiche d'Alpha n'a pas bougé (heure, destination d'origine)", [x for x in db_all("persons") if x["id"] == ALPHA["id"]][0]["dest_place"] == "Lieu Cible" and [x for x in db_all("persons") if x["id"] == ALPHA["id"]][0]["schedule"]["time_weekly"] == "09:30")

    # ================= 6. ajouter une course (exceptionnelle) =================
    tap('[data-a="aadd"]')
    labs = [x.strip().replace("\n", " ") for x in pg.locator("#ds-panel .list-item .name").all_inner_texts()]
    ok(tag + " « Ajouter une course » : liste des personnes SANS carte ce jour-là (Gamma ; ni les 3 déjà prévues, ni l'archivée Epsilon)", pg.locator("#ds-title").inner_text() == "Ajouter une course" and labs == ["Gamma Trois"], labs)
    tap('[data-a="dspick"]')
    ok(tag + " choisir Gamma : formulaire heure + destination (vides comme sa fiche)", pg.locator("#ds-title").inner_text() == "Ajouter une course" and pg.input_value("#ds-heure") == "10:00" and pg.input_value("#ds-lieu") == "")
    pg.fill("#ds-heure", "16:00"); pg.fill("#ds-lieu", "Visite"); tap('[data-a="dssave"]')
    gg = [x for x in live() if x["person_id"] == GAMMA["id"]]
    ok(tag + " course exceptionnelle enregistrée : « Course ajoutée », marquée « ajoutée », heure 16:00, prix et km inconnus (null)", len(gg) == 1 and gg[0]["added"] is True and gg[0]["time"] == "16:00" and gg[0]["dest_place"] == "Visite" and gg[0]["price_cents"] is None and toast_msg() == "Course ajoutée", gg)
    ok(tag + " elle apparaît dans la journée (4 courses), triée après Alpha 14h : Beta, Delta, Alpha, Gamma", nom() == ["Beta", "Delta", "Alpha", "Gamma"], nom())
    tap('[data-a="aadd"]')
    ok(tag + " plus personne à ajouter : message « Toutes les personnes ont déjà une course ce jour-là. »", "Toutes les personnes ont déjà une course ce jour-là." in pg.locator("#ds-panel").inner_text())
    tap('#ds-panel [data-a="dsclose"]')
    tap('#s-aujourdhui .frow:has(.nom:text-is("Gamma")) .fmain')
    ok(tag + " la course exceptionnelle propose « Supprimer cette course »", pg.locator('.person.open [data-a="dsdel"]').count() == 1)
    tap('.person.open [data-a="dsdel"]')
    gg = [x for x in db_all("rides") if x["person_id"] == GAMMA["id"]]
    ok(tag + " supprimer : « Course supprimée » avec « Annuler » ; la course va à la corbeille (jamais effacée), la carte disparaît", toast_msg() == "Course supprimée" and has_undo() and len(gg) == 1 and gg[0]["deleted_at"] and "Gamma" not in nom(), gg)
    tap('#toast [data-a="undo"]')
    ok(tag + " « Annuler » : la course revient", "Gamma" in nom() and not [x for x in db_all("rides") if x["person_id"] == GAMMA["id"]][0]["deleted_at"])

    # ================= 7. la fiche ne réécrit jamais une course =================
    to_day(-1)
    tap('#s-aujourdhui .frow:has(.nom:text-is("Alpha")) .rnd.ok')           # hier : course faite avec les valeurs d'avant
    yest = [x for x in live() if x["person_id"] == ALPHA["id"] and x["date"] == d(-1).isoformat()][0]
    to_day(0)
    goto("personnes"); tap('#plist .list-item:has-text("Alpha")')
    pg.fill("#f-prix", "99"); pg.fill("#f-km", "1"); pg.fill("#f-heure", "07:00"); pg.fill("#f-lieu", "Nouveau lieu"); pg.fill("#f-lrue", "5 rue Neuve")
    for j in range(1, 8): tap('[data-a="jour"][data-j="%d"]' % j)             # on décoche tous les jours habituels
    tap('[data-a="savefiche"]')
    to_day(-1)
    y2 = [x for x in db_all("rides") if x["id"] == yest["id"]][0]
    ok(tag + " la fiche d'Alpha change (prix 99, km 1, heure 7:00, autre destination, plus aucun jour) : la course d'HIER est inchangée (heure, destination, 1250 / 8500, fait)", y2["time"] == "09:30" and y2["dest_place"] == "Lieu Cible" and y2["price_cents"] == 1250 and y2["km_m"] == 8500 and y2["status"] == "done" and "Alpha" in nom() and pg.locator("#s-aujourdhui .frow:has(.nom:text-is('Alpha')) .rnd.ok.on").count() == 1, y2)
    to_day(0)
    t2 = [x for x in db_all("rides") if x["person_id"] == ALPHA["id"] and x["date"] == TISO and not x["deleted_at"]][0]
    ok(tag + " la course d'AUJOURD'HUI (déjà enregistrée) garde aussi ses valeurs : 14:00, « Autre lieu », 1250 centimes", t2["time"] == "14:00" and t2["dest_place"] == "Autre lieu" and t2["price_cents"] == 1250 and "Alpha" in nom(), t2)
    to_day(1)
    ok(tag + " demain, sans course : plus de carte d'Alpha (plus aucun jour habituel) — l'avenir suit la fiche, le passé non", "Alpha" not in nom(), nom())
    goto("personnes"); tap('#plist .list-item:has-text("Alpha")')
    for j in (1, 2, 3, 4, 5, 6, 7): tap('[data-a="jour"][data-j="%d"]' % j)
    fill_prix = pg.fill("#f-prix", "99"); tap('[data-a="savefiche"]')
    to_day(1)
    new_alpha = row("Alpha")
    ok(tag + " jours rétablis avec la nouvelle fiche : la carte de demain prend la NOUVELLE heure (7h) ; ouverte elle montre 99 et la nouvelle destination ; rien n'est enregistré", new_alpha.count() == 1 and "Rendez-vous 7h" in new_alpha.locator(".l2").inner_text() and not [x for x in live() if x["person_id"] == ALPHA["id"] and x["date"] == d(1).isoformat()])
    tap('#s-aujourdhui .frow:has(.nom:text-is("Alpha")) .fmain')
    ok(tag + " … carte ouverte de demain : montant « 99 », km « 1 », « Nouveau lieu »", pg.input_value("#m-montant") == "99" and pg.input_value("#m-km") == "1" and "Nouveau lieu" in pg.locator(".person.open").inner_text())
    tap('.person.open [data-a="afold"] >> nth=0')

    # ================= 8. archiver =================
    to_day(0)
    goto("personnes"); tap('#plist .list-item:has-text("Delta")'); tap('[data-a="archiveask"]'); tap("#confirm-ok")
    to_day(0)
    ok(tag + " personne archivée (Delta, avec une course d'aujourd'hui non notée) : plus de carte prévue ni de course non notée aujourd'hui", "Delta" not in nom(), nom())
    goto("personnes"); tap('[data-a="archshow"]'); tap('[data-a="restore"]'); tap('[data-a="archhide"]')
    to_day(0)
    ok(tag + " restaurée : sa carte revient (avec sa course et son montant gardés)", "Delta" in nom())
    to_day(-1)
    tap('#s-aujourdhui .frow:has(.nom:text-is("Epsilon")) .rnd.ko') if "Epsilon" in nom() else None
    ok(tag + " Epsilon (archivée) n'a aucune carte prévue dans le passé non plus", "Epsilon" not in nom())
    # une course NOTÉE d'une personne archivée reste visible dans le passé
    ride_old = {"id": "00000000-0000-4000-8000-0000000000e1", "person_id": EPSILON["id"], "date": d(-5).isoformat(), "time": "09:00", "dest_place": "", "dest_street": "", "dest_zip": "", "dest_city": "", "price_cents": None, "km_m": None,
                "usual_price_cents": None, "usual_km_m": None, "status": "done", "changed": False, "added": False, "skip": False, "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z", "deleted_at": None}
    seed([], [ride_old]); to_day(-5)
    ok(tag + " une course passée NOTÉE d'une personne archivée reste visible (« Epsilon », fait)", "Epsilon" in nom() and pg.locator("#s-aujourdhui .frow:has(.nom:text-is('Epsilon')) .rnd.ok.on").count() == 1, nom())

    # ================= 9. persistance et hors connexion =================
    to_day(0)
    before = {r["id"]: r["status"] for r in live()}
    pg.close(); pg = cx.new_page(); pg.on("pageerror", lambda e: errs.append("pageerror " + str(e))); boot(); goto("aujourdhui")
    ok(tag + " fermeture et réouverture : les courses et leurs états sont toujours là (Beta toujours à faire, Delta avec son montant)", {r["id"]: r["status"] for r in live()} == before and "Beta" in nom())
    pg.wait_for_function("!!navigator.serviceWorker.controller"); pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.wait_for_timeout(500)
    cx.set_offline(True)
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready", timeout=15000); pg.evaluate("window.__ag.ready"); w()
    goto("aujourdhui")
    ok(tag + " MODE AVION : Aujourd'hui s'ouvre avec ses cartes", "Beta" in nom() and "Delta" in nom(), nom())
    tap('#s-aujourdhui .frow:has(.nom:text-is("Beta")) .rnd.ok')
    ok(tag + " MODE AVION : « Fait » s'enregistre", [x for x in live() if x["person_id"] == BETA["id"]][0]["status"] == "done")
    cx.set_offline(False)

    # ================= 10. masquage =================
    tap('#s-aujourdhui .frow:has(.nom:text-is("Alpha")) .fmain') if "Alpha" in nom() else tap('#s-aujourdhui .frow >> nth=0')
    ok(tag + " carte ouverte avec montant et adresses", pg.locator(".person.open").count() == 1 and pg.locator("#m-montant").count() == 1)
    tap('.screen.on [data-a="hide"]')
    vt = pg.evaluate("document.getElementById('veil').innerText.trim()")
    pts = pg.evaluate("""()=>{let n=0,c=0;for(let x=10;x<innerWidth;x+=Math.floor(innerWidth/6))for(let y=10;y<innerHeight;y+=Math.floor(innerHeight/8)){n++;const e=document.elementFromPoint(x,y);if(e&&e.closest('#veil'))c++}return [n,c]}""")
    ok(tag + " œil sur Aujourd'hui : « Agenda » seul, plein écran, rien de lisible", masked() and vt == "Agenda" and pts[0] == pts[1] and pg.evaluate("document.getElementById('views').inert"), (vt, pts))
    ok(tag + " … et les cartes sont refermées dessous : montants et adresses retirés de la page (aucun champ « Montant » dans le document)", pg.locator("#m-montant").count() == 0 and "2 rue" not in pg.evaluate("document.getElementById('s-aujourdhui').innerText"))
    pg.locator("#veil").tap(); w()
    tap('[data-a="aadd"]')
    ok(tag + " panneau « Ajouter une course » ouvert", pg.locator("#daysheet.on").count() == 1)
    jump(125000); pg.wait_for_timeout(1700)
    vt = pg.evaluate("document.getElementById('veil').innerText.trim()")
    cov = pg.evaluate("(()=>{const r=document.querySelector('#ds-panel').getBoundingClientRect();const e=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return !!e&&!!e.closest('#veil')})()")
    ok(tag + " 2 minutes simulées avec le panneau ouvert : masqué tout seul, panneau couvert et inerte, rien de lisible", masked() and vt == "Agenda" and cov and pg.evaluate("document.getElementById('daysheet').inert"), (vt, cov))
    pg.locator("#veil").tap(); w(); tap('#ds-panel [data-a="dsclose"]')
    # ================= 11. zones de toucher =================
    AUD = """()=>{const app=document.getElementById('app').getBoundingClientRect(), out=[];
      document.querySelectorAll('.screen.on button, .screen.on a.btn, .screen.on input').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width||e.closest('[hidden]'))return;
        const tool=e.classList.contains('tool')&&e.closest('.tools.row');
        if(r.height<(tool?27.5:43.5)||r.width<43.5)out.push('PETIT '+(e.id||e.dataset.a||e.textContent.trim().slice(0,14))+' '+r.width.toFixed(0)+'x'+r.height.toFixed(0));
        if(r.right>app.right+.5||r.left<app.left-.5)out.push('DEBORDE '+(e.id||e.dataset.a))});
      const c=document.querySelector('.screen.on .content');if(c.scrollWidth>c.clientWidth+1)out.push('LARGEUR '+c.scrollWidth+'>'+c.clientWidth);return out}"""
    to_day(0); z = pg.evaluate(AUD)
    ok(tag + " Aujourd'hui (lignes repliées) : zones de 44 px (œil 44 x 28 comme la maquette), rien qui déborde", not z, z)
    tap('#s-aujourdhui .frow >> nth=0'); z = pg.evaluate(AUD)
    ok(tag + " Aujourd'hui (carte ouverte) : zones de 44 px, rien qui déborde", not z, z)
    pg.screenshot(path=SHOTS + "/courses_aujourdhui_%dx%d_%s.png" % (W, H, SCHEME))
    tap('.person.open [data-a="dschg"]')
    AUDS = """()=>{const app=document.getElementById('app').getBoundingClientRect(), pn=document.querySelector('#daysheet .panel').getBoundingClientRect(), out=[];
      const R=[...document.querySelectorAll('#daysheet .panel button, #daysheet .panel input')].filter(e=>e.getBoundingClientRect().width>0).map(e=>({n:e.id||e.dataset.a,r:e.getBoundingClientRect()}));
      R.forEach(a=>{ if(a.r.right>app.right+.5||a.r.left<app.left-.5) out.push('DEBORDE '+a.n); if(a.r.height<43.5) out.push('PETIT '+a.n) });
      for(let i=0;i<R.length;i++)for(let j=i+1;j<R.length;j++){const a=R[i].r,b=R[j].r;if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)out.push('CHEVAUCHE '+R[i].n+' / '+R[j].n)}
      if(pn.top<0||pn.bottom>innerHeight+.5)out.push('HORS ECRAN');return out}"""
    z = pg.evaluate(AUDS)
    ok(tag + " panneau « Changer ce jour » : zones de 44 px, rien qui déborde ni se chevauche, dans l'écran", not z, z)
    tap('[data-a="dsback"]')
    ok(tag + " « Annuler » du panneau ouvert depuis une carte : il se ferme", pg.locator("#daysheet.on").count() == 0)

    ok(tag + " aucune erreur JavaScript", not errs, errs)
    outside = [u for u in reqs if not u.startswith(BASE) and not u.startswith("data:") and not u.startswith("blob:")]
    ok(tag + " aucune requête hors de l'appli (%d requêtes)" % len(reqs), not outside, outside)
    b.close()

    # ================= 12. journée vide =================
    b, cx2 = p.chromium.launch(channel="msedge", headless=True), None
    cx2 = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, color_scheme=SCHEME)
    cx2.add_init_script(INIT)
    pe = cx2.new_page(); pe.goto(BASE); pe.wait_for_function("window.__ag && window.__ag.ready"); pe.evaluate("window.__ag.ready"); pe.wait_for_timeout(300)
    ok(tag + " journée vide (aucune personne) : « Aucune course prévue ce jour. » et « 0 course · 0 faite · 0 pas faite »", "Aucune course prévue ce jour." in pe.locator("#s-aujourdhui").inner_text() and pe.locator("#day-summary").inner_text() == "0 course · 0 faite · 0 pas faite")
    b.close()

    # ================= 13. changement d'heure du dimanche 25 octobre 2026 =================
    b = p.chromium.launch(channel="msedge", headless=True)
    target = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc).timestamp() * 1000      # samedi 24 octobre 2026, 12 h à Bruxelles (heure d'été)
    cx3 = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, color_scheme=SCHEME, timezone_id="Europe/Brussels", locale="fr-FR")
    cx3.add_init_script("window.__off=%d-Date.now(); window.__freeze=false; (function(){ var n=Date.now.bind(Date); Date.now=function(){ return n()+window.__off; }; })();" % int(target))
    pd = cx3.new_page(); derrs = []
    pd.on("pageerror", lambda e: derrs.append(str(e)))
    pd.goto(BASE); pd.wait_for_function("window.__ag && window.__ag.ready"); pd.evaluate("window.__ag.ready")
    DIM = person(11, "Dimanche", "Seul", schedule={"weekdays": [7], "time_weekly": "08:00"}, usual_price_cents=500, usual_km_m=2000)
    TOUS = person(12, "Quotidien", "Tous", schedule={"weekdays": [1, 2, 3, 4, 5, 6, 7], "time_weekly": "15:00"}, usual_price_cents=None, usual_km_m=None)
    pd.evaluate("""async(ps)=>{for(const p of ps) await AG.putPerson(p); await AG.putSetting('idle_sec',0)}""", [DIM, TOUS]); pd.reload(); pd.wait_for_function("window.__ag && window.__ag.ready"); pd.evaluate("window.__ag.ready"); pd.wait_for_timeout(400)
    lab = lambda: pd.locator("#day-label").inner_text().lower()
    nm = lambda: [x.strip() for x in pd.locator("#s-aujourdhui .frow .nom").all_inner_texts()]
    ok(tag + " horloge simulée au samedi 24 octobre 2026 (Bruxelles) : « samedi 24 octobre », « Quotidien » seulement", lab() == "samedi 24 octobre" and nm() == ["Quotidien"] and pd.evaluate("__ag.day") == "2026-10-24", (lab(), nm()))
    pd.locator('[data-a="day"][data-d="1"]').tap(); pd.wait_for_timeout(200)
    ok(tag + " jour suivant : « dimanche 25 octobre » (jour du changement d'heure, 25 heures), deux cartes : Dimanche 8h puis Quotidien 15h", lab() == "dimanche 25 octobre" and nm() == ["Dimanche", "Quotidien"] and pd.evaluate("__ag.day") == "2026-10-25", (lab(), nm()))
    pd.locator('#s-aujourdhui .frow:has(.nom:text-is("Dimanche")) .rnd.ok').tap(); pd.wait_for_timeout(300)
    pd.locator('[data-a="day"][data-d="1"]').tap(); pd.wait_for_timeout(200)
    ok(tag + " lundi 26 octobre : « Dimanche » n'a pas de carte, « Quotidien » oui (aucun jour sauté ni compté deux fois)", lab() == "lundi 26 octobre" and nm() == ["Quotidien"], (lab(), nm()))
    pd.locator('#s-aujourdhui .frow:has(.nom:text-is("Quotidien")) .rnd.ko').tap(); pd.wait_for_timeout(300)
    pd.locator('[data-a="day"][data-d="-1"]').tap(); pd.wait_for_timeout(150); pd.locator('[data-a="day"][data-d="-1"]').tap(); pd.wait_for_timeout(200)
    ok(tag + " retour au 24 : toujours « samedi 24 octobre »", lab() == "samedi 24 octobre")
    rds = pd.evaluate("""new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const g=q.result.transaction('rides').objectStore('rides').getAll();g.onsuccess=()=>{q.result.close();r(g.result.map(x=>[x.person_id.slice(-2),x.date,x.status]).sort())}}})""")
    ok(tag + " dates rangées en TEXTE : course du dimanche = « 2026-10-25 » (fait), course du lundi = « 2026-10-26 » (pas fait), rien de décalé", rds == [["11", "2026-10-25", "done"], ["12", "2026-10-26", "not_done"]], rds)
    pd.locator('[data-a="today"]').tap() if pd.locator('[data-a="today"]').count() else None; pd.wait_for_timeout(200)
    pd.evaluate("window.__off += 24*3600*1000"); pd.wait_for_timeout(1800)      # 24 h plus tard : dimanche 25 octobre, 11 h (heure d'hiver) ; l'appli suit toute seule
    ok(tag + " 24 h plus tard (le dimanche du changement d'heure, 11 h) : « Aujourd'hui » est bien « dimanche 25 octobre »", pd.evaluate("__ag.day") == "2026-10-25" and lab() == "dimanche 25 octobre", (pd.evaluate("__ag.day"), lab()))
    pd.evaluate("window.__off += 14*3600*1000"); pd.wait_for_timeout(1800)
    ok(tag + " 14 h de plus (lundi 26 octobre, 1 h du matin heure d'hiver) : « Aujourd'hui » devient « lundi 26 octobre »", pd.evaluate("__ag.day") == "2026-10-26" and lab() == "lundi 26 octobre", (pd.evaluate("__ag.day"), lab()))
    ok(tag + " aucune erreur JavaScript (changement d'heure)", not derrs, derrs)
    b.close()
    srv.shutdown()
print("TOTAL", total, "ECHECS", fails)
