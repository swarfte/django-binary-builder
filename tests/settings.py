"""Minimal Django settings for the django-binary-builder test suite."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = "test-secret-key"

DEBUG = True

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

STATIC_URL = "static/"

USE_TZ = True

WSGI_APPLICATION = "tests.wsgi.application"
