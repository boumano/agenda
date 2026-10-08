"""Cache cohérent après « Mettre à jour » (correctif 0.5.1). Preuve de la cause AVANT correction, disparition APRÈS.
Vrais fichiers de 0.4.1 (commit 886bcbd) puis « publication » de la version actuelle, avec le vrai service worker.
Après « Mettre à jour » et rechargement, on compare le contenu de CHAQUE fichier réellement servi à la page (octets) avec ceux de la version actuelle,
et on mesure : menu du bas présent, écran présent, base prête. Scénarios : normal, réseau lent, réseau coupé juste après, 2e page ouverte,
réseau lent pendant l'installation du nouveau service worker, fichier manquant à l'installation (installation atomique).
NEW_REF=HEAD (ou un autre commit) : joue les mêmes scénarios avec les fichiers de CE commit comme « version publiée » (preuve du défaut AVANT correction).
Aucune donnée de personne. W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, shutil, subprocess, tempfile, threading, pathlib, http.server, time, hashlib
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
OLD = "886bcbd"
NEW_FILES = ("index.html", "garde.js", "app.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "style.css", "sw.js", "manifest.json", "version.js", "icon-192.png", "icon-512.png")
OLD_FILES = ("index.html", "app.js", "db.js", "rides.js", "style.css", "sw.js", "manifest.json", "version.js")
NEW_REF = os.environ.get("NEW_REF", "")
fails = 0; total = 0


def ok(n, c, e=""):
    global fails, total
    total += 1
    if not c: fails += 1
    print(("PASS " if c else "FAIL ") + n + (" | " + str(e)[:700] if not c else ""))


class State:
    delay = {}          # nom de fichier -> secondes de retard ("*" = tous)
    offline = False     # True : 503 partout
    broken = set()      # fichiers qui répondent 503 (pour l'installation atomique)


def make_handler(directory):
    class H_(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k): super().__init__(*a, directory=str(directory), **k)
        def do_GET(self):
            name = self.path.split("?")[0].lstrip("/") or "index.html"
            if State.offline or name in State.broken:
                self.send_error(503); return
            d = State.delay.get(name) or State.delay.get("*")
            if d: time.sleep(d)
            super().do_GET()
        def end_headers(self):
            self.send_header("Cache-Control", "max-age=600")
            super().end_headers()
        def log_message(self, *a): pass
    return H_


def serve(directory):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), make_handler(directory))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d/" % srv.server_address[1]


def git_show(name):
    r = subprocess.run(["git", "-C", str(ROOT), "show", "%s:%s" % (OLD, name)], capture_output=True)
    if r.returncode: raise RuntimeError(r.stderr.decode(errors="replace"))
    return r.stdout


def new_bytes(name):
    if not NEW_REF: return (ROOT / name).read_bytes()
    r = subprocess.run(["git", "-C", str(ROOT), "show", "%s:%s" % (NEW_REF, name)], capture_output=True)
    return r.stdout if r.returncode == 0 else None


NEW_FILES = tuple(n for n in NEW_FILES if new_bytes(n) is not None)
CUR = re.search(r"APP_VERSION\s*=\s*'([^']+)'", new_bytes("version.js").decode("utf-8")).group(1)
if NEW_REF: tag = tag[:-1] + " publié=%s %s]" % (NEW_REF, CUR)


def sha(b): return hashlib.sha1(b).hexdigest()


def setup(p):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="agenda_coh_"))
    for n in OLD_FILES: (tmp / n).write_bytes(git_show(n))
    for n in ("icon-192.png", "icon-512.png"): shutil.copy(ROOT / n, tmp / n)
    State.delay = {}; State.offline = False; State.broken = set()
    srv, base = serve(tmp)
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="allow")
    return tmp, srv, base, b, cx


def boot(cx, base):
    pg = cx.new_page(); pg.goto(base)
    pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready")
    pg.wait_for_function("!!navigator.serviceWorker.controller"); pg.reload()
    pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(400)
    return pg


def publish(tmp):
    for n in NEW_FILES: (tmp / n).write_bytes(new_bytes(n))


def ask_update(pg, wait=30000):
    pg.locator('.nav button.t[data-t="bilan"]').tap(); pg.wait_for_timeout(250); pg.locator('[data-a="reglages"]').tap(); pg.wait_for_timeout(250)
    for _ in range(6):
        pg.locator('[data-a="checkupdate"]').tap()
        try:
            pg.wait_for_function("document.getElementById('update').hidden===false", timeout=wait // 3); return True
        except Exception:
            pg.wait_for_timeout(500)
    return False


def served_report(pg):
    """Pour chaque fichier : empreinte du contenu que la page reçoit maintenant (fetch, donc via le service worker)."""
    return pg.evaluate("""async(names)=>{const out={};for(const n of names){try{const r=await fetch(n);if(!r.ok){out[n]='HTTP'+r.status;continue}const b=new Uint8Array(await r.arrayBuffer());
      const h=await crypto.subtle.digest('SHA-1',b);out[n]=[...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,'0')).join('')}catch(e){out[n]='ERR'}}return out}""", list(NEW_FILES))


def mixed(rep):
    return sorted(n for n in NEW_FILES if n != "sw.js" and rep.get(n) != sha(new_bytes(n)))


def screen_state(pg):
    return pg.evaluate("""({nav:document.querySelectorAll('.nav button.t').length, navVisible:(()=>{const n=document.querySelector('.nav');if(!n)return false;const r=n.getBoundingClientRect();return r.height>10&&getComputedStyle(n).display!=='none'})(),
      fatal:document.getElementById('fatal').classList.contains('on'), cur:window.__ag&&window.__ag.cur, version:window.__ag&&window.__ag.version})""")


def one_update(p, name, after_tap=None, second_page=False, slow_install=None):
    tmp, srv, base, b, cx = setup(p)
    try:
        errs = []; loads = []
        p1 = boot(cx, base); p1.on("pageerror", lambda e: errs.append(str(e))); p1.on("load", lambda: loads.append(1))
        p2 = boot(cx, base) if second_page else None
        publish(tmp)
        if slow_install: State.delay = dict(slow_install)
        found = ask_update(p1, 90000)
        State.delay = {}
        ok(tag + " [%s] « Nouvelle version disponible » apparaît" % name, found)
        if not found: return
        p1.evaluate("window.__marqueur=1")
        p1.locator('#update [data-a="applyupdate"]').tap()
        if after_tap: after_tap()
        try:
            p1.wait_for_function("window.__marqueur===undefined", timeout=25000)
        except Exception:
            pass
        try:
            p1.wait_for_function("window.__ag && window.__ag.ready", timeout=15000); p1.evaluate("window.__ag.ready")
        except Exception:
            pass
        p1.wait_for_timeout(1500)
        st = screen_state(p1)
        ok(tag + " [%s] menu du bas + écran présents après le rechargement, version %s" % (name, CUR), st["nav"] == 4 and st["navVisible"] and not st["fatal"] and st["version"] == CUR, st)
        State.offline = True                                   # on juge ce que le service worker sert SEUL (réseau coupé)
        rep = served_report(p1)
        State.offline = False
        mx = mixed(rep)
        ok(tag + " [%s] TOUS les fichiers servis sont ceux de la version %s (aucun mélange de versions)" % (name, CUR), not mx, "fichiers pas à jour : %s" % {n: rep[n][:8] for n in mx})
        ok(tag + " [%s] pas d'erreur JavaScript" % name, not errs, errs)
        p1.locator('.nav button.t[data-t="personnes"]').tap(); p1.wait_for_timeout(300)
        ok(tag + " [%s] le menu du bas répond" % name, p1.evaluate("__ag.cur") == "personnes")
    finally:
        b.close(); srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)


def set_offline():
    State.offline = True


with sync_playwright() as p:
    one_update(p, "normal")
    one_update(p, "normal, 2e page ouverte", second_page=True)
    one_update(p, "réseau lent (1,5 s par fichier) pendant l'installation", slow_install={"*": 1.5})
    one_update(p, "réseau lent sur app.js et style.css seulement", slow_install={"app.js": 4, "style.css": 3})
    one_update(p, "réseau coupé juste après le toucher", after_tap=set_offline)
    one_update(p, "réseau coupé juste après le toucher, 2e page ouverte", second_page=True, after_tap=set_offline)
    # installation atomique : un fichier de la nouvelle version manque pendant l'installation → l'ancienne version doit rester entière
    tmp, srv, base, b, cx = setup(p)
    try:
        p1 = boot(cx, base)
        publish(tmp); State.broken = {"fuel.js"}
        found = ask_update(p1, 12000)
        ok(tag + " [fichier manquant] l'installation échoue en entier : pas de « Nouvelle version disponible » à moitié prête", not found)
        State.offline = True
        rep = served_report(p1); State.offline = False
        ok(tag + " [fichier manquant] l'appli continue de servir la version 0.4.1 ENTIÈRE", rep.get("app.js") == sha(git_show("app.js")) and rep.get("version.js") == sha(git_show("version.js")), rep)
        st = screen_state(p1)
        ok(tag + " [fichier manquant] l'écran reste utilisable", st["nav"] == 4 and not st["fatal"], st)
    finally:
        b.close(); srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
    # installation interrompue (réseau mobile capricieux) : un cache PARTIEL de la nouvelle version ne doit jamais être servi à la place de l'ancienne version.
    # L'ancien service worker (0.4.1, vrai code) cherche dans TOUTES les réserves ; fuel.js n'existe pas en 0.4.1 : s'il est servi, c'est un mélange.
    tmp, srv, base, b, cx = setup(p)
    try:
        p1 = boot(cx, base)
        publish(tmp); State.broken = {"icon-512.png"}
        found = ask_update(p1, 12000)
        State.offline = True
        r = p1.evaluate("""fetch('fuel.js',{cache:'no-store'}).then(r=>r.status).catch(()=>'réseau')""")
        State.offline = False
        ok(tag + " [cache partiel] après une installation interrompue, fuel.js (absent de 0.4.1) n'est PAS servi depuis une réserve incomplète de la nouvelle version", r != 200, "fuel.js servi (code %s) : mélange 0.4.1 + nouvelle version" % r)
        ks = p1.evaluate("caches.keys()")
        ok(tag + " [cache partiel] aucune réserve incomplète ne reste après l'échec", ks == ["agenda-0.4.1"], ks)
        State.broken = set()                                                   # le réseau revient : nouvel essai complet
        found = ask_update(p1, 30000)
        ok(tag + " [cache partiel] au nouvel essai, l'installation aboutit et « Nouvelle version disponible » apparaît", found)
    finally:
        b.close(); srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
print("TOTAL", total, "ECHECS", fails)
raise SystemExit(1 if fails else 0)
