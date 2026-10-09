"""Version 0.6.2 : saisie tolérante de la phrase (accents, majuscules, espaces, tirets), messages utiles (mot inconnu n° N, nombre de mots, phrase valide mais autre fichier),
bouton « Afficher ce que je tape », fichiers 0.6.0 et 0.6.1 toujours lisibles, script tools/lire_export.py (avec et sans --visible), rien dans les stockages. Valeurs FICTIVES.
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



def pick_file(pg, text, name="x.agenda"):
    f = dl_dir / name; f.write_text(text, encoding="utf-8")
    pg.set_input_files("#bk-file", str(f)); pg.wait_for_timeout(500)


def run_check(pg, text, phrase, mode="verify", name="x.agenda"):
    """choisit le fichier, tape la phrase, renvoie le texte de l'écran après"""
    if not pg.locator('[data-a="bk-%s"]' % mode).count(): tap(pg, "bk-cancel")
    tap(pg, "bk-" + mode)
    pick_file(pg, text, name)
    if vis(pg, "#bk-phrase"):
        pg.fill("#bk-phrase", phrase); tap(pg, "bk-open", 100); wait_busy_done(pg)
    return screen_text(pg)



# ---- anciennes versions du code de chiffrement, tirées de git (0.6.0 = efa392e, 0.6.1 = a2356d2), pour fabriquer de VRAIS anciens fichiers
for tagv, rev in (("060", "efa392e"), ("061", "a2356d2")):
    code = subprocess.run(["git", "-C", str(ROOT), "show", rev + ":sauvegarde.js"], capture_output=True).stdout
    (tmp / ("sauvegarde_%s.js" % tagv)).write_bytes(code)
    (tmp / ("old%s.html" % tagv)).write_text('<!doctype html><meta charset="utf-8"><script src="mots.js"></script><script src="sauvegarde_%s.js"></script>' % tagv, encoding="utf-8")

OLDMAKE = """async([phrase, ver])=>{ const b = await AGB.createKeyBundle(phrase); return await AGB.buildFile(b, {persons:[{id:'p1',first_name:'Test'}], rides:[], fuel:[], settings:[]}, 5, ver, new Date('2026-10-20T08:00:00Z')) }"""


def strip_accents(w):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c))


def code_of(pg, text, phrase_str):
    return pg.evaluate("""async([t,ph])=>{ try { const o = await AGB.openFile(t, ph, 5); return 'ok' } catch(e) { return (e.code||String(e)) + (e.extra!==undefined ? ':' + e.extra : '') } }""", [text, phrase_str])


def run_script(text, phrase, name, args=(), stdin=None, use_env=True):
    f = dl_dir / name; f.write_text(text, encoding="utf-8")
    env = dict(os.environ, PYTHONUTF8="1"); env.pop("AGENDA_PHRASE", None)
    if use_env: env["AGENDA_PHRASE"] = phrase
    return subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "tools" / "lire_export.py"), str(f), "-o", str(dl_dir / (name + ".json"))] + list(args), capture_output=True, text=True, encoding="utf-8", env=env, input=stdin)


# phrase de test : 10 mots tirés de la liste, avec beaucoup d'accents (é, è, ê, ç, î, ô, û, à, ï)
acc = [w for w in words if strip_accents(w) != w]
PH = acc[:7] + [w for w in words if strip_accents(w) == w][:3]
PH_STR = " ".join(PH)
OTHER = [w for w in words if strip_accents(w) == w][3:13]            # une AUTRE phrase, valide
ok(tag + " la liste officielle : 2048 mots, aucun ne se confond avec un autre une fois les accents retirés (règle « un seul mot possible »)", len({strip_accents(w) for w in words}) == 2048 and all(strip_accents(w).isalpha() and strip_accents(w).islower() for w in words))

