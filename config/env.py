"""
Chargement d'un fichier .env (variables d'environnement du serveur).

Sur le serveur, les secrets (clé secrète, mot de passe de la base...) sont
écrits dans un fichier .env à la racine du projet. Ce fichier n'est JAMAIS
versionné (voir .gitignore) ; modèle : .env.exemple.
Une variable déjà définie dans l'environnement n'est pas écrasée.
"""

import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def charger_env(chemin=None):
    chemin = Path(chemin or os.environ.get("PIXBANK_ENV_FILE", RACINE / ".env"))
    if not chemin.is_file():
        return False
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), valeur.strip().strip("\"'"))
    return True
