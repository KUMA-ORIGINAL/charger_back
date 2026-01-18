from datetime import timedelta
from pathlib import Path

import environ
import sentry_sdk
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from sentry_sdk.integrations.django import DjangoIntegration

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False)
)

SECRET_KEY = env('SECRET_KEY')

DEBUG = bool(env("DEBUG", default=0))

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS").split(" ")

DOMAIN = env("DOMAIN")

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True
# CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS").split(" ")
CORS_ALLOW_HEADERS = ["Authorization", "Content-Type", "Accept"]
# CORS_ALLOWED_ORIGIN_REGEXES = [
#     r"^https:\/\/.*\.netlify\.app$",
# ]

if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
else:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


INSTALLED_APPS = [
    'daphne',
    'modeltranslation',
    'unfold',
    "unfold.contrib.forms",
    "unfold.contrib.filters",  # optional, if special filters are needed  # optional, if special form elements are needed
    "unfold.contrib.inlines",  # optional, if special inlines are needed
    "unfold.contrib.import_export",

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "django.contrib.postgres",

    'rest_framework',
    'drf_spectacular',
    'django_filters',
    'corsheaders',
    'cachalot',
    'channels',
    "phonenumber_field",
    "import_export",

    'account',
    'payments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',

    'corsheaders.middleware.CorsMiddleware',
    'djangorestframework_camel_case.middleware.CamelCaseMiddleWare',
    'config.middleware.LanguageMiddleware',

    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'account/templates',
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('POSTGRES_DB'),
        'USER': env('POSTGRES_USER'),
        'PASSWORD': env('POSTGRES_PASSWORD'),
        'HOST': env('POSTGRES_HOST'),
        'PORT': env('POSTGRES_PORT'),
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


LANGUAGE_CODE = 'ru'

TIME_ZONE = 'Asia/Bishkek'

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'
STATICFILES_DIRS = [
    BASE_DIR / 'account/static/',
    BASE_DIR / 'common/static/',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# if not DEBUG:
#     sentry_sdk.init(
#         dsn=env('SENTRY_DSN'),
#         integrations=[DjangoIntegration()],
#         traces_sample_rate=0.5,  # Для мониторинга производительности. Можно уменьшить
#         send_default_pii=True,
#         environment="production",
#     )

PHONENUMBER_DEFAULT_REGION = 'KG'

LANGUAGES = (
    ('ru', 'Russian'),
    ('ky', 'Kyrgyz'),
)
MODELTRANSLATION_DEFAULT_LANGUAGE = 'ru'
MODELTRANSLATION_LANGUAGES = ('ru', 'ky')
MODELTRANSLATION_FALLBACK_LANGUAGES = {
    'default': ('ru',),
    'ky': ('ru',),
}
MODELTRANSLATION_AUTO_POPULATE = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

CSRF_TRUSTED_ORIGINS = [f"https://{DOMAIN}", f"http://{DOMAIN}"]

AUTH_USER_MODEL = 'account.User'

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
    'SHOW_COLLAPSED': True,
    'ENABLE_STACKTRACES': False,
    'DISABLE_PANELS': {
        'debug_toolbar.panels.redirects.RedirectsPanel',
        'cachalot.panels.CachalotPanel',
    },
}

# Внутренние IP-адреса (для локальной разработки)
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

if DEBUG:
    INSTALLED_APPS += ['silk', "debug_toolbar",]
    MIDDLEWARE.insert(0, 'silk.middleware.SilkyMiddleware')
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware',)

CACHALOT_ENABLED = True
CACHALOT_ONLY_CACHABLE_TABLES = (
    'common_pagetext',
    'common_qaentry',
    'common_pagetextglobalversion',
)
CACHALOT_TIMEOUT = 60 * 60

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": ['redis://redis:6379/2'],  # Используем другой слот Redis (например, /2)
        },
    },
}


