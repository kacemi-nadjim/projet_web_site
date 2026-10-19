"""
QUALITE.PY — Le moteur de contrôle qualité de la labélisation.

Compare le travail d'un stagiaire (ZIP de labels LabelMe) à la
vérité terrain (labels de référence du manager) et produit un rapport.

Trois volets :
  1. STRUCTUREL : complétude (toutes les images labélisées ?),
     JSON valides, catégories cohérentes.
  2. PRÉCISION (IoU) : pour chaque objet annoté, mesure le recouvrement
     entre le rectangle du stagiaire et celui de référence.
     IoU = aire d'intersection / aire d'union (0 = aucun recouvrement,
     1 = parfait). C'est la métrique standard en computer vision.
  3. SIGNALEMENT : images marquées "floues/inexploitables" par le
     stagiaire (flag LabelMe), exclues du score et remontées au manager.
"""

import json
import zipfile

SEUIL_IOU = 0.5          # au-dessus, l'annotation est jugée correcte
FLAGS_FLOU = ("flou", "inexploitable", "blurry", "unusable")


def _lire_labels(fichier_zip):
    """Extrait {nom_image: contenu_json} des fichiers labels/*.json d'un ZIP."""
    labels = {}
    zf = zipfile.ZipFile(fichier_zip)
    for n in zf.namelist():
        bas = n.lower()
        if n.endswith("/") or "__MACOSX" in n:
            continue
        if ("/labels/" in bas or bas.startswith("labels/")) and bas.endswith(".json"):
            cle = n.split("/")[-1].rsplit(".", 1)[0]
            try:
                labels[cle] = json.loads(zf.read(n).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                labels[cle] = None  # JSON corrompu, signalé plus bas
    return labels


def _bbox(shape):
    """Retourne (x_min, y_min, x_max, y_max) d'une forme LabelMe."""
    pts = shape.get("points", [])
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def iou(boxA, boxB):
    """Intersection over Union entre deux rectangles."""
    if not boxA or not boxB:
        return 0.0
    xA = max(boxA[0], boxB[0]); yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2]); yB = min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    if inter == 0:
        return 0.0
    aireA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    aireB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    union = aireA + aireB - inter
    return inter / union if union > 0 else 0.0


def _est_flou(label_json):
    """Détecte si l'image est marquée floue/inexploitable (flag LabelMe)."""
    if not label_json:
        return False
    flags = label_json.get("flags", {}) or {}
    return any(flags.get(f) for f in FLAGS_FLOU)


def controler(zip_reference, zip_travail, categories_autorisees=None):
    """
    Compare le travail du stagiaire à la référence.
    Retourne un dict 'rapport' complet + un score global (0-100).
    """
    ref = _lire_labels(zip_reference)
    trav = _lire_labels(zip_travail)
    cats_ok = set(c.lower() for c in (categories_autorisees or []))

    lignes = []
    scores_images = []
    nb_floues = 0
    nb_manquantes = 0
    nb_erreurs_cat = 0

    for nom_img, ref_json in ref.items():
        ligne = {"image": nom_img, "statut": "ok", "iou": None,
                 "details": "", "flou": False}

        # 1. Image signalée floue par le stagiaire ?
        trav_json = trav.get(nom_img)
        if _est_flou(trav_json):
            ligne["statut"] = "floue"
            ligne["flou"] = True
            ligne["details"] = "Signalée inexploitable par l'annotateur"
            nb_floues += 1
            lignes.append(ligne)
            continue

        # 2. Complétude : le stagiaire a-t-il labélisé cette image ?
        if nom_img not in trav or trav_json is None:
            ligne["statut"] = "manquante"
            ligne["details"] = "Aucune annotation fournie (ou JSON invalide)"
            nb_manquantes += 1
            scores_images.append(0.0)
            lignes.append(ligne)
            continue

        # 3. Vérification des catégories utilisées
        shapes_trav = trav_json.get("shapes", [])
        if cats_ok:
            cats_utilisees = set(s.get("label", "").lower() for s in shapes_trav)
            hors = cats_utilisees - cats_ok
            if hors:
                ligne["statut"] = "categorie"
                ligne["details"] = f"Catégorie(s) non autorisée(s) : {', '.join(hors)}"
                nb_erreurs_cat += 1

        # 4. Précision IoU : on apparie chaque objet de référence au
        #    meilleur objet du stagiaire et on moyenne.
        shapes_ref = ref_json.get("shapes", []) if ref_json else []
        if shapes_ref:
            ious = []
            for sr in shapes_ref:
                box_r = _bbox(sr)
                meilleur = max((iou(box_r, _bbox(st)) for st in shapes_trav),
                               default=0.0)
                ious.append(meilleur)
            score_img = round(100 * sum(ious) / len(ious), 1)
            ligne["iou"] = score_img
            scores_images.append(score_img / 100)
            if ligne["statut"] == "ok":
                if score_img >= SEUIL_IOU * 100:
                    ligne["details"] = "Annotation conforme"
                else:
                    ligne["statut"] = "imprecis"
                    ligne["details"] = f"Recouvrement faible ({score_img}%)"
        else:
            ligne["details"] = "Pas d'objet de référence à comparer"

        lignes.append(ligne)

    # Score global = moyenne des scores d'images (hors floues)
    score_global = round(100 * sum(scores_images) / len(scores_images), 1) \
        if scores_images else 0.0

    rapport = {
        "score_global": score_global,
        "nb_images": len(ref),
        "nb_correctes": sum(1 for l in lignes if l["statut"] == "ok"),
        "nb_imprecises": sum(1 for l in lignes if l["statut"] == "imprecis"),
        "nb_manquantes": nb_manquantes,
        "nb_floues": nb_floues,
        "nb_erreurs_categorie": nb_erreurs_cat,
        "seuil_iou": int(SEUIL_IOU * 100),
        "lignes": lignes,
    }
    return rapport, score_global
