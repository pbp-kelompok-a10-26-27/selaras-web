import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import MIDDLEWARE


def env_flag(name, default):
    value = os.environ.get(name, "").strip().lower()
    return value in ("1", "true", "yes") if value else default


DEBUG = False

# Dari environment, contoh: ALLOWED_HOSTS="selaras.example.com,www.example.com"
PWS_HOST = "steven-dyanizha-selaras-web.pws.cs.ui.ac.id"
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", PWS_HOST).split(",") if h.strip()
]
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]

# Jangan pernah jalan dengan secret key bawaan
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("Set SECRET_KEY (minimal 50 karakter) di environment.")

# Gunicorn tidak melayani /static/; WhiteNoise yang melayani. Finders membuatnya
# tetap jalan walau collectstatic tidak dijalankan saat build.
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
WHITENOISE_USE_FINDERS = True

# PostgreSQL dari PWS. Tanpa DB_HOST jatuh ke SQLite, yang hilang tiap redeploy.
if os.environ.get("DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", ""),
            "USER": os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ["DB_HOST"],
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {
                "options": f"-c search_path={os.environ.get('SCHEMA', 'public')}"
            },
        }
    }

# Tidak ada web server terpisah di PWS, jadi Django yang melayani /media/
SERVE_MEDIA = env_flag("SERVE_MEDIA", True)

# HTTPS di balik reverse proxy. Kalau halaman redirect terus-menerus, set
# SECURE_SSL_REDIRECT=false di environment.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_flag("SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
