# PixBank — Banque d'images d'entraînement pour le deep learning

Projet annuel — Bachelor Data & Business Intelligence (Nexa Digital School)
Titre RNCP40857 « Chef de projet web »

## 🌐 Site en ligne (URL publique)

**https://nadjimkacemi.pythonanywhere.com**

Back-office administrateur : https://nadjimkacemi.pythonanywhere.com/admin/

Le site est déployé et accessible directement depuis un navigateur, sans
installation. Les identifiants de test figurent plus bas dans ce document.
Hébergement : PythonAnywhere (offre gratuite), servi en HTTPS.

Plateforme web **multi-clients** centralisant les images d'entraînement des
modèles de computer vision. Des contributeurs déposent des images classées
par catégorie (visage, plaque, écran, animal, véhicule...), un administrateur
valide les dépôts, les data scientists du client filtrent puis **exportent un
dataset** (ZIP + annotations CSV) pour entraîner leurs modèles.

## Fonctionnalités

- Authentification à 3 rôles : contributeur / data scientist / administrateur
- **Cloisonnement multi-clients** : chaque organisation ne voit que ses données
- Dépôt d'images **multiple** avec **multi-catégories** (une image, plusieurs labels)
- **Détection de doublons** par empreinte SHA-256 au dépôt
- Workflow de **validation qualité** par l'administrateur (back-office)
- Conformité **RGPD** : consentement obligatoire pour les données personnelles, soft delete (droit à l'effacement)
- **Export ETL** : génération d'un ZIP contenant les images + un fichier `annotations.csv`
- **Dashboard BI** : KPIs, répartition par catégorie, état des dépôts, historique des exports
- Traçabilité des exports (qui a téléchargé quoi, quand)
- **Module de labélisation** : le manager dépose un lot d'images (ZIP avec vérité terrain), le stagiaire labélise sur LabelMe et redépose son travail, le site contrôle automatiquement la qualité (complétude, catégories, score de précision IoU, détection des images signalées floues)
- **Demande d'inscription** : un visiteur demande à devenir contributeur ; l'administrateur vérifie et crée le compte manuellement (aucun accès automatique)

## Stack technique

| Brique | Techno | Justification |
|---|---|---|
| Back-end | Django 5.2 (LTS) | Framework Python « piles incluses » : sécurité native (CSRF, injections SQL, XSS), ORM, back-office admin intégré |
| Front-end | Templates Django (SSR) + CSS mobile-first | Site orienté contenu : rendu serveur = rapidité + SEO |
| Base de données | SQLite (dev) → PostgreSQL (prod) | Données à structure stricte → relationnel, intégrité par clés étrangères |
| Traitement images | Pillow | Validation des fichiers + extraction des dimensions |
| Export | zipfile + csv (stdlib Python) | Brique ETL : Extract (base) → Transform (CSV) → Load (ZIP) |

## Installation

```bash
python -m venv venv
venv\Scripts\activate          # Windows  (Mac/Linux : source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed         
python manage.py runserver
```

Site : http://127.0.0.1:8000 — Back-office : http://127.0.0.1:8000/admin/

## Identifiants de test

| Compte | Mot de passe | Rôle | Client |
|---|---|---|---|
| admin | demo1234 | Administrateur | Wassa |
| karim_contrib | demo1234 | Contributeur | Wassa |
| lea_ds | demo1234 | Data Scientist | Wassa |
| paul_acme | demo1234 | Contributeur | ACME Parking |
| sara_ds_acme | demo1234 | Data Scientist | ACME Parking |

Démo recommandée : se connecter en `lea_ds`, ouvrir le **Dashboard**, puis
cliquer **Exporter le dataset** depuis la galerie → un ZIP se télécharge.
Comparer avec `sara_ds_acme` pour constater le cloisonnement.

## Tests

```bash
python manage.py test
```

12 tests couvrent les règles critiques : cloisonnement, RGPD, export, soft delete.

## Base de données

`dump.sql` à la racine (structure + données de démo). Régénérer :
```bash
python -c "import sqlite3;[print(l) for l in sqlite3.connect('db.sqlite3').iterdump()]" > dump.sql
```

## Structure

```
config/      Configuration Django
core/
  models.py  MCD : Client, User, Category, Image (multi-cat.), Export
  views.py   galerie, upload (multiple+anti-doublon), exporter (ETL), dashboard
  forms.py   validation (multi-fichiers, RGPD)
  admin.py   back-office, validation des dépôts
  tests.py   tests automatisés
  management/commands/seed.py   jeu de données de test
templates/   pages HTML (mobile-first)
static/css/  feuille de style
```
