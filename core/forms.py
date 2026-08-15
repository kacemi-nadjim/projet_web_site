"""
FORMS.PY — Validation des données côté serveur.
Règle d'or : ne jamais faire confiance aux saisies utilisateur.
"""

from django import forms
from .models import Category


class MultiFileInput(forms.ClearableFileInput):
    """Widget HTML autorisant la sélection de plusieurs fichiers."""
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    """
    Champ qui valide CHAQUE fichier d'une sélection multiple.
    Le FileField standard de Django ne valide que le premier ;
    on surcharge clean() pour traiter toute la liste.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultiFileInput(attrs={"multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data]
        return [single(data, initial)]


class ImageUploadForm(forms.Form):
    """Formulaire de dépôt : upload multiple + multi-catégories + RGPD."""
    fichiers = MultiFileField(label="Images à déposer (plusieurs possibles)")
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Catégories présentes dans les images")
    consentement = forms.BooleanField(
        required=False,
        label="Je certifie disposer du consentement / d'une base légale "
              "pour les données personnelles (RGPD)")

    def clean(self):
        data = super().clean()
        categories = data.get("categories")
        consentement = data.get("consentement")
        if categories:
            sensible = any(c.donnee_personnelle for c in categories)
            if sensible and not consentement:
                raise forms.ValidationError(
                    "Une catégorie sélectionnée contient des données "
                    "personnelles : vous devez certifier le consentement (RGPD).")
        return data


class ContactForm(forms.Form):
    """Formulaire de contact avec consentement RGPD et anti-spam simple."""
    nom = forms.CharField(max_length=100, label="Nom")
    email = forms.EmailField(label="E-mail")
    message = forms.CharField(widget=forms.Textarea, label="Message")
    consentement = forms.BooleanField(
        label="J'accepte que mes données soient utilisées pour traiter "
              "ma demande (voir politique de confidentialité)")
    # Champ "honeypot" : invisible pour les humains, rempli par les bots.
    # S'il est rempli, on rejette silencieusement (anti-spam sans captcha intrusif).
    site_web = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_site_web(self):
        if self.cleaned_data.get("site_web"):
            raise forms.ValidationError("Spam détecté.")
        return ""


class DemandeInscriptionForm(forms.ModelForm):
    """Formulaire public de demande d'accès contributeur."""
    class Meta:
        from .models import DemandeInscription
        model = DemandeInscription
        fields = ["nom", "email", "entreprise_souhaitee", "motivation"]
        labels = {
            "nom": "Votre nom complet",
            "email": "Votre e-mail professionnel",
            "entreprise_souhaitee": "Votre entreprise",
            "motivation": "Pourquoi souhaitez-vous déposer des images ?",
        }
        widgets = {
            "motivation": forms.Textarea(attrs={"rows": 4}),
        }

    # Consentement RGPD obligatoire (traitement des données du demandeur)
    consentement_rgpd = forms.BooleanField(
        required=True,
        label="J'accepte que mes données (nom, e-mail) soient traitées pour "
              "l'étude de ma demande, conformément au RGPD.",
        error_messages={"required": "Vous devez accepter le traitement de vos "
                        "données pour envoyer la demande (RGPD)."},
    )

    # Anti-spam honeypot (champ invisible rempli par les bots)
    site_web = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_site_web(self):
        if self.cleaned_data.get("site_web"):
            raise forms.ValidationError("Spam détecté.")
        return ""


class BatchCreationForm(forms.Form):
    """Création d'un lot par le manager : dépôt du ZIP de référence."""
    nom = forms.CharField(max_length=120, label="Nom du lot")
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False,
        label="Description / consignes pour le stagiaire")
    zip_reference = forms.FileField(
        label="ZIP de référence (sous-dossiers images/ et labels/)")
    assigne_a = forms.ModelChoiceField(
        queryset=None, required=False,
        label="Assigner à (stagiaire)")

    def __init__(self, *args, client=None, manager=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Un data scientist ne peut assigner qu'aux contributeurs qu'il encadre
        # (dont il est le manager). On complète par le cloisonnement client.
        from .models import User
        qs = User.objects.filter(role="CONTRIB")
        if manager is not None:
            # Contributeurs rattachés à ce data scientist OU à sa boîte
            from django.db.models import Q
            cond = Q(manager=manager)
            if client:
                cond = cond | Q(client=client)
            qs = qs.filter(cond)
        elif client:
            qs = qs.filter(client=client)
        self.fields["assigne_a"].queryset = qs.distinct()


class BatchSoumissionForm(forms.Form):
    """Soumission du travail par le stagiaire : son ZIP labélisé."""
    zip_travail = forms.FileField(
        label="Votre ZIP de travail (vos fichiers labels/ au format LabelMe)")
