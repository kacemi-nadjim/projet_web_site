"""
TESTS DU CYCLE DE VIE DES IMAGES — dépôt, doublons, miniatures, galerie,
export ETL, dashboard, back-office, formulaire de contact.
"""

import csv
import io
import zipfile

from django.contrib.messages import get_messages
from django.core.management import call_command
from django.db import IntegrityError, transaction
from PIL import Image as PILImage

from core.models import Export, Image, JournalAcces, MessageContact

from .outils import DonneesDeBase, contenu, image_jpeg


def couleur(i):
    """Couleurs bien distinctes : deux teintes trop proches donnent le même
    JPEG (donc la même empreinte), ce qui serait un doublon."""
    return f"#{(i * 97) % 256:02x}{(i * 57 + 80) % 256:02x}{(i * 23 + 160) % 256:02x}"


def creer_image(client, auteur, statut="VALIDEE", couleur="#0e9f6e", categories=()):
    img = Image(fichier=image_jpeg(couleur=couleur), client=client,
                uploaded_by=auteur, statut=statut, consentement=True)
    img.save()
    img.categories.set(categories)
    return img


class DepotEtDoublonsTest(DonneesDeBase):

    def test_depot_multiple_cree_images_et_miniatures(self):
        self.connecter(self.contrib)
        r = self.client.post("/deposer/", {
            "fichiers": [image_jpeg("a.jpg", "#111111", (1600, 1200)),
                         image_jpeg("b.jpg", "#222222", (800, 600))],
            "categories": [self.animal.id]})
        self.assertRedirects(r, "/galerie/")
        self.assertEqual(Image.objects.count(), 2)
        for img in Image.objects.all():
            self.assertEqual(img.statut, "ATTENTE")
            self.assertEqual(len(img.hash_fichier), 64)
            self.assertEqual(list(img.categories.all()), [self.animal])
            self.assertTrue(img.miniature.name.endswith(".webp"))
            with PILImage.open(img.miniature) as mini:
                self.assertLessEqual(max(mini.size), 480)
        grande = Image.objects.get(largeur=1600)
        self.assertEqual(grande.hauteur, 1200)

    def test_doublon_sha256_ignore(self):
        """Le même fichier déposé deux fois n'est enregistré qu'une fois."""
        self.connecter(self.contrib)
        data = {"categories": [self.animal.id]}
        self.client.post("/deposer/", {**data, "fichiers": [image_jpeg()]})
        r = self.client.post("/deposer/", {**data, "fichiers": [image_jpeg()]})
        self.assertEqual(Image.objects.count(), 1)
        textes = [str(m) for m in get_messages(r.wsgi_request)]
        self.assertTrue(any("doublon" in t for t in textes))

    def test_meme_image_autorisee_pour_un_autre_client(self):
        creer_image(self.wassa, self.contrib)
        creer_image(self.acme, self.contrib_acme)
        self.assertEqual(Image.objects.count(), 2)

    def test_redepot_possible_apres_suppression(self):
        img = creer_image(self.wassa, self.contrib)
        img.is_deleted = True
        img.save()
        creer_image(self.wassa, self.contrib)
        self.assertEqual(Image.objects.count(), 2)

    def test_contrainte_unicite_garantie_par_la_base(self):
        """Même si le code applicatif était contourné, la base refuse le doublon."""
        creer_image(self.wassa, self.contrib)
        with self.assertRaises(IntegrityError), transaction.atomic():
            creer_image(self.wassa, self.contrib2)

    def test_miniature_sans_donnees_gps(self):
        """Les métadonnées EXIF (dont la position GPS) ne sont pas recopiées."""
        exif = PILImage.Exif()
        exif[0x010F] = "MarqueTelephone"       # Make
        exif[0x8825] = {2: (48.0, 51.0, 0.0)}   # GPSInfo
        img = Image(fichier=image_jpeg(exif=exif.tobytes()), client=self.wassa,
                    uploaded_by=self.contrib)
        img.save()
        with PILImage.open(img.fichier) as orig:
            self.assertTrue(orig.getexif())
        with PILImage.open(img.miniature) as mini:
            self.assertFalse(mini.getexif())

    def test_commande_generer_miniatures(self):
        """Cas réel de mise à jour : après la migration 0006, les anciennes
        images ont une miniature NULL ; d'autres peuvent avoir une valeur vide."""
        a = creer_image(self.wassa, self.contrib, couleur="#101010")
        b = creer_image(self.wassa, self.contrib, couleur="#e0e0e0")
        Image.objects.filter(pk=a.pk).update(miniature=None)
        Image.objects.filter(pk=b.pk).update(miniature="")
        sortie = io.StringIO()
        call_command("generer_miniatures", stdout=sortie)
        for img in (a, b):
            img.refresh_from_db()
            self.assertTrue(img.miniature.name.endswith(".webp"))
        self.assertIn("2 miniature(s) créée(s)", sortie.getvalue())

    def test_suppression_par_un_tiers_refusee(self):
        img = creer_image(self.wassa, self.contrib)
        self.connecter(self.contrib2)
        self.client.post(f"/image/{img.id}/supprimer/")
        img.refresh_from_db()
        self.assertFalse(img.is_deleted)

    def test_suppression_exige_post(self):
        img = creer_image(self.wassa, self.contrib)
        self.connecter(self.contrib)
        self.assertEqual(self.client.get(f"/image/{img.id}/supprimer/").status_code, 405)


