# PixBank — Banque d'images d'entraînement pour le deep learning

Projet annuel — Bachelor Data & Business Intelligence (Nexa Digital School)
Titre RNCP40857 « Chef de projet web » — **V2**

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
- **RGPD** : pages légales complètes, consentement, effacement définitif après 30 jours, formulaires effacés après un an, journal
  conservé 180 jours, aucun service tiers
- **Sécurité** : anti force brute, journal d'accès, CSP, HTTPS/HSTS, anti
  bombe ZIP
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

## Prérequis

| Élément | Version | Remarque |
|---|---|---|
| Python | 3.11 à 3.14 | `python --version` pour vérifier (Pillow 13 exige 3.11 au minimum) |
| pip | fourni avec Python | installe les dépendances listées dans `requirements.txt` |
| Navigateur web | Chrome, Edge, Firefox ou Safari récent | voir « Compatibilité multi-navigateurs » |
| Git | facultatif | seulement pour cloner le dépôt au lieu d'utiliser l'archive |
| PostgreSQL 16 | facultatif | par défaut, le projet utilise SQLite (aucune installation) |

Aucune variable d'environnement n'est nécessaire pour l'installation
locale : `manage.py` active automatiquement le mode développement.

## Installation (poste local)

Depuis le dossier du projet (celui qui contient `manage.py`) :

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (Mac/Linux : source venv/bin/activate)
pip install -r requirements-dev.txt
python manage.py migrate         # crée la base SQLite db.sqlite3
python manage.py loaddata dump.json   # données de démonstration du projet
python manage.py runserver
```
Site : http://127.0.0.1:8000 — Back-office : http://127.0.0.1:8000/admin/

Le dossier `media/` (photos et ZIP de démonstration) est fourni avec le
code : il doit rester à côté de `manage.py`.

**Variante avec l'export SQL** : `dump.sql` contient la même base
(schéma + données) au format SQL SQLite. Au lieu de `migrate` et
`loaddata` :
```bash
python -c "import sqlite3; sqlite3.connect('db.sqlite3').executescript(open('dump.sql', encoding='utf-8').read())"
```
(ou `sqlite3 db.sqlite3 < dump.sql` si l'outil `sqlite3` est installé).

**Variante sans données** : `python manage.py seed` crée une démonstration
minimale (mêmes comptes que ci-dessous).

Ces trois procédures ont été vérifiées sur une installation neuve
(base vide, environnement virtuel neuf).

## Identifiants de test

Mot de passe identique pour les cinq comptes ci-dessous : **demo1234**

| Compte | Rôle | Entreprise | À tester |
|---|---|---|---|
| **admin** | Administrateur (accès au back-office `/admin/`) | Wassa | Validation des dépôts, journal d'accès, comptes, demandes d'inscription |
| lea_ds | Data scientist | Wassa | Dashboard, galerie, export du dataset, création de lots |
| karim_contrib | Contributeur | Wassa | Dépôt d'images, lot assigné, soumission du travail |
| sara_ds_acme | Data scientist | ACME Parking | Cloisonnement : ne voit aucune donnée de Wassa |
| paul_acme | Contributeur | ACME Parking | Cloisonnement côté contributeur |

Ces comptes ne contiennent que des données de démonstration. Pour
vérifier la protection contre la force brute, se tromper 5 fois de mot
de passe sur un compte : il est bloqué 15 minutes.

## Accès administrateur au back-office

- Adresse : `/admin/` (en local : http://127.0.0.1:8000/admin/)
- Identifiant : **admin** — mot de passe : **demo1234**
- Rubriques utiles : *Images* (validation avec aperçu), *Journal d'accès*
  (lecture seule), *Demandes d'inscription*, *Lots de travail*,
  *Messages de contact*, *Utilisateurs* et *Clients*.

Créer un autre administrateur : `python manage.py createsuperuser`.

## Base de données : connexion

| Moteur | Utilisation | Identifiants |
|---|---|---|
| **SQLite** (par défaut) | installation locale et site de démonstration | Aucun identifiant : la base est le fichier `db.sqlite3`, créé par `migrate` (ou par l'import de `dump.sql`) |
| **PostgreSQL 16** (cible de production) | activé par la variable `DATABASE_URL` | Base `pixbank`, utilisateur `pixbank_app`, mot de passe choisi à la création (script `outils/postgresql_setup.sql`) |

Exemple PostgreSQL :
```bash
# Windows : set DATABASE_URL=...   Mac/Linux : export DATABASE_URL=...
DATABASE_URL=postgres://pixbank_app:MOT_DE_PASSE@localhost:5432/pixbank
python manage.py migrate
python manage.py loaddata dump.json
```

## Compatibilité multi-navigateurs

| Vérification | Résultat |
|---|---|
| Recette automatisée dans Chromium (`outils/verifier_navigateur.py`) : parcours complet, ordinateur et mobile (320 px, largeur de référence du RGAA) | 0 erreur JavaScript, 0 ressource en erreur, aucun débordement horizontal |
| Analyse des propriétés CSS (`outils/compatibilite_css/`, base de données « Can I use ») pour les 2 dernières versions de Chrome, Edge, Firefox, Safari, Safari iOS, Chrome Android et Firefox ESR | Aucune propriété non prise en charge |
| JavaScript | Deux petits scripts dans des fichiers séparés (bandeau cookies, confirmation avant suppression), écrits en JavaScript standard compatible avec tous les navigateurs |
| Validité du HTML (validateur W3C, 17 pages) | 0 erreur, 0 avertissement |

Le site n'utilise ni framework JavaScript ni fonctionnalité expérimentale :
le rendu est identique sur les navigateurs récents.

Démo recommandée :
1. Se connecter en `lea_ds`, ouvrir le **Dashboard**, puis **Exporter le dataset**.
2. Se connecter en `sara_ds_acme` pour constater le cloisonnement.
3. Ouvrir l'adresse d'une photo dans une fenêtre de navigation privée :
   l'accès est refusé.

## Tests et qualité

```bash
python manage.py test                              # 136 tests (~4 à 25 s selon le PC)
coverage run manage.py test && coverage report     # couverture : 96 %
ruff check .  &&  bandit -r core config -x core/tests,core/migrations
pip-audit -r requirements.txt
```

Comparaison avec la V1 (étiquette Git `V1`), mêmes règles des deux côtés :
`ruff check --isolated --select E,W,F,B --line-length 100 --extend-exclude core/migrations .`
→ 32 erreurs sur la V1, 0 sur la V2.

**Audit d'accessibilité** (WCAG 2.1 A et AA, moteur axe-core, 16 pages),
site lancé avec les données de démonstration :
```bash
pip install playwright && playwright install chromium
cd outils/audits_web && npm install && cd ../..
python outils/audit_accessibilite.py --base http://127.0.0.1:8000
# → Pages auditées : 16 — éléments en défaut : 0
```

**Scans de sécurité** (référentiel OWASP Top 10, 2025) :
```bash
# Analyse statique : règles de sécurité Django / Python de Semgrep (classées OWASP)
pip install semgrep && git clone --depth 1 https://github.com/semgrep/semgrep-rules
semgrep scan --metrics=off --config semgrep-rules/python/django/security \
  --config semgrep-rules/python/lang/security --exclude core/tests --exclude core/migrations .
