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

📋 Numéro de candidature : {candidature.numero_candidature}
🎓 Formation : {candidature.filiere.nom} - {candidature.niveau.nom}
🏫 Établissement : {candidature.etablissement.nom}
📅 Date de soumission : {candidature.date_soumission.strftime('%d/%m/%Y à %H:%M')}

════════════════════════════════════════════════════════════════
PROCHAINES ÉTAPES
════════════════════════════════════════════════════════════════

✓ Votre dossier sera examiné dans les prochains jours
✓ Notre équipe vérifiera les documents fournis
✓ Vous recevrez un email dès qu'une décision sera prise

IMPORTANT : Conservez précieusement votre numéro de candidature ({candidature.numero_candidature})
pour toute correspondance avec l'établissement.

════════════════════════════════════════════════════════════════
CONTACT
════════════════════════════════════════════════════════════════

Pour toute question concernant votre candidature :
📧 Email : contact@{candidature.etablissement.nom.lower().replace(' ', '')}.bf
📞 Téléphone : {candidature.etablissement.telephone if hasattr(candidature.etablissement, 'telephone') else 'N/A'}

════════════════════════════════════════════════════════════════

Nous vous remercions de votre confiance et vous souhaitons bonne chance !

Cordialement,
L'équipe de {candidature.etablissement.nom}

---
Ceci est un email automatique, merci de ne pas y répondre directement.
Pour toute question, utilisez les coordonnées ci-dessus.
            """

            # Envoyer l'email
            result = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[candidature.email],
                fail_silently=False
            )

            if result == 1:
                logger.info(
                    f"✅ Email de confirmation envoyé avec succès à {candidature.email} "
                    f"(Candidature: {candidature.numero_candidature})"
                )
                return True
            else:
                logger.error(f"❌ Échec envoi email à {candidature.email}")
                return False

        except Exception as e:
            logger.error(
                f"❌ Erreur lors de l'envoi de l'email de confirmation à {candidature.email}: {str(e)}",
                exc_info=True
            )
            return False

    @staticmethod
    def send_candidature_evaluated(candidature):
        """Envoie un email de notification d'évaluation"""
        try:
            if candidature.statut == 'APPROUVEE':
                subject = f"✅ Candidature Approuvée - {candidature.numero_candidature}"

                message = f"""
Bonjour {candidature.prenom} {candidature.nom},

🎉 Félicitations ! Votre candidature a été APPROUVÉE ! 🎉

════════════════════════════════════════════════════════════════
INFORMATIONS
════════════════════════════════════════════════════════════════

📋 Numéro de candidature : {candidature.numero_candidature}
🎓 Formation : {candidature.filiere.nom} - {candidature.niveau.nom}
🏫 Établissement : {candidature.etablissement.nom}
📅 Date de décision : {candidature.date_decision.strftime('%d/%m/%Y à %H:%M')}

════════════════════════════════════════════════════════════════
PROCHAINES ÉTAPES
════════════════════════════════════════════════════════════════

✓ Un compte utilisateur a été créé pour vous
✓ Vous allez recevoir vos identifiants de connexion par email séparé
✓ Connectez-vous à la plateforme avec vos identifiants
✓ Complétez votre profil si nécessaire
✓ Consultez les informations sur votre inscription

Pour toute information complémentaire, contactez l'établissement.

════════════════════════════════════════════════════════════════

Bienvenue dans notre communauté académique !

Cordialement,
L'équipe de {candidature.etablissement.nom}
                """

            else:  # REJETEE
                subject = f"❌ Candidature Non Retenue - {candidature.numero_candidature}"

                message = f"""
Bonjour {candidature.prenom} {candidature.nom},

Nous avons le regret de vous informer que votre candidature n'a pas été retenue.

════════════════════════════════════════════════════════════════
INFORMATIONS
════════════════════════════════════════════════════════════════

📋 Numéro de candidature : {candidature.numero_candidature}
🎓 Formation : {candidature.filiere.nom} - {candidature.niveau.nom}
🏫 Établissement : {candidature.etablissement.nom}
📅 Date de décision : {candidature.date_decision.strftime('%d/%m/%Y à %H:%M')}
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

            # Envoyer l'email
            result = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[candidature.email],
                fail_silently=False
            )

            if result == 1:
                logger.info(f"✅ Email d'évaluation envoyé à {candidature.email}")
                return True
            else:
                logger.error(f"❌ Échec envoi email d'évaluation à {candidature.email}")
                return False

        except Exception as e:
            logger.error(f"❌ Erreur envoi email évaluation: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def send_account_created(user, password, establishment):
        """Envoie les informations de connexion au nouvel utilisateur"""
        try:
            subject = f"🔑 Vos identifiants de connexion - {establishment.nom}"

            message = f"""
