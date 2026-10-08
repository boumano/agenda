"""La « garde » de la version 0.5.1 : diagnostic du premier affichage, erreurs, fichiers de versions différentes, message « Un problème est survenu ».
Vérifie : tampon de version dans chaque fichier (= version.js), ligne « Écran affiché (menu prêt) » au démarrage normal, erreur JavaScript non attrapée et promesse
rejetée notées dans le journal (court, sans donnée), 20 lignes au plus, une partie du code qui échoue n'empêche pas le menu du bas ni l'écran (message + bouton « Recharger »),
fichiers de versions différentes : liste dans le journal, UN seul rechargement en contournant les réserves (puis tout va bien), et si le défaut reste : message simple, pas de boucle ;
rien de lisible quand l'écran est masqué.
Aucune donnée de personne. W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, shutil, subprocess, sys, tempfile, threading, pathlib, http.server
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
FILES = ("index.html", "garde.js", "app.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "style.css", "sw.js", "manifest.json", "version.js", "icon-192.png", "icon-512.png")
CUR = re.search(r"APP_VERSION\s*=\s*'([^']+)'", (ROOT / "version.js").read_text(encoding="utf-8")).group(1)
fails = 0; total = 0


def ok(n, c, e=""):
    global fails, total
    total += 1
    if not c: fails += 1
    print(("PASS " if c else "FAIL ") + n + (" | " + str(e)[:600] if not c else ""))


class S:
    once = {}       # nom -> octets servis UNE fois seulement (puis le vrai fichier)
    always = {}     # nom -> octets toujours servis à la place du vrai fichier


def make_handler(directory):
    class H_(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k): super().__init__(*a, directory=str(directory), **k)
        def do_GET(self):
            name = self.path.split("?")[0].lstrip("/") or "index.html"
            data = S.once.pop(name, None) or S.always.get(name)
            if data is not None:
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript" if name.endswith(".js") else "text/css" if name.endswith(".css") else "text/html")
                self.send_header("Content-Length", str(len(data))); self.send_header("Cache-Control", "max-age=600"); self.end_headers(); self.wfile.write(data); return
            super().do_GET()
        def end_headers(self):
            self.send_header("Cache-Control", "max-age=600")
            super().end_headers()
        def log_message(self, *a): pass
    return H_


def start():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="agenda_garde_"))
    for n in FILES: shutil.copy(ROOT / n, tmp / n)
    S.once = {}; S.always = {}
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return tmp, srv, "http://127.0.0.1:%d/" % srv.server_address[1]


def journal(pg):
    return pg.evaluate("""new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const g=q.result.transaction('meta').objectStore('meta').get('update_log');g.onsuccess=()=>{q.result.close();r((g.result&&g.result.value)||[])}}})""")


def texts(pg): return [x["e"] for x in journal(pg)]


def new_ctx(p):
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="block")
    return b, cx


def open_page(cx, base, settle=1500):
    errs = []; loads = []
    pg = cx.new_page(); pg.on("load", lambda: loads.append(1)); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(base); pg.wait_for_timeout(settle)
    return pg, loads, errs


def vis(pg, sel): return pg.evaluate("s=>{const e=document.querySelector(s);if(!e)return false;const r=e.getBoundingClientRect();return r.height>0&&r.width>0&&getComputedStyle(e).display!=='none'&&!e.hidden}", sel)


# ---------- 0. tampons : un numéro de version dans chaque fichier, égal à celui de version.js (sans navigateur)
r = subprocess.run([sys.executable, str(HERE / "sync_version.py"), "--check"], capture_output=True, text=True, encoding="utf-8")
ok(tag + " tampons de version : chaque fichier JavaScript, style.css et index.html portent le numéro de version.js (%s)" % CUR, r.returncode == 0, r.stdout + r.stderr)
for f in ("garde.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "app.js"):
    t = (ROOT / f).read_text(encoding="utf-8")
    ok(tag + " %s : tampon en toute première ligne" % f, t.startswith("self.AG_STAMPS=self.AG_STAMPS||{};self.AG_STAMPS['%s']='%s';" % (f, CUR)), t[:100])

with sync_playwright() as p:
    # ---------- 1. démarrage normal
    tmp, srv, base = start(); b, cx = new_ctx(p)
    try:
        pg, loads, errs = open_page(cx, base)
        tx = texts(pg)
        ok(tag + " démarrage normal : « Écran affiché (menu prêt) » dans le journal, après « Démarrage de la version %s »" % CUR, "Écran affiché (menu prêt)" in tx and tx.index("Écran affiché (menu prêt)") > tx.index("Démarrage de la version " + CUR), tx)
        ok(tag + " démarrage normal : ni « Erreur », ni « Fichiers de versions différentes », ni message de problème, un seul chargement", not [x for x in tx if x.startswith(("Erreur", "Fichiers de versions"))] and not vis(pg, "#fatal.on") and len(loads) == 1 and not errs, (tx, len(loads)))
        ok(tag + " … le bouton « Recharger » est caché", not vis(pg, "#fatal-btn"))
        # erreur après le démarrage : notée, mais aucun message (l'appli marche)
        pg.evaluate("setTimeout(()=>{ null.x }, 0)"); pg.evaluate("setTimeout(()=>{ Promise.reject(new Error('rejet essai')) }, 0)"); pg.wait_for_timeout(500)
        tx = texts(pg)
        ok(tag + " erreur JavaScript non attrapée et promesse rejetée : deux lignes « Erreur : … » courtes dans le journal", any(x.startswith("Erreur :") and "null" in x for x in tx) and any(x.startswith("Erreur :") and "rejet essai" in x for x in tx) and all(len(x) <= 160 for x in tx), tx)
        ok(tag + " … l'appli continue de fonctionner, sans message (l'erreur est survenue après l'affichage)", not vis(pg, "#fatal.on") and vis(pg, ".nav"))
        pg.evaluate("for(let i=0;i<30;i++) setTimeout(()=>{ null.y }, 0)"); pg.wait_for_timeout(500)
        ok(tag + " au plus 20 lignes dans le journal, et au plus 3 lignes d'erreur par chargement (pas d'inondation)", len(journal(pg)) <= 20 and len([x for x in texts(pg) if x.startswith("Erreur")]) <= 3 + 0, len(journal(pg)))
        # le journal reste invisible hors Réglages
        ok(tag + " le journal ne s'affiche que dans Réglages (rien de lisible ailleurs)", not vis(pg, "#rg-log"))
    finally:
        b.close(); srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)

    # ---------- 2. une partie du code échoue au premier affichage : le menu et l'écran restent, message + bouton
    tmp, srv, base = start(); b, cx = new_ctx(p)
    try:
        app = (ROOT / "app.js").read_bytes().decode("utf-8")
        assert "function renderAuj() {" in app
        S.always["app.js"] = app.replace("function renderAuj() {", "function renderAuj() { throw new Error('essai affichage');", 1).encode("utf-8")
        pg, loads, errs = open_page(cx, base)
        tx = texts(pg)
        ok(tag + " affichage qui échoue : le menu du bas est là (4 boutons) et répond", pg.locator(".nav button.t").count() == 4 and vis(pg, ".nav"))
        ok(tag + " … « Erreur : essai affichage » notée, puis « Écran pas affiché correctement : écran vide »", any(x.startswith("Erreur : essai affichage") for x in tx) and any(x.startswith("Écran pas affiché correctement") for x in tx), tx)
        ok(tag + " … message « Un problème est survenu à l’affichage » + bouton « Recharger » (plus d'écran figé muet)", vis(pg, "#fatal.on") and "problème est survenu à l’affichage" in pg.locator("#fatal-title").inner_text() and "Touchez pour recharger" in pg.locator("#fatal-text").inner_text() and vis(pg, "#fatal-btn") and pg.locator("#fatal-btn").inner_text() == "Recharger")
        pg.screenshot(path=SHOTS + "/garde_probleme_%dx%d_%s.png" % (W, H, SCHEME))
        n0 = len(loads)
        S.always.clear()                                       # le problème est « réparé » côté site : le bouton recharge et tout revient
        pg.locator("#fatal-btn").tap(); pg.wait_for_timeout(2000)
        ok(tag + " … toucher « Recharger » : la page se recharge une fois et s'affiche normalement", len(loads) == n0 + 1 and not vis(pg, "#fatal.on") and "Écran affiché (menu prêt)" in texts(pg), (len(loads), n0, vis(pg, "#fatal.on"), texts(pg)))
    finally:
        b.close(); srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)

    # ---------- 3. fichiers de versions différentes, réparé par UN rechargement
    tmp, srv, base = start(); b, cx = new_ctx(p)
    try:
        stale = (ROOT / "db.js").read_bytes().decode("utf-8").replace("AG_STAMPS['db.js']='%s'" % CUR, "AG_STAMPS['db.js']='0.0.1'", 1).encode("utf-8")
        css_stale = (ROOT / "style.css").read_bytes().decode("utf-8").replace('--ag-version:"%s"' % CUR, '--ag-version:"0.0.1"', 1).encode("utf-8")
        S.once["db.js"] = stale; S.once["style.css"] = css_stale
        pg, loads, errs = open_page(cx, base, 3500)
        tx = texts(pg)
        mix = [x for x in tx if x.startswith("Fichiers de versions différentes")]
        ok(tag + " versions différentes (db.js et style.css anciens) : la liste figure dans le journal", len(mix) == 1 and "db.js 0.0.1" in mix[0] and "style.css 0.0.1" in mix[0] and "rechargement unique" in mix[0], tx)
        ok(tag + " … UN seul rechargement (2 chargements au total), puis tout est cohérent : écran affiché, aucun message", len(loads) == 2 and not vis(pg, "#fatal.on") and "Écran affiché (menu prêt)" in tx and pg.evaluate("AGG.mismatches().length") == 0, (len(loads), tx))
        pg.wait_for_timeout(3000)
        ok(tag + " … pas de boucle de rechargements 3 s plus tard", len(loads) == 2, len(loads))
    finally:
        b.close(); srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)

    # ---------- 4. fichiers de versions différentes qui le restent : message, pas de boucle
    tmp, srv, base = start(); b, cx = new_ctx(p)
    try:
        S.always["db.js"] = (ROOT / "db.js").read_bytes().decode("utf-8").replace("AG_STAMPS['db.js']='%s'" % CUR, "AG_STAMPS['db.js']='0.0.1'", 1).encode("utf-8")
        pg, loads, errs = open_page(cx, base, 4500)
        tx = texts(pg)
        mix = [x for x in tx if x.startswith("Fichiers de versions différentes")]
        ok(tag + " versions différentes qui persistent : deux lignes dans le journal (rechargement unique, puis « le problème reste »)", len(mix) == 2 and "rechargement unique" in mix[0] and "le problème reste" in mix[1], tx)
        ok(tag + " … exactement 2 chargements (aucune boucle) et le message « Un problème est survenu » avec son bouton", len(loads) == 2 and vis(pg, "#fatal.on") and vis(pg, "#fatal-btn"), len(loads))
        pg.wait_for_timeout(3000)
        ok(tag + " … toujours 2 chargements 3 s plus tard", len(loads) == 2, len(loads))
        pg.screenshot(path=SHOTS + "/garde_versions_%dx%d_%s.png" % (W, H, SCHEME))
    finally:
        b.close(); srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)

    # ---------- 5. rien de lisible quand l'écran est masqué
    tmp, srv, base = start(); b, cx = new_ctx(p)
    try:
        pg, loads, errs = open_page(cx, base)
        pg.locator('.nav button.t[data-t="personnes"]').tap(); pg.wait_for_timeout(200)
        pg.locator('#s-personnes [data-a="hide"]').tap(); pg.wait_for_timeout(300)
        masked = pg.evaluate("__ag.masked")
        pg.evaluate("AGG.shown=false; AGG.problem()"); pg.wait_for_timeout(300)
        ok(tag + " écran masqué : le message de problème n'apparaît PAS sous l'écran neutre", masked and not vis(pg, "#fatal.on"), masked)
        pg.locator("#veil").tap(); pg.wait_for_timeout(400)
        ok(tag + " … il apparaît au retour de l'écran", vis(pg, "#fatal.on") and vis(pg, "#fatal-btn"))
    finally:
        b.close(); srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
print("TOTAL", total, "ECHECS", fails)
raise SystemExit(1 if fails else 0)
