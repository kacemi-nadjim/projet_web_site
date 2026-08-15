"""
ADMIN.PY — Le back-office (offert par Django).
L'admin valide les dépôts, gère catégories, clients et utilisateurs.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from django.utils import timezone
from .models import (Batch, Category, Client, DemandeInscription, Export,
                     MessageContact,
                     Image, User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Rattachement métier", {"fields": ("role", "client", "manager")}),
    )
    # Champs métier disponibles dès la création d'un compte
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Rattachement métier", {
            "fields": ("email", "role", "client", "manager"),
            "description": "Pour une nouvelle boîte cliente : créez d'abord le "
                           "client (menu Clients), puis ici un Data Scientist "
                           "rattaché à ce client. Le champ manager ne sert que "
                           "pour les contributeurs.",
        }),
    )
    list_display = ("username", "email", "role", "client", "manager", "is_active")
    list_filter = ("role", "client")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("nom", "secteur", "date_creation")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("nom", "donnee_personnelle")
    list_filter = ("donnee_personnelle",)


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    """Écran de validation des dépôts : le workflow qualité."""
    list_display = ("__str__", "client", "uploaded_by", "statut",
                    "consentement", "date_upload", "is_deleted")
    list_filter = ("statut", "categories", "client", "is_deleted")
    filter_horizontal = ("categories",)
    actions = ["valider", "refuser"]

    @admin.action(description="Valider les images sélectionnées")
    def valider(self, request, queryset):
        n = queryset.update(statut=Image.Statut.VALIDEE)
        self.message_user(request, f"{n} image(s) validée(s).")

    @admin.action(description="Refuser les images sélectionnées")
    def refuser(self, request, queryset):
        n = queryset.update(statut=Image.Statut.REFUSEE)
        self.message_user(request, f"{n} image(s) refusée(s).")


@admin.register(Export)
class ExportAdmin(admin.ModelAdmin):
    list_display = ("user", "client", "date", "nb_images", "filtre_applique")
    list_filter = ("client",)


@admin.register(DemandeInscription)
class DemandeInscriptionAdmin(admin.ModelAdmin):
    """
    Modération des demandes d'accès. L'admin vérifie la demande puis,
    via l'action 'marquer approuvée', crée manuellement le compte
    (en choisissant le client réel dans l'écran Utilisateurs).
    """
    list_display = ("nom", "email", "entreprise_souhaitee", "statut",
                    "date_demande", "note_admin")
    list_filter = ("statut",)
    search_fields = ("nom", "email", "entreprise_souhaitee")
    actions = ["approuver_et_creer_compte", "marquer_refusee"]

    @admin.action(description="Approuver et créer le compte contributeur")
    def approuver_et_creer_compte(self, request, queryset):
        """
        Approuve les demandes et crée les comptes contributeurs.
        L'admin choisit d'abord le DATA SCIENTIST référent (le manager) sur une
        page intermédiaire. Le contributeur hérite du client de ce data scientist.
        """
        import secrets
        from django.shortcuts import render
        from django.http import HttpResponseRedirect
        from .models import User

        # Étape 2 : l'admin a validé le formulaire avec le data scientist choisi
        if request.POST.get("confirmer_rattachement"):
            ds_id = request.POST.get("data_scientist")
            manager = User.objects.filter(id=ds_id, role=User.Role.DATA_SCIENTIST).first()
            if not manager:
                self.message_user(request,
                    "Data scientist introuvable. Opération annulée.",
                    level="error")
                return HttpResponseRedirect(request.get_full_path())

            ids = request.POST.getlist("_selected_action")
            crees = []
            for demande in DemandeInscription.objects.filter(id__in=ids):
                if demande.statut == DemandeInscription.Statut.APPROUVEE:
                    continue
                base = demande.email.split("@")[0].lower()
                username, i = base, 1
                while User.objects.filter(username=username).exists():
                    i += 1; username = f"{base}{i}"
                mdp = secrets.token_urlsafe(9)
                # Le contributeur hérite du client de son manager (data scientist)
                user = User(username=username, email=demande.email,
                            role=User.Role.CONTRIBUTEUR,
                            client=manager.client, manager=manager)
                user.set_password(mdp)
                user.save()
                demande.statut = DemandeInscription.Statut.APPROUVEE
                demande.traitee_le = timezone.now()
                demande.note_admin = (f"Compte {username} · manager : "
                                      f"{manager.username}")
                demande.save()
                crees.append(f"{demande.nom} → identifiant : {username} · "
                             f"mot de passe : {mdp}")
            if crees:
                self.message_user(request,
                    f"Compte(s) créé(s), rattaché(s) à {manager.username} "
                    f"(client {manager.client.nom}). Identifiants à transmettre : "
                    + " | ".join(crees))
            return HttpResponseRedirect(request.get_full_path())

        # Étape 1 : afficher la page de choix du data scientist référent
        data_scientists = User.objects.filter(
            role=User.Role.DATA_SCIENTIST).select_related("client").order_by("client__nom")
        return render(request, "admin/rattacher_contributeur.html", {
            "demandes": queryset,
            "data_scientists": data_scientists,
            "action_name": "approuver_et_creer_compte",
        })

    @admin.action(description="Refuser les demandes sélectionnées")
    def marquer_refusee(self, request, queryset):
        n = queryset.update(statut=DemandeInscription.Statut.REFUSEE,
                            traitee_le=timezone.now())
        self.message_user(request, f"{n} demande(s) refusée(s).")


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("nom", "client", "assigne_a", "statut", "nb_images",
                    "score_qualite", "date_creation")
    list_filter = ("statut", "client")


@admin.register(MessageContact)
class MessageContactAdmin(admin.ModelAdmin):
    """Consultation des messages envoyés via le formulaire de contact."""
    list_display = ("nom", "email", "date_envoi", "traite")
    list_filter = ("traite", "date_envoi")
    search_fields = ("nom", "email", "message")
    readonly_fields = ("nom", "email", "message", "consentement", "date_envoi")
    list_editable = ("traite",)
    fields = ("nom", "email", "message", "consentement", "date_envoi", "traite")
