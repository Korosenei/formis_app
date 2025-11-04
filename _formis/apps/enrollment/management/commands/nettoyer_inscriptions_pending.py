from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.enrollment.models import Inscription
from apps.payments.models import Paiement, InscriptionPaiement


class Command(BaseCommand):
    help = 'Nettoie les inscriptions PENDING orphelines (sans paiement actif)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait nettoyé sans appliquer les changements'
        )
        parser.add_argument(
            '--age',
            type=int,
            default=1,
            help='Âge minimum en heures pour considérer une inscription comme orpheline (défaut: 1)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        age_heures = options['age']

        self.stdout.write(self.style.SUCCESS(
            f"\n{'=' * 80}\n"
            f"🧹 NETTOYAGE DES INSCRIPTIONS PENDING ORPHELINES\n"
            f"{'=' * 80}\n"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Mode DRY-RUN - Aucun changement ne sera appliqué\n'
            ))

        # Trouver les inscriptions PENDING anciennes
        cutoff_time = timezone.now() - timedelta(hours=age_heures)

        inscriptions_pending = Inscription.objects.filter(
            statut='PENDING',
            created_at__lt=cutoff_time
        ).select_related('apprenant', 'candidature')

        self.stdout.write(f"📊 {inscriptions_pending.count()} inscription(s) PENDING de plus de {age_heures}h\n")

        stats = {
            'total': 0,
            'sans_paiement': 0,
            'paiements_annules': 0,
            'inscriptions_supprimees': 0,
            'erreurs': 0
        }

        for inscription in inscriptions_pending:
            stats['total'] += 1

            self.stdout.write(f"\n{'─' * 80}")
            self.stdout.write(
                f"📋 Inscription: {inscription.numero_inscription}\n"
                f"   Apprenant: {inscription.apprenant.get_full_name()} ({inscription.apprenant.email})\n"
                f"   Créée: {inscription.created_at.strftime('%d/%m/%Y %H:%M')}"
            )

            # Vérifier les paiements
            paiements_actifs = Paiement.objects.filter(
                inscription_paiement__inscription=inscription,
                statut__in=['EN_ATTENTE', 'EN_COURS']
            )

            paiements_count = paiements_actifs.count()

            if paiements_count == 0:
                stats['sans_paiement'] += 1
                self.stdout.write(self.style.WARNING(
                    f"   ⚠️  Aucun paiement actif - SUPPRESSION"
                ))

                if not dry_run:
                    try:
                        with transaction.atomic():
                            # Supprimer l'InscriptionPaiement
                            InscriptionPaiement.objects.filter(
                                inscription=inscription
                            ).delete()

                            # Supprimer l'inscription
                            inscription.delete()

                            stats['inscriptions_supprimees'] += 1
                            self.stdout.write(self.style.SUCCESS("   ✅ Supprimée"))
                    except Exception as e:
                        stats['erreurs'] += 1
                        self.stdout.write(self.style.ERROR(
                            f"   ❌ Erreur: {str(e)}"
                        ))
                else:
                    self.stdout.write("   [DRY-RUN] Serait supprimée")
            else:
                self.stdout.write(f"   💳 {paiements_count} paiement(s) actif(s)")

                # Vérifier l'âge des paiements
                paiements_anciens = paiements_actifs.filter(
                    created_at__lt=cutoff_time
                )

                if paiements_anciens.exists():
                    self.stdout.write(self.style.WARNING(
                        f"   ⚠️  {paiements_anciens.count()} paiement(s) ancien(s) - ANNULATION"
                    ))

                    if not dry_run:
                        try:
                            paiements_anciens.update(
                                statut='ANNULE',
                                notes_admin=f'Annulé automatiquement (plus de {age_heures}h sans confirmation)'
                            )
                            stats['paiements_annules'] += paiements_anciens.count()
                            self.stdout.write(self.style.SUCCESS("   ✅ Annulés"))
                        except Exception as e:
                            stats['erreurs'] += 1
                            self.stdout.write(self.style.ERROR(f"   ❌ Erreur: {str(e)}"))
                    else:
                        self.stdout.write("   [DRY-RUN] Seraient annulés")

        # Statistiques finales
        self.stdout.write(self.style.SUCCESS(
            f"\n{'=' * 80}\n"
            f"📊 STATISTIQUES\n"
            f"{'=' * 80}\n"
        ))
        self.stdout.write(f"Total traité: {stats['total']}")
        self.stdout.write(f"Sans paiement: {stats['sans_paiement']}")

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Paiements annulés: {stats['paiements_annules']}"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"✅ Inscriptions supprimées: {stats['inscriptions_supprimees']}"
            ))
            if stats['erreurs'] > 0:
                self.stdout.write(self.style.ERROR(
                    f"❌ Erreurs: {stats['erreurs']}"
                ))
        else:
            self.stdout.write(self.style.WARNING(
                f"\n💡 Relancez sans --dry-run pour appliquer les changements\n"
            ))