"""
SEED.PY — Jeu de données de test (fixtures), exigé par le cours BDD.
Usage : python manage.py seed
"""

import io
import random

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image as PILImage, ImageDraw

from core.models import Category, Client, Image, calculer_hash, User

CATEGORIES = [
    ("Visage", True, "Visages humains (détection/floutage)."),
    ("Plaque d'immatriculation", True, "Plaques de véhicules."),
    ("Écran de téléphone", False, "Smartphones avec écran visible."),
    ("Écran TV / moniteur", False, "Téléviseurs et moniteurs."),
    ("Animal", False, "Animaux domestiques et sauvages."),
    ("Véhicule", False, "Voitures, camions, deux-roues."),
]


def fake_image(label, couleur, n):
    img = PILImage.new("RGB", (640, 480), couleur)
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 600, 440], outline="white", width=4)
    d.text((60, 60), f"DEMO #{n} — {label}", fill="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return ContentFile(buf.getvalue(), name=f"demo_{n}_{random.randint(100,999)}.jpg")


class Command(BaseCommand):
    help = "Remplit la base avec des données de démonstration"

    def handle(self, *args, **options):
        wassa, _ = Client.objects.get_or_create(nom="Wassa", defaults={"secteur": "IA / Computer vision"})
        acme, _ = Client.objects.get_or_create(nom="ACME Parking", defaults={"secteur": "Gestion de parkings"})

        for username, role, client, su in [
            ("admin", "ADMIN", wassa, True),
            ("karim_contrib", "CONTRIB", wassa, False),
            ("lea_ds", "DS", wassa, False),
            ("paul_acme", "CONTRIB", acme, False),
            ("sara_ds_acme", "DS", acme, False),
        ]:
            if not User.objects.filter(username=username).exists():
                u = User(username=username, role=role, client=client,
                         email=f"{username}@example.com", is_staff=su, is_superuser=su)
                u.set_password("demo1234")
                u.save()
                self.stdout.write(f"Utilisateur : {username} / demo1234")

        cats = {}
        for nom, dp, desc in CATEGORIES:
            cat, _ = Category.objects.get_or_create(nom=nom, defaults={"donnee_personnelle": dp, "description": desc})
            cats[nom] = cat

        if Image.objects.count() == 0:
            karim = User.objects.get(username="karim_contrib")
            paul = User.objects.get(username="paul_acme")
            couleurs = ["#0e9f6e", "#3b5bdb", "#b7791f", "#845ef7", "#c0392b", "#1098ad"]
            noms = list(cats.keys())
            for i in range(20):
                user = karim if i % 5 else paul
                contenu = fake_image(noms[i % len(noms)], couleurs[i % 6], i)
                empreinte = calculer_hash(contenu)
                img = Image(client=user.client, uploaded_by=user,
                            hash_fichier=empreinte,
                            consentement=True,
                            statut=random.choice([Image.Statut.VALIDEE, Image.Statut.VALIDEE, Image.Statut.EN_ATTENTE]))
                img.fichier.save(contenu.name, contenu)
                # multi-catégories : parfois 1, parfois 2 labels
                choix = [cats[noms[i % len(noms)]]]
                if i % 3 == 0:
                    choix.append(cats[noms[(i + 1) % len(noms)]])
                img.categories.set(choix)
            self.stdout.write(f"{Image.objects.count()} images de démo créées")

        self.stdout.write(self.style.SUCCESS("Seed terminé !"))