Bonjour {user.prenom} {user.nom},

Votre compte a été créé avec succès suite à l'approbation de votre candidature ! 🎉

════════════════════════════════════════════════════════════════
VOS IDENTIFIANTS DE CONNEXION
════════════════════════════════════════════════════════════════

👤 Matricule : {user.matricule}
📧 Email : {user.email}
🔒 Mot de passe temporaire : {password}

════════════════════════════════════════════════════════════════
⚠️ IMPORTANT - SÉCURITÉ
════════════════════════════════════════════════════════════════

Pour des raisons de sécurité, veuillez IMPÉRATIVEMENT changer ce mot de 
passe lors de votre première connexion.

════════════════════════════════════════════════════════════════
ACCÈS À LA PLATEFORME
════════════════════════════════════════════════════════════════

🌐 Lien de connexion : {settings.SITE_URL}/accounts/login/

════════════════════════════════════════════════════════════════
PROCHAINES ÉTAPES
════════════════════════════════════════════════════════════════

1️⃣ Connectez-vous avec vos identifiants
2️⃣ Changez votre mot de passe temporaire
3️⃣ Complétez votre profil
4️⃣ Consultez vos informations académiques

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

            # Envoyer l'email
            result = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )

            if result == 1:
                logger.info(f"✅ Email de création de compte envoyé à {user.email}")
                return True
            else:
                logger.error(f"❌ Échec envoi email compte à {user.email}")
                return False

        except Exception as e:
            logger.error(f"❌ Erreur envoi email compte: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def send_inscription_confirmee(inscription):
        """
        Envoie un email de confirmation d'inscription active

        Args:
            inscription: Instance de Inscription
        """
        try:
            apprenant = inscription.apprenant
            candidature = inscription.candidature

            subject = f"✅ Inscription confirmée - {candidature.etablissement.nom}"

            context = {
                'apprenant': apprenant,
                'inscription': inscription,
                'candidature': candidature,
                'etablissement': candidature.etablissement,
                'filiere': candidature.filiere,
                'niveau': candidature.niveau,
                'classe': inscription.classe_assignee,
                'annee_academique': candidature.annee_academique,
            }

            # Email HTML
            html_message = render_to_string(
                'enrollment/inscription/emails/inscription_confirmee.html',
                context
            )

            # Email texte simple
            text_message = f"""
    Bonjour {apprenant.prenom} {apprenant.nom},

    Félicitations ! Votre inscription est maintenant confirmée.

    INFORMATIONS DE VOTRE INSCRIPTION
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Numéro d'inscription : {inscription.numero_inscription}
    Formation : {candidature.filiere.nom}
    Niveau : {candidature.niveau.nom}
    {f"Classe : {inscription.classe_assignee.nom}" if inscription.classe_assignee else ""}
    Année académique : {candidature.annee_academique.nom}

    PROCHAINES ÉTAPES
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    1. Connectez-vous à votre espace apprenant
    2. Consultez votre emploi du temps
    3. Accédez à vos cours et ressources pédagogiques

    Vous pouvez vous connecter dès maintenant sur :
    {settings.SITE_URL}/accounts/login/

    Vos identifiants de connexion :
    Email : {apprenant.email}
    (Utilisez le mot de passe qui vous a été envoyé précédemment)

    Pour toute question, n'hésitez pas à nous contacter.

    Cordialement,
    L'équipe de {candidature.etablissement.nom}
                """.strip()

            # Envoi de l'email
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[apprenant.email]
            )
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)

            logger.info(f"Email inscription confirmée envoyé à {apprenant.email}")
            return True

        except Exception as e:
            logger.error(f"Erreur envoi email inscription confirmée: {str(e)}", exc_info=True)
            return False

