"""
TESTS.PY — Tests automatisés (exigence du jury : tests unitaires + intégration).
Lancer avec : python manage.py test
Ces tests prouvent que les règles métier critiques fonctionnent.
"""

import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image as PIL

from .models import Category, Client, Image, User


def img_file(name="t.jpg", color="#0e9f6e"):
    b = io.BytesIO()
    PIL.new("RGB", (60, 60), color).save(b, "JPEG")
    return SimpleUploadedFile(name, b.getvalue(), content_type="image/jpeg")


class BaseData(TestCase):
    def setUp(self):
        self.wassa = Client.objects.create(nom="Wassa")
        self.acme = Client.objects.create(nom="ACME")
        self.cat = Category.objects.create(nom="Animal", donnee_personnelle=False)
        self.cat_dp = Category.objects.create(nom="Visage", donnee_personnelle=True)
        self.contrib = User.objects.create_user(
            "k", password="p", role="CONTRIB", client=self.wassa)
        self.ds = User.objects.create_user(
            "d", password="p", role="DS", client=self.wassa)
        self.ds_acme = User.objects.create_user(
            "a", password="p", role="DS", client=self.acme)


class CloisonnementTest(BaseData):
    """Un utilisateur ne doit voir QUE les images de son client."""
    def test_galerie_cloisonnee(self):
        img = Image.objects.create(fichier=img_file(), client=self.wassa,
                                   uploaded_by=self.contrib, statut="VALIDEE")
        img.categories.set([self.cat])
        self.client.login(username="a", password="p")  # data scientist ACME
        r = self.client.get("/galerie/")
        self.assertNotContains(r, img.fichier.name)


class RGPDTest(BaseData):
    """Une catégorie 'donnée personnelle' impose le consentement."""
    def test_upload_visage_sans_consentement_refuse(self):
        self.client.login(username="k", password="p")
        r = self.client.post("/deposer/", {
            "fichiers": [img_file()], "categories": [self.cat_dp.id]})
        self.assertContains(r, "consentement")
        self.assertEqual(Image.objects.count(), 0)


class ExportTest(BaseData):
    """Seul un data scientist peut exporter ; le ZIP contient le CSV."""
    def test_contributeur_ne_peut_pas_exporter(self):
        self.client.login(username="k", password="p")
        r = self.client.get("/exporter/", follow=True)
        self.assertNotEqual(r.get("Content-Type"), "application/zip")

    def test_export_contient_annotations(self):
        img = Image.objects.create(fichier=img_file(), client=self.wassa,
                                   uploaded_by=self.contrib, statut="VALIDEE")
        img.categories.set([self.cat])
        self.client.login(username="d", password="p")
        r = self.client.get("/exporter/")
        self.assertEqual(r["Content-Type"], "application/zip")
        import zipfile
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        self.assertIn("annotations.csv", zf.namelist())


class SoftDeleteTest(BaseData):
    """La suppression masque l'image sans détruire la ligne."""
    def test_soft_delete(self):
        img = Image.objects.create(fichier=img_file(), client=self.wassa,
                                   uploaded_by=self.contrib, statut="VALIDEE")
        self.client.login(username="k", password="p")
        self.client.post(f"/image/{img.id}/supprimer/")
        img.refresh_from_db()
        self.assertTrue(img.is_deleted)          # masquée
        self.assertEqual(Image.objects.count(), 1)  # mais toujours en base


