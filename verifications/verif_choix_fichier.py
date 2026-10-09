"""Version 0.6.3 : « Vérifier une sauvegarde » / « Restaurer » ne perdent plus le fichier choisi quand le sélecteur de fichiers d'Android met l'appli en arrière-plan.
Simule : clic sur « Choisir le fichier », page cachée puis visible, choix du fichier ; choix pendant le masquage ; annulation ; rechargement forcé de la page. Fichiers de test FICTIFS.
W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, json, shutil, subprocess, sys, tempfile, threading, pathlib, http.server, functools, datetime, itertools
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
FILES = ("index.html", "garde.js", "app.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "style.css", "sw.js", "manifest.json", "version.js", "icon-192.png", "icon-512.png")
fails = 0; total = 0


def ok(n, c, e=""):
    global fails, total
    total += 1
    if not c: fails += 1
    print(("PASS " if c else "FAIL ") + n + (" | " + str(e)[:500] if not c else ""))


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def log_message(self, *a): pass


def serve(directory):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(directory)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d/" % srv.server_address[1]


# ---------------------------------------------------------------- 1. la liste de mots (sans navigateur)
src = (ROOT / "mots.js").read_text(encoding="utf-8")
words = re.search(r"self\.AG_WORDS = '([^']+)'\.split", src).group(1).split(" ")
PEOPLE = [
    {"id": "00000000-0000-4000-8000-0000000000a1", "last_name": "Zorglub", "first_name": "Alpha", "pickup_street": "42 rue Introuvable", "pickup_zip": "11111", "pickup_city": "Quenouilleville",
     "dest_place": "Clinique Fictive", "dest_street": "7 avenue Imaginaire", "dest_zip": "22222", "dest_city": "Bravoland", "phone": "0100000001", "usual_price_cents": 1250, "usual_km_m": 8500, "archived": False,
     "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z", "schedule": {"mode": "weekly", "weekdays": [1, 3], "time_weekly": "09:00", "from": None, "to": None, "dates": [], "time_dates": None}},
    {"id": "00000000-0000-4000-8000-0000000000a2", "last_name": "Quenouille", "first_name": "Bravo", "pickup_street": "8 impasse Fictive", "pickup_zip": "33333", "pickup_city": "Deltaville",
     "dest_place": "Centre Imaginaire", "dest_street": "9 rue Rien", "dest_zip": "44444", "dest_city": "Echoland", "phone": "", "usual_price_cents": None, "usual_km_m": None, "archived": False,
     "created_at": "2026-01-02T00:00:00.000Z", "updated_at": "2026-01-02T00:00:00.000Z", "schedule": {"mode": "dates", "weekdays": [], "time_weekly": None, "from": None, "to": None, "dates": ["2026-10-26"], "time_dates": "10:30"}},
    {"id": "00000000-0000-4000-8000-0000000000a3", "last_name": "Fantomas", "first_name": "Charlie", "pickup_street": "1 chemin Archive", "pickup_zip": "55555", "pickup_city": "Foxtrotville",
     "dest_place": "Lieu Archive", "dest_street": "2 chemin Archive", "dest_zip": "66666", "dest_city": "Golfland", "phone": "", "usual_price_cents": 990, "usual_km_m": 3000, "archived": True, "archived_at": "2026-05-01T00:00:00.000Z",
     "created_at": "2026-01-03T00:00:00.000Z", "updated_at": "2026-05-01T00:00:00.000Z", "schedule": {"mode": "weekly", "weekdays": [2], "time_weekly": None, "from": None, "to": None, "dates": [], "time_dates": None}},
]


def ride(n, pid, date, status, deleted=None):
    return {"id": "00000000-0000-4000-9000-%012d" % n, "person_id": pid, "date": date, "time": "09:00", "dest_place": "Clinique Fictive", "dest_street": "7 avenue Imaginaire", "dest_zip": "22222", "dest_city": "Bravoland",
            "price_cents": 1250, "km_m": 8500, "usual_price_cents": 1250, "usual_km_m": 8500, "status": status, "changed": False, "added": False, "skip": False,
            "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z", "deleted_at": deleted}


RIDES = [ride(1, PEOPLE[0]["id"], "2026-10-05", "done"), ride(2, PEOPLE[0]["id"], "2026-10-07", "not_done"), ride(3, PEOPLE[1]["id"], "2026-10-26", "done"),
         ride(4, PEOPLE[2]["id"], "2026-09-15", "done"), ride(5, PEOPLE[0]["id"], "2026-10-12", "done", "2026-10-13T08:00:00.000Z")]       # la 5e est à la corbeille
FUEL = [{"id": "00000000-0000-4000-a000-000000000001", "date": "2026-10-03", "price_milli": 1789, "liters_ml": 38500, "amount_cents": 6888, "calc": "amount", "created_at": "2026-10-03T08:00:00.000Z", "updated_at": "2026-10-03T08:00:00.000Z", "deleted_at": None},
        {"id": "00000000-0000-4000-a000-000000000002", "date": "2026-10-04", "price_milli": 1800, "liters_ml": 20000, "amount_cents": 3600, "calc": "amount", "created_at": "2026-10-04T08:00:00.000Z", "updated_at": "2026-10-04T08:00:00.000Z", "deleted_at": "2026-10-05T08:00:00.000Z"}]
OTHER_PEOPLE = [dict(PEOPLE[1], id="00000000-0000-4000-8000-0000000000b1", last_name="Delta", first_name="Telephone", pickup_street="3 rue Autre")]
MARKERS = ["Zorglub", "Quenouille", "Fantomas", "Introuvable", "Imaginaire", "Clinique", "Bravoland", "Quenouilleville", "0100000001", "Foxtrotville", "Archive", "Zorglub".lower()]

INIT = """window.__off=0; (function(){ var n=Date.now.bind(Date); Date.now=function(){ return n()+window.__off; }; })();
window.__clicks=[]; (function(){ var c=HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click=function(){ if(window.__noDownload && this.download) throw new Error('telechargement refuse'); return c.apply(this, arguments); }; })();"""

SNAP = """(async()=>{ const s = await AG.snapshotAll(); const by=(a)=>a.slice().sort((x,y)=>(x.id||x.key)<(y.id||y.key)?-1:1); return {persons:by(s.persons), rides:by(s.rides), fuel:by(s.fuel), settings:by(s.settings)} })()"""
META = """(async()=>({last: await AG.getMeta('last_export'), hasKey: !!(await AG.getMeta('backup_key')), safety: !!(await AG.getSafety())}))()"""

tmp = pathlib.Path(tempfile.mkdtemp(prefix="agenda_bk_"))
for n in FILES: shutil.copy(ROOT / n, tmp / n)
srv, BASE = serve(tmp)
dl_dir = pathlib.Path(tempfile.mkdtemp(prefix="agenda_dl_"))


def new_phone(p, offline=False):
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="block", accept_downloads=True, timezone_id="Europe/Paris", locale="fr-FR")
    cx.add_init_script(INIT)
    pg = cx.new_page(); reqs = []
    pg.on("request", lambda r: reqs.append(r.url)); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(300)
    return b, cx, pg, reqs, errs


def seed(pg, people, rides, fuel, idle=None):
    pg.evaluate("""async([ps,rs,fs,idle])=>{ for(const x of ps) await AG.putPerson(x); for(const x of rs) await AG.putRide(x); for(const x of fs) await AG.putFuel(x); if(idle!==null) await AG.putSetting('idle_sec', idle) }""", [people, rides, fuel, idle])
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(300)


def open_save(pg):
    pg.locator('.nav button.t[data-t="bilan"]').tap(); pg.wait_for_timeout(250); pg.locator('[data-a="reglages"]').tap(); pg.wait_for_timeout(250)
    pg.locator('[data-a="opensave"]').tap(); pg.wait_for_timeout(300)


def vis(pg, sel): return pg.evaluate("s=>{const e=document.querySelector(s);if(!e)return false;const r=e.getBoundingClientRect();return r.height>0&&r.width>0&&getComputedStyle(e).display!=='none'&&!e.hidden}", sel)
def text_of(pg, sel): return pg.locator(sel).inner_text() if pg.locator(sel).count() else ""
def screen_text(pg): return pg.evaluate("document.getElementById('s-sauvegarde').innerText")
def tap(pg, a, wait=300): pg.locator('[data-a="%s"]' % a).tap(); pg.wait_for_timeout(wait)
def wait_busy_done(pg): pg.wait_for_function("document.getElementById('bk-busy')===null", timeout=30000); pg.wait_for_timeout(200)
def eye(pg): pg.locator('#s-sauvegarde [data-a="hide"]').tap(); pg.wait_for_timeout(300)
def unmask(pg): pg.locator("#veil").tap(); pg.wait_for_timeout(300)
def set_clock(pg, local_iso):
    """avance (ou recule) l'horloge de l'appli ; le saut peut masquer l'écran (comme sur un vrai téléphone) : on le rouvre"""
    pg.evaluate("t=>{ window.__off = new Date(t).getTime() - (Date.now() - window.__off) }", local_iso)
    pg.wait_for_timeout(1500)
    if pg.evaluate("__ag.masked"): unmask(pg)




