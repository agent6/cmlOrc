import os
from pathlib import Path


def _csv_env(name: str, default=None):
    """Parse a comma-separated environment variable into a list.
    Trims whitespace and drops empty items.
    """
    raw = os.environ.get(name)
    if not raw:
        return [] if default is None else list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-secret-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
# Allow all hosts (wildcard). Note: not recommended for production
ALLOWED_HOSTS = ["*"]
# CSRF trusted origins (HTTPS origins only). Env overrides defaults below.
CSRF_TRUSTED_ORIGINS = _csv_env(
    "CSRF_TRUSTED_ORIGINS",
    [
        "https://cmlorc.myexam-prep.com",
    ],
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "orchestrator",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cmlorc.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "cmlorc.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TZ", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

# Serve static files in production via WhiteNoise (when DEBUG=0)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

WHITENOISE_KEEP_ONLY_HASHED_FILES = True

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# Background worker guard to avoid duplicate threads (default OFF).
# Enable explicitly with RUN_BACKGROUND_WORKER=1 or when using runserver.
RUN_BACKGROUND_WORKER = os.environ.get("RUN_BACKGROUND_WORKER", "0") == "1"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Basic logging to console (DEBUG for orchestrator)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "orchestrator": {"handlers": ["console"], "level": "DEBUG", "propagate": True},
    },
}

# Health check interval (seconds)
HEALTH_CHECK_INTERVAL = int(os.environ.get("HEALTH_CHECK_INTERVAL", "30"))
# Scheduler tick (seconds) for the background worker loop; should be <= 5 to allow fast rechecks
HEALTH_SCHEDULER_TICK = int(os.environ.get("HEALTH_SCHEDULER_TICK", "1"))
# Health check HTTP timeout (seconds)
HEALTH_CHECK_HTTP_TIMEOUT = int(os.environ.get("HEALTH_CHECK_HTTP_TIMEOUT", "12"))
# Backoff after failures (seconds). Next delay = min(max, base * 2^failures)
HEALTH_CHECK_BACKOFF_BASE = int(os.environ.get("HEALTH_CHECK_BACKOFF_BASE", "15"))
HEALTH_CHECK_BACKOFF_MAX = int(os.environ.get("HEALTH_CHECK_BACKOFF_MAX", "300"))

# Import/upload HTTP timeout (seconds) for lab YAML pushes
IMPORT_HTTP_TIMEOUT = int(os.environ.get("IMPORT_HTTP_TIMEOUT", "8"))
