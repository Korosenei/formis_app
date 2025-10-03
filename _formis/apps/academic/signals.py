# apps/academic/signals.py

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from .models import (
    Departement, Filiere, Niveau, Classe, 
    PeriodeAcademique, Programme
)


@receiver(post_save, sender=Classe)
@receiver(post_delete, sender=Classe)
def update_niveau_stats(sender, instance, **kwargs):
    """Met à jour les statistiques du niveau quand une classe est ajoutée/supprimée"""
    try:
        niveau = instance.niveau
        # Vous pouvez ajouter ici la logique pour mettre à jour les statistiques
        # Par exemple, compter le nombre de classes actives
        pass
    except:
        pass


@receiver(pre_save, sender=PeriodeAcademique)
def validate_periode_courante(sender, instance, **kwargs):
    """S'assurer qu'il n'y a qu'une seule période courante par établissement"""
    if instance.est_courante:
        # Désactiver les autres périodes courantes du même établissement
        PeriodeAcademique.objects.filter(
            etablissement=instance.etablissement,
            est_courante=True
        ).exclude(id=instance.id).update(est_courante=False)


@receiver(post_save, sender=Filiere)
def create_default_programme(sender, instance, created, **kwargs):
    """Créer un programme par défaut pour une nouvelle filière"""
    if created and not hasattr(instance, 'programme'):
        Programme.objects.create(
            filiere=instance,
            nom=f"Programme {instance.nom}",
            description=f"Programme de formation pour la filière {instance.nom}",
            objectifs=f"Objectifs pédagogiques de la filière {instance.nom}",
            competences=f"Compétences à acquérir dans la filière {instance.nom}",
            date_derniere_revision=instance.created_at.date()
        )


@receiver(post_save, sender=Niveau)
@receiver(post_delete, sender=Niveau)
def update_filiere_stats(sender, instance, **kwargs):
    """Met à jour les statistiques de la filière"""
    try:
        filiere = instance.filiere
        # Logique pour mettre à jour les statistiques de la filière
        pass
    except:
        pass


# Signal pour valider la cohérence des données
@receiver(pre_save, sender=Classe)
def validate_classe_data(sender, instance, **kwargs):
    """Valide les données de la classe avant sauvegarde"""
    # Vérifier que l'effectif ne dépasse pas la capacité
    if instance.effectif_actuel > instance.capacite_maximale:
        raise ValidationError(
            "L'effectif actuel ne peut pas dépasser la capacité maximale"
        )
    
    # Vérifier que le niveau appartient à l'établissement
    if instance.niveau.filiere.etablissement != instance.etablissement:
        raise ValidationError(
            "Le niveau sélectionné n'appartient pas à cet établissement"
        )