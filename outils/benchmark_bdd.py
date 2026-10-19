"""
BENCHMARK_BDD.PY — Mesure l'effet des index de la v1.1 sur les requêtes réelles.

Le script crée une base JETABLE (jamais la base du site), la remplit avec
un volume réaliste, puis chronomètre les requêtes exactes de l'application
dans deux situations :
  1. « v1.0 » : sans les index ajoutés en v1.1 ;
  2. « v1.1 » : avec les index partiels et composites.
Chaque requête est exécutée 25 fois (après 3 exécutions de chauffe) ; on
retient la médiane (valeur typique) et le 95e centile (cas lents).

Usage :
    python outils/benchmark_bdd.py                         (SQLite, 50 000 images)
    python outils/benchmark_bdd.py --images 200000
    python outils/benchmark_bdd.py --base postgres://user:mdp@hote:5432/pixbank_bench
       (la base PostgreSQL doit être VIDE et dédiée au test)
Résultats : affichés + enregistrés en JSON (--sortie).
"""

import argparse
import json
import os
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

REPETITIONS, CHAUFFE = 25, 3


def preparer_django(url_base):
    os.environ["DATABASE_URL"] = url_base
    os.environ.setdefault("DJANGO_DEBUG", "True")
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    import django
    django.setup()


def chrono(fonction):
    for _ in range(CHAUFFE):
        fonction()
    mesures = []
    for _ in range(REPETITIONS):
        debut = time.perf_counter()
        fonction()
        mesures.append((time.perf_counter() - debut) * 1000)
    mesures.sort()
    return {"mediane_ms": round(statistics.median(mesures), 3),
            "p95_ms": round(mesures[int(0.95 * (len(mesures) - 1))], 3)}


def peupler(nb_images, graine=42):
    from django.contrib.auth.hashers import make_password
    from django.db import connection

    from core.models import Category, Client, Export, Image, JournalAcces, User

    # Aléatoire reproductible pour fabriquer des données de test.
    rnd = random.Random(graine)  # noqa: S311  # nosec B311
    clients = [Client.objects.create(nom="Wassa"), Client.objects.create(nom="ACME")]
    cats = [Category.objects.create(nom=f"Catégorie {i}", donnee_personnelle=i < 2)
            for i in range(6)]
    mdp = make_password("x")
    users = User.objects.bulk_create([
        User(username=f"u{i}", password=mdp, client=clients[i % 2],
             role="CONTRIB" if i >= 4 else "DS") for i in range(40)])
    statuts = ["VALIDEE"] * 6 + ["ATTENTE"] * 3 + ["REFUSEE"]
    lot = 5000
    for depart in range(0, nb_images, lot):
        images = []
        for i in range(depart, min(depart + lot, nb_images)):
            client = clients[0] if rnd.random() < 0.6 else clients[1]
            auteurs = [u for u in users if u.client_id == client.id]
            images.append(Image(
                fichier=f"images/2026/01/photo_{i}.jpg",
                miniature=f"miniatures/2026/01/photo_{i}.webp",
                client=client, uploaded_by=rnd.choice(auteurs),
                statut=rnd.choice(statuts), consentement=True,
                largeur=4032, hauteur=3024, hash_fichier=f"{i:064x}",
                is_deleted=rnd.random() < 0.1))
        crees = Image.objects.bulk_create(images)
        liaison = Image.categories.through
        liaison.objects.bulk_create([
            liaison(image_id=img.id, category_id=c.id)
            for img in crees for c in rnd.sample(cats, rnd.choice((1, 1, 2)))])

    # Dates de dépôt réparties sur deux ans (bulk_create met « maintenant »).
    with connection.cursor() as cur:
        if connection.vendor == "postgresql":
            cur.execute("UPDATE core_image SET date_upload = now() "
                        "- (id % 730) * interval '1 day' - (id % 86400) * interval '1 second'")
        else:
            cur.execute("UPDATE core_image SET date_upload = datetime('now', "
                        "'-' || (id % 730) || ' days', '-' || (id % 86400) || ' seconds')")

    Export.objects.bulk_create([
        Export(user=rnd.choice(users[:4]), client=rnd.choice(clients),
               nb_images=rnd.randint(10, 5000), filtre_applique="toutes catégories")
        for _ in range(5000)])
    evts = list(JournalAcces.Evenement.values)
    JournalAcces.objects.bulk_create([
        JournalAcces(evenement=rnd.choice(evts), identifiant=f"u{rnd.randint(0, 999)}",
                     ip="203.0.113.1") for _ in range(100_000)])
    analyser()
    return clients[0]


