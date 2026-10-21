# Plan de tests et résultats — PixBank v1.1

## 1. Stratégie

| Type de test | Ce qu'il vérifie | Exemple dans PixBank |
|---|---|---|
| **Unitaire** | Une fonction isolée, sans navigateur ni serveur | Calcul de l'IoU, règles d'accès, validation d'un ZIP |
| **Intégration** | Un parcours complet : requête HTTP → vue → base → réponse | Créer un lot avec le vrai ZIP de 20 images, puis soumettre le travail |
| **Sécurité** | Qu'une attaque identifiée échoue | Dépôt d'un fichier HTML piégé, force brute, accès hors périmètre |
| **Performance** | Qu'une page ne ralentit pas quand la base grossit | Nombre de requêtes SQL constant, index utilisés |
| **Non-régression** | Qu'un bug corrigé ne revient pas | Formulaire de contact (INC-002), miniatures après migration (ANO-010) |
| **Accessibilité** | Que la structure des pages reste accessible | Langue déclarée, un seul titre `h1`, alertes `role="alert"` |

Toute anomalie corrigée reçoit un test qui échouerait si elle revenait
(voir [REGISTRE_ANOMALIES.md](REGISTRE_ANOMALIES.md)).

## 2. Lancer les tests

```bash
python manage.py test                       # 125 tests, environ 3 secondes
coverage run manage.py test && coverage report   # taux de couverture
DATABASE_URL=postgres://… python manage.py test  # même suite sur PostgreSQL
```

Les tests sont **isolés** de l'environnement réel (`core/tests/runner.py`) :
dossier `media/` temporaire, base de test créée puis détruite, journaux
neutralisés.

## 3. Organisation (125 tests)

| Fichier | Tests | Fonctionnalités critiques couvertes |
|---|---:|---|
| `test_regles_metier.py` | 12 | Les 12 tests de la v1.0 : cloisonnement, RGPD, export, suppression logique, inscription, IoU, rattachement, mot de passe |
| `test_securite.py` | 26 | Dépôt de fichiers piégés, bombe ZIP, chemins `../`, accès aux médias, force brute, journal, en-têtes CSP, configuration de production |
| `test_images.py` | 24 | Dépôt multiple, doublons SHA-256 (code **et** contrainte de base), miniatures, EXIF/GPS, galerie et pagination, export ETL complet, dashboard, back-office, formulaire de contact |
| `test_lots.py` | 20 | Labélisation de bout en bout avec les vrais ZIP : création, téléchargement sans les réponses, travail réussi → VALIDÉ, travail échoué → À CORRIGER, fichiers invalides, cloisonnement |
| `test_maintenance.py` | 14 | Sauvegarde puis restauration après sinistre simulé, détection d'une sauvegarde corrompue, rotation, purges RGPD, supervision `/sante/`, fichier `.env`, contraintes CHECK et PROTECT |
| `test_qualite.py` | 10 | Moteur IoU : recouvrement partiel exact, polygones, images manquantes, imprécises, catégories interdites, JSON corrompu |
| `test_pages_et_commandes.py` | 10 | Pages publiques et privées, commandes `seed` et `reset_admin`, workflow d'approbation des inscriptions |
| `test_performance.py` | 6 | Nombre de requêtes SQL constant (export, galerie, dashboard), index réellement utilisés (`EXPLAIN`) |
| `test_permissions.py` | 3 | Matrice complète « qui peut voir / gérer quoi » pour chaque rôle |

## 4. Résultats

### Exécution
```
Ran 125 tests in 2.918s — OK                    (SQLite)
Ran 125 tests in 4.746s — OK (skipped=3)        (PostgreSQL 16)
```
Les 3 tests ignorés sous PostgreSQL lisent un plan d'exécution au format
propre à SQLite. Sous PostgreSQL, le même contrôle est fait par
`outils/benchmark_bdd.py` (voir [MESURES_PERFORMANCE.md](MESURES_PERFORMANCE.md)).

### Couverture du code (part des lignes exécutées par les tests)

| Module | v1.0 (12 tests) | v1.1 (125 tests) |
|---|---:|---:|
| `views.py` (les pages) | 47 % | **94 %** |
| `batch_utils.py` (import des lots) | 11 % | **98 %** |
| `qualite.py` (moteur IoU) | 81 % | **98 %** |
| `models.py` | 91 % | **96 %** |
| `securite.py`, `etl.py`, `permissions.py` (nouveaux) | — | 97 à 100 % |
| **Total** | **62 %** | **96 %** |

Rapports complets : `docs/mesures/audits/coverage_v1.0.txt` et `coverage_v1.1.txt`.
Lignes non couvertes restantes : branches de secours, comme un fichier
illisible pendant la génération d'une miniature ou une erreur disque.

### Tests de sécurité outillés

| Outil | Ce qu'il contrôle | v1.0 | v1.1 |
|---|---|---|---|
| `pip-audit` | Vulnérabilités connues des dépendances | **9 alertes** (Django 5.2.15) | **0** |
| `manage.py check --deploy` | Réglages de sécurité Django pour la production | 1 avertissement (clé secrète) | **0** |
| `bandit` | Failles courantes dans le code Python | 4 alertes (faible) | **0** |
| `ruff` (règles E, F, W, I, B, UP, S, DJ) | Erreurs, style PEP 8, sécurité, bonnes pratiques Django | 32 erreurs | **0** |
| Validateur W3C (Nu Html Checker), 17 pages | Validité du HTML (accessibilité, compatibilité navigateurs) | 5 erreurs | **0 erreur, 0 avertissement** |
| `doiuse` (base « Can I use »), `outils/compatibilite_css/` | Propriétés CSS prises en charge par Chrome, Edge, Firefox, Safari, Safari iOS, Chrome Android (2 dernières versions) et Firefox ESR | — | **0 propriété non prise en charge** |

Sorties brutes : `docs/mesures/audits/`.

### Accessibilité
- Les audits Lighthouse de la v1.0 restent valables (Accessibilité 90+,
  Bonnes pratiques 100). Les contrastes avaient déjà été corrigés.
- Ajouts v1.1 :
  - erreurs de formulaire annoncées aux lecteurs d'écran (`role="alert"`) ;
  - pagination balisée (`<nav aria-label>`, `aria-current`) ;
  - dimensions des images déclarées (pas de décalage de mise en page).
- Contrôle automatique : `test_pages_et_commandes.PagesPubliquesTest`
  vérifie, sur chaque page publique, la langue, l'unicité du `h1` et la
  balise `viewport`.

### Recette dans un vrai navigateur
`outils/verifier_navigateur.py` parcourt le site dans Chromium avec les
données de démonstration :
- **0** erreur JavaScript, **0** violation de la politique CSP,
  **0** ressource en erreur ;
- photo inaccessible sans connexion (redirection vers la connexion) ;
- 16 miniatures sur 16 affichées dans la galerie ; export téléchargé ;
- fichier piégé refusé avec message ;
- blocage après 5 échecs de connexion ;
- 20 aperçus sur 20 dans le back-office ;
- largeur mobile (390 px) respectée, sans défilement horizontal.

Captures : `docs/captures/`.

## 5. Anomalies découvertes par les tests

La campagne de tests a mis au jour 20 anomalies, dont 4 critiques. Elles
sont toutes corrigées et couvertes par un test. Détail et analyse de
cause : [REGISTRE_ANOMALIES.md](REGISTRE_ANOMALIES.md).