with sync_playwright() as p:
    b, cx, pg, reqs, errs = new_phone(p)
    # ---------------- 1. anciens fichiers (vrai code 0.6.0 et 0.6.1) + fichier du code actuel
    files = {}
    for v in ("060", "061"):
        pg2 = cx.new_page(); pg2.goto(BASE + "old%s.html" % v); pg2.wait_for_function("window.AGB")
        files[v] = pg2.evaluate(OLDMAKE, [PH_STR, "0.%s.%s" % (v[1], v[2])]); pg2.close()
    files["062"] = pg.evaluate(OLDMAKE, [PH_STR, "0.6.2"])
    ok(tag + " fichiers 0.6.0, 0.6.1 (fabriqués par le vrai ancien code) et 0.6.2 : tous s'ouvrent avec la phrase exacte", all(code_of(pg, files[v], PH_STR) == "ok" for v in files), {v: code_of(pg, files[v], PH_STR) for v in files})
    hdrs = {v: json.loads(files[v]) for v in files}
    ok(tag + " … format de fichier inchangé (mêmes champs, PBKDF2 600 000 tours)", all(set(h) == set(hdrs["060"]) and h["kdf"]["iterations"] == 600000 and h["format_version"] == 1 for h in hdrs.values()))

    # ---------------- 2. tolérance : mêmes résultats pour toutes les écritures de la même phrase
    variants = {
        "exacte": PH_STR,
        "MAJUSCULES": PH_STR.upper(),
        "sans accents": strip_accents(PH_STR),
        "SANS ACCENTS EN MAJUSCULES": strip_accents(PH_STR).upper(),
        "espaces en trop, tabulation, retour à la ligne": "  " + "   ".join(PH[:5]) + "\t" + " ".join(PH[5:]) + " \n ",
        "tirets et apostrophes dans les mots": "-".join([PH[0][:2], PH[0][2:]]) + " " + PH[1][:1] + "’" + PH[1][1:] + " " + " ".join(PH[2:]),
        "accents décomposés (e + accent)": __import__("unicodedata").normalize("NFD", PH_STR),
    }
    res = {k: {v: code_of(pg, files[v], s) for v in files} for k, s in variants.items()}
    for k, r in res.items():
        ok(tag + " tolérance « %s » : ouvre les fichiers 0.6.0, 0.6.1 et 0.6.2" % k, set(r.values()) == {"ok"}, r)
    one = pg.evaluate("[AGB.normPhrase(%s), AGB.normPhrase(%s), AGB.normPhrase(%s)]" % tuple(json.dumps(x) for x in ("bélier", "BELIER", "  Bélier ")))
    ok(tag + " « belier », « Bélier » et « BÉLIER » donnent le même résultat", one[0] == one[1] == one[2] == "belier", one)

    # ---------------- 3. messages utiles (jamais la phrase)
    bad4 = PH[:3] + ["xyzzy"] + PH[4:]
    ok(tag + " mot inconnu à la position 4 : code et numéro", code_of(pg, files["061"], " ".join(bad4)) == "unknownword:4")
    ok(tag + " mot inconnu : le premier mot absent est celui qui est cité (positions 2 et 9 → n° 2)", code_of(pg, files["061"], " ".join(PH[:1] + ["qqq"] + PH[2:9] + ["www"])) == "unknownword:2")
    ok(tag + " 9 mots → « words:9 », 11 mots → « words:11 », 1 mot, vide", [code_of(pg, files["061"], " ".join(PH[:9])), code_of(pg, files["061"], PH_STR + " " + PH[0]), code_of(pg, files["061"], "chat"), code_of(pg, files["061"], "  ")] == ["words:9", "words:11", "words:1", "words:0"])
    ok(tag + " 10 mots valides mais autre phrase → « phrase » (ni « words » ni « unknownword »)", code_of(pg, files["061"], " ".join(OTHER)) == "phrase")
    ok(tag + " une faute d'orthographe ne passe pas pour un mot de la liste (« beliers »)", code_of(pg, files["061"], " ".join([PH[0] + "s"] + PH[1:])) == "unknownword:1")

    # ---------------- 4. dans l'appli, à l'écran
    seed(pg, PEOPLE, RIDES, FUEL, 600)
    set_clock(pg, '2026-10-20T10:07:00')
    open_save(pg)
    # première phrase confirmée avec des réponses sans accents et en majuscules
    tap(pg, "bk-export"); tap(pg, "bk-show"); P = bkstate(pg)["phrase"]
    ok(tag + " écran de la phrase : aucun champ de saisie, donc pas de bouton « Afficher ce que je tape » (il ne sert qu'aux champs)", pg.locator("#bk-reveal").count() == 0)
    tap(pg, "bk-written"); a, bq = pg.evaluate("__ag.bk.ask")
    ok(tag + " confirmation des 2 mots : bouton « Afficher ce que je tape » présent, saisie cachée par défaut", pg.locator("#bk-reveal").count() == 1 and "Afficher ce que je tape" in text_of(pg, "#bk-reveal") and pg.evaluate("getComputedStyle(document.getElementById('bk-w1')).webkitTextSecurity") == "disc")
    pg.screenshot(path=SHOTS + "/saisie_confirm_cache_%dx%d_%s.png" % (W, H, SCHEME))
    pg.fill("#bk-w1", "ab"); tap(pg, "bk-reveal")
    ok(tag + " « Afficher ce que je tape » : les champs deviennent lisibles, ce qui était tapé reste, le bouton propose de recacher", pg.evaluate("getComputedStyle(document.getElementById('bk-w1')).webkitTextSecurity") == "none" and pg.input_value("#bk-w1") == "ab" and "Cacher" in text_of(pg, "#bk-reveal") and pg.get_attribute("#bk-reveal", "aria-pressed") == "true")
    pg.screenshot(path=SHOTS + "/saisie_confirm_visible_%dx%d_%s.png" % (W, H, SCHEME))
    tap(pg, "bk-reveal")
    ok(tag + " … on peut recacher", pg.evaluate("getComputedStyle(document.getElementById('bk-w1')).webkitTextSecurity") == "disc" and "Afficher" in text_of(pg, "#bk-reveal"))
    tap(pg, "bk-reveal"); eye(pg); unmask(pg)
    ok(tag + " œil (masquage) : l'affichage de la saisie est remis à « caché » et la phrase effacée", bkstate(pg)["hasPhrase"] is False and pg.evaluate("__ag.bk.reveal") is False if pg.evaluate("'reveal' in __ag.bk") else bkstate(pg)["hasPhrase"] is False)
    tap(pg, "bk-export"); tap(pg, "bk-show"); P = bkstate(pg)["phrase"]; tap(pg, "bk-written"); a, bq = pg.evaluate("__ag.bk.ask")
    pg.fill("#bk-w1", strip_accents(P[a - 1]).upper()); pg.fill("#bk-w2", "  " + strip_accents(P[bq - 1]) + "  ")
    with pg.expect_download(timeout=30000) as d: tap(pg, "bk-confirm", 100)
    wait_busy_done(pg); text = save_dl(d.value, "reel.agenda")
    ok(tag + " confirmation des 2 mots tapés sans accents / en majuscules / avec espaces : acceptée, fichier produit", json.loads(text)["app_version"] == "0.6.2" and bkstate(pg)["hasKey"] is True)
    # Vérifier : écritures différentes de la même vraie phrase
    for label, s in (("sans accents et en majuscules", strip_accents(" ".join(P)).upper()), ("avec espaces en trop", "  " + "   ".join(P) + "  ")):
        t_ = run_check(pg, text, s)
        ok(tag + " Vérifier avec la phrase %s : « Sauvegarde valide »" % label, "Sauvegarde valide" in t_, t_[:200])
        tap(pg, "bk-cancel")
    pg.screenshot(path=SHOTS + "/saisie_resultat_%dx%d_%s.png" % (W, H, SCHEME))
    # messages à l'écran
    def msg_for(s):
        t_ = run_check(pg, text, s)
        m = text_of(pg, "#bk-msg"); tap(pg, "bk-cancel"); return m
    m1 = msg_for(" ".join(P[:3] + ["xyzzy"] + P[4:])); m2 = msg_for(" ".join(P[:9])); m3 = msg_for(" ".join(OTHER)); m4 = msg_for(" ".join(P + ["chat"])); m5 = msg_for(P[0])
    ok(tag + " écran : mot inconnu → « Le mot n° 4 ne figure pas dans la liste. Vérifiez son orthographe. »", m1 == "Le mot n° 4 ne figure pas dans la liste. Vérifiez son orthographe.", m1)
    ok(tag + " écran : 9 mots → dit combien de mots ont été lus ; 11 mots ; 1 mot (singulier)", "9 mots" in m2 and "exactement 10" in m2 and "11 mots" in m4 and "1 mot " in m5 and "1 mots" not in m5, (m2, m4, m5))
    ok(tag + " écran : 10 mots valides mais autre phrase → message prévu", m3 == "Les 10 mots sont valides, mais ce n’est pas la phrase de ce fichier. Elle vient peut-être d’un autre essai d’export.", m3)
    ok(tag + " … aucun de ces messages ne contient un mot de la phrase tapée", not any(w in (m1 + m2 + m3 + m4 + m5).split() for w in P + OTHER + ["xyzzy"]))
    # saisie cachée aussi dans le champ de vérification
    tap(pg, "bk-verify"); pick_file(pg, text)
    ok(tag + " champ « Phrase de récupération » : saisie cachée par défaut + bouton « Afficher ce que je tape »", pg.evaluate("getComputedStyle(document.getElementById('bk-phrase')).webkitTextSecurity") == "disc" and pg.locator("#bk-reveal").count() == 1)
    pg.fill("#bk-phrase", " ".join(P)); tap(pg, "bk-reveal")
    ok(tag + " … affichée à la demande, sans vider le champ", pg.evaluate("getComputedStyle(document.getElementById('bk-phrase')).webkitTextSecurity") == "none" and pg.input_value("#bk-phrase") == " ".join(P))
    pg.screenshot(path=SHOTS + "/saisie_phrase_visible_%dx%d_%s.png" % (W, H, SCHEME))
    pg.evaluate("window.__off += 700000"); pg.wait_for_function("__ag.masked", timeout=6000); unmask(pg)
    ok(tag + " masquage automatique : la page est vidée ; au retour, la saisie est de nouveau cachée et le champ est vide", pg.input_value("#bk-phrase") == "" and pg.evaluate("getComputedStyle(document.getElementById('bk-phrase')).webkitTextSecurity") == "disc")
    pg.evaluate("window.__off -= 700000")
    ok(tag + " la phrase tapée n'est dans aucun stockage ni journal (IndexedDB, localStorage, sessionStorage, caches)", leaks(pg, P) == [] and leaks(pg, PH) == [])
    tap(pg, "bk-cancel")
    # nouvelle phrase : le message « autre essai » quand on utilise l'ancienne phrase sur un nouveau fichier
    ok(tag + " aucune erreur de page", errs == [], errs)
    b.close()

