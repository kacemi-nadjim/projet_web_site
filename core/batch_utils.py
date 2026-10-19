"""
BATCH_UTILS.PY — Utilitaires pour les lots de travail.

Validation DÉFENSIVE des ZIP : on ne fait jamais confiance au fichier
déposé. On vérifie la structure avant de l'accepter, pour éviter tout
plantage (surtout pendant la démo devant le jury).

Structure attendue d'un ZIP de référence :
    mon_lot.zip
    ├── images/   (les photos : .jpg, .png...)
    └── labels/   (les annotations LabelMe : un .json par image)
"""

import json
import zipfile

EXTENSIONS_IMAGE = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def _noms_propres(zf):
    """Liste les fichiers utiles d'un ZIP (ignore dossiers macOS, cachés)."""
    noms = []
    for n in zf.namelist():
        if n.endswith("/"):
            continue
        if "__MACOSX" in n or n.split("/")[-1].startswith("."):
            continue
        noms.append(n)
    return noms


def analyser_zip_reference(fichier_zip):
    """
    Vérifie qu'un ZIP de référence est bien formé.
    Retourne (ok, message, infos) :
      - ok : booléen
      - message : explication lisible (succès ou erreur)
      - infos : dict {images: [...], labels: [...]} si ok
    """
    try:
        zf = zipfile.ZipFile(fichier_zip)
    except zipfile.BadZipFile:
        return False, "Le fichier n'est pas un ZIP valide.", None

    noms = _noms_propres(zf)
    images, labels = {}, {}
    for n in noms:
        bas = n.lower()
        court = n.split("/")[-1]
        if "/images/" in bas or bas.startswith("images/"):
            if bas.endswith(EXTENSIONS_IMAGE):
                cle = court.rsplit(".", 1)[0]
                images[cle] = n
        elif "/labels/" in bas or bas.startswith("labels/"):
            if bas.endswith(".json"):
                cle = court.rsplit(".", 1)[0]
                labels[cle] = n

    if not images:
        return False, ("Aucune image trouvée. Le ZIP doit contenir un "
                       "sous-dossier 'images/' avec vos photos."), None
    if not labels:
        return False, ("Aucun label trouvé. Le ZIP doit contenir un "
                       "sous-dossier 'labels/' avec les fichiers JSON "
                       "de référence (un par image)."), None

    # Vérifie que les JSON de référence sont valides
    for cle, chemin in labels.items():
        try:
            json.loads(zf.read(chemin).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False, (f"Le fichier de label '{chemin}' n'est pas un "
                           f"JSON valide."), None

    infos = {
        "nb_images": len(images),
        "nb_labels": len(labels),
        "images": sorted(images.keys()),
        "labels": sorted(labels.keys()),
    }
    msg = (f"ZIP valide : {len(images)} image(s) et {len(labels)} "
           f"fichier(s) de label de référence.")
    return True, msg, infos


def construire_zip_pour_stagiaire(fichier_zip_reference):
    """
    Prépare le ZIP que le stagiaire télécharge : on lui donne SEULEMENT
    les images (pas les labels de référence, sinon il tricherait !).
    Retourne les octets d'un nouveau ZIP ne contenant que images/.
    """
    import io
    src = zipfile.ZipFile(fichier_zip_reference)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as dst:
        for n in _noms_propres(src):
            bas = n.lower()
            if ("/images/" in bas or bas.startswith("images/")) and \
               bas.endswith(EXTENSIONS_IMAGE):
                court = n.split("/")[-1]
                dst.writestr(f"images/{court}", src.read(n))
    buffer.seek(0)
    return buffer.getvalue()