MIN = 60000
PAPER = "Avant de commencer : prenez un papier et un stylo. Vous avez 10 minutes."
GONE = "Pour votre sécurité, la phrase a été effacée. Une nouvelle phrase va être créée."
DUMP = """(async()=>{ const out=[]; const dbs = await indexedDB.databases();
  for (const d of dbs){ const db = await new Promise((res,rej)=>{const r=indexedDB.open(d.name); r.onsuccess=()=>res(r.result); r.onerror=()=>rej(r.error)});
    for (const sn of db.objectStoreNames){ const tx=db.transaction(sn,'readonly'); const all = await new Promise((res,rej)=>{const r=tx.objectStore(sn).getAll(); r.onsuccess=()=>res(r.result); r.onerror=()=>rej(r.error)}); out.push(sn, JSON.stringify(all)); }
    db.close(); }
  out.push(JSON.stringify(Object.assign({},localStorage)), JSON.stringify(Object.assign({},sessionStorage)));
  for (const k of await caches.keys()){ const c = await caches.open(k); for (const rq of await c.keys()){ out.push(rq.url); out.push(await (await c.match(rq)).clone().text()) } }
  out.push(document.title); return out.join('\\n') })()"""
BUNDLE = "(async()=>{ const k = await AG.getMeta('backup_key'); return JSON.stringify([k.kdf, k.wrapped]) })()"
NOKEY = "(async()=>!(await AG.getMeta('backup_key')))()"


