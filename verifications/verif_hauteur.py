"""Hauteur de la fenêtre (correctif 0.5.2) : le menu du bas doit rester ENTIÈREMENT dans la zone visible, même quand la taille de la fenêtre change
après le démarrage (barre système Android qui apparaît après coup, rotation, clavier), après un rechargement ou une mise à jour.
Scénarios : taille changée après « Écran affiché » (780 → 700 → 780 → 860 → 700), démarrage plus grand que la taille finale (860 puis 780 tout de suite),
rechargement normal avec changement de taille, « Mettre à jour » avec changement de taille juste après le rechargement, et une fenêtre dont la hauteur « vue par la page »
reste trop grande (zone visible plus petite que la fenêtre de mise en page : cas observé sur le Galaxy A12), rejouée en rendant la hauteur de #app périmée.
Aucune donnée de personne. W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, shutil, tempfile, threading, pathlib, http.server, functools
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
import sys; sys.path.insert(0, str(HERE))
from _outils import fausse_version
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
        self.send_header("Cache-Control", "max-age=600")
        super().end_headers()
    def log_message(self, *a): pass


def serve(directory):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(directory)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d/" % srv.server_address[1]


def copy_app():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="agenda_haut_"))
    for n in FILES: shutil.copy(ROOT / n, tmp / n)
    return tmp


MEASURE = """()=>{const n=document.querySelector('.nav').getBoundingClientRect(), a=document.getElementById('app').getBoundingClientRect(), v=window.visualViewport?visualViewport.height:innerHeight;
  return {navBottom:Math.round(n.bottom*10)/10, navTop:Math.round(n.top), appBottom:Math.round(a.bottom*10)/10, appH:Math.round(a.height), visible:Math.round(v), inner:innerHeight}}"""


def inside(m): return m["navBottom"] <= m["visible"] + 0.6 and m["navBottom"] >= m["visible"] - 1.5      # entièrement visible ET collé au bas


def new_ctx(p, w=W, h=H, sw="block"):
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": w, "height": h}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers=sw)
    return b, cx


def ready(pg):
    pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(500)


def journal(pg):
    return pg.evaluate("""new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const g=q.result.transaction('meta').objectStore('meta').get('update_log');g.onsuccess=()=>{q.result.close();r(((g.result&&g.result.value)||[]).map(x=>x.e))}}})""")


with sync_playwright() as p:
    tmp = copy_app(); srv, base = serve(tmp)
    try:
        # ---- 1. changements de taille après l'affichage
        b, cx = new_ctx(p)
        pg = cx.new_page(); pg.goto(base); ready(pg)
        m = pg.evaluate(MEASURE)
        ok(tag + " au départ (%dx%d) : menu du bas entièrement visible, collé au bas" % (W, H), inside(m), m)
        for hh in (H - 80, H, H + 80, H - 80):
            pg.set_viewport_size({"width": W, "height": hh}); pg.wait_for_timeout(400)
            m = pg.evaluate(MEASURE)
            ok(tag + " fenêtre changée en %dx%d après l'affichage : menu du bas toujours entièrement visible" % (W, hh), inside(m), m)
        pg.screenshot(path=SHOTS + "/hauteur_%dx%d_%s.png" % (W, H, SCHEME))
        b.close()

        # ---- 2. démarrage plus grand que la hauteur finale (la barre système apparaît après coup)
        for delay in (0, 150, 1200):
            b, cx = new_ctx(p, W, H + 90)
            pg = cx.new_page(); pg.goto(base); pg.wait_for_function("document.querySelector('.nav')")
            pg.wait_for_timeout(delay); pg.set_viewport_size({"width": W, "height": H}); ready(pg); pg.wait_for_timeout(600)
            m = pg.evaluate(MEASURE)
            ok(tag + " démarrage à %d puis fenêtre réduite à %d après %d ms : menu du bas entièrement visible" % (H + 90, H, delay), inside(m), m)
            b.close()

        # ---- 3. rechargement normal avec changement de taille juste après
        b, cx = new_ctx(p)
        pg = cx.new_page(); pg.goto(base); ready(pg)
        pg.set_viewport_size({"width": W, "height": H + 90}); pg.reload(); pg.set_viewport_size({"width": W, "height": H}); ready(pg); pg.wait_for_timeout(800)
        m = pg.evaluate(MEASURE)
        ok(tag + " rechargement normal + fenêtre réduite juste après : menu du bas entièrement visible", inside(m), m)
        b.close()

        # ---- 4. hauteur « vue par la page » périmée : la zone visible est plus petite que la fenêtre de mise en page (Galaxy A12 après le rechargement)
        #         on rejoue en figeant la hauteur de #app AVANT que la page ne lise la zone visible, puis en réduisant la fenêtre sans que #app ne suive
        b, cx = new_ctx(p)
        pg = cx.new_page(); pg.goto(base); ready(pg)
        pg.evaluate("""()=>{ const a=document.getElementById('app'); const h=a.getBoundingClientRect().height; window.__figee=h; a.style.setProperty('height', (h+90)+'px', 'important'); }""")
        pg.wait_for_timeout(100)
        pg.evaluate("window.dispatchEvent(new Event('resize'))"); pg.wait_for_timeout(2600)
        m = pg.evaluate(MEASURE)
        ok(tag + " hauteur de #app périmée (trop grande de 90 px) : la page se corrige seule, menu du bas entièrement visible", inside(m), m)
        tx = journal(pg)
        ok(tag + " … le journal note « Mise en page corrigée : fenêtre H, visible V, bas du menu B » (une seule fois)", len([x for x in tx if x.startswith("Mise en page corrigée : fenêtre ")]) == 1, tx)
        ok(tag + " … et « Mise en page : fenêtre H, visible V, bas du menu B » au moment de « Écran affiché (menu prêt) »", any(re.match(r"^Mise en page : fenêtre \d+, visible \d+, bas du menu \d+", x) for x in tx), tx)
        b.close()

        # ---- 5. « Mettre à jour » avec changement de taille juste après le rechargement
        fausse_version(tmp, "9.9.8")                    # la version « déjà installée » : fichiers cohérents 9.9.8
        b, cx = new_ctx(p, W, H, "allow")
        pg = cx.new_page(); pg.goto(base); ready(pg)
        pg.wait_for_function("!!navigator.serviceWorker.controller"); pg.reload(); ready(pg)
        fausse_version(tmp, "9.9.9")                    # « publication » de la suivante
        pg.locator('.nav button.t[data-t="bilan"]').tap(); pg.wait_for_timeout(250); pg.locator('[data-a="reglages"]').tap(); pg.wait_for_timeout(250)
        found = False
        for _ in range(4):
            pg.locator('[data-a="checkupdate"]').tap()
            try: pg.wait_for_function("document.getElementById('update').hidden===false", timeout=9000); found = True; break
            except Exception: pg.wait_for_timeout(500)
        ok(tag + " « Nouvelle version disponible » apparaît (9.9.8 → 9.9.9)", found)
        pg.evaluate("window.__marqueur=1")
        pg.locator('#update [data-a="applyupdate"]').tap()
        pg.wait_for_function("window.__marqueur===undefined", timeout=25000)
        pg.set_viewport_size({"width": W, "height": H + 90}); pg.wait_for_timeout(150); pg.set_viewport_size({"width": W, "height": H})
        ready(pg); pg.wait_for_timeout(2600)
        m = pg.evaluate(MEASURE)
        ok(tag + " « Mettre à jour » + changement de taille juste après le rechargement : version 9.9.9 et menu du bas entièrement visible", pg.evaluate("__ag.version") == "9.9.9" and inside(m), (pg.evaluate("__ag.version"), m))
        b.close()
    finally:
        srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
print("TOTAL", total, "ECHECS", fails)
raise SystemExit(1 if fails else 0)
