# Sécurité, conformité et protection des données — PixBank v1.1

PixBank stocke des **données personnelles sensibles** (photos de visages,
plaques d'immatriculation) pour plusieurs entreprises clientes. Les
mesures ci-dessous découlent d'une analyse de risques. Chaque mesure est
vérifiée par au moins un test automatisé.

## 1. Analyse des risques

| # | Risque | Probabilité | Impact | Mesure en place | Preuve |
|---|---|---|---|---|---|
| R1 | Un client voit les images d'un autre client | Moyenne | Critique | Filtre par client sur **chaque** requête, côté serveur ; règles centralisées dans `permissions.py` | `test_permissions`, `test_regles_metier`, `AccesMediasTest` |
| R2 | Accès direct à une photo par son adresse | Élevée | Critique | Fichiers servis uniquement par `media_protege` après contrôle des droits | `AccesMediasTest` (7 tests) |
| R3 | Un contributeur récupère la vérité terrain (triche) | Moyenne | Majeur | ZIP de référence réservé aux managers ; le contributeur reçoit un ZIP reconstruit sans les labels | `test_contributeur_ne_recupere_pas_la_verite_terrain` |
| R4 | Dépôt d'un fichier malveillant (HTML, script) | Moyenne | Critique | Contenu vérifié par Pillow, liste blanche de formats, 15 Mo max, en-tête `nosniff` | `DepotFichiersTest` |
| R5 | XSS (script injecté dans une page) | Faible | Critique | Échappement automatique des gabarits Django **et** CSP `script-src 'self'` (aucun script en ligne) | `EnTetesTest` |
| R6 | Bombe ZIP / chemins `../` saturant ou piégeant le serveur | Faible | Majeur | Taille, nombre de fichiers, taille décompressée et chemins vérifiés avant ouverture | `ValidationZipTest` |
| R7 | Mot de passe deviné par force brute | Élevée | Critique | Blocage 15 min après 5 échecs (site et back-office), journalisé | `ForceBruteTest` |
| R8 | Injection SQL | Faible | Critique | ORM Django : requêtes paramétrées, aucune requête SQL écrite à la main dans les vues | revue de code, `bandit` |
| R9 | CSRF (action déclenchée à l'insu de l'utilisateur) | Faible | Majeur | Jeton CSRF sur tous les formulaires, suppression accessible en POST uniquement | `test_suppression_exige_post` |
| R10 | Clickjacking (site affiché dans une iframe piège) | Faible | Moyen | `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'` | `EnTetesTest` |
| R11 | Interception réseau | Faible | Critique | HTTPS obligatoire (redirection), HSTS 1 an, cookies `Secure` et `HttpOnly` | `check --deploy` sans avertissement |
| R12 | Fuite d'informations par les pages d'erreur | Moyenne | Majeur | `DEBUG=False` par défaut, clé secrète obligatoire hors du code | `ConfigurationProductionTest` |
| R13 | Dépendance vulnérable | Élevée | Critique | Versions figées, `pip-audit` mensuel, Django LTS maintenu | `pip-audit` : 0 vulnérabilité |
| R14 | Doublon créé par deux dépôts simultanés | Faible | Faible | Contrainte d'unicité **en base** (en plus du contrôle applicatif) | `test_contrainte_unicite_garantie_par_la_base` |
| R15 | Perte de données (panne, erreur humaine) | Moyenne | Critique | Sauvegarde quotidienne vérifiée par SHA-256, rotation sur 7 jours, restauration testée | `SauvegardeRestaurationTest` |
| R16 | Intrusion non détectée | Moyenne | Majeur | Journal d'accès en lecture seule : connexions, échecs, blocages, exports, téléchargements, accès refusés | `JournalTest`, `ForceBruteTest` |

**Risque résiduel accepté (R7)** : comme le blocage se fait par identifiant,
quelqu'un qui connaît un identifiant peut le bloquer volontairement
pendant 15 minutes. Ce choix est délibéré. Un blocage par adresse IP
serait contournable, car l'adresse transmise par le proxy de l'hébergeur
peut être falsifiée. La gêne reste limitée (15 min), et elle est visible
dans le journal, où l'administrateur peut identifier l'origine.

## 2. Protection des données stockées

| Donnée | Protection |
|---|---|
| Mots de passe | Jamais stockés en clair : hachage PBKDF2-SHA256 avec sel (Django), 1 000 000 d'itérations |
| Photos et ZIP | Hors de l'espace public. Accès uniquement après authentification et contrôle du client ; refus journalisés |
| Miniatures | Métadonnées EXIF retirées (position GPS, modèle d'appareil) |
| Base de données | En production PostgreSQL, compte applicatif à privilèges minimaux (`docs/postgresql_setup.sql`) ; jamais d'accès superutilisateur pour l'application |
| Sauvegardes | Manifeste avec empreintes SHA-256 : une sauvegarde altérée est refusée à la restauration |
| Journal d'accès | Non modifiable, même par un administrateur ; conservation limitée à 180 jours |

**Chiffrement au repos** : la confidentialité repose aujourd'hui sur le
contrôle d'accès applicatif et sur le chiffrement en transit (HTTPS).
Le chiffrement des fichiers sur le disque relève de l'hébergeur et figure
dans les évolutions envisagées (stockage objet chiffré, voir
[MAINTENANCE.md](MAINTENANCE.md)).

## 3. Conformité RGPD

| Principe RGPD | Mise en œuvre |
|---|---|
| Base légale / consentement | Case obligatoire pour toute catégorie « donnée personnelle », pour l'inscription et pour le contact |
| Minimisation | Miniatures sans EXIF ; journal limité au strict nécessaire (identifiant, IP, événement) |
| Limitation de conservation | Journal : 180 jours (`purger_journal`). Images supprimées : effacement définitif après 30 jours (`purger_images_supprimees`) |
| Droit à l'effacement (art. 17) | Suppression immédiate pour l'utilisateur, effacement réel (ligne + fichiers) après 30 jours |
| Traçabilité / responsabilité | Historique des exports, journal d'accès non modifiable |
| Pas de transfert à des tiers | Plus aucun appel à Google Fonts ; aucun traceur ; un seul cookie technique de session |
| Sécurité du traitement (art. 32) | Voir les sections 1 et 2 |

## 4. Accessibilité (RGAA / WCAG)

- La conformité de la v1.0 est conservée : contrastes corrigés,
  Lighthouse Accessibilité 90+, validation W3C sans erreur, approche
  mobile-first.
- Ajouts v1.1 :
  - messages d'erreur annoncés (`role="alert"`) ;
  - navigation de pagination balisée (`aria-label`, `aria-current`) ;
  - attribut `alt` décrivant les catégories de chaque image ;
  - dimensions d'image déclarées.

## 5. Audits automatisés (avant / après)

| Contrôle | v1.0 | v1.1 |
|---|---|---|
| `pip-audit` (dépendances) | 9 vulnérabilités | 0 |
| `check --deploy` (configuration production) | 1 avertissement | 0 |
| `bandit` (code) | 4 alertes | 0 |
| Tests de sécurité automatisés | 3 | 32 (29 nouveaux dans `test_securite.py` et `test_permissions.py`, plus les 3 de la v1.0) |
