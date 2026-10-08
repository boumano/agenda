"""Lit un fichier de sauvegarde .agenda HORS de l'appli (sur le PC), avec la phrase de récupération.
Vérifie l'empreinte (SHA-256) et les comptes de contrôle, puis écrit un fichier JSON lisible.
Sert à prouver que la sauvegarde se déchiffre sans l'appli, et de base à l'archivage futur dans la base Python.

Installation (une fois) :   pip install cryptography
Usage :                     python tools/lire_export.py agenda-2026-10-25-0930.agenda
                            python tools/lire_export.py agenda-2026-10-25-0930.agenda -o contenu.json
La phrase (10 mots) est demandée au clavier, sans s'afficher. Pour un essai automatique : variable d'environnement AGENDA_PHRASE.
Le JSON produit contient des données personnelles : à ranger comme du papier sensible. Ce script ne modifie jamais le fichier .agenda.

Format du fichier .agenda (texte JSON) :
  format "agenda-export", format_version 1, app_version, schema (structure des données), exported_at (UTC, ISO 8601),
  kdf {name "PBKDF2-SHA256", iterations, salt (base64, 16 octets)},
  wrapped_key {iv, ct} : la clé de données (32 octets) chiffrée en AES-GCM par la clé tirée de la phrase (données associées : "agenda-key|1"),
  cipher "AES-256-GCM", iv (12 octets), ct : le contenu, chiffré avec la clé de données (données associées : "agenda-export|1|<schema>|<exported_at>").
  Le contenu déchiffré est un JSON {counts:{persons,rides,fuel}, sha256, data} ; data est un TEXTE JSON dont le SHA-256 doit valoir sha256."""
import argparse, base64, getpass, hashlib, json, os, sys, unicodedata

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
except ImportError:
    sys.exit("Il faut installer la bibliothèque « cryptography » :  pip install cryptography")


def norm_phrase(s):
    """même règle que l'appli : sans accents, en minuscules, espaces simples"""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return " ".join(s.split())


def lire(texte, phrase):
    try:
        h = json.loads(texte)
    except ValueError:
        raise SystemExit("Fichier abîmé ou incomplet (ce n'est pas du JSON lisible).")
    if h.get("format") != "agenda-export":
        raise SystemExit("Ce fichier n'est pas une sauvegarde Agenda.")
    if h.get("format_version", 0) > 1:
        raise SystemExit("Format de fichier plus récent que ce script : mettre le script à jour.")
    mots = norm_phrase(phrase).split(" ")
    if len(mots) != 10:
        raise SystemExit("La phrase doit comporter exactement 10 mots.")
    try:
        k = h["kdf"]
        salt = base64.b64decode(k["salt"], validate=True)
        kek = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=int(k["iterations"])).derive(" ".join(mots).encode("utf-8"))
        w = h["wrapped_key"]
        dk = AESGCM(kek).decrypt(base64.b64decode(w["iv"], validate=True), base64.b64decode(w["ct"], validate=True), b"agenda-key|1")
    except InvalidTag:
        raise SystemExit("La phrase ne correspond pas à ce fichier.")
    except (KeyError, ValueError, TypeError):
        raise SystemExit("Fichier abîmé (en-tête illisible).")
    aad = ("agenda-export|%d|%s|%s" % (h["format_version"], h["schema"], h["exported_at"])).encode("utf-8")
    try:
        plain = AESGCM(dk).decrypt(base64.b64decode(h["iv"], validate=True), base64.b64decode(h["ct"], validate=True), aad)
    except (InvalidTag, ValueError, KeyError):
        raise SystemExit("Fichier abîmé ou modifié : le contenu ne peut pas être déchiffré.")
    p = json.loads(plain.decode("utf-8"))
    if hashlib.sha256(p["data"].encode("utf-8")).hexdigest() != p["sha256"]:
        raise SystemExit("Empreinte (SHA-256) différente : contenu altéré.")
    data = json.loads(p["data"])
    c = {"persons": len(data["persons"]), "rides": len(data["rides"]), "fuel": len(data.get("fuel", []))}
    if c != p["counts"]:
        raise SystemExit("Les comptes de contrôle ne correspondent pas : %s au lieu de %s." % (c, p["counts"]))
    return {"header": {x: h[x] for x in ("format", "format_version", "app_version", "schema", "exported_at")}, "counts": c, "sha256": p["sha256"], "data": data}


def main():
    ap = argparse.ArgumentParser(description="Lit une sauvegarde Agenda (.agenda) et écrit un JSON lisible.")
    ap.add_argument("fichier"); ap.add_argument("-o", "--sortie", help="fichier JSON à écrire (défaut : <fichier>.json)")
    a = ap.parse_args()
    texte = open(a.fichier, "r", encoding="utf-8").read()
    phrase = os.environ.get("AGENDA_PHRASE") or getpass.getpass("Phrase de récupération (10 mots) : ")
    r = lire(texte, phrase)
    sortie = a.sortie or a.fichier + ".json"
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    c = r["counts"]
    print("Sauvegarde valide : export du %s, %d personnes, %d courses, %d pleins. Écrit : %s" % (r["header"]["exported_at"], c["persons"], c["rides"], c["fuel"], sortie))


if __name__ == "__main__":
    main()
