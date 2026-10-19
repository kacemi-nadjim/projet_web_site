# Mesures de performance et d'éco-conception — v1.0 → v1.1

Toutes les valeurs ci-dessous ont été **mesurées** (et non estimées) le
19 octobre 2026, sur la même machine, avec les mêmes données pour les deux
versions. Les scripts sont livrés dans `outils/` pour que n'importe qui
puisse refaire les mesures. Les résultats bruts sont dans `docs/mesures/`.

---

## 1. Base de données : effet des index (C4.7, C4.8)

### Méthode
`outils/benchmark_bdd.py` crée une base jetable et la remplit avec un
volume réaliste :
- 50 000 images réparties entre 2 clients (60 % et 40 %) ;
- 10 % d'images supprimées et un statut varié (60 % validées) ;
- des dépôts étalés sur deux ans, 1 à 2 catégories par image ;
- 5 000 exports et 100 000 entrées de journal.

Le script exécute ensuite les **requêtes exactes de l'application**,
25 fois chacune après 3 exécutions de chauffe, et retient la médiane.
Situation « v1.0 » : sans les index de la v1.1, avec l'index d'origine
sur l'empreinte. Situation « v1.1 » : avec les index et le code optimisé.

```bash
python outils/benchmark_bdd.py --images 50000                       # SQLite
python outils/benchmark_bdd.py --base postgres://…/pixbank_bench    # PostgreSQL 16
```

### Résultats (médiane, en millisecondes)

| Requête (vue concernée) | SQLite v1.0 | SQLite v1.1 | Gain | PostgreSQL v1.0 | PostgreSQL v1.1 | Gain |
|---|---:|---:|---:|---:|---:|---:|
| Galerie — page 1 (24 images) | 6,53 | 0,57 | **×11,5** | 14,88 | 1,45 | **×10,3** |
| Galerie — page 50 | 13,81 | 0,61 | **×22,6** | 15,63 | 1,91 | **×8,2** |
| Galerie — nombre total | 7,03 | 1,37 | ×5,1 | 5,28 | 2,46 | ×2,1 |
| Export — sélection des images validées* | 15,26 | 5,81 | ×2,6 | 12,26 | 8,64 | ×1,4 |
| Dashboard — calcul complet des indicateurs* | 105,48 | 86,19 | ×1,2 | 83,32 | 59,76 | ×1,4 |
| Dépôt — détection de doublon (SHA-256) | 0,24 | 0,20 | ×1,2 | 0,59 | 0,83 | ×0,7 |
| Connexion — compteur anti force brute | 11,38 | 0,43 | **×26,7** | 6,95 | 1,01 | **×6,9** |

\* requête dont le code a aussi été réécrit en v1.1 (pas seulement indexé).

### Ce que montrent les plans d'exécution (`EXPLAIN`)

**Galerie, v1.0 (PostgreSQL)** : la base lit toute la table, puis trie
26 739 lignes pour n'en garder que 24.
```
Limit -> Sort (Sort Key: date_upload DESC)
      -> Seq Scan on core_image  Filter: (NOT is_deleted AND client_id = 1)
         Rows Removed by Filter: 23257          Execution Time: 23.8 ms
```
**Galerie, v1.1** : l'index fournit directement les 24 lignes dans le bon
ordre, sans rien lire de plus.
```
Limit -> Index Scan using image_galerie_idx on core_image
         Index Cond: (client_id = 1)            Execution Time: 0.07 ms
```

### Choix techniques et justification

