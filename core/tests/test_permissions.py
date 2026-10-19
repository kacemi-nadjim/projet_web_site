"""TESTS UNITAIRES DES RÈGLES D'ACCÈS (permissions.py)."""

from core.models import Batch, Image
from core.permissions import peut_gerer_lot, peut_voir_image, peut_voir_lot

from .outils import DonneesDeBase


class ReglesAccesTest(DonneesDeBase):

    def test_matrice_lot(self):
        lot = Batch(client=self.wassa, assigne_a=self.contrib, cree_par=self.ds)
        attendu = {
            # utilisateur        voir   gérer
            "lea (DS Wassa)":   (True,  True),
            "karim (assigné)":  (True,  False),
            "nora (même boîte)": (True, False),
            "sara (DS ACME)":   (False, False),
            "paul (ACME)":      (False, False),
            "admin":            (True,  True),
        }
        users = [self.ds, self.contrib, self.contrib2, self.ds_acme,
                 self.contrib_acme, self.admin]
        for (libelle, (voir, gerer)), user in zip(attendu.items(), users):
            with self.subTest(libelle):
                self.assertEqual(peut_voir_lot(user, lot), voir)
                self.assertEqual(peut_gerer_lot(user, lot), gerer)

    def test_contributeur_assigne_d_une_autre_boite_voit_le_lot(self):
        lot = Batch(client=self.wassa, assigne_a=self.contrib_acme, cree_par=self.ds)
        self.assertTrue(peut_voir_lot(self.contrib_acme, lot))
        self.assertFalse(peut_gerer_lot(self.contrib_acme, lot))

    def test_matrice_image(self):
        img = Image(client=self.wassa, uploaded_by=self.contrib)
        self.assertTrue(peut_voir_image(self.contrib, img))
        self.assertTrue(peut_voir_image(self.ds, img))
        self.assertTrue(peut_voir_image(self.admin, img))
        self.assertFalse(peut_voir_image(self.contrib2, img))
        self.assertFalse(peut_voir_image(self.ds_acme, img))
        img.is_deleted = True
        self.assertFalse(peut_voir_image(self.ds, img))
