"""Version 0.9.0 : liste des lieux d'une personne.
Vérifie : « Autres lieux » dans la fiche (vide au départ), ajout d'un lieu (nom ou adresse obligatoire, code postal, doublon refusé, l'habituel compte comme doublon),
enregistrement de la fiche (persisté), menu des lieux dans le panneau d'un jour (habituel / autre lieu / nouveau),
« Changer lieu de destination » qui n'ajoute pas de lieu si la case est décochée, qui garde le nouveau lieu sinon,
et que le lieu choisi est bien celui enregistré dans la course. Noms FICTIFS seulement. W, H, SCHEME comme les autres contrôles."""
import os, re, threading, pathlib, http.server, functools
from datetime import date, timedelta
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
fails = 0; total = 0


def ok(n, c, e=""):
    global fails, total
    total += 1
    if not c: fails += 1
    print(("PASS " if c else "FAIL ") + n + (" | " + str(e)[:500] if not c else ""))


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "max-age=600"); super().end_headers()
    def log_message(self, *a): pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % srv.server_address[1]
INIT = """window.__off=0; window.__freeze=false; (function(){ var n=Date.now.bind(Date); Date.now=function(){ return n()+window.__off; }; var si=window.setInterval.bind(window); window.setInterval=function(f,t){ return si(function(){ if(!window.__freeze) f(); },t); }; })();"""

# Alpha : travaille du lundi au vendredi, lieu habituel « Lieu Cible »
ALPHA = {"id": "00000000-0000-4000-8000-000000000001", "last_name": "Alpha", "first_name": "Un", "pickup_street": "1 rue Depart", "pickup_zip": "11111", "pickup_city": "Villedepart",
         "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible", "phone": "", "usual_price_cents": 1250, "usual_km_m": 8500,
         "archived": False, "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z",
         "schedule": {"mode": "weekly", "weekdays": [1, 2, 3, 4, 5], "time_weekly": "09:00", "from": None, "to": None, "dates": [], "time_dates": None}}

# trois prochains jours ouvrés (à partir de demain) pour tester le panneau d'un jour
d = date.today() + timedelta(days=1); JOURS = []
while len(JOURS) < 3:
    if d.weekday() < 5: JOURS.append(d)
    d += timedelta(days=1)
J1, J2, J3 = JOURS

