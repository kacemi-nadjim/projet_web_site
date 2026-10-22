# Rattrapage BC4 — Correspondance critères ↔ preuves

**Candidat** : KACEMI Nadjim — **Projet** : PixBank — **Bloc** : BC4 (option 1)
« Concevoir et développer des solutions web » (C4.1 à C4.10).

**Session 1** : 4 compétences acquises sur 10 (40 %), alors que la
validation du bloc en demande 60 %.
Ce document reprend **chaque critère de la grille**. Pour chacun, il
indique ce qui manquait en v1.0, ce qui a été fait en v1.1 et **où le
jury peut le vérifier**.

Barème de la grille : acquis = 2, en cours = 1, non acquis = 0.
Une compétence est acquise à partir de 1,2.

---

## Compétences non acquises en session 1

### C4.8 — Optimisation des requêtes et des performances de la base (0,67)

| Critère | S1 | Ce qui a été fait en v1.1 | Preuve |
|---|---|---|---|
| Requêtes optimisées, temps de réponse mesuré, indexation | En cours | Banc d'essai sur 50 000 images, SQLite et PostgreSQL. Index partiels et composites : galerie ×10 à ×22, anti force brute ×7 à ×27 | `docs/MESURES_PERFORMANCE.md` §1, `outils/benchmark_bdd.py`, `docs/mesures/benchmark_*.json` |
| Méthodes d'optimisation de l'accès aux données et de leur sécurité (permissions, transactions) | En cours | Préchargement des relations (fin des N+1), dépôt en transaction atomique, unicité garantie par la base, compte PostgreSQL à privilèges minimaux, accès aux fichiers filtré | `core/views.py` (`upload`, `media_protege`), `core/etl.py`, `docs/postgresql_setup.sql`, `test_performance.py` |
| Choix techniques justifiés et impact sur les performances globales | **Non acquis** | Tableau des choix (pourquoi un index **partiel** : constat `NOT is_deleted`). Plans `EXPLAIN` avant/après. Cas sans gain expliqués (sélectivité). Impact mesuré sur la page entière : export 1,6 s → 0,18 s | `docs/MESURES_PERFORMANCE.md` §1 « Choix techniques », « Cas sans gain » et §3 |

### C4.9 — Tests unitaires, d'intégration, de sécurité et d'accessibilité (1,00)

| Critère | S1 | Ce qui a été fait en v1.1 | Preuve |
|---|---|---|---|
| Les tests couvrent les fonctionnalités critiques, résultats clairs | **Non acquis** | 12 → **125 tests** ; couverture **62 % → 96 %** (vues 47 → 94 %, import des lots 11 → 98 %) ; parcours de labélisation testé de bout en bout avec les vrais ZIP ; suite validée sur SQLite **et** PostgreSQL | `docs/TESTS.md`, `core/tests/`, `docs/mesures/audits/coverage_v1.*.txt` |
| Tests de sécurité et d'accessibilité conformes aux normes | En cours | 32 tests de sécurité (OWASP : dépôt piégé, XSS/CSP, force brute, cloisonnement, bombe ZIP…) ; audits outillés `pip-audit` 9 → 0, `bandit` 4 → 0, `check --deploy` 1 → 0 ; contrôle automatique de structure accessible | `core/tests/test_securite.py`, `docs/SECURITE.md` §5, `docs/TESTS.md` §4 |
| Choix des tests expliqués | Acquis | Stratégie par type de test | `docs/TESTS.md` §1 |
| Anomalies analysées, solutions présentées | En cours | **20 anomalies** documentées : constat, cause, correctif, test de non-régression (dont 4 critiques) | `docs/REGISTRE_ANOMALIES.md` |

### C4.4 — Développement serveur et standards de programmation (1,00)

| Critère | S1 | Ce qui a été fait en v1.1 | Preuve |
|---|---|---|---|
| Standards de programmation démontrés, intégration front/back (temps de réponse serveur mesuré) | En cours | `ruff` : 32 erreurs → 0 (PEP 8, erreurs, règles de sécurité et Django), configuration versionnée ; temps de réponse et nombre de requêtes mesurés par page ; point de supervision `/sante/` | `pyproject.toml`, `docs/mesures/audits/ruff_v1.*.txt`, `docs/mesures/requetes_par_page.json` |
| Bonnes pratiques de conception (modularité, scalabilité), intégration validée par des tests | En cours | Logique métier sortie des vues : `etl`, `permissions`, `securite`, `statistiques`, `miniatures`, chacun testé séparément ; application sans état, prête pour PostgreSQL et plusieurs serveurs ; 20 tests d'intégration du module de lots | `core/*.py`, `core/tests/test_lots.py`, `core/tests/test_permissions.py` |

### C4.5 — Sécurité, conformité et responsabilité numérique (1,00)

