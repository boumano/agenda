# Agenda : notes (étapes 1 et 2)

État au 7 octobre 2026 : **version 0.2.0, structure des données n° 2**. Dossier : `agenda/` (son propre dépôt git, publié sur GitHub Pages).
Plan de référence : `PLAN_VRAIE_VERSION.md` (dans le dossier de la maquette), étapes 1 et 2.
**Rien de réel dans ce dossier** : aucune donnée de personne, ni réelle ni fictive (l'appli démarre vide), aucun nom, aucune adresse, aucun téléphone. La maquette reste la référence et n'est pas copiée ici. Les contrôles automatiques n'emploient que de faux noms (« Essai », « Beta », etc.).

## Ce qui est construit

| Fichier | Rôle |
|---|---|
| `index.html` | La page : écrans Aujourd'hui, Personnes, Bilan, Essence, Fiche, Réglages, barre du bas à 4 boutons, fenêtre de confirmation, écran neutre « Agenda ». |
| `style.css` | Styles repris de la maquette (palette sombre / claire automatiques, bandeau, barre du bas, œil, boutons, fiche, calendrier). Toutes les couleurs sont définies une seule fois, en haut. |
| `app.js` | Écrans et comportements : Personnes, Fiche, œil et masquage automatique, Réglages, message de mise à jour. |
| `db.js` | **Un seul endroit** qui lit et écrit dans IndexedDB : ouverture, migrations, personnes, courses (comptage), suppression sûre. |
| `sw.js` | Service worker : garde les fichiers sur le téléphone pour que l'appli s'ouvre sans internet. Ne remplace jamais une version tout seul. |
| `version.js` | **Le seul endroit** où est écrit le numéro de version (`0.2.0`). |
| `manifest.json`, `icon.svg`, `icon-192.png`, `icon-512.png` | Nom (« Agenda »), couleurs, icônes : ce qui permet à Chrome de proposer « Installer ». |
| `verifications/verif_coquille.py` | Contrôles de la coquille (71) : fichiers, manifeste, service worker, hors connexion, version, stockage, migration, œil, masquage, mise à jour, barre du bas. |
| `verifications/verif_personnes.py` | Contrôles de l'étape 2 (126) : personnes, fiche, « Quand », archivage, suppression, migration 1 → 2, masquage. |
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
- **Quitter sans enregistrer ?** (« Quitter » / « Rester ») : sur une **nouvelle** fiche déjà remplie, au toucher de « Retour », d'un onglet de la barre du bas, ou de la touche Retour d'Android. Comme la maquette, la modification d'une fiche existante n'a pas cette question.
- **Clavier** : majuscules automatiques pour noms, villes et lieu ; champs numériques pour code postal (5 chiffres), prix, km, téléphone, heure ; les lettres sont retirées à la frappe dans les champs numériques.
- **Heures** : « 13:00 », « 1300 », « 13h », « 13h30 », « 9h5 » sont comprises et rangées en `HH:MM` ; « 25:00 » est refusée.
- **Masquage** : œil ou masquage automatique avec la fiche (ou la fenêtre de confirmation, ou un message) ouverte : rien de lisible, la saisie est gardée au retour.

## Comment tester

### Sur le PC (PowerShell, depuis `agenda\verifications`)

    $env:SCHEME="dark"; $env:W="390"; $env:H="780"; python verif_coquille.py; python verif_personnes.py
    $env:SCHEME="light"; $env:W="360"; $env:H="640"; python verif_coquille.py; python verif_personnes.py

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
- **Courses** : le magasin `rides` est vide ; la règle « course notée = suppression impossible » est testée avec des courses placées directement dans la base d'essai, pas avec de vraies courses (étape 3).
- Beaucoup de personnes (centaines), très longs noms, très longues adresses : non essayés.
- Le sélecteur de date natif (« Du » / « Au ») : montré selon la langue de Chrome (jj-mm-aaaa) ; la valeur rangée est toujours `AAAA-MM-JJ`.
- Un échec isolé et **non reproduit** a été vu deux fois dans `verif_coquille` (un toucher sur un élément « non visible » juste après une modification des fichiers, puis la détection de mise à jour une fois) ; relances suivantes toutes à 0 échec. Le délai d'attente de ce contrôle a été allongé.
- Autres écrans (Aujourd'hui, Bilan, Essence) : toujours vides, seulement leur titre (étapes suivantes).

## Écarts par rapport au plan et à la maquette
- Pas de glissement gauche / droite entre les écrans et pas de transition animée (la maquette les avait).
- Sur une fiche **existante**, rien ne demande « Quitter sans enregistrer ? » (comme la maquette) : une modification non enregistrée est perdue si on touche « Retour ». À discuter après l'essai.
- La fiche n'a pas encore le lien « Calendrier et courses » ni « Copier l'adresse » (étape 3 pour le calendrier ; la copie d'adresse n'était pas demandée).
- Le code postal est coupé à 360 px de large dans le champ (« Code posta… ») : même disposition que la maquette.
- `theme_color` et `background_color` du manifeste sont fixes (bleu sombre / fond sombre) ; la page suit le thème clair / sombre. Le champ date déclare `color-scheme` clair et sombre pour que son icône reste visible en mode sombre (seul ajout de style).
- Heure rangée en `HH:MM` avec zéro devant (« 09:30 ») : la maquette l'écrivait « 9h30 ».