def analyser():
    from django.db import connection
    with connection.cursor() as cur:
        cur.execute("ANALYZE")


def index_v11():
    """Les index et contraintes ajoutés par la migration 0006 (v1.1)."""
    from core.models import Export, Image, JournalAcces
    elements = []
    for modele in (Image, Export, JournalAcces):
        for idx in modele._meta.indexes:
            elements.append((modele, "index", idx))
    for c in Image._meta.constraints:
        elements.append((Image, "contrainte", c))
    return elements


def basculer_index(actifs):
    from django.db import connection
    with connection.schema_editor() as editeur:
        for modele, sorte, objet in index_v11():
            if sorte == "index":
                (editeur.add_index if actifs else editeur.remove_index)(modele, objet)
            else:
                (editeur.add_constraint if actifs else editeur.remove_constraint)(modele, objet)
    analyser()


def dashboard_v10(client):
    """Réplique exacte du calcul du dashboard de la v1.0 (y compris la double
    évaluation de la requête par catégorie et l'auteur de chaque export)."""
    from django.db.models import Count, Q

    from core.models import Category, Export, Image

    images = Image.objects.filter(client=client, is_deleted=False)
    par_categorie = (Category.objects
                     .filter(images__client=client, images__is_deleted=False)
                     .annotate(n=Count("images")).order_by("-n"))
    _ = par_categorie[0].n if par_categorie else 1     # 1re évaluation
    list(par_categorie)                                # 2e (le gabarit)
    images.aggregate(total=Count("id"),
                     validees=Count("id", filter=Q(statut="VALIDEE")),
                     attente=Count("id", filter=Q(statut="ATTENTE")),
                     refusees=Count("id", filter=Q(statut="REFUSEE")))
    images.filter(categories__donnee_personnelle=True).distinct().count()
    images.values("uploaded_by").distinct().count()
    for e in Export.objects.filter(client=client)[:10]:
        _ = e.user.username                            # 1 requête par export


def dashboard_v11(client):
    from core.statistiques import indicateurs_client
    ctx = indicateurs_client(client)
    for e in ctx["exports"]:
        _ = e.user.username


def requetes(client, version):
    """Les requêtes exactes des vues. Quand le CODE a changé en v1.1, chaque
    version exécute sa propre requête (signalé par « * » dans le rapport)."""
    from datetime import timedelta

    from django.utils import timezone

    from core.models import Image, JournalAcces

    actives = Image.objects.filter(client=client, is_deleted=False)
    un_hash = actives.values_list("hash_fichier", flat=True)[1000]
    v10 = version == "v1.0"
    return {
        "Galerie — page 1 (24 images)":
            lambda: list(actives.order_by("-date_upload")[:24]),
        "Galerie — page 50":
            lambda: list(actives.order_by("-date_upload")[24 * 49:24 * 50]),
        "Galerie — nombre total":
            lambda: actives.count(),
        "Export — sélection des images validées *":
            (lambda: list(actives.filter(statut="VALIDEE").values_list("id", flat=True)))
            if v10 else
            (lambda: list(actives.filter(statut="VALIDEE").order_by("pk")
                          .values_list("id", flat=True))),
        "Dashboard — calcul complet des indicateurs *":
            (lambda: dashboard_v10(client)) if v10 else (lambda: dashboard_v11(client)),
        "Dépôt — détection de doublon (SHA-256)":
            lambda: actives.filter(hash_fichier=un_hash).exists(),
        "Connexion — compteur anti force brute":
            lambda: JournalAcces.objects.filter(
                identifiant="u42", evenement="CONNEXION_ECHEC",
                date__gte=timezone.now() - timedelta(minutes=15)).count(),
    }


