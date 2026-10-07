# Agenda : notes (étapes 1 à 3)

État au 7 octobre 2026 : **version 0.3.0, structure des données n° 3**. Dossier : `agenda/` (son propre dépôt git, publié sur GitHub Pages).
Plan de référence : `PLAN_VRAIE_VERSION.md` (dans le dossier de la maquette), étapes 1 à 3.
**Rien de réel dans ce dossier** : aucune donnée de personne, ni réelle ni fictive (l'appli démarre vide), aucun nom, aucune adresse, aucun téléphone. La maquette reste la référence et n'est pas copiée ici. Les contrôles automatiques n'emploient que de faux noms (« Essai », « Beta », etc.).

## Ce qui est construit

| Fichier | Rôle |
|---|---|
| `index.html` | La page : écrans Aujourd'hui, Personnes, Bilan, Essence, Fiche, Réglages, barre du bas à 4 boutons, fenêtre de confirmation, écran neutre « Agenda ». |
| `style.css` | Styles repris de la maquette (palette sombre / claire automatiques, bandeau, barre du bas, œil, boutons, fiche, calendrier). Toutes les couleurs sont définies une seule fois, en haut. |
| `app.js` | Écrans et comportements : Personnes, Fiche, œil et masquage automatique, Réglages, message de mise à jour. |
| `db.js` | **Un seul endroit** qui lit et écrit dans IndexedDB : ouverture, migrations, personnes, courses, journal de mise à jour, suppression sûre. |
| `rides.js` | La **logique des courses**, sans écran ni stockage : cartes prévues calculées à partir des fiches, création d'une course (valeurs copiées), état d'un jour. |
| `sw.js` | Service worker : garde les fichiers sur le téléphone pour que l'appli s'ouvre sans internet. Ne remplace jamais une version tout seul. |
| `version.js` | **Le seul endroit** où est écrit le numéro de version (`0.3.0`). |
| `manifest.json`, `icon.svg`, `icon-192.png`, `icon-512.png` | Nom (« Agenda »), couleurs, icônes : ce qui permet à Chrome de proposer « Installer ». |
| `verifications/verif_coquille.py` | Contrôles de la coquille (71) : fichiers, manifeste, service worker, hors connexion, version, stockage, migration, œil, masquage, mise à jour, barre du bas. |
| `verifications/verif_personnes.py` | Contrôles de l'étape 2 (140) : personnes, fiche, « Quand », « Quitter sans enregistrer ? », archivage, suppression, migration 1 → 2, masquage. |
| `verifications/verif_miseajour.py` | Contrôles du correctif 0.2.1 (19) : ancienne page qui garde la base ouverte pendant une mise à niveau, message de blocage, base pas prête après 5 s, lâcher de connexion (versionchange), vraie mise à jour avec migration 3 → 4 sur une copie d'essai, un seul rechargement. |
| `verifications/verif_courses.py` | Étape 3, écran Aujourd'hui (71) : cartes prévues, création à la première action, fait / pas fait / annuler, changer ce jour, ajouter une course, montant et km, fiche qui ne réécrit rien, archivage, persistance, hors connexion, masquage, changement d'heure du 25 octobre 2026. |
| `verifications/verif_calendrier.py` | Étape 3, calendrier d'une personne (64) : lien dans la fiche, états des jours, panneau d'un jour, « Pas de course », corbeille, suppression d'une personne, masquage. |
| `verifications/verif_maj030.py` | Mise à jour **réelle** 0.2.1 → 0.3.0 (fichiers de l'ancienne version tirés de git, structure 2 → 3, 2e page ouverte) et journal de mise à jour (28). |
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
- Écrans Bilan (hors Réglages) et Essence : toujours vides, seulement leur titre (étapes suivantes).

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
