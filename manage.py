#!/usr/bin/env python
"""Utilitaire en ligne de commande de Django (runserver, migrate, test...)."""
import os
import sys


def main():
    """Lance les commandes d'administration."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # Sur le serveur, le fichier .env fournit les réglages de production
    # (dont DJANGO_DEBUG=False) : les commandes utilisent alors exactement
    # la même configuration que le site.
    from config.env import charger_env
    charger_env()
    # Sans .env (poste de développement), DEBUG est activé par défaut.
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
