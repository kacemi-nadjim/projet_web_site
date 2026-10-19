# Plan de maintenance et de mises à jour — PixBank

Objectif : garder PixBank **sûr, performant et conforme** dans la durée,
en planifiant les mises à jour au lieu de les subir.

## 1. Gestion des versions

PixBank suit le **versionnage sémantique** (SemVer) : `MAJEUR.MINEUR.CORRECTIF`.

| Changement | Exemple | Version |
|---|---|---|
| Correctif sans changement visible | Corriger un bug d'affichage | 1.1.0 → 1.1.**1** |
| Nouvelle fonctionnalité compatible | Ajouter un filtre à la galerie | 1.1 → 1.**2**.0 |
| Changement incompatible | Changer le format de l'export CSV | 1.x → **2**.0.0 |

- Chaque version est une **étiquette Git** (`git tag v1.1.0`).
- Chaque version est décrite dans [CHANGELOG.md](../CHANGELOG.md).
- La version en ligne s'affiche en pied de page et sur `/sante/`.
- On sait donc toujours quelle version tourne, et on peut revenir à la
  précédente en une commande (voir [DEPLOIEMENT.md](DEPLOIEMENT.md)).

## 2. Calendrier des mises à jour

| Fréquence | Action | Outil | Responsable |
|---|---|---|---|
| **À réception d'une alerte** | Correctif de sécurité Django : déployé sous 7 jours (sous 48 h si la faille est critique) | Liste de diffusion `django-announce` (alertes publiées à l'avance) | Chef de projet |
| **Mensuelle** (1er lundi du mois) | Contrôle des vulnérabilités connues des dépendances | `pip-audit -r requirements.txt` | Chef de projet |
| **Mensuelle** | Revue du journal d'accès (pics d'échecs de connexion, accès refusés) et des erreurs | back-office « Journal d'accès », `logs/pixbank.log` | Administrateur |
| **Trimestrielle** | Mise à jour des versions correctives (Django 5.2.x, Pillow, psycopg) puis campagne de tests complète | `pip install -U`, `python manage.py test` | Développeur |
| **Trimestrielle** | Test de restauration d'une sauvegarde sur une base de recette | `restaurer` | Administrateur |
| **Semestrielle** | Audit d'accessibilité et de poids des pages | Lighthouse, `outils/mesurer_pages.py` | Développeur |
| **Annuelle** | Planification de la montée de version majeure (voir §3) | — | Chef de projet |

**Tâches automatiques quotidiennes** (onglet « Tasks » de PythonAnywhere,
ou `cron` sur un autre hébergeur) :
```bash
python manage.py sauvegarder               # 02:00 — sauvegarde + rotation sur 7 jours
python manage.py purger_journal            # 02:30 — journal > 180 jours (RGPD)
python manage.py purger_images_supprimees  # 02:45 — effacement définitif > 30 jours (RGPD)
```

## 3. Feuille de route technique (évolutions des technologies)

| Échéance | Évolution | Pourquoi |
|---|---|---|
| **Fait (v1.1)** | Django 5.2.15 → 5.2.18 | 9 alertes de sécurité connues sur la 5.2.15 |
| **Fait (v1.1)** | Configuration PostgreSQL via `DATABASE_URL`, tests validés sur PostgreSQL 16 | Base robuste pour plusieurs utilisateurs simultanés |
| **Avant avril 2027** | Passage de l'hébergement en Python 3.12 ou plus | Les versions de Django à partir de la 6.0 exigent Python 3.12 au minimum |
| **2ᵉ semestre 2027** | Migration vers **Django 6.2 LTS** (sortie prévue en avril 2027, maintenue jusqu'en avril 2030) | Django 5.2 LTS n'est plus maintenu après **avril 2028** : on migre avec plusieurs mois de marge, une fois les premiers correctifs de la 6.2 publiés |
| **À partir de 2028** | Rythme annuel (Django 2028, 2029…) | Django passe à une version par an, chacune maintenue 3 ans |
| Évolution envisagée | Cache des indicateurs du dashboard (5 min) | Le calcul par catégorie reste la requête la plus coûteuse (60 à 86 ms sur 50 000 images) |
| Évolution envisagée | Stockage objet chiffré (type S3) pour les images | Chiffrement au repos et capacité de stockage hors du serveur web |
| Évolution envisagée | API REST documentée | Utile seulement si des outils tiers doivent consommer les datasets |

**Procédure pour chaque mise à jour de dépendance** :
1. Lire les notes de version (changements incompatibles, dépréciations).
2. Mettre à jour `requirements.txt` sur une branche.
3. Lancer `python manage.py test` (125 tests) sur SQLite **et** PostgreSQL.
4. Lancer `check --deploy`, `pip-audit` et `bandit`.
5. Vérifier l'accessibilité (Lighthouse) et faire la recette visuelle
   (`outils/verifier_navigateur.py`), car une mise à jour ne doit jamais
   dégrader l'affichage ni la conformité RGAA.
6. Mettre à jour le CHANGELOG, poser une étiquette de version, déployer
   (voir [DEPLOIEMENT.md](DEPLOIEMENT.md)).

## 4. Supervision

| Dispositif | Ce qu'il détecte | Délai de détection |
|---|---|---|
| **`/sante/`** + service de surveillance externe gratuit (ex. UptimeRobot, appel toutes les 5 min) | Site arrêté, base de données injoignable (réponse 503) | ≤ 5 min, alerte par e-mail |
| **E-mail automatique aux administrateurs** (`DJANGO_ADMINS`) | Toute erreur 500, avec la trace complète | Immédiat |
| **`logs/pixbank.log`** (rotation 5 × 2 Mo) | Erreurs, avertissements de sécurité, fichiers manquants, dépôts refusés | Consultation quotidienne |
| **Journal d'accès** (back-office) | Échecs de connexion, blocages, accès refusés hors périmètre, exports | Revue mensuelle |

Le traitement d'un incident détecté suit [INCIDENTS.md](INCIDENTS.md).
