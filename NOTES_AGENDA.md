# Agenda : notes de l'étape 1 (coquille installable)

État au 7 octobre 2026. Dossier : `agenda/` (son propre dépôt git). Plan de référence : `PLAN_VRAIE_VERSION.md` (dans le dossier de la maquette), étape 1.
**Rien de réel dans ce dossier** : aucune donnée de personne, ni réelle ni fictive, aucun nom, aucune adresse, aucun téléphone. La maquette reste la référence et n'est pas copiée ici.

## Ce qui est construit

| Fichier | Rôle |
|---|---|
| `index.html` | La page : 4 écrans vides (Aujourd'hui, Personnes, Bilan, Essence) avec seulement leur titre, l'écran Réglages, la barre du bas à 4 boutons, l'écran neutre « Agenda ». |
| `style.css` | Styles repris de la maquette (palette sombre / claire automatiques, bandeau, barre du bas, œil, boutons). Toutes les couleurs sont définies une seule fois, en haut. |
| `app.js` | Navigation, œil et masquage automatique, IndexedDB (numéro de structure + migrations), demande de stockage persistant, Réglages, message de mise à jour. |
| `sw.js` | Service worker : garde les fichiers sur le téléphone pour que l'appli s'ouvre sans internet. Ne remplace jamais une version tout seul. |
| `version.js` | **Le seul endroit** où est écrit le numéro de version (`0.1.0`). |
| `manifest.json` | Nom (« Agenda »), nom court, couleurs, icônes : ce qui permet à Chrome de proposer « Installer ». |
| `icon.svg`, `icon-192.png`, `icon-512.png` | Icône : un calendrier avec une coche (le PNG vient du SVG). |
| `verifications/verif_coquille.py` | Contrôles automatiques de cette étape (71). |
| `verifications/verif_publication.py` | À lancer après la publication : vérifie que le site répond et sert les bons fichiers. |

Règles respectées : JavaScript simple, aucune bibliothèque, aucun outil de construction, **aucune ressource chargée depuis internet** (ni police, ni script, ni image). Le seul trafic réseau est le téléchargement des fichiers de l'appli.

### Comportements
- **Œil** (en haut à droite de chaque écran) : un toucher cache tout derrière l'écran neutre « Agenda » (sans code) ; un toucher rouvre au même endroit. Il n'y a **ni cadenas ni code** (décision de Pascal).
- **Masquage automatique** après inactivité : Jamais / 1 minute / **2 minutes (défaut)** / 10 minutes, réglable dans Réglages, gardé après fermeture. Il se calcule **par comparaison d'heure** (heure du dernier toucher contre heure actuelle), pas par minuterie. Si l'horloge recule, l'appli masque par prudence. Dès que l'appli passe en arrière-plan, l'écran neutre s'affiche tout de suite.
- **IndexedDB** : base « agenda », structure n° 1 (magasins `meta` et `settings`), mécanisme de migration (liste `MIGRATIONS` : on n'ajoute que de nouvelles entrées à la fin, une migration n'efface rien). Si la base vient d'une version plus **récente** que l'appli, l'appli refuse de l'ouvrir, l'explique et **n'efface rien**.
- **Stockage persistant** : demandé **une seule fois**, au premier lancement ; l'état (« accordé » / « non accordé ») est affiché dans Réglages (Bilan → Réglages), avec un bouton « Redemander à Chrome » s'il n'est pas accordé.
- **Hors connexion** : le service worker garde 8 fichiers (réserve `agenda-<version>`). L'appli s'ouvre en mode avion.
- **Mises à jour** : si une nouvelle version existe, le message « Nouvelle version disponible » apparaît avec le bouton « Mettre à jour ». **Jamais de rechargement automatique** : l'appli ne se recharge qu'après ce bouton. Le message apparaît seulement quand une version est vraiment prête (pas à la première installation).
- **Numéro de version** visible dans Réglages, avec le numéro de structure des données.

## Comment tester

### Sur le PC (contrôles automatiques, environ 40 secondes chacun)
Dans PowerShell, depuis `agenda\verifications` :

    $env:SCHEME="dark"; $env:W="390"; $env:H="780"; python verif_coquille.py
    $env:SCHEME="light"; $env:W="360"; $env:H="640"; python verif_coquille.py

Le script lance un petit serveur local (`127.0.0.1`) et un navigateur Edge sans fenêtre ; il n'utilise pas internet. Pour essayer l'appli à la main sur le PC : `python -m http.server 8000` dans le dossier `agenda`, puis `http://localhost:8000` dans Chrome.

### Après la publication
    python verif_publication.py https://boumano.github.io/agenda/

### Sur le téléphone
Voir les étapes numérotées du rapport (installer, mode avion, masquage, aperçu des applis récentes, stockage persistant, mise à jour).

## Ce qui n'est PAS testé
- **Sur un vrai téléphone** (Galaxy A12, Chrome) : installation réelle, icône sur l'écran d'accueil, mode avion réel, clavier, geste « retour » d'Android.
- **Aperçu des applis récentes d'Android** : l'appli masque l'écran quand elle passe en arrière-plan, mais une page web ne peut pas garantir ce que montre l'aperçu. **À regarder sur le A12.**
- **Réponse réelle de Chrome au stockage persistant** : dans les contrôles, la réponse de Chrome est simulée (accordé / refusé). La vraie réponse du A12 est à noter.
- **Mise à jour réelle sur GitHub Pages** : testée en local avec un faux numéro de version ; à refaire en vrai en publiant une version 0.1.1.
- **GitHub Pages** : pas encore publié (voir le rapport).
- Mode sombre / clair du **téléphone** (les contrôles utilisent la simulation du navigateur), couleur de la barre d'état Android, écran divisé ou autre orientation.
- Plusieurs onglets / fenêtres ouverts en même temps pendant une mise à niveau de la structure.
- Le déroulement d'une migration réelle (il n'y en a pas encore : la structure n° 1 est la première) : seul le mécanisme est testé, sur une base d'essai.
- Un échec isolé et **non reproduit** a été vu une fois (un toucher sur un élément « non visible » en début de série après une modification du code) ; 7 relances de suite à 0 échec ensuite.

## Écarts par rapport au plan et à la maquette
- Pas de glissement gauche / droite entre les écrans (la maquette l'avait) : pas demandé pour la coquille.
- Pas de transition animée entre les écrans.
- `theme_color` et `background_color` du manifeste sont fixes (bleu du bandeau sombre / fond sombre) : le manifeste ne peut pas suivre le thème. La page, elle, déclare deux couleurs de thème (clair et sombre).
- Le nom « Agenda » est partout (titre, manifeste, écran neutre).
