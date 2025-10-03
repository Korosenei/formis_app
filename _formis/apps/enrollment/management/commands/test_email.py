from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from ...models import Candidature
from ...utils import (
    envoyer_email_candidature_soumise,
    envoyer_email_candidature_evaluee,
    envoyer_informations_connexion
)
import logging

logger = logging.getLogger('enrollment')


class Command(BaseCommand):
    help = 'Test l\'envoi d\'emails pour le système de candidature'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['simple', 'candidature', 'evaluation', 'connexion'],
            default='simple',
            help='Type de test email à envoyer'
        )
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Adresse email de destination'
        )
        parser.add_argument(
            '--candidature-id',
            type=str,
            help='ID de la candidature pour les tests spécifiques'
        )

    def handle(self, *args, **options):
        email_type = options['type']
        dest_email = options['email']
        candidature_id = options.get('candidature_id')

        self.stdout.write(
            self.style.SUCCESS(f'Test d\'envoi d\'email de type "{email_type}" vers {dest_email}')
        )

        try:
            if email_type == 'simple':
                success = self.test_simple_email(dest_email)
            elif email_type == 'candidature':
                success = self.test_candidature_email(dest_email, candidature_id)
            elif email_type == 'evaluation':
                success = self.test_evaluation_email(dest_email, candidature_id)
            elif email_type == 'connexion':
                success = self.test_connexion_email(dest_email)

            if success:
                self.stdout.write(
                    self.style.SUCCESS('Email envoyé avec succès!')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Échec de l\'envoi de l\'email')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erreur: {str(e)}')
            )
            logger.error(f'Erreur test email: {e}', exc_info=True)

    def test_simple_email(self, dest_email):
        """Test d'envoi d'email simple"""
        try:
            subject = 'Test d\'envoi d\'email - Système de candidature'
            message = '''
            Bonjour,

            Ceci est un email de test pour vérifier la configuration du système d'envoi d'emails.

            Si vous recevez cet email, la configuration fonctionne correctement.

            Cordialement,
            L'équipe technique
            '''

            result = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
                recipient_list=[dest_email],
                fail_silently=False,
            )

            return result == 1

        except Exception as e:
            logger.error(f'Erreur test simple email: {e}')
            return False

    def test_candidature_email(self, dest_email, candidature_id):
        """Test d'email de candidature soumise"""
        if not candidature_id:
            self.stdout.write(
                self.style.ERROR('L\'ID de candidature est requis pour ce test')
            )
            return False

        try:
            candidature = Candidature.objects.get(pk=candidature_id)
            return envoyer_email_candidature_soumise(candidature)

        except Candidature.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Candidature {candidature_id} non trouvée')
            )
            return False

    def test_evaluation_email(self, dest_email, candidature_id):
        """Test d'email d'évaluation de candidature"""
        if not candidature_id:
            self.stdout.write(
                self.style.ERROR('L\'ID de candidature est requis pour ce test')
            )
            return False

        try:
            candidature = Candidature.objects.get(pk=candidature_id)
            return envoyer_email_candidature_evaluee(candidature)

        except Candidature.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Candidature {candidature_id} non trouvée')
            )
            return False

    def test_connexion_email(self, dest_email):
        """Test d'email d'informations de connexion"""
        try:
            # Créer un utilisateur fictif pour le test
            from django.contrib.auth import get_user_model

            User = get_user_model()

            # Utiliser un utilisateur existant ou créer un utilisateur de test
            try:
                user = User.objects.get(email=dest_email)
            except User.DoesNotExist:
                # Créer un utilisateur temporaire pour le test
                user = User(
                    username='test_user',
                    email=dest_email,
                    first_name='Test',
                    last_name='User'
                )
                # Ne pas sauvegarder en base, juste pour le test

            return envoyer_informations_connexion(user, 'password123')

        except Exception as e:
            logger.error(f'Erreur test email connexion: {e}')
            return False

    def test_configuration(self):
        """Test de la configuration email"""
        self.stdout.write('Configuration email actuelle:')
        self.stdout.write(f'  EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'  EMAIL_HOST: {settings.EMAIL_HOST}')
        self.stdout.write(f'  EMAIL_PORT: {settings.EMAIL_PORT}')
        self.stdout.write(f'  EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}')
        self.stdout.write(f'  EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}')
        self.stdout.write(f'  DEFAULT_FROM_EMAIL: {getattr(settings, "DEFAULT_FROM_EMAIL", "Non défini")}')
