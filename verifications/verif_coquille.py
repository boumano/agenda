"""Étape 1 d'Agenda (mis à jour : version 0.2.0, structure 2) : la coquille installable, sans aucune donnée de personne.
Vérifie : fichiers et contenu (aucune adresse internet, aucune donnée, numéro de version à un seul endroit), manifeste valide et icônes,
service worker enregistré, appli qui s'ouvre sans réseau, numéro de version affiché, structure IndexedDB et son numéro, mécanisme de migration,
refus d'ouvrir des données plus récentes (sans rien effacer), demande de stockage persistant (une seule fois) et son état, mise à jour proposée
(jamais rechargée toute seule), œil et masquage automatique (rien de lisible, y compris après 2 minutes simulées), barre du bas à 4 boutons
(zones de 44 px minimum), couleurs de la maquette, aucune erreur JavaScript, aucune requête hors de l'appli.
W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light. Durée : environ 1 minute.
Aucun navigateur n'utilise Internet : un petit serveur local (127.0.0.1) sert les fichiers."""
import os, re, json, shutil, struct, tempfile, threading, pathlib, http.server, functools
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
import sys; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _outils import fausse_version
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
fails = 0; total = 0


def ok(n, c, e=""):
    global fails, total
    total += 1
    if not c: fails += 1
    print(("PASS " if c else "FAIL ") + n + (" | " + str(e)[:400] if not c else ""))


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "max-age=600")      # comme GitHub Pages
        super().end_headers()
    def log_message(self, *a): pass


def serve(directory):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(directory)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d/" % srv.server_address[1]


def version_in_file(root):
    return re.search(r"APP_VERSION\s*=\s*'([^']+)'", (pathlib.Path(root) / "version.js").read_text(encoding="utf-8")).group(1)


