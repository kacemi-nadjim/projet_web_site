"""
VIEWS.PY — La logique métier (architecture MVT de Django).

Deux règles de sécurité systématiques dans chaque vue :
1. @login_required : pas connecté = pas d'accès
2. Cloisonnement : on ne montre QUE les données du client connecté
"""

import csv
import io
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ContactForm, DemandeInscriptionForm, ImageUploadForm
from .models import Category, Export, Image, MessageContact, calculer_hash


def home(request):
    return render(request, "core/home.html")


def contact(request):
    """Page contact avec formulaire + case consentement RGPD.

    Le message est enregistré en base (modèle MessageContact) pour que
    l'administrateur puisse le consulter depuis le back-office."""
    envoye = False
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            # Enregistrement du message : l'admin le retrouvera dans le
            # back-office (menu « Messages de contact »).
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

    categorie_id = request.GET.get("categorie")
    if categorie_id:
        images = images.filter(categories__id=categorie_id)
    statut = request.GET.get("statut")
    if statut:
        images = images.filter(statut=statut)

    context = {
        "images": images.distinct()[:60],
        "categories": Category.objects.all(),
        "filtre_categorie": categorie_id or "",
        "filtre_statut": statut or "",
        "total": images.distinct().count(),
    }
    return render(request, "core/galerie.html", context)


@login_required
def upload(request):
    if request.method == "POST":
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            fichiers = request.FILES.getlist("fichiers")
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
                image = Image(fichier=f, client=request.user.client,
                              uploaded_by=request.user, consentement=consentement,
                              hash_fichier=empreinte, statut=Image.Statut.EN_ATTENTE)
                image.save()
                image.categories.set(categories)
                deposees += 1
            if deposees:
                messages.success(request, f"{deposees} image(s) déposée(s), en attente de validation.")
            if doublons:
                messages.warning(request, f"{doublons} image(s) ignorée(s) : déjà présentes (doublon).")
            return redirect("galerie")
    else:
        form = ImageUploadForm()
    return render(request, "core/upload.html", {"form": form})


@login_required
def supprimer_image(request, image_id):
    image = get_object_or_404(Image, pk=image_id, client=request.user.client)
    if image.uploaded_by != request.user and not request.user.is_admin_metier():
        messages.error(request, "Vous ne pouvez supprimer que vos images.")
        return redirect("galerie")
    if request.method == "POST":
        image.is_deleted = True
        image.deleted_at = timezone.now()
        image.save()
        messages.success(request, "Image supprimée.")
    return redirect("galerie")


@login_required
def exporter(request):
    """EXPORT ZIP + CSV — la brique ETL (Extract → Transform → Load)."""
    if not request.user.is_data_scientist():
        messages.error(request, "Seuls les data scientists peuvent exporter.")
        return redirect("galerie")

    images = _images_du_client(request.user).filter(statut=Image.Statut.VALIDEE)
    categorie_id = request.GET.get("categorie")
    libelle_filtre = "toutes catégories"
    if categorie_id:
        images = images.filter(categories__id=categorie_id).distinct()
        cat = Category.objects.filter(id=categorie_id).first()
        libelle_filtre = cat.nom if cat else libelle_filtre

    if not images.exists():
        messages.warning(request, "Aucune image validée à exporter pour ce filtre.")
        return redirect("galerie")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["nom_fichier", "categories", "largeur", "hauteur",
                         "date_upload", "donnee_personnelle"])
        for img in images:
            nom = img.fichier.name.split("/")[-1]
            writer.writerow([nom, img.labels(), img.largeur, img.hauteur,
                             img.date_upload.strftime("%Y-%m-%d"),
                             "oui" if img.contient_donnee_perso() else "non"])
        zf.writestr("annotations.csv", csv_buffer.getvalue())
        for img in images:
            try:
                img.fichier.open("rb")
                nom = img.fichier.name.split("/")[-1]
                zf.writestr(f"images/{nom}", img.fichier.read())
                img.fichier.close()
            except Exception:
                continue

    Export.objects.create(user=request.user, client=request.user.client,
                          nb_images=images.count(), filtre_applique=libelle_filtre)
    buffer.seek(0)
    horodatage = timezone.now().strftime("%Y%m%d_%H%M")
    nom_zip = f"dataset_{request.user.client.nom}_{horodatage}.zip"
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{nom_zip}"'
    return response


@login_required
def dashboard(request):
    """DASHBOARD BI — statistiques cloisonnées par client."""
    if not request.user.is_data_scientist():
        messages.error(request, "Accès réservé.")
        return redirect("galerie")

    images = Image.objects.filter(client=request.user.client, is_deleted=False)
    par_categorie = (Category.objects
                     .filter(images__client=request.user.client, images__is_deleted=False)
                     .annotate(n=Count("images")).order_by("-n"))
    max_cat = par_categorie[0].n if par_categorie else 1
    stats_statut = images.aggregate(
        total=Count("id"),
        validees=Count("id", filter=Q(statut="VALIDEE")),
        attente=Count("id", filter=Q(statut="ATTENTE")),
        refusees=Count("id", filter=Q(statut="REFUSEE")))
    total = stats_statut["total"] or 1
    taux_validation = round(100 * stats_statut["validees"] / total)
    nb_dp = images.filter(categories__donnee_personnelle=True).distinct().count()
    context = {
        "stats": stats_statut, "taux_validation": taux_validation,
        "par_categorie": par_categorie, "max_cat": max_cat,
        "nb_donnees_perso": nb_dp,
        "nb_contributeurs": images.values("uploaded_by").distinct().count(),
        "exports": Export.objects.filter(client=request.user.client)[:10],
    }
    return render(request, "core/dashboard.html", context)


