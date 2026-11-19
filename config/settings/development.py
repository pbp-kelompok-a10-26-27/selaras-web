import sys
import tempfile
from pathlib import Path

from .base import *  # noqa: F403

DEBUG = True  # Set to True for development, False for production
# Dukung Flutter Android emulator (10.0.2.2) & local LAN
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "10.0.2.2", "*"]

# Saat test, file unggahan ditulis ke folder sementara (bukan media/ milik dev)
if "test" in sys.argv:
    _TEST_MEDIA = Path(tempfile.mkdtemp(prefix="selaras-test-"))
    MEDIA_ROOT = _TEST_MEDIA / "media"
    PRIVATE_MEDIA_ROOT = _TEST_MEDIA / "private"
