import os
from pathlib import Path
from decouple import config
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-your-secret-key-here')

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = config('DEBUG', default=True, cast=bool)
# DEBUG = config('DEBUG', default=True, cast=bool)
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '10.0.2.2', '192.168.1.*', '*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_yasg',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'import_export',
    'ckeditor',
    'django_celery_beat',
    'django_celery_results',
    'storages',
    
    # Local apps
    'apps.core',
    'apps.api',
    
    'crispy_forms',
    'crispy_bootstrap5',
    
    'django_extensions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'apps.core.middleware.CustomErrorMiddleware',
]

ROOT_URLCONF = 'vehicle_insurance_backend.urls'


CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Login URL
LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'core:login'

# Session settings
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.notification_count', 
            ],
        },
    },
]

WSGI_APPLICATION = 'vehicle_insurance_backend.wsgi.application'

# Database
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': config('DB_NAME', default='vehicle_insurance_backend'),
#         'USER': config('DB_USER', default='postgres'),
#         'PASSWORD': config('DB_PASSWORD', default='password'),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='5432'),
#     }
# }


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Custom User Model
AUTH_USER_MODEL = 'core.User'

# Authentication
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'login': '5/minute',
        'otp': '3/minute',
    },
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# CORS Settings
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://localhost:8000').split(',')
CORS_ALLOW_CREDENTIALS = True

# Static and Media Files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp-relay.brevo.com')  # Changed default to Brevo
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = f'Vehicle Insurance <{EMAIL_HOST_USER}>'

# Comment this out to actually send emails
# if DEBUG:
#     EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Staff notification emails for contact form
STAFF_NOTIFICATION_EMAILS = [
    'support@vehicleinsure.ng',
    'hello@vehicleinsure.ng',
]
SERVER_EMAIL = 'server@vehicleinsure.ng'

# Password Reset Settings
PASSWORD_RESET_TIMEOUT = 3600

# Celery Configuration
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Lagos'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Flutterwave Payment Configuration
FLUTTERWAVE_PUBLIC_KEY = config('FLUTTERWAVE_PUBLIC_KEY', default='FLWPUBK_TEST-aa2f8a3732b5c9a5a6deead05e8adb2d-X')
FLUTTERWAVE_SECRET_KEY = config('FLUTTERWAVE_SECRET_KEY', default='FLWSECK_TEST-feff543f125048d47ff25b1b16c342f7-X')
FLUTTERWAVE_ENCRYPTION_KEY = config('FLUTTERWAVE_ENCRYPTION_KEY', default='FLWSECK_TESTa5a6deead05e8adb2d')
FLUTTERWAVE_BASE_URL = 'https://api.flutterwave.com/v3'
FLUTTERWAVE_WEBHOOK_SECRET = config('FLUTTERWAVE_WEBHOOK_SECRET', default='')

# SMS Configuration
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = config('TWILIO_PHONE_NUMBER', default='')

# FCM Configuration
FCM_DJANGO_SETTINGS = {
    'FCM_SERVER_KEY': config('FCM_SERVER_KEY', default=''),
    'ONE_DEVICE_PER_USER': True,
    'DELETE_INACTIVE_DEVICES': True,
}

# Django AllAuth
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_LOGOUT_ON_GET = True
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/debug.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# Security Settings (Production)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# Custom error handlers
handler404 = 'apps.core.views.handler404'
handler500 = 'apps.core.views.handler500'
handler403 = 'apps.core.views.handler403'
handler400 = 'apps.core.views.handler400'

# Email settings for error notifications
ADMINS = [
    ('Admin', 'admin@vehicleinsure.ng'),
]



# Add at the bottom of settings.py
# Django-Python 3.14 compatibility fix
import sys

if sys.version_info >= (3, 14):
    import django.template.context
    from copy import copy
    
    # Store the original __copy__ methods
    _original_context_copy = django.template.context.Context.__copy__
    _original_request_context_copy = django.template.context.RequestContext.__copy__
    
    def patched_context_copy(self):
        """Patched __copy__ for Context class."""
        try:
            # Try the original method first
            return _original_context_copy(self)
        except AttributeError:
            # Create a new instance and manually copy attributes
            duplicate = self.__class__()
            
            # Copy all relevant attributes
            if hasattr(self, 'dicts'):
                duplicate.dicts = self.dicts[:] if isinstance(self.dicts, list) else []
            if hasattr(self, '_flattened_contexts'):
                duplicate._flattened_contexts = self._flattened_contexts
            if hasattr(self, '_builtins'):
                duplicate._builtins = self._builtins
            if hasattr(self, 'autoescape'):
                duplicate.autoescape = self.autoescape
            if hasattr(self, 'use_l10n'):
                duplicate.use_l10n = self.use_l10n
            if hasattr(self, 'use_tz'):
                duplicate.use_tz = self.use_tz
            if hasattr(self, 'template'):
                duplicate.template = self.template
            if hasattr(self, 'render_context'):
                duplicate.render_context = self.render_context
            
            return duplicate
    
    def patched_request_context_copy(self):
        """Patched __copy__ for RequestContext class."""
        try:
            # Try the original method first
            return _original_request_context_copy(self)
        except AttributeError:
            # Create a new RequestContext with the same request
            duplicate = django.template.context.RequestContext(self.request)
            
            # Copy all relevant attributes
            if hasattr(self, 'dicts'):
                duplicate.dicts = self.dicts[:] if isinstance(self.dicts, list) else []
            if hasattr(self, '_flattened_contexts'):
                duplicate._flattened_contexts = self._flattened_contexts
            if hasattr(self, '_builtins'):
                duplicate._builtins = self._builtins
            if hasattr(self, '_processors'):
                duplicate._processors = self._processors
            if hasattr(self, 'autoescape'):
                duplicate.autoescape = self.autoescape
            if hasattr(self, 'use_l10n'):
                duplicate.use_l10n = self.use_l10n
            if hasattr(self, 'use_tz'):
                duplicate.use_tz = self.use_tz
            if hasattr(self, 'template'):
                duplicate.template = self.template
            if hasattr(self, 'render_context'):
                duplicate.render_context = self.render_context
            if hasattr(self, 'csrf_token'):
                duplicate.csrf_token = self.csrf_token
            
            return duplicate
    
    # Apply the patches
    django.template.context.Context.__copy__ = patched_context_copy
    django.template.context.RequestContext.__copy__ = patched_request_context_copy
    
    print("✅ Applied Django-Python 3.14 compatibility patches")