class InscriptionTest(BaseData):
    """Une demande d'inscription ne crée jamais de compte automatiquement."""
    def test_demande_enregistree_sans_compte(self):
        from .models import DemandeInscription, User
        nb_users_avant = User.objects.count()
        r = self.client.post("/inscription/", {
            "nom": "Nouveau Contributeur",
            "email": "nouveau@example.com",
            "entreprise_souhaitee": "Wassa",
            "motivation": "Je dois déposer des images d'entraînement.",
            "consentement_rgpd": "on",
        })
        # La demande est bien enregistrée
        self.assertEqual(DemandeInscription.objects.count(), 1)
        d = DemandeInscription.objects.first()
        self.assertEqual(d.statut, "ATTENTE")
        # Mais AUCUN compte n'a été créé (sécurité)
        self.assertEqual(User.objects.count(), nb_users_avant)

    def test_inscription_sans_consentement_rgpd_refusee(self):
        """Sans cocher le consentement RGPD, la demande n'est pas enregistrée."""
        from .models import DemandeInscription
        r = self.client.post("/inscription/", {
            "nom": "Sans Consentement",
            "email": "refus@example.com",
            "entreprise_souhaitee": "Wassa",
            "motivation": "Test sans consentement.",
            # consentement_rgpd volontairement absent
        })
        self.assertEqual(DemandeInscription.objects.count(), 0)


class QualiteTest(TestCase):
    """Le moteur de contrôle qualité calcule correctement l'IoU et les statuts."""
    def test_iou_et_rapport(self):
        import io, json, zipfile
        from .qualite import controler, iou

        # IoU de rectangles identiques = 1.0
        self.assertEqual(iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)
        # IoU sans recouvrement = 0.0
        self.assertEqual(iou((0, 0, 5, 5), (10, 10, 15, 15)), 0.0)

        def zip_labels(specs):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                for nom, (shapes, flou) in specs.items():
                    data = {"flags": {"flou": True} if flou else {},
                            "shapes": [{"label": l, "points": [[a, b], [c, d]],
                                        "shape_type": "rectangle"}
                                       for (l, a, b, c, d) in shapes]}
                    zf.writestr(f"labels/{nom}.json", json.dumps(data))
            buf.seek(0)
            return buf

        ref = zip_labels({"i0": ([("visage", 10, 10, 50, 50)], False),
                          "i1": ([("visage", 10, 10, 50, 50)], False)})
        trav = zip_labels({"i0": ([("visage", 10, 10, 50, 50)], False),  # parfait
                           "i1": ([], True)})                              # flou
        rapport, score = controler(ref, trav, ["visage"])
        # i0 parfait (100), i1 floue (exclue) -> score = 100
        self.assertEqual(score, 100.0)
        self.assertEqual(rapport["nb_floues"], 1)
        self.assertEqual(rapport["nb_correctes"], 1)


class ApprobationCompteTest(TestCase):
    """L'approbation rattache le contributeur à un data scientist et crée le compte."""
    def test_approbation_rattache_au_data_scientist(self):
        from .models import DemandeInscription, User, Client

        # Une boîte cliente avec son data scientist (le manager)
        boite = Client.objects.create(nom="Wassa")
        ds = User(username="ds_ref", email="ds@wassa.com",
                  role=User.Role.DATA_SCIENTIST, client=boite)
        ds.set_password("x"); ds.save()

        # Un admin
        admin_user = User.objects.create_user("tmpadmin", password="adminpass",
                                              is_superuser=True, is_staff=True)
        d = DemandeInscription.objects.create(
            nom="Test User", email="test.user@wassa.com",
            entreprise_souhaitee="Wassa", motivation="Test.")
        nb_avant = User.objects.count()

        # L'admin approuve en choisissant le data scientist référent
        self.client.login(username="tmpadmin", password="adminpass")
        self.client.post("/admin/core/demandeinscription/", {
            "action": "approuver_et_creer_compte",
            "_selected_action": [str(d.id)],
            "confirmer_rattachement": "1",
            "data_scientist": str(ds.id),
        })

        # Un compte contributeur a été créé
        self.assertEqual(User.objects.count(), nb_avant + 1)
        d.refresh_from_db()
        self.assertEqual(d.statut, DemandeInscription.Statut.APPROUVEE)

        # Il est rattaché au bon data scientist ET hérite de sa boîte
        nouveau = User.objects.get(email="test.user@wassa.com")
        self.assertEqual(nouveau.role, User.Role.CONTRIBUTEUR)
        self.assertEqual(nouveau.manager, ds)
        self.assertEqual(nouveau.client, boite)

        # Le compte est connectable
        nouveau.set_password("motdepasse_test"); nouveau.save()
        self.assertTrue(self.client.login(
            username=nouveau.username, password="motdepasse_test"))


