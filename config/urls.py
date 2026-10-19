"""
URLS.PY (projet) — Le routeur principal.
Branche : l'admin Django, l'authentification fournie par Django
(login/logout/changement de mot de passe), et notre app core.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("compte/", include("django.contrib.auth.urls")),
    path("", include("core.urls")),
]

# En développement, Django sert lui-même les images uploadées.
# En production, c'est le serveur web (Nginx) qui s'en charge.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
