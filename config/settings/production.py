from .base import *

DEBUG = False
ALLOWED_HOSTS = ["steven-dyanizha-selaras-web.pws.cs.ui.ac.id"]
CSRF_TRUSTED_ORIGINS = ["https://steven-dyanizha-selaras-web.pws.cs.ui.ac.id"]

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATIC_URL = "/static/"
WHITENOISE_USE_FINDERS = True