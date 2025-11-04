# apps/enrollment/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Candidature
from apps.accounts.models import Utilisateur, ProfilApprenant
from apps.accounts.managers import send_account_creation_email
from apps.accounts.views import generate_password

import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Candidature)
def creer_compte_apprenant_apres_approbation(sender, instance, created, **kwargs):
    """
    Crée automatiquement un compte apprenant lorsqu'une candidature est approuvée
    """
    # Vérifier si la candidature vient d'être approuvée
    if not created and instance.statut == 'APPROUVEE':
        # Vérifier si un compte n'existe pas déjà pour cet email
        if Utilisateur.objects.filter(email=instance.email).exists():
            logger.info(f"Compte existant pour {instance.email}, pas de création")
            return

        try:
            with transaction.atomic():
                # Générer un mot de passe temporaire
                temp_password = generate_password()

                # Créer l'utilisateur apprenant
                apprenant = Utilisateur.objects.create(
                    role='APPRENANT',
                    prenom=instance.prenom,
                    nom=instance.nom,
                    email=instance.email,
                    date_naissance=instance.date_naissance,
                    lieu_naissance=instance.lieu_naissance,
                    genre=instance.genre,
                    telephone=instance.telephone,
                    adresse=instance.adresse,
                    etablissement=instance.etablissement,
                    departement=instance.filiere.departement,
                    est_actif=True,
                    cree_par=instance.examine_par
                )

                # Définir le mot de passe
                apprenant.set_password(temp_password)
                apprenant.save()

                logger.info(f"✅ Compte apprenant créé: {apprenant.matricule} - {apprenant.email}")

                # Créer le profil apprenant
                profil = ProfilApprenant.objects.create(
                    utilisateur=apprenant,
                    niveau_actuel=instance.niveau,
                    annee_academique=instance.annee_academique,
                    statut_paiement='EN_ATTENTE',
                    nom_pere=instance.nom_pere,
                    telephone_pere=instance.telephone_pere,
                    nom_mere=instance.nom_mere,
                    telephone_mere=instance.telephone_mere,
                    nom_tuteur=instance.nom_tuteur,
                    telephone_tuteur=instance.telephone_tuteur,
                )

                logger.info(f"✅ Profil apprenant créé pour {apprenant.matricule}")

                # Envoyer l'email avec les identifiants
                email_sent = send_account_creation_email(
                    user=apprenant,
                    password=temp_password,
                    establishment=instance.etablissement,
                    created_by=instance.examine_par
                )

                if email_sent:
                    logger.info(f"✅ Email envoyé à {apprenant.email}")
                else:
                    logger.warning(f"⚠️ Échec envoi email à {apprenant.email}")
                    logger.warning(f"   Mot de passe: {temp_password}")

        except Exception as e:
            logger.error(f"❌ Erreur création compte apprenant: {str(e)}", exc_info=True)
            raise
