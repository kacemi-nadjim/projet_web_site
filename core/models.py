"""
MODELS.PY — Le cœur de l'application : la traduction du MCD en code.

Chaque classe = une table dans la base de données.
Django génère le SQL automatiquement via les migrations (ORM).

ÉVOLUTIONS v2 :
- Image <-> Category devient du multi-catégories (table de liaison)
  -> une photo de rue peut contenir un visage ET une plaque ET une voiture
- Ajout d'un hash (empreinte) pour détecter les doublons à l'upload
- L'Export enregistre désormais le détail de ce qui a été téléchargé

ÉVOLUTIONS v1.1 (rattrapage) :
- Index composites alignés sur les requêtes réelles (galerie, export,
  dashboard) -> mesures avant/après : outils/benchmark_bdd.py
- Contrainte d'unicité PARTIELLE : l'anti-doublon est garanti par la base
  elle-même, pas seulement par le code (résiste aux dépôts simultanés)
- Contrainte CHECK sur le score qualité (toujours entre 0 et 100)
- Miniature WebP générée à l'upload (éco-conception de la galerie)
- Journal d'accès (connexions, échecs, exports, téléchargements)
"""

import hashlib
import logging

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q

logger = logging.getLogger("pixbank.models")


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
    # Version allégée (WebP, 480 px max) affichée dans la galerie.
    # Les métadonnées EXIF (dont la position GPS) n'y sont pas recopiées.
    miniature = models.ImageField(upload_to="miniatures/%Y/%m/",
                                  null=True, blank=True, editable=False)

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
    # (v1.1) Plus d'index simple sur ce champ : l'index unique partiel
    # « image_unique_par_client » sert à la fois de garde-fou et d'index de
    # recherche pour l'anti-doublon. Sous PostgreSQL, l'ancien index en créait
    # en réalité deux (dont un pour les recherches LIKE, jamais utilisées).
    hash_fichier = models.CharField(max_length=64, blank=True)

    date_upload = models.DateTimeField(auto_now_add=True)

    # Soft delete (cours BDD étape 3) : on masque, on ne détruit pas.
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_upload"]
        indexes = [
            # Index PARTIELS (WHERE NOT is_deleted) : Django traduit le filtre
            # is_deleted=False par « NOT is_deleted », condition qu'un index
            # composite classique ne sait pas exploiter. Un index partiel ne
            # contient que les images actives : il correspond exactement aux
            # requêtes de l'application et il est plus petit (moins de disque).
            #
            # Galerie : WHERE client=? AND NOT is_deleted ORDER BY date DESC
            # -> l'index fournit directement l'ordre, sans tri en mémoire.
            models.Index(fields=["client", "-date_upload"],
                         condition=Q(is_deleted=False),
                         name="image_galerie_idx"),
            # Export et dashboard : WHERE client=? AND NOT is_deleted
            # AND statut=?
            models.Index(fields=["client", "statut"],
                         condition=Q(is_deleted=False),
                         name="image_client_statut_idx"),
        ]
        constraints = [
            # Anti-doublon garanti par la base : une même empreinte ne peut
            # exister qu'une fois par client parmi les images non supprimées.
            # (index unique PARTIEL : les images supprimées ne comptent pas)
            # L'empreinte est toujours calculée à l'enregistrement (save) et
            # la migration 0006 a complété les anciennes lignes qui n'en
            # avaient pas.
            models.UniqueConstraint(
                fields=["client", "hash_fichier"],
                condition=Q(is_deleted=False),
                name="image_unique_par_client",
            ),
        ]

    def __str__(self):
        return f"{self.fichier.name}"

    def save(self, *args, **kwargs):
        if self.fichier and not self.largeur:
            try:
                self.largeur = self.fichier.width
                self.hauteur = self.fichier.height
            except (OSError, ValueError):
                logger.warning("Dimensions illisibles pour %s", self.fichier.name)
        if self.fichier and not self.hash_fichier:
            self.hash_fichier = calculer_hash(self.fichier)
        if self.fichier and not self.miniature:
            from .miniatures import creer_miniature
            contenu = creer_miniature(self.fichier)
            if contenu is not None:
                self.miniature.save(contenu.name, contenu, save=False)
        super().save(*args, **kwargs)

    def labels(self):
        """Liste lisible des catégories (pour les templates et le CSV)."""
        return ", ".join(c.nom for c in self.categories.all())

    def contient_donnee_perso(self):
        # On parcourt categories.all() plutôt que .filter() : si les
        # catégories ont été préchargées (prefetch_related), aucune requête
        # SQL supplémentaire n'est faite (corrige un problème N+1 de l'export).
        return any(c.donnee_personnelle for c in self.categories.all())


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
        indexes = [models.Index(fields=["client", "-date"],
                                name="export_client_date_idx")]

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
        constraints = [
            # Le score qualité est un pourcentage : la base refuse toute
            # valeur hors de [0 ; 100], même en cas de bug applicatif.
            models.CheckConstraint(
                condition=Q(score_qualite__isnull=True)
                | Q(score_qualite__gte=0, score_qualite__lte=100),
                name="batch_score_entre_0_et_100",
            ),
        ]

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


