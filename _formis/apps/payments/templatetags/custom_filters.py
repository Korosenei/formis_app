from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Récupérer un élément dans un dictionnaire par clé"""
    if not dictionary:
        return None
    return dictionary.get(key)
