"""
Supprime les entrées du journal d'accès plus anciennes que la durée de
conservation (180 jours par défaut). Les adresses IP sont des données
personnelles : le RGPD impose de ne pas les garder indéfiniment.
Usage : python manage.py purger_journal [--jours 180]
Planification conseillée : tâche quotidienne (onglet « Tasks » de
PythonAnywhere), voir docs/MAINTENANCE.md.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import JournalAcces


class Command(BaseCommand):
    help = "Purge le journal d'accès au-delà de la durée de conservation."

    def add_arguments(self, parser):
        parser.add_argument("--jours", type=int,
                            default=settings.PIXBANK_JOURNAL_CONSERVATION_JOURS)

    def handle(self, *args, **options):
        limite = timezone.now() - timedelta(days=options["jours"])
        nb, _ = JournalAcces.objects.filter(date__lt=limite).delete()
        self.stdout.write(self.style.SUCCESS(
            f"{nb} entrée(s) de plus de {options['jours']} jours supprimée(s)."))