class GalerieTest(DonneesDeBase):

    def test_pagination_24_par_page(self):
        for i in range(30):
            creer_image(self.wassa, self.contrib, couleur=couleur(i))
        self.connecter(self.ds)
        p1 = self.client.get("/galerie/")
        self.assertEqual(len(p1.context["images"]), 24)
        self.assertEqual(p1.context["total"], 30)
        self.assertContains(p1, "Page 1 / 2")
        p2 = self.client.get("/galerie/?page=2")
        self.assertEqual(len(p2.context["images"]), 6)

    def test_galerie_affiche_les_miniatures(self):
        img = creer_image(self.wassa, self.contrib)
        self.connecter(self.ds)
        r = self.client.get("/galerie/")
        self.assertContains(r, img.miniature.url)
        self.assertNotContains(r, img.fichier.url)

    def test_contributeur_ne_voit_que_ses_depots(self):
        creer_image(self.wassa, self.contrib, couleur="#aaaaaa")
        creer_image(self.wassa, self.contrib2, couleur="#bbbbbb")
        self.connecter(self.contrib)
        self.assertEqual(self.client.get("/galerie/").context["total"], 1)

    def test_filtres_categorie_statut_et_valeurs_invalides(self):
        creer_image(self.wassa, self.contrib, "VALIDEE", "#010101", [self.animal])
        creer_image(self.wassa, self.contrib, "ATTENTE", "#020202", [self.visage])
        self.connecter(self.ds)
        reponse = self.client.get(f"/galerie/?categorie={self.animal.id}")
        self.assertEqual(reponse.context["total"], 1)
        self.assertEqual(self.client.get("/galerie/?statut=ATTENTE").context["total"], 1)
        # Valeurs fantaisistes : ignorées au lieu de provoquer une erreur
        r = self.client.get("/galerie/?categorie=abc&statut=PIRATE")
        self.assertEqual(r.context["total"], 2)


class ExportTest(DonneesDeBase):

    def test_export_complet_et_trace(self):
        a = creer_image(self.wassa, self.contrib, "VALIDEE", "#010101", [self.animal])
        creer_image(self.wassa, self.contrib, "VALIDEE", "#020202", [self.visage, self.animal])
        creer_image(self.wassa, self.contrib, "ATTENTE", "#030303", [self.animal])
        supprimee = creer_image(self.wassa, self.contrib, "VALIDEE", "#040404")
        supprimee.is_deleted = True
        supprimee.save()
        creer_image(self.acme, self.contrib_acme, "VALIDEE", "#050505")

        self.connecter(self.ds)
        r = self.client.get("/exporter/")
        zf = zipfile.ZipFile(io.BytesIO(contenu(r)))
        lignes = list(csv.reader(io.StringIO(zf.read("annotations.csv").decode())))
        self.assertEqual(len(lignes), 3)                     # en-tête + 2 validées
        self.assertEqual(len([n for n in zf.namelist() if n.startswith("images/")]), 2)
        perso = {ligne[0]: ligne[5] for ligne in lignes[1:]}
        self.assertEqual(perso[a.fichier.name.split("/")[-1]], "non")
        self.assertIn("oui", perso.values())
        # Les images (déjà compressées) sont stockées sans recompression
        info = zf.getinfo(f"images/{a.fichier.name.split('/')[-1]}")
        self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
        # Traçabilité
        self.assertEqual(Export.objects.get().nb_images, 2)
        self.assertTrue(JournalAcces.objects.filter(
            evenement=JournalAcces.Evenement.EXPORT, utilisateur=self.ds).exists())

    def test_export_filtre_par_categorie(self):
        creer_image(self.wassa, self.contrib, "VALIDEE", "#010101", [self.animal])
        creer_image(self.wassa, self.contrib, "VALIDEE", "#020202", [self.visage])
        self.connecter(self.ds)
        r = self.client.get(f"/exporter/?categorie={self.visage.id}")
        zf = zipfile.ZipFile(io.BytesIO(contenu(r)))
        self.assertEqual(len(zf.read("annotations.csv").decode().strip().splitlines()), 2)
        self.assertEqual(Export.objects.get().filtre_applique, "visage")

    def test_export_vide_redirige(self):
        self.connecter(self.ds)
        r = self.client.get("/exporter/")
        self.assertRedirects(r, "/galerie/")
        self.assertEqual(Export.objects.count(), 0)

    def test_fichier_manquant_signale_sans_bloquer_l_export(self):
        a = creer_image(self.wassa, self.contrib, "VALIDEE", "#010101")
        creer_image(self.wassa, self.contrib, "VALIDEE", "#020202")
        a.fichier.storage.delete(a.fichier.name)
        self.connecter(self.ds)
        with self.assertLogs("pixbank.etl", "ERROR"):
            r = self.client.get("/exporter/")
        zf = zipfile.ZipFile(io.BytesIO(contenu(r)))
        self.assertEqual(len([n for n in zf.namelist() if n.startswith("images/")]), 1)
        self.assertEqual(Export.objects.get().nb_images, 1)


