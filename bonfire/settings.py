

import importlib.util
import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

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






DEBUG = _env_bool("DJANGO_DEBUG", False)
HUNTER_CREATOR_RULESET_CHECKSUM = os.environ.get('HUNTER_CREATOR_RULESET_CHECKSUM', '').strip()

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        # Só dev: chave insegura e publicamente conhecida, nunca usar em produção.
        SECRET_KEY = 'django-insecure-x6%=xcc0x#6+#17z8-p+815+e-)&yy2q_*0u+q7wnsoa!845iw'
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY ausente em produção")

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
                'home.context_processors.site_presentation',
            ],
        },
    },
]

WSGI_APPLICATION = 'bonfire.wsgi.application'





_db_engine = os.environ.get('DB_ENGINE', '').strip()
_postgres_url = os.environ.get('POSTGRES_URL', '').strip()

if _postgres_url:
    try:
        _parsed_db = urlparse(_postgres_url)
        _db_host = _parsed_db.hostname
        _db_port = _parsed_db.port or 5432
    except ValueError:
        # Erros do parser podem incluir o netloc, inclusive credenciais.
        raise ImproperlyConfigured('POSTGRES_URL contém dados inválidos.') from None
    if (
        _parsed_db.scheme not in {'postgres', 'postgresql'}
        or not _db_host
        or not _parsed_db.path.strip('/')
    ):
        raise ImproperlyConfigured(
            'POSTGRES_URL deve ser uma URL PostgreSQL válida com host e banco.'
        )
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _parsed_db.path.lstrip('/'),
            'USER': _parsed_db.username or 'postgres',
            'PASSWORD': _parsed_db.password or '',
            'HOST': _db_host,
            'PORT': str(_db_port),
            'OPTIONS': {'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', '5'))},
        }
    }
elif _db_engine.lower() in {'postgresql', 'django.db.backends.postgresql'}:
    _db_name = os.environ.get('DB_NAME', 'postgres').strip() or 'postgres'
    _db_host = os.environ.get('DB_HOST', 'localhost').strip() or 'localhost'
    _db_user = os.environ.get('DB_USER', 'postgres').strip() or 'postgres'
    _db_port = os.environ.get('DB_PORT', '5432').strip() or '5432'
    try:
        _db_port_number = int(_db_port)
    except ValueError as exc:
        raise ImproperlyConfigured('DB_PORT deve ser uma porta PostgreSQL válida.') from exc
    if not 1 <= _db_port_number <= 65535:
        raise ImproperlyConfigured('DB_PORT deve ser uma porta PostgreSQL válida.')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _db_name,
            'USER': _db_user,
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': _db_host,
            'PORT': str(_db_port_number),
            'OPTIONS': {'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', '5'))},
        }
    }
else:
    raise ImproperlyConfigured(
        'Configuração PostgreSQL obrigatória: defina POSTGRES_URL válida ou '
        'DB_ENGINE=postgresql.'
    )





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

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


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
# Em DEBUG (dev sobre http://127.0.0.1) os cookies NÃO podem ser Secure, senão o
# navegador descarta o sessionid/csrf em conexões http e o login (inclusive o OAuth
# do Discord, que depende do state na sessão) nunca persiste. Em produção DEBUG=False
# e os flags voltam a respeitar o .env (HTTPS via Cloudflare).
SESSION_COOKIE_SECURE = (not DEBUG) and _env_bool("DJANGO_SESSION_COOKIE_SECURE", SECURE_SSL_REDIRECT)
CSRF_COOKIE_SECURE = (not DEBUG) and _env_bool("DJANGO_CSRF_COOKIE_SECURE", SECURE_SSL_REDIRECT)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)