SPECTACULAR_SETTINGS = {
    'TITLE': 'Osago',
    'DESCRIPTION': 'Your project description',
    'VERSION': '1.0.0',
    'SCHEMA_VERSION': '3.1.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CAMELIZE_NAMES': True,
    'COMPONENT_SPLIT_REQUEST': True,

    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.contrib.djangorestframework_camel_case.camelize_serializer_fields',
    ],

    'SERVE_PUBLIC': True,
    'SERVE_HTTPS': True,
    'SERVE_PERMISSIONS': ['config.permissions.IsSuperUser'],
    'SERVE_AUTHENTICATION': ['rest_framework.authentication.SessionAuthentication',]
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=90),
    "AUTH_HEADER_TYPES": ("Bearer",),
    'UPDATE_LAST_LOGIN': True,
}


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': (
        'djangorestframework_camel_case.render.CamelCaseJSONRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'djangorestframework_camel_case.parser.CamelCaseFormParser',
        'djangorestframework_camel_case.parser.CamelCaseMultiPartParser',
        'djangorestframework_camel_case.parser.CamelCaseJSONParser',
    ),
}


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',  # Можно изменить на 'DEBUG' для более подробного вывода
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',  # Логи с уровнем DEBUG и выше будут записываться в файл
            'class': 'logging.FileHandler',
            'filename': 'django_app.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        # 'django.db.backends': {
        #     'level': 'DEBUG',
        #     'handlers': ['console'],
        # },
        'cachalot': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}


UNFOLD = {
    "SITE_TITLE": 'Charger',
    "SITE_HEADER": "Charger",
    "SITE_URL": "/",
    "SITE_SYMBOL": "menu",  # symbol from icon set
    "SHOW_HISTORY": True, # show/hide "History" button, default: True
    "SHOW_VIEW_ON_SITE": True, # show/hide "View on site" button, default: True
    "LOGIN": {
        "image": lambda request: static("login-bg.jpg"),
    },
    "BORDER_RADIUS": "6px",
    "COLORS": {
        "base": {
            "50": "249 250 251",
            "100": "243 244 246",
            "200": "229 231 235",
            "300": "209 213 219",
            "400": "156 163 175",
            "500": "107 114 128",
            "600": "75 85 99",
            "700": "55 65 81",
            "800": "31 41 55",
            "900": "17 24 39",
            "950": "3 7 18",
        },
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "233 213 255",
            "300": "216 180 254",
            "400": "192 132 252",
            "500": "168 85 247",
            "600": "147 51 234",
            "700": "126 34 206",
            "800": "107 33 168",
            "900": "88 28 135",
            "950": "59 7 100",
        },
        "font": {
            "subtle-light": "var(--color-base-500)",  # text-base-500
            "subtle-dark": "var(--color-base-400)",  # text-base-400
            "default-light": "var(--color-base-600)",  # text-base-600
            "default-dark": "var(--color-base-300)",  # text-base-300
            "important-light": "var(--color-base-900)",  # text-base-900
            "important-dark": "var(--color-base-100)",  # text-base-100
        },
    },
    'TABS': [
    ],
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "navigation": [
            {
                "title": _("Пользователи и Доступ"),
                "collapsible": False,
                "items": [
                    {
                        "title": _("Станции"),
                        "icon": "charger",
                        "link": reverse_lazy("admin:account_chargepoint_changelist"),
                        "permission": "account.utils.permission_callback_for_admin",
                    },
                    {
                        "title": _("CSMS сервисы"),
                        "icon": "cloud",
                        "link": reverse_lazy("admin:account_csmsservice_changelist"),
                        "permission": "account.utils.permission_callback_for_admin",
                    },
                    {
                        "title": _("Сессии зарядки"),
                        "icon": "bolt",
                        "link": reverse_lazy("admin:account_chargingsession_changelist"),
                        "permission": "account.utils.permission_callback_for_admin",
                    },
                    {
                        "title": _("QR‑платежи"),
                        "icon": "qr_code",
                        "link": reverse_lazy("admin:payments_qrpayment_changelist"),
                    },
                    {
                        "title": _("Пользователи"),
                        "icon": "person",
                        "link": reverse_lazy("admin:account_user_changelist"),
                        "permission": "account.utils.permission_callback_for_admin",
                    },
                    {
                        "title": _("Группы"),
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                ],
            },
        ],
    }
}