class DashboardTest(DonneesDeBase):

    def test_statistiques_cloisonnees(self):
        creer_image(self.wassa, self.contrib, "VALIDEE", "#010101", [self.visage])
        creer_image(self.wassa, self.contrib2, "ATTENTE", "#020202", [self.animal])
        creer_image(self.wassa, self.contrib, "REFUSEE", "#030303", [self.animal])
        creer_image(self.acme, self.contrib_acme, "VALIDEE", "#040404", [self.animal])
        self.connecter(self.ds)
        ctx = self.client.get("/dashboard/").context
        self.assertEqual(ctx["stats"]["total"], 3)
        self.assertEqual(ctx["stats"]["validees"], 1)
        self.assertEqual(ctx["taux_validation"], 33)
        self.assertEqual(ctx["nb_donnees_perso"], 1)
        self.assertEqual(ctx["nb_contributeurs"], 2)
        self.assertEqual({c.nom: c.n for c in ctx["par_categorie"]},
                         {"Animal": 2, "visage": 1})

    def test_dashboard_interdit_aux_contributeurs(self):
        self.connecter(self.contrib)
        self.assertRedirects(self.client.get("/dashboard/"), "/galerie/")


class BackOfficeTest(DonneesDeBase):

    def test_actions_valider_et_refuser(self):
        a = creer_image(self.wassa, self.contrib, "ATTENTE", "#010101")
        b = creer_image(self.wassa, self.contrib, "ATTENTE", "#020202")
        self.connecter(self.admin)
        url = "/admin/core/image/"
        self.client.post(url, {"action": "valider", "_selected_action": [a.id]})
        self.client.post(url, {"action": "refuser", "_selected_action": [b.id]})
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((a.statut, b.statut), ("VALIDEE", "REFUSEE"))

    def test_liste_avec_apercu(self):
        img = creer_image(self.wassa, self.contrib)
        self.connecter(self.admin)
        r = self.client.get("/admin/core/image/")
        self.assertContains(r, img.miniature.url)


class ContactTest(DonneesDeBase):

    def test_message_enregistre_en_base(self):
        """Non-régression de l'incident INC-002 (messages perdus)."""
        r = self.client.post("/contact/", {"nom": "Alice", "email": "alice@example.com",
                                           "message": "Bonjour", "consentement": "on"})
        self.assertTrue(r.context["envoye"])
        m = MessageContact.objects.get()
        self.assertEqual((m.nom, m.consentement, m.traite), ("Alice", True, False))

    def test_robot_piege_par_le_champ_invisible(self):
        self.client.post("/contact/", {"nom": "Bot", "email": "bot@example.com",
                                       "message": "spam", "consentement": "on",
                                       "site_web": "http://spam.example"})
        self.assertEqual(MessageContact.objects.count(), 0)

    def test_consentement_obligatoire(self):
        self.client.post("/contact/", {"nom": "A", "email": "a@example.com", "message": "m"})
        self.assertEqual(MessageContact.objects.count(), 0)
