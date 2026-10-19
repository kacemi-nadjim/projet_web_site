"""
TESTS DU MODULE DE LABÉLISATION — de bout en bout, avec les vrais ZIP de
démonstration (lot de 20 images, travail réussi, travail échoué).
"""

import io
import zipfile

from core import batch_utils
from core.models import Batch, JournalAcces

from .outils import DonneesDeBase, contenu, fixture, zip_en_memoire


class CreationLotTest(DonneesDeBase):

    def creer(self, zip_ref, user=None):
        self.connecter(user or self.ds)
        return self.client.post("/lots/creer/", {
            "nom": "Lot test", "description": "consignes",
            "zip_reference": zip_ref, "assigne_a": self.contrib.id})

    def test_creation_avec_le_vrai_lot_de_20_images(self):
        r = self.creer(fixture("lot_reference_20images.zip"))
        lot = Batch.objects.get()
        self.assertRedirects(r, f"/lots/{lot.id}/")
        self.assertEqual(lot.nb_images, 20)
        self.assertEqual(lot.statut, "A_FAIRE")
        self.assertEqual(lot.assigne_a, self.contrib)
        self.assertEqual(lot.client, self.wassa)

    def test_contributeur_ne_peut_pas_creer(self):
        r = self.creer(fixture("lot_reference_20images.zip"), user=self.contrib)
        self.assertRedirects(r, "/lots/")
        self.assertEqual(Batch.objects.count(), 0)

    def test_zip_sans_labels_refuse(self):
        r = self.creer(zip_en_memoire({"images/a.jpg": b"x"}))
        self.assertContains(r, "Aucun label")
        self.assertEqual(Batch.objects.count(), 0)

    def test_zip_dangereux_refuse_avant_analyse(self):
        r = self.creer(zip_en_memoire({"../evil.json": {"shapes": []}}))
        self.assertContains(r, "chemin de fichier interdit")

    def test_ds_ne_peut_assigner_qu_a_ses_contributeurs(self):
        self.connecter(self.ds)
        self.client.post("/lots/creer/", {
            "nom": "Lot", "zip_reference": fixture("lot_reference_20images.zip"),
            "assigne_a": self.contrib_acme.id})
        self.assertEqual(Batch.objects.count(), 0)   # choix invalide -> refusé