with sync_playwright() as p:
    try: b = p.chromium.launch(channel="msedge", headless=True)
    except Exception: b = p.chromium.launch(headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="allow")
    cx.add_init_script(INIT)
    errs = []
    pg = cx.new_page()
    pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
    pg.on("console", lambda m: errs.append("console " + m.text) if m.type == "error" else None)
    w = lambda: pg.wait_for_timeout(300)
    tap = lambda sel: (pg.locator(sel).first.tap(), w())
    goto = lambda t: tap('.nav button.t[data-t="%s"]' % t)
    fill = lambda sel, v: (pg.locator(sel).first.fill(v), w())

    def db_all(store):
        return pg.evaluate("""(s)=>new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result;const g=d.transaction(s).objectStore(s).getAll();g.onsuccess=()=>{d.close();r(g.result)}}})""", store)
    def boot():
        pg.goto(BASE); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(250)
    def seed(persons):
        pg.evaluate("""async(ps)=>{ for(const p of ps) await AG.putPerson(p) }""", persons)
        pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    def person_row(pid):
        return [x for x in db_all("persons") if x["id"] == pid][0]
    def ride_for(iso):
        return [x for x in db_all("rides") if x["date"] == iso and not x.get("deleted_at")]

    boot(); seed([ALPHA])
    goto("personnes"); tap('#plist .list-item:has-text("Alpha")')

    # ===== 1. fiche : section Autres lieux =====
    ok(tag + " fiche : « Autres lieux » vide au départ", "Aucun autre lieu" in pg.locator("#f-places").inner_text(), pg.locator("#f-places").inner_text())
    ok(tag + " formulaire d'ajout caché au départ", pg.locator("#f-xform").is_hidden())
    tap('[data-a="fxshow"]')
    ok(tag + " « + Ajouter un lieu » ouvre le formulaire", pg.locator("#f-xform").is_visible())
    tap('[data-a="fxadd"]')
    ok(tag + " ajout vide refusé", "Écris au moins" in pg.locator("#f-x-err").inner_text(), pg.locator("#f-x-err").inner_text())
    fill("#f-xnom", "Clinique Nord"); fill("#f-xrue", "9 rue Nord"); fill("#f-xcp", "33"); fill("#f-xville", "Nordville")
    tap('[data-a="fxadd"]')
    ok(tag + " code postal trop court : refusé", "4 ou 5 chiffres" in pg.locator("#f-x-err").inner_text(), pg.locator("#f-x-err").inner_text())
    fill("#f-xcp", "3333")
    tap('[data-a="fxadd"]')
    ok(tag + " lieu ajouté à la liste", "Clinique Nord" in pg.locator("#f-places").inner_text(), pg.locator("#f-places").inner_text())
    ok(tag + " formulaire refermé après ajout", pg.locator("#f-xform").is_hidden() and pg.locator("#f-xshow").is_visible())
    tap('[data-a="fxshow"]'); fill("#f-xnom", "clinique   NORD"); fill("#f-xrue", "9 Rue nord"); fill("#f-xcp", "3333"); fill("#f-xville", "NORDVILLE")
    tap('[data-a="fxadd"]')
    ok(tag + " même lieu écrit autrement : refusé comme doublon", "déjà dans la liste" in pg.locator("#f-x-err").inner_text(), pg.locator("#f-x-err").inner_text())
    tap('[data-a="fxcancel"]')
    tap('[data-a="fxshow"]')
    fill("#f-xnom", "Lieu Cible"); fill("#f-xrue", "2 rue Cible"); fill("#f-xcp", "22222"); fill("#f-xville", "Villecible")
    tap('[data-a="fxadd"]')
    ok(tag + " le lieu habituel compte comme doublon", "déjà dans la liste" in pg.locator("#f-x-err").inner_text(), pg.locator("#f-x-err").inner_text())
    tap('[data-a="fxcancel"]')
    tap('[data-a="savefiche"]')
    w()
    stored = person_row(ALPHA["id"]).get("places", [])
    ok(tag + " fiche enregistrée : un lieu gardé", len(stored) == 1 and stored[0]["place"] == "Clinique Nord", stored)
    ok(tag + " lieu habituel inchangé", person_row(ALPHA["id"])["dest_place"] == "Lieu Cible")

    # ===== 2. panneau d'un jour : menu des lieux =====
    goto("personnes"); tap('#plist .list-item:has-text("Alpha")'); tap('[data-a="calfiche"]')
    pg.locator('#s-calendrier .cell[data-iso="%s"]' % J1.isoformat()).first.tap(); w()
    tap('[data-a="dschg"]')
    ok(tag + " « Changer ce jour » ouvre le formulaire", pg.locator("#ds-choix").is_visible())
    opts = pg.evaluate("[...document.querySelectorAll('#ds-choix option')].map(o=>o.textContent)")
    ok(tag + " menu : habituel, autre lieu, nouveau lieu", opts == ["Lieu habituel : Lieu Cible", "Clinique Nord", "Nouveau lieu…"], opts)
    ok(tag + " case « garder » cachée pour un lieu existant", pg.locator("#ds-keepwrap").is_hidden())
    pg.select_option("#ds-choix", "0"); w()
    ok(tag + " choisir Clinique Nord remplit l'adresse", pg.input_value("#ds-lieu") == "Clinique Nord" and pg.input_value("#ds-ville") == "Nordville" and pg.input_value("#ds-cp") == "3333", pg.input_value("#ds-lieu"))
    tap('[data-a="dssave"]')
    w()
    r1 = ride_for(J1.isoformat())
    ok(tag + " course enregistrée avec Clinique Nord", len(r1) == 1 and r1[0]["dest_place"] == "Clinique Nord", r1)
    ok(tag + " liste inchangée (pas de doublon)", len(person_row(ALPHA["id"]).get("places", [])) == 1)

    # ===== 3. nouveau lieu, case cochée : gardé dans la liste =====
    pg.locator('#s-calendrier .cell[data-iso="%s"]' % J2.isoformat()).first.tap(); w()
    tap('[data-a="dschg"]')
    pg.select_option("#ds-choix", "new"); w()
    ok(tag + " « Nouveau lieu » : case « garder » visible et cochée", pg.locator("#ds-keepwrap").is_visible() and pg.locator("#ds-keep").is_checked())
    fill("#ds-lieu", "Maison de repos Les Tilleuls"); fill("#ds-rue", "7 rue Neuve"); fill("#ds-cp", "44444"); fill("#ds-ville", "Neuville")
    tap('[data-a="dssave"]'); w()
    r2 = ride_for(J2.isoformat())
    ok(tag + " course avec le nouveau lieu", len(r2) == 1 and r2[0]["dest_place"] == "Maison de repos Les Tilleuls", r2)
    names = [x["place"] for x in person_row(ALPHA["id"]).get("places", [])]
    ok(tag + " nouveau lieu gardé dans la liste de la personne", names == ["Clinique Nord", "Maison de repos Les Tilleuls"], names)

    # ===== 4. nouveau lieu, case décochée : pas gardé =====
    pg.locator('#s-calendrier .cell[data-iso="%s"]' % J3.isoformat()).first.tap(); w()
    tap('[data-a="dschg"]')
    pg.select_option("#ds-choix", "new"); w()
    pg.locator("#ds-keep").uncheck(); w()
    fill("#ds-lieu", "Cabinet du Docteur Ponctuel"); fill("#ds-rue", "3 place Unique"); fill("#ds-cp", "55555"); fill("#ds-ville", "Ponctville")
    tap('[data-a="dssave"]'); w()
    r3 = ride_for(J3.isoformat())
    ok(tag + " course ponctuelle enregistrée", len(r3) == 1 and r3[0]["dest_place"] == "Cabinet du Docteur Ponctuel", r3)
    names = [x["place"] for x in person_row(ALPHA["id"]).get("places", [])]
    ok(tag + " lieu ponctuel NON gardé dans la liste", names == ["Clinique Nord", "Maison de repos Les Tilleuls"], names)
    ok(tag + " la course de J1 garde son lieu malgré tout", ride_for(J1.isoformat())[0]["dest_place"] == "Clinique Nord")

    # ===== 5. persistance : après rechargement, la liste est là =====
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    goto("personnes"); tap('#plist .list-item:has-text("Alpha")')
    ok(tag + " après rechargement : les deux lieux dans la fiche", "Maison de repos" in pg.locator("#f-places").inner_text() and "Clinique Nord" in pg.locator("#f-places").inner_text())

    ok(tag + " aucune erreur JavaScript", not errs, errs)
    ok(tag + " pas de défilement de côté", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    b.close()

print("%s %d/%d réussis" % (tag, total - fails, total))
srv.shutdown()
raise SystemExit(1 if fails else 0)