# ================= 1. fichiers (sans navigateur) =================
EXPECTED = {"garde.js", "app.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "icon-192.png", "icon-512.png", "icon.svg", "index.html", "manifest.json", "style.css", "sw.js", "version.js", "NOTES_AGENDA.md", ".gitignore"}
present = {p.name for p in ROOT.iterdir() if p.is_file()}
ok(tag + " fichiers : ceux de l'étape 1, rien d'autre (ni maquette, ni notes de la maquette, ni base de données)", present <= EXPECTED and {"index.html", "garde.js", "app.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "style.css", "sw.js", "manifest.json", "version.js", "icon-192.png", "icon-512.png"} <= present, sorted(present ^ EXPECTED))
code = {n: (ROOT / n).read_text(encoding="utf-8") for n in ("index.html", "garde.js", "app.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "style.css", "sw.js", "manifest.json", "version.js", "icon.svg")}
ext = [(n, u) for n, t in code.items() for u in re.findall(r"https?://[^\s\"')<>]+", t) if u != "http://www.w3.org/2000/svg"]
ok(tag + " aucune adresse internet dans les fichiers (ni police, ni script, ni image externes)", not ext, ext)
ok(tag + " aucun outil de construction ni bibliothèque : pas de package.json, pas de node_modules", not (ROOT / "package.json").exists() and not (ROOT / "node_modules").exists())
ok(tag + " aucun import, require, fetch vers l'extérieur dans app.js, db.js et rides.js (JavaScript simple)", not re.search(r"\bimport\s|require\(|importScripts\(['\"]https?", code["app.js"] + code["db.js"] + code["rides.js"]))
V = version_in_file(ROOT)
STAMP = re.compile(r'^.*(AG_STAMPS|--ag-version|name="ag-version").*$', re.M)          # les tampons recopient le numéro (sync_version.py) : ce n'est pas une 2e source
others = [n for n in ("index.html", "garde.js", "app.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "style.css", "sw.js", "manifest.json", "icon.svg") if re.search(r"\b" + re.escape(V) + r"\b", STAMP.sub("", code[n]))]
ok(tag + " numéro de version (%s) écrit à UN seul endroit : version.js (hors tampons recopiés par sync_version.py)" % V, not others and code["version.js"].count(V) == 1, others)
names = []
mq = ROOT.parent / "chauffeur" / "maquette.html"
if mq.exists():
    t = mq.read_text(encoding="utf-8")
    names = sorted(set(re.findall(r"\bnom:'([^']+)'", t) + re.findall(r"\bpre:'([^']+)'", t)))
alltext = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in ROOT.iterdir() if p.is_file() and p.suffix in (".js", ".html", ".css", ".json", ".md", ".svg")) + "\n" + "\n".join(p.read_text(encoding="utf-8") for p in HERE.glob("*.py") if p.name != pathlib.Path(__file__).name)
hit = [n for n in names if re.search(r"\b" + re.escape(n) + r"\b", alltext)]
ok(tag + " aucun nom de la maquette (%d noms comparés, lus dans la maquette au moment du test) dans les fichiers" % len(names), not hit and (names or True), hit)
ok(tag + " aucun numéro de téléphone ni adresse en dur (téléphones à 10 chiffres, « rue », « avenue »)", not re.search(r"\b0[1-9](?:[ .]?\d{2}){4}\b|\b(?:rue|avenue|impasse|chemin) [A-Za-zÀ-ÿ]", "\n".join(v for k, v in code.items() if k != "mots.js")), "")
man = json.loads(code["manifest.json"])
ok(tag + " manifeste : nom et nom court « Agenda », démarrage ./, affichage autonome, couleurs, deux icônes", man.get("name") == "Agenda" and man.get("short_name") == "Agenda" and man.get("start_url") == "./" and man.get("display") == "standalone" and re.fullmatch(r"#[0-9A-Fa-f]{6}", man.get("theme_color", "")) and re.fullmatch(r"#[0-9A-Fa-f]{6}", man.get("background_color", "")) and [i["sizes"] for i in man.get("icons", [])] == ["192x192", "512x512"], man)


def png_size(p):
    b = pathlib.Path(p).read_bytes(); return (b[:8] == b"\x89PNG\r\n\x1a\n") and struct.unpack(">II", b[16:24])
ok(tag + " icônes : deux vrais PNG de 192 et 512 px", png_size(ROOT / "icon-192.png") == (192, 192) and png_size(ROOT / "icon-512.png") == (512, 512))
css = code["style.css"]
pal = {"--page": ("#F4F6F9", "#0F1217"), "--card": ("#FFFFFF", "#1A1F27"), "--accent": ("#1A69AE", "#4DA3E8"), "--band": ("#D6E4F2", "#123A5E"), "--text": ("#1B2330", "#F2F4F8")}
ok(tag + " couleurs : mêmes valeurs que la maquette, thème clair et sombre automatiques (prefers-color-scheme)", all(c in css for v in pal.values() for c in v) and "prefers-color-scheme:dark" in css.replace(" ", ""))
ok(tag + " mode clair / sombre : couleur du navigateur déclarée pour les deux", len(re.findall(r'name="theme-color"', code["index.html"])) == 2)

# ================= 2. dans le navigateur =================
INIT_TIME = "window.__off=0; window.__freeze=false; (function(){ var n=Date.now.bind(Date); Date.now=function(){ return n()+window.__off; }; var si=window.setInterval.bind(window); window.setInterval=function(f,t){ return si(function(){ if(!window.__freeze) f(); },t); }; })();"


def init_script(grant):
    return INIT_TIME + """
(function(){
  window.__pc=0; var G=%s;
  if(navigator.storage){
    navigator.storage.persist=function(){ window.__pc++; if(G) localStorage.setItem('mock_p','1'); return Promise.resolve(G); };
    navigator.storage.persisted=function(){ return Promise.resolve(localStorage.getItem('mock_p')==='1'); };
  }
})();""" % ("true" if grant else "false")


def new_context(p, scheme, grant=True, w=W, h=H, offline_ok=True):
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": w, "height": h}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=scheme, service_workers="allow")
    cx.add_init_script(init_script(grant))
    return b, cx


with sync_playwright() as p:
    srv, BASE = serve(ROOT)
    b, cx = new_context(p, SCHEME)
    pg = cx.new_page(); errs = []; reqs = []
    pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
    pg.on("console", lambda m: errs.append("console " + m.text) if m.type == "error" else None)
    cx.on("request", lambda r: reqs.append(r.url))
    pg.goto(BASE); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(300)
    w = lambda: pg.wait_for_timeout(250)
    tap = lambda sel: (pg.locator(sel).first.tap(), w())
    goto = lambda t: tap('.nav button.t[data-t="%s"]' % t)
    cur = lambda: pg.evaluate("__ag.cur")
    masked = lambda: pg.evaluate("__ag.masked")
    jump = lambda ms: pg.evaluate("window.__off += %d" % ms)

    # --- premier lancement : stockage persistant demandé une fois, bannière de mise à jour absente
    pc1 = pg.evaluate("window.__pc")
    ok(tag + " premier lancement : le stockage persistant est demandé exactement une fois", pc1 == 1, pc1)
    ok(tag + " premier lancement : pas de message « Nouvelle version disponible »", pg.locator("#update").is_hidden())
    pg.wait_for_function("!!navigator.serviceWorker.controller")
    reg = pg.evaluate("navigator.serviceWorker.getRegistration().then(r=>({scope:r.scope,state:r.active.state,url:r.active.scriptURL}))")
    ok(tag + " service worker enregistré et actif (sw.js, portée = l'appli)", reg["state"] == "activated" and reg["url"] == BASE + "sw.js" and reg["scope"] == BASE, reg)
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(400)
    ok(tag + " après rechargement : l'appli est contrôlée par le service worker", pg.evaluate("!!navigator.serviceWorker.controller"))
    ok(tag + " 2e lancement : le stockage persistant n'est PAS redemandé", pg.evaluate("window.__pc") == 0, pg.evaluate("window.__pc"))
    ok(tag + " page : titre « Agenda », manifeste relié, deux couleurs de thème", pg.title() == "Agenda" and pg.evaluate("document.querySelector('link[rel=manifest]').getAttribute('href')") == "manifest.json")
    mj = pg.evaluate("fetch('manifest.json').then(async r=>({ok:r.ok,ct:r.headers.get('content-type'),j:await r.json()}))")
    ok(tag + " manifeste servi (200, type JSON) et lisible par la page", mj["ok"] and "json" in (mj["ct"] or "") and mj["j"]["name"] == "Agenda", mj)
    icons = pg.evaluate("Promise.all(['icon-192.png','icon-512.png'].map(u=>new Promise(r=>{const i=new Image();i.onload=()=>r([u,i.naturalWidth]);i.onerror=()=>r([u,0]);i.src=u})))")
    ok(tag + " icônes servies et affichables (192 et 512)", icons == [["icon-192.png", 192], ["icon-512.png", 512]], icons)

    # --- IndexedDB
    dbinfo = pg.evaluate("""async()=>{const d=await __ag.openDatabase(__ag.dbName,[{version:__ag.schemaTarget,up(){}}]);
      const o={v:d.version,stores:[...d.objectStoreNames].sort(),sv:await __ag.dbGet(d,'meta','schema_version'),created:await __ag.dbGet(d,'meta','created_at'),asked:await __ag.dbGet(d,'meta','persist_asked')};d.close();return o}""")
    ok(tag + " IndexedDB « agenda » : structure n° 5, magasins « fuel », « meta », « persons », « rides », « safety » et « settings », numéro noté dans la base", dbinfo["v"] == 5 and dbinfo["stores"] == ["fuel", "meta", "persons", "rides", "safety", "settings"] and dbinfo["sv"] == 5 and dbinfo["created"] and dbinfo["asked"], dbinfo)
    mig = pg.evaluate("""async()=>{ const name='agenda-essai-migration';
      const del=()=>new Promise(r=>{const q=indexedDB.deleteDatabase(name);q.onsuccess=q.onerror=q.onblocked=()=>r()}); await del();
      const m1={version:1,up:(db,tx)=>{db.createObjectStore('meta',{keyPath:'key'});db.createObjectStore('a',{keyPath:'k'})}};
      const m2={version:2,up:(db,tx)=>{db.createObjectStore('b',{keyPath:'k'})}};
      let d=await __ag.openDatabase(name,[m1]); const s1=[...d.objectStoreNames].sort(), v1=d.version;
      await new Promise(r=>{const t=d.transaction('a','readwrite');t.objectStore('a').put({k:'ancien',value:42});t.oncomplete=r}); d.close();
      d=await __ag.openDatabase(name,[m1,m2]); const s2=[...d.objectStoreNames].sort(), v2=d.version;
      const old=await new Promise(r=>{const q=d.transaction('a').objectStore('a').get('ancien');q.onsuccess=()=>r(q.result)});
      const sv=await __ag.dbGet(d,'meta','schema_version'); d.close();
      let newer=null; try{ await __ag.openDatabase(name,[m1]) }catch(e){ newer=e.code }
      await del(); return {s1,v1,s2,v2,old,sv,newer} }""")
    ok(tag + " migration : de la structure 1 à 2, le nouveau magasin apparaît, la donnée ancienne est gardée, le numéro passe à 2", mig["s1"] == ["a", "meta"] and mig["v1"] == 1 and mig["s2"] == ["a", "b", "meta"] and mig["v2"] == 2 and mig["old"] and mig["old"]["value"] == 42 and mig["sv"] == 2, mig)
    ok(tag + " une base plus récente que l'appli est refusée proprement (code « newer »), jamais écrasée", mig["newer"] == "newer", mig["newer"])

    # --- écrans : seulement leur titre
    for t, title in [("aujourdhui", "Aujourd’hui"), ("personnes", "Personnes"), ("bilan", "Bilan"), ("essence", "Essence")]:
        goto(t)
        txt = pg.locator(".screen.on").inner_text().strip()
        exp = "Bilan\nRéglages" if t == "bilan" else title
        if t == "aujourdhui":
            ok(tag + " page « Aujourd’hui » : titre, jour, flèches, « Aucune course prévue ce jour. », « Ajouter une course »", cur() == t and pg.locator(".screen.on h1").text_content() == title and "Aucune course prévue ce jour." in txt and "Ajouter une course" in txt and pg.locator('[data-a="day"]').count() == 2, repr(txt))
        elif t == "bilan":
            pg.wait_for_timeout(300)
            ok(tag + " page « Bilan » : titre, choix « Totaux » / « Jour par jour », mois, ligne « Réglages »", cur() == t and pg.locator(".screen.on h1").inner_text() == title and [x.strip() for x in pg.locator('[data-a="bview"]').all_inner_texts()] == ["Totaux", "Jour par jour"] and pg.locator('[data-a="reglages"]').count() == 1 and pg.locator('[data-a="bmonth"]').count() == 2, repr(txt))
        elif t == "personnes":
            ok(tag + " page « Personnes » : titre, recherche, liste vide (« Aucune personne pour l’instant »), « Nouvelle personne »", cur() == t and pg.locator(".screen.on h1").inner_text() == title and "Aucune personne pour l’instant" in txt and "Nouvelle personne" in txt and pg.locator("#q").count() == 1, repr(txt))
        else:
            pg.wait_for_timeout(300)
            ok(tag + " page « Essence » : titre, mois, calendrier, « Total du mois » à zéro, « Aucun plein noté ce mois-ci. »", cur() == t and pg.locator(".screen.on h1").inner_text() == title and "Aucun plein noté ce mois-ci." in pg.locator(".screen.on").inner_text() and pg.locator("#fu-count").inner_text() == "0", repr(txt))
    pg.screenshot(path=SHOTS + "/coquille_essence_%dx%d_%s.png" % (W, H, SCHEME))

    # --- barre du bas : 4 boutons à 44 px minimum
    nav = pg.evaluate("""()=>{const app=document.getElementById('app').getBoundingClientRect();return [...document.querySelectorAll('.nav button.t')].map(b=>{const r=b.getBoundingClientRect(),rg=document.createRange();rg.selectNodeContents(b);const t=rg.getBoundingClientRect();
      return {lbl:b.textContent.trim(),use:b.querySelector('use').getAttribute('href'),w:r.width,h:r.height,l:r.left,r:r.right,b:r.bottom,clip:b.scrollWidth>b.clientWidth+.5,tin:t.left>=r.left-.5&&t.right<=r.right+.5,inapp:r.left>=app.left-.5&&r.right<=app.right+.5&&r.bottom<=innerHeight+.5}})}""")
    ok(tag + " barre du bas : Aujourd’hui, Personnes, Bilan, Essence, avec les icônes de la maquette", [x["lbl"] for x in nav] == ["Aujourd’hui", "Personnes", "Bilan", "Essence"] and [x["use"] for x in nav] == ["#i-calcheck", "#i-users", "#i-chart", "#i-fuel"], nav)
    ok(tag + " 4 boutons : au moins 44 px de large et de haut, même largeur, mots entiers, dans l'écran", all(x["w"] >= 44 and x["h"] >= 44 and not x["clip"] and x["tin"] and x["inapp"] for x in nav) and max(x["w"] for x in nav) - min(x["w"] for x in nav) < 1, nav)
    tools = pg.evaluate("""()=>[...document.querySelectorAll('.screen .tool')].map(e=>{const r=e.getBoundingClientRect();return [r.width,r.height,e.closest('.screen').id]}).filter(x=>x[0]>0)""")
    ok(tag + " œil : un par écran, 44 x 44 px minimum (44 x 28 sur Aujourd’hui, comme la maquette), étiquette « Masquer l’écran »", pg.locator('.screen [data-a="hide"]').count() == 5 and pg.locator('[data-a="lock"]').count() == 0 and all(x[0] >= 43.5 and x[1] >= (27.5 if x[2] == "s-aujourdhui" else 43.5) for x in tools) and pg.locator('[aria-label="Masquer l’écran"]').count() == 5, tools)
    ok(tag + " aucun cadenas, aucun champ de code dans la page", pg.locator("#v-code, #v-form, [data-a=lock]").count() == 0 and "cadenas" not in code["index.html"].lower() and "code" not in pg.evaluate("document.body.innerText").lower())
    pal_now = pg.evaluate("""()=>{const s=getComputedStyle(document.documentElement);return ['--page','--card','--accent','--band','--text'].map(k=>s.getPropertyValue(k).trim().toUpperCase())}""")
    expc = [pal[k][1 if SCHEME == "dark" else 0] for k in ("--page", "--card", "--accent", "--band", "--text")]
    ok(tag + " couleurs du thème %s identiques à la maquette" % SCHEME, pal_now == expc, (pal_now, expc))

    # --- Réglages (depuis le Bilan)
    goto("bilan"); tap('[data-a="reglages"]')
    ok(tag + " Bilan → « Réglages » : l'écran s'ouvre et l'onglet Bilan reste allumé", cur() == "reglages" and pg.locator('.nav button.t[aria-current="page"]').inner_text().strip() == "Bilan")
    ok(tag + " Réglages : numéro de version affiché = celui de version.js (%s)" % V, pg.locator("#rg-version").inner_text() == V)
    ok(tag + " Réglages : structure des données n° 5", pg.locator("#rg-schema").inner_text() == "5")
    ok(tag + " Réglages : stockage persistant « accordé » (réponse simulée de Chrome)", pg.locator("#rg-persist").inner_text() == "accordé" and pg.locator("#rg-persist-btn").is_hidden(), pg.locator("#rg-persist").inner_text())
    ok(tag + " Réglages : masquage automatique 2 minutes par défaut, quatre choix", pg.locator('[data-a="idle"]').count() == 4 and pg.locator('[data-a="idle"][data-n="120"][aria-pressed="true"]').count() == 1 and [x.strip() for x in pg.locator('[data-a="idle"]').all_inner_texts()] == ["Jamais", "1 minute", "2 minutes", "10 minutes"])
    pg.screenshot(path=SHOTS + "/coquille_reglages_%dx%d_%s.png" % (W, H, SCHEME))
    z = pg.evaluate("""()=>{const app=document.getElementById('app').getBoundingClientRect(),out=[];document.querySelectorAll('.screen.on button').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width)return;if(r.height<43.5||r.width<43.5)out.push('PETIT '+e.textContent.trim()+' '+r.width.toFixed(0)+'x'+r.height.toFixed(0));if(r.right>app.right+.5||r.left<app.left-.5)out.push('DEBORDE '+e.textContent.trim())});const c=document.querySelector('.screen.on .content');if(c.scrollWidth>c.clientWidth+1)out.push('LARGEUR');return out}""")
    ok(tag + " Réglages : zones de 44 px, rien qui déborde ni défile en largeur", not z, z)
    pg.evaluate("history.back()"); w()
    ok(tag + " touche Retour d'Android : de Réglages vers le Bilan, puis vers Aujourd'hui", cur() == "bilan")
    pg.evaluate("history.back()"); w()
    ok(tag + " … puis vers Aujourd'hui", cur() == "aujourdhui")
    goto("bilan"); tap('[data-a="reglages"]'); tap('[data-a="back"]')
    ok(tag + " bouton « Retour » de Réglages : revient au Bilan", cur() == "bilan")

    # --- œil
    goto("personnes"); tap('.screen.on [data-a="hide"]')
    vt = pg.evaluate("document.getElementById('veil').innerText.trim()")
    pts = pg.evaluate("""()=>{let n=0,c=0;for(let x=10;x<innerWidth;x+=Math.floor(innerWidth/6))for(let y=10;y<innerHeight;y+=Math.floor(innerHeight/8)){n++;const e=document.elementFromPoint(x,y);if(e&&e.closest('#veil'))c++}return [n,c]}""")
    ok(tag + " œil : écran neutre « Agenda » seul, plein écran (%d/%d points couverts), pages et barre du bas inertes" % tuple(reversed(pts)), masked() and vt == "Agenda" and pts[0] == pts[1] and pg.evaluate("document.getElementById('views').inert&&document.querySelector('.nav').inert&&document.querySelector('.nav').getAttribute('aria-hidden')==='true'"), (vt, pts))
    pg.screenshot(path=SHOTS + "/coquille_masque_%dx%d_%s.png" % (W, H, SCHEME))
    pg.locator("#veil").tap(); w()
    ok(tag + " un toucher rouvre, sur la même page (Personnes)", not masked() and cur() == "personnes" and pg.evaluate("!document.getElementById('views').inert"))

    # --- masquage automatique (heure simulée)
    pg.wait_for_timeout(300)
    jump(115000); pg.wait_for_timeout(1500)
    ok(tag + " 1 min 55 s simulées sans toucher : pas encore masqué", not masked())
    jump(8000); pg.wait_for_timeout(1700)
    vt = pg.evaluate("document.getElementById('veil').innerText.trim()")
    ok(tag + " 2 minutes simulées sans toucher : masqué tout seul, rien de lisible (« Agenda » seul, pages inertes)", masked() and vt == "Agenda" and pg.evaluate("document.getElementById('views').inert"), vt)
    bar = pg.evaluate("(()=>{const r=document.querySelector('.nav button.t[data-t=essence]').getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]})()")
    pg.touchscreen.tap(bar[0], bar[1]); w()
    ok(tag + " écran masqué : un toucher à l'endroit de la barre du bas rouvre l'écran mais ne change pas de page", (not masked()) and cur() == "personnes", (masked(), cur()))
    pg.evaluate("window.__freeze=true"); jump(130000)
    pg.touchscreen.tap(bar[0], bar[1]); w()
    ok(tag + " délai dépassé (minuterie arrêtée) : le premier toucher masque et n'agit pas dessous (reste sur Personnes)", masked() and cur() == "personnes", (masked(), cur()))
    pg.evaluate("window.__freeze=false")
    pg.locator("#veil").tap(); w()
    goto("bilan"); tap('[data-a="reglages"]')
    jump(125000); pg.wait_for_timeout(1700)
    ok(tag + " 2 minutes simulées sur la page Réglages : masqué aussi (version et stockage illisibles)", masked() and "Agenda" == pg.evaluate("document.getElementById('veil').innerText.trim()"))
    pg.locator("#veil").tap(); w()
    ok(tag + " rouvert sur Réglages, même page", not masked() and cur() == "reglages")
    # réglages : 1 minute, 10 minutes, jamais
    tap('[data-a="idle"][data-n="60"]'); jump(55000); pg.wait_for_timeout(1500)
    a = masked(); jump(8000); pg.wait_for_timeout(1700)
    ok(tag + " réglage 1 minute : pas masqué à 55 s, masqué après 1 min", (not a) and masked(), (a, masked()))
    pg.locator("#veil").tap(); w()
    tap('[data-a="idle"][data-n="600"]'); jump(595000); pg.wait_for_timeout(1500)
    a = masked(); jump(8000); pg.wait_for_timeout(1700)
    ok(tag + " réglage 10 minutes : pas masqué à 9 min 55 s, masqué après 10 min", (not a) and masked(), (a, masked()))
    pg.locator("#veil").tap(); w()
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(300)
    ok(tag + " le réglage (10 minutes) est gardé après fermeture et réouverture", pg.evaluate("__ag.idle") == 600)
    goto("bilan"); tap('[data-a="reglages"]'); tap('[data-a="idle"][data-n="0"]'); jump(3 * 3600 * 1000); pg.wait_for_timeout(1700)
    ok(tag + " réglage « Jamais » : pas de masquage, même après 3 heures simulées", not masked())
    tap('[data-a="idle"][data-n="120"]')
    jump(-30000); pg.wait_for_timeout(1700)
    ok(tag + " horloge reculée de 30 s : masqué par prudence", masked())
    pg.locator("#veil").tap(); w(); goto("personnes")
    pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true}); document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(200)
    ok(tag + " appli passée en arrière-plan : écran neutre tout de suite", masked())
    pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false}); document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(200)
    pg.locator("#veil").tap(); w()
    pg.evaluate("window.dispatchEvent(new Event('pagehide'))"); pg.wait_for_timeout(200)
    ok(tag + " « pagehide » (page quittée) : écran neutre tout de suite", masked())
    pg.locator("#veil").tap(); w()

    # --- hors connexion
    caches = pg.evaluate("caches.keys().then(async ks=>({ks, n: ks.length? (await (await caches.open(ks[0])).keys()).length : 0}))")
    ok(tag + " réserve du service worker « agenda-%s » : 14 fichiers gardés" % V, caches["ks"] == ["agenda-" + V] and caches["n"] == 14, caches)
    cx.set_offline(True)
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready", timeout=15000); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(300)
    ok(tag + " MODE AVION : l'appli s'ouvre (titre « Aujourd’hui », barre du bas)", pg.locator("#s-aujourdhui.on h1").inner_text() == "Aujourd’hui" and pg.locator(".nav button.t").count() == 4)
    goto("bilan"); tap('[data-a="reglages"]')
    ok(tag + " MODE AVION : Réglages, version et stockage s'affichent", pg.locator("#rg-version").inner_text() == V and pg.locator("#rg-persist").inner_text() == "accordé")
    page2 = cx.new_page(); page2.goto(BASE + "index.html"); page2.wait_for_function("window.__ag && window.__ag.ready", timeout=15000)
    ok(tag + " MODE AVION : une nouvelle fenêtre (index.html) s'ouvre aussi", page2.title() == "Agenda" and page2.locator(".nav button.t").count() == 4)
    page2.close()
    cx.set_offline(False)

    ok(tag + " aucune erreur JavaScript ni message d'erreur dans la console", not errs, errs)
    outside = [u for u in reqs if not u.startswith(BASE) and not u.startswith("data:") and not u.startswith("blob:")]
    ok(tag + " aucune requête hors de l'appli (%d requêtes, toutes vers le serveur local)" % len(reqs), not outside, outside)
    b.close()

    # --- stockage persistant refusé
    b2, cx2 = new_context(p, SCHEME, grant=False)
    pgx = cx2.new_page(); pgx.goto(BASE); pgx.wait_for_function("window.__ag && window.__ag.ready"); pgx.evaluate("window.__ag.ready"); pgx.wait_for_timeout(300)
    pgx.locator('.nav button.t[data-t="bilan"]').tap(); pgx.wait_for_timeout(250); pgx.locator('[data-a="reglages"]').tap(); pgx.wait_for_timeout(250)
    ok(tag + " stockage persistant refusé par Chrome : affiché « non accordé » avec le bouton « Redemander à Chrome »", pgx.locator("#rg-persist").inner_text() == "non accordé" and pgx.locator("#rg-persist-btn").is_visible() and pgx.evaluate("window.__pc") == 1)
    pgx.locator("#rg-persist-btn").tap(); pgx.wait_for_timeout(300)
    ok(tag + " « Redemander » : Chrome est interrogé de nouveau (2e demande)", pgx.evaluate("window.__pc") == 2)
    b2.close()

    # --- données plus récentes que l'appli : message, rien d'effacé
    b3, cx3 = new_context(p, SCHEME)
    pn = cx3.new_page(); pn.goto(BASE + "manifest.json")
    pn.evaluate("""new Promise(r=>{const q=indexedDB.open('agenda',9);q.onupgradeneeded=()=>{const d=q.result;d.createObjectStore('meta',{keyPath:'key'});d.createObjectStore('futur',{keyPath:'k'})};
      q.onsuccess=()=>{const t=q.result.transaction('futur','readwrite');t.objectStore('futur').put({k:'a',value:'précieux'});t.oncomplete=()=>{q.result.close();r()}}})""")
    pn.goto(BASE); pn.wait_for_timeout(800)
    ok(tag + " base d'une version plus récente : message « Données plus récentes que l’appli » affiché", pn.locator("#fatal.on").count() == 1 and "plus récentes" in pn.locator("#fatal-title").inner_text() + pn.locator("#fatal-text").inner_text() and "Rien n’a été effacé" in pn.locator("#fatal-text").inner_text())
    left = pn.evaluate("""new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result,v=d.version,s=[...d.objectStoreNames];const g=d.transaction('futur').objectStore('futur').get('a');g.onsuccess=()=>{d.close();r({v,s,val:g.result&&g.result.value})}}})""")
    ok(tag + " … et rien n'a été effacé ni modifié (base toujours en version 9, donnée « précieux » intacte)", left == {"v": 9, "s": ["futur", "meta"], "val": "précieux"}, left)
    b3.close()
    srv.shutdown()

    # --- mise à jour proposée, jamais imposée
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="agenda_maj_"))
    for n in ("index.html", "garde.js", "app.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "style.css", "sw.js", "manifest.json", "version.js", "icon-192.png", "icon-512.png"): shutil.copy(ROOT / n, tmp / n)
    srv2, B2 = serve(tmp)
    b4, cx4 = new_context(p, SCHEME)
    pu = cx4.new_page(); uerrs = []
    pu.on("pageerror", lambda e: uerrs.append(str(e)))
    pu.goto(B2); pu.wait_for_function("window.__ag && window.__ag.ready"); pu.evaluate("window.__ag.ready")
    pu.wait_for_function("!!navigator.serviceWorker.controller"); pu.reload(); pu.wait_for_function("window.__ag && window.__ag.ready"); pu.wait_for_timeout(400)
    pu.evaluate("window.__marqueur=1")
    pu.locator('.nav button.t[data-t="bilan"]').tap(); pu.wait_for_timeout(250); pu.locator('[data-a="reglages"]').tap(); pu.wait_for_timeout(250)
    fausse_version(tmp, "9.9.9")        # « publication » d'une nouvelle version
    pu.locator('[data-a="checkupdate"]').tap()
    try:
        pu.wait_for_function("document.getElementById('update').hidden===false", timeout=30000)
    except Exception:
        pass
    pu.wait_for_timeout(2500)
    ok(tag + " nouvelle version publiée : le message « Nouvelle version disponible » avec le bouton « Mettre à jour » s'affiche", pu.locator("#update").is_visible() and "Nouvelle version disponible" in pu.locator("#update").inner_text() and pu.locator('#update [data-a="applyupdate"]').inner_text() == "Mettre à jour")
    ok(tag + " … aucun message contradictoire « Cette version est la plus récente » en même temps", "plus récente" not in (pu.locator("#toast").inner_text() if pu.locator("#toast").is_visible() else ""))
    ok(tag + " … la page n'a PAS été rechargée toute seule (la saisie en cours serait gardée) et tourne toujours en %s" % V, pu.evaluate("window.__marqueur") == 1 and pu.locator("#rg-version").inner_text() == V and "nouvelle version" in pu.locator("#rg-update-txt").inner_text().lower())
    pu.screenshot(path=SHOTS + "/coquille_maj_%dx%d_%s.png" % (W, H, SCHEME))
    pu.locator('#update [data-a="applyupdate"]').tap()
    try:
        pu.wait_for_function("window.__marqueur===undefined", timeout=15000)
    except Exception:
        pass
    pu.wait_for_function("window.__ag && window.__ag.ready"); pu.evaluate("window.__ag.ready"); pu.wait_for_timeout(500)
    pu.locator('.nav button.t[data-t="bilan"]').tap(); pu.wait_for_timeout(250); pu.locator('[data-a="reglages"]').tap(); pu.wait_for_timeout(250)
    ks = pu.evaluate("caches.keys()")
    ok(tag + " « Mettre à jour » : l'appli se recharge et affiche la version 9.9.9, le message a disparu, l'ancienne réserve est effacée", pu.locator("#rg-version").inner_text() == "9.9.9" and pu.locator("#update").is_hidden() and ks == ["agenda-9.9.9"], (pu.locator("#rg-version").inner_text(), ks))
    ok(tag + " les données restent après la mise à jour (même base, numéro de structure 5)", pu.locator("#rg-schema").inner_text() == "5")
    ok(tag + " aucune erreur JavaScript pendant la mise à jour", not uerrs, uerrs)
    b4.close(); srv2.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
print("TOTAL", total, "ECHECS", fails)
