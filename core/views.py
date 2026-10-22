"""
VIEWS.PY — Les vues (architecture MVT de Django).

Rôle d'une vue : recevoir la requête, vérifier les droits, appeler la
logique métier, choisir la réponse. La logique métier elle-même vit dans
des modules dédiés, testés séparément :
    etl.py           construction du dataset exporté
    qualite.py       contrôle qualité IoU des lots
    batch_utils.py   lecture des ZIP de lots
    securite.py      validation des fichiers, anti force brute
    permissions.py   règles d'accès (cloisonnement)
    miniatures.py    éco-conception de la galerie

Deux règles de sécurité systématiques :
1. @login_required : pas connecté = pas d'accès
2. Cloisonnement : on ne montre QUE les données du client connecté
"""

import logging
import mimetypes

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import batch_utils, etl, qualite, securite, statistiques
from .forms import (
    BatchCreationForm,
    BatchSoumissionForm,
    ContactForm,
    DemandeInscriptionForm,
    ImageUploadForm,
)
from .models import Batch, Category, Export, Image, JournalAcces, MessageContact, calculer_hash
from .permissions import peut_gerer_lot, peut_voir_image, peut_voir_lot

logger = logging.getLogger("pixbank.vues")

# Certaines installations de Python ne déclarent pas le type WebP.
mimetypes.add_type("image/webp", ".webp")


def _refuser(request, detail):
    """Accès hors périmètre : on journalise puis on répond 404 (on ne
    confirme même pas l'existence de la ressource)."""
    JournalAcces.enregistrer(JournalAcces.Evenement.ACCES_REFUSE,
                             request=request, detail=detail)
    raise Http404("Ressource introuvable")


# ============================================================
# PAGES PUBLIQUES
# ============================================================

def home(request):
    return render(request, "core/home.html")


def contact(request):
    """Page contact avec formulaire + case consentement RGPD.

    Le message est enregistré en base (modèle MessageContact) pour que
    l'administrateur puisse le consulter depuis le back-office
    (correctif de l'incident INC-002, voir le dossier de projet, section 2.12)."""
    envoye = False
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            MessageContact.objects.create(
                nom=form.cleaned_data["nom"],
                email=form.cleaned_data["email"],
                message=form.cleaned_data["message"],
                consentement=form.cleaned_data["consentement"],
            )
            envoye = True
            form = ContactForm()
    else:
        form = ContactForm()
    return render(request, "core/contact.html", {"form": form, "envoye": envoye})


def demande_inscription(request):
    """
    Demande publique pour devenir contributeur.
    Aucune création de compte ici : on enregistre une demande que
    l'administrateur traitera. Sécurité : l'accès n'est jamais automatique.
    """
    envoye = False
    if request.method == "POST":
        form = DemandeInscriptionForm(request.POST)
        if form.is_valid():
            form.save()
            envoye = True
            form = DemandeInscriptionForm()
    else:
        form = DemandeInscriptionForm()
    return render(request, "core/inscription.html",
                  {"form": form, "envoye": envoye})


def mentions(request):
    return render(request, "core/mentions.html")


def confidentialite(request):
    return render(request, "core/confidentialite.html")


def cgu(request):
    return render(request, "core/cgu.html")


def sante(request):
    """
    Point de supervision (« healthcheck ») : un service de surveillance
    externe (ex. UptimeRobot, gratuit) l'interroge toutes les 5 minutes et
    alerte par e-mail si le site ou la base ne répondent plus.
    """
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        base = "ok"
    except Exception:  # noqa: BLE001 — toute panne de base doit être signalée
        logger.exception("Healthcheck : base de données indisponible")
        base = "erreur"
    statut = 200 if base == "ok" else 503
    return JsonResponse({"statut": "ok" if statut == 200 else "degrade",
                         "version": settings.PIXBANK_VERSION,
                         "base_de_donnees": base}, status=statut)


# ============================================================
# IMAGES
# ============================================================

def _images_du_client(user):
    """Cloisonnement centralisé : images non supprimées du client."""
    return (Image.objects
            .filter(client=user.client, is_deleted=False)
            .prefetch_related("categories")
            .select_related("uploaded_by"))


