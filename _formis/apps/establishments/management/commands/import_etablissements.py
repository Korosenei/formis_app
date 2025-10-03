from django.core.management.base import BaseCommand
from django.db import transaction
import csv
from establishments.models import Etablissement, TypeEtablissement, Localite


class Command(BaseCommand):
    help = 'Importe les établissements depuis un fichier CSV'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Chemin vers le fichier CSV')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans sauvegarde en base',
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('Mode simulation activé - aucune donnée ne sera sauvegardée'))

        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                created_count = 0
                updated_count = 0
                error_count = 0

                with transaction.atomic():
                    for row in reader:
                        try:
                            # Récupérer ou créer le type d'établissement
                            type_etab, _ = TypeEtablissement.objects.get_or_create(
                                code=row.get('type_code', 'AUTRE'),
                                defaults={
                                    'nom': row.get('type_nom', 'Autre'),
                                    'description': 'Type créé automatiquement lors de l\'import'
                                }
                            )

                            # Récupérer ou créer la localité
                            localite, _ = Localite.objects.get_or_create(
                                nom=row.get('localite', 'Non spécifiée'),
                                defaults={
                                    'region': row.get('region', ''),
                                    'pays': 'Burkina Faso'
                                }
                            )

                            # Créer ou mettre à jour l'établissement
                            etablissement, created = Etablissement.objects.update_or_create(
                                code=row['code'],
                                defaults={
                                    'nom': row['nom'],
                                    'sigle': row.get('sigle', ''),
                                    'type_etablissement': type_etab,
                                    'localite': localite,
                                    'adresse': row.get('adresse', ''),
                                    'telephone': row.get('telephone', ''),
                                    'email': row.get('email', ''),
                                    'capacite_totale': int(row.get('capacite', 0)),
                                    'actif': row.get('actif', 'true').lower() == 'true',
                                    'public': row.get('public', 'true').lower() == 'true',
                                }
                            )

                            if created:
                                created_count += 1
                                self.stdout.write(f'Créé: {etablissement.nom}')
                            else:
                                updated_count += 1
                                self.stdout.write(f'Mis à jour: {etablissement.nom}')

                        except Exception as e:
                            error_count += 1
                            self.stdout.write(
                                self.style.ERROR(f'Erreur ligne {reader.line_num}: {str(e)}')
                            )

                    if dry_run:
                        raise transaction.TransactionManagementError("Rollback pour simulation")

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'Fichier non trouvé: {csv_file}'))
            return
        except transaction.TransactionManagementError:
            pass  # Rollback normal en mode dry-run
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erreur: {str(e)}'))
            return

        # Afficher le résumé
        self.stdout.write(
            self.style.SUCCESS(
                f'\nRésumé:\n'
                f'- Établissements créés: {created_count}\n'
                f'- Établissements mis à jour: {updated_count}\n'
                f'- Erreurs: {error_count}'
            )
        )

