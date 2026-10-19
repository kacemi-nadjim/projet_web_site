# Registre des anomalies — PixBank v1.0 → v1.1

Ce registre recense les anomalies détectées pendant la campagne de tests et
d'audit menée en octobre 2026 sur la version soutenue en septembre (v1.0).

Chaque ligne suit le même cycle : **détection → analyse de la cause →
correction → test automatisé qui empêche la régression**. Tous les tests
cités se trouvent dans `core/tests/` et passent (`python manage.py test`).

Les incidents survenus **en production** (site en ligne) sont traités à
part, dans [INCIDENTS.md](INCIDENTS.md).

## Gravité

| Niveau | Définition |
|---|---|
| **Critique** | Faille de sécurité exploitable ou fuite de données personnelles |
| **Majeure** | Fonctionnalité fausse ou inutilisable, ou risque de sécurité sérieux |
| **Mineure** | Performance, maintenabilité, confort, sans impact sur les données |

## Synthèse

| N° | Anomalie | Gravité | Détectée par | Statut |
|---|---|---|---|---|
| ANO-001 | Django 5.2.15 : 9 vulnérabilités connues | Critique | `pip-audit` | Corrigée |
| ANO-002 | `DEBUG` activé et clé secrète connue par défaut | Critique | relecture + `check --deploy` | Corrigée |
| ANO-003 | Un fichier HTML/JavaScript accepté comme « image » | Critique | test d'intrusion manuel | Corrigée |
| ANO-004 | Dossier `media/` public : photos et vérité terrain accessibles sans droit | Critique | relecture du code | Corrigée |
| ANO-005 | Export : une requête SQL par image (N+1) et recompression inutile | Majeure | mesure des requêtes | Corrigée |
| ANO-006 | Erreurs ignorées en silence (export, contrôle qualité) | Majeure | relecture + `bandit` | Corrigée |
| ANO-007 | Les tests écrivaient dans le vrai dossier `media/` | Mineure | inspection du disque | Corrigée |
| ANO-008 | Galerie tronquée à 60 images, sans pagination | Majeure | relecture du code | Corrigée |
| ANO-009 | Messages d'erreur des formulaires non affichés | Majeure | nouveaux tests | Corrigée |
| ANO-010 | Miniatures non générées pour les images existantes après migration | Majeure | test de migration sur les vraies données | Corrigée avant livraison |
| ANO-011 | Aucune limite de tentatives de connexion | Majeure | analyse des risques | Corrigée |
| ANO-012 | ZIP déposés non contrôlés (bombe ZIP, chemins `../`) | Majeure | analyse des risques | Corrigée |
| ANO-013 | `reset_admin` remettait le mot de passe public `demo1234` en production | Majeure | relecture du code | Corrigée |
| ANO-014 | Polices chargées depuis Google : adresse IP transmise sans consentement | Majeure (RGPD) | audit RGPD | Corrigée |
| ANO-015 | La sauvegarde `dump.json` n'était pas restaurable dans une base neuve | Majeure | test de restauration | Corrigée |
| ANO-016 | Dashboard : requête exécutée deux fois et une requête par export | Mineure | mesure des requêtes | Corrigée |
| ANO-017 | Galerie triée en mémoire à chaque affichage (aucun index adapté) | Mineure | plan d'exécution `EXPLAIN` | Corrigée |
| ANO-018 | Images supprimées conservées indéfiniment (fichiers compris) | Majeure (RGPD) | audit RGPD | Corrigée |
| ANO-019 | Défauts d'affichage : vignettes rognées, barres du dashboard vides, cases à cocher décalées | Majeure | recette dans un vrai navigateur | Corrigée |
| ANO-020 | HTML invalide sur les pages d'inscription et de mot de passe (5 erreurs W3C) | Mineure | validateur W3C sur 17 pages | Corrigée |

## Détail

### ANO-001 — Dépendance vulnérable (Critique)
- **Constat** : `pip-audit` signale 9 avis de sécurité sur Django 5.2.15
  (5 failles distinctes), corrigées dans les versions 5.2.16 et 5.2.17
  (`docs/mesures/audits/pip_audit_v1.0.txt`).