@login_required
def galerie(request):
    images = _images_du_client(request.user)
    if request.user.role == "CONTRIB":
        images = images.filter(uploaded_by=request.user)

    categorie_id = request.GET.get("categorie", "")
    if categorie_id.isdigit():
        images = images.filter(categories__id=categorie_id).distinct()
    else:
        categorie_id = ""
    statut = request.GET.get("statut", "")
    if statut in Image.Statut.values:
        images = images.filter(statut=statut)
    else:
        statut = ""

    # Pagination réelle (24 images par page) : on ne charge jamais toute
    # la banque d'images d'un coup, quelle que soit sa taille.
    page = Paginator(images, settings.PIXBANK_IMAGES_PAR_PAGE).get_page(
        request.GET.get("page"))

    context = {
        "page": page,
        "images": page.object_list,
        "categories": Category.objects.all(),
        "filtre_categorie": categorie_id,
        "filtre_statut": statut,
        "total": page.paginator.count,
    }
    return render(request, "core/galerie.html", context)


@login_required
def upload(request):
    if request.method == "POST":
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            fichiers = form.cleaned_data["fichiers"]
            categories = form.cleaned_data["categories"]
            consentement = form.cleaned_data["consentement"]
            deposees, doublons = 0, 0
            for f in fichiers:
                empreinte = calculer_hash(f)
                if Image.objects.filter(client=request.user.client,
                                        hash_fichier=empreinte,
                                        is_deleted=False).exists():
                    doublons += 1
                    continue
                try:
                    # Transaction : l'image et ses catégories sont
                    # enregistrées ensemble, ou pas du tout.
                    with transaction.atomic():
                        image = Image(fichier=f, client=request.user.client,
                                      uploaded_by=request.user,
                                      consentement=consentement,
                                      hash_fichier=empreinte,
                                      statut=Image.Statut.EN_ATTENTE)
                        image.save()
                        image.categories.set(categories)
                except IntegrityError:
                    # Deux dépôts simultanés du même fichier : la contrainte
                    # d'unicité de la base a bloqué le second.
                    doublons += 1
                    continue
                deposees += 1
            if deposees:
                messages.success(
                    request, f"{deposees} image(s) déposée(s), en attente de validation.")
            if doublons:
                messages.warning(
                    request, f"{doublons} image(s) ignorée(s) : déjà présentes (doublon).")
            return redirect("galerie")
    else:
        form = ImageUploadForm()
    return render(request, "core/upload.html", {"form": form})


@login_required
@require_POST
def supprimer_image(request, image_id):
    image = get_object_or_404(Image, pk=image_id, client=request.user.client)
    if image.uploaded_by != request.user and not request.user.is_admin_metier():
        messages.error(request, "Vous ne pouvez supprimer que vos images.")
        return redirect("galerie")
    image.is_deleted = True
    image.deleted_at = timezone.now()
    image.save(update_fields=["is_deleted", "deleted_at"])
    messages.success(request, "Image supprimée.")
    return redirect("galerie")


@login_required
def media_protege(request, chemin):
    """
    Seule porte d'accès aux fichiers déposés (photos, miniatures, ZIP).

    Avant la V2, le dossier media/ était public : toute personne
    connaissant l'adresse d'une photo (visages, plaques) pouvait l'ouvrir
    sans être connectée, et un contributeur pouvait récupérer le ZIP de
    référence contenant les réponses attendues (anomalie ANO-004).
    Désormais chaque fichier est rattaché à son objet en base, et les
    règles de cloisonnement sont vérifiées avant de l'envoyer.
    """
    user = request.user
    image = (Image.objects.filter(Q(fichier=chemin) | Q(miniature=chemin))
             .only("id", "client_id", "uploaded_by_id", "is_deleted",
                   "fichier", "miniature").first())
    if image is not None:
        if not peut_voir_image(user, image):
            _refuser(request, f"image {image.pk}")
        champ = image.miniature if image.miniature.name == chemin else image.fichier
        return _envoyer(champ, cache=True)

    batch = Batch.objects.filter(
        Q(zip_reference=chemin) | Q(zip_travail=chemin)).first()
    if batch is not None:
        if batch.zip_reference.name == chemin:
            # Le ZIP de référence contient la vérité terrain : réservé aux
            # managers (sinon un contributeur aurait les réponses).
            autorise = peut_gerer_lot(user, batch)
        else:
            autorise = peut_gerer_lot(user, batch) or batch.assigne_a_id == user.id
        if not autorise:
            _refuser(request, f"fichier du lot {batch.pk}")
        JournalAcces.enregistrer(JournalAcces.Evenement.TELECHARGEMENT,
                                 request=request, detail=chemin)
        champ = batch.zip_reference if batch.zip_reference.name == chemin else batch.zip_travail
        return _envoyer(champ, cache=False, piece_jointe=True)

    raise Http404("Fichier introuvable")


