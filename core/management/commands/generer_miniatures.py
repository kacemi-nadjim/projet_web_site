"""
Génère les miniatures manquantes (images déposées avant la v1.1).
Usage : python manage.py generer_miniatures
À lancer une seule fois après la mise à jour (voir docs/DEPLOIEMENT.md).
"""

from django.core.management.base import BaseCommand

from core.miniatures import creer_miniature
from core.models import Image


class Command(BaseCommand):
    help = "Crée la miniature WebP des images qui n'en ont pas encore."

    def handle(self, *args, **options):
        faites, echecs = 0, 0
        for image in Image.objects.filter(miniature="").iterator():
            contenu = creer_miniature(image.fichier)
            if contenu is None:
                echecs += 1
                continue
            image.miniature.save(contenu.name, contenu, save=False)
            image.save(update_fields=["miniature"])
            faites += 1
        self.stdout.write(self.style.SUCCESS(
            f"{faites} miniature(s) créée(s), {echecs} échec(s)."))
