"""Mise à jour sans blocage (correctif 0.2.1). Simule ce qui s'est passé sur le téléphone : une ANCIENNE page encore ouverte garde sa connexion à la base
pendant que la nouvelle version veut mettre la structure des données à niveau.
Vérifie : message « Fermez et rouvrez l'appli pour finir la mise à jour » (au lieu d'un écran muet) quand l'ouverture est bloquée, disparition toute seule
quand le blocage se lève, même message si la base n'est pas prête après 5 secondes, lâcher de la connexion quand une autre page demande une nouvelle structure
(versionchange), mise à jour avec migration réelle (structure 3 → 4 sur une copie d'essai) avec UNE seule page puis avec une AUTRE page encore ouverte,
un seul rechargement après « Mettre à jour » (pas de boucle), aucune donnée perdue.
Aucune donnée de personne : seulement des réglages d'essai. W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, shutil, tempfile, threading, pathlib, http.server, functools
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
fails = 0; total = 0
MSG = "Fermez et rouvrez l’appli pour finir la mise à jour"


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


FILES = ("index.html", "app.js", "db.js", "rides.js", "style.css", "sw.js", "manifest.json", "version.js", "icon-192.png", "icon-512.png")


def copy_app():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="agenda_maj_"))
    for n in FILES: shutil.copy(ROOT / n, tmp / n)
    return tmp


def ctx_new(p, init=None):
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="allow")
    if init: cx.add_init_script(init)
    return b, cx


# base « version 0.1 » (structure 1) créée à la main, sans l'appli : meta + settings, un réglage reconnaissable
RAW_V1 = """new Promise(r=>{const q=indexedDB.open('agenda',1);q.onupgradeneeded=()=>{const d=q.result;d.createObjectStore('meta',{keyPath:'key'});d.createObjectStore('settings',{keyPath:'key'});
  const t=q.transaction;t.objectStore('meta').put({key:'created_at',value:'2026-10-07T08:00:00.000Z'});t.objectStore('meta').put({key:'schema_version',value:1});t.objectStore('meta').put({key:'persist_asked',value:'x'});t.objectStore('settings').put({key:'idle_sec',value:60})};
  q.onsuccess=()=>{window.__old=q.result;r(true)}})"""
DB_INFO = """new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result,v=d.version,s=[...d.objectStoreNames].sort();d.close();r({v,s})}})"""

with sync_playwright() as p:
    srv, BASE = serve(ROOT)

    # ================= A. ancienne page qui garde sa connexion (comme l'ancienne version 0.1) =================
    b, cx = ctx_new(p)
    old = cx.new_page(); old.goto(BASE + "manifest.json"); old.evaluate(RAW_V1)
    page = cx.new_page(); errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(BASE); page.wait_for_function("window.__ag"); page.wait_for_timeout(1500)
    state = page.evaluate("Promise.race([window.__ag.ready.then(()=>'prête',()=>'erreur'), new Promise(r=>setTimeout(()=>r('en attente'),800))])")
    ok(tag + " ancienne page qui garde la base ouverte : la mise à niveau est retenue (l'ouverture reste « en attente », rien n'est perdu)", state == "en attente", state)
    vis = page.evaluate("(()=>{const f=document.getElementById('fatal');return f.classList.contains('on')&&getComputedStyle(f).display!=='none'})()")
    ok(tag + " message affiché tout de suite (évènement « bloqué ») : « %s »" % MSG, vis and page.locator("#fatal-title").inner_text() == MSG, page.locator("#fatal-title").inner_text())
    ok(tag + " … avec une phrase simple en dessous (rien n'a été effacé, fermer complètement l'appli)", "Rien n’a été effacé" in page.locator("#fatal-text").inner_text() and "applis récentes" in page.locator("#fatal-text").inner_text())
    cov = page.evaluate("""(()=>{let n=0,c=0;for(let x=10;x<innerWidth;x+=Math.floor(innerWidth/6))for(let y=10;y<innerHeight;y+=Math.floor(innerHeight/8)){n++;const e=document.elementFromPoint(x,y);if(e&&e.closest('#fatal'))c++}return [n,c]})()""")
    ok(tag + " le message couvre tout l'écran, barre du bas comprise (pas d'écran muet avec menu absent ni de menu qui ne répond pas)", cov[0] == cov[1], cov)
    page.screenshot(path=SHOTS + "/miseajour_bloque_%dx%d_%s.png" % (W, H, SCHEME))
    old.evaluate("window.__old.close()")                      # l'ancienne page lâche enfin sa connexion
    page.wait_for_function("document.getElementById('fatal').classList.contains('on')===false", timeout=10000)
    page.evaluate("window.__ag.ready"); page.wait_for_timeout(300)
    info = page.evaluate(DB_INFO)
    ok(tag + " dès que le blocage se lève : la mise à niveau se termine toute seule, le message disparaît, sans rien rouvrir", info["v"] == 3 and info["s"] == ["meta", "persons", "rides", "settings"] and page.locator("#fatal.on").count() == 0, info)
    ok(tag + " … les données d'avant sont gardées (réglage de masquage 1 minute), la barre du bas répond", page.evaluate("__ag.idle") == 60 and page.locator(".nav button.t").count() == 4 and (page.locator('.nav button.t[data-t="personnes"]').tap() or True) and page.evaluate("__ag.cur") == "personnes")
    ok(tag + " aucune erreur JavaScript (cas bloqué)", not errs, errs)
    b.close()

    # ================= B. base pas prête après 5 secondes (sans évènement « bloqué ») =================
    b, cx = ctx_new(p, "indexedDB.open = function(){ return {}; };")     # l'ouverture ne répond jamais
    page = cx.new_page(); page.goto(BASE); page.wait_for_function("window.__ag"); page.wait_for_timeout(3500)
    ok(tag + " base pas prête à 3,5 s : pas encore de message (on laisse le temps)", page.locator("#fatal.on").count() == 0)
    page.wait_for_timeout(2200)
    ok(tag + " base pas prête après 5 secondes : le même message « %s » apparaît (au lieu d'un écran figé)" % MSG, page.locator("#fatal.on").count() == 1 and page.locator("#fatal-title").inner_text() == MSG)
    b.close()

    # ================= C. une autre page demande une nouvelle structure : on lâche la connexion =================
    b, cx = ctx_new(p)
    page = cx.new_page(); page.goto(BASE); page.wait_for_function("window.__ag"); page.evaluate("window.__ag.ready"); page.wait_for_timeout(300)
    other = cx.new_page(); other.goto(BASE + "manifest.json")
    r = other.evaluate("""new Promise(r=>{const t0=Date.now();const q=indexedDB.open('agenda',4);q.onupgradeneeded=()=>{q.result.createObjectStore('futur',{keyPath:'k'})};
      let blocked=false;q.onblocked=()=>{blocked=true};q.onsuccess=()=>{const v=q.result.version;q.result.close();r({v,blocked,ms:Date.now()-t0})};q.onerror=()=>r({err:String(q.error)})})""")
    ok(tag + " une autre page demande la structure 4 : l'appli ouverte lâche sa connexion, la demande n'est PAS bloquée (%s ms)" % r.get("ms"), r.get("v") == 4 and not r.get("blocked") and r.get("ms", 9999) < 3000, r)
    page.wait_for_timeout(300)
    ok(tag + " l'appli ouverte explique : « Agenda a été mis à jour dans une autre fenêtre » (rien d'effacé)", page.locator("#fatal.on").count() == 1 and "autre fenêtre" in page.locator("#fatal-title").inner_text() and "Rien n’a été effacé" in page.locator("#fatal-text").inner_text())
    b.close()
    srv.shutdown()

    # ================= D. vraie mise à jour avec migration (structure 3 → 4 sur une copie d'essai) =================
    tmp = copy_app(); srv2, B2 = serve(tmp)
    b, cx = ctx_new(p)
    p1 = cx.new_page(); nav1 = []; e1 = []
    p1.on("pageerror", lambda e: e1.append(str(e)))
    p1.on("load", lambda pg_: nav1.append(pg_.url))      # chaque chargement complet de la page (pas les simples changements d'adresse internes)
    p1.goto(B2); p1.wait_for_function("window.__ag"); p1.evaluate("window.__ag.ready")
    p1.wait_for_function("!!navigator.serviceWorker.controller"); p1.reload(); p1.wait_for_function("window.__ag"); p1.evaluate("window.__ag.ready"); p1.wait_for_timeout(500)
    p2 = cx.new_page(); p2.goto(B2); p2.wait_for_function("window.__ag"); p2.evaluate("window.__ag.ready"); p2.wait_for_timeout(300)   # une 2e page (autre onglet) reste ouverte
    # « publication » : nouvelle version + nouvelle migration (3)
    dbjs = (tmp / "db.js").read_text(encoding="utf-8")
    marker = "tx.objectStore('rides').createIndex('date', 'date', { unique: false });\n  } }\n];"
    assert dbjs.replace("\r\n", "\n").count(marker) == 1
    (tmp / "db.js").write_text(dbjs.replace("\r\n", "\n").replace(marker, "tx.objectStore('rides').createIndex('date', 'date', { unique: false });\n  } },\n  { version: 4, up: function (db, tx) { db.createObjectStore('extra', { keyPath: 'id' }); } }\n];"), encoding="utf-8")
    (tmp / "version.js").write_text("self.APP_VERSION = '9.9.9';\n", encoding="utf-8")
    p1.locator('.nav button.t[data-t="bilan"]').tap(); p1.wait_for_timeout(250); p1.locator('[data-a="reglages"]').tap(); p1.wait_for_timeout(250)
    for essai in range(4):          # une recherche déjà en cours au chargement peut absorber la première demande : on redemande
        p1.locator('[data-a="checkupdate"]').tap()
        try:
            p1.wait_for_function("document.getElementById('update').hidden===false", timeout=9000); break
        except Exception:
            p1.wait_for_timeout(500)
    p1.wait_for_timeout(800)
    ok(tag + " nouvelle version + nouvelle structure publiées : « Nouvelle version disponible » apparaît, la page ne se recharge pas toute seule", p1.locator("#update").is_visible() and len(nav1) == 2 and p1.locator("#rg-schema").inner_text() == "3", (len(nav1), p1.locator("#rg-schema").inner_text()))
    n_before = len(nav1)
    p1.evaluate("window.__marqueur=1")
    p1.locator('#update [data-a="applyupdate"]').tap()
    p1.wait_for_function("window.__marqueur===undefined", timeout=20000)
    p1.wait_for_function("window.__ag && window.__ag.ready"); p1.evaluate("window.__ag.ready"); p1.wait_for_timeout(1500)
    nav_after = len(nav1) - n_before
    ok(tag + " « Mettre à jour » : UN SEUL rechargement (%d), pas de boucle (on attend encore 5 s)" % nav_after, nav_after == 1, nav_after)
    p1.wait_for_timeout(5000)
    ok(tag + " … toujours un seul rechargement 5 s plus tard", len(nav1) - n_before == 1, len(nav1) - n_before)
    p1.locator('.nav button.t[data-t="bilan"]').tap(); p1.wait_for_timeout(250); p1.locator('[data-a="reglages"]').tap(); p1.wait_for_timeout(250)
    ok(tag + " migration réelle 3 → 4 faite malgré la 2e page ouverte : version 9.9.9, structure n° 4, aucun message de blocage", p1.locator("#rg-version").inner_text() == "9.9.9" and p1.locator("#rg-schema").inner_text() == "4" and p1.locator("#fatal.on").count() == 0, (p1.locator("#rg-version").inner_text(), p1.locator("#rg-schema").inner_text()))
    info = p1.evaluate(DB_INFO)
    ok(tag + " la base est bien en structure 4 avec le nouveau magasin, les anciens magasins gardés", info["v"] == 4 and info["s"] == ["extra", "meta", "persons", "rides", "settings"], info)
    ok(tag + " la nouvelle page affiche son menu du bas et répond (4 onglets, un toucher change de page)", p1.locator(".nav button.t").count() == 4 and (p1.locator('.nav button.t[data-t="essence"]').tap() or True) and p1.evaluate("__ag.cur") == "essence")
    ok(tag + " la 2e page restée ouverte a lâché sa connexion et l'explique (« mis à jour dans une autre fenêtre »), sans bloquer", p2.locator("#fatal.on").count() == 1 and "autre fenêtre" in p2.locator("#fatal-title").inner_text())
    ok(tag + " aucune erreur JavaScript pendant la mise à jour avec migration", not e1, e1)
    p1.screenshot(path=SHOTS + "/miseajour_apres_%dx%d_%s.png" % (W, H, SCHEME))
    b.close(); srv2.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
print("TOTAL", total, "ECHECS", fails)