def _envoyer(champ, cache, piece_jointe=False):
    try:
        f = champ.open("rb")
    except (FileNotFoundError, OSError) as exc:
        logger.error("Fichier manquant sur le disque : %s", champ.name)
        raise Http404("Fichier introuvable") from exc
    type_mime = mimetypes.guess_type(champ.name)[0] or "application/octet-stream"
    resp = FileResponse(f, content_type=type_mime, as_attachment=piece_jointe,
                        filename=champ.name.split("/")[-1])
    # Fichiers privés : le navigateur peut les garder en cache (éco), mais
    # jamais un proxy partagé.
    resp["Cache-Control"] = "private, max-age=86400" if cache else "private, no-store"
    return resp


@login_required
def exporter(request):
    """EXPORT ZIP + CSV — la brique ETL (Extract → Transform → Load)."""
    if not request.user.is_data_scientist():
        messages.error(request, "Seuls les data scientists peuvent exporter.")
        return redirect("galerie")

    qs = _images_du_client(request.user).filter(statut=Image.Statut.VALIDEE)
    categorie_id = request.GET.get("categorie", "")
    libelle_filtre = "toutes catégories"
    if categorie_id.isdigit():
        qs = qs.filter(categories__id=categorie_id).distinct()
        cat = Category.objects.filter(id=categorie_id).first()
        libelle_filtre = cat.nom if cat else libelle_filtre

    # Tri par identifiant : ordre stable, directement fourni par l'index
    # partiel (client, statut) -> pas de tri de milliers de lignes.
    images = list(qs.order_by("pk"))   # une requête (+1 pour les catégories)
    if not images:
        messages.warning(request, "Aucune image validée à exporter pour ce filtre.")
        return redirect("galerie")

    fichier_zip, nb = etl.construire_dataset(images)
    Export.objects.create(user=request.user, client=request.user.client,
                          nb_images=nb, filtre_applique=libelle_filtre)
    JournalAcces.enregistrer(JournalAcces.Evenement.EXPORT, request=request,
                             detail=f"{nb} images — {libelle_filtre}")
    horodatage = timezone.now().strftime("%Y%m%d_%H%M")
    nom_zip = f"dataset_{request.user.client.nom}_{horodatage}.zip"
    return FileResponse(fichier_zip, as_attachment=True, filename=nom_zip,
                        content_type="application/zip")


@login_required
def dashboard(request):
    """DASHBOARD BI — statistiques cloisonnées par client."""
    if not request.user.is_data_scientist():
        messages.error(request, "Accès réservé.")
        return redirect("galerie")
    return render(request, "core/dashboard.html",
                  statistiques.indicateurs_client(request.user.client))


# ============================================================
# MODULE LOTS DE TRAVAIL (labélisation)
# ============================================================

@login_required
def batches(request):
    """Liste des lots de travail, cloisonnée par rôle."""
    if request.user.role == "CONTRIB":
        # Un contributeur voit uniquement les lots qui lui sont assignés
        # (l'assignation est le filtre le plus précis, indépendant du client).
        qs = Batch.objects.filter(assigne_a=request.user)
    else:
        # Data scientist / admin : les lots de leur boîte (cloisonnement client)
        qs = Batch.objects.filter(client=request.user.client)
    qs = qs.select_related("cree_par", "assigne_a")
    return render(request, "core/batches.html", {"batches": qs})


@login_required
def batch_creer(request):
    """Création d'un lot par le manager (data scientist / admin)."""
    if not request.user.is_data_scientist():
        messages.error(request, "Seuls les managers peuvent créer un lot.")
        return redirect("batches")

    if request.method == "POST":
        form = BatchCreationForm(request.POST, request.FILES,
                                 client=request.user.client,
                                 manager=request.user)
        if form.is_valid():
            zip_ref = form.cleaned_data["zip_reference"]
            # VALIDATION DÉFENSIVE du ZIP avant tout enregistrement :
            # 1) sécurité (taille, bombe ZIP, chemins), 2) structure métier.
            erreur = securite.valider_zip(zip_ref)
            if erreur:
                messages.error(request, f"ZIP refusé : {erreur}")
                return render(request, "core/batch_creer.html", {"form": form})
            ok, message, infos = batch_utils.analyser_zip_reference(zip_ref)
            if not ok:
                messages.error(request, f"ZIP refusé : {message}")
                return render(request, "core/batch_creer.html", {"form": form})

            zip_ref.seek(0)
            batch = Batch.objects.create(
                nom=form.cleaned_data["nom"],
                description=form.cleaned_data["description"],
                client=request.user.client,
                cree_par=request.user,
                assigne_a=form.cleaned_data["assigne_a"],
                zip_reference=zip_ref,
                nb_images=infos["nb_images"],
                statut=Batch.Statut.A_FAIRE,
            )
            logger.info("Lot %s créé par %s (%s images)", batch.pk,
                        request.user, infos["nb_images"])
            messages.success(request, f"Lot créé. {message}")
            return redirect("batch_detail", batch_id=batch.id)
    else:
        form = BatchCreationForm(client=request.user.client,
                                 manager=request.user)
    return render(request, "core/batch_creer.html", {"form": form})


