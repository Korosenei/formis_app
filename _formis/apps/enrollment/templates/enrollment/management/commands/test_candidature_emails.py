# enrollment/management/commands/test_candidature_emails.py

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_test_mail
from django.conf import settings

from enrollment.models import Candidature
from enrollment.utils import (
    envoyer_email_candidature_soumise,
    envoyer_email_candidature_evaluee,
    envoyer_informations_connexion
)


class Command(BaseCommand):
    help = 'Teste la configuration email avec les templates de candidature'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email de destination pour le test'
        )

        parser.add_argument(
            '--type',
            type=str,
            default='all',
            choices=['all', 'soumise', 'approuvee', 'rejetee', 'welcome', 'config'],
            help='Type d\'email à tester'
        )

    def handle(self, *args, **options):
        email_dest = options['email']
        type_test = options['type']

        self.stdout.write(f"Test d'emails vers: {email_dest}")
        self.stdout.write(f"Configuration SMTP: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")

        try:
            if type_test in ['all', 'config']:
                self.test_configuration_email(email_dest)

            if type_test in ['all', 'soumise', 'approuvee', 'rejetee']:
                self.test_emails_candidature(email_dest, type_test)

            if type_test in ['all', 'welcome']:
                self.test_email_welcome(email_dest)

        except Exception as e:
            raise CommandError(f"Erreur lors du test: {str(e)}")

    def test_configuration_email(self, email_dest):
        """Teste la configuration email de base"""
        self.stdout.write("\n=== TEST CONFIGURATION EMAIL ===")

        try:
            send_test_mail(['admin@example.com'], email_dest)
            self.stdout.write(self.style.SUCCESS("✓ Configuration email OK"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Erreur configuration: {str(e)}"))

    def test_emails_candidature(self, email_dest, type_test):
        """Teste les emails de candidature"""
        self.stdout.write("\n=== TEST EMAILS CANDIDATURE ===")

        # Créer une candidature de test
        try:
            candidature = self.creer_candidature_test(email_dest)

            if type_test in ['all', 'soumise']:
                candidature.statut = 'SOUMISE'
                candidature.save()

                if envoyer_email_candidature_soumise(candidature):
                    self.stdout.write(self.style.SUCCESS("✓ Email candidature soumise envoyé"))
                else:
                    self.stdout.write(self.style.ERROR("✗ Échec email candidature soumise"))

            if type_test in ['all', 'approuvee']:
                candidature.statut = 'APPROUVEE'
                candidature.save()

                if envoyer_email_candidature_evaluee(candidature):
                    self.stdout.write(self.style.SUCCESS("✓ Email candidature approuvée envoyé"))
                else:
                    self.stdout.write(self.style.ERROR("✗ Échec email candidature approuvée"))

            if type_test in ['all', 'rejetee']:
                candidature.statut = 'REJETEE'
                candidature.motif_rejet = "Test de rejet pour validation email"
                candidature.save()

                if envoyer_email_candidature_evaluee(candidature):
                    self.stdout.write(self.style.SUCCESS("✓ Email candidature rejetée envoyé"))
                else:
                    self.stdout.write(self.style.ERROR("✗ Échec email candidature rejetée"))

            # Nettoyer
            candidature.delete()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur test candidature: {str(e)}"))

    def test_email_welcome(self, email_dest):
        """Teste l'email de bienvenue"""
        self.stdout.write("\n=== TEST EMAIL BIENVENUE ===")

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # Créer utilisateur temporaire
            user_test = User(
                username='test_user',
                email=email_dest,
                nom='Test',
                prenom='Utilisateur'
            )

            if envoyer_informations_connexion(user_test, 'MotDePasseTest123'):
                self.stdout.write(self.style.SUCCESS("✓ Email de bienvenue envoyé"))
            else:
                self.stdout.write(self.style.ERROR("✗ Échec email de bienvenue"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur test bienvenue: {str(e)}"))

    def creer_candidature_test(self, email):
        """Crée une candidature de test"""
        from establishments.models import Etablissement, AnneeAcademique
        from academic.models import Filiere, Niveau

        # Utiliser les premiers objets disponibles
        etablissement = Etablissement.objects.first()
        filiere = Filiere.objects.first()
        niveau = Niveau.objects.first()
        annee = AnneeAcademique.objects.first()

        if not all([etablissement, filiere, niveau, annee]):
            raise CommandError("Données de test manquantes (établissement, filière, niveau, année)")

        return Candidature.objects.create(
            etablissement=etablissement,
            filiere=filiere,
            niveau=niveau,
            annee_academique=annee,
            prenom='Test',
            nom='Candidature',
            email=email,
            telephone='+22670000000',
            date_naissance='2000-01-01',
            lieu_naissance='Test City',
            genre='M',
            adresse='Adresse de test',
            statut='BROUILLON'
        )