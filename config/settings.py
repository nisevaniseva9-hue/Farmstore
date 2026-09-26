"""
Django settings for the farmstore project.

Kept deliberately simple: one settings module, configured entirely through
environment variables (see .env.example). No settings/dev/prod split is
introduced unless the project actually needs one later.
"""

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# Python 3.14+ compatibility monkeypatch for Django 4.2 BaseContext.__copy__
# --------------------------------------------------------------------------
try:
    from django.template.context import BaseContext

    def _patched_basecontext_copy(self):
        cls = self.__class__
        obj = cls.__new__(cls)
        obj.__dict__ = self.__dict__.copy()
        obj.dicts = self.dicts[:]
        return obj

    BaseContext.__copy__ = _patched_basecontext_copy
except Exception:
    pass


# --------------------------------------------------------------------------
# Core / security
# --------------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="127.0.0.1,localhost,.onrender.com,.pythonanywhere.com",
    cast=Csv(),
)

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.catalog",
    "apps.inventory",
    "apps.orders",
    "apps.payments",
    "apps.notifications",
    # Phase 3+: "apps.inventory"
    # Phase 5+: "apps.orders"
    # Phase 8+: "apps.notifications"
    # Phase 7+: "apps.payments"
    # Phase 6+: "apps.delivery"
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Enable WhiteNoise for serving static files in production when available
try:
    import whitenoise  # noqa: F401
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
except ImportError:
    pass

ROOT_URLCONF = "config.urls"

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
                "config.context_processors.farm_info",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# Database configuration
# Supports:
# 1. DATABASE_URL (standard for Neon.tech, Render Postgres, Supabase, Koyeb)
# 2. Individual DB_* variables (PostgreSQL)
# 3. SQLite fallback (set DB_ENGINE=sqlite3)
# --------------------------------------------------------------------------
DATABASE_URL = config("DATABASE_URL", default="")
DB_ENGINE = config("DB_ENGINE", default="").lower()

if DATABASE_URL:
    try:
        import dj_database_url
        DATABASES = {
            "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, conn_health_checks=True)
        }
    except Exception:
        import urllib.parse
        parsed = urllib.parse.urlparse(DATABASE_URL)
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": parsed.path.lstrip("/"),
                "USER": parsed.username or "",
                "PASSWORD": parsed.password or "",
                "HOST": parsed.hostname or "127.0.0.1",
                "PORT": str(parsed.port or 5432),
                "CONN_MAX_AGE": 600,
                "CONN_HEALTH_CHECKS": True,
            }
        }
elif DB_ENGINE == "sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / config("DB_NAME", default="db.sqlite3"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="farmstore"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="127.0.0.1"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": 600,
            "CONN_HEALTH_CHECKS": True,
        }
    }

if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"].setdefault("CONN_MAX_AGE", 600)
    DATABASES["default"].setdefault("CONN_HEALTH_CHECKS", True)

# --------------------------------------------------------------------------
# Auth / custom user model
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.PhoneNumberBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Frictionless authentication: no complex password rules
AUTH_PASSWORD_VALIDATORS = []


LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# --------------------------------------------------------------------------
# Internationalization
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static & media files
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# File uploads (allow mobile camera photos up to 20MB)
# --------------------------------------------------------------------------
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB

# --------------------------------------------------------------------------
# In-memory caching for lightning fast catalog page loads
# --------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "farmstore-cache",
        "TIMEOUT": 300,
        "OPTIONS": {
            "MAX_ENTRIES": 1000,
        },
    }
}

# --------------------------------------------------------------------------
# Security hardening (mostly relevant once DEBUG=False in production)
# --------------------------------------------------------------------------
CSRF_COOKIE_HTTPONLY = True
# Permanent login: session cookie lasts 10 years, refreshes on every visit, persists on browser restart
SESSION_COOKIE_AGE = 315360000  # 10 years in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_REFERRER_POLICY = "same-origin"


CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://127.0.0.1,http://localhost,https://*.onrender.com,https://*.pythonanywhere.com",
    cast=Csv(),
)

if not DEBUG:
    # Nginx terminates TLS and forwards requests to Gunicorn over plain
    # HTTP on localhost; this tells Django to trust Nginx's
    # X-Forwarded-Proto header when deciding if a request was secure,
    # otherwise SECURE_SSL_REDIRECT would redirect-loop forever.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# --------------------------------------------------------------------------
# Farm-specific settings (used by the base template / homepage)
# --------------------------------------------------------------------------
FARM_NAME = config("FARM_NAME", default="Farm Fresh")
FARM_TAGLINE = config("FARM_TAGLINE", default="Fresh products directly from our farm.")

# --------------------------------------------------------------------------
# WhatsApp Notifications Configuration (Meta Cloud API, Twilio, or Console)
# Set WHATSAPP_PROVIDER to:
#   'console' (default: simulates sending, logs output, requires no purchase)
#   'meta'    (Meta WhatsApp Cloud API / Facebook Graph API)
#   'twilio'  (Twilio WhatsApp Messaging API)
# --------------------------------------------------------------------------
WHATSAPP_PROVIDER = config("WHATSAPP_PROVIDER", default="meta")
WHATSAPP_API_TOKEN = config("WHATSAPP_API_TOKEN", default="")
WHATSAPP_PHONE_NUMBER_ID = config("WHATSAPP_PHONE_NUMBER_ID", default="")
TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="")
TWILIO_WHATSAPP_FROM = config("TWILIO_WHATSAPP_FROM", default="")

# --------------------------------------------------------------------------
# Logging — errors go to a file, nothing sensitive is ever logged
# --------------------------------------------------------------------------
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "django.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
            "delay": True,
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
    },
}