| Index / contrainte | Requête servie | Pourquoi ce choix |
|---|---|---|
| `image_galerie_idx` : `(client, date_upload DESC) WHERE NOT is_deleted` | galerie, pagination | Index **partiel**. Django traduit `is_deleted=False` par `NOT is_deleted` : un index composite classique `(client, is_deleted, date)` n'était pas utilisé (constaté par un test qui a échoué). L'index partiel correspond exactement à la condition et ne contient que les images actives, ce qui le rend plus petit. |
| `image_client_statut_idx` : `(client, statut) WHERE NOT is_deleted` | export, dashboard | Le calcul « par statut » est réécrit en `GROUP BY statut`, servi par cet index sans lire la table : 16,4 ms → 2,8 ms sur cette seule requête (SQLite). |
| `image_unique_par_client` : UNIQUE `(client, hash) WHERE NOT is_deleted` | anti-doublon | Double rôle. **Garde-fou** : la base refuse un doublon même si deux dépôts arrivent en même temps. **Index de recherche** : il remplace l'ancien index simple sur l'empreinte. |
| `journal_tentatives_idx` : `(identifiant, evenement, date)` | anti force brute | La requête est exécutée à **chaque** tentative de connexion : elle doit rester rapide quelle que soit la taille du journal. |
| `export_client_date_idx` : `(client, date DESC)` | 10 derniers exports | Évite de trier tout l'historique. |
| CHECK `score_qualite` entre 0 et 100 | intégrité | La base refuse une valeur aberrante même en cas de bug applicatif. |

### Les cas sans gain, expliqués
- **Export : gain limité (×1,4 à ×2,6)**. La requête renvoie environ
  16 000 lignes, soit un tiers de la table. Un index sert surtout à
  retrouver *peu* de lignes parmi beaucoup. Ici, le coût vient du volume
  renvoyé. Le gain obtenu vient surtout du tri retiré, devenu inutile.
  Dans l'export réel, la lecture des fichiers images domine de toute façon
  (section 3).
- **Doublon sous PostgreSQL : 0,59 → 0,83 ms**. L'index unique
  `(client, hash)` est un peu plus large que l'ancien index `(hash)` seul.
  On reste sous la milliseconde, et cet index apporte la garantie
  d'unicité, ce que l'ancien ne faisait pas.
- **Dashboard : ×1,2 à ×1,4**. Le poste principal (répartition par
  catégorie) parcourt la table de liaison image ↔ catégorie, environ
  35 000 lignes. Évolution possible : mettre ces indicateurs en cache
  quelques minutes (voir [MAINTENANCE.md](MAINTENANCE.md)).

### Taille des index (PostgreSQL, 50 000 images)

| | v1.0 | v1.1 |
|---|---:|---:|
| Index de la table `core_image` | **13,4 Mo** | **10,3 Mo** |

La v1.1 a **plus** d'index utiles, mais ils occupent **23 % de place en
moins**. Sous PostgreSQL, `db_index=True` sur l'empreinte créait en effet
deux index de 4,8 Mo, dont un réservé aux recherches `LIKE`, jamais
utilisées. Ils sont remplacés par l'index unique partiel. Moins d'index
inutiles, c'est moins de disque et des écritures plus rapides.

---

## 2. Poids des pages et EcoIndex (C4.5 éco-conception, C4.3)

### Méthode
`outils/mesurer_pages.py` ouvre un **vrai navigateur Chromium** :
1. il se connecte (compte `lea_ds`) et vide le cache ;
2. il charge la page et la fait défiler jusqu'en bas, pour déclencher le
   chargement différé des images ;
3. il relève le poids transféré, le nombre de requêtes et la taille du DOM ;
4. il calcule l'**EcoIndex** (méthode officielle GreenIT / cnumr,
   reprise dans `outils/ecoindex.py` et vérifiée contre l'implémentation
   de référence).

Jeu de données identique pour les deux versions : **24 photos au format
smartphone** (4032 × 3024 pixels, 12 Mpx, 2,7 Mo chacune), toutes validées.

### Résultats

| Page | Version | Poids transféré | Requêtes | Chargement | EcoIndex |
|---|---|---:|---:|---:|---|
| Galerie | v1.0 | **63,8 Mo** | 27 | 1 572 ms | 68,9 — **C** |
| Galerie | v1.1 | **0,25 Mo** | 32 | 793 ms | 81,8 — **A** |

