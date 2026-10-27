import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    """Files outside MEDIA_ROOT: they are only reachable through a view that checks
    who is asking (e.g. ticket attachments). The folder is read from settings on
    every use, so tests can point it somewhere temporary."""

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)


def private_storage():
    return PrivateStorage()
