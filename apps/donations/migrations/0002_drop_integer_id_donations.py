# Donations switch to UUID primary keys. The project is still in early development
# with no data worth keeping, so the old table is dropped here and recreated by the
# next migration; this works the same on every database backend.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("donations", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(name="Donation"),
    ]