def _lot_accessible(request, batch_id):
    batch = get_object_or_404(
        Batch.objects.select_related("cree_par", "assigne_a"), pk=batch_id)
    if not peut_voir_lot(request.user, batch):
        _refuser(request, f"lot {batch_id}")
    return batch


@login_required
def batch_detail(request, batch_id):
    """Détail d'un lot + soumission du travail par le contributeur."""
    batch = _lot_accessible(request, batch_id)

    # Le contributeur soumet son travail -> contrôle qualité automatique
    if request.method == "POST" and request.user == batch.assigne_a:
        form = BatchSoumissionForm(request.POST, request.FILES)
        if form.is_valid():
            zip_travail = form.cleaned_data["zip_travail"]
            erreur = securite.valider_zip(zip_travail)
            if erreur:
                messages.error(request, f"ZIP refusé : {erreur}")
                return redirect("batch_detail", batch_id=batch.id)
            cats = list(Category.objects.values_list("nom", flat=True))
            try:
                with batch.zip_reference.open("rb") as ref:
                    rapport, score = qualite.controler(
                        ref, zip_travail, categories_autorisees=cats)
            except Exception:  # noqa: BLE001 — fichier déposé non fiable
                logger.exception("Contrôle qualité impossible (lot %s)", batch.pk)
                messages.error(request,
                    "Le contrôle qualité a échoué : vérifiez que votre ZIP "
                    "contient un dossier labels/ avec des JSON LabelMe valides.")
                return redirect("batch_detail", batch_id=batch.id)

            zip_travail.seek(0)
            batch.zip_travail = zip_travail
            batch.rapport = rapport
            batch.score_qualite = score
            # Statut selon le score (seuil de validation : 70%)
            batch.statut = (Batch.Statut.VALIDE if score >= qualite.SEUIL_VALIDATION_LOT
                            else Batch.Statut.A_CORRIGER)
            batch.date_soumission = timezone.now()
            batch.save()
            logger.info("Lot %s soumis : score %s%%", batch.pk, score)
            messages.success(request,
                f"Travail analysé ! Score qualité : {score}%.")
            return redirect("batch_detail", batch_id=batch.id)
    else:
        form = BatchSoumissionForm()

    return render(request, "core/batch_detail.html",
                  {"batch": batch, "form": form})


@login_required
def batch_telecharger_images(request, batch_id):
    """Le contributeur télécharge les images à labéliser (sans les labels !)."""
    batch = _lot_accessible(request, batch_id)
    try:
        with batch.zip_reference.open("rb") as ref:
            contenu = batch_utils.construire_zip_pour_stagiaire(ref)
    except OSError:
        logger.exception("ZIP de référence illisible (lot %s)", batch.pk)
        messages.error(request, "Impossible de préparer le ZIP.")
        return redirect("batch_detail", batch_id=batch.id)

    if batch.statut == Batch.Statut.A_FAIRE:
        batch.statut = Batch.Statut.EN_COURS
        batch.save(update_fields=["statut"])

    JournalAcces.enregistrer(JournalAcces.Evenement.TELECHARGEMENT,
                             request=request, detail=f"images du lot {batch.pk}")
    resp = HttpResponse(contenu, content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="images_a_labeliser_{batch.id}.zip"'
    return resp


@login_required
def batch_telecharger_travail(request, batch_id):
    """
    Le data scientist (manager) télécharge le ZIP labélisé par le contributeur.
    Réservé aux data scientists de la boîte du lot.
    """
    batch = get_object_or_404(Batch, pk=batch_id)
    if not peut_gerer_lot(request.user, batch):
        _refuser(request, f"travail du lot {batch_id}")

    if not batch.zip_travail:
        messages.error(request, "Le contributeur n'a pas encore soumis son travail.")
        return redirect("batch_detail", batch_id=batch.id)

    try:
        fichier = batch.zip_travail.open("rb")
    except OSError:
        logger.exception("ZIP de travail illisible (lot %s)", batch.pk)
        messages.error(request, "Impossible de récupérer le fichier.")
        return redirect("batch_detail", batch_id=batch.id)

    JournalAcces.enregistrer(JournalAcces.Evenement.TELECHARGEMENT,
                             request=request, detail=f"travail du lot {batch.pk}")
    return FileResponse(fichier, as_attachment=True,
                        filename=f"travail_labelise_{batch.id}.zip",
                        content_type="application/zip")
