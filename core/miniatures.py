"""
MINIATURES.PY — Éco-conception de la galerie.

Une photo de smartphone pèse 2 à 5 Mo. Afficher 24 originaux dans la
galerie revient à transférer des dizaines de Mo pour des vignettes de
quelques centimètres à l'écran. On génère donc, une seule fois au dépôt,
une miniature WebP (480 px de côté maximum, quelques dizaines de Ko).

Gains : poids de page divisé, bande passante et énergie économisées côté
serveur, réseau et terminal. Mesures : docs/mesures/poids_pages.json.
L'original reste intact pour l'export des datasets (qualité préservée).
"""

import io
import logging
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image as PILImage
from PIL import ImageOps

logger = logging.getLogger("pixbank.miniatures")


def creer_miniature(fichier):
    """
    Retourne un ContentFile WebP prêt à être enregistré, ou None si le
    fichier source n'est pas lisible (on ne bloque jamais le dépôt pour ça).
    """
    taille = settings.PIXBANK_MINIATURE_TAILLE
    try:
        if getattr(fichier, "closed", False):
            fichier.open("rb")        # fichier déjà enregistré puis refermé
        fichier.seek(0)
        with PILImage.open(fichier) as img:
            img = ImageOps.exif_transpose(img)     # respecte l'orientation photo
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            img.thumbnail((taille, taille))        # garde les proportions
            sortie = io.BytesIO()
            # Pas de paramètre exif= : les métadonnées (GPS...) sont retirées.
            img.save(sortie, format="WEBP",
                     quality=settings.PIXBANK_MINIATURE_QUALITE, method=6)
    except (OSError, ValueError) as exc:
        logger.warning("Miniature impossible pour %s : %s",
                       getattr(fichier, "name", "?"), exc)
        return None
    finally:
        try:
            fichier.seek(0)
        except (OSError, ValueError):
            pass
    nom = Path(getattr(fichier, "name", "image")).stem + ".webp"
    return ContentFile(sortie.getvalue(), name=nom)
