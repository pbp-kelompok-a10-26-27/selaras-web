# Posts and comments switch to UUID primary keys. The project is still in early
# development with no data worth keeping, so the old tables are dropped here and
# recreated by the next migration; this works the same on every database backend
# (an in-place integer -> UUID primary key change does not).

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0003_alter_post_challenge"),
    ]

    operations = [
        migrations.DeleteModel(name="Like"),
        migrations.DeleteModel(name="Comment"),
        migrations.DeleteModel(name="Post"),
    ]
