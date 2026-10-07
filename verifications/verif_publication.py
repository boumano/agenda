"""À lancer APRÈS la publication sur GitHub Pages : vérifie que l'adresse répond et que les bons fichiers sont servis.
Usage :  python verif_publication.py https://boumano.github.io/agenda/
Aucune bibliothèque à installer. Ne lit et n'envoie aucune donnée : il demande seulement les fichiers de l'appli."""
import sys, re, json, pathlib, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
base = (sys.argv[1] if len(sys.argv) > 1 else "https://boumano.github.io/agenda/").rstrip("/") + "/"
fails = 0; total = 0


def ok(n, c, e=""):
    global fails, total
    total += 1
    if not c: fails += 1
    print(("PASS " if c else "FAIL ") + n + (" | " + str(e)[:300] if not c else ""))


def get(path):
    try:
        with urllib.request.urlopen(base + path, timeout=20) as r:
            return r.status, r.headers.get("content-type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, "", b""
    except Exception as e:
        return 0, "", str(e).encode()


ok("l'adresse est en https", base.startswith("https://"), base)
s, ct, body = get("")
ok("la page d'accueil répond (200) et c'est « Agenda »", s == 200 and b"<title>Agenda</title>" in body, (s, body[:80]))
s, ct, body = get("manifest.json")
j = {}
try: j = json.loads(body)
except Exception: pass
ok("manifest.json : servi (200, type JSON) et valide (nom « Agenda », démarrage ./, affichage autonome)", s == 200 and "json" in ct and j.get("name") == "Agenda" and j.get("start_url") == "./" and j.get("display") == "standalone", (s, ct, j))
for ic, size in (("icon-192.png", 192), ("icon-512.png", 512)):
    s, ct, body = get(ic)
    ok("%s : servi (200, image PNG)" % ic, s == 200 and body[:8] == b"\x89PNG\r\n\x1a\n" and "png" in ct, (s, ct))
s, ct, body = get("sw.js")
ok("sw.js : servi (200, JavaScript)", s == 200 and "javascript" in ct and b"importScripts" in body, (s, ct))
local = re.search(r"APP_VERSION\s*=\s*'([^']+)'", (ROOT / "version.js").read_text(encoding="utf-8")).group(1)
s, ct, body = get("version.js")
online = re.search(rb"APP_VERSION\s*=\s*'([^']+)'", body)
ok("version.js en ligne = version du dossier (%s)" % local, s == 200 and online and online.group(1).decode() == local, (s, online and online.group(1)))
for f in ("app.js", "style.css"):
    s, ct, body = get(f)
    ok("%s : servi (200)" % f, s == 200 and len(body) > 500, (s, len(body)))
s, ct, body = get("maquette.html")
ok("aucune maquette ni donnée en ligne (maquette.html introuvable : 404)", s == 404, s)
print("TOTAL", total, "ECHECS", fails)