| Critère | S1 | Ce qui a été fait en v1.1 | Preuve |
|---|---|---|---|
| Pratiques de sécurité conformes (RGPD, chiffrement) | Acquis | Renforcées : HTTPS/HSTS, CSP, cookies sécurisés, secrets hors du code | `config/settings.py`, `core/middleware.py` |
| Mesures de réduction de l'empreinte écologique, justifiées | **Non acquis** | Miniatures WebP : galerie **63,8 Mo → 0,25 Mo**, EcoIndex **C → A** (mesuré dans Chromium) ; pagination ; polices auto-hébergées ; export sans recompression (temps ÷ 8,8) ; index plus légers (−23 %) ; purges de données | `docs/MESURES_PERFORMANCE.md` §2, `outils/mesurer_pages.py`, `outils/ecoindex.py`, `docs/mesures/poids_pages.json` |
| Risques identifiés et solutions adaptées (monitoring des accès) | En cours | Analyse de 16 risques (probabilité, impact, mesure, test) ; **journal d'accès** en lecture seule (connexions, échecs, blocages, accès refusés, exports) ; anti force brute ; alertes e-mail | `docs/SECURITE.md` §1, back-office « Journal d'accès », `core/signals.py` |

### C4.7 — Conception et sécurité de la base de données (1,00)

| Critère | S1 | Ce qui a été fait en v1.1 | Preuve |
|---|---|---|---|
| Conception adaptée (PostgreSQL, schéma relationnel, types de données) | En cours | **PostgreSQL 16** pris en charge par `DATABASE_URL` et validé par les 125 tests ; diagramme entité-relation ; types justifiés un par un ; contraintes UNIQUE partielle, CHECK et PROTECT ; migration des données v1.0 testée sur les vraies données | `docs/SCHEMA_BDD.md`, `core/migrations/0006_*.py` |
| Sécurité des données stockées (chiffrement, contrôle d'accès, validation par des outils) | En cours | Photos **sorties de l'espace public** et servies après contrôle des droits ; mots de passe PBKDF2 (1 M d'itérations) ; compte BDD à privilèges minimaux + SSL ; sauvegardes vérifiées par SHA-256 ; 0 alerte `bandit` / `pip-audit` / `check --deploy` | `core/views.py::media_protege`, `docs/SECURITE.md` §2, `docs/postgresql_setup.sql` |

### C4.10 — Mises à jour et incidents après déploiement (1,00)

| Critère | S1 | Ce qui a été fait en v1.1 | Preuve |
|---|---|---|---|
| Plan des mises à jour (calendrier, gestion des versions) | En cours | Versionnage sémantique + étiquettes Git + CHANGELOG ; calendrier (alertes Django, mensuel, trimestriel, annuel) ; feuille de route Django 5.2 LTS (fin en avril 2028) → 6.2 LTS (Python 3.12 requis) ; mises à jour réelles : Django 5.2.15 → 5.2.18, puis Pillow 12.3.0 → 13.0.0 (v1.1.1, 35 failles signalées par `pip-audit`, corrigées le jour même) | `docs/MAINTENANCE.md` §1 à 3, `CHANGELOG.md` |
| Processus de déploiement structuré, supervision des incidents | En cours | Script de déploiement qui s'arrête à la moindre erreur et sauvegarde avant de modifier ; retour arrière testé (migration réversible) ; `/sante/` + surveillance externe ; e-mail sur erreur 500 ; processus d'incident (P1/P2/P3) et **2 fiches d'incidents réels** | `outils/deployer.sh`, `docs/DEPLOIEMENT.md`, `docs/INCIDENTS.md` |
| Stratégies expliquées (impact des évolutions technologiques sur performance et sécurité) | En cours | Procédure de mise à jour en 6 étapes (tests sur 2 moteurs, audits, accessibilité) ; analyse de l'impact d'une montée de version (Python, LTS, cycle annuel de Django à partir de 2028) | `docs/MAINTENANCE.md` §3 |

---

## Compétences déjà acquises (renforcées)

| Compétence | S1 | Renforcement v1.1 |
|---|---|---|
| C4.1 Architecture, accessibilité et sécurité dès la conception | 1,75 | Critère « flexible et scalable » (en cours) : PostgreSQL, application sans état, pagination, index, compteurs en base (compatibles avec plusieurs serveurs) |
| C4.2 Maquettes et prototypes | 2 | — |
| C4.3 Front-end mobile-first | 2 | Images à chargement différé avec dimensions déclarées, pagination accessible, EcoIndex A |
| C4.6 Conformité RGPD / RGAA | 2 | Effacement définitif après 30 jours, miniatures sans GPS, plus de transfert d'IP vers Google, alertes accessibles |

---

## Démonstration proposée pour l'oral (environ 6 minutes)

1. **`/sante/`** → affiche la version 1.1.1 et l'état de la base (supervision).
2. **Adresse d'une photo ouverte en navigation privée** → redirection vers
   la connexion. Connecté avec un autre client → 404, visible ensuite dans
   le journal d'accès (C4.5, C4.7).
3. **5 mauvais mots de passe**, puis le bon → refusé (« Trop de
   tentatives »), blocage journalisé (C4.5).
4. **Galerie, outils de développement du navigateur ouverts (onglet
   Réseau)** → quelques centaines de Ko au lieu de 64 Mo (C4.5).
5. **`python manage.py test`** en direct → 125 tests en 4 secondes, puis
   `coverage report` → 96 % (C4.9).
6. **Tableau avant/après** des index et du plan `EXPLAIN` (C4.8).
7. **`CHANGELOG.md` et `outils/deployer.sh`** → comment une version est
   publiée, supervisée et annulée si besoin (C4.10).
