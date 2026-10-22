"""
Génère les miniatures manquantes (images déposées avant la V2).
Usage : python manage.py generer_miniatures
À lancer une seule fois après la mise à jour vers la V2.
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from core.miniatures import creer_miniature
from core.models import Image


class Command(BaseCommand):
    help = "Crée la miniature WebP des images qui n'en ont pas encore."

    def handle(self, *args, **options):
        faites, echecs = 0, 0
        # Après la migration 0006, les images existantes ont une miniature
        # NULL (colonne ajoutée) ; celles créées ensuite sans miniature ont "".
        sans_miniature = Q(miniature="") | Q(miniature__isnull=True)
        for image in Image.objects.filter(sans_miniature).iterator():
            contenu = creer_miniature(image.fichier)
            if contenu is None:
                echecs += 1
                continue
            image.miniature.save(contenu.name, contenu, save=False)
            image.save(update_fields=["miniature"])
            faites += 1
        self.stdout.write(self.style.SUCCESS(
            f"{faites} miniature(s) créée(s), {echecs} échec(s)."))
