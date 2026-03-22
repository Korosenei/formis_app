# apps/enrollment/managers.py
import logging
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailCandidatureManager:
    """Gestionnaire d'emails pour les candidatures"""

    @staticmethod
    def send_candidature_submitted(candidature):
        """Envoie un email de confirmation de soumission"""
        try:
            subject = f"Confirmation de soumission - Candidature {candidature.numero_candidature}"

            message = f"""
Bonjour {candidature.prenom} {candidature.nom},

Votre candidature a été soumise avec succès !

════════════════════════════════════════════════════════════════
INFORMATIONS DE VOTRE CANDIDATURE
════════════════════════════════════════════════════════════════

Numéro de candidature : {candidature.numero_candidature}
Formation : {candidature.filiere.nom} - {candidature.niveau.nom}
Établissement : {candidature.etablissement.nom}
Date de soumission : {candidature.date_soumission.strftime('%d/%m/%Y à %H:%M')}

════════════════════════════════════════════════════════════════
PROCHAINES ÉTAPES
════════════════════════════════════════════════════════════════

- Votre dossier sera examiné dans les prochains jours
- Notre équipe vérifiera les documents fournis
- Vous recevrez un email dès qu'une décision sera prise

IMPORTANT : Conservez précieusement votre numéro de candidature ({candidature.numero_candidature})
pour toute correspondance avec l'établissement.

════════════════════════════════════════════════════════════════

Nous vous remercions de votre confiance et vous souhaitons bonne chance !

Cordialement,
L'équipe de {candidature.etablissement.nom}

---
Ceci est un email automatique, merci de ne pas y répondre directement.
            """

            result = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[candidature.email],
                fail_silently=False
            )

            if result == 1:
                logger.info(
                    f"[OK] Email de confirmation envoye a {candidature.email} "
                    f"(Candidature: {candidature.numero_candidature})"
                )
                return True
            else:
                logger.error(f"[ERROR] Echec envoi email a {candidature.email}")
                return False

        except Exception as e:
            logger.error(
                f"[ERROR] Erreur envoi email confirmation a {candidature.email}: {str(e)}",
                exc_info=True
            )
            return False

    @staticmethod
    def send_candidature_evaluated(candidature):
        """Envoie un email de notification d'évaluation (approuvée ou rejetée)"""
        try:
            if candidature.statut == 'APPROUVEE':
                subject = f"[APPROUVEE] Candidature {candidature.numero_candidature}"

                message = f"""
Bonjour {candidature.prenom} {candidature.nom},

Félicitations ! Votre candidature a été APPROUVÉE !

════════════════════════════════════════════════════════════════
INFORMATIONS
════════════════════════════════════════════════════════════════

Numéro de candidature : {candidature.numero_candidature}
Formation : {candidature.filiere.nom} - {candidature.niveau.nom}
Établissement : {candidature.etablissement.nom}
Date de décision : {candidature.date_decision.strftime('%d/%m/%Y à %H:%M')}

════════════════════════════════════════════════════════════════
VOTRE COMPTE A ÉTÉ CRÉÉ
════════════════════════════════════════════════════════════════

Un compte apprenant a été créé automatiquement pour vous.
Vous allez recevoir vos identifiants de connexion dans un email séparé 
dans quelques instants.

════════════════════════════════════════════════════════════════
PROCHAINES ÉTAPES
════════════════════════════════════════════════════════════════

1. Consultez l'email contenant vos identifiants
2. Connectez-vous à la plateforme
3. Complétez votre profil si nécessaire
4. Consultez votre emploi du temps et vos cours

════════════════════════════════════════════════════════════════

Bienvenue dans notre communauté académique !

Cordialement,
L'équipe de {candidature.etablissement.nom}
                """

            else:  # REJETEE
                subject = f"[REJETEE] Candidature {candidature.numero_candidature}"

                message = f"""
Bonjour {candidature.prenom} {candidature.nom},

Nous avons le regret de vous informer que votre candidature n'a pas été retenue.

════════════════════════════════════════════════════════════════
INFORMATIONS
════════════════════════════════════════════════════════════════

Numéro de candidature : {candidature.numero_candidature}
Formation : {candidature.filiere.nom} - {candidature.niveau.nom}
Établissement : {candidature.etablissement.nom}
Date de décision : {candidature.date_decision.strftime('%d/%m/%Y à %H:%M')}
"""

                if candidature.motif_rejet:
                    message += f"""
════════════════════════════════════════════════════════════════
MOTIF
════════════════════════════════════════════════════════════════

{candidature.motif_rejet}

"""

                message += f"""
════════════════════════════════════════════════════════════════

Nous vous encourageons à postuler à nouveau lors des prochaines sessions
de candidature.

Pour plus d'informations, n'hésitez pas à contacter l'établissement.

Cordialement,
L'équipe de {candidature.etablissement.nom}
                """

            result = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[candidature.email],
                fail_silently=False
            )

            if result == 1:
                logger.info(f"[OK] Email evaluation envoye a {candidature.email}")
                return True
            else:
                logger.error(f"[ERROR] Echec envoi email evaluation a {candidature.email}")
                return False

        except Exception as e:
            logger.error(f"[ERROR] Erreur envoi email evaluation: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def send_account_created(user, password, establishment):
        """Envoie les identifiants de connexion au nouvel apprenant"""
        try:
            subject = f"Vos identifiants de connexion - {establishment.nom}"

            message = f"""
Bonjour {user.prenom} {user.nom},

Votre compte apprenant a été créé avec succès suite à l'approbation de votre candidature !

════════════════════════════════════════════════════════════════
VOS IDENTIFIANTS DE CONNEXION
════════════════════════════════════════════════════════════════

Matricule : {user.matricule}
Email : {user.email}
Mot de passe temporaire : {password}

════════════════════════════════════════════════════════════════
IMPORTANT - SÉCURITÉ
════════════════════════════════════════════════════════════════

Pour des raisons de sécurité, veuillez IMPÉRATIVEMENT changer ce mot de 
passe lors de votre première connexion.

════════════════════════════════════════════════════════════════
ACCÈS À LA PLATEFORME
════════════════════════════════════════════════════════════════

Lien de connexion : {settings.SITE_URL}/accounts/login/

════════════════════════════════════════════════════════════════
PROCHAINES ÉTAPES
════════════════════════════════════════════════════════════════

1. Connectez-vous avec vos identifiants
2. Changez votre mot de passe temporaire
3. Complétez votre profil
4. Consultez vos informations académiques

════════════════════════════════════════════════════════════════

Si vous rencontrez des difficultés, contactez le support technique 
de votre établissement.

Bienvenue dans notre communauté académique !

Cordialement,
L'équipe de {establishment.nom}

---
Ceci est un email automatique contenant des informations sensibles.
Merci de le supprimer après avoir changé votre mot de passe.
            """

            result = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )

            if result == 1:
                logger.info(f"[OK] Email identifiants envoye a {user.email}")
                return True
            else:
                logger.error(f"[ERROR] Echec envoi email identifiants a {user.email}")
                return False

        except Exception as e:
            logger.error(f"[ERROR] Erreur envoi email identifiants: {str(e)}", exc_info=True)
            return False


# Fonctions helper
def envoyer_email_candidature_soumise(candidature):
    """Wrapper pour compatibilité"""
    return EmailCandidatureManager.send_candidature_submitted(candidature)


def envoyer_email_candidature_evaluee(candidature):
    """Wrapper pour compatibilité"""
    return EmailCandidatureManager.send_candidature_evaluated(candidature)


def envoyer_email_compte_cree(user, password, establishment):
    """Wrapper pour compatibilité"""
    return EmailCandidatureManager.send_account_created(user, password, establishment)