class JournalAcces(models.Model):
    """
    Journal de sécurité : qui s'est connecté, qui a échoué, qui a exporté
    ou téléchargé quoi. Sert à :
      - détecter les attaques (échecs répétés -> blocage temporaire) ;
      - enquêter après un incident (qui a accédé à quoi, quand) ;
      - prouver la traçabilité exigée par le RGPD.
    Conservation limitée (voir la commande purger_journal).
    """

    class Evenement(models.TextChoices):
        CONNEXION_OK = "CONNEXION_OK", "Connexion réussie"
        CONNEXION_ECHEC = "CONNEXION_ECHEC", "Échec de connexion"
        CONNEXION_BLOQUEE = "BLOQUEE", "Connexion bloquée (trop d'échecs)"
        DECONNEXION = "DECONNEXION", "Déconnexion"
        EXPORT = "EXPORT", "Export de dataset"
        TELECHARGEMENT = "TELECHARGEMENT", "Téléchargement de fichier"
        ACCES_REFUSE = "ACCES_REFUSE", "Accès refusé (hors périmètre)"

    date = models.DateTimeField(auto_now_add=True)
    evenement = models.CharField(max_length=20, choices=Evenement.choices)
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name="journal")
    identifiant = models.CharField(
        max_length=150, blank=True,
        help_text="Identifiant saisi (même s'il ne correspond à aucun compte).")
    ip = models.GenericIPAddressField(null=True, blank=True)
    detail = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Entrée du journal d'accès"
        verbose_name_plural = "Journal d'accès"
        ordering = ["-date"]
        indexes = [
            # Requête de l'anti force brute : échecs récents d'un identifiant.
            models.Index(fields=["identifiant", "evenement", "date"],
                         name="journal_tentatives_idx"),
            models.Index(fields=["date"], name="journal_date_idx"),
        ]

    def __str__(self):
        qui = self.utilisateur or self.identifiant or "anonyme"
        return f"{self.date:%d/%m/%Y %H:%M} — {self.get_evenement_display()} — {qui}"

    @classmethod
    def enregistrer(cls, evenement, request=None, utilisateur=None,
                    identifiant="", detail=""):
        """Raccourci utilisé par les vues et les signaux."""
        from .securite import ip_client

        if utilisateur is None and request is not None and \
                getattr(request, "user", None) is not None and \
                request.user.is_authenticated:
            utilisateur = request.user
        if not identifiant and utilisateur is not None:
            identifiant = utilisateur.get_username()
        return cls.objects.create(
            evenement=evenement, utilisateur=utilisateur,
            identifiant=identifiant[:150], ip=ip_client(request),
            detail=detail[:255])
