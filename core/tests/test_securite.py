"""
TESTS DE SÉCURITÉ — chaque test correspond à un risque identifié
(voir docs/REGISTRE_ANOMALIES.md et la section sécurité du dossier).
"""

import io
import os
import subprocess  # nosec B404 — lance manage.py du projet dans les tests
import sys
import zipfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from core import securite
from core.models import Batch, Image, JournalAcces

from .outils import DonneesDeBase, image_jpeg, zip_en_memoire

RACINE = Path(__file__).resolve().parents[2]


class DepotFichiersTest(DonneesDeBase):
    """Risque : déposer un fichier dangereux en le faisant passer pour une image."""

    def deposer(self, fichier):
        self.connecter(self.contrib)
        return self.client.post("/deposer/", {"fichiers": [fichier],
                                              "categories": [self.animal.id]})

    def test_fichier_html_refuse(self):
        """ANO-003 : un HTML avec du JavaScript était accepté comme image."""
        piege = SimpleUploadedFile("piege.html", b"<script>alert(1)</script>",
                                   content_type="text/html")
        r = self.deposer(piege)
        self.assertContains(r, "n&#x27;est pas une image valide")
        self.assertEqual(Image.objects.count(), 0)

    def test_fausse_extension_jpg_refusee(self):
        """Renommer un script en .jpg ne suffit pas : on lit le contenu réel."""
        piege = SimpleUploadedFile("vacances.jpg", b"#!/bin/sh\nrm -rf /",
                                   content_type="image/jpeg")
        self.deposer(piege)
        self.assertEqual(Image.objects.count(), 0)

    @override_settings(PIXBANK_IMAGE_TAILLE_MAX=1000)
    def test_image_trop_lourde_refusee(self):
        r = self.deposer(image_jpeg(taille=(400, 400), couleur="#123456"))
        self.assertContains(r, "taille maximale")
        self.assertEqual(Image.objects.count(), 0)

    def test_format_hors_liste_blanche_refuse(self):
        buf = io.BytesIO()
        from PIL import Image as PILImage
        PILImage.new("RGB", (20, 20)).save(buf, "GIF")
        r = self.deposer(SimpleUploadedFile("anim.gif", buf.getvalue(),
                                            content_type="image/gif"))
        self.assertContains(r, "format GIF non autorisé")

    def test_vraie_image_acceptee(self):
        self.deposer(image_jpeg())
        self.assertEqual(Image.objects.count(), 1)


class ValidationZipTest(SimpleTestCase):
    """Risques : bombe ZIP, chemins « ../ », fichier qui n'est pas un ZIP."""

    def test_pas_un_zip(self):
        f = SimpleUploadedFile("x.zip", b"pas un zip")
        self.assertIn("pas un ZIP", securite.valider_zip(f))

    def test_chemin_dangereux(self):
        f = zip_en_memoire({"../../config/settings.py": b"x"})
        self.assertIn("chemin", securite.valider_zip(f))

    @override_settings(PIXBANK_ZIP_DECOMPRESSE_MAX=10_000)
    def test_bombe_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("images/zeros.bin", b"\0" * 1_000_000)  # 1 Mo -> ~1 Ko compressé
        f = SimpleUploadedFile("bombe.zip", buf.getvalue())
        self.assertLess(f.size, 10_000)
        self.assertIn("trop volumineux", securite.valider_zip(f))

    @override_settings(PIXBANK_ZIP_NB_FICHIERS_MAX=3)
    def test_trop_de_fichiers(self):
        f = zip_en_memoire({f"images/{i}.jpg": b"x" for i in range(5)})
        self.assertIn("trop de fichiers", securite.valider_zip(f))

    def test_zip_sain_accepte(self):
        f = zip_en_memoire({"images/a.jpg": b"x", "labels/a.json": {"shapes": []}})
        self.assertIsNone(securite.valider_zip(f))


class AccesMediasTest(DonneesDeBase):
    """ANO-004 : les photos et les ZIP du dossier media/ étaient publics."""

    def setUp(self):
        self.image = Image(fichier=image_jpeg(), client=self.wassa,
                           uploaded_by=self.contrib, statut="VALIDEE")
        self.image.save()

    def test_visiteur_anonyme_redirige_vers_connexion(self):
        r = self.client.get(self.image.fichier.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/compte/login/", r["Location"])

    def test_autre_entreprise_refusee_et_journalisee(self):
        self.connecter(self.ds_acme)
        r = self.client.get(self.image.fichier.url)
        self.assertEqual(r.status_code, 404)
        self.assertTrue(JournalAcces.objects.filter(
            evenement=JournalAcces.Evenement.ACCES_REFUSE,
            utilisateur=self.ds_acme).exists())

    def test_autre_contributeur_meme_entreprise_refuse(self):
        self.connecter(self.contrib2)
        self.assertEqual(self.client.get(self.image.fichier.url).status_code, 404)

    def test_proprietaire_et_data_scientist_autorises(self):
        for user in (self.contrib, self.ds, self.admin):
            self.client.force_login(user)
            r = self.client.get(self.image.miniature.url)
            self.assertEqual(r.status_code, 200, user)
            self.assertEqual(r["Content-Type"], "image/webp")
            self.assertIn("private", r["Cache-Control"])

    def test_image_supprimee_inaccessible(self):
        self.image.is_deleted = True
        self.image.save()
        self.connecter(self.ds)
        self.assertEqual(self.client.get(self.image.fichier.url).status_code, 404)

    def test_fichier_inconnu(self):
        self.connecter(self.ds)
        self.assertEqual(self.client.get("/media/images/inexistant.jpg").status_code, 404)

    def test_contributeur_ne_recupere_pas_la_verite_terrain(self):
        """Le ZIP de référence contient les réponses : réservé aux managers."""
        lot = Batch.objects.create(
            nom="L", client=self.wassa, cree_par=self.ds, assigne_a=self.contrib,
            zip_reference=zip_en_memoire({"images/a.jpg": b"x",
                                          "labels/a.json": {"shapes": []}}),
            zip_travail=zip_en_memoire({"labels/a.json": {"shapes": []}}, "t.zip"))
        self.connecter(self.contrib)
        self.assertEqual(self.client.get(lot.zip_reference.url).status_code, 404)
        # ... mais il peut récupérer son propre travail
        self.assertEqual(self.client.get(lot.zip_travail.url).status_code, 200)
        self.connecter(self.ds)
        r = self.client.get(lot.zip_reference.url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])