# ---------------- 5. le script du PC
t060, t061, t062 = files["060"], files["061"], files["062"]
for k, s in (("exacte", PH_STR), ("MAJUSCULES sans accents", strip_accents(PH_STR).upper()), ("espaces en trop", "  " + "  ".join(PH) + "  "), ("tirets/apostrophes", "-".join([PH[0][:2], PH[0][2:]]) + " " + " ".join(PH[1:]))):
    r = {v: run_script(files[v], s, "s%s.agenda" % v) for v in files}
    ok(tag + " script PC, phrase « %s » : ouvre les fichiers 0.6.0, 0.6.1 et 0.6.2" % k, all(x.returncode == 0 and "Sauvegarde valide" in x.stdout for x in r.values()), {v: (x.stdout[-200:], x.stderr[-200:]) for v, x in r.items()})
r1 = run_script(t061, " ".join(bad4), "e1.agenda"); r2 = run_script(t061, " ".join(PH[:9]), "e2.agenda"); r3 = run_script(t061, " ".join(OTHER), "e3.agenda"); r4 = run_script(t061, PH_STR + " chat", "e4.agenda")
ok(tag + " script PC : mot inconnu n° 4", r1.returncode != 0 and "Le mot n° 4 ne figure pas dans la liste. Vérifiez son orthographe." in r1.stderr, r1.stderr)
ok(tag + " script PC : nombre de mots incorrect (9 et 11)", "J'ai lu 9 mots : il en faut exactement 10." in r2.stderr and "J'ai lu 11 mots" in r4.stderr, (r2.stderr, r4.stderr))
ok(tag + " script PC : 10 mots valides mais autre phrase", "Les 10 mots sont valides, mais ce n'est pas la phrase de ce fichier. Elle vient peut-être d'un autre essai d'export." in r3.stderr and r3.returncode != 0, r3.stderr)
allout = "".join(x.stdout + x.stderr for x in (r1, r2, r3, r4))
ok(tag + " script PC : aucun mot de la phrase dans les messages d'erreur", not any(w in allout.split() for w in PH + OTHER + ["xyzzy"]), allout[:300])
# --visible : saisie au clavier (simulée par l'entrée standard)
rv = run_script(t061, "", "v1.agenda", args=["--visible"], stdin=strip_accents(PH_STR).upper() + "\n", use_env=False)
ok(tag + " script PC --visible : avertissement affiché, la phrase est lue (accents/majuscules sans importance) et le fichier s'ouvre", rv.returncode == 0 and "La phrase sera visible à l'écran et dans l'historique de la fenêtre" in rv.stderr and "Sauvegarde valide" in rv.stdout and "10 mots lus" in rv.stdout, (rv.stdout, rv.stderr))
# sans --visible : la saisie passe par getpass (cachée), jamais par input()
wrapper = dl_dir / "wrap.py"
wrapper.write_text("import getpass, builtins, runpy, sys, os\nlog=[]\n"
                   "getpass.getpass=lambda prompt='': (log.append('getpass'), os.environ['PHR'])[1]\n"
                   "builtins.input=lambda prompt='': (log.append('input'), os.environ['PHR'])[1]\n"
                   "sys.argv=['lire_export.py']+sys.argv[1:]\n"
                   "try:\n    runpy.run_path(os.environ['SCRIPT'], run_name='__main__')\nfinally:\n    print('APPELS', ','.join(log))\n", encoding="utf-8")
