import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

load_dotenv(REPO_ROOT / ".env")


def env_required(name):
    value = os.environ.get(name)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def env_decimal_rate(name, default):
    """Read a sales-tax rate from the environment as a normalized Decimal.

    Whitespace is stripped and a blank value falls back to ``default``. The
    rate must parse as a Decimal in the inclusive range [0, 1]; anything else
    raises at startup so misconfiguration fails loudly rather than silently
    taxing customers at the wrong rate.
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return Decimal(default)
    raw = raw.strip()
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise RuntimeError(
            f"Invalid {name}: {raw!r} is not a valid decimal sales tax rate."
        ) from exc
    if value < Decimal("0") or value > Decimal("1"):
        raise RuntimeError(
            f"Invalid {name}: {value} must be between 0 and 1 (e.g. 0.0825 for 8.25%)."
        )
    return value


def env_bool(name):
    return env_required(name).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name):
    return [
        item.strip() for item in env_required(name).replace(" ", ",").split(",") if item.strip()
    ]


SECRET_KEY = env_required("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
SHOP_DISPLAY_NAME = os.environ.get("SHOP_DISPLAY_NAME", "Daniel's Paint and Body").strip()
if not SHOP_DISPLAY_NAME:
    SHOP_DISPLAY_NAME = "Daniel's Paint and Body"

# Combined Texas state/local sales tax rate, snapshotted onto estimates and
# invoices. Defaults to 8.25% until the shop verifies its exact rate via the
# Texas Comptroller Sales Tax Rate Locator. See ADR 0051 and app/core/tax.py.
SHOP_SALES_TAX_RATE = env_decimal_rate("SHOP_SALES_TAX_RATE", "0.0825")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "attachments",
    "communications",
    "customers",
    "vehicles",
    "repair_orders",
    "billing",
    "estimates",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
                "core.context_processors.shop_identity",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_required("POSTGRES_DB"),
        "USER": env_required("POSTGRES_USER"),
        "PASSWORD": env_required("POSTGRES_PASSWORD"),
        "HOST": env_required("POSTGRES_HOST"),
        "PORT": env_required("POSTGRES_PORT"),
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = os.environ.get("DJANGO_MEDIA_URL", "media/")
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", REPO_ROOT / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user model introduced before domain models so future models can
# reference staff users without an expensive AUTH_USER_MODEL swap later.
AUTH_USER_MODEL = "accounts.User"

# Auth flow routing. URL names are defined in accounts/urls.py and core/urls.py.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