- **Cause** : la version était figée lors du développement et aucune veille
  sur les mises à jour de sécurité n'était organisée.
- **Correction** : passage à Django 5.2.18. Toutes les dépendances sont
  désormais figées dans `requirements.txt`, et un contrôle mensuel est
  planifié ([MAINTENANCE.md](MAINTENANCE.md)).
- **Preuve** : `pip-audit -r requirements.txt` → « No known vulnerabilities found ».

### ANO-002 — Configuration de production dangereuse par défaut (Critique)
- **Constat** : `DEBUG` valait `True` si la variable d'environnement était
  absente, et une clé secrète était écrite en dur dans le code.
  Un simple oubli au déploiement affichait les traces d'erreur
  (code, chemins, variables) à n'importe quel visiteur.
- **Correction** : `DEBUG` vaut `False` par défaut. Sans `DJANGO_SECRET_KEY`,
  le site refuse de démarrer en production. `manage.py` active `DEBUG`
  uniquement pour le développement local.
- **Tests** : `test_securite.ConfigurationProductionTest` (2 tests) — dont
  `check --deploy` sans aucun avertissement.

### ANO-003 — Dépôt de fichiers non-images (Critique)
- **Constat** : un fichier `piege.html` contenant `<script>` était accepté
  par `/deposer/`, enregistré et servi publiquement sous `/media/`
  (risque de faille XSS stockée et d'hébergement de contenu malveillant).
- **Cause** : le formulaire utilisait un champ « fichier » générique.
  L'image n'était jamais vérifiée, car `Image.save()` ignorait l'erreur
  de lecture.
- **Correction** : `core/securite.py::valider_image` lit le contenu réel
  avec Pillow (`verify()`), applique une liste blanche de formats
  (JPEG, PNG, WebP, BMP) et une taille maximale (15 Mo).
- **Tests** : `test_securite.DepotFichiersTest` (5 tests : HTML, faux `.jpg`,
  taille, format GIF, vraie image).

### ANO-004 — Fichiers déposés accessibles sans contrôle (Critique)
- **Constat** : il suffisait de connaître l'adresse d'une photo
  (`/media/images/…`) pour l'ouvrir sans être connecté, y compris des
  visages et des plaques. Un contributeur pouvait aussi télécharger le
  ZIP de référence, qui contient les réponses attendues.
- **Correction** : `views.media_protege` devient la seule porte d'accès
  aux fichiers. Chaque fichier est rattaché à son objet en base, et les
  règles de cloisonnement sont vérifiées avant l'envoi. Les refus sont
  journalisés. En production, l'accès direct au dossier `/media/` doit
  être retiré (voir [DEPLOIEMENT.md](DEPLOIEMENT.md)).
- **Tests** : `test_securite.AccesMediasTest` (7 tests).

### ANO-005 — Export lent et coûteux (Majeure)
- **Constat** : pour 24 photos, l'export exécutait **31 requêtes SQL** et
  prenait **1,6 s**. `contient_donnee_perso()` refaisait une requête par
  image, et les JPEG (déjà compressés) étaient recompressés pour un gain
  de 0,02 %.
- **Correction** : nouveau module `core/etl.py`, catégories préchargées
  sans requête supplémentaire, images stockées sans recompression, ZIP
  construit dans un fichier temporaire au lieu de la mémoire.
- **Résultat** : **7 requêtes, 0,18 s** (×8,8), voir
  [MESURES_PERFORMANCE.md](MESURES_PERFORMANCE.md).
- **Test** : `test_performance.test_export_sans_n_plus_1` vérifie que le
  nombre de requêtes ne dépend pas du nombre d'images.

### ANO-006 — Erreurs avalées sans trace (Majeure)
- **Constat** : `try/except: continue` dans l'export (signalé par
  `bandit` B112) : une image dont le fichier manquait était ignorée sans
  trace, tout en étant **comptée** dans l'historique des exports, qui
  devenait donc faux. Le contrôle qualité masquait aussi les exceptions.
