"""
Commande Django pour tester l'envoi d'emails

Structure du fichier :
apps/accounts/
    management/
        __init__.py
        commands/
            __init__.py
            test_email.py  <- Ce fichier

Usage : python manage.py test_email
"""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import traceback
import smtplib
from email.mime.text import MIMEText


class Command(BaseCommand):
    help = 'Test l\'envoi d\'emails et diagnostique la configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email destinataire (par défaut: leandrebenilde07@gmail.com)',
        )
        parser.add_argument(
            '--test-smtp',
            action='store_true',
            help='Test SMTP direct avec debug',
        )
        parser.add_argument(
            '--test-user',
            action='store_true',
            help='Test avec un utilisateur de la base',
        )

    def handle(self, *args, **options):
        email = options.get('email') or 'leandrebenilde07@gmail.com'

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("🚀 TEST D'ENVOI D'EMAIL FORMIS"))
        self.stdout.write("=" * 60 + "\n")

        # Afficher la configuration
        self.show_configuration()

        # Test simple
        if not options['test_smtp'] and not options['test_user']:
            self.test_simple_email(email)

        # Test SMTP direct
        if options['test_smtp']:
            self.test_smtp_connection()

        # Test avec utilisateur
        if options['test_user']:
            self.test_with_user()

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ FIN DES TESTS"))
        self.stdout.write("=" * 60 + "\n")

    def show_configuration(self):
        """Affiche la configuration email actuelle"""
        self.stdout.write("\n📋 CONFIGURATION EMAIL ACTUELLE :")
        self.stdout.write("-" * 60)

        config = {
            'Backend': settings.EMAIL_BACKEND,
            'Host': settings.EMAIL_HOST,
            'Port': settings.EMAIL_PORT,
            'User': settings.EMAIL_HOST_USER,
            'Use TLS': settings.EMAIL_USE_TLS,
            'Use SSL': settings.EMAIL_USE_SSL,
            'From': settings.DEFAULT_FROM_EMAIL,
        }

        for key, value in config.items():
            self.stdout.write(f"  • {key:12} : {value}")

        # Vérifier le mot de passe (sans l'afficher)
        if hasattr(settings, 'EMAIL_HOST_PASSWORD') and settings.EMAIL_HOST_PASSWORD:
            self.stdout.write(f"  • {'Password':12} : {'*' * len(settings.EMAIL_HOST_PASSWORD)} (configuré)")
        else:
            self.stdout.write(self.style.ERROR(f"  • {'Password':12} : ❌ NON CONFIGURÉ"))

        self.stdout.write("")

    def test_simple_email(self, email):
        """Test d'envoi simple"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📧 TEST 1 : Envoi d'email simple")
        self.stdout.write("=" * 60 + "\n")

        try:
            self.stdout.write(f"Envoi vers : {email}")

            result = send_mail(
                subject='🧪 Test Email FORMIS',
                message='''Bonjour,

Ceci est un email de test depuis la plateforme FORMIS.

Si vous recevez ce message, cela signifie que :
✅ La configuration email est correcte
✅ Le serveur SMTP répond
✅ L'authentification fonctionne

Date du test : {date}

Cordialement,
L'équipe FORMIS
'''.format(date=__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M:%S')),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            if result == 1:
                self.stdout.write(self.style.SUCCESS("\n✅ Email envoyé avec succès !"))
                self.stdout.write(self.style.WARNING(f"\n⚠️  Vérifiez la boîte {email}"))
                self.stdout.write(self.style.WARNING("⚠️  N'oubliez pas de vérifier les SPAMS !"))
            else:
                self.stdout.write(self.style.ERROR("\n❌ L'email n'a pas été envoyé (result = 0)"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ ERREUR lors de l'envoi :"))
            self.stdout.write(self.style.ERROR(f"   Type : {type(e).__name__}"))
            self.stdout.write(self.style.ERROR(f"   Message : {str(e)}"))

            self.stdout.write("\n🔍 SOLUTIONS POSSIBLES :")
            self.stdout.write("   1. Vérifiez que le mot de passe est un 'mot de passe d'application'")
            self.stdout.write("   2. Activez la validation en deux étapes sur Gmail")
            self.stdout.write("   3. Allez sur : https://myaccount.google.com/security")
            self.stdout.write("   4. Créez un mot de passe d'application pour 'Mail' ou 'Django'")

            if self.verbosity >= 2:
                self.stdout.write("\nTraceback complet :")
                traceback.print_exc()

    def test_smtp_connection(self):
        """Test de connexion SMTP directe avec debug"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("🔌 TEST 2 : Connexion SMTP directe")
        self.stdout.write("=" * 60 + "\n")

        try:
            self.stdout.write("Connexion au serveur SMTP...")
            server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10)

            if self.verbosity >= 2:
                server.set_debuglevel(1)

            self.stdout.write(self.style.SUCCESS("✅ Connexion établie"))

            self.stdout.write("\nDémarrage TLS...")
            server.starttls()
            self.stdout.write(self.style.SUCCESS("✅ TLS activé"))

            self.stdout.write(f"\nAuthentification avec {settings.EMAIL_HOST_USER}...")
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            self.stdout.write(self.style.SUCCESS("✅ Authentification réussie !"))

            # Envoi d'un email de test
            self.stdout.write("\nEnvoi d'un email de test...")
            msg = MIMEText("Test de connexion SMTP directe depuis FORMIS")
            msg['Subject'] = '🔧 Test SMTP Direct FORMIS'
            msg['From'] = settings.EMAIL_HOST_USER
            msg['To'] = 'leandrebenilde07@gmail.com'

            server.send_message(msg)
            self.stdout.write(self.style.SUCCESS("✅ Email envoyé via SMTP direct !"))

            server.quit()
            self.stdout.write(self.style.SUCCESS("\n✅ Tous les tests SMTP ont réussi !"))

        except smtplib.SMTPAuthenticationError as e:
            self.stdout.write(self.style.ERROR(f"\n❌ ERREUR D'AUTHENTIFICATION :"))
            self.stdout.write(self.style.ERROR(f"   {str(e)}"))
            self.stdout.write("\n🔧 SOLUTION :")
            self.stdout.write("   1. Allez sur https://myaccount.google.com/security")
            self.stdout.write("   2. Activez la validation en deux étapes")
            self.stdout.write("   3. Allez dans 'Mots de passe des applications'")
            self.stdout.write("   4. Créez un mot de passe pour 'Django' ou 'Mail'")
            self.stdout.write("   5. Remplacez EMAIL_HOST_PASSWORD dans settings.py")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ ERREUR : {str(e)}"))
            if self.verbosity >= 2:
                traceback.print_exc()

    def test_with_user(self):
        """Test avec un utilisateur de la base"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("👤 TEST 3 : Email avec un utilisateur")
        self.stdout.write("=" * 60 + "\n")

        try:
            from apps.accounts.models import Utilisateur

            user = Utilisateur.objects.first()

            if not user:
                self.stdout.write(self.style.ERROR("❌ Aucun utilisateur trouvé dans la base"))
                return

            self.stdout.write(f"Utilisateur : {user.get_full_name()}")
            self.stdout.write(f"Email : {user.email}")
            self.stdout.write(f"Matricule : {user.matricule}")
            self.stdout.write(f"Rôle : {user.get_role_display()}")

            if not user.email:
                self.stdout.write(self.style.ERROR("\n❌ L'utilisateur n'a pas d'email"))
                return

            self.stdout.write(f"\n📧 Envoi vers {user.email}...")

            establishment_name = user.etablissement.nom if user.etablissement else "FORMIS"

            result = send_mail(
                subject=f'🧪 Test Email - {establishment_name}',
                message=f'''Bonjour {user.prenom} {user.nom},

Ceci est un email de test depuis la plateforme FORMIS.

Vos informations :
- Matricule : {user.matricule}
- Rôle : {user.get_role_display()}
- Établissement : {establishment_name}

Si vous recevez ce message, la configuration email fonctionne correctement !

Date du test : {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

Cordialement,
L'équipe FORMIS
''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

            if result == 1:
                self.stdout.write(self.style.SUCCESS("\n✅ Email envoyé avec succès !"))
                self.stdout.write(self.style.WARNING(f"\n⚠️  Vérifiez la boîte {user.email} (et les spams)"))
            else:
                self.stdout.write(self.style.ERROR("\n❌ L'email n'a pas été envoyé"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ ERREUR : {str(e)}"))
            if self.verbosity >= 2:
                traceback.print_exc()