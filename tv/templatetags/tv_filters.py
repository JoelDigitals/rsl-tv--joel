from django import template

register = template.Library()

@register.filter(name='split')
def split(value, arg):
    """
    Split a string by the given separator.
    Usage: {{ value|split:"," }}
    """
    if value:
        return value.split(arg)
    return []

@register.filter(name='trim')
def trim(value):
    """
    Trim whitespace from a string.
    Usage: {{ value|trim }}
    """
    if value:
        return value.strip()
    return ''
