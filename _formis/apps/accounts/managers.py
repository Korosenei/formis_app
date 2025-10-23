# apps/accounts/managers.py

"""
Gestionnaire d'envoi d'emails pour le système de comptes utilisateurs
"""

import logging
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone

# Configuration du logger
logger = logging.getLogger(__name__)


class EmailManager:
    """Gestionnaire centralisé pour l'envoi d'emails"""

    @staticmethod
    def send_account_creation_email(user, password, establishment, created_by=None):
        """
        Envoie un email de création de compte à l'utilisateur
        """
        try:
            # Contexte pour le template
            context = {
                'user': user,
                'password': password,
                'establishment': establishment,
                'login_url': f"{settings.SITE_URL}/accounts/login/",
                'created_by': created_by,
                'year': timezone.now().year,
            }

            # Sujet de l'email
            subject = f"Création de votre compte - {establishment.nom}"

            # Message texte simple (fallback)
            text_message = f"""
Bonjour {user.prenom} {user.nom},

Votre compte a été créé avec succès sur la plateforme FORMIS de {establishment.nom}.

Vos identifiants de connexion :
- Matricule : {user.matricule}
- Email : {user.email}
- Mot de passe temporaire : {password}

⚠️ IMPORTANT : Veuillez changer ce mot de passe lors de votre première connexion.

Lien de connexion : {context['login_url']}

Si vous avez des questions, contactez l'administration.

Cordialement,
L'équipe {establishment.nom}
            """

            # Essayer d'utiliser le template HTML s'il existe
            try:
                html_message = render_to_string('email/account_created.html', context)
            except Exception as e:
                logger.warning(f"Template HTML introuvable, utilisation du texte brut : {e}")
                html_message = None

            # Envoi de l'email
            if html_message:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=strip_tags(html_message),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email],
                )
                email.attach_alternative(html_message, "text/html")
                email.send(fail_silently=False)
            else:
                send_mail(
                    subject=subject,
                    message=text_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False
                )

            logger.info(
                f"Email de création de compte envoyé avec succès à {user.email} "
                f"(Matricule: {user.matricule}, Rôle: {user.role})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Erreur lors de l'envoi de l'email de création à {user.email}: {str(e)}",
                exc_info=True
            )
            return False

    @staticmethod
    def send_password_recovery_email(user, establishment, reset_url):
        """
        Envoie un email de récupération de compte
        """
        try:
            subject = f"Récupération de votre compte - {establishment.nom}"

            message = f"""
Bonjour {user.prenom} {user.nom},

Vous avez demandé la réinitialisation de votre mot de passe.

Cliquez sur le lien ci-dessous pour créer un nouveau mot de passe :
{reset_url}

⚠️ Ce lien est valable pendant 24 heures.

Si vous n'avez pas demandé cette réinitialisation, ignorez ce message.

Cordialement,
L'équipe {establishment.nom}
            """

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )

            logger.info(
                f"Email de récupération envoyé avec succès à {user.email} "
                f"(Matricule: {user.matricule})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Erreur lors de l'envoi de l'email de récupération à {user.email}: {str(e)}",
                exc_info=True
            )
            return False

    @staticmethod
    def send_password_changed_email(user, establishment, ip_address=None):
        """
        Envoie un email de confirmation de changement de mot de passe
        """
        try:
            subject = f"Modification de votre mot de passe - {establishment.nom}"

            message = f"""
Bonjour {user.prenom} {user.nom},

Votre mot de passe a été modifié avec succès.

Date : {timezone.now().strftime('%d/%m/%Y à %H:%M')}
"""
            if ip_address:
                message += f"Adresse IP : {ip_address}\n"

            message += f"""

Si vous n'êtes pas à l'origine de cette modification, contactez immédiatement l'administration.

Cordialement,
L'équipe {establishment.nom}
            """

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )

            logger.info(
                f"Email de confirmation de changement de mot de passe envoyé à {user.email} "
                f"(Matricule: {user.matricule})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Erreur lors de l'envoi de l'email de confirmation à {user.email}: {str(e)}",
                exc_info=True
            )
            return False

    @staticmethod
    def send_account_reactivation_email(user, establishment):
        """
        Envoie un email lors de la réactivation d'un compte
        """
        try:
            subject = f"Réactivation de votre compte - {establishment.nom}"

            message = f"""
Bonjour {user.prenom} {user.nom},

Votre compte sur la plateforme FORMIS de {establishment.nom} a été réactivé.

Vous pouvez maintenant vous connecter avec vos identifiants habituels :
- Matricule : {user.matricule}
- Email : {user.email}

Lien de connexion : {settings.SITE_URL}/accounts/login/

Si vous avez des questions, contactez l'administration.

Cordialement,
L'équipe {establishment.nom}
            """

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )

            logger.info(
                f"Email de réactivation envoyé avec succès à {user.email} "
                f"(Matricule: {user.matricule})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Erreur lors de l'envoi de l'email de réactivation à {user.email}: {str(e)}",
                exc_info=True
            )
            return False

    @staticmethod
    def send_account_deactivation_email(user, establishment, reason=None):
        """
        Envoie un email lors de la désactivation d'un compte
        """
        try:
            subject = f"Désactivation de votre compte - {establishment.nom}"

            message = f"""
Bonjour {user.prenom} {user.nom},

Votre compte sur la plateforme FORMIS de {establishment.nom} a été désactivé.

Matricule : {user.matricule}
Date : {timezone.now().strftime('%d/%m/%Y à %H:%M')}
"""
            if reason:
                message += f"\nRaison : {reason}"

            message += f"""

Si vous pensez qu'il s'agit d'une erreur, veuillez contacter l'administration de votre établissement.

Cordialement,
L'équipe {establishment.nom}
            """

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )

            logger.info(
                f"Email de désactivation envoyé avec succès à {user.email} "
                f"(Matricule: {user.matricule})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Erreur lors de l'envoi de l'email de désactivation à {user.email}: {str(e)}",
                exc_info=True
            )
            return False


# Fonctions helper pour utilisation directe
def send_account_creation_email(user, password, establishment, created_by=None):
    """Wrapper pour compatibilité"""
    return EmailManager.send_account_creation_email(user, password, establishment, created_by)


def send_password_recovery_email(user, establishment, reset_url):
    """Wrapper pour compatibilité"""
    return EmailManager.send_password_recovery_email(user, establishment, reset_url)


def send_password_changed_email(user, establishment, ip_address=None):
    """Wrapper pour compatibilité"""
    return EmailManager.send_password_changed_email(user, establishment, ip_address)


def send_account_reactivation_email(user, establishment):
    """Wrapper pour compatibilité"""
    return EmailManager.send_account_reactivation_email(user, establishment)


def send_account_deactivation_email(user, establishment, reason=None):
    """Wrapper pour compatibilité"""
    return EmailManager.send_account_deactivation_email(user, establishment, reason)