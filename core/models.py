"""
MODELS.PY — Le cœur de l'application : la traduction du MCD en code.

Chaque classe = une table dans la base de données.
Django génère le SQL automatiquement via les migrations (ORM).

ÉVOLUTIONS v2 :
- Image <-> Category devient du multi-catégories (table de liaison)
  -> une photo de rue peut contenir un visage ET une plaque ET une voiture
- Ajout d'un hash (empreinte) pour détecter les doublons à l'upload
- L'Export enregistre désormais le détail de ce qui a été téléchargé
"""

import hashlib

from django.contrib.auth.models import AbstractUser
from django.db import models


class Client(models.Model):
    """L'entreprise cliente. Clé du cloisonnement multi-clients."""
    nom = models.CharField(max_length=100, unique=True)
    secteur = models.CharField(max_length=100, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Client"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class User(AbstractUser):
    """
    Utilisateur personnalisé : on garde tout Django (mot de passe haché,
    sessions, permissions) et on ajoute le rôle + le client de rattachement.
    """

    class Role(models.TextChoices):
        CONTRIBUTEUR = "CONTRIB", "Contributeur"
        DATA_SCIENTIST = "DS", "Data Scientist"
        ADMIN = "ADMIN", "Administrateur"

    role = models.CharField(max_length=10, choices=Role.choices,
                            default=Role.CONTRIBUTEUR)
    client = models.ForeignKey(Client, on_delete=models.PROTECT,
                               null=True, blank=True,
                               related_name="utilisateurs")
    # Data scientist référent d'un contributeur (son manager).
    # Le contributeur hérite automatiquement du client de son manager.
    manager = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="contributeurs",
        limit_choices_to={"role": "DS"},
        help_text="Data scientist qui encadre ce contributeur "
                  "(uniquement pour les contributeurs).")

    def is_data_scientist(self):
        return self.role in (self.Role.DATA_SCIENTIST, self.Role.ADMIN)

    def is_admin_metier(self):
        return self.role == self.Role.ADMIN


class Category(models.Model):
    """
    Catégorie = label d'entraînement (visage, plaque, écran, animal...).
    Le drapeau donnee_personnelle déclenche l'exigence de consentement RGPD.
    """
    nom = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    donnee_personnelle = models.BooleanField(
        default=False,
        help_text="Cocher si la catégorie contient des données personnelles "
                  "au sens du RGPD (visages, plaques...).")

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Image(models.Model):
    """
    L'entité centrale : une image d'entraînement déposée par un
    contributeur, validée par un admin, exportable par les data scientists
    du même client.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "ATTENTE", "En attente de validation"
        VALIDEE = "VALIDEE", "Validée"
        REFUSEE = "REFUSEE", "Refusée"

    fichier = models.ImageField(upload_to="images/%Y/%m/")

    # MULTI-CATÉGORIES : une image peut porter plusieurs labels.
    # ManyToManyField crée automatiquement une table de liaison
    # (schéma relationnel avancé attendu par le jury).
    categories = models.ManyToManyField(Category, related_name="images")

    client = models.ForeignKey(Client, on_delete=models.CASCADE,
                               related_name="images")
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT,
                                    related_name="images_deposees")

    statut = models.CharField(max_length=10, choices=Statut.choices,
                              default=Statut.EN_ATTENTE)
    consentement = models.BooleanField(default=False)

    largeur = models.PositiveIntegerField(editable=False, null=True)
    hauteur = models.PositiveIntegerField(editable=False, null=True)

    # Empreinte du fichier : sert à détecter les doublons à l'upload.
    # Deux fichiers identiques produisent le même hash SHA-256.
    hash_fichier = models.CharField(max_length=64, blank=True, db_index=True)

    date_upload = models.DateTimeField(auto_now_add=True)

    # Soft delete (cours BDD étape 3) : on masque, on ne détruit pas.
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_upload"]

    def save(self, *args, **kwargs):
        if self.fichier and not self.largeur:
            try:
                self.largeur = self.fichier.width
                self.hauteur = self.fichier.height
            except Exception:
                pass
        super().save(*args, **kwargs)

    def labels(self):
        """Liste lisible des catégories (pour les templates et le CSV)."""
        return ", ".join(c.nom for c in self.categories.all())

    def contient_donnee_perso(self):
        return self.categories.filter(donnee_personnelle=True).exists()

    def __str__(self):
        return f"{self.fichier.name}"


def calculer_hash(fichier):
    """Calcule l'empreinte SHA-256 d'un fichier uploadé (anti-doublon)."""
    h = hashlib.sha256()
    for chunk in fichier.chunks():
        h.update(chunk)
    fichier.seek(0)  # on remet le curseur au début pour la sauvegarde
    return h.hexdigest()


class Export(models.Model):
    """
    Historique des téléchargements : qui a exporté quoi, quand.
    Traçabilité RGPD + matière première du dashboard BI.
    """
    user = models.ForeignKey(User, on_delete=models.PROTECT,
                             related_name="exports")
    client = models.ForeignKey(Client, on_delete=models.CASCADE,
                               related_name="exports", null=True)
    date = models.DateTimeField(auto_now_add=True)
    nb_images = models.PositiveIntegerField()
    filtre_applique = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user} — {self.nb_images} images le {self.date:%d/%m/%Y}"


class DemandeInscription(models.Model):
    """
    Demande d'accès déposée par un visiteur souhaitant devenir contributeur.
    L'inscription n'est JAMAIS automatique : un administrateur vérifie la
    légitimité de la demande, puis crée manuellement le compte en choisissant
    l'entreprise de rattachement. C'est le même principe de validation que
    pour les images — l'accès à des données sensibles ne peut pas être libre.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "ATTENTE", "En attente de traitement"
        APPROUVEE = "APPROUVEE", "Approuvée (compte créé)"
        REFUSEE = "REFUSEE", "Refusée"

    nom = models.CharField(max_length=100)
    email = models.EmailField()
    entreprise_souhaitee = models.CharField(
        max_length=120,
        help_text="Entreprise que le demandeur déclare. L'admin vérifie "
                  "et choisit le client réel au moment de créer le compte.")
    motivation = models.TextField(
        help_text="Pourquoi cette personne souhaite-t-elle déposer des images ?")
    statut = models.CharField(max_length=10, choices=Statut.choices,
                              default=Statut.EN_ATTENTE)
    date_demande = models.DateTimeField(auto_now_add=True)
    traitee_le = models.DateTimeField(null=True, blank=True)
    note_admin = models.CharField(
        max_length=200, blank=True,
        help_text="Note interne (ex : motif de refus, client attribué).")

    class Meta:
        verbose_name = "Demande d'inscription"
        verbose_name_plural = "Demandes d'inscription"
        ordering = ["-date_demande"]

    def __str__(self):
        return f"{self.nom} — {self.email} ({self.get_statut_display()})"


