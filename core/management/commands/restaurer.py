"""
Restaure une sauvegarde créée par « sauvegarder ».

Usage : python manage.py restaurer backups/pixbank_AAAAMMJJ_HHMMSS --confirmer

Étapes : vérification des empreintes SHA-256 du manifeste -> vidage de la
base -> rechargement des données -> remise en place des fichiers.
L'option --confirmer est obligatoire : la restauration remplace les
données actuelles (procédure détaillée dans docs/DEPLOIEMENT.md).
"""

import gzip
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from .sauvegarder import sha256


def extraire_sans_risque(tar, destination):
    """Extrait l'archive en refusant tout chemin qui sortirait du dossier
    cible (attaque « path traversal »)."""
    racine = Path(destination).resolve()
    for membre in tar.getmembers():
        cible = (racine / membre.name).resolve()
        if racine not in cible.parents and cible != racine:
            raise CommandError(f"Chemin interdit dans l'archive : {membre.name}")
        if membre.issym() or membre.islnk():
            raise CommandError(f"Lien interdit dans l'archive : {membre.name}")
    try:
        tar.extractall(destination, filter="data")  # Python >= 3.10.12
    except TypeError:
        # Chemins et liens vérifiés ci-dessus avant extraction.
        tar.extractall(destination)  # noqa: S202  # nosec B202


class Command(BaseCommand):
    help = "Restaure la base de données et les fichiers depuis une sauvegarde."

    def add_arguments(self, parser):
        parser.add_argument("dossier")
        parser.add_argument("--confirmer", action="store_true")

    def handle(self, *args, **options):
        dossier = Path(options["dossier"])
        manifeste_path = dossier / "manifeste.json"
        if not manifeste_path.exists():
            raise CommandError("Manifeste introuvable : dossier de sauvegarde invalide.")
        manifeste = json.loads(manifeste_path.read_text(encoding="utf-8"))
        for nom, attendu in manifeste["sha256"].items():
            if sha256(dossier / nom) != attendu:
                raise CommandError(f"Fichier corrompu : {nom} (empreinte différente).")
        if not options["confirmer"]:
            raise CommandError("Ajoutez --confirmer : les données actuelles seront remplacées.")

        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "donnees.json"
            with gzip.open(dossier / "donnees.json.gz", "rt", encoding="utf-8") as src:
                fixture.write_text(src.read(), encoding="utf-8")
            with transaction.atomic():
                call_command("flush", interactive=False, verbosity=0)
                call_command("loaddata", str(fixture), verbosity=0)

        media = Path(settings.MEDIA_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(dossier / "media.tar.gz", "r:gz") as tar:
                extraire_sans_risque(tar, tmp)
            if media.exists():
                shutil.rmtree(media)
            source = Path(tmp) / "media"
            if source.exists():
                shutil.copytree(source, media)
            else:
                media.mkdir(parents=True, exist_ok=True)

        self.stdout.write(self.style.SUCCESS(
            f"Restauration terminée : {manifeste['nb_objets']} objets "
            f"(sauvegarde du {manifeste['date'][:19]})."))
