"""
MESURER_EXPORT.PY — Nombre de requêtes SQL et temps de l'export du dataset.

Appelle la page /exporter/ comme le ferait le navigateur d'un data
scientist, sur la base du projet, et relève pour chaque essai :
  - le nombre de requêtes SQL envoyées à la base,
  - le temps de réponse (construction du ZIP comprise),
  - le nombre d'images et le poids du ZIP produit.
Chaque essai est annulé à la fin (transaction) : la base n'est pas modifiée.

Usage (depuis le dossier qui contient manage.py, environnement activé) :
    python outils/mesurer_export.py
    python outils/mesurer_export.py --compte lea_ds --essais 5
"""

import argparse
import os
import statistics
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
try:  # mêmes réglages que manage.py (fichier .env s'il existe)
    from config.env import charger_env
    charger_env()
except ImportError:
    pass
os.environ.setdefault("DJANGO_DEBUG", "True")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection, transaction  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402


class AnnulerEssai(Exception):
    """Sert à annuler la transaction de chaque essai."""


def un_essai(utilisateur):
    client = Client()
    client.force_login(utilisateur)
    resultat = {}
    try:
        with transaction.atomic():
            with CaptureQueriesContext(connection) as requetes:
                debut = time.perf_counter()
                reponse = client.get("/exporter/", HTTP_HOST="127.0.0.1")
                contenu = b"".join(reponse.streaming_content) \
                    if reponse.streaming else reponse.content
                duree = time.perf_counter() - debut
            sql = [q["sql"] for q in requetes.captured_queries
                   if not q["sql"].upper().startswith(("SAVEPOINT", "RELEASE"))]
            resultat = {"statut": reponse.status_code, "requetes": len(sql),
                        "temps_ms": duree * 1000, "contenu": contenu}
            raise AnnulerEssai
    except AnnulerEssai:
        pass
    return resultat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compte", default="lea_ds",
                        help="data scientist qui exporte (défaut : lea_ds)")
    parser.add_argument("--essais", type=int, default=5)
    args = parser.parse_args()

    utilisateur = get_user_model().objects.get(username=args.compte)
    essais = [un_essai(utilisateur) for _ in range(args.essais)]
    if essais[0]["statut"] != 200 or not essais[0]["contenu"].startswith(b"PK"):
        sys.exit(f"Export impossible (code {essais[0]['statut']}) : le compte "
                 "doit être data scientist et son client avoir des images validées.")

    with zipfile.ZipFile(BytesIO(essais[0]["contenu"])) as z:
        nb_images = sum(1 for n in z.namelist() if not n.endswith(".csv"))
    temps = [e["temps_ms"] for e in essais]
    print(f"Compte : {args.compte} — {nb_images} images exportées, "
          f"ZIP de {len(essais[0]['contenu']) / 1_000_000:.1f} Mo")
    print(f"Requêtes SQL     : {essais[0]['requetes']}")
    print(f"Temps (médiane)  : {statistics.median(temps):.0f} ms "
          f"(min {min(temps):.0f} ms, max {max(temps):.0f} ms, {args.essais} essais)")


if __name__ == "__main__":
    main()
