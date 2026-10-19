"""
Lanceur de tests PixBank : isole complètement les tests de l'environnement
réel.
  - MEDIA_ROOT temporaire : les tests n'écrivent plus de fichiers dans le
    vrai dossier media/ (anomalie ANO-007 : des fichiers t_*.jpg laissés
    par les tests de la v1.0 y traînaient) ;
  - hachage de mot de passe rapide (MD5) : réservé aux tests, il divise
    leur durée sans rien changer à la logique testée ;
  - journaux applicatifs neutralisés pendant les tests.
"""

import logging
import shutil
import tempfile

from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class PixbankTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media = tempfile.mkdtemp(prefix="pixbank_tests_media_")
        self._override = override_settings(
            MEDIA_ROOT=self._media,
            PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        )
        self._override.enable()
        for nom in ("pixbank", "django.security", "django.request"):
            journal = logging.getLogger(nom)
            self.__dict__.setdefault("_handlers", {})[nom] = journal.handlers
            journal.handlers = [logging.NullHandler()]

    def teardown_test_environment(self, **kwargs):
        for nom, handlers in self.__dict__.get("_handlers", {}).items():
            logging.getLogger(nom).handlers = handlers
        self._override.disable()
        shutil.rmtree(self._media, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
