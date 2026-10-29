# The article editor requires a category, but a fresh database had none and the
# site offered no way to add one, so nobody could create an article. Seed a few
# starter categories (admins can rename or add more on the category page).

from django.db import migrations
from django.utils.text import slugify

STARTER_CATEGORIES = (
    "Lingkungan",
    "Konsumsi Sadar",
    "Energi",
    "Pangan & Kebun",
    "Daur Ulang",
    "Gaya Hidup",
)


def seed_categories(apps, schema_editor):
    ArticleCategory = apps.get_model("articles", "ArticleCategory")
    for name in STARTER_CATEGORIES:
        if not ArticleCategory.objects.filter(name__iexact=name).exists():
            slug = slugify(name)
            if ArticleCategory.objects.filter(slug=slug).exists():
                continue
            ArticleCategory.objects.create(name=name, slug=slug)


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0003_article_review_and_reads"),
    ]

    operations = [
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]
