"""Petits outils communs aux contrôles."""
import re, pathlib


def fausse_version(dossier, v):
    """Écrit la « version suivante » inventée v dans version.js ET dans les tampons de chaque fichier du dossier d'essai (comme le ferait sync_version.py)."""
    d = pathlib.Path(dossier)
    (d / "version.js").write_text("self.APP_VERSION = '%s';\n" % v, encoding="utf-8")
    for f in ("garde.js", "db.js", "rides.js", "fuel.js", "mots.js", "sauvegarde.js", "app.js"):
        t = (d / f).read_bytes().decode("utf-8")
        (d / f).write_bytes(re.sub(r"^(self\.AG_STAMPS=self\.AG_STAMPS\|\|\{\};self\.AG_STAMPS\['[^']+'\]=')[^']*(';)", r"\g<1>%s\g<2>" % v, t, count=1, flags=re.M).encode("utf-8"))
    t = (d / "style.css").read_bytes().decode("utf-8")
    (d / "style.css").write_bytes(re.sub(r'^(:root\{--ag-version:")[^"]*("\})', r"\g<1>%s\g<2>" % v, t, count=1, flags=re.M).encode("utf-8"))
    t = (d / "index.html").read_bytes().decode("utf-8")
    (d / "index.html").write_bytes(re.sub(r'^(<meta name="ag-version" content=")[^"]*(">)', r"\g<1>%s\g<2>" % v, t, count=1, flags=re.M).encode("utf-8"))
