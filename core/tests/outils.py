"""Outils partagés par les tests : fabrication d'images, de ZIP, de comptes."""

import io
import json
import zipfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image as PILImage

from core.models import Category, Client, User

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def image_jpeg(nom="photo.jpg", couleur="#0e9f6e", taille=(60, 60), exif=None):
    buf = io.BytesIO()
    img = PILImage.new("RGB", taille, couleur)
    if exif is not None:
        img.save(buf, "JPEG", exif=exif)
    else:
        img.save(buf, "JPEG")
    return SimpleUploadedFile(nom, buf.getvalue(), content_type="image/jpeg")


def fixture(nom):
    """Un des vrais ZIP de démonstration (lot de 20 images, travail réussi/échoué)."""
    return SimpleUploadedFile(nom, (FIXTURES / nom).read_bytes(),
                              content_type="application/zip")


def zip_en_memoire(fichiers, nom="lot.zip"):
    """fichiers : dict {chemin_dans_le_zip: contenu (bytes ou dict JSON)}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for chemin, contenu in fichiers.items():
            if isinstance(contenu, dict):
                contenu = json.dumps(contenu)
            zf.writestr(chemin, contenu)
    return SimpleUploadedFile(nom, buf.getvalue(), content_type="application/zip")


def contenu(response):
    """Contenu d'une réponse, qu'elle soit classique ou en flux (FileResponse)."""
    if getattr(response, "streaming", False):
        return b"".join(response.streaming_content)
    return response.content


class DonneesDeBase(TestCase):
    """Deux entreprises clientes, des catégories et un compte par rôle."""

    @classmethod
    def setUpTestData(cls):
        cls.wassa = Client.objects.create(nom="Wassa")
        cls.acme = Client.objects.create(nom="ACME")
        cls.animal = Category.objects.create(nom="Animal")
        cls.visage = Category.objects.create(nom="visage", donnee_personnelle=True)
        cls.ds = User.objects.create_user("lea", password="p", role="DS", client=cls.wassa)
        cls.contrib = User.objects.create_user("karim", password="p", role="CONTRIB",
                                               client=cls.wassa, manager=cls.ds)
        cls.contrib2 = User.objects.create_user("nora", password="p", role="CONTRIB",
                                                client=cls.wassa, manager=cls.ds)
        cls.ds_acme = User.objects.create_user("sara", password="p", role="DS", client=cls.acme)
        cls.contrib_acme = User.objects.create_user("paul", password="p", role="CONTRIB",
                                                    client=cls.acme)
        cls.admin = User.objects.create_user("admin", password="p", role="ADMIN",
                                             client=cls.wassa, is_staff=True,
                                             is_superuser=True)

    def connecter(self, user):
        self.client.force_login(user)
