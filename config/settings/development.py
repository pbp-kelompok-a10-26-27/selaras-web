import sys
import tempfile
from pathlib import Path

from .base import *  # noqa: F403

DEBUG = True  # Set to True for development, False for production
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]  # Add your development host here

# Saat test, file unggahan ditulis ke folder sementara (bukan media/ milik dev)
if "test" in sys.argv:
    _TEST_MEDIA = Path(tempfile.mkdtemp(prefix="selaras-test-"))
    MEDIA_ROOT = _TEST_MEDIA / "media"
    PRIVATE_MEDIA_ROOT = _TEST_MEDIA / "private"
