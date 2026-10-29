import math
import re
from decimal import Decimal, InvalidOperation

from django import template
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def rupiah(value):
    """Format an amount the Indonesian way: 1250000 -> 1.250.000, 125.5 -> 125,50."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return value

    whole, _, fraction = f"{abs(amount):.2f}".partition(".")
    grouped = f"{int(whole):,}".replace(",", ".")
    sign = "-" if amount < 0 else ""
    return f"{sign}{grouped}" + ("" if fraction == "00" else f",{fraction}")


@register.filter
def days_until(value):
    """Whole days left until a datetime (0 once it has passed, None without a date)."""
    if not value:
        return None
    seconds = (value - timezone.now()).total_seconds()
    return max(math.ceil(seconds / 86400), 0)


MENTION = re.compile(r"(?<![\w@])@([\w.+-]{1,150})")


@register.filter
def mentions(value):
    """Escape text and highlight @username mentions (used in posts and replies)."""
    text = escape(value or "")
    return mark_safe(  # noqa: S308 - the text was escaped above
        MENTION.sub(r'<span class="font-semibold text-secondary-600">@\1</span>', text)
    )