class RattachementContributeurTest(TestCase):
    """Un contributeur rattaché à un DS voit ses lots, et le DS peut l'assigner."""
    def test_ds_assigne_et_contributeur_voit_son_lot(self):
        from .models import Client, User, Batch
        from .forms import BatchCreationForm

        boite = Client.objects.create(nom="NouvelleBoite")
        ds = User(username="ds_x", role=User.Role.DATA_SCIENTIST, client=boite)
        ds.set_password("p"); ds.save()
        contrib = User(username="contrib_x", role=User.Role.CONTRIBUTEUR,
                       client=boite, manager=ds)
        contrib.set_password("p"); contrib.save()

        # 1. Le DS trouve le contributeur dans la liste d'assignation
        form = BatchCreationForm(client=ds.client, manager=ds)
        assignables = list(form.fields["assigne_a"].queryset)
        self.assertIn(contrib, assignables)

        # 2. Un lot assigné au contributeur est visible par lui
        lot = Batch.objects.create(nom="Lot X", client=boite, cree_par=ds,
                                   assigne_a=contrib, nb_images=0, statut="A_FAIRE")
        self.client.login(username="contrib_x", password="p")
        r = self.client.get("/lots/")
        self.assertContains(r, "Lot X")
        self.assertEqual(self.client.get(f"/lots/{lot.id}/").status_code, 200)

    def test_contributeur_ne_voit_pas_lot_autre_boite(self):
        from .models import Client, User, Batch
        b1 = Client.objects.create(nom="B1")
        b2 = Client.objects.create(nom="B2")
        ds1 = User(username="ds_1", role=User.Role.DATA_SCIENTIST, client=b1)
        ds1.set_password("p"); ds1.save()
        c1 = User(username="c_1", role=User.Role.CONTRIBUTEUR, client=b1, manager=ds1)
        c1.set_password("p"); c1.save()
        c2 = User(username="c_2", role=User.Role.CONTRIBUTEUR, client=b2)
        c2.set_password("p"); c2.save()
        lot = Batch.objects.create(nom="Lot Privé", client=b1, cree_par=ds1,
                                   assigne_a=c1, nb_images=0, statut="A_FAIRE")
        # c2 (autre boîte) ne voit pas le lot et ne peut pas y accéder
        self.client.login(username="c_2", password="p")
        r = self.client.get("/lots/")
        self.assertNotContains(r, "Lot Privé")
        self.assertEqual(self.client.get(f"/lots/{lot.id}/").status_code, 404)


class ChangementMotDePasseTest(TestCase):
    """Chaque utilisateur peut modifier son propre mot de passe."""
    def test_utilisateur_change_son_mot_de_passe(self):
        from .models import User, Client
        boite = Client.objects.create(nom="Boite")
        u = User(username="user_x", role=User.Role.CONTRIBUTEUR, client=boite)
        u.set_password("AncienMdp2026!"); u.save()

        self.client.login(username="user_x", password="AncienMdp2026!")
        # La page est accessible
        self.assertEqual(
            self.client.get("/compte/password_change/").status_code, 200)
        # Le changement fonctionne
        self.client.post("/compte/password_change/", {
            "old_password": "AncienMdp2026!",
            "new_password1": "NouveauMdp2026!",
            "new_password2": "NouveauMdp2026!",
        })
        # L'ancien ne marche plus, le nouveau oui
        c2 = self.client_class()
        self.assertFalse(c2.login(username="user_x", password="AncienMdp2026!"))
        self.assertTrue(c2.login(username="user_x", password="NouveauMdp2026!"))