- **Correction** : chaque erreur est écrite dans le journal
  (`logs/pixbank.log`), et `Export.nb_images` compte les images
  réellement incluses.
- **Tests** : `test_images.test_fichier_manquant_signale_sans_bloquer_l_export`,
  `test_lots.test_json_labelme_mal_forme_ne_fait_pas_planter_le_site`.

### ANO-007 — Tests non isolés (Mineure)
- **Constat** : 9 fichiers `t_*.jpg` créés par les tests de la v1.0 se
  trouvaient dans le vrai dossier `media/` livré. Au total, 30 des 52
  fichiers de ce dossier (0,25 Mo) n'étaient rattachés à aucune donnée
  de `dump.json` : restes de tests et anciens jeux de démonstration.
- **Correction** : un lanceur de tests (`core/tests/runner.py`) utilise un
  dossier temporaire. La commande `nettoyer_medias` liste puis supprime
  les fichiers orphelins.
- **Test** : `test_maintenance.test_fichiers_orphelins`.

### ANO-008 — Galerie tronquée (Majeure)
- **Constat** : la galerie affichait au plus 60 images (`[:60]`) tout en
  annonçant le total réel : au-delà, les images étaient **inaccessibles**.
- **Correction** : vraie pagination (24 images par page) qui conserve les filtres.
- **Test** : `test_images.test_pagination_24_par_page`.

### ANO-009 — Erreurs de formulaire invisibles (Majeure)
- **Constat** : le gabarit de dépôt n'affichait pas les erreurs propres au
  champ « fichiers », et la page de connexion remplaçait tous les
  messages par un texte fixe, y compris le message de blocage.
