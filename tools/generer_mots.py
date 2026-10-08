"""Fabrique mots.js (la liste de 2048 mots de la phrase de récupération) à partir de fichiers de mots candidats.
Règles : lettres seulement (a-z et accents français), 4 à 9 lettres ; deux mots ne sont jamais égaux une fois les accents retirés ;
deux mots gardés diffèrent toujours d'au moins 2 lettres (distance d'édition >= 2 : pas de singulier/pluriel, pas de faute de frappe qui donne un autre mot) ;
aucun mot n'est le début d'un autre. On garde les premiers mots de la liste, dans l'ordre, jusqu'à 2048 (= 2^11 : un tirage sur 11 bits est sans biais).
Usage :  python tools/generer_mots.py candidats1.txt candidats2.txt ...   (écrit mots.js à la racine)
Aucune donnée personnelle ici : seulement des mots courants."""
import re, sys, unicodedata, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXCLUS = {"vovage", "vérandas", "yack", "lecon", "rené", "aujourd", "rendez", "machoire", "tobogan", "vergé", "tousser"}   # fautes ou formes à éviter


def norm(w): return "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c)).lower()


def dist_le1(a, b):
    """vrai si la distance d'édition entre a et b est 0 ou 1"""
    if a == b: return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1: return False
    if la == lb:
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    if la > lb: a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]: i += 1
    return a[i:] == b[i + 1:]


def main(files):
    words = []
    for f in files:
        words += pathlib.Path(f).read_text(encoding="utf-8").split()
    kept = []; keptn = []; seen = set()
    for w in words:
        w = w.strip().lower()
        n = norm(w)
        if w in EXCLUS or not re.fullmatch(r"[a-zàâäçéèêëîïôöùûüÿœæ]{4,9}", w) or not re.fullmatch(r"[a-z]+", n) or n in seen: continue
        if any(dist_le1(n, k) or n.startswith(k) or k.startswith(n) for k in keptn): continue
        kept.append(w); keptn.append(n); seen.add(n)
        if len(kept) == 2048: break
    print("candidats :", len(words), " gardés :", len(kept))
    if len(kept) < 2048: raise SystemExit("pas assez de mots (il en manque %d) : ajouter des candidats" % (2048 - len(kept)))
    out = ("self.AG_STAMPS=self.AG_STAMPS||{};self.AG_STAMPS['mots.js']='0.6.0'; /* numéro écrit par verifications/sync_version.py : ne pas modifier à la main */\n"
           "/* Agenda : la liste de 2048 mots français de la phrase de récupération (fabriquée par tools/generer_mots.py ; ne pas modifier à la main).\n"
           "   2048 = 2^11 : un nombre de 11 bits tiré au hasard désigne un mot, sans biais. Aucun mot ne ressemble à un autre à une lettre près. Aucune donnée personnelle. */\n"
           "self.AG_WORDS = '" + " ".join(kept) + "'.split(' ');\n")
    (ROOT / "mots.js").write_bytes(out.encode("utf-8"))


main(sys.argv[1:])
