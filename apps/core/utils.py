# Utils Functions

from django.utils.text import slugify

def generate_slug(text):
    """
    Generate a slug from the given text.
    """
    return slugify(text)

