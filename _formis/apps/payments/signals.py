# apps/payments/signals.py

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Paiement, InscriptionPaiement, HistoriquePaiement


@receiver(post_save, sender=Paiement)
def paiement_post_save(sender, instance, created, **kwargs):
    """Actions après sauvegarde d'un paiement"""

    # Créer l'historique si c'est une nouvelle instance
    if created:
        HistoriquePaiement.objects.create(
            paiement=instance,
            type_action='CREATION',
            nouveau_statut=instance.statut,
            details=f"Paiement créé: {instance.montant} XOF via {instance.get_methode_paiement_display()}"
        )


@receiver(pre_save, sender=Paiement)
def paiement_pre_save(sender, instance, **kwargs):
    """Actions avant sauvegarde d'un paiement"""

    # Stocker l'ancien statut pour l'historique
    if instance.pk:
        try:
            ancien_paiement = Paiement.objects.get(pk=instance.pk)
            instance._ancien_statut = ancien_paiement.statut
        except Paiement.DoesNotExist:
            instance._ancien_statut = None
    else:
        instance._ancien_statut = None


@receiver(post_save, sender=Paiement)
def paiement_changement_statut(sender, instance, **kwargs):
    """Gérer les changements de statut des paiements"""

    if hasattr(instance, '_ancien_statut') and instance._ancien_statut:
        if instance._ancien_statut != instance.statut:
            # Créer l'historique du changement de statut
            HistoriquePaiement.objects.create(
                paiement=instance,
                type_action='MODIFICATION',
                ancien_statut=instance._ancien_statut,
                nouveau_statut=instance.statut,
                details=f"Changement de statut: {instance._ancien_statut} → {instance.statut}"
            )

            # Actions spécifiques selon le nouveau statut
            if instance.statut == 'CONFIRME':
                instance.mettre_a_jour_inscription()

                # Activer l'inscription si nécessaire
                inscription = instance.inscription_paiement.inscription
                if inscription.statut == 'PENDING':
                    if instance.inscription_paiement.est_inscrit_autorise():
                        inscription.statut = 'ACTIVE'
                        inscription.save()


@receiver(post_save, sender=InscriptionPaiement)
def inscription_paiement_post_save(sender, instance, created, **kwargs):
    """Actions après création/modification d'un InscriptionPaiement"""

    if created:
        # Mettre à jour le statut initial
        instance.mettre_a_jour_statut()
