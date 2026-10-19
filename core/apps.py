from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Branche les signaux du journal d'accès (connexions, échecs...).
        from . import signals  # noqa: F401
