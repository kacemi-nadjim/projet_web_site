"""
SETTINGS.PY — Configuration du projet PixBank.

Principe (V2) : le code est identique en développement et en production ;
seules les VARIABLES D'ENVIRONNEMENT changent (méthode « 12-factor app »).

Variables reconnues :
  DJANGO_DEBUG          "True" uniquement en local (manage.py le fait pour vous).
                        Par défaut : False -> un oubli ne peut plus exposer
                        les traces d'erreur en production.
  DJANGO_SECRET_KEY     clé secrète, OBLIGATOIRE dès que DEBUG est False.
  DJANGO_ALLOWED_HOSTS  domaines autorisés, séparés par des virgules.
  DATABASE_URL          base de données, ex. postgres://user:mdp@hote:5432/pixbank
                        (absente -> SQLite local, pratique en développement).
  DJANGO_ADMINS         "Nom:email" séparés par des virgules -> reçoivent un
                        e-mail à chaque erreur 500 (supervision).
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from . import __version__

BASE_DIR = Path(__file__).resolve().parent.parent

PIXBANK_VERSION = __version__

# ------------------------------------------------------------
# SÉCURITÉ DE BASE
# ------------------------------------------------------------
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        # Clé de développement uniquement : jamais utilisée en production,
        # car le site refuse de démarrer sans vraie clé quand DEBUG=False.
        SECRET_KEY = "dev-only-pixbank-cle-locale-non-secrete-0123456789abcdef"  # noqa: S105  # nosec B105
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY doit être défini en production "
            "(voir le modèle .env.exemple).")

ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

ADMINS = [tuple(a.split(":", 1)) for a in
          os.environ.get("DJANGO_ADMINS", "").split(",") if ":" in a]

# Envoi des alertes d'erreur par e-mail (serveur SMTP défini dans .env).
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", "pixbank@localhost")
EMAIL_SUBJECT_PREFIX = "[PixBank] "

# Durcissement automatique en production (DEBUG désactivé).
if not DEBUG:
    SECURE_SSL_REDIRECT = True          # force le HTTPS
    SESSION_COOKIE_SECURE = True        # cookie de session en HTTPS uniquement
    CSRF_COOKIE_SECURE = True           # cookie CSRF en HTTPS uniquement
    SECURE_HSTS_SECONDS = 31536000      # HSTS : impose HTTPS pendant 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Derrière le serveur intermédiaire de l'hébergeur (PythonAnywhere), le
    # HTTPS est signalé par cet en-tête : évite une boucle de redirections.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# En-têtes valables partout (dev et prod).
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
# Le jeton CSRF n'est lu par aucun script : cookie inaccessible au JavaScript
# (alerte « Cookie No HttpOnly Flag » du scan OWASP ZAP corrigée).
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 8 * 3600           # session de 8 h (une journée de travail)

# ------------------------------------------------------------
# APPLICATIONS
# ------------------------------------------------------------
INSTALLED_APPS = [
    "core",  # notre application métier
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.EnTetesSecuriteMiddleware",   # CSP + Permissions-Policy
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.version",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ------------------------------------------------------------
# BASE DE DONNÉES
# PostgreSQL en production via DATABASE_URL ; SQLite en local si absente.
# conn_max_age : réutilise la connexion entre requêtes (moins de latence).
# ------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------
# FICHIERS STATIQUES ET MÉDIAS
# ------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"      # cible de collectstatic (prod)

# Les médias (photos, ZIP de lots) ne sont JAMAIS servis directement :
# ils passent par des vues Django qui vérifient la connexion et le
# cloisonnement client (voir core/views.py : image_fichier).
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "core.User"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "galerie"
LOGOUT_REDIRECT_URL = "home"

# ------------------------------------------------------------
# LIMITES DE SÉCURITÉ SUR LES FICHIERS DÉPOSÉS
# ------------------------------------------------------------
PIXBANK_IMAGE_TAILLE_MAX = 15 * 1024 * 1024       # 15 Mo par image
PIXBANK_IMAGE_FORMATS = ("JPEG", "PNG", "WEBP", "BMP")
PIXBANK_ZIP_TAILLE_MAX = 200 * 1024 * 1024        # 200 Mo par ZIP déposé
PIXBANK_ZIP_DECOMPRESSE_MAX = 600 * 1024 * 1024   # anti « bombe ZIP »
PIXBANK_ZIP_NB_FICHIERS_MAX = 5000
DATA_UPLOAD_MAX_NUMBER_FILES = 100                # images par dépôt

# Éco-conception : miniatures affichées dans la galerie à la place des
# originaux (plusieurs Mo) -> poids de page divisé, moins de bande passante.
PIXBANK_MINIATURE_TAILLE = 480                    # plus grand côté, en pixels
PIXBANK_MINIATURE_QUALITE = 72                    # qualité WebP
PIXBANK_IMAGES_PAR_PAGE = 24

# Protection contre les attaques par force brute sur la connexion.
PIXBANK_CONNEXION_ESSAIS_MAX = 5
PIXBANK_CONNEXION_FENETRE_MINUTES = 15

# Durée de conservation du journal d'accès (RGPD : minimisation).
PIXBANK_JOURNAL_CONSERVATION_JOURS = 180

# ------------------------------------------------------------
# JOURNALISATION (supervision et diagnostic des incidents)
# ------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} [{levelname}] {name} : {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
        "fichier": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "pixbank.log",
            "maxBytes": 2 * 1024 * 1024,     # 2 Mo par fichier
            "backupCount": 5,                # 5 fichiers conservés
            "formatter": "standard",
            "encoding": "utf-8",
        },
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
        },
    },
    "loggers": {
        "django": {"handlers": ["console", "fichier"], "level": "WARNING"},
        "django.request": {
            "handlers": ["fichier", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["fichier", "mail_admins"],
            "level": "WARNING",
            "propagate": False,
        },
        "pixbank": {"handlers": ["fichier"], "level": "INFO"},
    },
}

# Lanceur de tests (médias temporaires, hachage rapide)
TEST_RUNNER = "core.tests.runner.PixbankTestRunner"
