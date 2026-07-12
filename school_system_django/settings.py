import os
from urllib.parse import urlparse
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def database_config():
    debug_mode = os.environ.get("DEBUG", "True").strip().lower() in ("true", "1", "yes")
    env_mode = os.environ.get("ENV", "").strip().lower()
    is_production = not debug_mode or env_mode == "production"

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if is_production and not database_url:
        raise ImproperlyConfigured("DATABASE_URL environment variable must be set in production. SQLite is not allowed in production.")

    if not database_url:
        sqlite_name = os.environ.get("SQLITE_NAME", "").strip()
        if sqlite_name:
            return {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": sqlite_name,
            }
        raise ImproperlyConfigured("DATABASE_URL environment variable is not set. The system must run on PostgreSQL.")
    parsed = urlparse(database_url)
    if parsed.scheme in {"postgres", "postgresql"}:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
            "CONN_MAX_AGE": 600,
        }
    raise ImproperlyConfigured("Unsupported DATABASE_URL scheme. The system must run on PostgreSQL.")


load_env_file()

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "local-development-only-change-this-key-before-production-2026",
)
DEBUG = env_bool("DEBUG", True)
SAAS_BASE_DOMAIN = os.environ.get("SAAS_BASE_DOMAIN", "raydonsystems.co.zw").strip().lower().rstrip(".")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost,.localhost,testserver")
if DEBUG:
    ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'students',
    'teachers',
    'fees',
    'finance',
    'academics',
    'attendance',
    'exams',
    'examinations',
    'reports',
    'settings_app',
    'parents',
    'staff',
    'portals',
    'website',
    'notifications',
    'payroll',
    'human_resources',
    'timetable',
    'academic_structure',
    'student_registry',
    'subject_management',
    'results_centre',
    'zimsec_analytics',
    'document_factory',
    'attendance_ledger',
    'timetable_engine',
    'exam_coordinator',
    'enterprise_communications',
    'fees_management',
    'accounting_erp',
    'procurement',
    'inventory_management',
    'medical',
    'saas_tenant_management',
    'library',
    'hostel',
    'transport',
    'assets',
    'discipline',
    'counselling',
    'system_administration',
    'business_intelligence',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'saas_tenant_management.middleware.TenantMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'school_system_django.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'django_templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.school_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'school_system_django.wsgi.application'


import sys
if 'test' in sys.argv or 'test_coverage' in sys.argv:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
else:
    DATABASES = {
        'default': database_config()
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'accounts.password_validation.LetterNumberPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = os.environ.get('TIME_ZONE', 'Africa/Harare')

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'uploads'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTHENTICATION_BACKENDS = [
    'accounts.backends.LegacyUserBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = '/django/staff/login/'
LOGIN_REDIRECT_URL = '/django/dashboard/'
LOGOUT_REDIRECT_URL = '/django/staff/login/'

SESSION_COOKIE_AGE = 60 * 60 * 2
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", False)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_TRUSTED_ORIGINS = [
    "https://raydonsystems.co.zw",
    "https://*.raydonsystems.co.zw",
    "https://raydonsystem.com",
    "https://*.raydonsystem.com",
    "http://raydonsystems.co.zw",
    "http://*.raydonsystems.co.zw",
    "http://raydonsystem.com",
    "http://*.raydonsystem.com",
    "http://localhost:8000",
    "http://localhost:8085",
    "http://127.0.0.1:8085",
]

extra_origins = env_list("CSRF_TRUSTED_ORIGINS", "")
for origin in extra_origins:
    if origin.strip():
        if not origin.startswith(("http://", "https://")):
            CSRF_TRUSTED_ORIGINS.append(f"https://{origin}")
            CSRF_TRUSTED_ORIGINS.append(f"http://{origin}")
        else:
            CSRF_TRUSTED_ORIGINS.append(origin)

SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)

TEST_RUNNER = 'school_system_django.test_runner.ManagedModelTestRunner'

import sys
if 'test' in sys.argv or 'test_coverage' in sys.argv:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"
    class DisableMigrations:
        def __contains__(self, item): return True
        def __getitem__(self, item): return None
    MIGRATION_MODULES = DisableMigrations()
