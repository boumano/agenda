"""Étape 5 d'Agenda : page Essence (pleins d'essence). Noms et valeurs FICTIFS seulement.
Vérifie : ajout / modification / corbeille et « Annuler » (5 s), calculs (deux chiffres remplis → le troisième se calcule, repère « calculé »), règle « inconnu » et « total partiel »,
totaux du mois et changement de mois, virgule et point, 0 refusé, trois chiffres incohérents refusés, jour à venir refusé, quitter sans enregistrer, masquage (œil, temps, formulaire ouvert),
persistance après fermeture et réouverture, hors connexion, jours autour du 25 octobre 2026 (changement d'heure : rien ne se décale).
W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, threading, pathlib, http.server, functools
from datetime import date
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
TODAY = date.today(); TISO = TODAY.isoformat()
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
fails = 0; total = 0


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


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % srv.server_address[1]
INIT = """window.__off=0; window.__freeze=false; (function(){ var n=Date.now.bind(Date); Date.now=function(){ return n()+window.__off; }; var si=window.setInterval.bind(window); window.setInterval=function(f,t){ return si(function(){ if(!window.__freeze) f(); },t); }; })();"""

_n = [0]
def plein(dt, ml, milli, cents, deleted=None):
    _n[0] += 1
    return {"id": "00000000-0000-4000-a000-%012d" % _n[0], "date": dt, "liters_ml": ml, "price_milli": milli, "total_cents": cents, "calc": None,
            "created_at": "2026-01-01T00:00:%02d.000Z" % _n[0], "updated_at": "2026-01-01T00:00:00.000Z", "deleted_at": deleted}

def first_of(dt): return dt.replace(day=1)
def add_month(dt, n):
    m = dt.month - 1 + n
    return date(dt.year + m // 12, m % 12 + 1, 1)
CM = first_of(TODAY); PM = add_month(CM, -1)

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="allow", timezone_id="Europe/Brussels")
    cx.add_init_script(INIT)
    errs = []
    pg = cx.new_page()
    pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
    pg.on("console", lambda m: errs.append("console " + m.text) if m.type == "error" else None)
    w = lambda: pg.wait_for_timeout(350)
    tap = lambda sel: (pg.locator(sel).first.tap(), w())
    txt = lambda sel: pg.locator(sel).inner_text().strip()
    cur = lambda: pg.evaluate("__ag.cur")
    masked = lambda: pg.evaluate("__ag.masked")
    def boot():
        pg.goto(BASE); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); pg.wait_for_timeout(250)
    def reload():
        pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    def fuel_all():
        return pg.evaluate("""()=>new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result;const g=d.transaction('fuel').objectStore('fuel').getAll();g.onsuccess=()=>{d.close();r(g.result)}}})""")
    def seed(rs):
        pg.evaluate("""async(rs)=>{ for (const r of rs) await AG.putFuel(r) }""", rs)
    def month_now():
        return txt("#fu-month").lower()
    def essence(first=None):
        tap('.nav button.t[data-t="essence"]')
        for _ in range(40):
            if first is None or month_now() == "%s %d" % (MOIS[first.month - 1], first.year): break
            cm = [i for i, m_ in enumerate(MOIS) if month_now().startswith(m_)][0] + 1; cy = int(month_now().split()[-1])
            tap('[data-a="emonth"][data-d="%d"]' % (1 if (first.year, first.month) > (cy, cm) else -1))
    def fill(sel, v):
        pg.locator(sel).fill(v); pg.wait_for_timeout(120)
    def toast_text(): return pg.locator("#toast").inner_text() if pg.locator("#toast").is_visible() else ""
    def sheet_open(): return pg.locator("#daysheet.on").count() == 1
    def notes(): return txt("#fu-notes") if pg.locator("#fu-notes").count() else ""

    boot()
    # ---------- 1. page vide ----------
    essence(CM)
    ok(tag + " Essence vide : titre, mois en cours, 2 chevrons, « 0 plein », « Aucun plein noté ce mois-ci. »", txt("#s-essence h1") == "Essence" and month_now() == "%s %d" % (MOIS[CM.month - 1], CM.year) and pg.locator('[data-a="emonth"]').count() == 2 and txt("#fu-count") == "0" and "Aucun plein noté ce mois-ci." in txt("#fu-list"))
    ok(tag + " total vide : « 0,00 L » et « 0,00 € », jamais « inconnu » sans plein", txt("#fu-lit") == "0,00 L" and txt("#fu-eur") == "0,00 €", (txt("#fu-lit"), txt("#fu-eur")))
    ok(tag + " la base est en structure 5 avec le magasin « fuel » et l'index « date »", pg.evaluate("""()=>new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result;const t=d.transaction('fuel');r([d.version,[...d.objectStoreNames].includes('fuel'),[...t.objectStore('fuel').indexNames]]);d.close()}})""") == [5, True, ["date"]])

    # ---------- 2. ajout : deux chiffres remplis, le troisième se calcule ----------
    tap('[data-a="eday"][data-iso="%s"]' % TISO)
    ok(tag + " jour sans plein : le formulaire « Ajouter un plein » s'ouvre directement, clavier décimal", txt("#ds-title") == "Ajouter un plein" and pg.locator("#fu-p, #fu-l, #fu-m").count() == 3 and pg.locator("#fu-l").get_attribute("inputmode") == "decimal")
    fill("#fu-p", "1,789"); fill("#fu-l", "38.5")
    ok(tag + " prix 1,789 + litres 38.5 (point accepté) → montant calculé 68,88 avec le repère « calculé »", pg.locator("#fu-m").input_value() == "68,88" and pg.locator("#fu-tag-m").is_visible() and not pg.locator("#fu-tag-p").is_visible(), pg.locator("#fu-m").input_value())
    pg.screenshot(path=SHOTS + "/essence_form_%dx%d_%s.png" % (W, H, SCHEME))
    tap('[data-a="esave"]')
    ok(tag + " enregistré : « Plein ajouté », la feuille se ferme", "Plein ajouté" in toast_text() and not sheet_open())
    ok(tag + " total : 1 plein, 38,50 L, 68,88 € ; la ligne montre « 38,5 L » et « 68,88 € »", txt("#fu-count") == "1" and txt("#fu-lit") == "38,50 L" and txt("#fu-eur") == "68,88 €" and "38,5 L" in txt("#fu-list") and "68,88 €" in txt("#fu-list"), (txt("#fu-lit"), txt("#fu-eur"), txt("#fu-list")))
    rs = fuel_all()
    ok(tag + " rangé en entiers : 38500 mL, 1789 millièmes, 6888 centimes, date en texte, calc « total », pas de corbeille", len(rs) == 1 and rs[0]["liters_ml"] == 38500 and rs[0]["price_milli"] == 1789 and rs[0]["total_cents"] == 6888 and rs[0]["date"] == TISO and rs[0]["calc"] == "total" and rs[0]["deleted_at"] is None, rs)
    ID1 = rs[0]["id"]

    # ---------- 3. modification ----------
    tap('.fuelrow[data-id="%s"]' % ID1)
    ok(tag + " toucher la ligne : « Modifier ce plein » avec les valeurs, repère « calculé » sur le montant, bouton « Supprimer ce plein »", txt("#ds-title") == "Modifier ce plein" and pg.locator("#fu-p").input_value() == "1,789" and pg.locator("#fu-l").input_value() == "38,5" and pg.locator("#fu-m").input_value() == "68,88" and pg.locator("#fu-tag-m").is_visible() and pg.locator('[data-a="edelask"]').count() == 1)
    fill("#fu-l", "40")
    ok(tag + " litres changés → le montant calculé suit (71,56), le prix saisi reste", pg.locator("#fu-m").input_value() == "71,56" and pg.locator("#fu-p").input_value() == "1,789", pg.locator("#fu-m").input_value())
    tap('[data-a="esave"]')
    ok(tag + " « Plein modifié » ; total 40,00 L et 71,56 €", "Plein modifié" in toast_text() and txt("#fu-lit") == "40,00 L" and txt("#fu-eur") == "71,56 €", (txt("#fu-lit"), txt("#fu-eur")))
    ok(tag + " modifier garde le même identifiant et ne crée pas de doublon", len(fuel_all()) == 1 and fuel_all()[0]["id"] == ID1)

    # ---------- 4. les trois combinaisons de calcul ----------
    tap('[data-a="eday"][data-iso="%s"]' % TISO)
    ok(tag + " jour avec un plein : la feuille est une liste avec « Ajouter un plein » et « Fermer »", pg.locator('[data-a="eadd"]').count() == 1 and pg.locator('#ds-panel [data-a="dsclose"]').count() == 1 and "71,56 €" in txt("#ds-panel"))
    tap('[data-a="eadd"]'); fill("#fu-m", "50"); fill("#fu-p", "2")
    ok(tag + " montant 50 + prix 2 → litres calculés 25 (repère « calculé » sur litres)", pg.locator("#fu-l").input_value() == "25" and pg.locator("#fu-tag-l").is_visible(), pg.locator("#fu-l").input_value())
    fill("#fu-l", "20")
    ok(tag + " retaper les litres : Pascal reprend la main, le repère « calculé » disparaît (trois chiffres saisis, rien n'est recalculé)", not pg.locator("#fu-tag-l").is_visible() and pg.locator("#fu-m").input_value() == "50", pg.locator("#fu-m").input_value())
    fill("#fu-m", "")
    ok(tag + " montant vidé → recalculé : litres 20 × prix 2 = 40 (« calculé »)", pg.locator("#fu-m").input_value() == "40" and pg.locator("#fu-tag-m").is_visible(), pg.locator("#fu-m").input_value())
    fill("#fu-p", ""); fill("#fu-m", "30")
    ok(tag + " prix vidé, montant 30 + litres 20 → prix calculé 1,5", pg.locator("#fu-p").input_value() == "1,5" and pg.locator("#fu-tag-p").is_visible(), pg.locator("#fu-p").input_value())
    tap('[data-a="esave"]')
    ok(tag + " 2 pleins : total 60,00 L et 101,56 €", txt("#fu-count") == "2" and txt("#fu-lit") == "60,00 L" and txt("#fu-eur") == "101,56 €", (txt("#fu-lit"), txt("#fu-eur")))

    # ---------- 5. refus ----------
    tap('[data-a="eday"][data-iso="%s"]' % TISO); tap('[data-a="eadd"]')
    fill("#fu-l", "0"); fill("#fu-m", "10"); tap('[data-a="esave"]')
    ok(tag + " 0 refusé : « Un zéro n’est pas possible : laisse la case vide si tu ne sais pas. », rien enregistré", pg.locator("#fu-err").is_visible() and txt("#fu-err") == "Un zéro n’est pas possible : laisse la case vide si tu ne sais pas." and len(fuel_all()) == 2, txt("#fu-err"))
    fill("#fu-l", "abc1,2,3")
    ok(tag + " les lettres sont retirées pendant la frappe", pg.locator("#fu-l").input_value() == "1,2,3", pg.locator("#fu-l").input_value())
    tap('[data-a="esave"]')
    ok(tag + " « 1,2,3 » refusé avec l'exemple : « Litres : écris un nombre comme 38,5, ou laisse vide. »", txt("#fu-err") == "Litres : écris un nombre comme 38,5, ou laisse vide.", txt("#fu-err"))
    fill("#fu-l", ""); tap('[data-a="esave"]')
    ok(tag + " un seul chiffre : « Remplis deux des trois chiffres : le troisième se calcule. »", txt("#fu-err") == "Remplis deux des trois chiffres : le troisième se calcule.", txt("#fu-err"))
    fill("#fu-l", "10"); fill("#fu-p", "2"); fill("#fu-m", "99"); tap('[data-a="esave"]')
    ok(tag + " trois chiffres incohérents : « Les trois chiffres ne correspondent pas. Garde-en deux. », rien enregistré", txt("#fu-err") == "Les trois chiffres ne correspondent pas. Garde-en deux." and len(fuel_all()) == 2, txt("#fu-err"))
    fill("#fu-m", "20,01"); tap('[data-a="esave"]')
    ok(tag + " trois chiffres justes à 1 centime près : accepté (3 pleins)", len(fuel_all()) == 3 and "Plein ajouté" in toast_text(), len(fuel_all()))
    ok(tag + " aucun plein enregistré avec une valeur 0", all(r[k] != 0 for r in fuel_all() for k in ("liters_ml", "price_milli", "total_cents")))

    # ---------- 6. quitter sans enregistrer ----------
    tap('[data-a="eday"][data-iso="%s"]' % TISO); tap('[data-a="eadd"]')
    tap('#ds-panel [data-a="eback"]')
    ok(tag + " formulaire intact : « Annuler » revient à la liste sans question", pg.locator("#confirm.on").count() == 0 and pg.locator('[data-a="eadd"]').count() == 1)
    tap('[data-a="eadd"]'); fill("#fu-l", "12")
    tap('#ds-panel [data-a="eback"]')
    ok(tag + " formulaire modifié : « Quitter sans enregistrer ? » (Rester / Quitter)", pg.locator("#confirm.on").count() == 1 and txt("#confirm-title") == "Quitter sans enregistrer ?" and txt("#confirm-cancel") == "Rester")
    tap('#confirm-cancel')
    ok(tag + " « Rester » : on garde la saisie", pg.locator("#fu-l").input_value() == "12" and pg.locator("#confirm.on").count() == 0)
    pg.evaluate("history.back()"); w()
    ok(tag + " touche Retour d'Android : même question", pg.locator("#confirm.on").count() == 1)
    tap('#confirm-cancel')
    tap('#ds-panel [data-a="eback"]'); tap('#confirm-ok')
    ok(tag + " « Quitter » : retour à la liste, rien d'enregistré (3 pleins)", len(fuel_all()) == 3 and pg.locator('[data-a="eadd"]').count() == 1)
    tap('#ds-panel [data-a="dsclose"]')
    ok(tag + " « Fermer » sans saisie : la feuille se ferme", not sheet_open())

    # ---------- 7. corbeille et Annuler (5 s) ----------
    tap('.fuelrow[data-id="%s"]' % ID1); tap('[data-a="edelask"]')
    ok(tag + " « Supprimer ce plein ? » demande confirmation", pg.locator("#confirm.on").count() == 1 and txt("#confirm-title") == "Supprimer ce plein ?")
    tap('#confirm-ok')
    ok(tag + " supprimé : « Plein supprimé » avec « Annuler » ; le total passe à 2 pleins", "Plein supprimé" in toast_text() and pg.locator("#toast [data-a='undo']").count() == 1 and txt("#fu-count") == "2", txt("#fu-count"))
    rs = {r["id"]: r for r in fuel_all()}
    ok(tag + " jamais effacé : le plein est toujours dans la base, marqué à la corbeille (deleted_at)", ID1 in rs and rs[ID1]["deleted_at"] is not None)
    tap("#toast [data-a='undo']")
    ok(tag + " « Annuler » : le plein revient (3 pleins, corbeille vide)", txt("#fu-count") == "3" and {r["id"]: r for r in fuel_all()}[ID1]["deleted_at"] is None)
    tap('.fuelrow[data-id="%s"]' % ID1); tap('[data-a="edelask"]'); tap('#confirm-ok')
    pg.wait_for_timeout(5400)
    ok(tag + " après 5 secondes le message disparaît, le plein reste à la corbeille", not pg.locator("#toast").is_visible() and txt("#fu-count") == "2")
    tap('.fuelrow >> nth=0'); tap('[data-a="edelask"]'); tap('#confirm-cancel')
    ok(tag + " « Annuler » dans la confirmation : rien n'est supprimé (2 pleins)", txt("#fu-count") == "2" and len([r for r in fuel_all() if not r["deleted_at"]]) == 2)
    if pg.locator("#daysheet.on").count():
        tap('#ds-panel [data-a="eback"]')
        if pg.locator("#confirm.on").count(): tap('#confirm-ok')
        if sheet_open(): tap('#ds-panel [data-a="dsclose"]')

    # ---------- 8. jour à venir ----------
    nxt = pg.evaluate("[...document.querySelectorAll('[data-a=eday]')].map(b=>b.dataset.iso).filter(i=>i>'%s')[0] || ''" % TISO)
    if nxt:
        tap('[data-a="eday"][data-iso="%s"]' % nxt)
        ok(tag + " un jour pas encore arrivé : « Ce jour n’est pas encore arrivé », pas de formulaire", "Ce jour n’est pas encore arrivé" in toast_text() and not sheet_open())

    # ---------- 9. règle « inconnu », totaux partiels, changement de mois ----------
    P1, P2, P3, P4 = [PM.replace(day=d).isoformat() for d in (3, 4, 5, 6)]
    seed([plein(P1, 30000, 1500, 4500), plein(P2, None, 1500, None), plein(P3, 20000, None, None), plein(P4, 99000, 1000, 9900, deleted="2026-02-01T00:00:00.000Z")])
    essence(PM)
    ok(tag + " mois précédent : 3 pleins (celui à la corbeille ne compte pas)", txt("#fu-count") == "3", txt("#fu-count"))
    ok(tag + " litres = somme des litres CONNUS (50,00 L), note « + 1 plein sans litres (total partiel) »", txt("#fu-lit") == "50,00 L" and "+ 1 plein sans litres (total partiel)" in notes(), (txt("#fu-lit"), notes()))
    ok(tag + " montant = 45,00 € (le connu seulement), note « + 2 pleins sans montant (total partiel) » : jamais de 0 inventé", txt("#fu-eur") == "45,00 €" and "+ 2 pleins sans montant (total partiel)" in notes(), (txt("#fu-eur"), notes()))
    ok(tag + " la ligne d'un plein incomplet dit « litres inconnus » / « montant inconnu » (jamais 0)", "litres inconnus" in txt("#fu-list") and "montant inconnu" in txt("#fu-list") and not re.search(r"(^|\s)0 L|0,00", txt("#fu-list")), txt("#fu-list"))
    pg.screenshot(path=SHOTS + "/essence_partiel_%dx%d_%s.png" % (W, H, SCHEME))
    PM3 = add_month(CM, -3)
    seed([plein(PM3.replace(day=2).isoformat(), None, 1500, None), plein(PM3.replace(day=3).isoformat(), None, 1400, None)])
    essence(PM3)
    ok(tag + " mois où rien n'est connu : litres et montant « inconnu » (pas « 0,00 »)", txt("#fu-count") == "2" and txt("#fu-lit") == "inconnu" and txt("#fu-eur") == "inconnu", (txt("#fu-lit"), txt("#fu-eur")))
    essence(PM)
    ok(tag + " retour au mois précédent : les données du mois suivent (3 pleins)", txt("#fu-count") == "3")
    tap('[data-a="emonth"][data-d="1"]')
    ok(tag + " mois en cours : 2 pleins ; un plein d'un autre mois n'y est jamais compté", month_now() == "%s %d" % (MOIS[CM.month - 1], CM.year) and txt("#fu-count") == "2")

    # ---------- 10. masquage ----------
    tap('[data-a="eday"][data-iso="%s"]' % TISO); tap('[data-a="eadd"]'); fill("#fu-l", "33"); fill("#fu-p", "1,5")
    pg.evaluate("document.querySelector('#s-essence [data-a=hide]').click()"); w()
    ok(tag + " œil touché pendant un formulaire ouvert : écran neutre", masked())
    left = pg.evaluate("document.querySelector('#s-essence').innerText + ' ' + document.querySelector('#ds-panel').innerText + ' ' + [...document.querySelectorAll('input')].map(i => i.value).join(' ')")
    ok(tag + " rien de lisible derrière l'écran neutre (ni totaux, ni formulaire, ni valeurs saisies)", not re.search(r"\d|plein|litre", left, re.I) and not sheet_open(), left[:200])
    pg.locator("#veil").tap(); w()
    ok(tag + " retour : page Essence revenue, formulaire abandonné", not masked() and cur() == "essence" and not sheet_open())
    ok(tag + " retour : totaux revenus, 2 pleins, aucun plein de plus", not masked() and txt("#fu-count") == "2" and len([r for r in fuel_all() if not r["deleted_at"] and r["date"].startswith(TISO[:7])]) == 2)
    pg.evaluate("window.__off += 400000"); pg.wait_for_timeout(2500)
    ok(tag + " 6 minutes sans toucher : masquage automatique, rien de lisible", masked() and not re.search(r"\d", pg.evaluate("document.querySelector('#s-essence').innerText")), pg.evaluate("document.querySelector('#s-essence').innerText")[:120])
    pg.locator("#veil").tap(); w()
    ok(tag + " retour après le masquage automatique : les totaux sont revenus", txt("#fu-count") == "2")

    # ---------- 11. persistance, hors connexion ----------
    reload(); essence(CM)
    ok(tag + " fermer / rouvrir : les 2 pleins du mois sont toujours là", txt("#fu-count") == "2")
    cx.set_offline(True); reload(); essence(CM)
    ok(tag + " hors connexion : la page Essence s'ouvre et les pleins s'affichent", txt("#fu-count") == "2")
    tap('[data-a="eday"][data-iso="%s"]' % TISO); tap('[data-a="eadd"]'); fill("#fu-l", "10"); fill("#fu-p", "2"); tap('[data-a="esave"]')
    ok(tag + " hors connexion : ajouter un plein marche (3 pleins)", txt("#fu-count") == "3")
    cx.set_offline(False)

    # ---------- 12. changement d'heure : 24, 25, 26 octobre 2026 ----------
    cx2 = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, color_scheme=SCHEME, service_workers="allow", timezone_id="Europe/Brussels")
    cx2.add_init_script(INIT)
    q = cx2.new_page()
    q.goto(BASE); q.wait_for_function("window.__ag && window.__ag.ready"); q.evaluate("window.__ag.ready")
    q.evaluate("window.__off = new Date('2026-10-28T10:00:00+01:00').getTime() - Date.now()"); q.wait_for_timeout(2500)
    if q.evaluate("__ag.masked"): q.locator("#veil").tap(); q.wait_for_timeout(300)
    q.locator('.nav button.t[data-t="personnes"]').first.tap(); q.wait_for_timeout(300)
    q.locator('.nav button.t[data-t="essence"]').first.tap(); q.wait_for_timeout(500)
    ok(tag + " horloge réglée au 28 octobre 2026 : Essence affiche « octobre 2026 »", q.locator("#fu-month").inner_text().strip().lower() == "octobre 2026", q.locator("#fu-month").inner_text())
    for dd in ("2026-10-24", "2026-10-25", "2026-10-26"):
        q.locator('[data-a="eday"][data-iso="%s"]' % dd).first.tap(); q.wait_for_timeout(300)
        q.locator("#fu-l").fill("20"); q.locator("#fu-p").fill("2"); q.wait_for_timeout(100)
        q.locator('[data-a="esave"]').first.tap(); q.wait_for_timeout(450)
    got = q.evaluate("""()=>new Promise(r=>{const x=indexedDB.open('agenda');x.onsuccess=()=>{const d=x.result;const g=d.transaction('fuel').objectStore('fuel').getAll();g.onsuccess=()=>{d.close();r(g.result.map(z=>z.date).sort())}}})""")
    ok(tag + " pleins des 24, 25 et 26 octobre : chacun gardé à sa date (rien de décalé par le changement d'heure)", got == ["2026-10-24", "2026-10-25", "2026-10-26"], got)
    cells = q.evaluate("[...document.querySelectorAll('.calgrid .cell.f')].map(c=>c.dataset.iso)")
    ok(tag + " le calendrier marque exactement ces 3 jours ; total 60,00 L et 120,00 €", cells == ["2026-10-24", "2026-10-25", "2026-10-26"] and q.locator("#fu-lit").inner_text().strip() == "60,00 L" and q.locator("#fu-eur").inner_text().strip() == "120,00 €", (cells, q.locator("#fu-lit").inner_text(), q.locator("#fu-eur").inner_text()))
    cx2.close()

    ok(tag + " aucune erreur de page ni de console", not errs, errs)
    b.close()

print("\n%s %d/%d verifications reussies" % (tag, total - fails, total))
raise SystemExit(1 if fails else 0)
