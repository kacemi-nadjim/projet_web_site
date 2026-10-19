"""
Efface DÉFINITIVEMENT les images supprimées depuis plus de 30 jours.

La suppression dans l'application est d'abord « logique » (soft delete) :
l'image disparaît immédiatement pour les utilisateurs, mais reste
récupérable 30 jours par un administrateur (erreur de manipulation).
Passé ce délai, cette commande efface la ligne ET les fichiers (original
+ miniature) : le droit à l'effacement du RGPD (article 17) est respecté
jusqu'au bout et l'espace disque est libéré.

Usage : python manage.py purger_images_supprimees [--jours 30]
Planification : tâche quotidienne (voir docs/MAINTENANCE.md).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Image


class Command(BaseCommand):
    help = "Efface définitivement les images supprimées depuis plus de N jours."

    def add_arguments(self, parser):
        parser.add_argument("--jours", type=int, default=30)

    def handle(self, *args, **options):
        limite = timezone.now() - timedelta(days=options["jours"])
        a_effacer = Image.objects.filter(is_deleted=True, deleted_at__lt=limite)
        nb, octets = 0, 0
        for image in a_effacer.iterator():
            for champ in (image.fichier, image.miniature):
                if champ and champ.storage.exists(champ.name):
                    octets += champ.size
                    champ.storage.delete(champ.name)
            image.delete()
            nb += 1
        self.stdout.write(self.style.SUCCESS(
            f"{nb} image(s) effacée(s) définitivement, "
            f"{octets / 1024 / 1024:.1f} Mo libérés."))
