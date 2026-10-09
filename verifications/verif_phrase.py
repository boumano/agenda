"""Version 0.6.1 : phrase affichée pendant 10 minutes au plus (pause du masquage, retour d'une autre appli, effacement après 10 minutes ou par l'œil, rien dans le
stockage du navigateur) et « Créer une nouvelle phrase » (l'ancienne phrase ouvre l'ancien fichier mais PAS le nouveau, rien de définitif tant que la confirmation échoue,
test croisé avec tools/lire_export.py). Noms et valeurs FICTIFS seulement. W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
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


with sync_playwright() as p:
    b, cx, pg, reqs, errs = new_phone(p)
    seed(pg, PEOPLE, RIDES, FUEL, 600)
    set_clock(pg, '2026-10-20T10:07:00')
    pg.evaluate("document.querySelector('[data-a=idle][data-n=\"60\"]').click()")          # masquage automatique réglé à 1 minute
    open_save(pg)
    # ---- accueil et explication avant la phrase
    ok(tag + " accueil sans phrase créée : ligne « prenez un papier et un stylo, 10 minutes », pas de bouton « nouvelle phrase »", PAPER in screen_text(pg) and pg.locator('[data-a="bk-renew"]').count() == 0, screen_text(pg)[:200])
    tap(pg, "bk-export")
    ok(tag + " écran d'explication du premier export : la même ligne est là", PAPER in screen_text(pg))
    pg.screenshot(path=SHOTS + "/phrase_explication_%dx%d_%s.png" % (W, H, SCHEME))
    tap(pg, "bk-show"); P = bkstate(pg)["phrase"]
    ok(tag + " phrase affichée : 10 mots + compte à rebours discret « encore 10 min »", shown_words(pg) == P and "Cette phrase reste affichée encore 10 min" in screen_text(pg), screen_text(pg)[:300])
    pg.screenshot(path=SHOTS + "/phrase_affichee_%dx%d_%s.png" % (W, H, SCHEME))
    # ---- pause du masquage (réglé à 1 minute)
    advance(pg, 5 * MIN)
    ok(tag + " 5 minutes sans toucher (réglage : 1 minute) : le masquage automatique est en PAUSE, phrase intacte, « encore 5 min »",
       not pg.evaluate("__ag.masked") and shown_words(pg) == P and "encore 5 min" in screen_text(pg), (pg.evaluate("__ag.masked"), screen_text(pg)[:200]))
    ok(tag + " … la phrase n'est dans AUCUN stockage du navigateur (IndexedDB, localStorage, sessionStorage, caches)", leaks(pg, P) == [], leaks(pg, P))
    # ---- quitter l'appli puis revenir
    hide_app(pg)
    ok(tag + " autre application / autre onglet : l'écran est vidé (rien de lisible), la phrase reste EN MÉMOIRE", pg.evaluate("__ag.masked") and pg.evaluate("document.getElementById('s-sauvegarde').innerHTML") == "" and bkstate(pg)["phrase"] == P and pg.locator("#bk-count").count() == 0)
    ok(tag + " … toujours aucune trace dans les stockages pendant l'absence", leaks(pg, P) == [])
    advance(pg, 3 * MIN)
    show_app(pg); unmask(pg)
    ok(tag + " retour après 3 minutes (grand écart d'horodatage) : la MÊME phrase, au même écran, « encore 2 min »", shown_words(pg) == P and "encore 2 min" in screen_text(pg) and bkstate(pg)["step"] == "phrase", (shown_words(pg), screen_text(pg)[:200]))
    # ---- étape de confirmation : mêmes règles
    tap(pg, "bk-written"); ask0 = bkstate(pg)["ask"]
    hide_app(pg); show_app(pg); unmask(pg)
    ok(tag + " étape de confirmation : après un aller-retour, on y est toujours (mêmes mots demandés), compte à rebours visible", bkstate(pg)["step"] == "confirm" and bkstate(pg)["ask"] == ask0 and vis(pg, "#bk-w1") and "encore" in screen_text(pg))
    # ---- dépassement des 10 minutes, écran visible
    advance(pg, 3 * MIN)
    st = bkstate(pg)
    ok(tag + " après 10 minutes : phrase effacée, message simple, retour à l'explication", st["hasPhrase"] is False and st["step"] == "explain" and GONE in screen_text(pg) and " ".join(P[:3]) not in screen_text(pg), screen_text(pg)[:300])
    ok(tag + " … rien d'enregistré (pas de trousseau), aucune trace de la phrase", pg.evaluate(NOKEY) and leaks(pg, P) == [])
    pg.screenshot(path=SHOTS + "/phrase_effacee_%dx%d_%s.png" % (W, H, SCHEME))
    # ---- dépassement des 10 minutes pendant l'absence
    tap(pg, "bk-show"); P2 = bkstate(pg)["phrase"]
    hide_app(pg); advance(pg, 11 * MIN); show_app(pg); back_to_screen(pg)
    ok(tag + " absence de 11 minutes : au retour, phrase effacée + message, la phrase n'est plus nulle part", bkstate(pg)["hasPhrase"] is False and GONE in screen_text(pg) and " ".join(P2[:3]) not in screen_text(pg) and leaks(pg, P2) == [], screen_text(pg)[:300])
    # ---- l'œil
    if bkstate(pg)["step"] != "explain": tap(pg, "bk-export")
    tap(pg, "bk-show"); P3 = bkstate(pg)["phrase"]
    eye(pg)
    ok(tag + " l'œil : masque tout de suite ET définitivement (phrase effacée de la mémoire)", pg.evaluate("__ag.masked") and bkstate(pg)["hasPhrase"] is False and pg.evaluate("document.getElementById('s-sauvegarde').innerHTML") == "")
    unmask(pg)
    ok(tag + " … au retour : il faut recommencer, la phrase ne revient pas", " ".join(P3[:3]) not in screen_text(pg) and pg.locator("#bk-words").count() == 0 and "recommencez" in screen_text(pg) and pg.evaluate(NOKEY))
    # ---- premier export complet
    tap(pg, "bk-export"); tap(pg, "bk-show"); P4 = bkstate(pg)["phrase"]
    d = confirm_ok(pg, P4, True); text1 = save_dl(d, "un.agenda")
    ok(tag + " premier export mené à bout : fichier produit, version 0.6.1 dans l'en-tête", json.loads(text1)["app_version"] == "0.6.1" and bkstate(pg)["hasKey"] is True)
    # ---- nouvelle phrase
    ok(tag + " accueil avec phrase confirmée : bouton « Créer une nouvelle phrase », plus de ligne « papier et stylo »", pg.locator('[data-a="bk-renew"]').count() == 1 and PAPER not in screen_text(pg))
    pg.screenshot(path=SHOTS + "/phrase_accueil_%dx%d_%s.png" % (W, H, SCHEME))
    bundle0 = pg.evaluate(BUNDLE)
    tap(pg, "bk-renew"); t = screen_text(pg)
    ok(tag + " explication : ancienne phrase seulement pour les anciens fichiers, nouveaux exports avec la nouvelle, export juste après, papier et stylo",
       "nouvelle phrase" in t.lower() and "L’ancienne phrase ne servira plus qu’à ouvrir les fichiers déjà exportés avec elle" in t and "prochains exports utiliseront la nouvelle" in t and "export tout de suite après" in t and PAPER in t, t[:400])
    pg.screenshot(path=SHOTS + "/phrase_nouvelle_explication_%dx%d_%s.png" % (W, H, SCHEME))
    tap(pg, "bk-show"); P5 = bkstate(pg)["phrase"]
    ok(tag + " nouvelle phrase : 10 mots, différente de l'ancienne", len(P5) == 10 and P5 != P4 and shown_words(pg) == P5)
    tap(pg, "bk-written"); a, bq = pg.evaluate("__ag.bk.ask")
    pg.fill("#bk-w1", "zzzz"); pg.fill("#bk-w2", P5[bq - 1]); tap(pg, "bk-confirm")
    ok(tag + " confirmation ratée : message, même phrase, RIEN de définitif (trousseau inchangé)", "pas bon" in screen_text(pg) and shown_words(pg) == P5 and pg.evaluate(BUNDLE) == bundle0)
    eye(pg); unmask(pg)
    ok(tag + " œil avant confirmation : on recommence, trousseau toujours celui d'avant", pg.evaluate(BUNDLE) == bundle0 and leaks(pg, P5) == [])
    # 2e essai : phrase expirée pendant la création
    tap(pg, "bk-renew"); tap(pg, "bk-show"); advance(pg, 11 * MIN); back_to_screen(pg)
    ok(tag + " nouvelle phrase non confirmée en 10 minutes : effacée, message, on reste dans le parcours « nouvelle phrase », trousseau inchangé",
       GONE in screen_text(pg) and "nouvelle phrase" in screen_text(pg).lower() and bkstate(pg)["renew"] is True and pg.evaluate(BUNDLE) == bundle0, screen_text(pg)[:200])
    # 3e essai : jusqu'au bout
    tap(pg, "bk-show"); P6 = bkstate(pg)["phrase"]
    confirm_ok(pg, P6)
    bundle1 = pg.evaluate(BUNDLE)
    ok(tag + " confirmation réussie : trousseau remplacé (nouveau sel), aucun téléchargement automatique, bouton « Exporter maintenant »", bundle1 != bundle0 and json.loads(bundle1)[0]["salt"] != json.loads(bundle0)[0]["salt"] and vis(pg, '[data-a="bk-export"]') and "Exporter maintenant" in screen_text(pg), screen_text(pg)[:300])
    pg.screenshot(path=SHOTS + "/phrase_nouvelle_ok_%dx%d_%s.png" % (W, H, SCHEME))
    log = pg.evaluate("AG.getLog().then(l=>l.map(x=>x.e))")
    ok(tag + " journal : « Phrase de récupération renouvelée », sans rien de lisible", "Phrase de récupération renouvelée" in log and leaks(pg, P6) == [] and leaks(pg, P4) == [] and leaks(pg, P5) == [], log[-4:])
    with pg.expect_download(timeout=30000) as dd: tap(pg, "bk-export", 100)
    wait_busy_done(pg); text2 = save_dl(dd.value, "deux.agenda")
    h1, h2 = json.loads(text1), json.loads(text2)
    ok(tag + " « Exporter maintenant » : nouveau fichier avec la NOUVELLE enveloppe seulement (autre sel, autre clé enveloppée)", h2["kdf"]["salt"] != h1["kdf"]["salt"] and h2["wrapped_key"] != h1["wrapped_key"])
    # ---- qui ouvre quoi
    r = {"ancien/ancienne": try_open(pg, text1, P4), "ancien/nouvelle": try_open(pg, text1, P6), "nouveau/nouvelle": try_open(pg, text2, P6), "nouveau/ancienne": try_open(pg, text2, P4)}
    ok(tag + " l'ancienne phrase ouvre l'ANCIEN fichier", r["ancien/ancienne"] == "ok:3", r)
    ok(tag + " l'ancienne phrase n'ouvre PAS le NOUVEAU fichier", r["nouveau/ancienne"] == "phrase", r)
    ok(tag + " la nouvelle phrase ouvre le NOUVEAU fichier", r["nouveau/nouvelle"] == "ok:3", r)
    ok(tag + " la nouvelle phrase n'ouvre pas l'ancien fichier (chaque fichier = sa phrase)", r["ancien/nouvelle"] == "phrase", r)
    # ---- test croisé avec le script du PC
    c1 = lire(text1, P4, "c1.agenda"); c2 = lire(text2, P6, "c2.agenda"); c3 = lire(text2, P4, "c3.agenda"); c4 = lire(text1, P6, "c4.agenda")
    ok(tag + " tools/lire_export.py : ancien fichier + ancienne phrase OK, nouveau fichier + nouvelle phrase OK", c1.returncode == 0 and c2.returncode == 0 and "Sauvegarde valide" in c1.stdout and "Sauvegarde valide" in c2.stdout, (c1.stderr, c2.stderr))
    ok(tag + " … nouveau fichier + ancienne phrase REFUSÉ, ancien fichier + nouvelle phrase refusé", c3.returncode != 0 and c4.returncode != 0 and "Sauvegarde valide" not in c3.stdout + c4.stdout, (c3.stdout, c4.stdout))
    a1 = json.loads((dl_dir / "c1.agenda.json").read_text(encoding="utf-8")); a2 = json.loads((dl_dir / "c2.agenda.json").read_text(encoding="utf-8"))
    ok(tag + " … contenu identique dans les deux fichiers", a1["data"]["persons"] == a2["data"]["persons"] and a1["data"]["rides"] == a2["data"]["rides"] and a1["counts"] == a2["counts"])
    ok(tag + " aucune des phrases n'est dans le stockage du navigateur à la fin", leaks(pg, P4) == [] and leaks(pg, P5) == [] and leaks(pg, P6) == [])
    ok(tag + " aucune erreur de page pendant tout le parcours", errs == [], errs)
    b.close()
srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(dl_dir, ignore_errors=True)
print("TOTAL", total, "ECHECS", fails)
raise SystemExit(1 if fails else 0)
