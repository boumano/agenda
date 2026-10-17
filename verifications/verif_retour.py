"""Version 0.7.1 : « Retour » d'une course (la personne revient avec quelqu'un d'autre).
Vérifie : la case Retour est cochée par défaut ; décochée, le montant et les km d'une course sont divisés par 2 (l'original est gardé) ;
recochée, ils reviennent exactement ; une course sans montant ni km reste « inconnu » (jamais 0) ; une course « pas faite » n'a pas de case ;
le fond violet de la case dans le calendrier, la légende seulement si le mois en contient une, le détail dans le libellé de la case ;
« Annuler » du message remet l'état d'avant ; rien n'est modifié en regardant.
Noms FICTIFS seulement. W et H par variables d'environnement, SCHEME=dark (défaut) ou light."""
import os, sys, threading, pathlib, http.server, functools
from datetime import date, timedelta
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
TODAY = date.today()
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

# mois précédent entier : toutes les dates passées, sans rien d'aujourd'hui
PM = (TODAY.replace(day=1) - timedelta(days=1)).replace(day=1)
def pm(day): return PM.replace(day=day)


def person(i, last, first, **kw):
    p = {"id": "00000000-0000-4000-8000-%012d" % i, "last_name": last, "first_name": first, "pickup_street": "1 rue Depart", "pickup_zip": "11111", "pickup_city": "Villedepart",
         "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible", "phone": "", "usual_price_cents": 1250, "usual_km_m": 8500,
         "archived": False, "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z",
         "schedule": {"mode": "weekly", "weekdays": [], "time_weekly": "09:00", "from": None, "to": None, "dates": [], "time_dates": None}}
    p.update(kw); return p


def ride(n, pid, dt, status=None, price=1250, km=8500):
    return {"id": "00000000-0000-4000-9000-%012d" % n, "person_id": pid, "date": dt.isoformat(), "time": "09:00", "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible",
            "price_cents": price, "km_m": km, "usual_price_cents": 1250, "usual_km_m": 8500, "status": status, "changed": False, "added": False, "skip": False,
            "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z", "deleted_at": None}


