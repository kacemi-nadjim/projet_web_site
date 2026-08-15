"""
RESET_ADMIN — Répare / réinitialise le compte administrateur.

Utile si l'accès au back-office /admin/ est perdu : force le mot de passe
et les droits (is_staff + is_superuser) du compte 'admin', qu'il existe déjà
ou non. Aucune donnée n'est supprimée.

Usage :
    python manage.py reset_admin
"""

from django.core.management.base import BaseCommand
from core.models import User, Client


class Command(BaseCommand):
    help = "Réinitialise le compte admin (mot de passe demo1234 + droits back-office)"

    def handle(self, *args, **options):
        wassa, _ = Client.objects.get_or_create(nom="Wassa")

        admin, cree = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@example.com", "role": "ADMIN",
                      "client": wassa})

        # On force les droits et le mot de passe dans tous les cas
        admin.is_staff = True        # accès au back-office /admin/
        admin.is_superuser = True    # tous les droits
        admin.role = "ADMIN"
        if not admin.client:
            admin.client = wassa
        admin.set_password("demo1234")
        admin.save()

        etat = "créé" if cree else "réparé"
        self.stdout.write(self.style.SUCCESS(
            f"Compte admin {etat} : identifiant 'admin', mot de passe 'demo1234'. "
            f"Accès au back-office /admin/ activé."))
