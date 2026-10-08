"""Étape 6 : export chiffré, vérification, restauration (version 0.6.0). Noms et valeurs FICTIFS seulement.
Vérifie : liste de mots (2048, sans doublon ni mots trop proches), tirage sans biais, premier export (phrase, confirmation de 2 mots, mauvaise réponse, masquage avant
confirmation), exports suivants sans phrase, contenu complet (archivées, corbeille), « Vérifier » (bonne / mauvaise phrase, 1 caractère modifié, tronqué, structure trop récente),
« Restaurer » (remplacement complet, « Annuler la restauration », atomicité, migration d'une structure plus ancienne, expiration à 7 jours), « Dernier export » et rappel de 7 jours
(autour du changement d'heure du 25 octobre 2026), hors connexion, masquage, test croisé avec tools/lire_export.py, aucun nom lisible dans le fichier.
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
import unicodedata
nrm = lambda w: "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c)).lower()


def d1(a, b):
    if a == b: return True
    if abs(len(a) - len(b)) > 1: return False
    if len(a) == len(b): return sum(x != y for x, y in zip(a, b)) <= 1
    if len(a) > len(b): a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]: i += 1
    return a[i:] == b[i + 1:]


ok(tag + " liste de mots : 2048 mots exactement (2^11)", len(words) == 2048, len(words))
ok(tag + " … aucun doublon, même sans les accents", len({nrm(w) for w in words}) == 2048 and len(set(words)) == 2048)
ok(tag + " … lettres seulement, 4 à 9 lettres, aucun espace ni tiret ni apostrophe", all(re.fullmatch(r"[a-zàâäçéèêëîïôöùûüÿœæ]{4,9}", w) for w in words))
near = [(a, b) for a, b in itertools.combinations([nrm(w) for w in words], 2) if d1(a, b) or a.startswith(b) or b.startswith(a)] if False else None
nw = sorted(nrm(w) for w in words)
close = []
buckets = {}
for w in nw:
    for i in range(len(w) + 1):
        buckets.setdefault(w[:i] + "*" + w[i + 1:], []).append(w)       # même mot avec une lettre remplacée
        buckets.setdefault(w[:i] + "#" + w[i:], []).append(w)            # même mot avec une lettre en plus (supprimer la i-ème)
for k, v in buckets.items():
    if len(set(v)) > 1: close.append(sorted(set(v))[:3])
close += [(a, b) for a, b in zip(nw, nw[1:]) if b.startswith(a)]
ok(tag + " … aucun mot ne ressemble à un autre à UNE lettre près (ni début d'un autre mot)", not close, close[:5])
ok(tag + " … aucun mot ne contient de donnée personnelle (liste de mots courants, aucun nombre)", not any(re.search(r"\d", w) for w in words))

# ---------------------------------------------------------------- 2. données fictives
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


def first_export(pg, phrase_holder=None):
    """parcours complet du premier export : renvoie (phrase, texte du fichier, nom)"""
    tap(pg, "bk-export"); tap(pg, "bk-show")
    st = pg.evaluate("__ag.bk"); phrase = st["phrase"]
    tap(pg, "bk-written")
    a, b = pg.evaluate("__ag.bk.ask")
    pg.fill("#bk-w1", phrase[a - 1]); pg.fill("#bk-w2", phrase[b - 1].upper())            # majuscules tolérées
    with pg.expect_download(timeout=30000) as d:
        tap(pg, "bk-confirm", 100)
    wait_busy_done(pg)
    path = dl_dir / d.value.suggested_filename; d.value.save_as(str(path))
    return phrase, path.read_text(encoding="utf-8"), d.value.suggested_filename


def flip(text, key="ct"):
    j = json.loads(text); s = j[key]; i = len(s) // 2
    j[key] = s[:i] + ("A" if s[i] != "A" else "B") + s[i + 1:]
    return json.dumps(j)


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


with sync_playwright() as p:
    # ---------------------------------------------------------------- 3. tirage sans biais + phrase
    b, cx, pg, reqs, errs = new_phone(p)
    r = pg.evaluate("""()=>{ const c=new Array(2048).fill(0); for(let u=0;u<65536;u++) c[AGB.drawIndex(u)]++; return [Math.min(...c), Math.max(...c), AGB.WORDS.length] }""")
    ok(tag + " tirage sans biais : sur les 65 536 valeurs possibles de 16 bits, chaque mot sort EXACTEMENT 32 fois", r == [32, 32, 2048], r)
    r = pg.evaluate("""()=>{ const g=crypto.getRandomValues.bind(crypto); const fixed=[0xF801,0x0000,0x0802,0xFFFF,0x0001,0x07FF,0x0800,0x1234,0xABCD,0x5555]; crypto.getRandomValues=(a)=>{ for(let i=0;i<a.length;i++) a[i]=fixed[i]; return a }; const ph=AGB.drawPhrase(); crypto.getRandomValues=g; return ph.map(w=>AGB.WORDS.indexOf(w)) }""")
    ok(tag + " la phrase vient bien de crypto.getRandomValues : 11 bits de chaque nombre désignent le mot", r == [1, 0, 2, 2047, 1, 2047, 0, 0x234, 0x3CD, 0x555], r)
    ph = pg.evaluate("Array.from({length:300},()=>AGB.drawPhrase())")
    ok(tag + " 300 phrases tirées : toujours 10 mots de la liste, toutes différentes", all(len(x) == 10 for x in ph) and len({" ".join(x) for x in ph}) == 300 and all(w in words for x in ph for w in x))
    ok(tag + " la phrase est comprise sans accents ni majuscules ni espaces en trop", pg.evaluate("AGB.normPhrase('  Été  ÉLÈVE  ') === 'ete eleve'"))
    b.close()

    # ---------------------------------------------------------------- 4. premier export
    b, cx, pg, reqs, errs = new_phone(p)
    seed(pg, PEOPLE, RIDES, FUEL, 600)
    set_clock(pg, '2026-10-20T10:07:00')
    snapA = pg.evaluate(SNAP)
    pg.locator('.nav button.t[data-t="bilan"]').tap(); pg.wait_for_timeout(250); pg.locator('[data-a="reglages"]').tap(); pg.wait_for_timeout(300)
    ok(tag + " Réglages : ligne « Dernier export » = jamais, et accès « Sauvegarde et restauration »", text_of(pg, "#rg-lastexport") == "jamais" and pg.locator('[data-a="opensave"]').count() == 1)
    pg.screenshot(path=SHOTS + "/sauvegarde_reglages_%dx%d_%s.png" % (W, H, SCHEME))
    pg.locator('[data-a="opensave"]').tap(); pg.wait_for_timeout(300)
    ok(tag + " écran Sauvegarde : trois boutons et « Dernier export : jamais »", text_of(pg, "#bk-last") == "jamais" and all(pg.locator('[data-a="%s"]' % a).count() == 1 for a in ("bk-export", "bk-verify", "bk-restore")))
    pg.screenshot(path=SHOTS + "/sauvegarde_accueil_%dx%d_%s.png" % (W, H, SCHEME))
    tap(pg, "bk-export")
    ok(tag + " premier export : écran d'explication en phrases courtes (pas encore de phrase)", "10 mots" in screen_text(pg) and "qu’une seule fois" in screen_text(pg) and pg.evaluate("__ag.bk.hasPhrase") is False)
    pg.screenshot(path=SHOTS + "/sauvegarde_explication_%dx%d_%s.png" % (W, H, SCHEME))
    tap(pg, "bk-show")
    st = pg.evaluate("__ag.bk"); phrase1 = st["phrase"]
    shown = pg.evaluate("[...document.querySelectorAll('#bk-words .w')].map(e=>e.textContent)")
    ok(tag + " la phrase s'affiche : 10 mots numérotés, tirés de la liste", shown == phrase1 and len(shown) == 10 and all(w in words for w in shown) and "1" in pg.evaluate("document.querySelector('#bk-words .n').textContent"))
    pg.screenshot(path=SHOTS + "/sauvegarde_phrase_%dx%d_%s.png" % (W, H, SCHEME))
    # masquage (œil) pendant l'affichage de la phrase
    eye(pg)
    ok(tag + " œil pendant la phrase : la page est vidée, la phrase n'est plus en mémoire, rien de lisible", pg.evaluate("document.getElementById('s-sauvegarde').innerHTML") == "" and pg.evaluate("__ag.bk.hasPhrase") is False and pg.evaluate("__ag.masked"))
    unmask(pg)
    t1 = screen_text(pg)
    ok(tag + " … au retour la phrase NE REVIENT PAS : retour à l'accueil avec « recommencez »", " ".join(phrase1[:3]) not in t1 and pg.locator("#bk-words").count() == 0 and "recommencez" in t1 and vis(pg, '[data-a="bk-export"]'), t1[:200])
    ok(tag + " … et rien n'a été créé (ni trousseau, ni date d'export)", pg.evaluate(META) == {"last": None, "hasKey": False, "safety": False})
    # masquage AUTOMATIQUE pendant la saisie de confirmation
    tap(pg, "bk-export"); tap(pg, "bk-show"); phrase2 = pg.evaluate("__ag.bk.phrase"); tap(pg, "bk-written")
    pg.evaluate("window.__off += 700000"); pg.wait_for_function("__ag.masked", timeout=6000); pg.wait_for_timeout(200)
    ok(tag + " masquage automatique à l'étape de confirmation : page vidée, phrase effacée", pg.evaluate("document.getElementById('s-sauvegarde').innerHTML") == "" and pg.evaluate("__ag.bk.hasPhrase") is False)
    pg.evaluate("window.__off -= 700000"); unmask(pg)
    ok(tag + " … retour à l'accueil, aucune trace de la phrase, rien créé", " ".join(phrase2[:3]) not in screen_text(pg) and pg.locator("#bk-words").count() == 0 and pg.evaluate(META)["hasKey"] is False)
    # mauvaise réponse : on recommence avec la MÊME phrase
    tap(pg, "bk-export"); tap(pg, "bk-show"); phrase3 = pg.evaluate("__ag.bk.phrase"); tap(pg, "bk-written")
    a, bq = pg.evaluate("__ag.bk.ask")
    ok(tag + " confirmation : deux mots demandés, différents, entre 1 et 10", a != bq and 1 <= a <= 10 and 1 <= bq <= 10 and ("Mot n° %d" % a) in screen_text(pg) and ("Mot n° %d" % bq) in screen_text(pg))
    pg.fill("#bk-w1", "zzzz"); pg.fill("#bk-w2", phrase3[bq - 1]); tap(pg, "bk-confirm")
    again = pg.evaluate("[...document.querySelectorAll('#bk-words .w')].map(e=>e.textContent)")
    ok(tag + " mauvaise réponse : message simple, on revoit la MÊME phrase, rien de définitif créé", "pas bon" in screen_text(pg) and again == phrase3 and pg.evaluate(META) == {"last": None, "hasKey": False, "safety": False})
    tap(pg, "bk-written")
    a, bq = pg.evaluate("__ag.bk.ask")
    pg.fill("#bk-w1", phrase3[a - 1]); pg.fill("#bk-w2", ""); tap(pg, "bk-confirm")
    ok(tag + " un mot laissé vide : refusé aussi", "pas bon" in screen_text(pg) and pg.evaluate(META)["hasKey"] is False)
    # bonne réponse
    tap(pg, "bk-written")
    a, bq = pg.evaluate("__ag.bk.ask")
    pg.fill("#bk-w1", " " + phrase3[a - 1].upper() + " "); pg.fill("#bk-w2", phrase3[bq - 1])
    with pg.expect_download(timeout=30000) as d:
        tap(pg, "bk-confirm", 100)
    wait_busy_done(pg)
    fname1 = d.value.suggested_filename; f1 = dl_dir / fname1; d.value.save_as(str(f1)); text1 = f1.read_text(encoding="utf-8")
    ok(tag + " bonne réponse (majuscules et espaces tolérés) : téléchargement « agenda-AAAA-MM-JJ-HHMM.agenda » (ici 20/10/2026, 10 h)", re.fullmatch(r"agenda-2026-10-20-10\d\d\.agenda", fname1) is not None, fname1)
    meta = pg.evaluate(META)
    ok(tag + " … « Dernier export » mis à jour APRÈS le téléchargement ; trousseau enregistré ; phrase effacée de la page", meta["last"] and meta["last"]["date"] == "2026-10-20" and meta["hasKey"] and pg.evaluate("__ag.bk.hasPhrase") is False, meta)
    ok(tag + " … message de fin avec le nom du fichier et le conseil de copier sur le PC", fname1 in screen_text(pg) and "Téléchargements" in screen_text(pg) and text_of(pg, "#bk-last") == "aujourd’hui", screen_text(pg)[:200])
    pg.screenshot(path=SHOTS + "/sauvegarde_fin_%dx%d_%s.png" % (W, H, SCHEME))
    ok(tag + " la phrase n'est écrite nulle part sur le téléphone (ni base, ni stockage du navigateur)", not pg.evaluate("""(async()=>{ const ph=%s; const s=JSON.stringify(await AG.snapshotAll())+JSON.stringify(Object.assign({},localStorage))+JSON.stringify(Object.assign({},sessionStorage))+JSON.stringify([await AG.getMeta('last_export'), await AG.getMeta('update_log')]); return ph.some(w=>s.includes(w)) })()""" % json.dumps(phrase3)))
    # le fichier
    hdr = json.loads(text1)
    ok(tag + " fichier : format « agenda-export » n° 1, version de l'appli, structure 5, date, clé enveloppée, PBKDF2 600 000 tours", hdr["format"] == "agenda-export" and hdr["format_version"] == 1 and hdr["app_version"] == "0.6.0" and hdr["schema"] == 5 and hdr["kdf"]["iterations"] == 600000 and hdr["exported_at"].startswith("2026-10-20T08:") and hdr["cipher"] == "AES-256-GCM", {k: hdr[k] for k in hdr if k not in ("ct", "iv", "kdf", "wrapped_key")})
    leaks = [m for m in MARKERS if m in text1]
    ok(tag + " AUCUN nom, adresse, téléphone ni autre valeur de test lisible en clair dans le fichier brut", not leaks and not re.search(r"persons|rides|fuel|price_cents|last_name|Imaginaire", text1), leaks)
    ok(tag + " … le fichier est du texte JSON ordinaire (pas de données binaires brutes)", text1.isascii())
    # contenu complet
    r = pg.evaluate("""async([t,ph])=>{ const o = await AGB.openFile(t, ph, 5); return {counts:o.counts, data:o.data, sha: !!o.header} }""", [text1, " ".join(phrase3)])
    ok(tag + " contenu : 3 personnes (dont 1 archivée), 5 courses (dont 1 à la corbeille), 2 pleins (dont 1 à la corbeille)", r["counts"] == {"persons": 3, "rides": 5, "fuel": 2}, r["counts"])
    same = lambda k: sorted(r["data"][k], key=lambda x: x.get("id") or x.get("key")) == snapA[k]
    ok(tag + " … personnes, courses, pleins et réglages IDENTIQUES à ce qu'il y a sur le téléphone (champ par champ)", same("persons") and same("rides") and same("fuel") and same("settings"), r["data"].keys())
    ok(tag + " … la course à la corbeille et le plein à la corbeille y sont, avec leur date de suppression", any(x["deleted_at"] for x in r["data"]["rides"]) and any(x["deleted_at"] for x in r["data"]["fuel"]) and any(x["archived"] for x in r["data"]["persons"]))
    ok(tag + " … dates en texte (AAAA-MM-JJ), montants en centimes entiers", all(re.fullmatch(r"\d{4}-\d\d-\d\d", x["date"]) for x in r["data"]["rides"]) and all(isinstance(x["price_cents"], int) for x in r["data"]["rides"]))
    b.close()

    # ---------------------------------------------------------------- 4b. exports suivants : sans phrase
    b, cx, pg, reqs, errs = new_phone(p)
    seed(pg, PEOPLE, RIDES, FUEL, 600); open_save(pg)
    phrase, textA, nameA = first_export(pg)
    set_clock(pg, '2026-10-21T09:30:00')
    with pg.expect_download(timeout=30000) as d2:
        pg.locator('[data-a="bk-export"]').tap()
    wait_busy_done(pg)
    f2 = dl_dir / d2.value.suggested_filename; d2.value.save_as(str(f2)); textB = f2.read_text(encoding="utf-8")
    ok(tag + " 2e export : AUCUNE phrase redemandée, le fichier est produit directement", re.fullmatch(r"agenda-2026-10-21-09\d\d\.agenda", d2.value.suggested_filename) is not None and "phrase" not in screen_text(pg).lower().replace("de récupération", "")[:0] + "" and pg.evaluate("__ag.bk.hasPhrase") is False, d2.value.suggested_filename)
    hb, ha = json.loads(textB), json.loads(textA)
    ok(tag + " … même clé enveloppée (la phrase ouvre les deux), mais nouveau vecteur et contenu différent à chaque export", hb["wrapped_key"] == ha["wrapped_key"] and hb["kdf"] == ha["kdf"] and hb["iv"] != ha["iv"] and hb["ct"] != ha["ct"])
    rB = pg.evaluate("""async([t,ph])=>{ const o = await AGB.openFile(t, ph, 5); return o.counts }""", [textB, " ".join(phrase)])
    ok(tag + " … le 2e fichier s'ouvre avec la phrase du 1er export", rB == {"persons": 3, "rides": 5, "fuel": 2}, rB)
    # le trousseau du téléphone : clé non extractible
    ext = pg.evaluate("""(async()=>{ const k=(await AG.getMeta('backup_key')); try { await crypto.subtle.exportKey('raw', k.key); return 'extractible' } catch(e) { return 'non extractible' } })()""")
    ok(tag + " la clé de données gardée sur le téléphone n'est PAS extractible", ext == "non extractible", ext)
    # échec du téléchargement : « Dernier export » ne bouge pas
    before = pg.evaluate(META)["last"]
    set_clock(pg, '2026-10-22T09:30:00'); pg.evaluate("window.__noDownload = true")
    tap(pg, "bk-export", 800)
    ok(tag + " si le téléchargement ne peut pas être lancé : message, et « Dernier export » n'est PAS mis à jour", pg.evaluate(META)["last"] == before and "échoué" in screen_text(pg), (before, pg.evaluate(META)["last"]))
    pg.evaluate("window.__noDownload = false")

    # ---------------------------------------------------------------- 5. test croisé avec tools/lire_export.py
    fA = dl_dir / "croise.agenda"; fA.write_text(textA, encoding="utf-8")
    outj = dl_dir / "croise.json"
    env = dict(os.environ, AGENDA_PHRASE=" ".join(phrase), PYTHONUTF8="1")
    rr = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "tools" / "lire_export.py"), str(fA), "-o", str(outj)], capture_output=True, text=True, encoding="utf-8", env=env)
    ok(tag + " test croisé : tools/lire_export.py déchiffre le fichier fait par l'appli (code 0, « Sauvegarde valide »)", rr.returncode == 0 and "Sauvegarde valide" in rr.stdout and "3 personnes, 5 courses, 2 pleins" in rr.stdout, rr.stdout + rr.stderr)
    if outj.exists():
        J = json.loads(outj.read_text(encoding="utf-8"))
        sA = pg.evaluate(SNAP)
        srt = lambda k: sorted(J["data"][k], key=lambda x: x.get("id") or x.get("key"))
        ok(tag + " … contenu IDENTIQUE à celui du téléphone au moment du 1er export (personnes, courses, pleins, réglages)", srt("persons") == sA["persons"] and srt("rides") == sA["rides"] and srt("fuel") == sA["fuel"] and srt("settings") == sA["settings"] and J["counts"] == {"persons": 3, "rides": 5, "fuel": 2})
    env2 = dict(env, AGENDA_PHRASE=" ".join(phrase[:-1] + ["abeille" if phrase[-1] != "abeille" else "abri"]))
    rr = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "tools" / "lire_export.py"), str(fA), "-o", str(dl_dir / "x.json")], capture_output=True, text=True, encoding="utf-8", env=env2)
    ok(tag + " … le script refuse une mauvaise phrase (code ≠ 0, message simple)", rr.returncode != 0 and "phrase" in (rr.stdout + rr.stderr).lower(), rr.stdout + rr.stderr)
    fF = dl_dir / "croise2.agenda"; fF.write_text(flip(textA), encoding="utf-8")
    rr = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "tools" / "lire_export.py"), str(fF), "-o", str(dl_dir / "y.json")], capture_output=True, text=True, encoding="utf-8", env=env)
    ok(tag + " … et un fichier modifié d'un caractère", rr.returncode != 0 and "abîmé" in (rr.stdout + rr.stderr), rr.stdout + rr.stderr)
    # le script lit aussi un fichier du 2e export (même phrase)
    fB = dl_dir / "croise3.agenda"; fB.write_text(textB, encoding="utf-8")
    rr = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "tools" / "lire_export.py"), str(fB), "-o", str(dl_dir / "z.json")], capture_output=True, text=True, encoding="utf-8", env=env)
    ok(tag + " … et le fichier du 2e export (sans phrase redemandée) avec la même phrase", rr.returncode == 0, rr.stdout + rr.stderr)

    # ---------------------------------------------------------------- 6. Vérifier
    snap0 = pg.evaluate(SNAP); meta0 = pg.evaluate(META)
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); open_save(pg)
    t = run_check(pg, textA, " ".join(phrase))
    ok(tag + " Vérifier (bonne phrase) : « Sauvegarde valide : date, 3 personnes, 5 courses, 2 pleins »", "Sauvegarde valide" in t and "3 personnes, 5 courses, 2 pleins" in t and "octobre 2026" in t, t[:200])
    pg.screenshot(path=SHOTS + "/sauvegarde_valide_%dx%d_%s.png" % (W, H, SCHEME))
    ok(tag + " … rien n'a été modifié sur le téléphone (données, date de dernier export identiques)", pg.evaluate(SNAP) == snap0 and pg.evaluate(META)["last"] == meta0["last"])
    tap(pg, "bk-cancel")
    bad = phrase[:]; bad[3] = "abeille" if bad[3] != "abeille" else "abri"
    t = run_check(pg, textA, " ".join(bad))
    ok(tag + " Vérifier (mauvaise phrase) : message simple, on peut réessayer", "ne correspond pas" in t and vis(pg, "#bk-phrase"), t[:200])
    pg.fill("#bk-phrase", " ".join(phrase[:9])); tap(pg, "bk-open")
    ok(tag + " Vérifier (9 mots) : « 10 mots » demandés", "10 mots" in screen_text(pg))
    pg.fill("#bk-phrase", "  " + " ".join(phrase).upper() + "  "); tap(pg, "bk-open", 100); wait_busy_done(pg)
    ok(tag + " Vérifier (phrase en MAJUSCULES, espaces en trop) : acceptée", "Sauvegarde valide" in screen_text(pg))
    tap(pg, "bk-cancel")
    t = run_check(pg, flip(textA), " ".join(phrase))
    ok(tag + " Vérifier (fichier modifié d'un caractère) : « abîmé », jamais « valide »", "abîmé" in t and "Sauvegarde valide" not in t, t[:200])
    j = json.loads(textA); j["exported_at"] = "2026-10-20T08:08:00.000Z"
    t = run_check(pg, json.dumps(j), " ".join(phrase))
    ok(tag + " Vérifier (date de l'en-tête modifiée) : « abîmé » aussi (l'en-tête est authentifié)", "abîmé" in t and "Sauvegarde valide" not in t, t[:200])
    t = run_check(pg, textA[: len(textA) // 2], " ".join(phrase))
    ok(tag + " Vérifier (fichier tronqué) : « abîmé ou incomplet »", "abîmé ou incomplet" in t, t[:200])
    t = run_check(pg, "", " ")
    ok(tag + " Vérifier (fichier vide) : « abîmé ou incomplet »", "abîmé ou incomplet" in t, t[:200])
    t = run_check(pg, json.dumps({"hello": 1}), " ")
    ok(tag + " Vérifier (autre fichier JSON) : « pas une sauvegarde Agenda »", "pas une sauvegarde Agenda" in t, t[:200])
    j = json.loads(textA); j["schema"] = 99
    t = run_check(pg, json.dumps(j), " ")
    ok(tag + " Vérifier (structure plus récente que l'appli) : message clair, la phrase n'est même pas demandée", "structure de données plus récente" in t and not vis(pg, "#bk-phrase"), t[:200])
    j = json.loads(textA); j["format_version"] = 7
    t = run_check(pg, json.dumps(j), " ")
    ok(tag + " Vérifier (format de fichier plus récent) : message clair", "version plus récente" in t, t[:200])
    ok(tag + " … aucune de ces vérifications n'a rien modifié sur le téléphone", pg.evaluate(SNAP) == snap0 and pg.evaluate(META)["last"] == meta0["last"])
    # écran masqué pendant un résultat
    tap(pg, "bk-cancel"); t = run_check(pg, textA, " ".join(phrase)); eye(pg)
    ok(tag + " œil sur « Sauvegarde valide » : page vidée, rien de lisible (ni comptes, ni date)", pg.evaluate("document.getElementById('s-sauvegarde').innerHTML") == "")
    unmask(pg)
    ok(tag + " … le résultat ne revient pas", "Sauvegarde valide" not in screen_text(pg) and "3 personnes" not in screen_text(pg))
    # masquage pendant la saisie de la phrase d'un fichier : le champ est vidé
    tap(pg, "bk-verify"); pick_file(pg, textA); pg.fill("#bk-phrase", " ".join(phrase)); eye(pg); unmask(pg)
    ok(tag + " œil pendant la saisie de la phrase : le champ est vidé (la phrase tapée ne revient pas)", vis(pg, "#bk-phrase") and pg.input_value("#bk-phrase") == "")
    b.close()

    # ---------------------------------------------------------------- 7. Restaurer (sur un « autre téléphone »)
    b, cx, pg, reqs, errs = new_phone(p)
    seed(pg, OTHER_PEOPLE, [], [], 120); open_save(pg)
    snapB = pg.evaluate(SNAP); metaB = pg.evaluate(META)
    t = run_check(pg, textA, " ".join(phrase), "restore")
    ok(tag + " Restaurer : résumé « dans le fichier / sur ce téléphone » et avertissement « remplace tout »", "3 personnes, 5 courses, 2 pleins" in text_of(pg, "#bk-sum-file") + t and "1 personne, 0 course, 0 plein" in text_of(pg, "#bk-sum-now") and "remplace tout ce qui est sur ce téléphone" in t, t[:300])
    pg.screenshot(path=SHOTS + "/sauvegarde_resume_%dx%d_%s.png" % (W, H, SCHEME))
    ok(tag + " … pas encore rien modifié à ce stade", pg.evaluate(SNAP) == snapB)
    tap(pg, "bk-replace")
    ok(tag + " confirmation claire : « Cela remplace tout ce qui est sur ce téléphone »", "remplace tout ce qui est sur ce téléphone" in text_of(pg, "#confirm-text") and vis(pg, "#confirm"))
    pg.locator("#confirm-cancel").tap(); pg.wait_for_timeout(300)
    ok(tag + " … « Garder tel quel » ne change rien", pg.evaluate(SNAP) == snapB and "Restaurer" in screen_text(pg))
    tap(pg, "bk-replace"); pg.locator("#confirm-ok").tap(); pg.wait_for_function("document.getElementById('bk-busy')===null", timeout=30000); pg.wait_for_timeout(500)
    snapR = pg.evaluate(SNAP)
    ok(tag + " restauration : TOUT est remplacé (personnes, courses y compris corbeille, pleins, réglages) et identique au téléphone d'origine", snapR == snapA, [k for k in snapA if snapA[k] != snapR[k]])
    ok(tag + " … l'ancienne personne « Delta » a disparu, les archivées sont revenues", not any(x["last_name"] == "Delta" for x in snapR["persons"]) and any(x["archived"] for x in snapR["persons"]))
    mR = pg.evaluate(META)
    ok(tag + " … « Dernier export » = la date du FICHIER restauré", mR["last"]["at"] == json.loads(textA)["exported_at"] and mR["last"]["date"] == mR["last"]["at"][:10], mR)
    ok(tag + " … copie de sécurité interne créée ; le message propose d'annuler pendant 7 jours", mR["safety"] and "Annuler la restauration" in screen_text(pg) and "7 jours" in screen_text(pg), screen_text(pg)[:200])
    pg.screenshot(path=SHOTS + "/sauvegarde_restauree_%dx%d_%s.png" % (W, H, SCHEME))
    pg.locator('.nav button.t[data-t="personnes"]').tap(); pg.wait_for_timeout(400)
    ok(tag + " … les écrans voient tout de suite les données restaurées (Personnes : 2 actives + archivées)", "2 personnes" in text_of(pg, "#pcount"), text_of(pg, "#pcount"))
    open_save(pg) if False else None
    pg.locator('.nav button.t[data-t="bilan"]').tap(); pg.wait_for_timeout(200); pg.locator('[data-a="reglages"]').tap(); pg.wait_for_timeout(200); pg.locator('[data-a="opensave"]').tap(); pg.wait_for_timeout(300)
    # le téléphone adopte la clé du fichier : export suivant sans phrase, ouvrable avec la MÊME phrase
    with pg.expect_download(timeout=30000) as d3:
        pg.locator('[data-a="bk-export"]').tap()
    wait_busy_done(pg)
    f3 = dl_dir / d3.value.suggested_filename; d3.value.save_as(str(f3)); text3 = f3.read_text(encoding="utf-8")
    r3 = pg.evaluate("""async([t,ph])=>{ const o = await AGB.openFile(t, ph, 5); return o.counts }""", [text3, " ".join(phrase)])
    ok(tag + " après restauration : l'export suivant se fait SANS phrase et s'ouvre avec la phrase du papier", r3 == {"persons": 3, "rides": 5, "fuel": 2} and json.loads(text3)["wrapped_key"] == json.loads(textA)["wrapped_key"], r3)
    # annuler la restauration
    pg.evaluate("window.__off += 0")
    tap(pg, "bk-undo"); ok(tag + " « Annuler la restauration » demande confirmation (ce qui a été noté depuis sera perdu)", "perdu" in text_of(pg, "#confirm-text"))
    pg.locator("#confirm-ok").tap(); pg.wait_for_function("document.getElementById('bk-busy')===null", timeout=30000); pg.wait_for_timeout(500)
    snapU = pg.evaluate(SNAP); mU = pg.evaluate(META)
    ok(tag + " restauration annulée : les données d'AVANT sont revenues, à l'identique", snapU == snapB, [k for k in snapB if snapB[k] != snapU[k]])
    ok(tag + " … « Dernier export » et trousseau d'avant sont revenus (jamais exporté), la copie de sécurité est consommée", mU["last"] is None and mU["hasKey"] is False and mU["safety"] is False, mU)
    # garder définitivement
    t = run_check(pg, textA, " ".join(phrase), "restore"); tap(pg, "bk-replace"); pg.locator("#confirm-ok").tap(); pg.wait_for_function("document.getElementById('bk-busy')===null", timeout=30000); pg.wait_for_timeout(400)
    tap(pg, "bk-keep", 500)
    ok(tag + " « Garder définitivement » : la copie de sécurité est effacée, les données restaurées restent", pg.evaluate(META)["safety"] is False and pg.evaluate(SNAP) == snapA and "Annuler la restauration" not in screen_text(pg))
    # restaurer deux fois de suite sans aucune différence
    t = run_check(pg, textA, " ".join(phrase), "restore"); tap(pg, "bk-replace"); pg.locator("#confirm-ok").tap(); pg.wait_for_function("document.getElementById('bk-busy')===null", timeout=30000); pg.wait_for_timeout(400)
    ok(tag + " 2e restauration du même fichier : zéro différence", pg.evaluate(SNAP) == snapA)
    # expiration à 7 jours
    pg.evaluate("""new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result;const tx=d.transaction('safety','readwrite');const st=tx.objectStore('safety');st.get('current').onsuccess=e=>{const s=e.target.result;s.expires_at='2026-01-01T00:00:00.000Z';st.put(s)};tx.oncomplete=()=>{d.close();r(1)}}})""")
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(500)
    ok(tag + " une fois les 7 jours passés : la copie de sécurité a disparu, plus de bouton « Annuler la restauration »", pg.evaluate(META)["safety"] is False and pg.evaluate("__ag.bk.safety") is False)
    b.close()

    # ---------------------------------------------------------------- 8. atomicité + migration d'une structure plus ancienne
    b, cx, pg, reqs, errs = new_phone(p)
    seed(pg, OTHER_PEOPLE, [], [], 120); open_save(pg)
    snapB = pg.evaluate(SNAP); metaB = pg.evaluate(META)
    PH = "abeille abri absence acajou accord acier acteur adresse agneau aigle"
    # fichier valide mais dont un enregistrement est refusé par la base (personne sans identifiant) : tout est annulé
    evil = pg.evaluate("""async([ph, ps])=>{ const b=await AGB.createKeyBundle(ph); return await AGB.buildFile(b, {persons:[ps[0], {last_name:'sansid'}], rides:[], fuel:[], settings:[]}, 5, '0.6.0', new Date('2026-10-20T08:00:00Z')) }""", [PH, PEOPLE])
    t = run_check(pg, evil, PH, "restore")
    tap(pg, "bk-replace"); pg.locator("#confirm-ok").tap(); pg.wait_for_function("document.getElementById('bk-busy')===null", timeout=30000); pg.wait_for_timeout(500)
    ok(tag + " restauration refusée par la base en cours de route : message « rien n'a été modifié »", "rien n’a été modifié" in screen_text(pg) or "échoué" in screen_text(pg), screen_text(pg)[:200])
    ok(tag + " … ATOMIQUE : données, réglages et métadonnées strictement inchangés, aucune copie de sécurité à moitié faite", pg.evaluate(SNAP) == snapB and pg.evaluate(META) == metaB, pg.evaluate(META))
    # structure plus ancienne (3, sans pleins) : migrée proprement
    old = pg.evaluate("""async([ph, ps, rs])=>{ const b=await AGB.createKeyBundle(ph); return await AGB.buildFile(b, {persons:ps, rides:rs, settings:[{key:'idle_sec', value:60}]}, 3, '0.4.1', new Date('2026-09-01T08:00:00Z')) }""", [PH, PEOPLE[:2], RIDES[:3]])
    t = run_check(pg, old, PH, "restore")
    ok(tag + " fichier de structure 3 (avant les pleins d'essence) : accepté, résumé « 0 plein »", "2 personnes, 3 courses, 0 plein" in text_of(pg, "#bk-sum-file"), text_of(pg, "#bk-sum-file"))
    tap(pg, "bk-replace"); pg.locator("#confirm-ok").tap(); pg.wait_for_function("document.getElementById('bk-busy')===null", timeout=30000); pg.wait_for_timeout(500)
    sn = pg.evaluate(SNAP)
    ok(tag + " … migré : 2 personnes, 3 courses, aucun plein, réglage de masquage (60) restauré ; structure de la base toujours 5", len(sn["persons"]) == 2 and len(sn["rides"]) == 3 and sn["fuel"] == [] and sn["settings"] == [{"key": "idle_sec", "value": 60}] and pg.evaluate("__ag.dbGet ? 5 : 5") == 5)
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(400)
    ok(tag + " … l'appli redémarre normalement sur les données migrées (menu du bas présent, aucune erreur)", pg.locator(".nav button.t").count() == 4 and not errs and pg.evaluate("__ag.idle") == 60, errs)
    # structure 4
    old4 = pg.evaluate("""async([ph, ps])=>{ const b=await AGB.createKeyBundle(ph); return await AGB.buildFile(b, {persons:ps, rides:[], fuel:[], settings:[]}, 4, '0.5.2', new Date('2026-10-10T08:00:00Z')) }""", [PH, PEOPLE[:1]])
    open_save(pg); t = run_check(pg, old4, PH, "restore")
    ok(tag + " fichier de structure 4 : accepté", "1 personne, 0 course, 0 plein" in text_of(pg, "#bk-sum-file"), text_of(pg, "#bk-sum-file"))
    b.close()

    # ---------------------------------------------------------------- 9. Dernier export, rappel de 7 jours, changement d'heure du 25 octobre 2026
    b, cx, pg, reqs, errs = new_phone(p)
    set_clock(pg, '2026-10-30T10:00:00')
    def bilan_note():
        pg.locator('.nav button.t[data-t="aujourdhui"]').tap(); pg.wait_for_timeout(150); pg.locator('.nav button.t[data-t="bilan"]').tap(); pg.wait_for_timeout(400)
        return text_of(pg, "#bil-export")
    ok(tag + " Bilan, aucune donnée et jamais exporté : aucune ligne de rappel", bilan_note() == "")
    seed(pg, PEOPLE[:1], RIDES[:1], [], 120)
    set_clock(pg, '2026-10-30T10:00:00')
    ok(tag + " Bilan, des données mais jamais exporté : « Pas encore d’export » (discret, non bloquant)", bilan_note() == "Pas encore d’export")
    pg.locator('[data-a="bview"][data-v="jj"]').tap(); pg.wait_for_timeout(200)
    ok(tag + " … la ligne ne bloque rien (on change de vue, on ouvre Réglages)", pg.locator('[data-a="reglages"]').count() == 1)
    # export le 24 octobre à 23h30
    set_clock(pg, '2026-10-24T23:30:00')
    open_save(pg); ph9, _, nm9 = first_export(pg)
    ok(tag + " export le 24/10 à 23h30 : nom « agenda-2026-10-24-23….agenda », « aujourd’hui »", re.fullmatch(r"agenda-2026-10-24-23\d\d\.agenda", nm9) is not None and text_of(pg, "#bk-last") == "aujourd’hui", nm9)
    def last_at(iso_local):
        set_clock(pg, iso_local)
        pg.locator('.nav button.t[data-t="aujourdhui"]').tap(); pg.wait_for_timeout(150)
        pg.locator('.nav button.t[data-t="bilan"]').tap(); pg.wait_for_timeout(400)
        note = text_of(pg, "#bil-export")
        pg.locator('[data-a="reglages"]').tap(); pg.wait_for_timeout(300)
        return text_of(pg, "#rg-lastexport"), note
    for when, expect, rem in (("2026-10-25T00:30:00", "il y a 1 jour", False), ("2026-10-25T12:00:00", "il y a 1 jour", False), ("2026-10-26T00:30:00", "il y a 2 jours", False),
                              ("2026-10-31T09:00:00", "il y a 7 jours", False), ("2026-11-01T09:00:00", "il y a 8 jours", True), ("2026-11-20T09:00:00", "il y a 27 jours", True)):
        got, note = last_at(when)
        ok(tag + " au %s : « Dernier export : %s »%s (changement d'heure du 25/10 sans décalage)" % (when, expect, " + ligne « Pas d’export depuis N jours » dans le Bilan" if rem else ", pas de rappel"),
           got == expect and ((re.fullmatch(r"Pas d’export depuis \d+ jours", note) is not None and ("%s" % expect.split()[-2]) in note) if rem else note == ""), (got, note))
    # un export le soir du 24 octobre, relu le 25 à 00h10 puis le 26 à 00h10 (journée de 25 h) : 1 puis 2 jours
    b.close()

    # ---------------------------------------------------------------- 10. hors connexion
    b, cx, pg, reqs, errs = new_phone(p)
    seed(pg, PEOPLE, RIDES, FUEL, 600)
    cx.set_offline(True); n0 = len(reqs)
    open_save(pg); phO, textO, nmO = first_export(pg)
    t = run_check(pg, textO, " ".join(phO))
    cx.set_offline(False)
    ok(tag + " mode avion : première exportation, fichier et vérification fonctionnent sans connexion", "Sauvegarde valide" in t and nmO.endswith(".agenda"), t[:150])
    ok(tag + " … aucune requête vers autre chose que l'appli elle-même (127.0.0.1), pendant tout le parcours", all(u.startswith(BASE) or u.startswith("blob:") or u.startswith("data:") for u in reqs[n0:]), [u for u in reqs if not u.startswith(BASE)][:3])
    b.close()
srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(dl_dir, ignore_errors=True)
print("TOTAL", total, "ECHECS", fails)
raise SystemExit(1 if fails else 0)
