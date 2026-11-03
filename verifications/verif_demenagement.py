"""Version 0.9.1 : corriger une adresse (faute, partout) ou déménager (à partir d'une date) : domicile et lieu habituel. Noms FICTIFS seulement."""
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


ROW_PAST = {"id": "00000000-0000-4000-9000-000000000101", "person_id": ALPHA["id"], "date": (date.today() - timedelta(days=10)).isoformat(), "time": "09:00",
            "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible", "price_cents": 1250, "km_m": 8500,
            "usual_price_cents": 1250, "usual_km_m": 8500, "status": "done", "changed": False, "added": False, "skip": False,
            "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z", "deleted_at": None}
ROW_FUT = dict(ROW_PAST, id="00000000-0000-4000-9000-000000000102", date=None, status=None)

with sync_playwright() as p:
    try: b = p.chromium.launch(channel="msedge", headless=True)
    except Exception: b = p.chromium.launch(channel=None, headless=True)
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
    def seed(persons, rides):
        pg.evaluate("""async([ps,rs])=>{ for(const p of ps) await AG.putPerson(p); for(const r of rs) await AG.putRide(r) }""", [persons, rides])
        pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    def person_now():
        return [x for x in db_all("persons") if x["id"] == ALPHA["id"]][0]
    def ride_now(iso):
        return [x for x in db_all("rides") if x["date"] == iso][0]
    def open_fiche():
        goto("personnes"); tap('#plist .list-item:has-text("Alpha")')

    boot(); seed([ALPHA], [dict(ROW_PAST, date=(date.today() - timedelta(days=10)).isoformat()), dict(ROW_FUT, date=J1.isoformat())])
    PAST = (date.today() - timedelta(days=10)).isoformat(); FUT = J1.isoformat()

    # 1. faute de frappe sur le lieu habituel : corrigé partout, y compris la course passée
    open_fiche(); tap('[data-a="fxedit"][data-i="h"]')
    ok(tag + " édition du lieu habituel ouverte", pg.locator("#f-edit").is_visible())
    fill("#f-erue", "2 rue Cibles"); tap('[data-a="fxfaute"]')
    pn = person_now()
    ok(tag + " faute : adresse habituelle corrigée", pn["dest_street"] == "2 rue Cibles" and not pn.get("dest_moves"), (pn.get("dest_street"), pn.get("dest_moves")))
    ok(tag + " faute : la course passée est corrigée aussi", ride_now(PAST)["dest_street"] == "2 rue Cibles", ride_now(PAST))
    ok(tag + " faute : la course à venir aussi", ride_now(FUT)["dest_street"] == "2 rue Cibles", ride_now(FUT))

    # 2. une adresse modifiée directement dans les champs est refusée (il faut passer par « Lieux »)
    ok(tag + " adresse en lecture seule : pas de champ modifiable, bouton « Corriger ou déménager »", pg.locator("#f-rue").count() == 1 and not pg.locator("#f-rue").is_visible() and pg.locator('[data-a="fxedit"][data-i="d"]').is_visible())
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()

    # 3. déménagement du domicile à partir d'une date : l'ancienne adresse reste pour les jours d'avant
    D = J2.isoformat(); open_fiche(); tap('[data-a="fxedit"][data-i="d"]')
    fill("#f-erue", "8 avenue Nouvelle"); fill("#f-ecp", "6666"); fill("#f-eville", "Nouvilla"); fill("#f-edate", D)
    tap('[data-a="fxdem"]')
    pn = person_now()
    ok(tag + " déménagement domicile : une entrée d'historique, avec l'ancienne adresse et la date", len(pn.get("pick_moves", [])) == 1 and pn["pick_moves"][0]["date"] == D and pn["pick_moves"][0]["old"]["street"] == "1 rue Depart", pn.get("pick_moves"))
    ok(tag + " déménagement domicile : nouvelle adresse dans la fiche", pn["pickup_street"] == "8 avenue Nouvelle" and pn["pickup_city"] == "Nouvilla", pn.get("pickup_street"))
    eff = pg.evaluate("[AGR.effectivePick(__ag.people.find(x=>x.id==='%s'), '%s').street, AGR.effectivePick(__ag.people.find(x=>x.id==='%s'), '%s').street]" % (ALPHA["id"], FUT, ALPHA["id"], D))
    ok(tag + " la veille du déménagement : ancienne adresse ; le jour même : nouvelle", eff == ["1 rue Depart", "8 avenue Nouvelle"], eff)

    # 4. déménagement du lieu habituel : les courses d'avant gardent l'ancienne adresse
    D2 = J3.isoformat(); open_fiche(); tap('[data-a="fxedit"][data-i="h"]')
    fill("#f-erue", "3 rue Neuve"); fill("#f-edate", D2); tap('[data-a="fxdem"]')
    pn = person_now()
    ok(tag + " déménagement lieu habituel : historique enregistré", len(pn.get("dest_moves", [])) == 1 and pn["dest_moves"][0]["old"]["street"] == "2 rue Cibles", pn.get("dest_moves"))
    ok(tag + " course passée et course à venir (avant la date) : ancienne adresse", ride_now(PAST)["dest_street"] == "2 rue Cibles" and ride_now(FUT)["dest_street"] == "2 rue Cibles", (ride_now(PAST)["dest_street"], ride_now(FUT)["dest_street"]))
    eff = pg.evaluate("[AGR.effectiveDest(__ag.people.find(x=>x.id==='%s'), '%s').street, AGR.effectiveDest(__ag.people.find(x=>x.id==='%s'), '%s').street]" % (ALPHA["id"], FUT, ALPHA["id"], D2))
    ok(tag + " habituel : avant la date ancienne adresse, à partir de la date nouvelle", eff == ["2 rue Cibles", "3 rue Neuve"], eff)

    # 5. pas de déménagement sans date
    open_fiche(); tap('[data-a="fxedit"][data-i="h"]'); fill("#f-erue", "4 rue Sans"); fill("#f-edate", ""); tap('[data-a="fxdem"]')
    ok(tag + " déménagement sans date refusé", "date du déménagement" in pg.locator("#f-e-err").inner_text(), pg.locator("#f-e-err").inner_text())
    tap('[data-a="fxecancel"]')

    ok(tag + " aucune erreur JavaScript", not errs, errs)
    ok(tag + " pas de défilement de côté", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    b.close()

print("%s %d/%d réussis" % (tag, total - fails, total))
srv.shutdown()
raise SystemExit(1 if fails else 0)
