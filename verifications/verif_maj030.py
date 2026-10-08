"""Mise à jour 0.2.1 → version actuelle (qui change la structure des données : 2 → 5) et journal de mise à jour.
Simule ce qui se passe sur le téléphone de Pascal : les VRAIS fichiers de la version 0.2.1 (retirés de l'historique git, commit 35b4c67) tournent dans deux pages,
puis la version actuelle est « publiée » ; on touche « Mettre à jour » dans la première page, la deuxième (ancienne) reste ouverte.
Vérifie : aucun blocage ni écran figé, UN seul rechargement, menu du bas présent, structure 5 avec index par date, personnes et réglages gardés,
la page restée ouverte lâche sa connexion et l'explique ; journal de mise à jour (évènements, ordre, 20 au plus, aucune donnée de personne),
et la même chose pour la suite (version actuelle → une version suivante avec une nouvelle structure 4 sur une copie d'essai) avec les évènements écrits AVANT le rechargement.
Noms FICTIFS seulement. W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, shutil, subprocess, tempfile, threading, pathlib, http.server, functools
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
import sys; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _outils import fausse_version
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
CUR = re.search(r"APP_VERSION\s*=\s*'([^']+)'", (ROOT / "version.js").read_text(encoding="utf-8")).group(1)      # version actuelle du dossier
NEXT = "9.9.9"                                      # « version suivante » inventée pour l'essai
T = lambda x: x.replace("@CUR@", CUR).replace("@NEXT@", NEXT)
OLD = "35b4c67"                                     # commit de la version 0.2.1
fails = 0; total = 0
NEW_FILES = ("index.html", "garde.js", "app.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "style.css", "sw.js", "manifest.json", "version.js", "icon-192.png", "icon-512.png")
OLD_FILES = ("index.html", "app.js", "db.js", "style.css", "sw.js", "manifest.json", "version.js")


def ok(n, c, e=""):
    global fails, total
    total += 1
    if not c: fails += 1
    print(("PASS " if c else "FAIL ") + n + (" | " + str(e)[:600] if not c else ""))


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "max-age=600")
        super().end_headers()
    def log_message(self, *a): pass


def serve(directory):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(directory)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d/" % srv.server_address[1]


def git_show(name):
    r = subprocess.run(["git", "-C", str(ROOT), "show", "%s:%s" % (OLD, name)], capture_output=True)
    if r.returncode: raise RuntimeError("git show %s:%s : %s" % (OLD, name, r.stderr.decode(errors="replace")))
    return r.stdout


PERSON = {"id": "00000000-0000-4000-8000-000000000001", "last_name": "Alpha", "first_name": "Un", "pickup_street": "1 rue Depart", "pickup_zip": "11111", "pickup_city": "Villedepart",
          "dest_place": "Lieu Cible", "dest_street": "2 rue Cible", "dest_zip": "22222", "dest_city": "Villecible", "phone": "", "usual_price_cents": 1250, "usual_km_m": 8500,
          "archived": False, "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z",
          "schedule": {"mode": "weekly", "weekdays": [1, 2, 3, 4, 5], "time_weekly": "09:00", "from": None, "to": None, "dates": [], "time_dates": None}}
DB_INFO = """new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result,v=d.version,s=[...d.objectStoreNames].sort();let idx=[];if(s.indexOf('rides')>=0)idx=[...d.transaction('rides').objectStore('rides').indexNames].sort();d.close();r({v,s,idx})}})"""


def ctx_new(p):
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="allow")
    cx.add_init_script("window.__off=0;")
    return b, cx


def load_page(cx, base, loads=None, errs=None):
    pg = cx.new_page()
    if loads is not None: pg.on("load", lambda pg_: loads.append(1))
    if errs is not None: pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(base); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready")
    pg.wait_for_function("!!navigator.serviceWorker.controller"); pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(400)
    return pg


def ask_update(pg):
    pg.locator('.nav button.t[data-t="bilan"]').tap(); pg.wait_for_timeout(250); pg.locator('[data-a="reglages"]').tap(); pg.wait_for_timeout(250)
    for essai in range(4):
        pg.locator('[data-a="checkupdate"]').tap()
        try:
            pg.wait_for_function("document.getElementById('update').hidden===false", timeout=9000); return True
        except Exception:
            pg.wait_for_timeout(500)
    return False


def journal(pg):
    return pg.evaluate("""new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const g=q.result.transaction('meta').objectStore('meta').get('update_log');g.onsuccess=()=>{q.result.close();r((g.result&&g.result.value)||[])}}})""")


with sync_playwright() as p:
    # ================= A. 0.2.1 → la version actuelle (changement de structure 2 → 5) avec une 2e page ouverte =================
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="agenda_030_"))
    for n in OLD_FILES: (tmp / n).write_bytes(git_show(n))
    for n in ("icon-192.png", "icon-512.png"): shutil.copy(ROOT / n, tmp / n)
    srv, B1 = serve(tmp)
    b, cx = ctx_new(p)
    loads1 = []; e1 = []; e2 = []
    ok(tag + " point de départ : les fichiers de la VRAIE version 0.2.1 (commit %s) tournent" % OLD, re.search(r"APP_VERSION\s*=\s*'([^']+)'", (tmp / "version.js").read_text(encoding="utf-8")).group(1) == "0.2.1")
    p1 = load_page(cx, B1, loads1, e1)
    p2 = load_page(cx, B1, None, e2)
    info0 = p1.evaluate(DB_INFO)
    p1.evaluate("""async(pp)=>{ await AG.putPerson(pp); await AG.putSetting('idle_sec',600) }""", PERSON)
    ok(tag + " version 0.2.1 : structure 2 (sans magasin de courses indexé par date), une personne et un réglage de masquage (10 minutes) enregistrés", info0["v"] == 2 and "rides" in info0["s"] and info0["idx"] == ["person_id"], info0)
    for n in NEW_FILES: shutil.copy(ROOT / n, tmp / n)                   # « publication » de la version actuelle (@CUR@, structure 5)
    ok(tag + T(" « publication » de la version actuelle : version.js = @CUR@"), re.search(r"APP_VERSION\s*=\s*'([^']+)'", (tmp / "version.js").read_text(encoding="utf-8")).group(1) == CUR)
    found = ask_update(p1)
    p1.wait_for_timeout(800)
    ok(tag + " dans l'appli installée (0.2.1) : « Nouvelle version disponible » apparaît, la page ne se recharge pas toute seule", found and p1.locator("#update").is_visible() and len(loads1) == 2 and p1.locator("#rg-version").inner_text() == "0.2.1", (found, len(loads1)))
    n_before = len(loads1)
    p1.evaluate("window.__marqueur=1")
    p1.locator('#update [data-a="applyupdate"]').tap()
    p1.wait_for_function("window.__marqueur===undefined", timeout=20000)
    p1.wait_for_function("window.__ag && window.__ag.ready"); p1.evaluate("window.__ag.ready"); p1.wait_for_timeout(1500)
    ok(tag + " « Mettre à jour » : la page se recharge UNE fois et ne reste pas figée (la base est prête, menu du bas présent)", len(loads1) - n_before == 1 and p1.locator(".nav button.t").count() == 4 and p1.locator("#fatal.on").count() == 0 and p1.evaluate("__ag.cur") == "aujourdhui", len(loads1) - n_before)
    ok(tag + " … le menu du bas répond tout de suite (toucher « Personnes »)", (p1.locator('.nav button.t[data-t="personnes"]').tap() or True) and (p1.wait_for_timeout(300) or True) and p1.evaluate("__ag.cur") == "personnes")
    p1.wait_for_timeout(5000)
    ok(tag + " … pas de boucle de rechargements (toujours un seul 5 s plus tard)", len(loads1) - n_before == 1, len(loads1) - n_before)
    p1.locator('.nav button.t[data-t="bilan"]').tap(); p1.wait_for_timeout(250); p1.locator('[data-a="reglages"]').tap(); p1.wait_for_timeout(500)
    ok(tag + T(" Réglages : version @CUR@ et structure n° 5"), p1.locator("#rg-version").inner_text() == CUR and p1.locator("#rg-schema").inner_text() == "5", (p1.locator("#rg-version").inner_text(), p1.locator("#rg-schema").inner_text()))
    info = p1.evaluate(DB_INFO)
    ok(tag + " la base est en structure 5 : magasins gardés, courses indexées par date ET par personne", info["v"] == 5 and info["s"] == ["fuel", "meta", "persons", "rides", "safety", "settings"] and info["idx"] == ["date", "person_id"], info)
    kept = p1.evaluate("""(async()=>({n:(await AG.allPersons()).length, id:(await AG.allPersons())[0].id, idle:await AG.getSetting('idle_sec'), rides:(await AG.allRides()).length}))()""")
    ok(tag + " personne et réglage de masquage (600) gardés, aucune course inventée", kept == {"n": 1, "id": PERSON["id"], "idle": 600, "rides": 0}, kept)
    p2.wait_for_timeout(300)
    ok(tag + " la 2e page, restée ouverte en 0.2.1, a lâché sa connexion (elle n'a PAS bloqué) et l'explique : « Agenda a été mis à jour dans une autre fenêtre »", p2.locator("#fatal.on").count() == 1 and "autre fenêtre" in p2.locator("#fatal-title").inner_text(), p2.locator("#fatal-title").inner_text())
    # ----- journal
    jl = journal(p1); texts = [x["e"] for x in jl]
    ok(tag + T(" journal : « Démarrage de la version @CUR@ », « Base ouverte (structure 5) »"), T("Démarrage de la version @CUR@") in texts and "Base ouverte (structure 5)" in texts, texts)
    ok(tag + " journal : « Structure des données mise à niveau : 2 → 5 » ; la version 0.2.1 n'avait pas de journal : « Version précédente non notée »", "Structure des données mise à niveau : 2 → 5" in texts and any(t.startswith("Version précédente non notée") for t in texts), texts)
    ok(tag + " journal : chaque évènement a une heure (AAAA-MM-JJTHH:MM:SS) et le numéro de version de l'appli qui l'a écrit", all(re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", x["t"]) and x["v"] for x in jl), jl[:2])
    li = p1.locator("#rg-log li")
    ok(tag + " Réglages : « Journal de mise à jour » affiche les évènements, le plus récent d'abord, avec heure (jj/mm hh:mm:ss) et version", li.count() == len(jl) and re.match(r"^\d\d/\d\d \d\d:\d\d:\d\d", li.first.locator("time").inner_text()) and li.first.locator(".v").inner_text() == CUR and p1.locator("#rg-log-empty").is_hidden(), (li.count(), len(jl)))
    ok(tag + " journal : aucun nom, adresse ni montant (rien de la personne « Alpha »)", not re.search(r"Alpha|Villedepart|rue Depart|1250", " ".join(texts) + p1.locator("#rg-log").inner_text()))
    p1.screenshot(path=SHOTS + "/maj030_journal_%dx%d_%s.png" % (W, H, SCHEME))
    ok(tag + T(" aucune erreur JavaScript (0.2.1 → @CUR@)"), not e1, e1)
    b.close(); srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)

    # ================= B. la version actuelle → la suivante (nouvelle structure 5, copie d'essai) : évènements du journal =================
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="agenda_031_"))
    for n in NEW_FILES: shutil.copy(ROOT / n, tmp / n)
    srv, B2 = serve(tmp)
    b, cx = ctx_new(p)
    loads = []; e3 = []
    q1 = load_page(cx, B2, loads, e3); q2 = load_page(cx, B2, None, None)
    q1.evaluate("""async(pp)=>{ await AG.putPerson(pp) }""", PERSON)
    dbjs = (tmp / "db.js").read_text(encoding="utf-8").replace("\r\n", "\n")
    marker = "db.createObjectStore('safety', { keyPath: 'key' });\n  } }\n];"
    assert dbjs.count(marker) == 1
    (tmp / "db.js").write_text(dbjs.replace(marker, "db.createObjectStore('safety', { keyPath: 'key' });\n  } },\n  { version: 6, up: function (db, tx) { db.createObjectStore('extra', { keyPath: 'id' }); } }\n];"), encoding="utf-8")
    fausse_version(tmp, NEXT)
    found = ask_update(q1); q1.wait_for_timeout(500)
    ok(tag + T(" @CUR@ → @NEXT@ : « Nouvelle version disponible » détectée"), found and q1.locator("#update").is_visible())
    n_before = len(loads)
    q1.evaluate("window.__marqueur=1")
    q1.locator('#update [data-a="applyupdate"]').tap()
    q1.wait_for_function("window.__marqueur===undefined", timeout=20000)
    q1.wait_for_function("window.__ag && window.__ag.ready"); q1.evaluate("window.__ag.ready"); q1.wait_for_timeout(1500)
    ok(tag + T(" mise à jour avec structure 6 et une 2e page @CUR@ ouverte : un seul rechargement, base prête, menu du bas présent, aucun message de blocage"), len(loads) - n_before == 1 and q1.locator(".nav button.t").count() == 4 and q1.locator("#fatal.on").count() == 0 and q1.evaluate("__ag.version") == NEXT, len(loads) - n_before)
    q1.locator('.nav button.t[data-t="bilan"]').tap(); q1.wait_for_timeout(250); q1.locator('[data-a="reglages"]').tap(); q1.wait_for_timeout(500)
    ok(tag + T(" Réglages : version @NEXT@, structure n° 6"), q1.locator("#rg-version").inner_text() == NEXT and q1.locator("#rg-schema").inner_text() == "6")
    q2.wait_for_timeout(300)
    ok(tag + T(" la 2e page (@CUR@) a lâché sa connexion et l'explique"), q2.locator("#fatal.on").count() == 1 and "autre fenêtre" in q2.locator("#fatal-title").inner_text())
    jl = journal(q1); texts = [x["e"] for x in jl]
    def pos(s): return next((i for i, t in enumerate(texts) if t.startswith(s)), -1)
    ok(tag + T(" journal (page @CUR@ qui lance la mise à jour) : « Réserve complète » vérifiée par le nouveau service worker, entre « Nouveau service worker actif » et « Rechargement de la page » ; puis « Écran affiché (menu prêt) », sans « Erreur » ni « Fichiers de versions différentes »"), 0 <= pos("Nouveau service worker actif") < pos("Réserve complète") < pos("Rechargement de la page") and "Écran affiché (menu prêt)" in texts[pos("Rechargement de la page"):] and pos("Erreur") < 0 and pos("Fichiers de versions différentes") < 0, texts)
    ok(tag + " journal : « Nouvelle version prête », « Bouton « Mettre à jour » touché », « Nouveau service worker actif », « Rechargement de la page » (écrits AVANT le rechargement)", all(pos(x) >= 0 for x in ["Nouvelle version prête", "Bouton « Mettre à jour » touché", "Nouveau service worker actif", "Rechargement de la page"]), texts)
    ok(tag + " journal : ces évènements sont dans l'ordre (prête < touché < actif < rechargement)", 0 <= pos("Nouvelle version prête") < pos("Bouton « Mettre à jour » touché") < pos("Nouveau service worker actif") < pos("Rechargement de la page"), texts)
    ok(tag + " journal : la 2e page a noté « Base fermée : une autre page demande une nouvelle structure » AVANT de lâcher sa connexion", pos("Base fermée : une autre page demande une nouvelle structure") >= 0, texts)
    ok(tag + T(" journal : après le rechargement, la nouvelle version note « Démarrage de la version @NEXT@ », la mise à niveau 5 → 6 et le changement de version @CUR@ → @NEXT@"), pos(T("Démarrage de la version @NEXT@")) > pos("Rechargement de la page") and pos("Structure des données mise à niveau : 5 → 6") >= 0 and pos(T("Version de l’appli passée de @CUR@ à @NEXT@")) >= 0, texts)
    # 20 au plus
    q1.evaluate("""AG.appendLog(Array.from({length:30},(_, i)=>({t:new Date().toISOString(),e:'essai '+i,v:'x'})))""")
    q1.wait_for_timeout(400)
    jl = journal(q1)
    ok(tag + " le journal garde les %d derniers évènements au plus (30 ajoutés d'un coup : les 20 derniers restent, du plus ancien « essai 10 » au plus récent « essai 29 »)" % 20, len(jl) == 20 and jl[0]["e"] == "essai 10" and jl[-1]["e"] == "essai 29", [x["e"] for x in jl][:3])
    q1.locator('.nav button.t[data-t="essence"]').tap(); q1.wait_for_timeout(250); q1.locator('.nav button.t[data-t="bilan"]').tap(); q1.wait_for_timeout(250); q1.locator('[data-a="reglages"]').tap(); q1.wait_for_timeout(500)
    ok(tag + " Réglages affiche bien 20 lignes (le plus récent en haut : « essai 29 »)", q1.locator("#rg-log li").count() == 20 and "essai 29" in q1.locator("#rg-log li").first.inner_text(), q1.locator("#rg-log li").count())
    ok(tag + T(" aucune erreur JavaScript (@CUR@ → @NEXT@)"), not e3, e3)
    b.close(); srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
print("TOTAL", total, "ECHECS", fails)
