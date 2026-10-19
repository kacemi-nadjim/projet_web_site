"""
STATISTIQUES.PY — Indicateurs du dashboard BI (cloisonnés par client).

Optimisations v1.1 (mesures : docs/MESURES_PERFORMANCE.md) :
  - répartition par statut en UNE requête GROUP BY, servie directement
    par l'index partiel (client, statut) sans lire la table ;
  - la requête « par catégorie » n'est plus exécutée deux fois (en v1.0,
    lire le maximum puis afficher la liste déclenchait deux requêtes) ;
  - images à données personnelles : sous-requête EXISTS au lieu d'une
    jointure suivie d'un DISTINCT ;
  - derniers exports chargés avec leur auteur (plus de requête par ligne).
"""

from django.db.models import Count, Exists, OuterRef

from .models import Category, Export, Image


def indicateurs_client(client):
    images = Image.objects.filter(client=client, is_deleted=False)

    par_statut = dict(images.order_by().values_list("statut").annotate(n=Count("id")))
    stats = {
        "validees": par_statut.get(Image.Statut.VALIDEE, 0),
        "attente": par_statut.get(Image.Statut.EN_ATTENTE, 0),
        "refusees": par_statut.get(Image.Statut.REFUSEE, 0),
    }
    stats["total"] = sum(par_statut.values())

    par_categorie = list(
        Category.objects
        .filter(images__client=client, images__is_deleted=False)
        .annotate(n=Count("images")).order_by("-n"))

    liaison = Image.categories.through.objects.filter(
        image_id=OuterRef("pk"), category__donnee_personnelle=True)
    nb_donnees_perso = images.filter(Exists(liaison)).count()

    return {
        "stats": stats,
        "taux_validation": round(100 * stats["validees"] / (stats["total"] or 1)),
        "par_categorie": par_categorie,
        "max_cat": par_categorie[0].n if par_categorie else 1,
        "nb_donnees_perso": nb_donnees_perso,
        "nb_contributeurs": images.values("uploaded_by").distinct().count(),
        "exports": list(Export.objects.filter(client=client).select_related("user")[:10]),
    }