class ForceBruteTest(DonneesDeBase):
    """Risque : deviner un mot de passe en essayant des milliers de combinaisons."""

    def tenter(self, mdp, url="/compte/login/"):
        return self.client.post(url, {"username": "lea", "password": mdp})

    def test_blocage_apres_5_echecs_meme_avec_bon_mot_de_passe(self):
        for _ in range(5):
            self.tenter("mauvais")
        r = self.tenter("p")
        self.assertContains(r, "Trop de tentatives")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(JournalAcces.objects.filter(
            identifiant="lea", evenement=JournalAcces.Evenement.CONNEXION_ECHEC).count(), 5)
        self.assertTrue(JournalAcces.objects.filter(
            identifiant="lea", evenement=JournalAcces.Evenement.CONNEXION_BLOQUEE).exists())

    def test_quatre_echecs_ne_bloquent_pas(self):
        for _ in range(4):
            self.tenter("mauvais")
        r = self.tenter("p")
        self.assertEqual(r.status_code, 302)

    def test_backoffice_egalement_protege(self):
        for _ in range(5):
            self.tenter("mauvais", url="/admin/login/")
        r = self.client.post("/admin/login/", {"username": "lea", "password": "p"})
        self.assertContains(r, "Trop de tentatives")

    def test_connexion_et_deconnexion_journalisees(self):
        self.client.post("/compte/login/", {"username": "lea", "password": "p"},
                         REMOTE_ADDR="203.0.113.7")
        entree = JournalAcces.objects.get(evenement=JournalAcces.Evenement.CONNEXION_OK)
        self.assertEqual(entree.utilisateur, self.ds)
        self.assertEqual(entree.ip, "203.0.113.7")
        self.client.post("/compte/logout/")
        self.assertTrue(JournalAcces.objects.filter(
            evenement=JournalAcces.Evenement.DECONNEXION, utilisateur=self.ds).exists())

    def test_journal_en_lecture_seule_dans_le_backoffice(self):
        self.connecter(self.admin)
        self.assertEqual(self.client.get("/admin/core/journalacces/").status_code, 200)
        self.assertEqual(self.client.get("/admin/core/journalacces/add/").status_code, 403)


class EnTetesTest(DonneesDeBase):
    def test_csp_et_entetes_presents(self):
        r = self.client.get("/")
        self.assertIn("script-src 'self'", r["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", r["Content-Security-Policy"])
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("camera=()", r["Permissions-Policy"])

    def test_aucune_ressource_externe(self):
        """Polices auto-hébergées : plus aucun appel à Google Fonts."""
        r = self.client.get("/")
        self.assertNotContains(r, "googleapis")
        self.assertNotContains(r, "<script>")      # plus de script en ligne


class ConfigurationProductionTest(SimpleTestCase):
    """La configuration de production refuse les réglages dangereux."""

    def lancer(self, env_sup, *args):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("DJANGO_", "DATABASE_URL"))}
        env.update(env_sup)
        return subprocess.run(  # nosec B603 — commande fixe, sans shell
            [sys.executable, "-c",
             "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE',"
             "'config.settings'); from django.core.management import "
             f"execute_from_command_line as e; e(['manage.py', *{list(args)!r}])"],
            cwd=RACINE, env=env, capture_output=True, text=True, timeout=120)

    def test_debug_desactive_par_defaut_et_cle_obligatoire(self):
        """Sans variable d'environnement : DEBUG=False et le site refuse de
        démarrer sans vraie clé secrète (plus de clé par défaut en prod)."""
        r = self.lancer({}, "check")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY doit être défini", r.stderr)

    def test_check_deploy_sans_avertissement(self):
        r = self.lancer({
            "DJANGO_SECRET_KEY": "x" * 20 + "Y7#kq!Lm2@pR9$vT4&wZ8^bN6*cD3(eF",
            "DJANGO_ALLOWED_HOSTS": "nadjimkacemi.pythonanywhere.com",
        }, "check", "--deploy", "--fail-level", "WARNING")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("no issues", r.stdout)
