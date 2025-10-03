# apps/core/models.py
from django.db import models
from django.utils import timezone
import uuid

class BaseModel(models.Model):
    """Modèle de base avec champs communs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        abstract = True

class TimestampedModel(models.Model):
    """Modèle avec timestamps uniquement"""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        abstract = True

class SoftDeleteModel(models.Model):
    """Modèle avec suppression logique"""
    is_deleted = models.BooleanField(default=False, verbose_name="Supprimé")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Supprimé le")
    deleted_by = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_%(model_name)s',
        verbose_name="Supprimé par"
    )

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        """Effectue une suppression logique"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()

    def restore(self):
        """Restaure un élément supprimé logiquement"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()

class AuditModel(BaseModel, SoftDeleteModel):
    """Modèle avec audit complet"""
    created_by = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_%(model_name)s',
        verbose_name="Créé par"
    )
    updated_by = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_%(model_name)s',
        verbose_name="Modifié par"
    )

    class Meta:
        abstract = True