# ============================================================
# MODULE LOTS DE TRAVAIL (labélisation) — Étape A : le tuyau
# ============================================================

from django.http import HttpResponse as _Http
from .forms import BatchCreationForm, BatchSoumissionForm
from .models import Batch
from . import batch_utils, qualite


@login_required
def batches(request):
    """Liste des lots de travail, cloisonnée par rôle."""
    if request.user.role == "CONTRIB":
        # Un contributeur voit uniquement les lots qui lui sont assignés
        # (l'assignation est le filtre le plus précis, indépendant du client).
        qs = Batch.objects.filter(assigne_a=request.user).select_related(
            "cree_par", "assigne_a")
    else:
        # Data scientist / admin : les lots de leur boîte (cloisonnement client)
        qs = Batch.objects.filter(client=request.user.client).select_related(
            "cree_par", "assigne_a")
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
            # VALIDATION DÉFENSIVE du ZIP avant tout enregistrement
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
            messages.success(request, f"Lot créé. {message}")
            return redirect("batch_detail", batch_id=batch.id)
    else:
        form = BatchCreationForm(client=request.user.client,
                                 manager=request.user)
    return render(request, "core/batch_creer.html", {"form": form})


@login_required
def batch_detail(request, batch_id):
    """Détail d'un lot + soumission du travail par le stagiaire."""
    batch = get_object_or_404(Batch, pk=batch_id)
    # Accès autorisé : membre de la boîte du lot, OU contributeur assigné au lot
    if batch.client != request.user.client and batch.assigne_a != request.user:
        from django.http import Http404
        raise Http404("Lot introuvable")

    # Le stagiaire soumet son travail -> contrôle qualité automatique
    if request.method == "POST" and request.user == batch.assigne_a:
        form = BatchSoumissionForm(request.POST, request.FILES)
        if form.is_valid():
            zip_travail = form.cleaned_data["zip_travail"]
            # Catégories autorisées = celles du client
            cats = list(Category.objects.values_list("nom", flat=True))
            try:
                batch.zip_reference.open("rb")
                rapport, score = qualite.controler(
                    batch.zip_reference, zip_travail,
                    categories_autorisees=cats)
                batch.zip_reference.close()
            except Exception as e:
                messages.error(request,
                    "Le contrôle qualité a échoué : vérifiez que votre ZIP "
                    "contient un dossier labels/ avec des JSON LabelMe valides.")
                return redirect("batch_detail", batch_id=batch.id)

            zip_travail.seek(0)
            batch.zip_travail = zip_travail
            batch.rapport = rapport
            batch.score_qualite = score
            # Statut selon le score (seuil de validation : 70%)
            batch.statut = (Batch.Statut.VALIDE if score >= 70
                            else Batch.Statut.A_CORRIGER)
            batch.date_soumission = timezone.now()
            batch.save()
            messages.success(request,
                f"Travail analysé ! Score qualité : {score}%.")
            return redirect("batch_detail", batch_id=batch.id)
    else:
        form = BatchSoumissionForm()

    return render(request, "core/batch_detail.html",
                  {"batch": batch, "form": form})


@login_required
def batch_telecharger_images(request, batch_id):
    """Le stagiaire télécharge les images à labéliser (sans les labels !)."""
    batch = get_object_or_404(Batch, pk=batch_id)
    # Accès autorisé : membre de la boîte du lot, OU contributeur assigné
    if batch.client != request.user.client and batch.assigne_a != request.user:
        from django.http import Http404
        raise Http404("Lot introuvable")
    try:
        batch.zip_reference.open("rb")
        contenu = batch_utils.construire_zip_pour_stagiaire(batch.zip_reference)
        batch.zip_reference.close()
    except Exception:
        messages.error(request, "Impossible de préparer le ZIP.")
        return redirect("batch_detail", batch_id=batch.id)

    if batch.statut == Batch.Statut.A_FAIRE:
        batch.statut = Batch.Statut.EN_COURS
        batch.save()

    resp = _Http(contenu, content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="images_a_labeliser_{batch.id}.zip"'
    return resp


@login_required
def batch_telecharger_travail(request, batch_id):
    """
    Le data scientist (manager) télécharge le ZIP labélisé par le contributeur.
    Réservé aux data scientists de la boîte du lot.
    """
    from django.http import Http404
    batch = get_object_or_404(Batch, pk=batch_id)

    # Réservé au manager / data scientist de la boîte
    if not request.user.is_data_scientist() or batch.client != request.user.client:
        raise Http404("Lot introuvable")

    if not batch.zip_travail:
        messages.error(request, "Le contributeur n'a pas encore soumis son travail.")
        return redirect("batch_detail", batch_id=batch.id)

    try:
        batch.zip_travail.open("rb")
        contenu = batch.zip_travail.read()
        batch.zip_travail.close()
    except Exception:
        messages.error(request, "Impossible de récupérer le fichier.")
        return redirect("batch_detail", batch_id=batch.id)

    resp = _Http(contenu, content_type="application/zip")
    resp["Content-Disposition"] = (
        f'attachment; filename="travail_labelise_{batch.id}.zip"')
    return resp
