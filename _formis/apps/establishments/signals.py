from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Etablissement, ParametresEtablissement, Salle, Campus


@receiver(post_save, sender=Etablissement)
def create_etablissement_parametres(sender, instance, created, **kwargs):
    """Créer automatiquement les paramètres par défaut pour un nouvel établissement"""
    if created:
        ParametresEtablissement.objects.get_or_create(etablissement=instance)


@receiver(post_save, sender=Salle)
@receiver(post_delete, sender=Salle)
def update_etablissement_capacite(sender, instance, **kwargs):
    """Mettre à jour la capacité totale de l'établissement quand une salle est ajoutée/supprimée"""
    etablissement = instance.etablissement
    total_capacite = etablissement.salle_set.filter(est_active=True).aggregate(
        total=models.Sum('capacite')
    )['total'] or 0

    # Ne pas écraser si l'établissement a une capacité personnalisée
    if etablissement.capacite_totale == 0 or not hasattr(etablissement, '_skip_auto_capacity'):
        etablissement.capacite_totale = total_capacite
        etablissement._skip_auto_capacity = True
        etablissement.save(update_fields=['capacite_totale'])
