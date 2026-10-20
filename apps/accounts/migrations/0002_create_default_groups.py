from django.db import migrations


def create_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Admin")
    Group.objects.get_or_create(name="User")


def remove_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Admin", "User"]).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(create_default_groups, remove_default_groups)]
