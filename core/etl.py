"""
ETL.PY — Construction du dataset exporté (Extract -> Transform -> Load).

  Extract   : les images validées du client (requête préparée par la vue)
  Transform : une ligne CSV par image (catégories, dimensions, date, RGPD)
  Load      : un ZIP contenant annotations.csv + le dossier images/

Optimisations v1.1 :
  - plus de requête SQL par image (catégories préchargées : N+1 corrigé) ;
  - les JPEG/PNG sont déjà compressés : on les stocke tels quels dans le
    ZIP (ZIP_STORED) au lieu de les recompresser pour un gain quasi nul ;
    seul le CSV est compressé -> export plus rapide, moins de CPU ;
  - le ZIP est construit dans un fichier temporaire qui bascule sur disque
    au-delà de 50 Mo, au lieu d'être gardé entièrement en mémoire.
"""

import csv
import io
import logging
import tempfile
import zipfile

logger = logging.getLogger("pixbank.etl")

SEUIL_MEMOIRE = 50 * 1024 * 1024
ENTETE_CSV = ["nom_fichier", "categories", "largeur", "hauteur",
              "date_upload", "donnee_personnelle"]


def ligne_csv(img):
    nom = img.fichier.name.split("/")[-1]
    return [nom, img.labels(), img.largeur, img.hauteur,
            img.date_upload.strftime("%Y-%m-%d"),
            "oui" if img.contient_donnee_perso() else "non"]


def construire_dataset(images):
    """
    images : liste d'Image avec categories préchargées.
    Retourne (fichier_temporaire_positionné_au_début, nb_images_incluses).
    """
    sortie = tempfile.SpooledTemporaryFile(max_size=SEUIL_MEMOIRE)
    nb_inclus = 0
    with zipfile.ZipFile(sortie, "w") as zf:
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(ENTETE_CSV)
        for img in images:
            writer.writerow(ligne_csv(img))
        zf.writestr("annotations.csv", csv_buffer.getvalue(),
                    compress_type=zipfile.ZIP_DEFLATED)
        for img in images:
            nom = img.fichier.name.split("/")[-1]
            try:
                with img.fichier.open("rb") as f:
                    zf.writestr(f"images/{nom}", f.read(),
                                compress_type=zipfile.ZIP_STORED)
                nb_inclus += 1
            except OSError:
                # Fichier absent du disque : on le signale dans les journaux
                # au lieu de l'ignorer silencieusement (anomalie ANO-006).
                logger.error("Export : fichier introuvable %s (image %s)",
                             img.fichier.name, img.pk)
    sortie.seek(0)
    return sortie, nb_inclus
