# apps/payments/templatetags/payment_tags.py
from django import template

register = template.Library()

@register.filter
def filter_by_tranche(paiements, tranche_id):
    """
    Filtre les paiements pour ne garder que ceux de la tranche donnée.
    """
    return [p for p in paiements if p.tranche_id == tranche_id]
