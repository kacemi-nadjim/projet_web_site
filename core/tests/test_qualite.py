"""
TESTS UNITAIRES DU MOTEUR DE CONTRÔLE QUALITÉ (qualite.py) — cas limites.
Le test « historique » (IoU identique / disjoint / image floue) est dans
test_regles_metier.py ; ici on couvre tous les autres statuts possibles.
"""

import io
import json
import zipfile

from django.test import SimpleTestCase

from core.qualite import _bbox, controler, iou


def zip_labels(specs):
    """specs : {nom_image: liste de (label, x1, y1, x2, y2)} ou contenu brut."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for nom, shapes in specs.items():
            if isinstance(shapes, (bytes, str)):
                zf.writestr(f"labels/{nom}.json", shapes)
                continue
            data = {"shapes": [{"label": lab, "points": [[a, b], [c, d]],
                                "shape_type": "rectangle"}
                               for (lab, a, b, c, d) in shapes]}
            zf.writestr(f"labels/{nom}.json", json.dumps(data))
    buf.seek(0)
    return buf


class IouTest(SimpleTestCase):

    def test_recouvrement_partiel_exact(self):
        # intersection 5x10=50, union 100+100-50=150 -> 1/3
        self.assertAlmostEqual(iou((0, 0, 10, 10), (5, 0, 15, 10)), 1 / 3)

    def test_boite_incluse(self):
        self.assertAlmostEqual(iou((0, 0, 10, 10), (0, 0, 5, 5)), 0.25)

    def test_boite_absente(self):
        self.assertEqual(iou(None, (0, 0, 1, 1)), 0.0)

    def test_polygone_converti_en_rectangle_englobant(self):
        forme = {"points": [[3, 8], [10, 2], [6, 12]]}
        self.assertEqual(_bbox(forme), (3, 2, 10, 12))
        self.assertIsNone(_bbox({"points": []}))


class ControleLotTest(SimpleTestCase):
    REF = {"i0": [("visage", 10, 10, 50, 50)],
           "i1": [("visage", 10, 10, 50, 50)],
           "i2": [("plaque", 0, 0, 20, 10)]}

    def controler(self, travail, categories=("visage", "plaque")):
        return controler(zip_labels(self.REF), zip_labels(travail), list(categories))

    def test_image_manquante_compte_zero(self):
        rapport, score = self.controler({"i0": self.REF["i0"], "i1": self.REF["i1"]})
        self.assertEqual(rapport["nb_manquantes"], 1)
        self.assertAlmostEqual(score, 66.7)

    def test_annotation_imprecise(self):
        rapport, _ = self.controler({"i0": [("visage", 30, 30, 70, 70)],
                                     "i1": self.REF["i1"], "i2": self.REF["i2"]})
        ligne = next(lg for lg in rapport["lignes"] if lg["image"] == "i0")
        self.assertEqual(ligne["statut"], "imprecis")
        self.assertEqual(rapport["nb_imprecises"], 1)

    def test_categorie_non_autorisee(self):
        rapport, _ = self.controler({"i0": [("chat", 10, 10, 50, 50)],
                                     "i1": self.REF["i1"], "i2": self.REF["i2"]})
        self.assertEqual(rapport["nb_erreurs_categorie"], 1)
        self.assertIn("chat", rapport["lignes"][0]["details"])

    def test_json_corrompu_traite_comme_manquant(self):
        rapport, _ = self.controler({"i0": b"{corrompu", "i1": self.REF["i1"],
                                     "i2": self.REF["i2"]})
        self.assertEqual(rapport["nb_manquantes"], 1)

    def test_travail_parfait(self):
        rapport, score = self.controler(self.REF)
        self.assertEqual(score, 100.0)
        self.assertEqual(rapport["nb_correctes"], 3)

    def test_aucune_image_comparable(self):
        rapport, score = controler(zip_labels({}), zip_labels({}), [])
        self.assertEqual(score, 0.0)
        self.assertEqual(rapport["nb_images"], 0)