if _env_bool("DJANGO_USE_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGIN_REDIRECT_URL = '/'

# ── E-mail (Gmail SMTP) ──────────────────────────────────────────────────────
# Defina EMAIL_HOST_USER (a conta) e EMAIL_HOST_PASSWORD (a "senha de app" do Google,
# NÃO a senha normal) no .env. Sem isso, cai no backend de console (não envia de verdade,
# útil em dev). EMAIL_CONFIGURADO indica se o envio real está ativo.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "").strip()
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@bonfiretales.com.br")
EMAIL_CONFIGURADO = bool(EMAIL_HOST_USER and EMAIL_HOST_PASSWORD)
EMAIL_BACKEND = ("django.core.mail.backends.smtp.EmailBackend" if EMAIL_CONFIGURADO
                 else "django.core.mail.backends.console.EmailBackend")

# Apresentação pública e publicidade. Anúncios são habilitados em duas camadas:
# globalmente por ambiente e explicitamente por view editorial. Assim ferramentas,
# login, erros e páginas vazias nunca viram inventário publicitário por acidente.
SITE_ORIGIN = os.environ.get("SITE_ORIGIN", "https://bonfiretales.com.br").rstrip("/")
ADSENSE_PUBLISHER_ID = os.environ.get("ADSENSE_PUBLISHER_ID", "ca-pub-1634793837919535").strip()
# Em produção o código de Auto Ads acompanha as páginas editoriais que fazem
# opt-in. Em desenvolvimento ele fica desligado; a env continua permitindo
# desativação imediata sem deploy.
ADSENSE_ENABLED = _env_bool("ADSENSE_ENABLED", not DEBUG) and bool(ADSENSE_PUBLISHER_ID)
ADSENSE_SIDEBAR_SLOT = os.environ.get("ADSENSE_SIDEBAR_SLOT", "").strip()
ADSENSE_HORIZONTAL_SLOT = os.environ.get("ADSENSE_HORIZONTAL_SLOT", "").strip()

BOT_POSTGRES_TABLES = {
    'quests': os.environ.get('BOT_POSTGRES_QUESTS_TABLE', 'rpg_quests'),
    'items': os.environ.get('BOT_POSTGRES_ITEMS_TABLE', 'rpg_items'),
    'dedicated_ranks': os.environ.get('BOT_POSTGRES_DEDICATED_RANKS_TABLE', 'dedicated-ranks'),
    'jobs': os.environ.get('BOT_POSTGRES_JOBS_TABLE', 'discord_jobs'),
    'store': os.environ.get('BOT_POSTGRES_STORE_TABLE', 'discord_bot_store'),
    'spells': os.environ.get('BOT_POSTGRES_SPELLS_TABLE', 'spells'),
    'backgrounds': os.environ.get('BOT_POSTGRES_BACKGROUNDS_TABLE', 'backgrounds'),
    'bestiary': os.environ.get('BOT_POSTGRES_BESTIARY_TABLE', 'bestiary'),
    'organizations': os.environ.get('BOT_POSTGRES_ORGANIZATIONS_TABLE', 'organizations'),
}
SITE_POSTGRES_TABLES = {
    'classes': os.environ.get('SITE_POSTGRES_CLASSES_TABLE', 'home_tbclasse'),
    'subclasses': os.environ.get('SITE_POSTGRES_SUBCLASSES_TABLE', 'home_tbsubclasse'),
    'class_features': os.environ.get('SITE_POSTGRES_CLASS_FEATURES_TABLE', 'home_tbclassehabilidade'),
    'class_resources': os.environ.get('SITE_POSTGRES_CLASS_RESOURCES_TABLE', 'home_tbrecursoclasse'),
    'races': os.environ.get('SITE_POSTGRES_RACES_TABLE', 'home_tbraca'),
    'lineages': os.environ.get('SITE_POSTGRES_LINEAGES_TABLE', 'home_tblinhagem'),
    'essences': os.environ.get('SITE_POSTGRES_ESSENCES_TABLE', 'home_tbessencia'),
    'racial_traits': os.environ.get('SITE_POSTGRES_RACIAL_TRAITS_TABLE', 'home_tbtracoracial'),
    'map_markers': os.environ.get('SITE_POSTGRES_MAP_MARKERS_TABLE', 'home_tbmapmarker'),
    'regions': os.environ.get('SITE_POSTGRES_REGIONS_TABLE', 'home_tbregiao'),
    'territories': os.environ.get('SITE_POSTGRES_TERRITORIES_TABLE', 'home_tbterritorio'),
    'talents': os.environ.get('SITE_POSTGRES_TALENTS_TABLE', 'home_tbtalento'),
    'options': os.environ.get('SITE_POSTGRES_OPTIONS_TABLE', 'home_tbopcaojogo'),
    'spells': os.environ.get('SITE_POSTGRES_SPELLS_TABLE', BOT_POSTGRES_TABLES['spells']),
    'backgrounds': os.environ.get('SITE_POSTGRES_BACKGROUNDS_TABLE', BOT_POSTGRES_TABLES['backgrounds']),
    'bestiary': os.environ.get('SITE_POSTGRES_BESTIARY_TABLE', BOT_POSTGRES_TABLES['bestiary']),
    'organizations': os.environ.get('SITE_POSTGRES_ORGANIZATIONS_TABLE', BOT_POSTGRES_TABLES['organizations']),
}


# Logs Console Admin
# Propositalmente hardcoded (decisao do PO 2026-07-17): o console do admin edita o .env, entao a senha do console NAO pode ser configuravel por env — trocar a senha exige commit.
SERVER_LOGS_PASSWORD_HASH = 'pbkdf2_sha256$1200000$gTvUJzX0lYFlWEmZJuVz6P$NFoDenHOCIGklcvrwoM4bL/9m8uKCLcXxQU+PrALvP0='

# Google Docs Import
DOCS_API_KEY = os.environ.get('DOCS_API_KEY', '')

# ── Discord OAuth2 (login/vínculo de conta) — fluxo custom enxuto ──────────────
# Credenciais vêm do .env (gitignored). REDIRECT_URI vazio = derivado da request
# (registre no Discord Dev Portal: http://localhost:8000/discord/callback/ e
# https://bonfiretales.com.br/discord/callback/).
DISCORD_OAUTH_CLIENT_ID = os.environ.get("DISCORD_OAUTH_CLIENT_ID", "").strip()
DISCORD_OAUTH_CLIENT_SECRET = os.environ.get("DISCORD_OAUTH_CLIENT_SECRET", "").strip()
DISCORD_OAUTH_REDIRECT_URI = os.environ.get("DISCORD_OAUTH_REDIRECT_URI", "").strip()

# ── Asaas (pagamentos) — webhook que cria a transação na tabela compartilhada ──
# TODAS as credenciais vêm do .env (gitignored). NUNCA hardcodar aqui.
# ASAAS_WEBHOOK_TOKEN: token forte (32-255 chars) configurado no painel do Asaas;
#   o webhook valida o header `asaas-access-token` contra ele.
# ASAAS_API_KEY: chave de API (access_token) p/ buscar o pagamento completo pelo id.
# ASAAS_API_BASE: sandbox por padrão; em produção use https://api.asaas.com/v3.
ASAAS_WEBHOOK_TOKEN = os.environ.get("ASAAS_WEBHOOK_TOKEN", "").strip()
ASAAS_API_KEY = os.environ.get("ASAAS_API_KEY", "").strip()
ASAAS_API_BASE = os.environ.get("ASAAS_API_BASE", "https://api-sandbox.asaas.com/v3").strip().rstrip("/")
BONFIRE_CHECKOUT_SIGNING_SECRET = os.environ.get("BONFIRE_CHECKOUT_SIGNING_SECRET", "").strip()

# Desativa apenas a melhoria por fetch, preservando formulário, contadores e recibos.
SPELL_SLOT_PARTIAL_ENABLED = os.environ.get('SPELL_SLOT_PARTIAL_ENABLED', '1') == '1'