class Batch(models.Model):
    """
    Un LOT DE TRAVAIL de labélisation.

    Cycle de vie :
    1. Le manager dépose un ZIP de référence (images/ + labels/ vérité terrain)
    2. Le lot est assigné à un stagiaire (annotateur)
    3. Le stagiaire télécharge les images, les labélise sur LabelMe,
       puis redépose son ZIP de travail
    4. Le site vérifie la qualité (étape B)

    Ce module est cloisonné par client, comme le reste de la plateforme.
    """

    class Statut(models.TextChoices):
        A_FAIRE = "A_FAIRE", "À labéliser"
        EN_COURS = "EN_COURS", "En cours"
        SOUMIS = "SOUMIS", "Soumis (en attente de contrôle)"
        VALIDE = "VALIDE", "Validé"
        A_CORRIGER = "A_CORRIGER", "À corriger"

    nom = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE,
                               related_name="batches")

    # Le manager qui crée le lot et dépose la référence
    cree_par = models.ForeignKey(User, on_delete=models.PROTECT,
                                 related_name="batches_crees")
    # Le stagiaire chargé de labéliser
    assigne_a = models.ForeignKey(User, on_delete=models.SET_NULL,
                                  null=True, blank=True,
                                  related_name="batches_assignes")

    # Le ZIP de référence déposé par le manager (images + labels vérité terrain)
    zip_reference = models.FileField(upload_to="batches/reference/%Y/%m/")
    # Le ZIP de travail redéposé par le stagiaire
    zip_travail = models.FileField(upload_to="batches/travail/%Y/%m/",
                                   null=True, blank=True)

    nb_images = models.PositiveIntegerField(default=0)
    statut = models.CharField(max_length=12, choices=Statut.choices,
                              default=Statut.A_FAIRE)

    # Résultats du contrôle qualité (remplis à l'étape B)
    score_qualite = models.FloatField(null=True, blank=True)
    rapport = models.JSONField(null=True, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_soumission = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Lot de travail"
        verbose_name_plural = "Lots de travail"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.nom} ({self.get_statut_display()})"


class MessageContact(models.Model):
    """Message envoyé via le formulaire de contact public.

    Stocké en base pour que l'administrateur puisse le consulter et le
    traiter depuis le back-office (au lieu d'être perdu à l'envoi)."""
    nom = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    consentement = models.BooleanField(default=False)
    traite = models.BooleanField(
        default=False, verbose_name="Traité",
        help_text="Cocher une fois que le message a reçu une réponse.")
    date_envoi = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message de contact"
        verbose_name_plural = "Messages de contact"
        ordering = ["-date_envoi"]

    def __str__(self):
        return f"{self.nom} — {self.email} ({self.date_envoi:%d/%m/%Y})"
