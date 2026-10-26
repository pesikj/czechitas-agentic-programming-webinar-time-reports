from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def hours(minutes):
    value = Decimal(minutes) / 60
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")