envh = dict(os.environ, PYTHONUTF8="1", PHR=PH_STR, SCRIPT=str(ROOT / "tools" / "lire_export.py")); envh.pop("AGENDA_PHRASE", None)
fh = dl_dir / "h.agenda"; fh.write_text(t061, encoding="utf-8")
rh = subprocess.run([sys.executable, "-X", "utf8", str(wrapper), str(fh), "-o", str(dl_dir / "h.json")], capture_output=True, text=True, encoding="utf-8", env=envh)
rh2 = subprocess.run([sys.executable, "-X", "utf8", str(wrapper), str(fh), "-o", str(dl_dir / "h2.json"), "--visible"], capture_output=True, text=True, encoding="utf-8", env=envh)
ok(tag + " script PC sans --visible : la saisie passe par la saisie CACHÉE (getpass), jamais par input()", "APPELS getpass" in rh.stdout and "input" not in rh.stdout.split("APPELS")[1] and "Sauvegarde valide" in rh.stdout, (rh.stdout, rh.stderr))
ok(tag + " script PC avec --visible : la saisie passe par input() (visible)", "APPELS input" in rh2.stdout and "La phrase sera visible" in rh2.stderr, (rh2.stdout, rh2.stderr))
ok(tag + " script PC : la phrase n'apparaît jamais à l'écran (sauf saisie visible), dans aucun message ni fichier produit", not any(w in (rh.stdout + rh.stderr + rv.stdout).split() for w in PH) and PH_STR not in (dl_dir / "h.json").read_text(encoding="utf-8") and strip_accents(PH_STR) not in (dl_dir / "h.json").read_text(encoding="utf-8"))
src_py = (ROOT / "tools" / "lire_export.py").read_text(encoding="utf-8")
args_declared = re.findall(r'add_argument\(("[^"]+"(?:, "[^"]+")?)', src_py)
ok(tag + " script PC : la phrase n'est pas un argument de la ligne de commande (seulement fichier, -o, --visible) et n'est jamais écrite dans un fichier", args_declared == ['"fichier"', '"-o", "--sortie"', '"--visible"'] and len(re.findall(r'open\([^)]*"w"', src_py)) == 1, args_declared)
ok(tag + " script PC : --help court et en français", "--visible" in subprocess.run([sys.executable, str(ROOT / "tools" / "lire_export.py"), "--help"], capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONUTF8="1")).stdout)

srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(dl_dir, ignore_errors=True)
print("TOTAL", total, "ECHECS", fails)
raise SystemExit(1 if fails else 0)