def leaks(pg, phrase):
    """mots de la phrase retrouvés dans IndexedDB (toutes les bases et tous les magasins, journal compris), localStorage, sessionStorage, caches"""
    d = pg.evaluate(DUMP)
    return [w for w in phrase if ('"%s"' % w) in d] + ([" ".join(phrase)] if " ".join(phrase) in d else [])


def hide_app(pg):
    pg.evaluate("Object.defineProperty(document,'hidden',{get:()=>true,configurable:true}); document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('pagehide'))")
    pg.wait_for_timeout(300)


def show_app(pg):
    pg.evaluate("Object.defineProperty(document,'hidden',{get:()=>false,configurable:true}); document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('pageshow'))")
    pg.wait_for_timeout(300)


def advance(pg, ms): pg.evaluate("n=>{ window.__off += n }", ms); pg.wait_for_timeout(1600)
def bkstate(pg): return pg.evaluate("__ag.bk")
def shown_words(pg): return pg.evaluate("[...document.querySelectorAll('#bk-words .w')].map(e=>e.textContent)")
def back_to_screen(pg):
    if pg.evaluate("__ag.masked"): unmask(pg)


def confirm_ok(pg, phrase, expect_download=False):
    tap(pg, "bk-written")
    a, bq = pg.evaluate("__ag.bk.ask")
    pg.fill("#bk-w1", phrase[a - 1]); pg.fill("#bk-w2", phrase[bq - 1])
    if expect_download:
        with pg.expect_download(timeout=30000) as d: tap(pg, "bk-confirm", 100)
        wait_busy_done(pg); return d.value
    tap(pg, "bk-confirm", 100); wait_busy_done(pg)


