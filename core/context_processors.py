"""Variables disponibles dans tous les gabarits."""

from django.conf import settings


def version(request):
    """Numéro de version affiché en pied de page (traçabilité des mises à jour)."""
    return {"PIXBANK_VERSION": settings.PIXBANK_VERSION}
