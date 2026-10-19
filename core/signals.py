"""
SIGNALS.PY — Alimentation automatique du journal d'accès.

Django émet un « signal » à chaque connexion, déconnexion et échec de
connexion ; on y branche l'écriture dans le journal. Ainsi aucune vue
n'a besoin d'y penser, et rien ne peut être oublié.
"""

import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import JournalAcces

logger = logging.getLogger("pixbank.securite")


@receiver(user_logged_in)
def connexion_reussie(sender, request, user, **kwargs):
    JournalAcces.enregistrer(JournalAcces.Evenement.CONNEXION_OK,
                             request=request, utilisateur=user)


@receiver(user_logged_out)
def deconnexion(sender, request, user, **kwargs):
    if user is not None:
        JournalAcces.enregistrer(JournalAcces.Evenement.DECONNEXION,
                                 request=request, utilisateur=user)


@receiver(user_login_failed)
def connexion_echouee(sender, credentials, request=None, **kwargs):
    identifiant = credentials.get("username", "")
    logger.warning("Échec de connexion pour « %s »", identifiant)
    JournalAcces.enregistrer(JournalAcces.Evenement.CONNEXION_ECHEC,
                             request=request, identifiant=identifiant)