def save_dl(d, name):
    f = dl_dir / name; d.save_as(str(f)); return f.read_text(encoding="utf-8")


def try_open(pg, text, phrase):
    return pg.evaluate("""async([t,ph])=>{ try { const o = await AGB.openFile(t, ph, 5); return 'ok:' + o.counts.persons } catch(e) { return e.code || String(e) } }""", [text, " ".join(phrase)])


def lire(text, phrase, name):
    f = dl_dir / name; f.write_text(text, encoding="utf-8")
    env = dict(os.environ, AGENDA_PHRASE=" ".join(phrase), PYTHONUTF8="1")
    return subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "tools" / "lire_export.py"), str(f), "-o", str(dl_dir / (name + ".json"))], capture_output=True, text=True, encoding="utf-8", env=env)



def strip_accents(w):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c))

PHR = " ".join(words[100:110])
NAME = "agenda-test-fictif.agenda"
MAKE = """async(ph)=>{ const b = await AGB.createKeyBundle(ph); return await AGB.buildFile(b, {persons:[{id:'p1',first_name:'Test'}], rides:[], fuel:[], settings:[]}, 5, '0.6.3', new Date('2026-10-20T08:00:00Z')) }"""
LOG = "AG.getLog().then(l=>l.map(x=>x.e))"


def journal(pg): return pg.evaluate(LOG)
def label(pg): return pg.locator('label[for="bk-file"]')


def to_pick(pg, mode="bk-verify"):
    """écran Sauvegarde, étape « choisir le fichier »"""
    if not pg.locator('[data-a="%s"]' % mode).count(): tap(pg, "bk-cancel")
    tap(pg, mode)


def click_label(pg):
    with pg.expect_file_chooser() as fc: label(pg).tap()
    pg.wait_for_timeout(200)
    return fc.value


def send(pg, chooser, name=NAME):
    f = dl_dir / name; f.write_text(FILE_TEXT, encoding="utf-8"); chooser.set_files(str(f)); pg.wait_for_timeout(600)


def got_file(pg):
    t = screen_text(pg)
    return NAME in t and "Tapez la phrase" in t and vis(pg, "#bk-phrase")


