"""
TESTS DES PAGES PUBLIQUES, DES COMMANDES D'ADMINISTRATION ET DU WORKFLOW
D'INSCRIPTION DANS LE BACK-OFFICE.
"""

import io

from django.core.management import call_command
from django.test import override_settings

from core.models import Category, DemandeInscription, Image, User

from .outils import DonneesDeBase


class PagesPubliquesTest(DonneesDeBase):

    def test_pages_accessibles_et_structurees(self):
        for url in ("/", "/contact/", "/inscription/", "/mentions-legales/",
                    "/confidentialite/", "/cgu/", "/compte/login/"):
            with self.subTest(url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, '<html lang="fr">')
                self.assertContains(r, "<h1", count=1)       # un seul titre principal
                self.assertContains(r, '<meta name="viewport"')

    def test_pages_privees_exigent_une_connexion(self):
        for url in ("/galerie/", "/deposer/", "/exporter/", "/dashboard/", "/lots/"):
            with self.subTest(url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 302)
                self.assertIn("/compte/login/", r["Location"])


class CommandesTest(DonneesDeBase):

    def test_seed_cree_la_demo_et_est_rejouable(self):
        Category.objects.all().delete()
        call_command("seed", stdout=io.StringIO())
        call_command("seed", stdout=io.StringIO())       # deuxième passage sans doublon
        self.assertTrue(User.objects.filter(username="lea_ds", role="DS").exists())
        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(Image.objects.count(), 20)
        self.assertTrue(all(i.miniature for i in Image.objects.all()))

    @override_settings(DEBUG=True)
    def test_reset_admin_en_local(self):
        call_command("reset_admin", stdout=io.StringIO())
        admin = User.objects.get(username="admin")
        self.assertTrue(admin.is_superuser and admin.is_staff)
        self.assertTrue(admin.check_password("demo1234"))

    @override_settings(DEBUG=False)
    def test_reset_admin_en_production_n_utilise_jamais_demo1234(self):
        sortie = io.StringIO()
        call_command("reset_admin", stdout=sortie)
        admin = User.objects.get(username="admin")
        self.assertFalse(admin.check_password("demo1234"))
        mdp = sortie.getvalue().split("mot de passe '")[1].split("'")[0]
        self.assertGreaterEqual(len(mdp), 20)
        self.assertTrue(admin.check_password(mdp))

    @override_settings(DEBUG=False)
    def test_reset_admin_refuse_un_mot_de_passe_faible_en_production(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("reset_admin", mdp="1234", stdout=io.StringIO())


class InscriptionBackOfficeTest(DonneesDeBase):

    def setUp(self):
        self.demande = DemandeInscription.objects.create(
            nom="Nina", email="nina@wassa.fr", entreprise_souhaitee="Wassa",
            motivation="Labéliser")
        self.connecter(self.admin)
        self.url = "/admin/core/demandeinscription/"

    def test_etape_1_choix_du_data_scientist(self):
        r = self.client.post(self.url, {"action": "approuver_et_creer_compte",
                                        "_selected_action": [self.demande.id]})
        self.assertContains(r, "lea")
        self.assertContains(r, "sara")

    def test_data_scientist_invalide_annule_l_operation(self):
        nb = User.objects.count()
        self.client.post(self.url, {"action": "approuver_et_creer_compte",
                                    "_selected_action": [self.demande.id],
                                    "confirmer_rattachement": "1",
                                    "data_scientist": str(self.contrib.id)})
        self.assertEqual(User.objects.count(), nb)

    def test_identifiant_unique_si_deja_pris(self):
        User.objects.create_user("nina", password="p", role="CONTRIB", client=self.wassa)
        self.client.post(self.url, {"action": "approuver_et_creer_compte",
                                    "_selected_action": [self.demande.id],
                                    "confirmer_rattachement": "1",
                                    "data_scientist": str(self.ds.id)})
        self.assertTrue(User.objects.filter(username="nina2", manager=self.ds).exists())

    def test_refus(self):
        self.client.post(self.url, {"action": "marquer_refusee",
                                    "_selected_action": [self.demande.id]})
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, "REFUSEE")
        self.assertIsNotNone(self.demande.traitee_le)
