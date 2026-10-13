"""Version 0.7.0 : le lieu de la course dans le calendrier d'une personne.
Vérifie : le lieu dans la fenêtre du jour (habituel, « changé » + rappel de l'habituel, « lieu inconnu »), les pastilles de couleur sur les jours hors habituel,
la légende (seulement les lieux du mois affiché, lieu habituel rappelé, nombre de courses hors habituel), un même lieu écrit avec des majuscules, accents ou espaces différents = un seul lieu,
une couleur et une lettre stables d'un mois à l'autre, une course à la corbeille sans effet, une personne sans course hors habituel (ni pastille ni légende),
aucune donnée créée ni modifiée en regardant, pas de défilement de côté. Noms FICTIFS seulement. W et H par variables d'environnement, SCHEME=dark (défaut) ou light."""
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


def ride(n, pid, dt, status=None, added=False, deleted=None, skip=False, price=1250, km=8500):
    return {"id": "00000000-0000-4000-9000-%012d" % n, "person_id": pid, "date": dt.isoformat(), "time": "09:00", "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible",
            "price_cents": price, "km_m": km, "usual_price_cents": 1250, "usual_km_m": 8500, "status": status, "changed": False, "added": added, "skip": skip,
            "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z", "deleted_at": deleted}



def ride_at(n, pid, dt, **kw):
    r = {"id": "00000000-0000-4000-9000-%012d" % n, "person_id": pid, "date": dt.isoformat(), "time": "09:00", "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible",
         "price_cents": 1250, "km_m": 8500, "usual_price_cents": 1250, "usual_km_m": 8500, "status": "done", "changed": False, "added": False, "skip": False,
         "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z", "deleted_at": None}
    r.update(kw); return r
def dest(place, street, zip_, city): return {"dest_place": place, "dest_street": street, "dest_zip": zip_, "dest_city": city, "changed": True}
CLINIQUE = dest("Clinique Nord", "9 rue Nord", "33333", "Nordville")
CLINIQUE_BIS = dest("  clinique   NORD ", "9 Rue  nord", "33333", "NORDVILLE")      # même lieu, écrit autrement
HOPITAL = dest("Hôpital Zéro", "5 avenue Zéro", "44444", "Zerovilla")
INCONNU = dest("", "", "", "")

