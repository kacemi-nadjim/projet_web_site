# PixBank — Banque d'images d'entraînement pour le deep learning

Projet annuel — Bachelor Data & Business Intelligence (Nexa Digital School)
Titre RNCP40857 « Chef de projet web » — **version 1.1.0**

## Site en ligne

**https://nadjimkacemi.pythonanywhere.com** — back-office : `/admin/` — supervision : `/sante/`

Plateforme web **multi-clients** qui centralise les images d'entraînement
des modèles de computer vision :
- des contributeurs déposent des images classées par catégorie (visage,
  plaque, écran, animal, véhicule…) ;
- un administrateur valide les dépôts ;
- les data scientists du client filtrent puis **exportent un dataset**
  (ZIP + annotations CSV) ;
- un module de labélisation contrôle automatiquement la qualité des
  annotations (IoU).

## Fonctionnalités

- Authentification à 3 rôles : contributeur / data scientist / administrateur
- **Cloisonnement multi-clients** appliqué côté serveur, y compris pour
  les fichiers (photos, ZIP)
- Dépôt **multiple** et **multi-catégories**, contenu des images vérifié,
  **doublons** détectés par SHA-256 (garantie en base)
- **Galerie paginée** affichant des miniatures WebP légères (sans
  métadonnées GPS)
- Validation des dépôts dans le back-office (avec aperçu)
- **Export ETL** : ZIP des images + `annotations.csv`
- **Dashboard BI** : indicateurs, répartition par catégorie, historique des exports
- **Module de labélisation** : lot de référence, travail du contributeur,
  contrôle qualité (complétude, catégories, IoU, images floues)
- **RGPD** : consentement, effacement définitif après 30 jours, journal
  conservé 180 jours, aucun service tiers
- **Sécurité** : anti force brute, journal d'accès, CSP, HTTPS/HSTS, anti
  bombe ZIP (voir [docs/SECURITE.md](docs/SECURITE.md))
- **Exploitation** : sauvegarde/restauration vérifiée, supervision
  `/sante/`, alertes e-mail, déploiement scripté

## Stack technique

| Brique | Techno | Justification |
|---|---|---|
| Back-end | Django 5.2 LTS (5.2.18) | Framework Python « piles incluses » : sécurité native (CSRF, injections SQL, XSS), ORM, back-office ; maintenu jusqu'en avril 2028 |
| Front-end | Gabarits Django (rendu serveur) + CSS mobile-first | Site orienté contenu : rapide, sans framework JavaScript à télécharger |
| Base de données | PostgreSQL 16 (production, via `DATABASE_URL`) / SQLite (développement) | Données structurées et reliées → relationnel ; index partiels et contraintes |
| Images | Pillow | Vérification du contenu, dimensions, miniatures WebP |
| Export | `zipfile` + `csv` (bibliothèque standard) | Brique ETL : Extract → Transform → Load |

## Installation (développement)

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (Mac/Linux : source venv/bin/activate)
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed            # données de démonstration
python manage.py runserver
```
Site : http://127.0.0.1:8000 — Back-office : http://127.0.0.1:8000/admin/

Données de démonstration réelles du projet (au lieu de `seed`) :
`python manage.py loaddata dump.json` (avec le dossier `media/` fourni).
`dump.sql` contient la même base au format SQL (SQLite).

## Identifiants de démonstration

| Compte | Mot de passe | Rôle | Client |
|---|---|---|---|
| admin | demo1234 | Administrateur | Wassa |
| karim_contrib | demo1234 | Contributeur | Wassa |
| lea_ds | demo1234 | Data Scientist | Wassa |
| paul_acme | demo1234 | Contributeur | ACME Parking |
| sara_ds_acme | demo1234 | Data Scientist | ACME Parking |

Ces comptes servent uniquement à la démonstration. Dans un vrai
déploiement, la commande `seed` n'est jamais lancée.

Démo recommandée :
1. Se connecter en `lea_ds`, ouvrir le **Dashboard**, puis **Exporter le dataset**.
2. Se connecter en `sara_ds_acme` pour constater le cloisonnement.
3. Ouvrir l'adresse d'une photo dans une fenêtre de navigation privée :
   l'accès est refusé.

## Tests et qualité

```bash
python manage.py test                              # 125 tests (~4 s)
coverage run manage.py test && coverage report     # couverture : 96 %
ruff check .  &&  bandit -r core config -x core/tests,core/migrations
pip-audit -r requirements.txt
```

| Indicateur | v1.0 | v1.1 |
|---|---|---|
| Tests automatisés | 12 | 125 |
| Couverture du code | 62 % | 96 % |
| Vulnérabilités des dépendances (`pip-audit`) | 9 | 0 |
| Alertes `bandit` / erreurs `ruff` | 4 / 32 | 0 / 0 |
| Galerie (24 photos) — poids / EcoIndex | 63,8 Mo / C | 0,25 Mo / A |
| Export (24 photos) — requêtes SQL / temps | 31 / 1,6 s | 7 / 0,18 s |

## Documentation

| Document | Contenu |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | Historique des versions |
| [docs/RATTRAPAGE_BC4.md](docs/RATTRAPAGE_BC4.md) | Correspondance critères du bloc 4 ↔ preuves |
| [docs/MESURES_PERFORMANCE.md](docs/MESURES_PERFORMANCE.md) | Index, requêtes, poids des pages, EcoIndex : mesures avant/après |
| [docs/TESTS.md](docs/TESTS.md) | Plan de tests, couverture, audits |
| [docs/REGISTRE_ANOMALIES.md](docs/REGISTRE_ANOMALIES.md) | 20 anomalies : cause, correctif, test |
| [docs/SECURITE.md](docs/SECURITE.md) | Analyse de risques, RGPD, RGAA |
| [docs/SCHEMA_BDD.md](docs/SCHEMA_BDD.md) | Modèle relationnel, types, contraintes, index, sauvegardes |
| [docs/MAINTENANCE.md](docs/MAINTENANCE.md) | Versions, calendrier de mises à jour, feuille de route, supervision |
| [docs/INCIDENTS.md](docs/INCIDENTS.md) | Processus d'incident et fiches réelles |
| [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md) | Mise en production, retour arrière, PostgreSQL, tâches planifiées |
| `docs/captures/` | Captures d'écran de la recette v1.1 |
| `docs/mesures/` | Résultats bruts des mesures et des audits (avant/après) |

## Structure

```
config/          réglages (variables d'environnement), routes, WSGI, chargement .env
core/
  models.py          modèle de données (index, contraintes, journal d'accès)
  views.py           vues : vérification des droits + appel de la logique métier
  etl.py             construction du dataset exporté
  qualite.py         moteur de contrôle qualité IoU
  batch_utils.py     lecture des ZIP de lots
  securite.py        validation des fichiers, anti force brute
  permissions.py     règles d'accès (cloisonnement)
  statistiques.py    indicateurs du dashboard
  miniatures.py      miniatures WebP (éco-conception)
  middleware.py      en-têtes de sécurité (CSP...)
  signals.py         alimentation du journal d'accès
  management/commands/  seed, sauvegarder, restaurer, purges, miniatures...
  tests/             125 tests (unitaires, intégration, sécurité, performance)
templates/       pages HTML (mobile-first)
static/          CSS, polices auto-hébergées, JS
outils/          déploiement et outils de mesure (benchmark, EcoIndex)
docs/            documentation technique et mesures
```
