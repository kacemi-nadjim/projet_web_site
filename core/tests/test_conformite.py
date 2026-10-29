"""
TESTS DE CONFORMITÉ — pages légales, bandeau cookies, purge des formulaires.

Chaque test vérifie le contenu réel (page servie ou état de la base), et
pas seulement que la page s'affiche : leçon de l'incident INC-002.
"""

import csv
import io
import zipfile
from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone

from core.etl import cellule_sure
from core.models import Category, DemandeInscription, MessageContact

from .outils import DonneesDeBase
from .test_images import creer_image


class PurgeFormulairesTest(DonneesDeBase):

    def test_purge_apres_un_an_sauf_demandes_en_attente(self):
        vieux = timezone.now() - timedelta(days=400)
        traitee = DemandeInscription.objects.create(
            nom="A", email="a@x.fr", entreprise_souhaitee="X", motivation="m",
            statut="REFUSEE")
        en_attente = DemandeInscription.objects.create(
            nom="B", email="b@x.fr", entreprise_souhaitee="X", motivation="m")
        recente = DemandeInscription.objects.create(
            nom="C", email="c@x.fr", entreprise_souhaitee="X", motivation="m",
            statut="APPROUVEE")
        DemandeInscription.objects.filter(pk__in=[traitee.pk, en_attente.pk]).update(
            date_demande=vieux)
        ancien_msg = MessageContact.objects.create(nom="D", email="d@x.fr", message="m")
        MessageContact.objects.filter(pk=ancien_msg.pk).update(date_envoi=vieux)
        MessageContact.objects.create(nom="E", email="e@x.fr", message="m")

        sortie = io.StringIO()
        call_command("purger_demandes_et_messages", stdout=sortie)
        self.assertEqual(set(DemandeInscription.objects.values_list("pk", flat=True)),
                         {en_attente.pk, recente.pk})
        self.assertEqual(MessageContact.objects.count(), 1)
        self.assertIn("1 demande(s)", sortie.getvalue())


class PagesLegalesTest(DonneesDeBase):

    def test_mentions_legales_completes(self):
        """La V1 publiait des mentions légales « à compléter »."""
        mentions = self.client.get("/mentions-legales/")
        self.assertNotContains(mentions, "À compléter")
        self.assertContains(mentions, "Directeur de la publication")
        self.assertContains(mentions, "PythonAnywhere")

    def test_confidentialite_decrit_les_traitements_reels(self):
        page = self.client.get("/confidentialite/")
        for texte in ("adresse IP", "30 jours", "180 jours", "un an", "CNIL", "CSRF"):
            with self.subTest(texte):
                self.assertContains(page, texte)
        # L'ancienne version annonçait un effacement « sur demande », remplacé en V2
        self.assertNotContains(page, "sur demande")

    def test_cgu_moderation(self):
        self.assertContains(self.client.get("/cgu/"), "Modération des contenus")

    def test_bandeau_cookies_exact(self):
        """Il n'y a pas « un seul cookie » : session, CSRF et bandeau."""
        page = self.client.get("/")
        self.assertContains(page, "cookies techniques")
        self.assertNotContains(page, "uniquement un cookie de session")


class InjectionDeFormuleTest(DonneesDeBase):
    """OWASP A05 (injection) — signalé par le scan Semgrep : une cellule CSV
    qui commence par = + - @ serait exécutée comme une formule par un tableur."""

    def test_cellules_dangereuses_neutralisees(self):
        for valeur in ("=HYPERLINK(\"http://x\")", "+1+1", "-2+3", "@SUM(A1)"):
            with self.subTest(valeur):
                self.assertEqual(cellule_sure(valeur), "'" + valeur)
        self.assertEqual(cellule_sure("photo.jpg"), "photo.jpg")
        self.assertEqual(cellule_sure(640), 640)

    def test_export_neutralise_une_categorie_piegee(self):
        piege = Category.objects.create(nom="=1+1")
        creer_image(self.wassa, self.contrib, categories=[piege])
        self.connecter(self.ds)
        reponse = self.client.get("/exporter/")
        contenu_zip = b"".join(reponse.streaming_content)
        with zipfile.ZipFile(io.BytesIO(contenu_zip)) as z:
            lignes = list(csv.reader(io.StringIO(z.read("annotations.csv").decode())))
        self.assertEqual(lignes[1][1], "'=1+1")


class LienEvitementTest(DonneesDeBase):
    """RGAA 12.7 : un lien permet d'aller directement au contenu principal."""

    def test_present_sur_les_pages(self):
        self.connecter(self.ds)
        for url in ("/", "/galerie/", "/dashboard/", "/contact/"):
            with self.subTest(url):
                page = self.client.get(url)
                self.assertContains(page, 'href="#contenu"')
                self.assertContains(page, 'id="contenu"')


class CorrectionsDuScanZapTest(DonneesDeBase):
    """Alertes du scan dynamique OWASP ZAP corrigées dans le code."""

    def test_csp_sans_unsafe_inline_et_aucun_style_en_ligne(self):
        self.connecter(self.ds)
        for url in ("/", "/galerie/", "/dashboard/", "/contact/"):
            with self.subTest(url):
                page = self.client.get(url)
                self.assertNotIn("unsafe-inline", page["Content-Security-Policy"])
                self.assertNotContains(page, 'style="')

    def test_cookie_csrf_inaccessible_au_javascript(self):
        from django.conf import settings
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        page = self.client.get("/contact/")
        self.assertTrue(page.cookies["csrftoken"]["httponly"])


class TableauxDefilantsTest(DonneesDeBase):
    """RGAA 10.11 : les tableaux larges défilent dans leur cadre (page sans débordement à 320 px)."""

    def test_tableaux_dans_un_cadre_defilant(self):
        self.connecter(self.ds)
        for url in ("/lots/", "/dashboard/"):
            with self.subTest(url):
                page = self.client.get(url).content.decode()
                if "<table" in page:
                    self.assertIn('class="table-defilante"', page)
