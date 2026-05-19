

import importlib.util
import os
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent.parent


def _read_env_file(path):
    values = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _package_available(name):
    return importlib.util.find_spec(name) is not None


BOT_PROJECT_DIR = Path(
    os.environ.get(
        'BONFIRE_BOT_DIR',
        BASE_DIR.parent / 'bonfire-bot-main',
    )
)
BOT_ENV = _read_env_file(BOT_PROJECT_DIR / '.env')



_PROJECT_ENV = _read_env_file(BASE_DIR / '.env')
for _k, _v in _PROJECT_ENV.items():
    os.environ.setdefault(_k, _v)






SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    'django-insecure-x6%=xcc0x#6+#17z8-p+815+e-)&yy2q_*0u+q7wnsoa!845iw',
)


DEBUG = _env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]



INSTALLED_APPS = [
    'home.apps.HomeConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if _package_available("whitenoise"):
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

ROOT_URLCONF = 'bonfire.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'home.context_processors.user_profile',
            ],
        },
    },
]

WSGI_APPLICATION = 'bonfire.wsgi.application'





_db_engine = os.environ.get('DB_ENGINE', '').strip()
_postgres_url = os.environ.get('POSTGRES_URL', '').strip()

if _postgres_url:
    _parsed_db = urlparse(_postgres_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': (_parsed_db.path or '/postgres').lstrip('/'),
            'USER': _parsed_db.username or 'postgres',
            'PASSWORD': _parsed_db.password or '',
            'HOST': _parsed_db.hostname or 'localhost',
            'PORT': str(_parsed_db.port or 5432),
            'OPTIONS': {'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', '5'))},
        }
    }
elif _db_engine and _db_engine != 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': _db_engine,
            'NAME': os.environ.get('DB_NAME', 'postgres'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'OPTIONS': {'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', '5'))},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.environ.get('BONFIRE_SQLITE_PATH') or BASE_DIR / 'bonfas_classes.db',
        }
    }





AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]




LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True





STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

if _package_available("whitenoise"):
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "https://*.trycloudflare.com,https://donna-palm-contents-francisco.trycloudflare.com"
    ).split(",")
    if origin.strip()
]

SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SESSION_COOKIE_SECURE", SECURE_SSL_REDIRECT)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_CSRF_COOKIE_SECURE", SECURE_SSL_REDIRECT)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)

if _env_bool("DJANGO_USE_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGIN_REDIRECT_URL = '/'

BOT_MONGO_COLLECTIONS = {
    'quests': os.environ.get('BOT_MONGO_QUESTS_COLLECTION', 'rpg_quests'),
    'items': os.environ.get('BOT_MONGO_ITEMS_COLLECTION', 'rpg_items'),
    'dedicated_ranks': os.environ.get('BOT_MONGO_DEDICATED_RANKS_COLLECTION', 'dedicated-ranks'),
    'jobs': os.environ.get('BOT_MONGO_JOBS_COLLECTION', 'discord_jobs'),
    'store': os.environ.get('BOT_MONGO_STORE_COLLECTION', 'discord_bot_store'),
    'spells': os.environ.get('BOT_MONGO_SPELLS_COLLECTION', 'spells'),
    'backgrounds': os.environ.get('BOT_MONGO_BACKGROUNDS_COLLECTION', 'backgrounds'),
    'bestiary': os.environ.get('BOT_MONGO_BESTIARY_COLLECTION', 'bestiary'),
    'organizations': os.environ.get('BOT_MONGO_ORGANIZATIONS_COLLECTION', 'organizations'),
}
SITE_MONGO_COLLECTIONS = {
    'classes': os.environ.get('SITE_MONGO_CLASSES_COLLECTION', 'site_sqlite_TB_Classe'),
    'subclasses': os.environ.get('SITE_MONGO_SUBCLASSES_COLLECTION', 'site_sqlite_TB_Subclasse'),
    'class_features': os.environ.get('SITE_MONGO_CLASS_FEATURES_COLLECTION', 'site_sqlite_TB_ClasseHabilidade'),
    'class_resources': os.environ.get('SITE_MONGO_CLASS_RESOURCES_COLLECTION', 'site_sqlite_TB_RecursoClasse'),
    'races': os.environ.get('SITE_MONGO_RACES_COLLECTION', 'site_sqlite_TB_Raca'),
    'lineages': os.environ.get('SITE_MONGO_LINEAGES_COLLECTION', 'site_sqlite_TB_Linhagem'),
    'essences': os.environ.get('SITE_MONGO_ESSENCES_COLLECTION', 'site_sqlite_TB_Essencia'),
    'racial_traits': os.environ.get('SITE_MONGO_RACIAL_TRAITS_COLLECTION', 'site_sqlite_TB_TracoRacial'),
    'map_markers': os.environ.get('SITE_MONGO_MAP_MARKERS_COLLECTION', 'site_sqlite_TB_MapMarker'),
    'regions': os.environ.get('SITE_MONGO_REGIONS_COLLECTION', 'site_sqlite_TB_Regiao'),
    'territories': os.environ.get('SITE_MONGO_TERRITORIES_COLLECTION', 'site_sqlite_TB_Territorio'),
    'talents': os.environ.get('SITE_MONGO_TALENTS_COLLECTION', 'site_sqlite_TB_Talento'),
    'options': os.environ.get('SITE_MONGO_OPTIONS_COLLECTION', 'site_sqlite_TB_OpcaoJogo'),
    'spells': os.environ.get('SITE_MONGO_SPELLS_COLLECTION', BOT_MONGO_COLLECTIONS['spells']),
    'backgrounds': os.environ.get('SITE_MONGO_BACKGROUNDS_COLLECTION', BOT_MONGO_COLLECTIONS['backgrounds']),
    'bestiary': os.environ.get('SITE_MONGO_BESTIARY_COLLECTION', BOT_MONGO_COLLECTIONS['bestiary']),
    'organizations': os.environ.get('SITE_MONGO_ORGANIZATIONS_COLLECTION', BOT_MONGO_COLLECTIONS['organizations']),
}
SITE_MONGO_SYNC_ENABLED = False
SITE_MONGO_SYNC_INTERVAL_SECONDS = int(os.environ.get('SITE_MONGO_SYNC_INTERVAL_SECONDS', '45'))
SITE_MONGO_SYNC_NAMESPACE = os.environ.get('SITE_MONGO_SYNC_NAMESPACE', 'site_sqlite')


# Logs Console Admin
SERVER_LOGS_PASSWORD_HASH = os.environ.get('SERVER_LOGS_PASSWORD_HASH', 'pbkdf2_sha256$1200000$gTvUJzX0lYFlWEmZJuVz6P$NFoDenHOCIGklcvrwoM4bL/9m8uKCLcXxQU+PrALvP0=')

# Google Docs Import
DOCS_API_KEY = os.environ.get('DOCS_API_KEY', '')