- **Correction** : erreurs affichées (avec `role="alert"` pour les
  lecteurs d'écran), message de connexion générique conservé pour ne pas
  révéler si un identifiant existe.
- **Tests** : `test_securite.DepotFichiersTest`, `ForceBruteTest`.

### ANO-010 — Miniatures absentes après migration (Majeure, trouvée avant livraison)
- **Constat** : en rejouant la mise à jour v1.0 → v1.1 sur les vraies
  données (`dump.json`), la commande `generer_miniatures` traitait
  0 image. La colonne ajoutée par la migration vaut `NULL`, alors que la
  commande cherchait une valeur vide `""`.
- **Correction** : la recherche couvre les deux cas.
- **Test** : `test_images.test_commande_generer_miniatures` couvre les deux cas.
- **Enseignement** : tester la migration sur une copie des données
  réelles fait désormais partie de la procédure de déploiement.

### ANO-011 — Pas de protection contre la force brute (Majeure)
- **Correction** : après 5 échecs en 15 minutes, l'identifiant est bloqué,
  même avec le bon mot de passe. Le blocage s'applique au site et au
  back-office, et chaque blocage est journalisé.
- **Tests** : `test_securite.ForceBruteTest` (5 tests).

### ANO-012 — ZIP non contrôlés (Majeure)
- **Correction** : `securite.valider_zip` vérifie, avant toute ouverture,
  la taille, le nombre de fichiers, la taille décompressée
  (anti « bombe ZIP ») et les chemins (`../`, chemins absolus).
- **Tests** : `test_securite.ValidationZipTest` (5 tests),
  `test_lots.test_zip_dangereux_refuse_avant_analyse`.

### ANO-013 — Commande `reset_admin` dangereuse en production (Majeure)
- **Correction** : en production, la commande génère un mot de passe
  aléatoire de 22 caractères, ou exige un mot de passe conforme aux règles.
- **Tests** : `test_pages_et_commandes.CommandesTest` (3 tests).

### ANO-014 — Google Fonts (Majeure, RGPD)
- **Constat** : chaque visite déclenchait des requêtes vers
  `fonts.googleapis.com` et `fonts.gstatic.com`, ce qui transmet l'adresse
  IP du visiteur à un tiers sans consentement (une juridiction allemande
  l'a jugé contraire au RGPD en 2022).
- **Correction** : les mêmes polices (licence OFL) sont servies par le
  site lui-même, au format WOFF2. Le script en ligne du bandeau cookies a
  été déplacé dans un fichier, ce qui permet une politique CSP stricte.
- **Test** : `test_securite.EnTetesTest.test_aucune_ressource_externe`.

### ANO-015 — Sauvegarde non restaurable (Majeure)
- **Constat** : `loaddata dump.json` échoue sur une base neuve
  (`UNIQUE constraint failed: django_content_type`), car le fichier
  contient des tables techniques que Django recrée lui-même.
- **Correction** : la commande `sauvegarder` produit données, fichiers,
  manifeste et empreintes SHA-256, et exclut ces tables. La commande
  `restaurer` vérifie l'intégrité avant de remplacer quoi que ce soit.
- **Tests** : `test_maintenance.SauvegardeRestaurationTest` (4 tests,
  dont un aller-retour complet après effacement simulé).

### ANO-016 et ANO-017 — Performance du dashboard et de la galerie (Mineures)
- Voir [MESURES_PERFORMANCE.md](MESURES_PERFORMANCE.md) : index partiels,
  requête `GROUP BY` couverte par l'index, suppression des doubles requêtes.
- **Tests** : `test_performance` (6 tests : nombre de requêtes constant,
  index réellement utilisés).

### ANO-018 — Effacement jamais définitif (Majeure, RGPD)
- **Constat** : la suppression « logique » masquait l'image, mais la ligne
  et les fichiers restaient indéfiniment. Le droit à l'effacement (art. 17)
  n'était donc pas respecté jusqu'au bout.
- **Correction** : la commande quotidienne `purger_images_supprimees`
  efface la ligne et les fichiers après 30 jours de délai de récupération.
- **Test** : `test_maintenance.test_effacement_definitif_apres_30_jours`.

### ANO-019 — Défauts d'affichage hérités de la v1.0 (Majeure)
- **Constat** : la recette dans un vrai navigateur (`outils/verifier_navigateur.py`,
  captures v1.0 / v1.1 comparées) a révélé trois défauts présents depuis la v1.0 :
  1. galerie : les vignettes montraient un **coin** de la photo à sa taille réelle,
     au lieu de la photo entière cadrée ;
  2. dashboard : les barres « Répartition par catégorie » restaient **vides**.
     La largeur en % était posée sur un `<span>` (élément en ligne), qui l'ignore ;
  3. dépôt : chaque case à cocher s'affichait centrée **au-dessus** de son libellé.
- **Correction** : règles CSS ciblées (`.card-img img`, `.bar-fill { display: block }`,
  `.checklist label`). Le statut de l'image est désormais affiché en
  pastille sur la vignette.
- **Vérification** : recette navigateur, sans aucune erreur console ni
  violation CSP. Captures dans `docs/captures/`.
- **Enseignement** : les tests automatisés vérifient le HTML produit, pas
  son rendu visuel. Une recette visuelle dans un navigateur fait désormais
  partie de la procédure de mise à jour ([MAINTENANCE.md](MAINTENANCE.md)).

### ANO-020 — HTML invalide sur deux formulaires (Mineure)
- **Constat** : le validateur officiel du W3C (Nu Html Checker), lancé sur
  17 pages (y compris les pages affichant des erreurs de formulaire),
  signale 5 erreurs :
  - sur les pages « Devenir contributeur » et « Changer mon mot de passe »,
    des champs annoncent une aide (`aria-describedby`) qui n'existe pas
    dans la page ;
  - une liste est placée à l'intérieur d'un paragraphe, ce qui est interdit.
  La validation de la v1.0 n'avait porté que sur la page d'accueil.
- **Correction** : les textes d'aide portent l'identifiant attendu, la
  liste est placée dans un bloc `div`, les erreurs du dépôt sont regroupées
  sous un seul identifiant, et chaque carte de la galerie a un titre
  réservé aux lecteurs d'écran.
- **Vérification** : 17 pages, **0 erreur, 0 avertissement**.
