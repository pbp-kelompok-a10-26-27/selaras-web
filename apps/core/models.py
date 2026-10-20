from django.db import models

# SELARAS Shared Model for reusable purpose
class TimeStamp(models.Model):

    """
    Abstract base model for providing datetime creation and updation purpose.
    """

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:

        abstract = True


class SoftDeleteModel(models.Model):

    """
    Abstract model for records that should be hidden instead of
    immediately deleted from the database.
    """

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        
        abstract = True
