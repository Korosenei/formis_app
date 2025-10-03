from django.db import models
from apps.accounts.models import Utilisateur

class Notification(models.Model):
    """Modèle pour les notifications utilisateur"""
    user = models.ForeignKey(
        Utilisateur, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    icon = models.CharField(max_length=50, default='fa-info-circle')
    url = models.URLField(blank=True, null=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user} - {self.title}"


class Message(models.Model):
    """Modèle pour les messages entre utilisateurs"""
    sender = models.ForeignKey(
        Utilisateur, 
        on_delete=models.CASCADE, 
        related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        Utilisateur, 
        on_delete=models.CASCADE, 
        related_name='received_messages'
    )
    subject = models.CharField(max_length=200)
    content = models.TextField()
    read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.sender} à {self.recipient}: {self.subject}"
    