with sync_playwright() as p:
    b, cx, pg, reqs, errs = new_phone(p)
    seed(pg, PEOPLE, RIDES, FUEL, 600)
    set_clock(pg, '2026-10-20T10:07:00')
    FILE_TEXT = pg.evaluate(MAKE, PHR)
    pg.evaluate("document.querySelector('[data-a=idle][data-n=\"60\"]').click()")          # masquage automatique : 1 minute
    j0 = journal(pg)
    ok(tag + " « Démarrage » : version, puis ligne de diagnostic (type de navigation, affichage, page rejetée)", any(x.startswith("Démarrage de la version") for x in j0) and any(x.startswith("Démarrage : type de navigation") and "affichage" in x and "page rejetée" in x for x in j0), j0)
    ok(tag + " l'entrée « fichier » est permanente : dans index.html, hors de la vue Sauvegarde", pg.evaluate("document.getElementById('bk-file') && !document.getElementById('s-sauvegarde').contains(document.getElementById('bk-file'))"))
    open_save(pg); to_pick(pg)
    el0 = pg.evaluate("window.__inp = document.getElementById('bk-file'); true")

    # ---- scénario A : clic, page cachée puis visible, puis choix
    ch = click_label(pg)
    ok(tag + " clic sur « Choisir le fichier » : journal « Choix du fichier : ouvert »", "Choix du fichier : ouvert" in journal(pg))
    hide_app(pg)
    ok(tag + " A. pendant que le sélecteur est ouvert, l'appli cachée N'EST PAS masquée (le sélecteur d'Android ne la fait plus repartir de zéro)", not pg.evaluate("__ag.masked"))
    advance(pg, 3 * MIN)
    show_app(pg)
    ok(tag + " A. retour après 3 minutes : toujours pas masquée, étape « choisir le fichier » intacte, même entrée <input> (jamais recréée)", not pg.evaluate("__ag.masked") and vis(pg, 'label[for="bk-file"]') and pg.evaluate("window.__inp === document.getElementById('bk-file')"))
    send(pg, ch)
    ok(tag + " A. fichier choisi : son NOM s'affiche et la phrase est demandée", got_file(pg), screen_text(pg)[:300])
    pg.screenshot(path=SHOTS + "/choix_fichier_recu_%dx%d_%s.png" % (W, H, SCHEME))
    j = journal(pg)
    ok(tag + " A. journal : ouvert, appli cachée, appli revenue, reçu (nom et taille)", all(any(x == m or x.startswith(m) for x in j) for m in ("Choix du fichier : ouvert", "Appli cachée", "Appli revenue", "Choix du fichier : reçu (" + NAME + ", ")), j)
    pg.fill("#bk-phrase", strip_accents(PHR).upper()); tap(pg, "bk-open", 100); wait_busy_done(pg)
    ok(tag + " A. suite : la phrase ouvre le fichier (« Sauvegarde valide »)", "Sauvegarde valide" in screen_text(pg), screen_text(pg)[:200])
    ok(tag + " A. la phrase tapée n'est ni dans le journal ni dans un stockage", leaks(pg, PHR.split()) == [] and not any(w in " ".join(journal(pg)).split() for w in PHR.split()))
    tap(pg, "bk-cancel")

    # ---- scénario B : le fichier arrive pendant que la page est CACHÉE, puis retour
    to_pick(pg); ch = click_label(pg)
    hide_app(pg); send(pg, ch); show_app(pg)
    ok(tag + " B. fichier reçu pendant que l'appli est cachée : au retour, nom + demande de phrase", got_file(pg), screen_text(pg)[:300])
    tap(pg, "bk-cancel")

    # ---- scénario C : l'écran a été masqué entre-temps (délai de 10 minutes du sélecteur dépassé), le fichier arrive pendant le masquage
    to_pick(pg); ch = click_label(pg)
    hide_app(pg); advance(pg, 11 * MIN); pg.wait_for_function("__ag.masked", timeout=6000)
    send(pg, ch)
    ok(tag + " C. écran masqué : rien de lisible sous l'écran neutre (ni nom ni phrase)", pg.evaluate("document.getElementById('s-sauvegarde').innerHTML") == "" or NAME not in pg.evaluate("document.getElementById('s-sauvegarde').innerText"))
    show_app(pg); back_to_screen(pg)
    ok(tag + " C. après avoir touché l'écran neutre : le fichier choisi n'est PAS perdu (nom + demande de phrase)", got_file(pg), screen_text(pg)[:300])
    tap(pg, "bk-cancel")

    # ---- scénario D : le sélecteur est annulé
    to_pick(pg); label(pg).tap(); pg.wait_for_timeout(300)
    pg.evaluate("document.getElementById('bk-file').dispatchEvent(new Event('cancel'))"); pg.wait_for_timeout(300)
    j = journal(pg)
    ok(tag + " D. annulation : journal « Choix du fichier : annulé », on reste à l'étape « choisir le fichier »", "Choix du fichier : annulé" in j and vis(pg, 'label[for="bk-file"]') and vis(pg, '[data-a="bk-cancel"]'), j[-4:])
    advance(pg, 3 * MIN)
    ok(tag + " D. après l'annulation le masquage automatique reprend (1 minute)", pg.evaluate("__ag.masked"))
    back_to_screen(pg)

    # ---- scénario E : mode « Restaurer » (même chemin)
    if pg.evaluate("__ag.masked"): unmask(pg)
    if not pg.locator('[data-a="bk-restore"]').count(): tap(pg, "bk-cancel")
    tap(pg, "bk-restore"); ch = click_label(pg); hide_app(pg); show_app(pg); send(pg, ch)
    ok(tag + " E. « Restaurer » : même comportement (nom + demande de phrase)", got_file(pg) and "restaurer" in screen_text(pg).lower(), screen_text(pg)[:200])
    tap(pg, "bk-cancel")

    # ---- scénario F : choisir deux fois le même fichier de suite
    to_pick(pg); ch = click_label(pg); send(pg, ch); tap(pg, "bk-cancel")
    to_pick(pg); ch = click_label(pg); send(pg, ch)
    ok(tag + " F. le même fichier rechoisi une 2e fois est bien reçu", got_file(pg))
    tap(pg, "bk-cancel")
    ok(tag + " aucune erreur de page (scénarios A à F)", errs == [], errs)

    # ---- scénario G : rechargement FORCÉ de la page entre le clic et le choix (Android qui tue la page)
    to_pick(pg); ch = click_label(pg)
    n_before = len(journal(pg))
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(400)
    j = journal(pg)
    ok(tag + " G. après rechargement : journal « Choix du fichier : ouvert » PUIS « Démarrage … type de navigation reload »", "Choix du fichier : ouvert" in j and any(x.startswith("Démarrage : type de navigation reload") for x in j) and max(i for i, x in enumerate(j) if x == "Choix du fichier : ouvert") < max(i for i, x in enumerate(j) if x.startswith("Démarrage : type de navigation reload")), j[-6:])
    st = pg.evaluate("[__ag.bk.step, __ag.bk.hasPhrase]"); cur = pg.evaluate("document.querySelector('.nav button.t[aria-selected=\"true\"],.nav button.t.on,.nav button.t.active') ? document.querySelector('.nav button.t[aria-selected=\"true\"],.nav button.t.on,.nav button.t.active').dataset.t : null")
    ok(tag + " G. après rechargement : l'appli repart de zéro (accueil de la sauvegarde, aucun état de choix en cours, pas d'erreur)", st[0] == "home" and not pg.evaluate("__ag.masked"), (st, cur))
    # un fichier livré à la page rechargée, sans « Vérifier » en cours : ignoré proprement
    f = dl_dir / NAME; f.write_text(FILE_TEXT, encoding="utf-8")
    pg.set_input_files("#bk-file", str(f)); pg.wait_for_timeout(500)
    ok(tag + " G. un fichier livré à la page rechargée (aucun « Vérifier » en cours) est ignoré sans erreur ; il faut recommencer « Choisir le fichier »", pg.evaluate("__ag.bk.step") == "home", pg.evaluate("__ag.bk.step"))
    pg.screenshot(path=SHOTS + "/choix_fichier_recharge_%dx%d_%s.png" % (W, H, SCHEME))
    open_save(pg); to_pick(pg); ch = click_label(pg); send(pg, ch)
    ok(tag + " G. … et en recommençant après le rechargement, tout fonctionne", got_file(pg))
    b.close()
srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(dl_dir, ignore_errors=True)
print("TOTAL", total, "ECHECS", fails)
raise SystemExit(1 if fails else 0)