ALPHA = person(1, "Alpha", "Un")
R_OK = ride(1, ALPHA["id"], pm(5), "done")                       # faite, montant et km connus
R_NOPRICE = ride(2, ALPHA["id"], pm(7), None, price=None, km=None)  # pas notée, montant et km inconnus
R_KO = ride(3, ALPHA["id"], pm(6), "not_done")                    # pas faite : pas de case Retour


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="allow")
    cx.add_init_script(INIT)
    errs = []
    pg = cx.new_page()
    pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
    pg.on("console", lambda m: errs.append("console " + m.text) if m.type == "error" else None)

    w = lambda: pg.wait_for_timeout(300)
    tap = lambda sel: (pg.locator(sel).first.tap(), w())
    goto = lambda t: tap('.nav button.t[data-t="%s"]' % t)
    toast_msg = lambda: pg.locator("#toast span").inner_text() if pg.locator("#toast").is_visible() and pg.locator("#toast span").count() else ""
    cell = lambda dt: '#s-calendrier .cell[data-iso="%s"]' % dt.isoformat()
    mois_lbl = lambda: pg.locator("#s-calendrier .monthnav .lbl").inner_text().lower()

    def db_all(store):
        return pg.evaluate("""(s)=>new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result;const g=d.transaction(s).objectStore(s).getAll();g.onsuccess=()=>{d.close();r(g.result)}}})""", store)
    def ride_db(rid): return [r for r in db_all("rides") if r["id"] == rid][0]
    def boot():
        pg.goto(BASE); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(250)
    def seed(persons, rides):
        pg.evaluate("""async([ps,rs])=>{ for(const p of ps) await AG.putPerson(p); for(const r of rs) await AG.putRide(r) }""", [persons, rides])
        pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    def open_cal(txt="Un"):
        goto("personnes"); tap('#plist .list-item:has-text("%s")' % txt); tap('[data-a="calfiche"]')
    def to_month(first):
        for _ in range(30):
            if mois_lbl().startswith(MOIS[first.month - 1]) and mois_lbl().endswith(str(first.year)): return
            cur_m = [i for i, m_ in enumerate(MOIS) if mois_lbl().startswith(m_)][0] + 1; cur_y = int(mois_lbl().split()[-1])
            pg.locator('#s-calendrier [data-a="month"][data-d="%d"]' % (1 if (first.year, first.month) > (cur_y, cur_m) else -1)).tap(); pg.wait_for_timeout(80)

    boot()
    seed([ALPHA], [R_OK, R_NOPRICE, R_KO])
    open_cal(); to_month(PM)

    # ================= 1. la case dans la fenêtre du jour =================
    tap(cell(pm(5)))
    box = pg.locator("#ds-panel .rtbox")
    ok(tag + " course faite : une case « Retour compté » est là, cochée par défaut", box.count() == 1 and box.get_attribute("aria-pressed") == "true" and "on" in (box.get_attribute("class") or "") and "Retour compté" in box.inner_text(), box.inner_text() if box.count() else "absent")
    ok(tag + " la case est placée après le lieu, avant les boutons Fait / Pas fait", pg.evaluate("(()=>{const a=document.getElementById('ds-place'),b=document.querySelector('#ds-panel .rtbox');return !!(a&&b)&&!!(a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_FOLLOWING)&&!!(b.compareDocumentPosition(document.querySelector('#ds-panel [data-a=dsfait]'))&Node.DOCUMENT_POSITION_FOLLOWING)})()"))
    ok(tag + " avant de toucher : aucune case du calendrier n'a le fond violet", pg.locator("#s-calendrier .cell.rt").count() == 0)

    # ================= 2. décocher : prix et km divisés par 2 =================
    box.tap(); w()
    r1 = ride_db(R_OK["id"])
    ok(tag + " décochée : retour = non, montant 1250 → 625, km 8500 → 4250 (base)", r1.get("retour") is False and r1["price_cents"] == 625 and r1["km_m"] == 4250, r1)
    ok(tag + " l'original est gardé (1250 / 8500) pour pouvoir remettre", (r1.get("aller_retour_orig") or {}).get("price_cents") == 1250 and (r1.get("aller_retour_orig") or {}).get("km_m") == 8500, r1.get("aller_retour_orig"))
    ok(tag + " la case affiche « Retour non compté » et la précision « prix et km divisés par 2 »", pg.locator("#ds-panel .rtbox").get_attribute("aria-pressed") == "false" and "Retour non compté" in pg.locator("#ds-panel .rtbox").inner_text() and "divisés par 2" in pg.locator("#ds-panel .rtbox").inner_text(), pg.locator("#ds-panel .rtbox").inner_text())
    ok(tag + " message « Retour non compté : montant et km divisés par 2. »", toast_msg() == "Retour non compté : montant et km divisés par 2.", toast_msg())
    ok(tag + " la case du calendrier a maintenant le fond violet, et le libellé le dit", pg.locator(cell(pm(5))).get_attribute("class").find(" rt") >= 0 and "retour non compté" in (pg.locator(cell(pm(5))).get_attribute("aria-label") or ""), pg.locator(cell(pm(5))).get_attribute("aria-label"))
    ok(tag + " une légende « Retour non compté » apparaît (il y en a un ce mois-ci)", pg.locator("#s-calendrier .legend .sw.r").count() == 1 and "Retour non compté" in pg.locator("#s-calendrier .legend").inner_text())
    ok(tag + " la case garde son état (faite = coche bleue) : seul le fond change", pg.locator(cell(pm(5)) + " .i").count() >= 1 and pg.locator(cell(pm(5))).get_attribute("class").find(" t") >= 0)

    # ================= 3. « Annuler » du message =================
    pg.locator('#toast [data-a="undo"]').tap(); w()
    tap('#ds-panel [data-a="dsclose"]')
    r2 = ride_db(R_OK["id"])
    ok(tag + " « Annuler » : retour de nouveau compté, montant 1250 et km 8500", r2.get("retour") in (True, None) and r2["price_cents"] == 1250 and r2["km_m"] == 8500 and r2.get("aller_retour_orig") is None, r2)
    ok(tag + " … la case du calendrier n'est plus violette", pg.locator(cell(pm(5))).get_attribute("class").find(" rt") < 0)

    # ================= 4. remettre le retour : montant et km exacts =================
    tap(cell(pm(5))); pg.locator("#ds-panel .rtbox").tap(); w()
    pg.locator("#ds-panel .rtbox").tap(); w()
    r3 = ride_db(R_OK["id"])
    ok(tag + " décochée puis recochée : montant 1250 et km 8500 exactement (pas de centime perdu)", r3["price_cents"] == 1250 and r3["km_m"] == 8500 and r3.get("retour") in (True, None), r3)
    ok(tag + " message « Retour compté : montant et km remis. »", toast_msg() == "Retour compté : montant et km remis.", toast_msg())
    tap('#ds-panel [data-a="dsclose"]')

    # ================= 5. montant et km inconnus : restent inconnus =================
    tap(cell(pm(7))); pg.locator("#ds-panel .rtbox").tap(); w()
    r4 = ride_db(R_NOPRICE["id"])
    ok(tag + " course sans montant ni km : décochée, ils restent « inconnus » (null, jamais 0)", r4.get("retour") is False and r4["price_cents"] is None and r4["km_m"] is None, r4)
    pg.locator("#ds-panel .rtbox").tap(); w()
    tap('#ds-panel [data-a="dsclose"]')

    # ================= 6. course pas faite : pas de case =================
    tap(cell(pm(6)))
    ok(tag + " course « pas faite » : pas de case Retour", pg.locator("#ds-panel .rtbox").count() == 0)
    tap('#ds-panel [data-a="dsclose"]')

    # ================= 7. le total du mois suit la base =================
    ok(tag + " aucune erreur JavaScript", not errs, errs[:3])

    b.close()

print("TOTAL %d échec(s) sur %d" % (fails, total))
sys.exit(1 if fails else 0)
