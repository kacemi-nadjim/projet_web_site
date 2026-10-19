#!/usr/bin/env python
"""Utilitaire en ligne de commande de Django (runserver, migrate, test...)."""
import os
import sys


def main():
    """Lance les commandes d'administration."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # manage.py sert au développement local : on y active DEBUG par défaut.
    # Le serveur de production passe par config/wsgi.py, où DEBUG reste
    # désactivé tant que DJANGO_DEBUG n'est pas explicitement défini.
    os.environ.setdefault("DJANGO_DEBUG", "True")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
