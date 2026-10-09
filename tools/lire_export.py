"""Lit un fichier de sauvegarde .agenda HORS de l'appli (sur le PC), avec la phrase de récupération.
Vérifie l'empreinte (SHA-256) et les comptes de contrôle, puis écrit un fichier JSON lisible.
Sert à prouver que la sauvegarde se déchiffre sans l'appli, et de base à l'archivage futur dans la base Python.

Installation (une fois) :   pip install cryptography
Usage :                     python tools/lire_export.py agenda-2026-10-25-0930.agenda
                            python tools/lire_export.py agenda-2026-10-25-0930.agenda -o contenu.json
                            python tools/lire_export.py agenda-2026-10-25-0930.agenda --visible     (la saisie s'affiche)
La phrase (10 mots) est demandée au clavier, SANS s'afficher (sauf avec --visible). Elle n'est jamais prise en argument de la ligne de commande,
jamais écrite dans un fichier, jamais affichée en dehors de --visible. Majuscules, accents, espaces en trop, tirets et apostrophes sont sans importance :
chaque mot est rapproché de la liste officielle (mots.js). Pour un essai automatique seulement : variable d'environnement AGENDA_PHRASE.
Le JSON produit contient des données personnelles : à ranger comme du papier sensible. Ce script ne modifie jamais le fichier .agenda.

Format du fichier .agenda (texte JSON) :
  format "agenda-export", format_version 1, app_version, schema (structure des données), exported_at (UTC, ISO 8601),
  kdf {name "PBKDF2-SHA256", iterations, salt (base64, 16 octets)},
  wrapped_key {iv, ct} : la clé de données (32 octets) chiffrée en AES-GCM par la clé tirée de la phrase (données associées : "agenda-key|1"),
  cipher "AES-256-GCM", iv (12 octets), ct : le contenu, chiffré avec la clé de données (données associées : "agenda-export|1|<schema>|<exported_at>").
  Le contenu déchiffré est un JSON {counts:{persons,rides,fuel}, sha256, data} ; data est un TEXTE JSON dont le SHA-256 doit valoir sha256."""
import argparse, base64, getpass, hashlib, json, os, re, sys, unicodedata

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
except ImportError:
    sys.exit("Il faut installer la bibliothèque « cryptography » :  pip install cryptography")


def plier(mot):
    """un mot « replié » : sans accents, en minuscules, sans tiret ni apostrophe ni autre signe (même règle que l'appli)"""
    s = unicodedata.normalize("NFD", mot)
    return "".join(c for c in s if "a" <= c.lower() <= "z" and not unicodedata.combining(c)).lower()


def charger_liste():
    """les mots officiels (mots.js, à côté du dossier tools/), repliés ; None si le fichier est introuvable"""
    ici = os.path.dirname(os.path.abspath(__file__))
    for chemin in (os.path.join(ici, "..", "mots.js"), os.path.join(ici, "mots.js")):
        if os.path.exists(chemin):
            m = re.search(r"self\.AG_WORDS = '([^']+)'\.split", open(chemin, encoding="utf-8").read())
            if m:
                return {plier(w) for w in m.group(1).split(" ")}
    return None


def norm_phrase(s, liste=None):
    """les 10 mots repliés, séparés par un espace. Refuse (sans jamais citer la phrase) si le nombre de mots n'est pas 10 ou si un mot n'est pas dans la liste."""
    mots = [plier(x) for x in s.split() if plier(x)]
    if len(mots) != 10:
        raise SystemExit("J'ai lu %d mot%s : il en faut exactement 10." % (len(mots), "s" if len(mots) > 1 else ""))
    if liste is not None:
        for i, w in enumerate(mots, 1):
            if w not in liste:
                raise SystemExit("Le mot n° %d ne figure pas dans la liste. Vérifiez son orthographe." % i)
    return " ".join(mots)


def lire(texte, phrase, liste=None):
    try:
        h = json.loads(texte)
    except ValueError:
        raise SystemExit("Fichier abîmé ou incomplet (ce n'est pas du JSON lisible).")
    if h.get("format") != "agenda-export":
        raise SystemExit("Ce fichier n'est pas une sauvegarde Agenda.")
    if h.get("format_version", 0) > 1:
        raise SystemExit("Format de fichier plus récent que ce script : mettre le script à jour.")
    mots = norm_phrase(phrase, liste).split(" ")
    try:
        k = h["kdf"]
        salt = base64.b64decode(k["salt"], validate=True)
        kek = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=int(k["iterations"])).derive(" ".join(mots).encode("utf-8"))
        w = h["wrapped_key"]
        dk = AESGCM(kek).decrypt(base64.b64decode(w["iv"], validate=True), base64.b64decode(w["ct"], validate=True), b"agenda-key|1")
    except InvalidTag:
        raise SystemExit("Les 10 mots sont valides, mais ce n'est pas la phrase de ce fichier. Elle vient peut-être d'un autre essai d'export.")
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
    ap = argparse.ArgumentParser(description="Lit une sauvegarde Agenda (.agenda) et écrit un JSON lisible. La phrase est demandée au clavier, cachée.",
                                 epilog="Majuscules, accents et espaces en trop n'ont pas d'importance. La phrase n'est jamais gardée ni écrite nulle part.")
    ap.add_argument("fichier"); ap.add_argument("-o", "--sortie", help="fichier JSON à écrire (défaut : <fichier>.json)")
    ap.add_argument("--visible", action="store_true", help="afficher ce que vous tapez (la phrase restera visible dans la fenêtre)")
    a = ap.parse_args()
    texte = open(a.fichier, "r", encoding="utf-8").read()
    liste = charger_liste()
    if liste is None:
        print("Attention : mots.js est introuvable, la liste des mots ne peut pas être contrôlée (accents et majuscules restent tolérés).", file=sys.stderr)
    phrase = os.environ.get("AGENDA_PHRASE")
    if not phrase:
        if a.visible:
            print("La phrase sera visible à l'écran et dans l'historique de la fenêtre.", file=sys.stderr)
            phrase = input("Phrase de récupération (10 mots), visible : ")
        else:
            phrase = getpass.getpass("Phrase de récupération (10 mots, rien ne s'affiche pendant la saisie) : ")
        n = len([x for x in phrase.split() if plier(x)])
        print("%d mot%s lu%s." % (n, "s" if n > 1 else "", "s" if n > 1 else ""))
    r = lire(texte, phrase, liste)
    sortie = a.sortie or a.fichier + ".json"
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    c = r["counts"]
    print("Sauvegarde valide : export du %s, %d personnes, %d courses, %d pleins. Écrit : %s" % (r["header"]["exported_at"], c["persons"], c["rides"], c["fuel"], sortie))


if __name__ == "__main__":
    main()
