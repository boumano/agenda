"""Étape 2 d'Agenda : personnes et fiche.
Vérifie : écran Personnes (liste vide au départ, recherche par nom et prénom sans tenir compte des accents, archivées sur la même page,
Restaurer, Personnes actives), fiche (création, modification, rangement dans IndexedDB : identifiant unique, prix en centimes, km en mètres,
heure HH:MM, « inconnu » = vide jamais 0), prix et km avec virgule ET point, 0 refusé, heure invalide, « Au » avant « Du », « Quand » dans les
deux modes (jours de la semaine / dates choisies, pas de jours passés, « Lun à ven », compteur, aller-retour sans perte), avertissement de doublon,
« Quitter sans enregistrer ? », archiver / restaurer / supprimer (personne vide effacée pour de bon, courses notées = suppression impossible),
annuler pendant 5 secondes, persistance après fermeture et réouverture, hors connexion, migration 1 → 2 (base d'essai et vraie base de la version 0.1),
masquage (fiche ouverte comprise), clavier (champs numériques, majuscules), zones de 44 px, aucune erreur JavaScript.
Noms FICTIFS seulement. W et H par variables d'environnement (390 x 780 par défaut), SCHEME=dark (défaut) ou light."""
import os, re, json, threading, pathlib, http.server, functools
from datetime import date, timedelta
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / "captures").mkdir(exist_ok=True)
SHOTS = (HERE / "captures").as_posix()
from playwright.sync_api import sync_playwright

W = int(os.environ.get("W", "390")); H = int(os.environ.get("H", "780")); SCHEME = os.environ.get("SCHEME", "dark")
tag = "[%s %dx%d]" % (SCHEME, W, H)
TODAY = date.today(); TISO = TODAY.isoformat()
fails = 0; total = 0


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


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % srv.server_address[1]
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
INIT = """window.__off=0; window.__freeze=false; (function(){ var n=Date.now.bind(Date); Date.now=function(){ return n()+window.__off; }; var si=window.setInterval.bind(window); window.setInterval=function(f,t){ return si(function(){ if(!window.__freeze) f(); },t); }; })();"""


def month_dates(y, m):
    d = date(y, m, 1); out = []
    while d.month == m: out.append(d); d += timedelta(days=1)
    return out


