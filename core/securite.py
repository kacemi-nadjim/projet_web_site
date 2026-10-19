"""
SECURITE.PY — Contrôles de sécurité centralisés.

1. Validation des images déposées : on vérifie le CONTENU réel du fichier
   (avec Pillow), pas seulement son extension. Avant la v1.1, un fichier
   HTML contenant du JavaScript était accepté comme « image » (anomalie
   ANO-003, voir docs/REGISTRE_ANOMALIES.md).
2. Validation des ZIP : taille, nombre de fichiers, taille décompressée
   (anti « bombe ZIP ») et chemins dangereux (« ../ »).
3. Limitation des tentatives de connexion (anti force brute), appuyée sur
   le journal d'accès stocké en base.
"""

import logging
import zipfile
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from PIL import Image as PILImage
from PIL import UnidentifiedImageError

logger = logging.getLogger("pixbank.securite")


# ------------------------------------------------------------
# 1. IMAGES
# ------------------------------------------------------------
def valider_image(fichier):
    """
    Lève ValidationError si le fichier n'est pas une vraie image autorisée.
    Contrôles : taille maximale, format réellement décodable par Pillow,
    format présent dans la liste blanche, intégrité du fichier.
    """
    if fichier.size > settings.PIXBANK_IMAGE_TAILLE_MAX:
        limite = settings.PIXBANK_IMAGE_TAILLE_MAX // (1024 * 1024)
        raise ValidationError(
            f"« {fichier.name} » dépasse la taille maximale de {limite} Mo.")
    try:
        fichier.seek(0)
        with PILImage.open(fichier) as img:
            fmt = img.format
            img.verify()          # détecte les fichiers tronqués ou falsifiés
    except (UnidentifiedImageError, OSError, SyntaxError,
            PILImage.DecompressionBombError) as exc:
        logger.warning("Fichier refusé (pas une image valide) : %s", fichier.name)
        raise ValidationError(
            f"« {fichier.name} » n'est pas une image valide.") from exc
    finally:
        fichier.seek(0)
    if fmt not in settings.PIXBANK_IMAGE_FORMATS:
        raise ValidationError(
            f"« {fichier.name} » : format {fmt} non autorisé "
            f"(acceptés : {', '.join(settings.PIXBANK_IMAGE_FORMATS)}).")
    return fmt


# ------------------------------------------------------------
# 2. ZIP
# ------------------------------------------------------------
def valider_zip(fichier):
    """
    Vérifie qu'un ZIP déposé est raisonnable AVANT de l'ouvrir en détail.
    Retourne None si tout va bien, sinon un message d'erreur lisible.
    """
    if fichier.size > settings.PIXBANK_ZIP_TAILLE_MAX:
        return "Le ZIP dépasse la taille maximale autorisée."
    try:
        fichier.seek(0)
        zf = zipfile.ZipFile(fichier)
    except zipfile.BadZipFile:
        return "Le fichier n'est pas un ZIP valide."
    infos = zf.infolist()
    if len(infos) > settings.PIXBANK_ZIP_NB_FICHIERS_MAX:
        return "Le ZIP contient trop de fichiers."
    total = sum(i.file_size for i in infos)
    if total > settings.PIXBANK_ZIP_DECOMPRESSE_MAX:
        logger.warning("ZIP refusé (bombe ZIP probable) : %s", fichier.name)
        return "Le contenu décompressé du ZIP est trop volumineux."
    for info in infos:
        nom = info.filename.replace("\\", "/")
        if nom.startswith("/") or ".." in nom.split("/"):
            logger.warning("ZIP refusé (chemin dangereux) : %s", info.filename)
            return "Le ZIP contient un chemin de fichier interdit."
    fichier.seek(0)
    return None


# ------------------------------------------------------------
# 3. CONNEXION : ANTI FORCE BRUTE
# ------------------------------------------------------------
def ip_client(request):
    """Adresse IP du visiteur (derrière le proxy de l'hébergeur si besoin)."""
    if request is None:
        return None
    transmise = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if transmise:
        return transmise.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def connexion_bloquee(identifiant):
    """
    True si cet identifiant a déjà échoué trop souvent récemment.
    On compte les échecs dans le journal d'accès (en base), ce qui fonctionne
    même si l'hébergeur fait tourner plusieurs processus.
    """
    from .models import JournalAcces

    depuis = timezone.now() - timedelta(
        minutes=settings.PIXBANK_CONNEXION_FENETRE_MINUTES)
    echecs = JournalAcces.objects.filter(
        identifiant=identifiant,
        evenement=JournalAcces.Evenement.CONNEXION_ECHEC,
        date__gte=depuis,
    ).count()
    return echecs >= settings.PIXBANK_CONNEXION_ESSAIS_MAX