# Test dynamique : OWASP ZAP (exploration + scan actif) sur le site lancé
zap.sh -cmd -quickurl http://127.0.0.1:8000/ -quickout rapport_zap.html
```
Résultats sur la V2 : Semgrep, 6 signalements (1 vraie faiblesse corrigée :
injection de formule dans le CSV exporté ; 5 faux positifs expliqués dans le
dossier) ; ZAP, aucune alerte de risque élevé ou moyen.

**Intégration continue** : le fichier `.github/workflows/qualite.yml` relance
automatiquement sur GitHub `pip-audit`, `ruff`, `bandit`, les tests (SQLite
et PostgreSQL 16) et `check --deploy`, à chaque envoi de code et chaque lundi.

**Contrôle de la configuration de production** : sur un poste sans
fichier `.env`, `manage.py` active le mode développement ; la commande
`check --deploy` affiche alors 5 avertissements attendus (HTTPS, cookies
sécurisés, HSTS, DEBUG). Pour contrôler les réglages réels de production :
```bash
# Mac/Linux (Windows : définir les mêmes variables avec « set »)
DJANGO_DEBUG=False DJANGO_SECRET_KEY=une-cle-longue-et-aleatoire-de-50-caracteres-minimum \
DJANGO_ALLOWED_HOSTS=nadjimkacemi.pythonanywhere.com python manage.py check --deploy
# → System check identified no issues (0 silenced).
```
Sur le serveur, le fichier `.env` fournit ces valeurs et le script de
déploiement refuse de publier une version si cette commande signale le
moindre avertissement.

| Indicateur | V1 | V2 |
|---|---|---|
| Tests automatisés | 12 | 136 |
| Accessibilité (axe-core, WCAG 2.1 AA, 16 pages) | non mesurée | 0 élément en défaut |
| Couverture du code | 62 % | 96 % |
| Vulnérabilités des dépendances (`pip-audit`) | 9 | 0 |
| Alertes `bandit` / erreurs `ruff` | 4 / 32 | 0 / 0 |
| Galerie (24 photos) — poids / EcoIndex | 63,8 Mo / C | 0,26 Mo / A |
| Export (24 photos) — requêtes SQL / temps | 31 / 1,6 s | 7 / 0,18 s |

Les lignes « 24 photos » ont été mesurées avec 24 photos de smartphone
(4032 × 3024, 2,7 Mo en moyenne). Pour mesurer l'export sur sa propre base :
```bash
python outils/mesurer_export.py            # compte lea_ds, 5 essais
```
Avec les données de démonstration (11 images validées, très légères), on
obtient 7 requêtes en V2 contre 18 en V1 : la V1 faisait une requête de
plus par image exportée (7 + 11). Le temps dépend surtout du poids des
photos : il n'est significatif qu'avec de vraies photos.

## Documentation

| Élément | Contenu |
|---|---|
| `KACEMI_NADJIM_PROJET_V2.pdf` | Dossier de projet (conception, choix techniques, mesures, tests, maintenance) |
| [CHANGELOG.md](CHANGELOG.md) | Historique des versions |

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
  tests/             136 tests (unitaires, intégration, sécurité, conformité, performance)
templates/       pages HTML (mobile-first)
static/          CSS, polices auto-hébergées, JS
outils/          déploiement et outils de mesure (benchmark, EcoIndex, accessibilité)
.github/         intégration continue (tests et audits à chaque envoi et chaque lundi)
```
