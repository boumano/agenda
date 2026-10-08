"""Recopie le numéro de version de version.js (l'unique source) dans les « tampons » de chaque fichier :
première ligne des fichiers JavaScript (AG_STAMPS), variable CSS --ag-version de style.css, balise <meta name="ag-version"> de index.html.
La page compare ces tampons au démarrage : si deux fichiers ne portent pas le même numéro, elle le note dans le journal et se recharge une fois.
Usage :  python verifications/sync_version.py            (écrit)
         python verifications/sync_version.py --check    (ne modifie rien ; code de sortie 1 si un tampon est faux)"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
V = re.search(r"APP_VERSION\s*=\s*'([^']+)'", (ROOT / "version.js").read_text(encoding="utf-8")).group(1)
check = "--check" in sys.argv
bad = []


def rewrite(name, pattern, repl):
    p = ROOT / name
    t = p.read_text(encoding="utf-8")
    new, n = re.subn(pattern, repl, t, count=1, flags=re.M)
    if n != 1:
        bad.append(name + " : tampon introuvable"); return
    if new != t:
        if check: bad.append("%s : tampon pas à jour" % name)
        else: p.write_bytes(new.encode("utf-8"))


for f in ("garde.js", "db.js", "rides.js", "fuel.js", "app.js"):
    rewrite(f, r"^(self\.AG_STAMPS=self\.AG_STAMPS\|\|\{\};self\.AG_STAMPS\['%s'\]=')[^']*(';)" % re.escape(f), r"\g<1>%s\g<2>" % V)
rewrite("style.css", r'^(:root\{--ag-version:")[^"]*("\})', r"\g<1>%s\g<2>" % V)
rewrite("index.html", r'^(<meta name="ag-version" content=")[^"]*(">)', r"\g<1>%s\g<2>" % V)
if bad:
    print("\n".join(bad)); raise SystemExit(1)
print("tampons %s : version %s" % ("vérifiés" if check else "écrits", V))