ALPHA = person(1, "Alpha", "Un"); BETA = person(2, "Beta", "Deux")
def pm(day): return PM.replace(day=day)
def cm(day): return CM.replace(day=day)
# jours d'essai : les jours 5 à 11 du mois précédent, et le jour 3 du mois en cours (peut être dans le futur : une course enregistrée reste affichée)
D_USUAL, D_CLI, D_CLI2, D_HOP, D_UNK, D_DEL = pm(5), pm(6), pm(7), pm(8), pm(9), pm(10)
RIDES = [ride_at(1, ALPHA["id"], D_USUAL), ride_at(2, ALPHA["id"], D_CLI, **CLINIQUE), ride_at(3, ALPHA["id"], D_CLI2, **CLINIQUE_BIS), ride_at(4, ALPHA["id"], D_HOP, **HOPITAL),
         ride_at(5, ALPHA["id"], D_UNK, **INCONNU), ride_at(6, ALPHA["id"], D_DEL, **dest("Lieu Fantome", "0 rue Fantome", "99999", "Fantomville"), deleted_at="2026-01-02T00:00:00.000Z"),
         ride_at(7, ALPHA["id"], cm(3), **CLINIQUE), ride_at(8, BETA["id"], pm(6))]

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
    txt_ = lambda sel: pg.locator(sel).inner_text().strip()
    mois_lbl = lambda: pg.locator("#s-calendrier .monthnav .lbl").inner_text().lower()
    cell = lambda dt: '#s-calendrier .cell[data-iso="%s"]' % dt.isoformat()
    pastille = lambda dt: pg.evaluate("(s)=>{const e=document.querySelector(s+' .pl');return e?[e.textContent,e.className.replace('pl ','')]:null}", cell(dt))

    def db_all(store):
        return pg.evaluate("""(s)=>new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result;const g=d.transaction(s).objectStore(s).getAll();g.onsuccess=()=>{d.close();r(g.result)}}})""", store)
    def boot():
        pg.goto(BASE); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(250)
    def seed(persons, rides):
        pg.evaluate("""async([ps,rs])=>{ for(const p of ps) await AG.putPerson(p); for(const r of rs) await AG.putRide(r) }""", [persons, rides])
        pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    def open_cal(txt):
        goto("personnes"); tap('#plist .list-item:has-text("%s")' % txt); tap('[data-a="calfiche"]')
    def to_prev():
        tap('#s-calendrier [data-a="month"][data-d="-1"]')

    boot(); seed([ALPHA, BETA], RIDES)
    before = sorted([(r["id"], r["updated_at"], r.get("deleted_at")) for r in db_all("rides")])

    # ===== 1. mois précédent d'Alpha : pastilles =====
    open_cal("Alpha"); to_prev()
    ok(tag + " mois précédent affiché", mois_lbl() == "%s %d" % (MOIS[PM.month - 1], PM.year), mois_lbl())
    ok(tag + " lieu habituel : aucune pastille", pastille(D_USUAL) is None, pastille(D_USUAL))
    # ordre des lieux hors habituel (tri par nom, sans accents ni majuscules) : « lieu inconnu » (vide) = A, Clinique Nord = B, Hôpital Zéro = C
    ok(tag + " lieu inconnu : pastille A, couleur 0", pastille(D_UNK) == ["A", "c0"], pastille(D_UNK))
    ok(tag + " Clinique Nord : pastille B, couleur 1", pastille(D_CLI) == ["B", "c1"], pastille(D_CLI))
    ok(tag + " même clinique écrite avec majuscules, espaces et accents différents : même pastille B (un seul lieu)", pastille(D_CLI2) == ["B", "c1"], pastille(D_CLI2))
    ok(tag + " Hôpital Zéro : pastille C, couleur 2", pastille(D_HOP) == ["C", "c2"], pastille(D_HOP))
    ok(tag + " course à la corbeille : aucune pastille", pastille(D_DEL) is None, pastille(D_DEL))
    lab = pg.locator(cell(D_CLI)).get_attribute("aria-label")
    ok(tag + " étiquette lisible du jour : « … : transportée · hors habituel : Clinique Nord (B) »", lab.endswith(": transportée · hors habituel : Clinique Nord (B)"), lab)
    ok(tag + " les bordures gardent leur sens (bleu transportée) malgré la pastille", pg.locator(cell(D_CLI)).get_attribute("class").split()[1] == "t")

    # ===== 2. légende =====
    ok(tag + " légende : lieu habituel rappelé", txt_("#cal-places .ph:first-child") == "Lieu habituel : Lieu Cible", txt_("#cal-places .ph:first-child"))
    ok(tag + " légende : 4 courses hors habituel ce mois-ci (inconnu, clinique ×2, hôpital)", txt_("#cal-off") == "4 courses hors habituel ce mois-ci", txt_("#cal-off"))
    items = pg.evaluate("[...document.querySelectorAll('#cal-places li')].map(li=>[li.querySelector('.pl').textContent, li.querySelector('.pl').className.replace('pl ',''), li.querySelector('span:not(.pl)').textContent])")
    ok(tag + " légende : 3 lieux, dans l'ordre, avec lettre et couleur", items == [["A", "c0", "lieu inconnu"], ["B", "c1", "Clinique Nord"], ["C", "c2", "Hôpital Zéro"]], items)
    ok(tag + " le lieu à la corbeille n'apparaît nulle part", "Fantome" not in pg.locator("#s-calendrier").inner_text())
    bgs = pg.evaluate("[...document.querySelectorAll('#cal-places li .pl')].map(e=>getComputedStyle(e).backgroundColor)")
    ok(tag + " trois couleurs différentes", len(set(bgs)) == 3, bgs)
    ok(tag + " pas de défilement de côté", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth && document.querySelector('#s-calendrier .content').scrollWidth <= document.querySelector('#s-calendrier .content').clientWidth + 1"))
    pg.screenshot(path=SHOTS + "/lieux-cal-%s-%dx%d.png" % (SCHEME, W, H))

    # ===== 3. fenêtre du jour =====
    tap(cell(D_CLI))
    pl = txt_("#ds-place")
    ok(tag + " fenêtre du jour (hors habituel) : lieu, « changé », adresse, rappel de l'habituel", "Clinique Nord" in pl and "changé" in pl and "9 rue Nord" in pl and "habituel : Lieu Cible" in pl, pl)
    ok(tag + " fenêtre du jour : même pastille B que dans le calendrier", pg.locator("#ds-place .pl").inner_text() == "B")
    ok(tag + " les boutons Fait / Pas fait et les champs montant et km sont toujours là", pg.locator('#ds-panel [data-a="dsfait"]').count() == 1 and pg.locator("#ds-montant").count() == 1 and pg.locator("#ds-km").count() == 1)
    tap('#ds-panel [data-a="dsclose"]')
    tap(cell(D_USUAL)); pl = txt_("#ds-place")
    ok(tag + " fenêtre du jour (lieu habituel) : « Lieu Cible », ni « changé » ni pastille ni rappel", "Lieu Cible" in pl and "changé" not in pl and "habituel" not in pl and pg.locator("#ds-place .pl").count() == 0, pl)
    tap('#ds-panel [data-a="dsclose"]')
    tap(cell(D_UNK)); pl = txt_("#ds-place")
    ok(tag + " fenêtre du jour (destination vide) : « lieu inconnu » et rappel de l'habituel", "lieu inconnu" in pl and "habituel : Lieu Cible" in pl, pl)
    tap('#ds-panel [data-a="dsclose"]')
    # jour habituel sans course enregistrée (carte prévue) : lieu habituel
    vd = [dt for dt in (PM.replace(day=d) for d in range(11, 28)) if dt.isoweekday() <= 5][0]
    tap(cell(vd)); pl = txt_("#ds-place")
    ok(tag + " jour prévu sans course enregistrée : lieu habituel affiché", "Lieu Cible" in pl and "changé" not in pl, pl)
    tap('#ds-panel [data-a="dsclose"]')
    ok(tag + " regarder ne crée ni ne modifie aucune course", sorted([(r["id"], r["updated_at"], r.get("deleted_at")) for r in db_all("rides")]) == before)

    # ===== 4. mois en cours : couleurs stables =====
    tap('#s-calendrier [data-a="month"][data-d="1"]')
    ok(tag + " mois en cours : Clinique Nord = même pastille B, même couleur que le mois précédent", pastille(cm(3)) == ["B", "c1"], pastille(cm(3)))
    ok(tag + " légende du mois en cours : seulement Clinique Nord, 1 course hors habituel", txt_("#cal-off") == "1 course hors habituel ce mois-ci" and pg.locator("#cal-places li").count() == 1 and "Clinique Nord" in txt_("#cal-places li"))

    # ===== 5. personne sans course hors habituel =====
    open_cal("Beta") if False else None
    pg.evaluate("history.back()"); w(); pg.evaluate("history.back()"); w()
    open_cal("Beta"); to_prev()
    ok(tag + " personne sans course hors habituel : ni pastille ni légende", pg.locator("#s-calendrier .cell .pl").count() == 0 and pg.locator("#cal-places").count() == 0)

    ok(tag + " aucune erreur dans la console", not errs, errs[:3])
    b.close()
print("\n%s %d contrôles, %d échec(s)" % (tag, total, fails))
raise SystemExit(1 if fails else 0)