class CycleDeVieLotTest(DonneesDeBase):

    def setUp(self):
        self.lot = Batch.objects.create(
            nom="Lot 20", client=self.wassa, cree_par=self.ds, assigne_a=self.contrib,
            zip_reference=fixture("lot_reference_20images.zip"), nb_images=20)

    def soumettre(self, nom_zip):
        self.connecter(self.contrib)
        return self.client.post(f"/lots/{self.lot.id}/", {"zip_travail": fixture(nom_zip)})

    def test_telechargement_des_images_sans_les_reponses(self):
        self.connecter(self.contrib)
        r = self.client.get(f"/lots/{self.lot.id}/images/")
        zf = zipfile.ZipFile(io.BytesIO(contenu(r)))
        noms = zf.namelist()
        self.assertEqual(len(noms), 20)
        self.assertTrue(all(n.startswith("images/") for n in noms))
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, "EN_COURS")
        self.assertTrue(JournalAcces.objects.filter(
            evenement=JournalAcces.Evenement.TELECHARGEMENT, utilisateur=self.contrib).exists())

    def test_travail_reussi_valide_le_lot(self):
        self.soumettre("travail_REUSSI.zip")
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, "VALIDE")
        self.assertGreaterEqual(self.lot.score_qualite, 70)
        self.assertEqual(self.lot.rapport["nb_images"], 20)
        self.assertIsNotNone(self.lot.date_soumission)

    def test_travail_echoue_renvoie_en_correction(self):
        self.soumettre("travail_ECHOUE.zip")
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, "A_CORRIGER")
        self.assertLess(self.lot.score_qualite, 70)

    def test_fichier_qui_n_est_pas_un_zip(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.connecter(self.contrib)
        r = self.client.post(f"/lots/{self.lot.id}/", {
            "zip_travail": SimpleUploadedFile("travail.zip", b"pas un zip")}, follow=True)
        self.assertContains(r, "ZIP refusé")
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, "A_FAIRE")

    def test_json_labelme_mal_forme_ne_fait_pas_planter_le_site(self):
        """Un JSON valide mais de mauvaise structure (liste au lieu d'objet)."""
        self.connecter(self.contrib)
        with self.assertLogs("pixbank.vues", "ERROR"):
            r = self.client.post(f"/lots/{self.lot.id}/", {
                "zip_travail": zip_en_memoire({"labels/img_00.json": b"[1, 2, 3]"})},
                follow=True)
        self.assertContains(r, "Le contrôle qualité a échoué")
        self.lot.refresh_from_db()
        self.assertIsNone(self.lot.score_qualite)

    def test_seul_le_contributeur_assigne_peut_soumettre(self):
        self.connecter(self.ds)
        self.client.post(f"/lots/{self.lot.id}/",
                         {"zip_travail": fixture("travail_REUSSI.zip")})
        self.lot.refresh_from_db()
        self.assertIsNone(self.lot.score_qualite)

    def test_manager_telecharge_le_travail(self):
        self.soumettre("travail_REUSSI.zip")
        self.connecter(self.ds)
        r = self.client.get(f"/lots/{self.lot.id}/travail/")
        self.assertEqual(r["Content-Type"], "application/zip")
        self.assertTrue(zipfile.ZipFile(io.BytesIO(contenu(r))).namelist())

    def test_travail_pas_encore_soumis(self):
        self.connecter(self.ds)
        r = self.client.get(f"/lots/{self.lot.id}/travail/")
        self.assertRedirects(r, f"/lots/{self.lot.id}/")

    def test_contributeur_ne_telecharge_pas_le_travail_via_la_vue_manager(self):
        self.soumettre("travail_REUSSI.zip")
        self.connecter(self.contrib)
        self.assertEqual(self.client.get(f"/lots/{self.lot.id}/travail/").status_code, 404)

    def test_autre_entreprise_ne_voit_rien(self):
        self.connecter(self.ds_acme)
        for url in (f"/lots/{self.lot.id}/", f"/lots/{self.lot.id}/images/",
                    f"/lots/{self.lot.id}/travail/"):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertEqual(JournalAcces.objects.filter(
            evenement=JournalAcces.Evenement.ACCES_REFUSE).count(), 3)

    def test_liste_des_lots_par_role(self):
        self.connecter(self.ds)
        self.assertContains(self.client.get("/lots/"), "Lot 20")
        self.connecter(self.contrib2)
        self.assertNotContains(self.client.get("/lots/"), "Lot 20")


class AnalyseZipTest(DonneesDeBase):
    """Fonctions de batch_utils.py testées directement (tests unitaires)."""

    def test_pas_un_zip(self):
        ok, msg, _ = batch_utils.analyser_zip_reference(io.BytesIO(b"rien"))
        self.assertFalse(ok)

    def test_sans_images(self):
        ok, msg, _ = batch_utils.analyser_zip_reference(
            zip_en_memoire({"labels/a.json": {"shapes": []}}))
        self.assertIn("Aucune image", msg)

    def test_json_invalide(self):
        ok, msg, _ = batch_utils.analyser_zip_reference(
            zip_en_memoire({"images/a.jpg": b"x", "labels/a.json": b"{oups"}))
        self.assertIn("pas un JSON valide", msg)

    def test_fichiers_systeme_macos_ignores(self):
        ok, _, infos = batch_utils.analyser_zip_reference(zip_en_memoire({
            "lot/images/a.jpg": b"x", "lot/labels/a.json": {"shapes": []},
            "__MACOSX/lot/images/._a.jpg": b"x", "lot/images/.DS_Store": b"x"}))
        self.assertTrue(ok)
        self.assertEqual(infos["nb_images"], 1)
