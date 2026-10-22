"""
TESTS DE PERFORMANCE — garde-fous automatiques.

1. Le nombre de requêtes SQL d'une page ne doit PAS dépendre du nombre
   d'images (sinon : problème « N+1 », la page ralentit à mesure que la
   base grossit). En v1.0, l'export faisait 1 requête de plus par image.
2. Les index créés en v1.1 sont réellement utilisés par la base
   (vérification du plan d'exécution).
Les mesures chiffrées (temps, avant/après) sont dans
le dossier de projet (script outils/benchmark_bdd.py).
"""

import unittest

from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.models import Image

from .outils import DonneesDeBase
from .test_images import couleur, creer_image


class NombreDeRequetesConstantTest(DonneesDeBase):

    def nb_requetes(self, url, user):
        self.client.force_login(user)
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(url)
            if getattr(r, "streaming", False):
                b"".join(r.streaming_content)
        self.assertLess(r.status_code, 400)
        return len(ctx.captured_queries)

    def peupler(self, n, depart=0):
        for i in range(depart, depart + n):
            creer_image(self.wassa, self.contrib, "VALIDEE", couleur(i),
                        [self.animal, self.visage])

    def verifier_constant(self, url, user=None):
        user = user or self.ds
        self.peupler(3)
        petit = self.nb_requetes(url, user)
        self.peupler(20, depart=3)
        grand = self.nb_requetes(url, user)
        self.assertEqual(petit, grand,
                         f"{url} : {petit} requêtes pour 3 images, {grand} pour 23")
        return grand

    def test_export_sans_n_plus_1(self):
        self.assertLessEqual(self.verifier_constant("/exporter/"), 12)

    def test_galerie_sans_n_plus_1(self):
        self.assertLessEqual(self.verifier_constant("/galerie/"), 8)

    def test_dashboard_sans_n_plus_1(self):
        self.assertLessEqual(self.verifier_constant("/dashboard/"), 10)


@unittest.skipUnless(connection.vendor == "sqlite", "plan d'exécution propre à SQLite")
class IndexUtilisesTest(DonneesDeBase):
    """On remplit la table (2 000 images, 2 clients, 10 % supprimées) et on
    met à jour les statistiques (ANALYZE), comme en production."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Image.objects.bulk_create([
            Image(fichier=f"images/x{i}.jpg", client=cls.wassa if i % 2 else cls.acme,
                  uploaded_by=cls.contrib, hash_fichier=f"{i:064x}",
                  statut=("VALIDEE", "ATTENTE", "REFUSEE")[i % 3],
                  is_deleted=(i % 10 == 0))
            for i in range(2000)])
        with connection.cursor() as cur:
            cur.execute("ANALYZE")

    def plan(self, queryset):
        sql, params = queryset.query.sql_with_params()
        with connection.cursor() as cur:
            cur.execute("EXPLAIN QUERY PLAN " + sql, params)
            return " | ".join(str(ligne[-1]) for ligne in cur.fetchall())

    def test_galerie_utilise_l_index_et_evite_le_tri(self):
        plan = self.plan(Image.objects.filter(client=self.wassa, is_deleted=False)
                         .order_by("-date_upload"))
        self.assertIn("image_galerie_idx", plan)
        self.assertNotIn("TEMP B-TREE", plan)        # pas de tri en mémoire

    def test_export_utilise_un_index_partiel(self):
        plan = self.plan(Image.objects.filter(client=self.wassa, is_deleted=False,
                                              statut="VALIDEE"))
        self.assertRegex(plan, "image_client_statut_idx|image_galerie_idx")

    def test_anti_doublon_utilise_l_index_de_l_empreinte(self):
        plan = self.plan(Image.objects.filter(client=self.wassa, is_deleted=False,
                                              hash_fichier="ab" * 32).order_by())
        self.assertRegex(plan, "image_unique_par_client|hash_fichier")
