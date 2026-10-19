"""
Point d'entrée du serveur web de production (WSGI).

Sur PythonAnywhere, le fichier WSGI de l'onglet « Web » se résume à :
    import sys
    sys.path.insert(0, "/home/<utilisateur>/projet_web_site")
    from config.wsgi import application
Les réglages (clé secrète, domaines, base) sont lus dans le fichier .env.
DEBUG reste désactivé tant que DJANGO_DEBUG=True n'y figure pas.
"""

import os

from django.core.wsgi import get_wsgi_application

from config.env import charger_env

charger_env()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
