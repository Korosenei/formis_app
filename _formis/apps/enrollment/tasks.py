# enrollment/tasks.py

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Candidature, DocumentCandidature
from .utils import (
    envoyer_email_candidature_soumise,
    envoyer_email_candidature_evaluee,
    creer_compte_utilisateur_depuis_candidature,
    nettoyer_candidatures_expirees,
    statistiques_candidatures
)

# Configuration du logger
logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3)
def nettoyer_candidatures_expirees_task(self):
    """Tâche pour nettoyer les candidatures expirées"""
    try:
        logger.info("Début nettoyage candidatures expirées")

        count = nettoyer_candidatures_expirees()

        logger.info(f"Nettoyage terminé: {count} candidatures marquées comme expirées")
        return {
            'success': True,
            'candidatures_expirees': count,
            'message': f'{count} candidatures marquées comme expirées'
        }

    except Exception as e:
        logger.error(f"Erreur nettoyage candidatures expirées: {str(e)}")
        # Retry avec délai exponentiel
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def envoyer_rappels_candidatures_incompletes(self):
    """Envoie des rappels pour les candidatures incomplètes"""
    try:
        logger.info("Début envoi rappels candidatures incomplètes")

        # Candidatures brouillons de plus de 3 jours mais moins de 25 jours
        date_min = timezone.now() - timedelta(days=25)
        date_max = timezone.now() - timedelta(days=3)

        candidatures_incompletes = Candidature.objects.filter(
            statut='BROUILLON',
            created_at__range=[date_min, date_max]
        ).select_related('etablissement', 'filiere', 'niveau')

        emails_envoyes = 0
        emails_echecs = 0

        for candidature in candidatures_incompletes:
            try:
                # Vérifier si un rappel n'a pas déjà été envoyé récemment
                # (on peut ajouter un champ last_reminder_sent si nécessaire)

                if envoyer_email_rappel_candidature_incomplete(candidature):
                    emails_envoyes += 1
                    logger.info(
                        f"Rappel envoyé à {candidature.email} pour candidature {candidature.numero_candidature}")
                else:
                    emails_echecs += 1
                    logger.error(f"Échec rappel pour candidature {candidature.numero_candidature}")

            except Exception as e:
                emails_echecs += 1
                logger.error(f"Erreur envoi rappel candidature {candidature.numero_candidature}: {str(e)}")

        logger.info(f"Rappels terminés: {emails_envoyes} envoyés, {emails_echecs} échecs")
        return {
            'success': True,
            'emails_envoyes': emails_envoyes,
            'emails_echecs': emails_echecs,
            'total_candidatures': len(candidatures_incompletes)
        }

    except Exception as e:
        logger.error(f"Erreur envoi rappels candidatures: {str(e)}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def traiter_candidatures_en_attente(self):
    """Traite les candidatures en attente de traitement"""
    try:
        logger.info("Début traitement candidatures en attente")

        # Marquer comme "en cours d'examen" les candidatures soumises depuis plus d'1 jour
        date_limite = timezone.now() - timedelta(days=1)

        candidatures_a_traiter = Candidature.objects.filter(
            statut='SOUMISE',
            date_soumission__lt=date_limite
        )

        count_mises_a_jour = candidatures_a_traiter.update(
            statut='EN_COURS_EXAMEN',
            date_examen=timezone.now()
        )

        logger.info(f"Traitement terminé: {count_mises_a_jour} candidatures marquées en cours d'examen")
        return {
            'success': True,
            'candidatures_mises_a_jour': count_mises_a_jour
        }

    except Exception as e:
        logger.error(f"Erreur traitement candidatures en attente: {str(e)}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def generer_rapport_candidatures_quotidien(self):
    """Génère un rapport quotidien des candidatures"""
    try:
        logger.info("Génération rapport quotidien candidatures")

        # Statistiques globales
        stats = statistiques_candidatures()

        # Candidatures du jour
        aujourd_hui = timezone.now().date()
        candidatures_jour = Candidature.objects.filter(
            created_at__date=aujourd_hui
        ).count()

        soumissions_jour = Candidature.objects.filter(
            date_soumission__date=aujourd_hui
        ).count()

        evaluations_jour = Candidature.objects.filter(
            date_decision__date=aujourd_hui
        ).count()

        # Candidatures en attente de traitement
        en_attente = Candidature.objects.filter(
            statut='SOUMISE'
        ).count()

        rapport = {
            'date': aujourd_hui.isoformat(),
            'nouvelles_candidatures': candidatures_jour,
            'soumissions': soumissions_jour,
            'evaluations': evaluations_jour,
            'en_attente_traitement': en_attente,
            'statistiques_globales': stats
        }

        # Envoyer le rapport aux administrateurs
        envoyer_rapport_admin(rapport)

        logger.info(f"Rapport quotidien généré: {candidatures_jour} nouvelles candidatures")
        return rapport

    except Exception as e:
        logger.error(f"Erreur génération rapport quotidien: {str(e)}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def creer_comptes_utilisateurs_batch(self, candidatures_ids):
    """Crée des comptes utilisateurs en lot pour les candidatures approuvées"""
    try:
        logger.info(f"Début création comptes utilisateurs batch: {len(candidatures_ids)} candidatures")

        candidatures = Candidature.objects.filter(
            id__in=candidatures_ids,
            statut='APPROUVEE'
        )

        comptes_crees = 0
        echecs = 0

        for candidature in candidatures:
            try:
                # Vérifier si l'utilisateur n'existe pas déjà
                if not User.objects.filter(email=candidature.email).exists():
                    utilisateur = creer_compte_utilisateur_depuis_candidature(candidature)
                    if utilisateur:
                        comptes_crees += 1
                        logger.info(f"Compte créé pour candidature {candidature.numero_candidature}")
                    else:
                        echecs += 1
                else:
                    logger.info(f"Compte existe déjà pour candidature {candidature.numero_candidature}")

            except Exception as e:
                echecs += 1
                logger.error(f"Erreur création compte pour candidature {candidature.numero_candidature}: {str(e)}")

        logger.info(f"Création batch terminée: {comptes_crees} comptes créés, {echecs} échecs")
        return {
            'success': True,
            'comptes_crees': comptes_crees,
            'echecs': echecs,
            'total_traites': len(candidatures)
        }

    except Exception as e:
        logger.error(f"Erreur création comptes batch: {str(e)}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True)
def envoyer_email_candidature_async(self, candidature_id, type_email):
    """Envoie un email de façon asynchrone"""
    try:
        candidature = Candidature.objects.get(id=candidature_id)

        if type_email == 'soumise':
            success = envoyer_email_candidature_soumise(candidature)
        elif type_email == 'evaluee':
            success = envoyer_email_candidature_evaluee(candidature)
        else:
            logger.error(f"Type d'email invalide: {type_email}")
            return {'success': False, 'error': 'Type email invalide'}

        if success:
            logger.info(f"Email {type_email} envoyé avec succès pour candidature {candidature.numero_candidature}")
            return {'success': True, 'message': f'Email {type_email} envoyé'}
        else:
            logger.error(f"Échec envoi email {type_email} pour candidature {candidature.numero_candidature}")
            return {'success': False, 'error': f'Échec envoi email {type_email}'}

    except Candidature.DoesNotExist:
        logger.error(f"Candidature non trouvée: {candidature_id}")
        return {'success': False, 'error': 'Candidature non trouvée'}
    except Exception as e:
        logger.error(f"Erreur envoi email async: {str(e)}")
        raise self.retry(exc=e, countdown=60)


# Fonctions utilitaires pour les tâches

def envoyer_email_rappel_candidature_incomplete(candidature):
    """Envoie un email de rappel pour une candidature incomplète"""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings

    try:
        subject = f"Complétez votre candidature - {candidature.numero_candidature}"

        context = {
            'candidature': candidature,
            'etablissement': candidature.etablissement,
            'filiere': candidature.filiere,
            'nom_complet': candidature.nom_complet(),
            'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
            'jours_restants': 25 - (timezone.now() - candidature.created_at).days
        }

        try:
            # Essayer avec template HTML
            html_message = render_to_string(
                'enrollment/candidature/emails/rappel_candidature_incomplete.html',
                context
            )

            from django.core.mail import EmailMessage
            email = EmailMessage(
                subject=subject,
                body=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[candidature.email],
            )
            email.content_subtype = 'html'
            email.send()

            return True

        except Exception as template_error:
            # Fallback avec email simple
            message = f"""
Bonjour {candidature.nom_complet()},

Votre candidature {candidature.numero_candidature} est en cours mais incomplète.

Formation demandée: {candidature.filiere.nom} - {candidature.niveau.nom}
Établissement: {candidature.etablissement.nom}

Pour finaliser votre candidature, connectez-vous sur notre plateforme et complétez les informations manquantes.

Attention: Les candidatures incomplètes sont automatiquement supprimées après 30 jours.
Il vous reste environ {25 - (timezone.now() - candidature.created_at).days} jours.

Lien: {getattr(settings, 'SITE_URL', 'http://localhost:8000')}

Cordialement,
L'équipe de {candidature.etablissement.nom}
"""

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[candidature.email],
                fail_silently=False,
            )

            return True

    except Exception as e:
        logger.error(f"Erreur envoi rappel candidature {candidature.numero_candidature}: {str(e)}")
        return False


def envoyer_rapport_admin(rapport):
    """Envoie le rapport quotidien aux administrateurs"""
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        # Récupérer les emails des administrateurs
        admins_emails = User.objects.filter(
            role='ADMIN',
            is_active=True
        ).values_list('email', flat=True)

        if not admins_emails:
            logger.warning("Aucun administrateur trouvé pour envoi du rapport")
            return False

        subject = f"Rapport quotidien candidatures - {rapport['date']}"

        message = f"""
Rapport quotidien des candidatures - {rapport['date']}

ACTIVITÉ DU JOUR:
- Nouvelles candidatures créées: {rapport['nouvelles_candidatures']}
- Candidatures soumises: {rapport['soumissions']}
- Candidatures évaluées: {rapport['evaluations']}

ÉTAT ACTUEL:
- En attente de traitement: {rapport['en_attente_traitement']}
- Total candidatures: {rapport['statistiques_globales']['total']}

RÉPARTITION PAR STATUT:
"""

        for statut, stats in rapport['statistiques_globales']['par_statut'].items():
            message += f"- {stats['label']}: {stats['count']} ({stats['pourcentage']}%)\n"

        message += f"""

Ce rapport est généré automatiquement chaque jour.

---
Système de gestion des candidatures
"""

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(admins_emails),
            fail_silently=False,
        )

        logger.info(f"Rapport quotidien envoyé à {len(admins_emails)} administrateurs")
        return True

    except Exception as e:
        logger.error(f"Erreur envoi rapport admin: {str(e)}")
        return False