def next_month(y, m): return (y + 1, 1) if m == 12 else (y, m + 1)


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    cx = b.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, device_scale_factor=2, color_scheme=SCHEME, service_workers="allow")
    cx.add_init_script(INIT)
    errs = []; reqs = []
    cx.on("request", lambda r: reqs.append(r.url))
    pg = cx.new_page()
    pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
    pg.on("console", lambda m: errs.append("console " + m.text) if m.type == "error" else None)

    def boot(page=None):
        page = page or pg
        page.goto(BASE); page.wait_for_function("window.__ag && window.__ag.ready"); page.evaluate("window.__ag.ready"); page.wait_for_timeout(250)

    boot()
    w = lambda: pg.wait_for_timeout(300)
    tap = lambda sel: (pg.locator(sel).first.tap(), w())
    goto = lambda t: tap('.nav button.t[data-t="%s"]' % t)
    cur = lambda: pg.evaluate("__ag.cur")
    masked = lambda: pg.evaluate("__ag.masked")
    toast_msg = lambda: pg.locator("#toast span").inner_text() if pg.locator("#toast").is_visible() and pg.locator("#toast span").count() else ""
    has_undo = lambda: pg.locator('#toast [data-a="undo"]').count() == 1 and pg.locator("#toast").is_visible()
    names = lambda: [x.strip().replace("\n", " ") for x in pg.locator("#plist .list-item .name").all_inner_texts()]
    jump = lambda ms: pg.evaluate("window.__off += %d" % ms)

    def db_all(store, page=None):
        return (page or pg).evaluate("""(s)=>new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result;const g=d.transaction(s).objectStore(s).getAll();g.onsuccess=()=>{d.close();r(g.result)}}})""", store)

    def seed(persons=(), rides=()):
        pg.evaluate("""async([ps,rs])=>{ for(const p of ps) await AG.putPerson(p); for(const r of rs) await new Promise(f=>{const t=AG.db.transaction('rides','readwrite');t.objectStore('rides').put(r);t.oncomplete=f}) }""", [list(persons), list(rides)])

    def person(i, last, first, **kw):
        d = {"id": "00000000-0000-4000-8000-%012d" % i, "last_name": last, "first_name": first, "pickup_street": "", "pickup_zip": "", "pickup_city": "", "dest_place": "", "dest_street": "", "dest_zip": "", "dest_city": "",
             "phone": "", "usual_price_cents": None, "usual_km_m": None, "archived": False, "created_at": "2026-01-01T00:00:00.000Z", "updated_at": "2026-01-01T00:00:00.000Z",
             "schedule": {"mode": "weekly", "weekdays": [], "time_weekly": None, "from": None, "to": None, "dates": [], "time_dates": None}}
        d.update(kw); return d

    def new_person():
        goto("personnes"); tap('[data-a="newperson"]')

    def fill(**kw):
        for k, v in kw.items(): pg.fill("#f-" + k, v)

    def save(): tap('[data-a="savefiche"]')
    def errtxt(i): return pg.locator("#" + i).inner_text() if pg.locator("#" + i).is_visible() else ""
    def open_fiche(txt): goto("personnes"); tap('#plist .list-item:has-text("%s")' % txt)

    # ================= 1. Personnes au départ =================
    goto("personnes")
    ok(tag + " Personnes au départ : « 0 personne », liste vide avec message, « Nouvelle personne », pas de ligne « Archivées »", pg.locator("#pcount").inner_text() == "0 personne" and "Aucune personne pour l’instant" in pg.locator("#plist").inner_text() and pg.locator('[data-a="newperson"]').inner_text().strip() == "Nouvelle personne" and pg.locator("#archwrap").inner_text().strip() == "")
    ok(tag + " recherche : champ « Nom ou prénom » et ligne « Recherche par nom et par prénom »", pg.locator("#q").get_attribute("placeholder") == "Nom ou prénom" and pg.locator("#qnote").inner_text() == "Recherche par nom et par prénom")
    ok(tag + " au départ la base ne contient aucune personne ni course", db_all("persons") == [] and db_all("rides") == [])

    # ================= 2. fiche vide =================
    tap('[data-a="newperson"]')
    labs = pg.evaluate("[...document.querySelectorAll('#s-fiche label')].map(l=>l.textContent.trim().replace(/\\s+/g,' '))")
    ok(tag + " fiche vide : titre « Nouvelle personne », onglet Personnes allumé", cur() == "fiche" and pg.locator("#s-fiche h1").inner_text() == "Nouvelle personne" and pg.locator('.nav button.t[aria-current="page"]').inner_text().strip() == "Personnes")
    ok(tag + " fiche : mêmes champs que la maquette, dans l'ordre", labs == ["Nom", "Prénom", "Prise en charge (et retour)", "Destination habituelle", "Prix et km habituels (facultatif)", "Prix de la course (€)", "Km de la course", "Téléphone (facultatif)", "Quand", "Jours habituels", "Heure habituelle", "Du", "Au (facultatif)", "Heure pour toutes les dates"], labs)
    ok(tag + " « Quand » : « Chaque semaine » choisi, « Du » = date du jour (%s), « Au » vide, lettres L M M J V S D" % TISO, pg.locator('[data-a="fmode"][data-m="sem"].sel').count() == 1 and pg.input_value("#f-du") == TISO and pg.input_value("#f-au") == "" and "".join(x.strip() for x in pg.locator("#q-sem .days button").all_inner_texts()) == "LMMJVSD")
    ok(tag + " fiche vide : pas de « Gérer cette fiche » (rien à archiver ni supprimer)", pg.locator("#s-fiche h2").count() == 0 and pg.locator('[data-a="archiveask"]').count() == 0)
    attrs = pg.evaluate("""()=>{const g=i=>document.getElementById(i);const a=(i,n)=>g(i).getAttribute(n);return {nom:a('f-nom','autocapitalize'),pre:a('f-pre','autocapitalize'),ville:a('f-ville','autocapitalize'),lieu:a('f-lieu','autocapitalize'),
      cp:[a('f-cp','inputmode'),a('f-cp','maxlength'),a('f-cp','pattern')],lcp:a('f-lcp','inputmode'),prix:a('f-prix','inputmode'),km:a('f-km','inputmode'),tel:[g('f-tel').type,a('f-tel','inputmode')],heure:[a('f-heure','inputmode'),a('f-heure','maxlength')],heureD:a('f-heured','inputmode')}}""")
    ok(tag + " clavier : majuscules automatiques pour noms, ville et lieu ; champs numériques pour code postal, prix, km, téléphone et heure", attrs["nom"] == attrs["pre"] == attrs["ville"] == attrs["lieu"] == "words" and attrs["cp"] == ["numeric", "5", "[0-9]*"] and attrs["lcp"] == "numeric" and attrs["prix"] == attrs["km"] == "decimal" and attrs["tel"] == ["tel", "tel"] and attrs["heure"] == ["numeric", "5"] and attrs["heureD"] == "numeric", attrs)
    pg.screenshot(path=SHOTS + "/personnes_fiche_vide_%dx%d_%s.png" % (W, H, SCHEME))
    tap('[data-a="back"]')
    ok(tag + " fiche vide non touchée : « Retour » revient à la liste sans question", cur() == "personnes" and pg.locator("#confirm.on").count() == 0)
    tap('[data-a="newperson"]'); save()
    ok(tag + " « Enregistrer » sans rien : « Indique au moins un nom », rien enregistré", toast_msg() == "Indique au moins un nom" and cur() == "fiche" and db_all("persons") == [], toast_msg())

    # ================= 3. création =================
    fill(nom="Essai", pre="Un", rue="1 rue Test", cp="12345", ville="Villetest", lieu="Lieu Test", lrue="2 rue Cible", lcp="54321", lville="Cibleville", prix="12,5", km="8.5", tel="01 23 45 67 89")
    tap('[data-a="jour"][data-j="1"]'); tap('[data-a="jour"][data-j="4"]'); fill(heure="930")
    ok(tag + " lettres L et J choisies (aria-pressed)", pg.locator('[data-a="jour"][aria-pressed="true"]').count() == 2 and pg.locator('[data-a="jour"][data-j="1"][aria-pressed="true"]').count() == 1)
    pg.screenshot(path=SHOTS + "/personnes_fiche_remplie_%dx%d_%s.png" % (W, H, SCHEME))
    save()
    ok(tag + " création : retour à la liste, « Essai Un ajouté » avec « Annuler » (5 s)", cur() == "personnes" and toast_msg() == "Essai Un ajouté" and has_undo() and names() == ["Essai Un"] and pg.locator("#pcount").inner_text() == "1 personne", (toast_msg(), names()))
    rec = db_all("persons")
    r0 = rec[0] if rec else {}
    ok(tag + " rangé dans IndexedDB : une fiche, identifiant unique aléatoire, noms, adresses, téléphone", len(rec) == 1 and UUID.match(r0.get("id", "")) and r0["last_name"] == "Essai" and r0["first_name"] == "Un" and r0["pickup_street"] == "1 rue Test" and r0["pickup_zip"] == "12345" and r0["pickup_city"] == "Villetest" and r0["dest_place"] == "Lieu Test" and r0["dest_street"] == "2 rue Cible" and r0["dest_zip"] == "54321" and r0["dest_city"] == "Cibleville" and r0["phone"] == "01 23 45 67 89" and r0["archived"] is False and r0["created_at"].endswith("Z"), r0)
    ok(tag + " prix en CENTIMES (12,5 € = 1250), km en MÈTRES (8.5 km = 8500), entiers", r0.get("usual_price_cents") == 1250 and r0.get("usual_km_m") == 8500 and isinstance(r0["usual_price_cents"], int) and isinstance(r0["usual_km_m"], int), (r0.get("usual_price_cents"), r0.get("usual_km_m")))
    sch = r0.get("schedule", {})
    ok(tag + " « Quand » rangé : semaine, jours [1, 4], heure « 09:30 » (HH:MM), « Du » = aujourd'hui, « Au » vide (null), aucune date choisie", sch == {"mode": "weekly", "weekdays": [1, 4], "time_weekly": "09:30", "from": TISO, "to": None, "dates": [], "time_dates": None}, sch)
    tap('#toast [data-a="undo"]')
    ok(tag + " « Annuler » dans les 5 s : la personne ajoutée disparaît (elle était vide) de la liste et de la base", names() == [] and db_all("persons") == [], names())
    new_person(); fill(nom="Essai", pre="Un", rue="1 rue Test", cp="12345", ville="Villetest", lieu="Lieu Test", lrue="2 rue Cible", lcp="54321", lville="Cibleville", prix="12,5", km="8.5", tel="01 23 45 67 89")
    tap('[data-a="jour"][data-j="1"]'); tap('[data-a="jour"][data-j="4"]'); fill(heure="930"); save()
    pg.wait_for_timeout(5300)
    ok(tag + " au bout de 5 secondes le message disparaît (plus d'« Annuler »)", not pg.locator("#toast").is_visible())

    # ================= 4. rouvrir, modifier =================
    rid = db_all("persons")[0]["id"]
    open_fiche("Essai")
    ok(tag + " fiche d'une personne : titre « Essai Un », champs relus (prix « 12,50 », km « 8,5 », heure « 09:30 »)", pg.locator("#s-fiche h1").inner_text().replace("\n", " ").strip() == "Essai Un" and pg.input_value("#f-prix") == "12,50" and pg.input_value("#f-km") == "8,5" and pg.input_value("#f-heure") == "09:30" and pg.input_value("#f-rue") == "1 rue Test" and pg.input_value("#f-lieu") == "Lieu Test" and pg.input_value("#f-tel") == "01 23 45 67 89", pg.input_value("#f-prix"))
    ok(tag + " jours L et J allumés, « Du » conservé, « Au » vide", pg.locator('[data-a="jour"][aria-pressed="true"]').count() == 2 and pg.input_value("#f-du") == TISO and pg.input_value("#f-au") == "")
    ok(tag + " « Appeler » : lien téléphone avec les chiffres seulement", pg.locator("#f-call").get_attribute("href") == "tel:0123456789", pg.locator("#f-call").get_attribute("href"))
    ok(tag + " « Gérer cette fiche » : « Archiver cette personne » et « Supprimer cette fiche » (active : aucune course)", pg.locator("#s-fiche h2").inner_text().lower() == "gérer cette fiche" and pg.locator('[data-a="archiveask"]').count() == 1 and pg.locator('[data-a="deleteask"]').count() == 1)
    fill(ville="Autreville", prix="15.75", km="9,25"); save()
    ok(tag + " modifier (prix « 15.75 » avec un POINT, km « 9,25 » avec une virgule) : « Fiche enregistrée » sans « Annuler »", toast_msg() == "Fiche enregistrée" and not has_undo() and cur() == "personnes")
    rec = db_all("persons")
    ok(tag + " modification rangée : même identifiant, ville changée, 1575 centimes, 9250 mètres, une seule fiche, date de modification mise à jour", len(rec) == 1 and rec[0]["id"] == rid and rec[0]["pickup_city"] == "Autreville" and rec[0]["usual_price_cents"] == 1575 and rec[0]["usual_km_m"] == 9250 and rec[0]["updated_at"] > rec[0]["created_at"], rec)

    # ================= 5. validations =================
    open_fiche("Essai")
    cases = [("0", "", "zéro", "f-prix"), ("0,00", "", "zéro", "f-prix"), ("", "0", "zéro", "f-km"), ("12,345", "", "Prix invalide", "f-prix"), ("", "8,555", "Km invalides", "f-km")]
    for prix, km, word, fid in cases:
        fill(prix=prix, km=km); save()
        ok(tag + " prix « %s » / km « %s » : refusé avec un message simple (« %s »), rien enregistré, champ marqué" % (prix, km, word), word in errtxt("f-pk-err") and pg.locator("#" + fid).get_attribute("aria-invalid") == "true" and db_all("persons")[0]["usual_price_cents"] == 1575 and cur() == "fiche", errtxt("f-pk-err"))
    fill(prix="1a2,5", km="x");
    ok(tag + " lettres refusées à la frappe : « 1a2,5 » devient « 12,5 », « x » devient vide", pg.input_value("#f-prix") == "12,5" and pg.input_value("#f-km") == "")
    fill(prix="", km=""); save()
    r1 = db_all("persons")[0]
    ok(tag + " prix et km vides : enregistrés comme INCONNUS (null), jamais 0", r1["usual_price_cents"] is None and r1["usual_km_m"] is None, (r1["usual_price_cents"], r1["usual_km_m"]))
    open_fiche("Essai")
    ok(tag + " prix et km inconnus : champs vides avec « inconnu » en gris", pg.input_value("#f-prix") == "" and pg.input_value("#f-km") == "" and pg.locator("#f-prix").get_attribute("placeholder") == "inconnu")
    fill(heure="25:00"); save()
    ok(tag + " heure « 25:00 » : « Heure invalide : écris par exemple 13:00, ou laisse vide. »", errtxt("f-h-err") == "Heure invalide : écris par exemple 13:00, ou laisse vide." and cur() == "fiche", errtxt("f-h-err"))
    for typed, stored in [("13h", "13:00"), ("1300", "13:00"), ("9h5", "09:50"), ("13:45", "13:45"), ("", None)]:
        fill(heure=typed); save()
        t = db_all("persons")[0]["schedule"]["time_weekly"]
        ok(tag + " heure « %s » enregistrée « %s »" % (typed, stored), t == stored and cur() == "personnes", (t, cur()))
        open_fiche("Essai")
    fill(du="2026-12-20", au="2026-12-10"); save()
    ok(tag + " « Au » avant « Du » : message exact et rien enregistré", errtxt("f-q-err") == "La date de fin (« Au ») est avant la date de début (« Du ») : corrige l’une des deux." and cur() == "fiche", errtxt("f-q-err"))
    fill(du="2026-12-10", au="2026-12-10"); save()
    s2 = db_all("persons")[0]["schedule"]
    ok(tag + " « Au » = « Du » : accepté (bornes incluses)", s2["from"] == "2026-12-10" and s2["to"] == "2026-12-10", s2)
    open_fiche("Essai"); fill(du="", au=""); save()
    s3 = db_all("persons")[0]["schedule"]
    ok(tag + " « Du » et « Au » vides : depuis toujours, sans fin (null)", s3["from"] is None and s3["to"] is None, s3)
    open_fiche("Essai"); fill(cp="12a3b"); fill(lcp="9 8x7")
    ok(tag + " code postal : seuls les chiffres restent (« 12a3b » → « 123 »)", pg.input_value("#f-cp") == "123" and pg.input_value("#f-lcp") == "987")
    fill(tel="")
    pg.locator("#f-call").tap(); w()
    ok(tag + " « Appeler » sans numéro : « Téléphone inconnu »", toast_msg() == "Téléphone inconnu", toast_msg())
    fill(nom="")
    save()
    ok(tag + " fiche existante sans nom : « Indique au moins un nom »", toast_msg() == "Indique au moins un nom" and db_all("persons")[0]["last_name"] == "Essai")
    tap('[data-a="back"]')
    ok(tag + " fiche existante MODIFIÉE puis « Retour » : « Quitter sans enregistrer ? » (comme pour une nouvelle fiche)", pg.locator("#confirm.on").count() == 1 and pg.locator("#confirm-title").inner_text() == "Quitter sans enregistrer ?" and cur() == "fiche")
    tap("#confirm-cancel")
    ok(tag + " « Rester » : la fiche et les modifications sont toujours là", cur() == "fiche" and pg.input_value("#f-cp") == "123" and pg.input_value("#f-nom") == "")
    tap('[data-a="back"]'); tap("#confirm-ok")
    ok(tag + " « Quitter » : retour à la liste, RIEN n'a été enregistré (la fiche garde son nom d'origine)", cur() == "personnes" and db_all("persons")[0]["last_name"] == "Essai" and db_all("persons")[0]["pickup_zip"] == "12345", db_all("persons")[0]["pickup_zip"])
    # --- fiche existante : demander seulement si quelque chose a changé
    open_fiche("Essai"); tap('[data-a="back"]')
    ok(tag + " fiche existante NON modifiée puis « Retour » : aucune question", cur() == "personnes" and pg.locator("#confirm.on").count() == 0)
    open_fiche("Essai"); fill(ville="Changeville"); tap('[data-a="back"]')
    ok(tag + " fiche existante : ville changée puis « Retour » : la question est posée", pg.locator("#confirm.on").count() == 1 and cur() == "fiche")
    tap("#confirm-cancel"); fill(ville=db_all("persons")[0]["pickup_city"]); tap('[data-a="back"]')
    ok(tag + " … si on remet la valeur d'origine, plus de question (rien n'a changé)", cur() == "personnes" and pg.locator("#confirm.on").count() == 0)
    for label, action in [("un jour de la semaine (lettre)", lambda: tap('[data-a="jour"][data-j="6"]')), ("l'heure habituelle", lambda: fill(heure="22:22")), ("le mode « Dates choisies »", lambda: tap('[data-a="fmode"][data-m="dat"]')), ("le téléphone", lambda: fill(tel="0102030405")), ("une date « Au »", lambda: fill(au="2099-01-01"))]:
        open_fiche("Essai"); action(); tap('[data-a="back"]')
        ok(tag + " fiche existante : changer %s puis « Retour » : la question est posée" % label, pg.locator("#confirm.on").count() == 1 and cur() == "fiche")
        tap("#confirm-ok")
    open_fiche("Essai"); fill(ville="Changeville"); goto("bilan")
    ok(tag + " fiche existante modifiée puis un onglet de la barre du bas : même question", pg.locator("#confirm.on").count() == 1 and cur() == "fiche")
    tap("#confirm-ok")
    ok(tag + " … « Quitter » : on arrive sur le Bilan, rien n'est enregistré", cur() == "bilan" and db_all("persons")[0]["pickup_city"] != "Changeville")
    open_fiche("Essai"); fill(ville="Changeville")
    pg.evaluate("history.back()"); w()
    ok(tag + " fiche existante modifiée puis touche Retour d'Android : même question", pg.locator("#confirm.on").count() == 1 and cur() == "fiche")
    tap("#confirm-ok")
    open_fiche("Essai"); fill(ville="Changeville"); save(); tap('[data-a="back"]') if cur() == "fiche" else None
    ok(tag + " après « Enregistrer », plus de question (la fiche est enregistrée)", cur() == "personnes" and pg.locator("#confirm.on").count() == 0 and db_all("persons")[0]["pickup_city"] == "Changeville")
    open_fiche("Essai"); fill(ville="Autreville"); save()

    # ================= 6. « Quand » : dates choisies =================
    y, m = TODAY.year, TODAY.month
    new_person(); fill(nom="Essai", pre="Deux")
    tap('[data-a="jour"][data-j="2"]'); fill(heure="7:15")
    tap('[data-a="fmode"][data-m="dat"]')
    ok(tag + " « Dates choisies » : calendrier du mois, heure pour toutes les dates, « Chaque semaine » caché mais gardé", pg.locator("#q-dat").is_visible() and pg.locator("#q-sem").is_hidden() and pg.locator('[data-a="fmode"][data-m="dat"][aria-pressed="true"]').count() == 1 and pg.locator("#f-dates .calgrid .cell").count() == len(month_dates(y, m)))
    ok(tag + " compteur au départ : « 0 jour choisi »", pg.locator("#f-count").inner_text() == "0 jour choisi")
    past = TODAY.day - 1
    ok(tag + " pas de jours passés : %d jour(s) désactivé(s) avant aujourd'hui, aujourd'hui entouré" % past, pg.locator("#f-dates .cell:disabled").count() == past and pg.locator("#f-dates .cell.today").count() == 1, pg.locator("#f-dates .cell:disabled").count())
    if past:
        pg.evaluate("document.querySelector('#f-dates .cell:disabled').click()"); w()
        ok(tag + " un jour passé ne peut pas être coché", pg.locator("#f-count").inner_text() == "0 jour choisi")
    wk = [d for d in month_dates(y, m) if d >= TODAY and d.isoweekday() <= 5]
    tap('[data-a="fshort"][data-j="0"]')
    ok(tag + " « Lun à ven » : coche les jours de semaine à partir d'aujourd'hui dans le mois (%d)" % len(wk), pg.locator("#f-dates .cell.sel").count() == len(wk) and pg.locator("#f-count").inner_text() == ("%d jours choisis" % len(wk) if len(wk) > 1 else "%d jour choisi" % len(wk)), pg.locator("#f-count").inner_text())
    tap('[data-a="fshort"][data-j="0"]')
    ok(tag + " « Lun à ven » une seconde fois : décoche tout", pg.locator("#f-dates .cell.sel").count() == 0)
    wed = [d for d in month_dates(y, m) if d >= TODAY and d.isoweekday() == 3]
    tap('#f-dates [data-a="fshort"][data-j="3"]')
    ok(tag + " lettre M (mercredi) : tous les mercredis du mois à partir d'aujourd'hui (%d), lettre allumée si au moins un" % len(wed), pg.locator("#f-dates .cell.sel").count() == len(wed) and (pg.locator('#f-dates [data-a="fshort"][data-j="3"][aria-pressed="true"]').count() == (1 if wed else 0)))
    ny, nm = next_month(y, m)
    tap('[data-a="fmonth"][data-d="1"]')
    ok(tag + " flèche de mois suivant : le mois suivant s'affiche, aucun jour désactivé", pg.locator("#f-dates .monthnav .lbl").inner_text().lower().startswith(["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"][nm - 1]) and pg.locator("#f-dates .cell:disabled").count() == 0)
    wk2 = [d for d in month_dates(ny, nm) if d.isoweekday() <= 5]
    tap('[data-a="fshort"][data-j="0"]')
    tot = len(wed) + len(wk2)
    ok(tag + " compteur sur tous les mois : %d jours choisis (mercredis de ce mois + jours de semaine du mois suivant)" % tot, pg.locator("#f-count").inner_text() == "%d jours choisis" % tot, pg.locator("#f-count").inner_text())
    tap('[data-a="fmonth"][data-d="-1"]')
    fill(heured="20h")
    tap('[data-a="fmode"][data-m="sem"]')
    ok(tag + " retour à « Chaque semaine » sans rien perdre : lettre M (mardi), heure 7:15", pg.locator('#q-sem [data-a="jour"][data-j="2"][aria-pressed="true"]').count() == 1 and pg.input_value("#f-heure") == "7:15" and pg.locator("#q-sem").is_visible())
    tap('[data-a="fmode"][data-m="dat"]')
    ok(tag + " … et les dates cochées et l'heure des dates sont toujours là", pg.input_value("#f-heured") == "20h" and pg.locator("#f-count").inner_text() == "%d jours choisis" % tot)
    save()
    rec2 = [x for x in db_all("persons") if x["first_name"] == "Deux"][0]
    exp_dates = sorted([d.isoformat() for d in wed] + [d.isoformat() for d in wk2])
    ok(tag + " « Dates choisies » rangé : mode « dates », les deux jeux de données gardés (jours [2] + « 07:15 », et %d dates + « 20:00 »)" % tot, rec2["schedule"]["mode"] == "dates" and rec2["schedule"]["weekdays"] == [2] and rec2["schedule"]["time_weekly"] == "07:15" and rec2["schedule"]["dates"] == exp_dates and rec2["schedule"]["time_dates"] == "20:00", rec2["schedule"])
    open_fiche("Deux")
    ok(tag + " rouvert : « Dates choisies » affiché, compteur et heures relus", pg.locator('[data-a="fmode"][data-m="dat"].sel').count() == 1 and pg.locator("#f-count").inner_text() == "%d jours choisis" % tot and pg.input_value("#f-heured") == "20:00" and pg.input_value("#f-heure") == "07:15")
    pg.screenshot(path=SHOTS + "/personnes_quand_dates_%dx%d_%s.png" % (W, H, SCHEME))
    tap('[data-a="back"]')

    # ================= 7. doublon, quitter sans enregistrer =================
    new_person(); fill(nom="essai", pre="UN")
    ok(tag + " doublon de nom (sans tenir compte des majuscules) : « Une fiche « Essai Un » existe déjà. Tu peux quand même enregistrer. »", pg.locator("#dup-warn").is_visible() and pg.locator("#dup-warn").inner_text() == "Une fiche « Essai Un » existe déjà. Tu peux quand même enregistrer.", pg.locator("#dup-warn").inner_text())
    fill(nom="Éssai", pre="Un")
    ok(tag + " … ni des accents (« Éssai » = « Essai »)", pg.locator("#dup-warn").is_visible())
    fill(pre="Trois")
    ok(tag + " autre prénom : plus d'avertissement", pg.locator("#dup-warn").is_hidden())
    tap('[data-a="back"]')
    ok(tag + " « Retour » sur une nouvelle fiche remplie : « Quitter sans enregistrer ? » (« Quitter » / « Rester »)", pg.locator("#confirm.on").count() == 1 and pg.locator("#confirm-title").inner_text() == "Quitter sans enregistrer ?" and pg.locator("#confirm-ok").inner_text() == "Quitter" and pg.locator("#confirm-cancel").inner_text() == "Rester" and pg.locator("#confirm-text").inner_text() == "Ce que tu as saisi sera perdu.")
    tap("#confirm-cancel")
    ok(tag + " « Rester » : la fiche et la saisie sont toujours là", cur() == "fiche" and pg.input_value("#f-nom") == "Éssai" and pg.input_value("#f-pre") == "Trois")
    goto("bilan")
    ok(tag + " changer d'onglet pendant la saisie : même question", pg.locator("#confirm.on").count() == 1 and cur() == "fiche")
    tap("#confirm-ok")
    ok(tag + " « Quitter » : on arrive sur le Bilan, rien n'est enregistré", cur() == "bilan" and len(db_all("persons")) == 2, (cur(), len(db_all("persons"))))
    new_person(); fill(nom="Quitte")
    pg.evaluate("history.back()"); w()
    ok(tag + " touche Retour d'Android sur une fiche remplie : même question (la fiche ne se ferme pas toute seule)", cur() == "fiche" and pg.locator("#confirm.on").count() == 1)
    tap("#confirm-ok")
    ok(tag + " … « Quitter » : retour à la liste, aucune fiche « Quitte » créée", cur() == "personnes" and "Quitte" not in " ".join(names()))
    new_person(); fill(nom="Essai", pre="Un"); save()
    ok(tag + " un doublon peut quand même être enregistré (non bloquant)", sorted(names()) == ["Essai Deux", "Essai Un", "Essai Un"], names())
    tap('#plist .list-item:has-text("Essai Un") >> nth=1');
    ok(tag + " les deux « Essai Un » ont des identifiants différents", len({x["id"] for x in db_all("persons") if x["first_name"] == "Un"}) == 2)
    # on supprime ce doublon vide pour la suite
    tap('[data-a="deleteask"]'); tap("#confirm-ok")
    ok(tag + " doublon vide supprimé (pour la suite)", len(db_all("persons")) == 2, len(db_all("persons")))

    # ================= 8. recherche =================
    seed([person(11, "Éloïse", "Zeta"), person(12, "Beta", "Élodie"), person(13, "Gamma", "Rose-Lise")]); pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    goto("personnes")
    ok(tag + " liste triée par nom (sans tenir compte des accents) : Beta, Éloïse, Essai (deux), Gamma", names() == ["Beta Élodie", "Essai Deux", "Essai Un", "Éloïse Zeta", "Gamma Rose-Lise"] or names() == ["Beta Élodie", "Éloïse Zeta", "Essai Deux", "Essai Un", "Gamma Rose-Lise"], names())
    pg.fill("#q", "eloi"); w()
    ok(tag + " recherche « eloi » trouve « Éloïse » (accents et majuscules ignorés), mot surligné", names() == ["Éloïse Zeta"] and pg.locator("#plist mark").count() == 1 and pg.locator("#qnote").inner_text() == "1 résultat pour « eloi »", (names(), pg.locator("#qnote").inner_text()))
    pg.fill("#q", "elod"); w()
    ok(tag + " recherche aussi par PRÉNOM (« elod » trouve « Beta Élodie »)", names() == ["Beta Élodie"])
    pg.fill("#q", "rose-l"); w()
    ok(tag + " recherche d'un prénom composé", names() == ["Gamma Rose-Lise"])
    pg.fill("#q", "ess"); w()
    ok(tag + " « ess » : 2 résultats", len(names()) == 2 and pg.locator("#qnote").inner_text() == "2 résultats pour « ess »")
    pg.fill("#q", "zzz"); w()
    ok(tag + " rien ne correspond : « Personne ne correspond. »", "Personne ne correspond." in pg.locator("#plist").inner_text())
    pg.fill("#q", ""); w()

    # ================= 9. archiver, restaurer =================
    open_fiche("Gamma")
    tap('[data-a="archiveask"]')
    ok(tag + " « Archiver cette personne » : confirmation « Archiver Gamma Rose-Lise ? » avec le texte de la maquette", pg.locator("#confirm-title").inner_text() == "Archiver Gamma Rose-Lise ?" and pg.locator("#confirm-text").inner_text() == "Il ne s’affichera plus dans les listes. Son historique reste." and pg.locator("#confirm-ok").inner_text() == "Archiver")
    tap("#confirm-ok")
    ok(tag + " archivée : sort de la liste, message « Gamma Rose-Lise archivé » avec « Annuler », ligne « Archivées (1) »", cur() == "personnes" and "Gamma Rose-Lise" not in names() and toast_msg() == "Gamma Rose-Lise archivé" and has_undo() and pg.locator("#archwrap").inner_text().strip().startswith("Archivées (1)") and pg.locator("#pcount").inner_text() == "4 personnes")
    tap('#toast [data-a="undo"]')
    ok(tag + " « Annuler » : la personne revient (5 secondes)", "Gamma Rose-Lise" in names() and pg.locator("#archwrap").inner_text().strip() == "")
    open_fiche("Gamma"); tap('[data-a="archiveask"]'); tap("#confirm-ok")
    tap('[data-a="archshow"]')
    ok(tag + " « Archivées (1) » : liste archivée SUR LA MÊME PAGE (pas de nouvelle page), « 1 archivée », « Restaurer », « Personnes actives », recherche cachée", cur() == "personnes" and pg.locator("#pcount").inner_text() == "1 archivée" and names() == ["Gamma Rose-Lise"] and pg.locator('[data-a="restore"]').count() == 1 and pg.locator('[data-a="restore"]').inner_text() == "Restaurer" and pg.locator('[data-a="archhide"]').inner_text().strip() == "Personnes actives" and pg.locator(".search").is_hidden() and pg.locator('[data-a="newperson"]').is_hidden())
    ok(tag + " la personne archivée est rangée archived = true avec une date, rien d'effacé", [x for x in db_all("persons") if x["last_name"] == "Gamma"][0]["archived"] is True and [x for x in db_all("persons") if x["last_name"] == "Gamma"][0]["archived_at"])
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w(); goto("personnes")
    ok(tag + " après fermeture et réouverture : toujours archivée (absente de la liste active)", "Gamma Rose-Lise" not in names())
    tap('[data-a="archshow"]'); tap('[data-a="restore"]')
    ok(tag + " « Restaurer » : « … de nouveau dans les listes. » avec « Annuler », retour dans la liste active", toast_msg() == "Gamma Rose-Lise de nouveau dans les listes." and has_undo() and pg.locator("#pcount").inner_text() == "0 archivée" and "Aucune personne archivée." in pg.locator("#plist").inner_text(), (toast_msg(), pg.locator("#pcount").inner_text()))
    tap('[data-a="archhide"]')
    ok(tag + " « Personnes actives » : retour à la liste (Gamma est de nouveau là)", "Gamma Rose-Lise" in names() and pg.locator("#pcount").inner_text() == "5 personnes" and pg.locator(".search").is_visible(), (names(), pg.locator("#pcount").inner_text()))

    # ================= 10. supprimer =================
    seed([person(21, "Jours", "Seul", schedule={"mode": "weekly", "weekdays": [1], "time_weekly": None, "from": None, "to": None, "dates": [], "time_dates": None}), person(22, "Vide", "Totalement"),
          person(23, "Notee", "Une"), person(24, "Notee", "Deux"), person(25, "Prevue", "Seule")],
         [{"id": "r1", "person_id": "00000000-0000-4000-8000-000000000023", "date": "2026-01-05", "status": "done"},
          {"id": "r2", "person_id": "00000000-0000-4000-8000-000000000024", "date": "2026-01-05", "status": "done"},
          {"id": "r3", "person_id": "00000000-0000-4000-8000-000000000024", "date": "2026-01-06", "status": "not_done"},
          {"id": "r4", "person_id": "00000000-0000-4000-8000-000000000025", "date": "2999-01-05", "status": None}])
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.evaluate("window.__ag.ready"); w()
    open_fiche("Vide")
    tap('[data-a="deleteask"]')
    ok(tag + " personne vide : « Supprimer Vide Totalement ? » et « Elle est vide, rien d’autre n’est perdu. »", pg.locator("#confirm-title").inner_text() == "Supprimer Vide Totalement ?" and pg.locator("#confirm-text").inner_text() == "Elle est vide, rien d’autre n’est perdu." and pg.locator("#confirm-ok").inner_text() == "Supprimer")
    tap("#confirm-cancel")
    ok(tag + " « Annuler » dans la confirmation : rien n'est supprimé", len([x for x in db_all("persons") if x["last_name"] == "Vide"]) == 1 and cur() == "fiche")
    tap('[data-a="deleteask"]'); tap("#confirm-ok")
    ok(tag + " supprimée « pour de bon » : plus dans la liste ni dans la base, message « … supprimée » avec « Annuler »", cur() == "personnes" and "Vide Totalement" not in names() and not [x for x in db_all("persons") if x["last_name"] == "Vide"] and toast_msg() == "Vide Totalement supprimée" and has_undo())
    tap('#toast [data-a="undo"]')
    back_rec = [x for x in db_all("persons") if x["last_name"] == "Vide"]
    ok(tag + " « Annuler » dans les 5 s : la fiche revient identique (même identifiant)", len(back_rec) == 1 and back_rec[0]["id"] == "00000000-0000-4000-8000-000000000022" and "Vide Totalement" in names())
    open_fiche("Vide"); tap('[data-a="deleteask"]'); tap("#confirm-ok"); pg.wait_for_timeout(5300)
    ok(tag + " sans « Annuler » : la suppression est définitive (base vide de cette fiche)", not [x for x in db_all("persons") if x["last_name"] == "Vide"] and not pg.locator("#toast").is_visible())
    open_fiche("Jours")
    tap('[data-a="deleteask"]')
    ok(tag + " personne avec jours habituels : « Ses jours habituels seront supprimés. »", pg.locator("#confirm-text").inner_text() == "Ses jours habituels seront supprimés.", pg.locator("#confirm-text").inner_text())
    tap("#confirm-cancel"); tap('[data-a="back"]')
    open_fiche("Prevue")
    tap('[data-a="deleteask"]')
    ok(tag + " personne avec une course prévue (pas notée) : « Sa course prévue sera supprimée. »", pg.locator("#confirm-text").inner_text() == "Sa course prévue sera supprimée.", pg.locator("#confirm-text").inner_text())
    tap("#confirm-ok")
    ok(tag + " … la fiche ET sa course prévue sont effacées de la base", not [x for x in db_all("persons") if x["last_name"] == "Prevue"] and not [r for r in db_all("rides") if r["id"] == "r4"])
    tap('#toast [data-a="undo"]')
    ok(tag + " « Annuler » rend la fiche et sa course prévue", [x for x in db_all("persons") if x["last_name"] == "Prevue"] and [r for r in db_all("rides") if r["id"] == "r4"])
    open_fiche("Notee Une")
    dis = pg.locator("#s-fiche .list-item[disabled]")
    ok(tag + " 1 course déjà notée : « Supprimer cette fiche » grisée avec « Impossible : 1 course déjà notée. »", dis.count() == 1 and "Supprimer cette fiche" in dis.inner_text() and "Impossible : 1 course déjà notée." in dis.inner_text() and pg.locator('[data-a="deleteask"]').count() == 0 and pg.locator("#s-fiche .list-item[disabled]").get_attribute("aria-disabled") == "true", dis.inner_text())
    pg.evaluate("document.querySelector('#s-fiche .list-item[disabled]').click()"); w()
    ok(tag + " … toucher le bouton grisé ne fait rien (pas de confirmation)", pg.locator("#confirm.on").count() == 0)
    ok(tag + " … et « Archiver » reste possible", pg.locator('[data-a="archiveask"]').count() == 1)
    tap('[data-a="back"]'); open_fiche("Notee Deux")
    ok(tag + " 2 courses déjà notées (faite et pas faite) : « Impossible : 2 courses déjà notées. »", "Impossible : 2 courses déjà notées." in pg.locator("#s-fiche .list-item[disabled]").inner_text())
    refus = pg.evaluate("AG.deletePerson('00000000-0000-4000-8000-000000000024')")
    ok(tag + " même en forçant par le code : la suppression est refusée (refused = 2), rien n'est effacé", refus == {"refused": 2} and len([x for x in db_all("persons") if x["last_name"] == "Notee"]) == 2 and len(db_all("rides")) >= 3, refus)
    tap('[data-a="back"]')

    # ================= 11. persistance, hors connexion =================
    before = db_all("persons"); n0 = len(before)
    pg.close(); pg = cx.new_page(); pg.on("pageerror", lambda e: errs.append("pageerror " + str(e))); boot()
    goto("personnes")
    ok(tag + " fermeture et réouverture de l'appli : les %d personnes sont toujours là, dans le même ordre" % n0, len(names()) == len([x for x in before if not x["archived"]]) and pg.locator("#pcount").inner_text() == "%d personnes" % len([x for x in before if not x["archived"]]), names())
    pg.wait_for_function("navigator.serviceWorker.getRegistration().then(r=>!!(r&&r.active))"); pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready"); pg.wait_for_timeout(400)
    cx.set_offline(True)
    pg.reload(); pg.wait_for_function("window.__ag && window.__ag.ready", timeout=15000); pg.evaluate("window.__ag.ready"); w()
    goto("personnes")
    ok(tag + " MODE AVION : l'appli s'ouvre et la liste des personnes s'affiche", len(names()) == len([x for x in before if not x["archived"]]), names())
    tap('#plist .list-item:has-text("Essai Un")')
    ok(tag + " MODE AVION : la fiche s'ouvre avec ses données", pg.input_value("#f-nom") == "Essai" and pg.input_value("#f-rue") == "1 rue Test")
    fill(ville="Horsligne"); save()
    ok(tag + " MODE AVION : une modification s'enregistre", [x for x in db_all("persons") if x["first_name"] == "Un"][0]["pickup_city"] == "Horsligne")
    cx.set_offline(False)

    # ================= 12. masquage =================
    new_person(); fill(nom="Secret", pre="Nom", rue="3 rue Cachée", ville="Villecachée", lieu="Lieu Secret", prix="21")
    tap('.screen.on [data-a="hide"]')
    vt = pg.evaluate("document.getElementById('veil').innerText.trim()")
    pts = pg.evaluate("""()=>{let n=0,c=0;for(let x=10;x<innerWidth;x+=Math.floor(innerWidth/6))for(let y=10;y<innerHeight;y+=Math.floor(innerHeight/8)){n++;const e=document.elementFromPoint(x,y);if(e&&e.closest('#veil'))c++}return [n,c]}""")
    ok(tag + " œil avec la fiche ouverte : écran neutre « Agenda » seul (aucun nom ni adresse), plein écran, fiche inerte et cachée aux lecteurs d'écran", masked() and vt == "Agenda" and pts[0] == pts[1] and pg.evaluate("document.getElementById('views').inert && document.getElementById('views').getAttribute('aria-hidden')==='true'"), (vt, pts))
    pg.locator("#veil").tap(); w()
    ok(tag + " un toucher rouvre : la saisie est toujours là", not masked() and cur() == "fiche" and pg.input_value("#f-nom") == "Secret" and pg.input_value("#f-rue") == "3 rue Cachée")
    jump(125000); pg.wait_for_timeout(1700)
    vt = pg.evaluate("document.getElementById('veil').innerText.trim()")
    ok(tag + " 2 minutes simulées avec la fiche ouverte : masqué tout seul, rien de lisible", masked() and vt == "Agenda", vt)
    pg.locator("#veil").tap(); w()
    ok(tag + " rouvert : même fiche, même saisie", cur() == "fiche" and pg.input_value("#f-lieu") == "Lieu Secret")
    tap('[data-a="back"]')
    ok(tag + " fenêtre « Quitter sans enregistrer ? » ouverte", pg.locator("#confirm.on").count() == 1)
    pg.evaluate("document.querySelector('.screen.on [data-a=\"hide\"]').click()"); w()
    vis = pg.evaluate("(()=>{const r=document.querySelector('#confirm .panel').getBoundingClientRect();const e=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return !!e&&!!e.closest('#veil')})()")
    ok(tag + " masqué avec la fenêtre de confirmation ouverte : elle est couverte et inerte", masked() and vis and pg.evaluate("document.getElementById('confirm').inert"), vis)
    pg.locator("#veil").tap(); w(); tap("#confirm-ok")
    goto("personnes")
    tap('.screen.on [data-a="hide"]')
    vt = pg.evaluate("document.getElementById('veil').innerText.trim()")
    ok(tag + " liste des personnes masquée : « Agenda » seul, aucun nom lisible", masked() and vt == "Agenda" and not re.search(r"Essai|Beta|Gamma", vt))
    pg.locator("#veil").tap(); w()
    open_fiche("Gamma"); tap('[data-a="archiveask"]'); tap("#confirm-ok")
    ok(tag + " message avec « Annuler » affiché", has_undo())
    tap('.screen.on [data-a="hide"]')
    ok(tag + " œil : le message (qui contient un nom) disparaît avec l'écran masqué", masked() and not pg.locator("#toast").is_visible())
    pg.locator("#veil").tap(); w()

    # ================= 13. zones de toucher et débordements =================
    AUD = """()=>{const app=document.getElementById('app').getBoundingClientRect(), out=[];
      document.querySelectorAll('.screen.on button, .screen.on a.btn, .screen.on input').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width||e.closest('[hidden]'))return;
        if(r.height<43.5||r.width<43.5)out.push('PETIT '+(e.id||e.dataset.a||e.textContent.trim().slice(0,14))+' '+r.width.toFixed(0)+'x'+r.height.toFixed(0));
        if(r.right>app.right+.5||r.left<app.left-.5)out.push('DEBORDE '+(e.id||e.dataset.a))});
      const c=document.querySelector('.screen.on .content');if(c.scrollWidth>c.clientWidth+1)out.push('LARGEUR '+c.scrollWidth+'>'+c.clientWidth);return out}"""
    goto("personnes"); z = pg.evaluate(AUD)
    ok(tag + " Personnes : zones de 44 px, rien qui déborde", not z, z)
    pg.screenshot(path=SHOTS + "/personnes_liste_%dx%d_%s.png" % (W, H, SCHEME))
    tap('#plist .list-item:has-text("Essai Un")'); z = pg.evaluate(AUD)
    ok(tag + " Fiche (semaine) : zones de 44 px, rien qui déborde ni défile en largeur", not z, z)
    tap('[data-a="fmode"][data-m="dat"]'); z = pg.evaluate(AUD)
    ok(tag + " Fiche (dates choisies) : zones de 44 px, rien qui déborde (le calendrier tient à %d px)" % W, not z, z)
    pg.evaluate("document.querySelector('#s-fiche .content').scrollTop=99999"); pg.wait_for_timeout(200)
    pg.screenshot(path=SHOTS + "/personnes_fiche_bas_%dx%d_%s.png" % (W, H, SCHEME))
    ok(tag + " « Enregistrer » et « Gérer cette fiche » atteignables en bas de la fiche, au-dessus de la barre", pg.evaluate("(()=>{const b=document.querySelector('[data-a=archiveask]').getBoundingClientRect(),n=document.querySelector('.nav').getBoundingClientRect();return b.bottom<=n.top+.5&&b.height>=44})()"))
    tap('[data-a="back"]'); tap("#confirm-ok")      # on a changé le mode pour le contrôle : « Quitter sans enregistrer ? » est posée
    goto("personnes"); tap('[data-a="archshow"]'); z = pg.evaluate(AUD)
    ok(tag + " liste archivée : zones de 44 px", not z, z); tap('[data-a="archhide"]')

    # ================= 14. les autres écrans n'ont pas bougé =================
    for t, title in [("aujourdhui", "Aujourd’hui"), ("essence", "Essence")]:
        goto(t); ok(tag + " « %s » : toujours seulement son titre" % title, pg.locator(".screen.on").inner_text().strip() == title)
    goto("bilan"); ok(tag + " « Bilan » : toujours son titre et la ligne « Réglages »", pg.locator(".screen.on").inner_text().strip() == "Bilan\nRéglages")
    tap('[data-a="reglages"]')
    ok(tag + " Réglages : version 0.2.1 et structure n° 2", pg.locator("#rg-version").inner_text() == re.search(r"APP_VERSION\s*=\s*'([^']+)'", (ROOT / "version.js").read_text(encoding="utf-8")).group(1) == "0.2.1" and pg.locator("#rg-schema").inner_text() == "2")

    # ================= 15. migration 1 → 2 =================
    mig = pg.evaluate("""async()=>{ const name='agenda-essai-v1v2';
      const del=()=>new Promise(r=>{const q=indexedDB.deleteDatabase(name);q.onsuccess=q.onerror=q.onblocked=()=>r()}); await del();
      const real=__ag.migrations;
      let d=await __ag.openDatabase(name,real.slice(0,1)); const s1=[...d.objectStoreNames].sort(), v1=d.version;
      await __ag.dbPut(d,'settings','idle_sec',600); await __ag.dbPut(d,'meta','persist_asked','2026-10-01T00:00:00Z'); d.close();
      d=await __ag.openDatabase(name,real); const s2=[...d.objectStoreNames].sort(), v2=d.version;
      const out={s1,v1,s2,v2,idle:await __ag.dbGet(d,'settings','idle_sec'),asked:await __ag.dbGet(d,'meta','persist_asked'),sv:await __ag.dbGet(d,'meta','schema_version'),created:!!(await __ag.dbGet(d,'meta','created_at'))};
      const tx=d.transaction(['persons','rides']); out.persons=await new Promise(r=>{const g=tx.objectStore('persons').getAll();g.onsuccess=()=>r(g.result.length)}); out.rides=await new Promise(r=>{const g=tx.objectStore('rides').getAll();g.onsuccess=()=>r(g.result.length)});
      out.idx=[...tx.objectStore('rides').indexNames]; out.keyPath=tx.objectStore('rides').index('person_id').keyPath; out.pk=[tx.objectStore('persons').keyPath,tx.objectStore('rides').keyPath]; d.close(); await del(); return out }""")
    ok(tag + " migration 1 → 2 sur une base d'essai : structure 1 avant (meta, settings), structure 2 après (+ persons, rides)", mig["s1"] == ["meta", "settings"] and mig["v1"] == 1 and mig["s2"] == ["meta", "persons", "rides", "settings"] and mig["v2"] == 2, mig)
    ok(tag + " … les données de la version 1 sont gardées (réglage 600, « stockage demandé », date de création) et le numéro noté passe à 2", mig["idle"] == 600 and mig["asked"] == "2026-10-01T00:00:00Z" and mig["sv"] == 2 and mig["created"], mig)
    ok(tag + " … les nouveaux magasins sont vides, courses indexées par personne (person_id), clé = id", mig["persons"] == 0 and mig["rides"] == 0 and mig["idx"] == ["person_id"] and mig["keyPath"] == "person_id" and mig["pk"] == ["id", "id"], mig)
    b.close()

    # vraie base de la version 0.1 sur le téléphone de Pascal : on la crée à l'identique AVANT d'ouvrir l'appli 0.2
    b2 = p.chromium.launch(channel="msedge", headless=True)
    cx2 = b2.new_context(viewport={"width": W, "height": H}, has_touch=True, is_mobile=True, color_scheme=SCHEME, service_workers="allow")
    cx2.add_init_script("window.__pc=0; if(navigator.storage){ navigator.storage.persist=function(){window.__pc++;return Promise.resolve(true)}; navigator.storage.persisted=function(){return Promise.resolve(false)} }")
    pm = cx2.new_page(); perr = []; pm.on("pageerror", lambda e: perr.append(str(e)))
    pm.goto(BASE + "manifest.json")
    pm.evaluate("""new Promise(r=>{const q=indexedDB.open('agenda',1);q.onupgradeneeded=()=>{const d=q.result;d.createObjectStore('meta',{keyPath:'key'});d.createObjectStore('settings',{keyPath:'key'});
      const t=q.transaction;t.objectStore('meta').put({key:'created_at',value:'2026-10-07T08:00:00.000Z'});t.objectStore('meta').put({key:'schema_version',value:1});t.objectStore('meta').put({key:'persist_asked',value:'2026-10-07T08:00:00.000Z'});t.objectStore('settings').put({key:'idle_sec',value:60})};
      q.onsuccess=()=>{q.result.close();r()}})""")
    boot(pm)
    info = pm.evaluate("""new Promise(r=>{const q=indexedDB.open('agenda');q.onsuccess=()=>{const d=q.result,v=d.version,s=[...d.objectStoreNames].sort();const g=d.transaction('meta').objectStore('meta').get('schema_version');g.onsuccess=()=>{const h=d.transaction('meta').objectStore('meta').get('created_at');h.onsuccess=()=>{d.close();r({v,s,sv:g.result.value,created:h.result.value})}}}})""")
    ok(tag + " VRAIE base de la version 0.1 (structure 1) ouverte par l'appli 0.2 : passe à la structure 2, ses données restent (date de création d'origine)", info["v"] == 2 and info["s"] == ["meta", "persons", "rides", "settings"] and info["sv"] == 2 and info["created"] == "2026-10-07T08:00:00.000Z", info)
    ok(tag + " … le réglage de masquage (1 minute) est conservé, le stockage persistant n'est PAS redemandé, aucune personne inventée", pm.evaluate("__ag.idle") == 60 and pm.evaluate("window.__pc") == 0 and pm.evaluate("__ag.people.length") == 0 and not perr, (pm.evaluate("__ag.idle"), pm.evaluate("window.__pc"), perr))
    b2.close()

    # ================= 16. général =================
    ok(tag + " aucune erreur JavaScript ni message d'erreur dans la console", not errs, errs)
    outside = [u for u in reqs if not u.startswith(BASE) and not u.startswith("data:") and not u.startswith("blob:")]
    ok(tag + " aucune requête hors de l'appli (%d requêtes, toutes vers le serveur local)" % len(reqs), not outside, outside)
    srv.shutdown()
print("TOTAL", total, "ECHECS", fails)
