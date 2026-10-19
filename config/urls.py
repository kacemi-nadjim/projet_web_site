"""
URLS.PY (projet) — Le routeur principal.
Branche : l'admin Django, l'authentification (avec protection anti force
brute), l'accès protégé aux fichiers déposés, et notre app core.
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.templatetags.static import static
from django.urls import include, path
from django.views.generic import RedirectView

from core import views
from core.forms import FormulaireConnexion, FormulaireConnexionAdmin

# Le back-office utilise le même anti force brute que le site.
admin.site.login_form = FormulaireConnexionAdmin
admin.site.site_header = "PixBank — Back-office"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("compte/login/",
         auth_views.LoginView.as_view(authentication_form=FormulaireConnexion),
         name="login"),
    path("compte/", include("django.contrib.auth.urls")),
    # Les fichiers déposés ne sont JAMAIS servis directement : ils passent
    # par une vue qui vérifie la connexion et le cloisonnement client.
    path("media/<path:chemin>", views.media_protege, name="media_protege"),
    path("sante/", views.sante, name="sante"),
    # Les navigateurs demandent /favicon.ico (le back-office ne déclare pas
    # d'icône) : on redirige vers l'icône du site au lieu d'une erreur 404.
    path("favicon.ico", RedirectView.as_view(url=static("favicon.svg"), permanent=True)),
    path("", include("core.urls")),
]
