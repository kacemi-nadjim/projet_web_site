"""
Sauvegarde complète : base de données + fichiers déposés.

Usage : python manage.py sauvegarder [--dossier backups] [--garder 7]

Produit backups/pixbank_AAAAMMJJ_HHMMSS/ contenant :
  - donnees.json.gz : toutes les données (format Django, indépendant du
    moteur : une sauvegarde SQLite peut être restaurée dans PostgreSQL)
  - media.tar.gz    : photos, miniatures et ZIP des lots
  - manifeste.json  : date, version, nombre d'objets, empreintes SHA-256
Les sauvegardes les plus anciennes au-delà de --garder sont supprimées.
Restauration : python manage.py restaurer backups/pixbank_... --confirmer
"""

import gzip
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

EXCLUS = ["contenttypes", "auth.permission", "sessions", "admin.logentry"]


def sha256(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


class Command(BaseCommand):
    help = "Sauvegarde la base de données et les fichiers déposés."

    def add_arguments(self, parser):
        parser.add_argument("--dossier", default=str(settings.BASE_DIR / "backups"))
        parser.add_argument("--garder", type=int, default=7)

    def handle(self, *args, **options):
        racine = Path(options["dossier"])
        cible = racine / f"pixbank_{timezone.now():%Y%m%d_%H%M%S}"
        cible.mkdir(parents=True, exist_ok=False)

        # 1. Données
        tampon = io.StringIO()
        call_command("dumpdata", exclude=EXCLUS, natural_foreign=True,
                     natural_primary=True, indent=None, stdout=tampon)
        donnees = tampon.getvalue()
        with gzip.open(cible / "donnees.json.gz", "wt", encoding="utf-8") as f:
            f.write(donnees)
        nb_objets = len(json.loads(donnees))

        # 2. Fichiers déposés
        media = Path(settings.MEDIA_ROOT)
        with tarfile.open(cible / "media.tar.gz", "w:gz") as tar:
            if media.exists():
                tar.add(media, arcname="media")

        # 3. Manifeste (permet de vérifier l'intégrité avant restauration)
        manifeste = {
            "date": timezone.now().isoformat(),
            "version_pixbank": settings.PIXBANK_VERSION,
            "moteur_bdd": settings.DATABASES["default"]["ENGINE"],
            "nb_objets": nb_objets,
            "sha256": {n: sha256(cible / n) for n in ("donnees.json.gz", "media.tar.gz")},
        }
        (cible / "manifeste.json").write_text(
            json.dumps(manifeste, indent=2, ensure_ascii=False), encoding="utf-8")

        # 4. Rotation : on ne garde que les N dernières sauvegardes
        anciennes = sorted(racine.glob("pixbank_*"))[:-options["garder"]]
        for dossier in anciennes:
            shutil.rmtree(dossier)

        self.stdout.write(self.style.SUCCESS(
            f"Sauvegarde créée : {cible} ({nb_objets} objets). "
            f"{len(anciennes)} ancienne(s) sauvegarde(s) supprimée(s)."))
