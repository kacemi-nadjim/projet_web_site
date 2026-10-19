# Journal des modifications — PixBank

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versions : [versionnage sémantique](https://semver.org/lang/fr/) (`MAJEUR.MINEUR.CORRECTIF`).
Chaque version correspond à une étiquette Git (`git tag`).

## [1.1.0] — 2026-10-19

Version de consolidation : sécurité, performance, éco-conception,
tests et exploitation. Aucune fonctionnalité existante n'a été retirée ;
la migration 0006 est réversible.

### Sécurité
- Vérification du contenu réel des images déposées (Pillow), liste
  blanche de formats, taille maximale de 15 Mo (ANO-003).
- Fichiers déposés servis uniquement après contrôle des droits ; le ZIP
  de référence est réservé aux managers (ANO-004).
- Blocage de 15 minutes après 5 échecs de connexion, sur le site et le
  back-office (ANO-011).
- Contrôle des ZIP déposés : taille, nombre de fichiers, bombe ZIP,
  chemins `../` (ANO-012).
- `DEBUG` désactivé par défaut, clé secrète obligatoire en production,
  secrets dans un fichier `.env` non versionné (ANO-002).
- En-têtes Content-Security-Policy, Permissions-Policy et Referrer-Policy ;
  `X-Frame-Options: DENY`.
- `reset_admin` ne remet plus le mot de passe public de démonstration en
  production (ANO-013).
- Django 5.2.15 → **5.2.18** : 9 alertes de sécurité corrigées (ANO-001).

### Ajouté
- Journal d'accès (connexions, échecs, blocages, exports,
  téléchargements, accès refusés), consultable en lecture seule dans le
  back-office.
- Miniatures WebP générées au dépôt, sans métadonnées GPS.
- Pagination de la galerie (24 images par page).
- Point de supervision `/sante/` (version + état de la base) ; alertes
  e-mail en cas d'erreur 500 ; journal applicatif `logs/pixbank.log`
  avec rotation.
- Commandes `sauvegarder` et `restaurer` (vérification SHA-256, rotation
  sur 7 jours), `generer_miniatures`, `purger_journal` (180 jours),
  `purger_images_supprimees` (30 jours, RGPD), `nettoyer_medias`.
- Support de PostgreSQL via `DATABASE_URL` (testé sur PostgreSQL 16) ;
  script SQL de création d'un compte à privilèges minimaux.
- Script de déploiement `outils/deployer.sh` ; outils de mesure
  `outils/benchmark_bdd.py`, `outils/mesurer_pages.py`, `outils/ecoindex.py`.
- Numéro de version affiché en pied de page.

### Performance et éco-conception
- Index partiels (galerie, statuts), contrainte d'unicité partielle
  (anti-doublon garanti par la base), contrainte CHECK sur le score
  qualité. Galerie : requête **10 à 22 fois plus rapide** sur 50 000 images.
- Export : 31 → 7 requêtes SQL, **1,6 s → 0,18 s** (plus de N+1 ni de
  recompression des JPEG) (ANO-005).
- Galerie : **63,8 Mo → 0,25 Mo** par affichage, EcoIndex **C → A**.
- Polices auto-hébergées : plus aucun appel à Google (ANO-014).
- Index de la table des images 23 % plus légers (PostgreSQL).

### Corrigé
- Galerie tronquée à 60 images (ANO-008).
- Erreurs ignorées en silence dans l'export ; nombre d'images exportées
  inexact en cas de fichier manquant (ANO-006).
- Messages d'erreur des formulaires de dépôt et de connexion non
  affichés (ANO-009).
- `STATIC_ROOT` absent du code versionné (suite de l'incident INC-001).
- Sauvegarde `dump.json` non restaurable dans une base neuve (ANO-015) ;
  `dump.json` et `dump.sql` régénérés au format v1.1.
- Défauts d'affichage hérités de la v1.0 : vignettes de la galerie
  rognées, barres du dashboard vides, cases à cocher décalées (ANO-019).
- Erreur 404 sur `/favicon.ico` à chaque visite : icône du site ajoutée.

### Qualité et tests
- 12 → **125 tests** automatisés ; couverture **62 % → 96 %** ; suite
  validée sur SQLite et PostgreSQL.
- `ruff` (PEP 8, erreurs, sécurité, Django) : 32 → 0 erreur ;
  `bandit` : 4 → 0 alerte ; `pip-audit` : 9 → 0 vulnérabilité.
- Logique métier sortie des vues : modules `etl.py`, `permissions.py`,
  `securite.py`, `statistiques.py`, `miniatures.py`.

### Mise à jour depuis 1.0.0
Voir [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md) : `bash outils/deployer.sh v1.1.0`,
puis **supprimer le mappage public `/media/`** dans l'onglet Web de PythonAnywhere.

## [1.0.0] — 2026-09 (version soutenue)

### Fonctionnalités
- Plateforme multi-clients à 3 rôles (contributeur, data scientist,
  administrateur), cloisonnement par client.
- Dépôt multiple et multi-catégories, détection des doublons par SHA-256.
- Validation des dépôts dans le back-office ; export ETL (ZIP + CSV) ;
  dashboard BI.
- Module de labélisation : lots, contrôle qualité automatique par IoU
  (seuil 70 %).
- Demandes d'inscription validées par un administrateur ; conformité
  RGPD (consentement, suppression logique, traçabilité des exports).

### Corrigé avant la soutenance
- Rattachement contributeur → data scientist ; visibilité des lots par
  assignation ; droits d'accès au détail et au téléchargement des lots ;
  workflow d'approbation des comptes.
- Messages du formulaire de contact non enregistrés (INC-002, migration 0005).
- Back-office sans style en production (INC-001).
