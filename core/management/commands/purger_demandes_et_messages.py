"""
Efface les demandes d'inscription traitées et les messages de contact de
plus d'un an.

Ces formulaires contiennent un nom et une adresse e-mail : le RGPD impose
une durée de conservation définie (principe de limitation de la
conservation). En V1, ils étaient gardés sans limite. Une demande encore
« en attente » n'est jamais effacée : elle doit d'abord être traitée par
l'administrateur.

Usage : python manage.py purger_demandes_et_messages [--jours 365]
Planification : tâche quotidienne, avec les autres purges.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import DemandeInscription, MessageContact


class Command(BaseCommand):
    help = "Efface les demandes traitées et les messages de contact de plus de N jours."

    def add_arguments(self, parser):
        parser.add_argument("--jours", type=int, default=365)

    def handle(self, *args, **options):
        limite = timezone.now() - timedelta(days=options["jours"])
        nb_demandes, _ = (DemandeInscription.objects
                          .filter(date_demande__lt=limite)
                          .exclude(statut=DemandeInscription.Statut.EN_ATTENTE)
                          .delete())
        nb_messages, _ = MessageContact.objects.filter(date_envoi__lt=limite).delete()
        self.stdout.write(self.style.SUCCESS(
            f"{nb_demandes} demande(s) d'inscription et {nb_messages} message(s) "
            f"de contact de plus de {options['jours']} jours supprimé(s)."))
