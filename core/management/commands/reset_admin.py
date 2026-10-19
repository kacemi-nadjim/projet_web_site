"""
RESET_ADMIN — Répare / réinitialise le compte administrateur.

Utile si l'accès au back-office /admin/ est perdu : force le mot de passe
et les droits (is_staff + is_superuser) du compte 'admin', qu'il existe déjà
ou non. Aucune donnée n'est supprimée.

Usage :
    python manage.py reset_admin                       (local : demo1234)
    python manage.py reset_admin --mot-de-passe XXXX   (mot de passe choisi)

Sécurité (v1.1) : en production (DEBUG désactivé), la commande ne remet
plus jamais le mot de passe de démonstration « demo1234 », connu de tous :
sans --mot-de-passe, elle génère un mot de passe aléatoire robuste,
affiché une seule fois.
"""

import secrets

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.models import Client, User


class Command(BaseCommand):
    help = "Réinitialise le compte admin (mot de passe + droits back-office)"

    def add_arguments(self, parser):
        parser.add_argument("--mot-de-passe", dest="mdp", default=None)

    def handle(self, *args, **options):
        mdp = options["mdp"]
        if mdp is None:
            mdp = "demo1234" if settings.DEBUG else secrets.token_urlsafe(16)
        elif not settings.DEBUG:
            try:
                validate_password(mdp)
            except ValidationError as e:
                raise CommandError(" ".join(e.messages)) from e

        wassa, _ = Client.objects.get_or_create(nom="Wassa")
        admin, cree = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@example.com", "role": "ADMIN",
                      "client": wassa})

        # On force les droits et le mot de passe dans tous les cas
        admin.is_staff = True        # accès au back-office /admin/
        admin.is_superuser = True    # tous les droits
        admin.is_active = True
        admin.role = "ADMIN"
        if not admin.client:
            admin.client = wassa
        admin.set_password(mdp)
        admin.save()

        etat = "créé" if cree else "réparé"
        self.stdout.write(self.style.SUCCESS(
            f"Compte admin {etat} : identifiant 'admin', mot de passe '{mdp}'. "
            f"Accès au back-office /admin/ activé."))