La galerie est **253 fois plus légère** et passe de la note C à la note A.
- **Cause** : la v1.0 affichait les photos originales (2,7 Mo chacune)
  dans des vignettes de 230 pixels de large.
- **Solution** : à chaque dépôt, une miniature WebP (480 px, 5,3 Ko en
  moyenne sur ce jeu de test) est générée une seule fois et affichée à la
  place. L'original reste intact pour l'export des datasets.
- **Limite de la mesure** : les photos de test sont synthétiques, et leurs
  miniatures sont sans doute plus légères que celles de vraies photos.
  Même avec 30 Ko par miniature (hypothèse prudente), la galerie resterait
  sous 1 Mo, soit environ 75 fois moins que la v1.0.
- **Gain associé** : les miniatures ne contiennent plus les métadonnées
  EXIF des photos, dont la position GPS (RGPD).

Pour un data scientist qui consulte la galerie 20 fois par jour, cela
représente environ **1,3 Go de transfert évité par jour**
(63,6 Mo × 20), avant même l'effet du cache.

**Pages d'accueil et dashboard** : poids équivalent entre les deux
versions, environ 97 Ko.
- En v1.0, les 5 fichiers de police venaient de Google. Le réseau de
  l'environnement de mesure bloque Google : ces fichiers n'ont pas pu
  être comptés (1 requête en échec).
- En v1.1, ce sont **exactement les mêmes polices**, servies par le site
  lui-même (73 Ko, format WOFF2).
- Le gain recherché ici n'est pas le poids, mais **la suppression de deux
  domaines tiers** (moins de connexions DNS et TLS) et la conformité au
  RGPD (ANO-014).

### Autres mesures d'éco-conception
| Mesure | Effet |
|---|---|
| Pagination à 24 images | Le poids de la galerie ne grossit plus avec la banque d'images (la v1.0 en chargeait jusqu'à 60) |
| `loading="lazy"`, `decoding="async"`, `width`/`height` | Images chargées seulement quand elles deviennent visibles, sans décalage de mise en page |
| `Cache-Control: private, max-age=86400` sur les miniatures | Une miniature déjà vue n'est plus retéléchargée pendant 24 h |
| Export sans recompression des JPEG | Même taille de ZIP (65,3 Mo), temps d'export divisé par 8,8 (section 3) |
| Purge à 30 jours des images supprimées, purge à 180 jours du journal | Le stockage ne grossit pas avec des données inutiles (sobriété + RGPD) |
| Commande `nettoyer_medias` | 30 fichiers orphelins sur 52 retirés du dossier livré |
| Index partiels | Index plus petits (section 1) |

---

## 3. Requêtes SQL par page et temps de réponse serveur (C4.4, C4.8)

Mesuré avec le client de test Django sur les mêmes 24 photos (médiane de
5 appels) — `docs/mesures/requetes_par_page.json`.

| Page | Requêtes SQL v1.0 | Requêtes SQL v1.1 | Temps v1.0 | Temps v1.1 |
|---|---:|---:|---:|---:|
| Galerie | 7 | 7 | 13,8 ms | 11,5 ms |
| Dashboard | 8 | 8 | 7,0 ms | 6,1 ms |
| **Export (ZIP de 65 Mo)** | **31** | **7** | **1 597 ms** | **181 ms** |

- **Export, v1.0** : le nombre de requêtes augmentait d'une unité par
  image (problème « N+1 ») ; avec 1 000 images, on aurait eu plus de
  1 000 requêtes.
- **Export, v1.1** : 7 requêtes, quel que soit le volume.
- **Garde-fou** : c'est vérifié automatiquement par
  `core/tests/test_performance.py`. Le test échoue si une page fait plus
  de requêtes avec 23 images qu'avec 3.
- **Dashboard v1.0** : chaque export affiché ajoutait une requête. Avec
  10 exports dans l'historique, on passait de 8 à 18 requêtes.
  La v1.1 en fait 8, toujours.
