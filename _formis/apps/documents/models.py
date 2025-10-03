from django.db import models
from django.utils import timezone
import uuid


class DemandeDocument(models.Model):
    """Modèle de base avec champs communs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        abstract = True