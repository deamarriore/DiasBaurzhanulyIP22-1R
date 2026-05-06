import os
from pathlib import Path

# Построение путей внутри проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: храните секретный ключ в безопасности!
SECRET_KEY = 'django-insecure-ts$d-7tm6yf_yl0fnc-7kpl3y+bzcrw2=$fuj5^w74*$mu%f6g'

# SECURITY WARNING: DEBUG всегда False в продакшене!
DEBUG = False

# Разрешаем все хосты для работы на Vercel
ALLOWED_HOSTS = ['*']

# Настройки для работы сессий и защиты на доменах vercel.app
CSRF_TRUSTED_ORIGINS = ['https://*.vercel.app']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'inventory',
    'accounting',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Для раздачи статики (нужно установить whitenoise)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'warehouse_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'warehouse_project.wsgi.application'

# База данных: используем os.path для надежности пути на Vercel
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Валидация паролей
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Интернационализация
LANGUAGE_CODE = 'ru-ru' # Сделаем админку на русском
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Статические файлы
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')] if os.path.exists(os.path.join(BASE_DIR, 'static')) else []

# Настройки входа
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accounting/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Настройка типа поля по умолчанию
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'