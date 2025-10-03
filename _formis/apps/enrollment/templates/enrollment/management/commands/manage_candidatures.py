# enrollment/management/commands/manage_candidatures.py

import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from datetime import timedelta

from enrollment.models import Candidature, DocumentCandidature
from enrollment.utils import (
    envoyer_email_candidature_soumise,
    envoyer_email_candidature_evaluee,
    creer_compte_utilisateur_depuis_candidature,
    nettoyer_candidatures_expirees,
    statistiques_candidatures
)

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Gestion des candidatures - nettoyage, statistiques, rappels'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            required=True,
            choices=[
                'nettoyer', 'stats', 'rappels', 'creer_comptes',
                'test_emails', 'valider_documents', 'rapport'
            ],
            help='Action à effectuer'
        )

        parser.add_argument(
            '--candidature-id',
            type=str,
            help='ID de la candidature pour actions spécifiques'
        )

        parser.add_argument(
            '--etablissement-code',
            type=str,
            help='Code établissement pour filtrer les actions'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mode simulation sans modifications'
        )

        parser.add_argument(
            '--force',
            action='store_true',
            help='Force l\'exécution sans confirmations'
        )

    def handle(self, *args, **options):
        action = options['action']

        try:
            if action == 'nettoyer':
                self.nettoyer_candidatures(options)
            elif action == 'stats':
                self.afficher_statistiques(options)
            elif action == 'rappels':
                self.envoyer_rappels(options)
            elif action == 'creer_comptes':
                self.creer_comptes_utilisateurs(options)
            elif action == 'test_emails':
                self.tester_emails(options)
            elif action == 'valider_documents':
                self.valider_documents(options)
            elif action == 'rapport':
                self.generer_rapport(options)

        except Exception as e:
            logger.error(f"Erreur dans commande manage_candidatures: {str(e)}")
            raise CommandError(f"Erreur: {str(e)}")

    def nettoyer_candidatures(self, options):
        """Nettoie les candidatures expirées"""
        self.stdout.write("=== NETTOYAGE DES CANDIDATURES EXPIRÉES ===")

        # Candidatures brouillons anciennes
        date_limite = timezone.now() - timedelta(days=30)
        candidatures_expirees = Candidature.objects.filter(
            statut='BROUILLON',
            created_at__lt=date_limite
        )

        if options.get('etablissement_code'):
            candidatures_expirees = candidatures_expirees.filter(
                etablissement__code=options['etablissement_code']
            )

        count = candidatures_expirees.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Aucune candidature expirée trouvée."))
            return

        self.stdout.write(f"Candidatures à marquer comme expirées: {count}")

        if not options['dry_run']:
            if not options['force']:
                confirm = input("Confirmer le marquage comme expirées ? (y/N): ")
                if confirm.lower() != 'y':
                    self.stdout.write("Opération annulée.")
                    return

            candidatures_expirees.update(statut='EXPIREE')
            self.stdout.write(
                self.style.SUCCESS(f"✓ {count} candidatures marquées comme expirées")
            )
            logger.info(f"Command: {count} candidatures marquées comme expirées")
        else:
            self.stdout.write(self.style.WARNING("Mode simulation - aucune modification"))

    def afficher_statistiques(self, options):
        """Affiche les statistiques des candidatures"""
        self.stdout.write("=== STATISTIQUES DES CANDIDATURES ===")

        etablissement_code = options.get('etablissement_code')
        if etablissement_code:
            try:
                from establishments.models import Etablissement
                etablissement = Etablissement.objects.get(code=etablissement_code)
                stats = statistiques_candidatures(etablissement)
                self.stdout.write(f"Statistiques pour {etablissement.nom}")
            except:
                self.stdout.write(self.style.ERROR("Établissement non trouvé"))
                return
        else:
            stats = statistiques_candidatures()
            self.stdout.write("Statistiques globales")

        self.stdout.write(f"\nTotal candidatures: {stats['total']}")
        self.stdout.write("\nRépartition par statut:")

        for statut_code, data in stats['par_statut'].items():
            self.stdout.write(
                f"  {data['label']}: {data['count']} ({data['pourcentage']}%)"
            )

        # Statistiques supplémentaires
        aujourd_hui = timezone.now().date()
        candidatures_jour = Candidature.objects.filter(
            created_at__date=aujourd_hui
        )

        if etablissement_code:
            candidatures_jour = candidatures_jour.filter(
                etablissement__code=etablissement_code
            )

        self.stdout.write(f"\nAujourd'hui ({aujourd_hui}):")
        self.stdout.write(f"  Nouvelles candidatures: {candidatures_jour.count()}")

        soumissions_jour = candidatures_jour.filter(
            statut__in=['SOUMISE', 'EN_COURS_EXAMEN', 'APPROUVEE', 'REJETEE']
        ).count()
        self.stdout.write(f"  Candidatures soumises: {soumissions_jour}")

    def envoyer_rappels(self, options):
        """Envoie des rappels pour candidatures incomplètes"""
        self.stdout.write("=== ENVOI DE RAPPELS ===")

        date_min = timezone.now() - timedelta(days=25)
        date_max = timezone.now() - timedelta(days=3)

        candidatures_incompletes = Candidature.objects.filter(
            statut='BROUILLON',
            created_at__range=[date_min, date_max]
        )

        if options.get('etablissement_code'):
            candidatures_incompletes = candidatures_incompletes.filter(
                etablissement__code=options['etablissement_code']
            )

        count = candidatures_incompletes.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Aucune candidature nécessitant un rappel."))
            return

        self.stdout.write(f"Candidatures à rappeler: {count}")

        if not options['dry_run']:
            if not options['force']:
                confirm = input("Confirmer l'envoi des rappels ? (y/N): ")
                if confirm.lower() != 'y':
                    self.stdout.write("Opération annulée.")
                    return

            emails_envoyes = 0
            for candidature in candidatures_incompletes:
                # Utiliser la fonction de rappel des tâches
                from enrollment.tasks import envoyer_email_rappel_candidature_incomplete
                if envoyer_email_rappel_candidature_incomplete(candidature):
                    emails_envoyes += 1
                    self.stdout.write(f"  ✓ Rappel envoyé: {candidature.email}")
                else:
                    self.stdout.write(f"  ✗ Échec: {candidature.email}")

            self.stdout.write(
                self.style.SUCCESS(f"✓ {emails_envoyes}/{count} rappels envoyés")
            )
        else:
            self.stdout.write(self.style.WARNING("Mode simulation - aucun email envoyé"))

    def creer_comptes_utilisateurs(self, options):
        """Crée des comptes pour les candidatures approuvées"""
        self.stdout.write("=== CRÉATION DE COMPTES UTILISATEURS ===")

        candidatures_approuvees = Candidature.objects.filter(
            statut='APPROUVEE'
        ).select_related('etablissement')

        if options.get('etablissement_code'):
            candidatures_approuvees = candidatures_approuvees.filter(
                etablissement__code=options['etablissement_code']
            )

        # Filtrer celles qui n'ont pas encore de compte utilisateur
        candidatures_sans_compte = []
        for candidature in candidatures_approuvees:
            if not User.objects.filter(email=candidature.email).exists():
                candidatures_sans_compte.append(candidature)

        count = len(candidatures_sans_compte)

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Tous les comptes utilisateurs sont déjà créés."))
            return

        self.stdout.write(f"Candidatures nécessitant un compte: {count}")

        if not options['dry_run']:
            if not options['force']:
                confirm = input("Confirmer la création des comptes ? (y/N): ")
                if confirm.lower() != 'y':
                    self.stdout.write("Opération annulée.")
                    return

            comptes_crees = 0
            for candidature in candidatures_sans_compte:
                try:
                    utilisateur = creer_compte_utilisateur_depuis_candidature(candidature)
                    if utilisateur:
                        comptes_crees += 1
                        self.stdout.write(f"  ✓ Compte créé: {utilisateur.username} ({candidature.email})")
                    else:
                        self.stdout.write(f"  ✗ Échec: {candidature.email}")
                except Exception as e:
                    self.stdout.write(f"  ✗ Erreur {candidature.email}: {str(e)}")

            self.stdout.write(
                self.style.SUCCESS(f"✓ {comptes_crees}/{count} comptes créés")
            )
        else:
            self.stdout.write(self.style.WARNING("Mode simulation - aucun compte créé"))

    def tester_emails(self, options):
        """Teste l'envoi d'emails pour une candidature spécifique"""
        self.stdout.write("=== TEST D'ENVOI D'EMAILS ===")

        candidature_id = options.get('candidature_id')
        if not candidature_id:
            raise CommandError("--candidature-id requis pour tester les emails")

        try:
            candidature = Candidature.objects.get(id=candidature_id)
        except Candidature.DoesNotExist:
            raise CommandError(f"Candidature {candidature_id} non trouvée")

        self.stdout.write(f"Test pour candidature: {candidature.numero_candidature}")
        self.stdout.write(f"Email: {candidature.email}")
        self.stdout.write(f"Statut: {candidature.get_statut_display()}")

        if not options['dry_run']:
            if candidature.statut in ['SOUMISE', 'EN_COURS_EXAMEN']:
                self.stdout.write("Test email candidature soumise...")
                if envoyer_email_candidature_soumise(candidature):
                    self.stdout.write(self.style.SUCCESS("✓ Email soumission envoyé"))
                else:
                    self.stdout.write(self.style.ERROR("✗ Échec email soumission"))

            if candidature.statut in ['APPROUVEE', 'REJETEE']:
                self.stdout.write("Test email candidature évaluée...")
                if envoyer_email_candidature_evaluee(candidature):
                    self.stdout.write(self.style.SUCCESS("✓ Email évaluation envoyé"))
                else:
                    self.stdout.write(self.style.ERROR("✗ Échec email évaluation"))
        else:
            self.stdout.write(self.style.WARNING("Mode simulation - aucun email envoyé"))

    def valider_documents(self, options):
        """Valide automatiquement certains documents"""
        self.stdout.write("=== VALIDATION AUTOMATIQUE DE DOCUMENTS ===")

        documents_non_valides = DocumentCandidature.objects.filter(
            est_valide=False
        ).select_related('candidature')

        if options.get('etablissement_code'):
            documents_non_valides = documents_non_valides.filter(
                candidature__etablissement__code=options['etablissement_code']
            )

        if options.get('candidature_id'):
            documents_non_valides = documents_non_valides.filter(
                candidature__id=options['candidature_id']
            )

        count = documents_non_valides.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Aucun document en attente de validation."))
            return

        self.stdout.write(f"Documents à valider: {count}")

        # Afficher les détails
        for doc in documents_non_valides[:10]:  # Limiter l'affichage
            self.stdout.write(f"  - {doc.nom} ({doc.candidature.numero_candidature})")

        if count > 10:
            self.stdout.write(f"  ... et {count - 10} autres")

        if not options['dry_run']:
            if not options['force']:
                confirm = input("Marquer tous ces documents comme validés ? (y/N): ")
                if confirm.lower() != 'y':
                    self.stdout.write("Opération annulée.")
                    return

            # Créer un utilisateur admin fictif pour la validation
            admin_user = User.objects.filter(role='ADMIN', is_active=True).first()

            if not admin_user:
                self.stdout.write(self.style.ERROR("Aucun administrateur trouvé pour la validation"))
                return

            documents_non_valides.update(
                est_valide=True,
                valide_par=admin_user,
                date_validation=timezone.now(),
                notes_validation="Validation automatique par commande"
            )

            self.stdout.write(
                self.style.SUCCESS(f"✓ {count} documents validés")
            )
        else:
            self.stdout.write(self.style.WARNING("Mode simulation - aucune validation"))

    def generer_rapport(self, options):
        """Génère un rapport détaillé"""
        self.stdout.write("=== RAPPORT DÉTAILLÉ ===")

        etablissement_code = options.get('etablissement_code')

        # Statistiques de base
        self.afficher_statistiques(options)

        # Candidatures problématiques
        self.stdout.write("\n=== CANDIDATURES PROBLÉMATIQUES ===")

        # Candidatures soumises depuis longtemps sans traitement
        date_limite = timezone.now() - timedelta(days=7)
        candidatures_en_retard = Candidature.objects.filter(
            statut='SOUMISE',
            date_soumission__lt=date_limite
        )

        if etablissement_code:
            candidatures_en_retard = candidatures_en_retard.filter(
                etablissement__code=etablissement_code
            )

        self.stdout.write(f"Candidatures en retard de traitement (>7j): {candidatures_en_retard.count()}")

        # Candidatures avec documents invalides
        candidatures_docs_invalides = Candidature.objects.filter(
            documents__est_valide=False,
            statut__in=['SOUMISE', 'EN_COURS_EXAMEN']
        ).distinct()

        if etablissement_code:
            candidatures_docs_invalides = candidatures_docs_invalides.filter(
                etablissement__code=etablissement_code
            )

        self.stdout.write(f"Candidatures avec documents non validés: {candidatures_docs_invalides.count()}")

        # Candidatures approuvées sans compte utilisateur
        candidatures_sans_compte = []
        candidatures_approuvees = Candidature.objects.filter(statut='APPROUVEE')

        if etablissement_code:
            candidatures_approuvees = candidatures_approuvees.filter(
                etablissement__code=etablissement_code
            )

        for candidature in candidatures_approuvees:
            if not User.objects.filter(email=candidature.email).exists():
                candidatures_sans_compte.append(candidature)

        self.stdout.write(f"Candidatures approuvées sans compte utilisateur: {len(candidatures_sans_compte)}")

        # Évolution sur 30 jours
        self.stdout.write("\n=== ÉVOLUTION (30 DERNIERS JOURS) ===")

        date_debut = timezone.now() - timedelta(days=30)

        candidatures_recentes = Candidature.objects.filter(
            created_at__gte=date_debut
        )

        if etablissement_code:
            candidatures_recentes = candidatures_recentes.filter(
                etablissement__code=etablissement_code
            )

        par_semaine = {}
        for i in range(5):  # 5 semaines
            debut_semaine = date_debut + timedelta(weeks=i)
            fin_semaine = debut_semaine + timedelta(weeks=1)

            count = candidatures_recentes.filter(
                created_at__range=[debut_semaine, fin_semaine]
            ).count()

            par_semaine[f"Semaine {i + 1}"] = count

        for semaine, count in par_semaine.items():
            self.stdout.write(f"  {semaine}: {count} candidatures")

        # Recommandations
        self.stdout.write("\n=== RECOMMANDATIONS ===")

        if candidatures_en_retard.count() > 0:
            self.stdout.write("• Traiter les candidatures en retard")

        if candidatures_docs_invalides.count() > 0:
            self.stdout.write("• Valider les documents en attente")

        if len(candidatures_sans_compte) > 0:
            self.stdout.write("• Créer les comptes utilisateurs manquants")

        # Candidatures brouillons anciennes
        brouillons_anciens = Candidature.objects.filter(
            statut='BROUILLON',
            created_at__lt=timezone.now() - timedelta(days=20)
        )

        if etablissement_code:
            brouillons_anciens = brouillons_anciens.filter(
                etablissement__code=etablissement_code
            )

        if brouillons_anciens.count() > 0:
            self.stdout.write(f"• {brouillons_anciens.count()} brouillons anciens à nettoyer")
