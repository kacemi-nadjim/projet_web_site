"""
TESTS DE CONFORMITÉ — pages légales, bandeau cookies, purge des formulaires.

Chaque test vérifie le contenu réel (page servie ou état de la base), et
pas seulement que la page s'affiche : leçon de l'incident INC-002.
"""

import io
from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone

from core.models import DemandeInscription, MessageContact

from .outils import DonneesDeBase


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
