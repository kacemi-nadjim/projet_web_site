"""
TESTS DE MAINTENANCE — sauvegarde/restauration, purge du journal,
supervision, contraintes d'intégrité de la base, version affichée.
"""

import io
import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from core.models import Batch, Category, Client, Image, JournalAcces, User

from .outils import DonneesDeBase, fixture
from .test_images import creer_image


class SauvegardeRestaurationTest(TransactionTestCase):
    """TransactionTestCase : la restauration vide puis recharge la base, ce
    qui doit se faire hors de la transaction englobante d'un TestCase
    (PostgreSQL refuse un TRUNCATE avec des contrôles de clés étrangères en
    attente). C'est aussi plus proche des conditions réelles."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="pixbank_backup_test_")
        self.wassa = Client.objects.create(nom="Wassa")
        self.animal = Category.objects.create(nom="Animal")
        self.ds = User.objects.create_user("lea", password="p", role="DS", client=self.wassa)
        self.contrib = User.objects.create_user("karim", password="p", role="CONTRIB",
                                                client=self.wassa, manager=self.ds)
        self.image = creer_image(self.wassa, self.contrib, "VALIDEE", "#123456",
                                 [self.animal])
        Batch.objects.create(nom="Lot", client=self.wassa, cree_par=self.ds,
                             zip_reference=fixture("lot_reference_20images.zip"),
                             nb_images=20, score_qualite=88.5)

    def sauvegarder(self):
        call_command("sauvegarder", dossier=self.dossier, stdout=io.StringIO())
        return sorted(Path(self.dossier).glob("pixbank_*"))[-1]

    def test_aller_retour_complet(self):
        sauvegarde = self.sauvegarder()
        manifeste = json.loads((sauvegarde / "manifeste.json").read_text())
        self.assertEqual(manifeste["version_pixbank"], settings.PIXBANK_VERSION)

        # Sinistre simulé : données et fichiers effacés
        chemin_photo = Path(self.image.fichier.path)
        Image.objects.all().delete()
        Batch.objects.all().delete()
        chemin_photo.unlink()

        call_command("restaurer", str(sauvegarde), confirmer=True, stdout=io.StringIO())

        img = Image.objects.get()
        self.assertEqual(img.hash_fichier, self.image.hash_fichier)
        self.assertEqual(list(img.categories.values_list("nom", flat=True)), ["Animal"])
        self.assertEqual(img.uploaded_by.username, "karim")
        self.assertTrue(Path(img.fichier.path).exists())
        self.assertEqual(Batch.objects.get().score_qualite, 88.5)
        self.assertTrue(User.objects.get(username="lea").check_password("p"))

    def test_sauvegarde_corrompue_detectee(self):
        sauvegarde = self.sauvegarder()
        with open(sauvegarde / "donnees.json.gz", "ab") as f:
            f.write(b"corruption")
        with self.assertRaisesMessage(CommandError, "corrompu"):
            call_command("restaurer", str(sauvegarde), confirmer=True)

    def test_confirmation_obligatoire(self):
        sauvegarde = self.sauvegarder()
        with self.assertRaisesMessage(CommandError, "--confirmer"):
            call_command("restaurer", str(sauvegarde))
        self.assertEqual(Image.objects.count(), 1)

    def test_rotation_des_sauvegardes(self):
        for i in range(4):
            with mock.patch("django.utils.timezone.now",
                            return_value=timezone.now() + timedelta(seconds=i)):
                call_command("sauvegarder", dossier=self.dossier, garder=2,
                             stdout=io.StringIO())
        self.assertEqual(len(list(Path(self.dossier).glob("pixbank_*"))), 2)


class JournalTest(DonneesDeBase):

    def test_purge_au_dela_de_la_duree_de_conservation(self):
        ancienne = JournalAcces.enregistrer(JournalAcces.Evenement.CONNEXION_OK,
                                            utilisateur=self.ds)
        JournalAcces.objects.filter(pk=ancienne.pk).update(
            date=timezone.now() - timedelta(days=200))
        JournalAcces.enregistrer(JournalAcces.Evenement.CONNEXION_OK, utilisateur=self.ds)
        sortie = io.StringIO()
        call_command("purger_journal", stdout=sortie)
        self.assertEqual(JournalAcces.objects.count(), 1)
        self.assertIn("1 entrée(s)", sortie.getvalue())


class SupervisionTest(DonneesDeBase):

    def test_point_de_sante(self):
        r = self.client.get("/sante/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"statut": "ok", "version": settings.PIXBANK_VERSION,
                                    "base_de_donnees": "ok"})

    def test_point_de_sante_signale_une_panne_de_base(self):
        with mock.patch("core.views.connection.cursor", side_effect=Exception("panne")), \
                self.assertLogs("pixbank.vues", "ERROR"):
            r = self.client.get("/sante/")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["base_de_donnees"], "erreur")

    def test_version_affichee_en_pied_de_page(self):
        self.assertContains(self.client.get("/"), f"v{settings.PIXBANK_VERSION}")


class ContraintesBaseTest(DonneesDeBase):

    def test_score_hors_bornes_refuse_par_la_base(self):
        for score in (-1, 100.5):
            with self.subTest(score=score), self.assertRaises(IntegrityError), \
                    transaction.atomic():
                Batch.objects.create(nom="L", client=self.wassa, cree_par=self.ds,
                                     zip_reference="x.zip", score_qualite=score)

    def test_score_limites_acceptees(self):
        for score in (0, 100, None):
            Batch.objects.create(nom="L", client=self.wassa, cree_par=self.ds,
                                 zip_reference="x.zip", score_qualite=score)
        self.assertEqual(Batch.objects.count(), 3)

    def test_client_avec_utilisateurs_non_supprimable(self):
        """PROTECT : on ne peut pas supprimer une entreprise qui a des comptes."""
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.acme.delete()