def plan(queryset):
    from django.db import connection
    sql, params = queryset.query.sql_with_params()
    prefixe = "EXPLAIN ANALYZE " if connection.vendor == "postgresql" else "EXPLAIN QUERY PLAN "
    with connection.cursor() as cur:
        cur.execute(prefixe + sql, params)
        return [str(ligne[-1]) for ligne in cur.fetchall()]


def taille_index():
    from django.db import connection
    if connection.vendor != "postgresql":
        return {}
    with connection.cursor() as cur:
        cur.execute("""SELECT indexrelname, pg_relation_size(indexrelid)
                       FROM pg_stat_user_indexes WHERE relname = 'core_image'""")
        return {nom: taille for nom, taille in cur.fetchall()}


def main():
    parser = argparse.ArgumentParser(description="Benchmark des index PixBank")
    parser.add_argument("--images", type=int, default=50_000)
    parser.add_argument("--base", default=None,
                        help="URL d'une base VIDE dédiée (défaut : SQLite temporaire)")
    parser.add_argument("--sortie", default=None)
    args = parser.parse_args()

    fichier_tmp = None
    if args.base is None:
        fichier_tmp = Path(tempfile.mkdtemp()) / "benchmark.sqlite3"
        args.base = f"sqlite:///{fichier_tmp}"
    preparer_django(args.base)

    from django.core.management import call_command
    from django.db import connection

    from core.models import Image

    call_command("migrate", verbosity=0)
    if Image.objects.exists():
        sys.exit("La base contient déjà des images : utilisez une base vide dédiée.")

    print(f"Remplissage : {args.images} images, 100 000 entrées de journal...")
    debut = time.perf_counter()
    client = peupler(args.images)
    print(f"  fait en {time.perf_counter() - debut:.0f} s")

    galerie = (Image.objects.filter(client=client, is_deleted=False)
               .order_by("-date_upload")[:24])
    resultats = {"moteur": connection.vendor, "images": args.images,
                 "repetitions": REPETITIONS, "requetes": {}, "plans": {}}

    basculer_index(False)
    resultats["plans"]["galerie_v1.0"] = plan(galerie)
    for nom, f in requetes(client, "v1.0").items():
        resultats["requetes"].setdefault(nom, {})["v1.0"] = chrono(f)

    basculer_index(True)
    resultats["plans"]["galerie_v1.1"] = plan(galerie)
    resultats["taille_index_octets"] = taille_index()
    for nom, f in requetes(client, "v1.1").items():
        resultats["requetes"][nom]["v1.1"] = chrono(f)

    print(f"\nMoteur : {connection.vendor} — {args.images} images "
          f"(médiane de {REPETITIONS} exécutions)\n")
    print(f"{'Requête':46} {'v1.0 (ms)':>11} {'v1.1 (ms)':>11} {'gain':>8}")
    for nom, r in resultats["requetes"].items():
        avant, apres = r["v1.0"]["mediane_ms"], r["v1.1"]["mediane_ms"]
        r["facteur"] = round(avant / apres, 1) if apres else None
        print(f"{nom:46} {avant:11.3f} {apres:11.3f} {r['facteur']:>7}x")
    print("* requête dont le code a aussi été optimisé en v1.1")
    print("\nPlan galerie v1.0 :", " | ".join(resultats["plans"]["galerie_v1.0"][:3]))
    print("Plan galerie v1.1 :", " | ".join(resultats["plans"]["galerie_v1.1"][:3]))

    if args.sortie:
        Path(args.sortie).write_text(json.dumps(resultats, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    if fichier_tmp:
        connection.close()
        fichier_tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
