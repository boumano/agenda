# Agenda : notes (étapes 1 à 5)

État au 9 octobre 2026 : **version 0.6.1, structure des données n° 5**. Dossier : `agenda/` (son propre dépôt git, publié sur GitHub Pages).
Plan de référence : `PLAN_VRAIE_VERSION.md` (dans le dossier de la maquette), étapes 1 à 5.
**Rien de réel dans ce dossier** : aucune donnée de personne, ni réelle ni fictive (l'appli démarre vide), aucun nom, aucune adresse, aucun téléphone. La maquette reste la référence et n'est pas copiée ici. Les contrôles automatiques n'emploient que de faux noms (« Essai », « Beta », etc.).

## Ce qui est construit

| Fichier | Rôle |
|---|---|
| `index.html` | La page : écrans Aujourd'hui, Personnes, Bilan, Essence, Fiche, Réglages, barre du bas à 4 boutons, fenêtre de confirmation, écran neutre « Agenda ». |
| `style.css` | Styles repris de la maquette (palette sombre / claire automatiques, bandeau, barre du bas, œil, boutons, fiche, calendrier). Toutes les couleurs sont définies une seule fois, en haut. |
| `app.js` | Écrans et comportements : Personnes, Fiche, œil et masquage automatique, Réglages, message de mise à jour. |
| `db.js` | **Un seul endroit** qui lit et écrit dans IndexedDB : ouverture, migrations, personnes, courses, journal de mise à jour, suppression sûre. |
| `rides.js` | La **logique des courses**, sans écran ni stockage : cartes prévues calculées à partir des fiches, création d'une course (valeurs copiées), état d'un jour, **totaux d'un mois** et **vue jour par jour**. |
| `fuel.js` | La **logique des pleins d'essence**, sans écran ni stockage : calcul du troisième chiffre, lecture « virgule ou point », 0 refusé, conversion en entiers (millilitres, millièmes d'euro, centimes), totaux du mois (valeurs inconnues comptées à part). |
| `sw.js` | Service worker : garde les fichiers sur le téléphone pour que l'appli s'ouvre sans internet. Ne remplace jamais une version tout seul. |
| `version.js` | **Le seul endroit** où est écrit le numéro de version (`0.6.1`). Les « tampons » (1re ligne de chaque fichier JavaScript, variable `--ag-version` de `style.css`, balise `ag-version` de `index.html`) en sont des copies, écrites par `python verifications/sync_version.py` (à lancer après avoir changé le numéro ; `--check` vérifie). |
| `garde.js` | La **garde**, chargée en premier : note dans le journal les erreurs JavaScript, vérifie que tous les fichiers sont de la même version, affiche « Un problème est survenu à l’affichage » + bouton « Recharger » au lieu d’un écran figé. |
| `manifest.json`, `icon.svg`, `icon-192.png`, `icon-512.png` | Nom (« Agenda »), couleurs, icônes : ce qui permet à Chrome de proposer « Installer ». |
| `verifications/verif_coquille.py` | Contrôles de la coquille (71) : fichiers, manifeste, service worker, hors connexion, version, stockage, migration, œil, masquage, mise à jour, barre du bas. |
| `verifications/verif_personnes.py` | Contrôles de l'étape 2 (140) : personnes, fiche, « Quand », « Quitter sans enregistrer ? », archivage, suppression, migration 1 → 2, masquage. |
| `verifications/verif_miseajour.py` | Contrôles du correctif 0.2.1 (19) : ancienne page qui garde la base ouverte pendant une mise à niveau, message de blocage, base pas prête après 5 s, lâcher de connexion (versionchange), vraie mise à jour avec migration 3 → 4 sur une copie d'essai, un seul rechargement. |
| `verifications/verif_courses.py` | Étape 3, écran Aujourd'hui (71) : cartes prévues, création à la première action, fait / pas fait / annuler, changer ce jour, ajouter une course, montant et km, fiche qui ne réécrit rien, archivage, persistance, hors connexion, masquage, changement d'heure du 25 octobre 2026. |
| `verifications/verif_calendrier.py` | Calendrier d'une personne (68) : lien dans la fiche, résumé du mois, états des jours, panneau d'un jour, « Pas de course », corbeille, suppression d'une personne, masquage. |
| `verifications/verif_maj030.py` | Mise à jour **réelle** 0.2.1 → version actuelle (fichiers de l'ancienne version tirés de git, structure 2 → 3, 2e page ouverte) et journal de mise à jour (28). |
| `verifications/verif_bilan.py` | Étape 4, Bilan (75) : noms complets, personne touchable → calendrier, retour selon l'origine, totaux par mois et par personne, prix ou km inconnus, corbeille, « pas fait », cartes jamais touchées, jour par jour, archivée, « changé », 25 octobre 2026, masquage, hors connexion, 6 048 courses fictives (lecture par l'index, temps d'affichage), rien pour le père. |
| `verifications/verif_essence.py` | Étape 5, page Essence : ajout, modification, corbeille + « Annuler », calculs, « inconnu » et totaux partiels, changement de mois, virgule / point, 0 refusé, quitter sans enregistrer, masquage (formulaire ouvert compris), persistance, hors connexion, 24-25-26 octobre 2026. |
| `verifications/verif_maj050.py` | Mise à jour **réelle** 0.4.1 → 0.5.0 (fichiers de l'ancienne version tirés de git, commit 886bcbd, structure 3 → 4, 2e page ouverte) et contenu du « Journal de mise à jour ». |
| `verifications/verif_cache_coherent.py` | Cache cohérent après « Mettre à jour » (36) : octets de chaque fichier servi, réseau lent / coupé, 2e page, installation interrompue. `NEW_REF=HEAD` le rejoue sur une autre version publiée (preuve avant correction). |
| `verifications/verif_garde.py` | La garde 0.5.1 (25) : tampons, « Écran affiché », erreurs, fichiers de versions différentes (un seul rechargement), message + bouton, écran masqué. |
| `mots.js`, `sauvegarde.js` | La liste des 2048 mots de la phrase de récupération (fabriquée par `tools/generer_mots.py`) ; le moteur de chiffrement de la sauvegarde (WebCrypto, sans accès à la base). |
| `tools/lire_export.py` | Script PC (Python 3 + `cryptography`) : lit un fichier `.agenda` avec la phrase et écrit un JSON lisible. |
| `verifications/verif_sauvegarde.py` | Étape 6 (92) : liste de mots, tirage sans biais, premier export, exports suivants, contenu complet, Vérifier, Restaurer, Annuler, atomicité, migration, rappel de 7 jours, hors connexion, masquage, test croisé avec le script PC. |
| `verifications/verif_hauteur.py` | Hauteur de la fenêtre (14) : le menu du bas reste entièrement visible quand la taille change après l'affichage, au démarrage, après rechargement ou « Mettre à jour », et quand la hauteur de `#app` est périmée. |
| `verifications/sync_version.py`, `_outils.py` | Recopie le numéro de version dans les tampons ; outil commun des contrôles. |
| `verifications/verif_publication.py` | À lancer après une publication : vérifie que le site répond et sert les bons fichiers (dont `version.js`). |

Règles respectées : JavaScript simple, aucune bibliothèque, aucun outil de construction, **aucune ressource chargée depuis internet**. Le seul trafic réseau est le téléchargement des fichiers de l'appli.

## Étape 1 (coquille) : comportements

- **Œil** (en haut à droite de chaque écran) : cache tout derrière l'écran « Agenda » (sans code), un toucher rouvre au même endroit. **Ni cadenas ni code** (décision de Pascal).
- **Masquage automatique** : Jamais / 1 minute / **2 minutes (défaut)** / 10 minutes (Réglages), **par comparaison d'heure** ; si l'horloge recule, masqué par prudence ; passage en arrière-plan = masqué tout de suite.
- **Stockage persistant** demandé une seule fois au premier lancement ; état dans Réglages (Bilan → Réglages) avec « Redemander à Chrome ».
- **Hors connexion** : le service worker garde 9 fichiers (réserve `agenda-<version>`).
- **Mises à jour** : « Nouvelle version disponible » + « Mettre à jour » ; jamais de rechargement automatique. Réglages affiche la version et la structure des données.

## Étape 2 : personnes et fiche

### Données (structure n° 2)
- **Migration 1 → 2** (`db.js`, liste `MIGRATIONS` : on n'ajoute que de nouvelles entrées à la fin, une migration n'efface rien) : ajoute les magasins `persons` (clé `id`) et `rides` (clé `id`, indexé par `person_id`, **vide** : utilisé à l'étape 3). Les réglages et informations de la version 0.1 sont gardés (vérifié sur une base d'essai ET sur une vraie base de la version 0.1 créée à l'identique).
- **Une fiche par personne** : `id` (identifiant aléatoire unique, `crypto.randomUUID()`), `last_name`, `first_name`, `pickup_street/zip/city`, `dest_place/street/zip/city`, `phone`, `usual_price_cents` (entier, **centimes**, `null` si inconnu), `usual_km_m` (entier, **mètres**, `null` si inconnu), `schedule`, `archived`, `archived_at`, `created_at`, `updated_at`.
- `schedule` : `mode` (`weekly` ou `dates`), `weekdays` (1 = lundi … 7 = dimanche), `time_weekly` (`HH:MM` ou `null`), `from` / `to` (`AAAA-MM-JJ` ou `null`), `dates` (liste `AAAA-MM-JJ`), `time_dates`. **Les deux jeux de données sont toujours gardés** : passer d'un mode à l'autre ne supprime rien.
- **« Inconnu » = vide (`null`), jamais 0** ; un 0 saisi est refusé avec un message simple.
- **Archiver plutôt que supprimer** : une personne archivée reste dans la base (`archived: true`). Une personne **vide** (aucune course notée) peut être effacée pour de bon ; ses courses « prévues » (pas notées) partent avec elle. S'il y a au moins une course notée, « Supprimer cette fiche » est grisée (« Impossible : N courses déjà notées. ») **et** la suppression est refusée même si on la déclenche par le code.
- Après une suppression ou un ajout, « Annuler » (5 secondes) remet exactement ce qui a été effacé (même identifiant, mêmes courses prévues).

### Écrans (même présentation, mêmes textes et mêmes règles que la maquette)
- **Personnes** : « N personnes », recherche par nom **et** prénom (accents et majuscules ignorés, mot surligné), liste triée, « Nouvelle personne » (ouvre la fiche vide), ligne « Archivées (N) » qui affiche la liste archivée **sur la même page** (« Restaurer », « Personnes actives »). Au départ : « Aucune personne pour l'instant. Touche « Nouvelle personne ». ».
- **Fiche** (même page pour créer et modifier) : Nom, Prénom (avertissement de doublon, non bloquant) ; Prise en charge (rue, code postal, ville) ; Destination habituelle (nom du lieu, rue, code postal, ville) ; Prix et km habituels (virgule **et** point) ; Téléphone avec « Appeler » ; **Quand** : « Chaque semaine » (L M M J V S D, heure habituelle, « Du » = date du jour pour une nouvelle personne, « Au » facultatif, « Au » avant « Du » refusé) ou « Dates choisies » (calendrier du mois, flèches de mois, lettres et « Lun à ven » qui cochent à partir d'aujourd'hui, pas de jours passés, heure unique, compteur « N jours choisis » sur tous les mois) ; « Enregistrer » ; « Gérer cette fiche » (Archiver, Supprimer).
- **Messages** : « X ajouté » (+ « Annuler » 5 s) pour une nouvelle personne, « Fiche enregistrée » pour une modification, « X archivé » (+ Annuler), « X de nouveau dans les listes. » (+ Annuler), « X supprimée » (+ Annuler).
- **Quitter sans enregistrer ?** (« Quitter » / « Rester ») : sur une fiche **nouvelle ou existante** dès que quelque chose a changé (champ, jour de la semaine, mode, date, heure), au toucher de « Retour », d'un onglet de la barre du bas, ou de la touche Retour d'Android. Si on remet la valeur d'origine, ou si rien n'a changé, aucune question. (Depuis 0.2.1 ; avant, seule une nouvelle fiche était protégée.)
- **Clavier** : majuscules automatiques pour noms, villes et lieu ; champs numériques pour code postal (5 chiffres), prix, km, téléphone, heure ; les lettres sont retirées à la frappe dans les champs numériques.
- **Heures** : « 13:00 », « 1300 », « 13h », « 13h30 », « 9h5 » sont comprises et rangées en `HH:MM` ; « 25:00 » est refusée.
- **Masquage** : œil ou masquage automatique avec la fiche (ou la fenêtre de confirmation, ou un message) ouverte : rien de lisible, la saisie est gardée au retour.

## Comment tester

### Sur le PC (PowerShell, depuis `agenda\verifications`)

    $env:SCHEME="dark"; $env:W="390"; $env:H="780"; python verif_coquille.py; python verif_personnes.py; python verif_miseajour.py
    $env:SCHEME="light"; $env:W="360"; $env:H="640"; python verif_coquille.py; python verif_personnes.py; python verif_miseajour.py

Chaque script lance un petit serveur local (`127.0.0.1`) et un navigateur Edge sans fenêtre ; aucun n'utilise internet. Essai à la main : `python -m http.server 8000` dans le dossier `agenda`, puis `http://localhost:8000` dans Chrome.

### Après une publication
    python verif_publication.py https://boumano.github.io/agenda/

### Sur le téléphone
Voir les étapes numérotées du rapport de l'étape 2.

## Ce qui n'est PAS testé
- **Sur un vrai téléphone** (Galaxy A12, Chrome) : clavier réel (virgule ou point décimal, clavier numérique des champs « heure » et « téléphone »), sélecteur de date de Chrome, installation, mode avion réel, geste « retour » d'Android.
- **Aperçu des applis récentes d'Android** : l'appli masque l'écran quand elle passe en arrière-plan, mais une page web ne peut pas garantir ce que montre l'aperçu.
- **Réponse réelle de Chrome au stockage persistant** (simulée dans les contrôles).
- **Mise à jour réelle sur GitHub Pages** vers 0.2.0 : à voir sur le téléphone (message « Nouvelle version disponible »).
- Beaucoup de personnes (centaines), très longs noms, très longues adresses : non essayés.
- Le sélecteur de date natif (« Du » / « Au ») : montré selon la langue de Chrome (jj-mm-aaaa) ; la valeur rangée est toujours `AAAA-MM-JJ`.
- Un échec isolé et **non reproduit** a été vu deux fois dans `verif_coquille` (un toucher sur un élément « non visible » juste après une modification des fichiers, puis la détection de mise à jour une fois) ; relances suivantes toutes à 0 échec. Le délai d'attente de ce contrôle a été allongé.
- (Étape 5 faite : la page Essence est complète ; voir plus bas.)

## Écarts par rapport au plan et à la maquette
- Pas de glissement gauche / droite entre les écrans et pas de transition animée (la maquette les avait).
- La fiche n'a pas encore le lien « Calendrier et courses » ni « Copier l'adresse » (étape 3 pour le calendrier ; la copie d'adresse n'était pas demandée).
- Le code postal est coupé à 360 px de large dans le champ (« Code posta… ») : même disposition que la maquette.
- `theme_color` et `background_color` du manifeste sont fixes (bleu sombre / fond sombre) ; la page suit le thème clair / sombre. Le champ date déclare `color-scheme` clair et sombre pour que son icône reste visible en mode sombre (seul ajout de style).
- Heure rangée en `HH:MM` avec zéro devant (« 09:30 ») : la maquette l'écrivait « 9h30 ».

## Correctifs 0.2.1 (trouvés par Pascal sur son téléphone)

### 1. Mise à jour figée (0.1.0 → 0.2.0)
- **Constat de Pascal** : après « Mettre à jour » (avec migration de la structure 1 → 2), la page est restée figée sur « Aujourd'hui », sans menu du bas ; après fermeture complète et réouverture, tout allait bien.
- **Cause la plus probable (reproduite en simulation, pas vue sur le téléphone)** : la mise à niveau des données est **retenue tant qu'une ancienne page garde sa connexion à la base ouverte**. La version 0.1 ne lâchait jamais sa connexion, et l'appli 0.2.0 ne disait rien quand l'ouverture était bloquée : elle attendait sans fin, sans message (la liste des personnes ne se remplissait jamais). Une fermeture complète de l'appli ferme toutes les pages, donc le blocage se lève : cela colle avec « tout était normal après réouverture ». **Non reproduit** : l'absence du menu du bas (dans la simulation le menu reste affiché sous un écran vide) ; l'ancienne version 0.2.0 n'a pas été relancée pour la comparaison.
- **Corrigé** :
  - la connexion à la base se **ferme dès qu'une autre page demande une nouvelle structure** (`onversionchange`), et la page l'explique (« Agenda a été mis à jour dans une autre fenêtre ») ;
  - l'évènement **« bloqué »** de l'ouverture affiche « Fermez et rouvrez l'appli pour finir la mise à jour » (écran entier, menu compris) ; le message **disparaît tout seul** si le blocage se lève ;
  - si la base n'est **pas prête après 5 secondes**, le même message s'affiche (plus d'écran figé) ;
  - le rechargement après « Mettre à jour » a lieu **une seule fois**, quand le nouveau service worker est **« activé »** (filet de sécurité de 3 s si l'évènement manque), et la page **lâche sa connexion à la base juste avant de recharger** ;
  - les mises à jour de 0.2.0 vers 0.2.1 ne changent pas la structure : la migration n'est pas en cause pour elles.
- **Limite** : les anciennes pages 0.1 n'avaient pas ce correctif ; il protège les mises à jour **à partir de 0.2.0**.

### 2. Fiche existante
- « Retour » (ou un onglet, ou la touche Retour d'Android) demande « Quitter sans enregistrer ? » quand quelque chose a changé, et ne demande rien sinon. La fiche note une « signature » de tout ce qui est modifiable à l'ouverture et la compare au moment de quitter.

### Contrôles
- `verif_miseajour.py` (19) simule une ancienne page qui garde sa connexion ouverte et une vraie mise à jour avec migration 2 → 3 (copie d'essai), avec une 2e page restée ouverte.
- Un échec isolé de détection de mise à jour (déjà vu deux fois dans `verif_coquille`) revient parfois : une recherche de mise à jour lancée au chargement peut absorber la première demande. Le contrôle redemande maintenant jusqu'à 4 fois. Dans l'appli, « Chercher une mise à jour » peut donc demander deux touchers dans de rares cas ; la recherche se refait aussi à chaque retour sur l'appli.

## Étape 3 : Aujourd'hui et calendrier d'une personne (0.3.0, structure n° 3)

### Données
- **Migration 2 → 3** : ajoute à `rides` l'**index par date** (celui par personne existe depuis la structure 2). Personnes, courses et réglages déjà là ne bougent pas. Vérifié sur une base d'essai, sur la vraie base d'une version 0.2.x et par une **vraie mise à jour 0.2.1 → 0.3.0** (`verif_maj030.py`).
- **Une course** : `id` (identifiant unique), `person_id`, `date` (texte `AAAA-MM-JJ`), `time` (`HH:MM` ou `null`), `dest_place/street/zip/city` (copiés), `price_cents` et `km_m` (entiers, `null` = inconnu, jamais 0) **copiés de la fiche à la création**, `usual_price_cents` / `usual_km_m` (valeurs habituelles copiées, pour le repère « habituel »), `status` (`null` = pas noté, `done` = fait, `not_done` = pas fait), `changed` (heure ou destination changée pour ce jour), `added` (course exceptionnelle), `skip` (« Pas de course »), `created_at`, `updated_at`, `deleted_at` (**corbeille** : `null` = visible).
- **Jamais d'effacement d'une course** : « supprimer » = `deleted_at`. « Annuler » après une première action remet l'état d'avant ; si l'action avait créé la course, « Annuler » la met à la corbeille.
- **Suppression d'une personne** : refusée dès qu'il existe une course **non supprimée** (même sans état) : « Impossible : N courses déjà notées. » (bouton grisé **et** refus par le code). Les courses déjà à la corbeille n'empêchent pas et ne sont pas touchées.
- **Journal de mise à jour** : les **20 derniers** évènements (`meta.update_log`), avec heure et numéro de version de l'appli qui les a écrits. Écrits **avant** un rechargement ou la fermeture de la connexion à la base. Aucune donnée de personne.

### Règles (`rides.js`)
- Une **carte prévue** pour un jour est **calculée** à partir des fiches des personnes **non archivées** : mode « Chaque semaine » (jour de la semaine coché, « Du » / « Au » bornes incluses) ou « Dates choisies » (date cochée) ; l'heure est celle du mode actif. Rien n'est enregistré.
- Une course n'est **créée** qu'à la **première action** : fait, pas fait, changer ce jour, ajouter une course, corriger le montant ou les km. Ouvrir une carte ne crée rien.
- Une course enregistrée **l'emporte** sur la carte prévue (jamais de doublon), « Pas de course » comprise. « Pas de course » sur un jour **à venir** : plus de carte ce jour-là.
- **Modifier la fiche** (prix, km, heure, destination, jours) ne réécrit **jamais** une course enregistrée ; l'avenir sans course suit la nouvelle fiche.
- Personne **archivée** : plus de carte prévue ; ses courses déjà notées (ou passées) restent visibles ; ses courses du jour ou à venir non notées sont cachées.
- Dates en **texte** : le changement d'heure du **dimanche 25 octobre 2026** ne décale rien (vérifié : 24, 25 et 26 octobre, courses rangées au bon jour, « Aujourd'hui » juste le 25 et le 26).

### Écrans
- **Aujourd'hui** (comme la maquette) : œil (44 × 28 px), jour en toutes lettres avec flèches, résumé « N courses · N faites · N pas faites », « Revenir à aujourd'hui », une ligne repliée par carte triée par heure (nom, « Rendez-vous 9h30 », « changé », ronds fait / pas fait ; un second toucher sur le rond actif remet à faire), carte ouverte (téléphone + « Appeler », prise en charge et destination avec « Copier », « Montant du jour » et « Kilomètres » avec repère « habituel », « Changer ce jour », « Supprimer cette course » pour une course exceptionnelle), « Ajouter une course » (choisir une personne sans carte ce jour-là), texte de journée vide « Aucune course prévue ce jour. ». À minuit, « Aujourd'hui » suit le calendrier tout seul.
- **Montant et km** : enregistrés quand on quitte le champ (ou « Entrée ») ; virgule ou point ; 0 refusé avec un message ; vide = inconnu ; le repère « habituel » disparaît dès que la valeur diffère de la fiche et revient si on retape la valeur habituelle.
- **Panneau d'un jour** (feuille du bas, pas une page), utilisé par Aujourd'hui et le calendrier : jour habituel → « Comme d'habitude » / « Changer ce jour » / « Pas de course » ; jour non habituel → « Ajouter une course » ; jour passé → « Fait » / « Pas fait » + montant et km ; formulaire = heure et destination seulement.
- **Calendrier et courses** : lien dans la fiche (« Courses de X »), mois avec coche (fait), croix rouge (pas fait), rond « à faire », rond vide « pas noté », case vide ; aujourd'hui entouré ; résumé « 2 transportée, 1 pas transportée, 27 jours sans note » ; légende ; mois précédent / suivant. « Retour » et la touche Retour d'Android reviennent à la fiche. Si la fiche est modifiée, le lien demande « Quitter sans enregistrer ? ».
- **Masquage** : œil ou masquage automatique sur Aujourd'hui, le calendrier ou un panneau ouvert : rien de lisible ; les cartes se referment (montants et adresses retirés de la page) ; la saisie en cours est validée au masquage.
- **Réglages** : « Journal de mise à jour » (20 lignes au plus, le plus récent en haut, heure + version).

### Écarts par rapport à la maquette
- **Pas de modification de l'heure directement sur la ligne** (la maquette avait « Rendez-vous » à toucher) : on passe par « Changer ce jour » (heure et destination), comme demandé.
- **Pas de ligne « Dernier export »** sous la date (étape 6), pas de « Passage 8h40 » (heure réelle de prise en charge) : ces éléments de la maquette ne font pas partie de l'étape.
- **Courses à la corbeille** : aucun écran pour les revoir pour l'instant (seulement « Annuler » pendant 5 secondes ; visible dans Réglages à l'étape 6 selon le plan).
- « Annuler » d'une action qui a créé la course : la course va à la corbeille (elle reste dans la base), plutôt que d'être effacée.
- **Le message « Impossible : N courses déjà notées. »** compte aussi les courses créées mais pas encore notées (règle demandée : toute course non supprimée empêche).

## Étape 4 : Bilan (0.4.0, structure inchangée n° 3)

**Le père ne reçoit RIEN de l'appli** : ni bouton de copie, ni envoi, ni partage (vérifié : aucun de ces mots ni appel dans le code du Bilan). Pascal lit l'écran à voix haute.

### Écran
- **Choix du mois** en haut (chevrons « Mois précédent / suivant », mois en cours au départ) et **deux vues** : « Totaux » | « Jour par jour ». Le mois et la vue sont gardés en revenant de Réglages. La ligne « Réglages » reste en bas, telle quelle.
- **Totaux** (mois choisi) : « N courses faites », total en **euros**, total en **km**, puis « Par personne » (courses faites, euros, km), ordre alphabétique des noms. **Seules** les courses « fait » non supprimées comptent. Les courses « pas fait », celles de la corbeille et les **cartes prévues jamais touchées** ne comptent jamais.
- **Inconnu ≠ 0** : une course « faite » sans prix (ou sans km) est comptée comme faite mais **pas comme 0** : « + N courses sans prix (total partiel) » / « + N courses sans km (total partiel) » (visibles même quand les montants sont masqués). Si **toutes** les courses du mois ont l'info inconnue, le total affiche « **inconnu** » (jamais « 0,00 € » ni « 0 km »).
- **Montants masqués** (« •••• € ») tant qu'on ne touche pas la tuile (comme la maquette) ; ils se recachent au changement de mois, de vue, en quittant le Bilan et au masquage. Les km ne sont pas masqués.
- Affichage : euros « 12,50 € », km avec 2 décimales au plus (« 8,4 km », « 17,73 km »).
- **Jour par jour** : une ligne par jour du mois **jusqu'à aujourd'hui** avec au moins une personne concernée (course enregistrée ou carte prévue), « mar 6 » puis, pour chaque personne, le **nom complet + un mot** : « oui » (fait, coche), « non » (pas fait, croix rouge), « pas noté » (jour passé, rien noté), « à faire » (aujourd'hui) (depuis 0.4.1 : une ligne par personne, voir les correctifs). Ligne « **N jours sans note** » = jours **passés** où une course était prévue (ou créée) et où **rien n'a été noté** (aujourd'hui jamais compté). Les jours sans personne concernée n'ont pas de ligne. **Toucher un jour ouvre ce jour dans Aujourd'hui.**
- **Personne archivée** : ses courses passées restent dans les totaux et dans « Jour par jour ». Les courses « changées » comptent avec **leurs valeurs propres**.
- **Masquage** (œil ou masquage automatique) : « Agenda » seul, aucun nom ni montant lisible, Totaux comme Jour par jour.

### Données et performance
- **Aucun changement de structure** : le Bilan lit les courses existantes. Le mois choisi est lu par l'**index des courses par date** (`ridesInRange`, borne de dates) : seules les courses du mois sont lues, jamais toute la base (vérifié : le nombre de courses lues = celles du mois). Avec **6 048 courses fictives** sur 24 mois : l'appli s'ouvre en moins d'une seconde et un mois s'affiche en moins de 25 ms (limite fixée : 500 ms).
- Dates en texte : le **changement d'heure du 25 octobre 2026** ne décale rien (jours 24, 25 et 26 chacun une fois, avec leurs courses).

### Écarts par rapport à la maquette
- **Plus de choix « Semaine / Mois »** : seulement le mois, comme demandé.
- La maquette cachait le prix et affichait des km « fictifs » ; ici les chiffres viennent des vraies courses.
- (Depuis 0.4.1 les lignes « Par personne » ouvrent le calendrier de la personne : voir les correctifs.)
- « Jour par jour » affiche **aussi** « pas noté » / « à faire » pour les personnes d'un jour partiellement noté (la maquette n'affichait que fait / pas fait / pas noté dans un seul résumé).
- Le résumé « Pas faits / Pas notés » de la maquette est remplacé par « N jours sans note » (définition ci-dessus).

## Correctifs 0.4.1 (demandés par Pascal après essai du Bilan 0.4.0)

- **Jour par jour : nom complet.** Chaque personne a maintenant **nom puis prénom** (même présentation que les lignes « Par personne » de « Totaux »). La date n'est écrite qu'**une fois**, puis **une ligne par personne** sous la date, avec « oui » / « non » / « pas noté » / « à faire » **à droite** (plus lisible à voix haute). Comme les noms complets distinguent les personnes, l'initiale ajoutée aux prénoms en double (« Un A. ») n'existe plus. Le masquage cache ces noms comme le reste.
- **Totaux : « Par personne » touchable.** Chaque ligne est un bouton avec la flèche à droite : il ouvre le **calendrier de cette personne** (le même que le lien « Calendrier et courses » de la fiche), **directement sur le mois affiché dans le Bilan**. Marche aussi pour une personne archivée. Pendant ce temps l'onglet **Bilan reste allumé**.
- **Résumé du mois en haut du calendrier** (aussi quand on arrive par la fiche) : courses faites, montant (**masqué** par « •••• € » tant qu'on ne touche pas, comme dans le Bilan), km. Mêmes règles que « Totaux » : seules les courses faites comptent ; un prix ou des km inconnus ne sont jamais comptés comme 0 (« + N courses sans prix / sans km (total partiel) », « inconnu » si tout est inconnu ; « 0,00 € » / « 0 km » seulement quand aucune course n'a été faite). Le résumé **suit le mois** quand on change de mois dans le calendrier ; le montant se recache à chaque changement de mois, au masquage et en quittant le calendrier.
- **« Retour » selon l'origine** : depuis le Bilan → retour au **Bilan, vue « Totaux », même mois** (les changements de mois faits dans le calendrier ne déplacent pas le Bilan) ; depuis la fiche → retour à la **fiche**. La touche Retour d'Android fait pareil.
- Pas de changement de structure des données. Ces changements sont dans `app.js`, `style.css` et `version.js`.

## Étape 5 : Essence et « jours sans note » du calendrier (0.5.0, structure n° 4)

### Correction du calendrier d'une personne
- La ligne « N jours sans note » ne compte plus que les jours **passés** où une course était **prévue** pour cette personne (habituelle ou ajoutée) et où **rien n'a été noté**. Jamais aujourd'hui, jamais un jour à venir, jamais un jour sans course prévue. Même règle que le Bilan (`AGR.state` = « pas noté »).
- Vérifié des deux côtés : `verif_calendrier` (modèle indépendant) et `verif_bilan` (une personne seule, un mois : « jours sans note » du Bilan = celui de son calendrier, y compris une course ajoutée un week-end et une course à la corbeille).

### Données (migration 3 → 4)
- Nouveau magasin `fuel` (clé `id`, index `date`). Rien d'autre ne change : personnes, courses, réglages et journal sont gardés.
- Un plein : `id`, `date` (texte AAAA-MM-JJ, donc rien ne bouge au changement d'heure), `liters_ml` (millilitres), `price_milli` (millièmes d'euro par litre), `total_cents` (centimes), `calc` (`price` / `liters` / `total` : le chiffre qui a été calculé, ou rien), `created_at`, `updated_at`, `deleted_at` (corbeille). Valeur vide = `null` = inconnu, **jamais 0**. Jamais effacé pour de bon.

### Page Essence (même présentation et mêmes règles que la maquette)
- Titre, œil, mois avec deux chevrons ; calendrier du mois (pompe sur les jours avec plein) ; « Total du mois » (pleins, litres, montant) ; « Pleins du mois » du plus récent au plus ancien. Un jour à venir est refusé (« Ce jour n’est pas encore arrivé »).
- Toucher un jour : liste des pleins du jour avec « Ajouter un plein » / « Fermer » (ou directement le formulaire s'il n'y en a pas). Formulaire : prix au litre, litres, montant ; **deux remplis → le troisième se calcule** (repère « calculé ») ; si Pascal retape un chiffre calculé, il reprend la main. Virgule **et** point acceptés, clavier décimal, lettres retirées à la frappe.
- Refus avec message simple : 0 (« Un zéro n’est pas possible : laisse la case vide si tu ne sais pas. »), format, un seul chiffre, trois chiffres qui ne correspondent pas (tolérance 1 centime).
- Supprimer : confirmation « Supprimer ce plein ? », puis message « Plein supprimé » avec « Annuler » pendant 5 secondes (le plein reste en corbeille dans la base).
- Totaux : jamais de 0 inventé. Litres ou montant inconnus : « + N pleins sans litres / sans montant (total partiel) » ; si **aucun** plein du mois n'a la valeur, « inconnu ».
- **Quitter sans enregistrer** : même question « Quitter sans enregistrer ? » (Rester / Quitter) que les fiches, pour « Annuler » du formulaire, « Fermer » et la touche Retour d'Android.
- **Masquage** : œil ou masquage automatique pendant que la page ou un formulaire est ouvert → la page Essence est **vidée** (aucun texte, aucun chiffre) et le formulaire en cours est abandonné ; au retour la page se redessine.

### Écarts
- Pas de champ « km du compteur » : la maquette n'en a pas (seulement prix, litres, montant).
- Un plein enregistré par l'écran a toujours au moins deux chiffres connus (règle de la maquette) ; les totaux savent pourtant gérer des pleins incomplets (testé avec des données posées directement dans la base).
- Les montants de la page Essence ne sont pas masqués par défaut (comme la maquette) ; ils le sont dès que l'écran est masqué.
- Mise à jour 0.4.1 → 0.5.0 : changement de structure 3 → 4, vérifié sans blocage avec une 2e page ouverte (`verif_maj050.py`) et vu dans le journal.

### Ce qui n'est PAS testé (étape 5)
- Les touchers réels sur le Galaxy A12 (clavier numérique réel, virgule du clavier du téléphone).
- La mise à jour 0.4.1 → 0.5.0 sur le vrai téléphone (simulée sur le PC).

## Correctif 0.5.1 : mise à jour « figée » (0.4.1 → 0.5.0 sur le vrai téléphone)

**Constat** (Galaxy A12) : après « Mettre à jour », la page restait sur « Aujourd'hui » sans menu du bas ; tout redevenait normal après fermeture complète. Le journal montrait que la base s'était ouverte normalement (« Base ouverte (structure 4) »), donc le blocage venait après.

**Cause : non reproduite telle quelle.** Dans le simulateur (Edge, vrais fichiers de 0.4.1, vrai service worker), la mise à jour réussit : menu présent, tous les fichiers servis sont ceux de la nouvelle version, y compris avec réseau lent (1,5 s par fichier ; 4 s sur `app.js`), réseau coupé juste après le toucher, 2e page ouverte. Aucune erreur JavaScript. Donc je ne peux pas dire que c'est LA cause sur le téléphone. Ce que j'ai **prouvé** (`verif_cache_coherent.py`, qui échoue sur le code de 0.5.0 et réussit sur 0.5.1) : un défaut du service worker qui permet précisément un mélange de fichiers de deux versions.
- Le service worker de 0.5.0 téléchargeait les fichiers **un par un** dans la réserve `agenda-0.5.0`. Si l'installation était interrompue (réseau mobile capricieux), il restait une réserve **à moitié remplie** ;
- et tout service worker de l'époque (0.4.1 comme 0.5.0) cherchait un fichier dans **toutes** les réserves, pas seulement la sienne. Une page encore en 0.4.1 pouvait donc recevoir `fuel.js` de la nouvelle version (vérifié : servi en code 200 alors qu'il n'existe pas en 0.4.1) ;
- hypothèses écartées par la simulation : rechargement trop tôt (le rechargement attend déjà l'état « activé »), erreur de base (la base s'ouvrait), vieux fichier gardé par le navigateur (`cache: 'reload'`).
Hypothèse restante, **non vérifiable sur PC** : une erreur JavaScript ou un affichage qui ne se fait pas sur le téléphone. C'est pour la voir que le journal reçoit de nouvelles lignes.

**Ce qui change**
- **Service worker (`sw.js`)** : installation « tout ou rien » (tous les fichiers sont téléchargés en mémoire et vérifiés, puis écrits d'un coup ; au moindre manque l'installation échoue et rien ne reste) ; ne sert **que sa propre réserve** ; efface les anciennes réserves seulement **après** avoir pris la main ; sait répondre à « ta réserve est-elle complète ? ».
- **Rechargement (`app.js`)** : seulement quand le bouton a été touché ET le nouveau service worker est actif ET il contrôle la page ET sa réserve est vérifiée complète (ligne « Réserve complète » dans le journal). Une seule fois.
- **Journal (20 lignes, gardé dans la base)** : « Écran affiché (menu prêt) » après le premier affichage réussi ; « Erreur : … » (court, au plus 3 par chargement) pour toute erreur non attrapée ou promesse rejetée ; « Fichiers de versions différentes : <liste> » (chaque fichier porte son numéro) ; « Écran pas affiché correctement » ou « … après 8 secondes ». Rien n'est visible hors Réglages.
- **Version différente détectée au démarrage** : la page se recharge **une seule fois** en vidant les réserves de l'appli et en redemandant tous les fichiers au site (seulement si le site répond), le note, puis affiche le message si ça persiste.
- **Premier affichage qui échoue** : le menu du bas et le reste s'affichent quand même ; message « Un problème est survenu à l’affichage. Touchez pour recharger » avec un bouton « Recharger » (qui contourne les réserves). Jamais affiché sous l'écran neutre : il attend le retour de l'écran.
- Pas de changement de structure des données. Aucun écran ni design modifié (seul ajout : le bouton dans le message d'erreur déjà existant).

**Limites** : la mise à jour 0.5.0 → 0.5.1 est lancée par le code de 0.5.0 déjà sur le téléphone (rechargement à l'état « activé », sans la vérification de réserve) ; les nouvelles protections de rechargement agiront à partir de la mise à jour suivante. Le service worker 0.5.1, lui, protège dès son installation. Non testé : le vrai Galaxy A12.

## Correctif 0.5.2 : menu du bas poussé sous le bord visible après « Mettre à jour »

**Constat** (Galaxy A12) : après 0.5.0 → 0.5.1, l'écran Aujourd'hui s'affiche mais le menu du bas est en bas, presque hors de l'écran, jusqu'à la fermeture complète de l'appli. Le journal est parfait (aucune erreur, « Écran affiché »), donc ce n'est ni la base ni les fichiers.

**Ce que j'ai trouvé dans le code** (rien de calculé en JavaScript : aucun `innerHeight`, `visualViewport`, `100vh` ni variable de hauteur) :
- `style.css`, règle `#app{position:relative;height:100dvh;…}` : **toute la hauteur de l'appli venait d'une seule unité CSS, `100dvh`**. Le menu du bas (`.nav`, dernier élément de la colonne `#app`, marge `env(safe-area-inset-bottom)`) est collé au bas de `#app` : si `100dvh` est trop grand, le menu descend d'autant sous le bord visible. `body{overflow:hidden}` empêche d'aller le chercher en défilant.
- `index.html` : `viewport` avec `viewport-fit=cover`, sans `interactive-widget`. `manifest.json` : `display: standalone`, `orientation: portrait`.
- **Cause probable** : juste après un rechargement déclenché par « Mettre à jour », Chrome Android calcule `100dvh` avant d'avoir appliqué la barre de navigation système, puis ne redéclenche pas la mise en page. Une réouverture complète recalcule tout, d'où le retour à la normale.
- **Ce qui a pu être prouvé sur PC** : le simulateur recalcule `100dvh` tout seul quand la fenêtre change (tous les changements de taille passent déjà sur 0.5.1). Le défaut du téléphone (hauteur CSS qui reste périmée) n'est donc reproduit que par un essai qui **fige** la hauteur de `#app` : `verif_hauteur.py` échoue sur 0.5.1 pour ce cas (3 échecs : menu 90 px sous le bord visible, pas de ligne au journal) et réussit sur 0.5.2.

**Ce qui change**
- `#app` est maintenant `position:fixed; inset:0` (collé aux quatre bords de la fenêtre, **aucune hauteur écrite**), largeur max 430 px centrée comme avant. Le menu reste collé au bas, marge `safe-area` conservée. Aucun changement visible.
- Filet de sécurité dans `garde.js` : si le bas du menu dépasse la zone visible (`visualViewport.height`, sinon `innerHeight`), la hauteur de `#app` est fixée sur la zone visible, puis suivie. Recalcul sur `resize`, `orientationchange`, `visualViewport.resize`, `pageshow`, `visibilitychange`, et à 300 ms, 1 s et 2 s après le démarrage. Pas de correction quand un champ de saisie est actif (clavier ouvert : comportement inchangé).
- Journal : « Mise en page : fenêtre H, visible V, bas du menu B » juste après « Écran affiché (menu prêt) » ; « Mise en page corrigée : fenêtre H, visible V, bas du menu B » (une fois par chargement) si la correction a servi. Rien de visible hors Réglages.
- Pas de changement de structure des données.

**Non testé** : le vrai Galaxy A12 (le défaut dépend de Chrome Android et de sa barre système). Si le menu redescend, la ligne « Mise en page » du journal donnera H, V et B.

## Étape 6 : export chiffré, vérification, restauration (0.6.0, structure n° 5)

**Où** : Réglages → « Sauvegarde et restauration » (écran `s-sauvegarde`), et ligne « Dernier export : il y a N jours » dans Réglages. Le Bilan affiche, discrètement et sans jamais bloquer, « Pas d’export depuis N jours » au-delà de 7 jours, ou « Pas encore d’export » s'il y a des données et aucun export.

### Le schéma de chiffrement (en phrases simples)
- Les données restent **non chiffrées sur le téléphone** (la protection est le verrou d'Android). **Seul le fichier d'export est chiffré.**
- **La phrase** : 10 mots tirés au hasard dans une liste de **2048 mots** français (`mots.js`), avec `crypto.getRandomValues`. 2048 = 2^11 : on prend 16 bits au hasard et on garde les 11 derniers, donc chaque mot a exactement la même chance (vérifié : sur les 65 536 valeurs possibles, chaque mot sort 32 fois). Cela fait **110 bits** de hasard (le plan prévoyait 7 776 mots, ≈ 129 bits : la liste de 2048 mots est un choix de Pascal ; 110 bits restent hors de portée de toute devinette, grâce aussi à la lenteur voulue de PBKDF2). Aucun mot ne ressemble à un autre à une lettre près, aucun n'est le début d'un autre, aucun doublon même sans accents. La phrase est comparée sans accents, sans majuscules, espaces en trop ignorés.
- **Pourquoi pas de phrase à chaque semaine** : le téléphone garde une **clé de données** (32 octets au hasard, AES-256-GCM) sous forme de **clé WebCrypto non extractible** : même le code de l'appli ne peut pas la relire, seulement s'en servir. À la création de la phrase, cette clé est **enveloppée** (chiffrée) par une clé fabriquée à partir de la phrase (**PBKDF2-SHA256, 600 000 tours**, sel de 16 octets au hasard). C'est cette « clé enveloppée » qui est gardée sur le téléphone et **recopiée dans chaque fichier**.
- **Chaque export** chiffre le contenu avec la clé de données (**AES-GCM**, nouveau vecteur d'initialisation à chaque fois) : aucune phrase à retaper. **Pour restaurer sur n'importe quel téléphone** : le fichier + la phrase suffisent (phrase → clé d'enveloppe → clé de données → contenu). Après une restauration, le téléphone **adopte la clé du fichier** (sans la revoir) : l'export suivant se fait aussi sans phrase et s'ouvre avec la même phrase.
- **La phrase n'est jamais enregistrée** : ni dans la base, ni dans le stockage du navigateur, ni dans le journal (vérifié). Elle n'existe en mémoire que le temps de l'afficher et de la confirmer.
- Pas de « mieux que PBKDF2 hors bibliothèque » : WebCrypto n'offre que PBKDF2 (pas d'Argon2 sans bibliothèque). Le nombre de tours est écrit dans le fichier (on pourra l'augmenter plus tard sans casser les anciens fichiers).
- **Authentification** : AES-GCM détecte toute modification (même un seul caractère). L'en-tête (format, structure, date) est lié au contenu (données associées) : changer la date de l'en-tête rend le fichier illisible.

### Format du fichier `.agenda` (texte JSON ; nom `agenda-AAAA-MM-JJ-HHMM.agenda`, heure locale)
`format` = « agenda-export » · `format_version` = 1 · `app_version` · `schema` (structure des données, ici 5) · `exported_at` (UTC, ISO) · `kdf` {`name` « PBKDF2-SHA256 », `iterations`, `salt` base 64} · `wrapped_key` {`iv`, `ct`} (clé de données enveloppée ; données associées « agenda-key|1 ») · `cipher` « AES-256-GCM » · `iv` · `ct` (contenu ; données associées « agenda-export|1|<structure>|<date> »).
Le contenu déchiffré : `counts` {`persons`, `rides`, `fuel`} (comptes de contrôle) · `sha256` (empreinte du texte `data`) · `data` (texte JSON : `schema`, `persons` **y compris archivées**, `rides` **y compris corbeille**, `fuel` **y compris corbeille**, `settings`). Dates en texte, montants en centimes, comme dans la base. Aucun nom, adresse ni valeur n'est lisible dans le fichier brut (vérifié).

### Comportements
- **Premier export** : explication en phrases courtes → phrase affichée (10 mots numérotés) → « J'ai tout écrit » → confirmation de **2 mots demandés au hasard** (ex. n° 3 et n° 7) → seulement alors le trousseau est créé et le fichier produit. Mauvaise réponse (ou mot vide) : on **revoit la même phrase**, rien n'est créé.
- **Masquage (œil ou automatique), règle de la 0.6.0, CHANGÉE en 0.6.1 pour l’écran de la phrase (voir « Corrections 0.6.1 » plus bas)** : la page de Sauvegarde est vidée ; la phrase est effacée de la mémoire et **ne revient pas** (retour à l'accueil, « recommencez », rien créé). Un résultat « Sauvegarde valide » ou un résumé de restauration ne revient pas non plus. Le fichier choisi (chiffré) et l'étape « taper la phrase » sont gardés (le champ est vidé), parce que le sélecteur de fichiers d'Android peut mettre l'appli en arrière-plan.
- **« Dernier export »** n'est mis à jour qu'**après** avoir lancé le téléchargement (si le navigateur refuse, rien ne change). Le nombre de jours est calculé en **jours de calendrier** (le changement d'heure du 25 octobre 2026 ne décale rien : testé).
- **Vérifier une sauvegarde** : fichier + phrase → « Sauvegarde valide : date, N personnes, N courses, N pleins », **sans rien modifier**. Messages simples : mauvaise phrase, fichier abîmé ou incomplet (un caractère modifié, tronqué, vide), pas une sauvegarde Agenda, format ou structure plus récents que l'appli (dit avant même de demander la phrase).
- **Restaurer** : même vérification, puis résumé « dans le fichier / sur ce téléphone », confirmation « Cela remplace tout ce qui est sur ce téléphone ». Avant de remplacer, une **copie de sécurité interne** de l'état actuel est gardée (un seul niveau, magasin `safety`), 7 jours. **Atomique** : un seul passage dans la base (`replaceAll`) ; si un enregistrement est refusé, **tout est annulé** (testé : données, réglages et métadonnées inchangés). « Annuler la restauration » (avec confirmation : ce qui a été noté depuis est perdu) remet l'état d'avant, y compris l'ancien « dernier export » et l'ancienne clé ; « Garder définitivement » efface la copie ; après 7 jours elle disparaît seule. Une structure plus ancienne est **migrée** (`AGB.migrateData` : structure 3 → ajoute les pleins vides, 4 → 5 rien à changer). **Après restauration, « Dernier export » reste celui du fichier.**
- **Migration de structure 4 → 5** (`db.js`) : crée le magasin `safety`. Le trousseau (`backup_key`) et la date (`last_export`) sont dans `meta`. Rien d'existant ne bouge (vérifié par la mise à jour 0.5.2 → 0.6.0 réelle dans `verif_maj*`).
- Aucune requête réseau : tout (liste de mots, chiffrement) est dans le dépôt et marche hors connexion (testé en mode avion).

### Script PC `tools/lire_export.py`
Prérequis : Python 3 et `pip install cryptography`. Usage : `python tools/lire_export.py agenda-2026-10-25-0930.agenda` (la phrase est demandée sans s'afficher) ; option `-o contenu.json`. Il vérifie l'empreinte et les comptes puis écrit un JSON lisible (en-tête, comptes, `data`). **Ce JSON contient des données personnelles** : à ranger comme du papier sensible. Il ne modifie jamais le fichier `.agenda` et sert de base à l'archivage futur dans la base Python. Testé par `verif_sauvegarde.py` : un fichier produit par l'appli est déchiffré par le script, contenu identique à celui du téléphone ; mauvaise phrase et fichier modifié refusés.

### Écarts et limites
- Liste de **2048** mots (et non 7 776 comme dans le plan) : demande de Pascal ; phrase de 110 bits au lieu de ≈ 129.
- Le nom du fichier est celui que propose le navigateur ; Chrome peut ajouter « (1) » si le nom existe déjà.
- Le script PC ne verse pas encore dans `chauffeur.db` (ce sera l'étape suivante : `chauffeur_import.py`).
- Comptes affichés = fichiers entiers, **corbeille comprise**.
- Non testé : le sélecteur de fichiers d'Android réel, le dossier Téléchargements du Galaxy A12, le temps de calcul de PBKDF2 sur ce téléphone (600 000 tours : de l'ordre de la seconde, un message « Un instant… » s'affiche).

## Corrections 0.6.1 : phrase qui reste affichée, nouvelle phrase (structure inchangée : n° 5, aucune migration)

**Pourquoi** : avec la 0.6.0, le masquage automatique (1 minute) effaçait la phrase avant la fin de la recopie, et un nouvel essai donnait une autre phrase. Quitter l'appli la perdait aussi.

### Phrase affichée (premier export et « nouvelle phrase »)
- **Pause du masquage** : tant que l'écran de la phrase (affichage ou confirmation) est ouvert, le masquage automatique ne se déclenche pas. Limite : **10 minutes** à partir de l'affichage (`BK_PHRASE_MS`, `bk.until`), comparées par horodatage (`Date.now()`), donc valables après un retour d'une autre appli. Le compte à rebours « Cette phrase reste affichée encore N min » est discret et absent quand l'écran est masqué.
- **Quitter puis revenir** (autre appli, autre onglet, écran éteint) : l'écran est vidé comme avant (rien de lisible sous l'écran neutre), mais la phrase reste **en mémoire de la page** (variable `bk.phrase`). Au retour (toucher l'écran neutre), la **même phrase** revient au même écran (affichage ou confirmation, mêmes mots demandés), avant 10 minutes.
- **Jamais stockée** : ni IndexedDB (toutes les bases et magasins, journal compris), ni localStorage, ni sessionStorage, ni caches (vérifié par `verif_phrase.py`, pendant l'affichage et pendant l'absence).
- **L'œil** efface la phrase immédiatement et pour de bon (« recommencez », rien créé). Quitter l'écran Sauvegarde (Retour, autre onglet du menu) l'efface aussi.
- **Après 10 minutes** (écran visible ou absence) : phrase effacée, message « Pour votre sécurité, la phrase a été effacée. Une nouvelle phrase va être créée. », retour à l'explication ; rien n'est enregistré. Si l'horloge recule de plus de 2 s, c'est traité comme un dépassement (par prudence). **Si Android ferme la page en arrière-plan**, la mémoire est perdue : au retour, on est à l'accueil de Sauvegarde (aucun message particulier, car rien n'est gardé pour s'en souvenir).
- Les autres écrans (saisie de la phrase pour vérifier/restaurer, résultats) gardent la règle de la 0.6.0.

### Nouvelle phrase de récupération
- **Où** : Sauvegarde et restauration → « Créer une nouvelle phrase » (seulement si une phrase a déjà été confirmée). Explication en phrases courtes (l'ancienne phrase ne sert plus qu'aux fichiers déjà exportés ; les prochains exports utilisent la nouvelle ; faire un export tout de suite après) puis même parcours que le premier export : affichage, papier, confirmation de 2 mots au hasard. **Rien n'est remplacé tant que la confirmation n'est pas bonne** (confirmation ratée, œil, expiration : le trousseau reste celui d'avant, vérifié).
- **Après confirmation** : le trousseau (`meta.backup_key`) est remplacé, une ligne « Phrase de récupération renouvelée » est écrite au journal (rien de lisible), et l'écran propose « Exporter maintenant » (pas d'export automatique).
- **Technique, et écart avec la demande** : la demande disait « même clé de données, ré-enveloppée avec la nouvelle phrase ». Or la clé de données du téléphone est **non extractible** (choix de la 0.6.0) : le code ne peut pas la relire pour la ré-envelopper. La nouvelle phrase crée donc une **nouvelle clé de données** (nouveau sel, nouvelle enveloppe), et les exports suivants s'en servent. Conséquences, toutes conformes à l'objectif : les fichiers suivants ne contiennent que la nouvelle enveloppe, l'ancienne phrase ne peut pas les ouvrir ; les anciens fichiers restent lisibles avec l'ancienne phrase seulement ; et c'est **plus sûr** que de garder la même clé (quelqu'un qui aurait l'ancienne phrase et un ancien fichier connaîtrait la clé et pourrait ouvrir les nouveaux fichiers). Le format de fichier ne change pas : `tools/lire_export.py` lit les deux (testé).
- **Restauration** : restaurer un fichier fait adopter la clé de CE fichier (comme avant) ; son annulation remet la clé d'avant.

### Ligne « papier et stylo »
« Avant de commencer : prenez un papier et un stylo. Vous avez 10 minutes. » s'affiche à l'accueil de Sauvegarde tant qu'aucune phrase n'est confirmée, et sur l'écran d'explication (premier export et nouvelle phrase).

### Vérifications
`verifications/verif_phrase.py` (33 contrôles) : pause du masquage (réglage 1 minute, 5 minutes sans toucher), aller-retour hidden/visible avec grand écart d'horodatage, étape de confirmation, effacement après 10 minutes (visible et absent), œil, nouvelle phrase (confirmation ratée, expiration, réussite), qui ouvre quoi (ancienne/nouvelle × ancien/nouveau fichier), test croisé `tools/lire_export.py`, scan de tous les stockages. `verif_sauvegarde.py` mis à jour (l'ancien test « masquage automatique efface la phrase » devient « après 10 minutes »).
- **Non testé** : un vrai téléphone (changement d'appli réel, fermeture de la page par Android, écran qui s'éteint), mise à jour 0.6.0 → 0.6.1 sans fermer l'appli sur le Galaxy A12.
