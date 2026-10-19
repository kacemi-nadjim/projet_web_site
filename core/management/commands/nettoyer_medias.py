"""
Repère (et supprime sur demande) les fichiers « orphelins » du dossier
media/ : fichiers présents sur le disque mais rattachés à aucune image ni
aucun lot en base (restes d'anciens jeux de démonstration, de tests...).

Usage :
    python manage.py nettoyer_medias              (liste seulement)
    python manage.py nettoyer_medias --supprimer  (supprime)
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Batch, Image


class Command(BaseCommand):
    help = "Liste ou supprime les fichiers de media/ qui ne sont référencés nulle part."

    def add_arguments(self, parser):
        parser.add_argument("--supprimer", action="store_true")

    def handle(self, *args, **options):
        racine = Path(settings.MEDIA_ROOT)
        connus = set()
        for f, m in Image.objects.values_list("fichier", "miniature"):
            connus.update(x for x in (f, m) if x)
        for r, t in Batch.objects.values_list("zip_reference", "zip_travail"):
            connus.update(x for x in (r, t) if x)
        orphelins = [p for p in racine.rglob("*") if p.is_file()
                     and p.relative_to(racine).as_posix() not in connus]
        octets = sum(p.stat().st_size for p in orphelins)
        for p in orphelins:
            self.stdout.write(f"  {p.relative_to(racine).as_posix()}")
            if options["supprimer"]:
                p.unlink()
        action = "supprimé(s)" if options["supprimer"] else "trouvé(s) (ajoutez --supprimer)"
        self.stdout.write(self.style.SUCCESS(
            f"{len(orphelins)} fichier(s) orphelin(s) {action}, "
            f"{octets / 1024 / 1024:.2f} Mo."))
