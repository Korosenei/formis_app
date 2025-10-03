from django.core.management.base import BaseCommand
from establishments.models import Etablissement


class Command(BaseCommand):
    help = 'Met à jour le nombre d\'étudiants pour tous les établissements'

    def add_arguments(self, parser):
        parser.add_argument(
            '--etablissement',
            type=int,
            help='ID de l\'établissement à mettre à jour (tous par défaut)',
        )

    def handle(self, *args, **options):
        etablissement_id = options['etablissement']

        if etablissement_id:
            try:
                etablissement = Etablissement.objects.get(pk=etablissement_id)
                etablissements = [etablissement]
            except Etablissement.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Établissement avec l\'ID {etablissement_id} non trouvé')
                )
                return
        else:
            etablissements = Etablissement.objects.filter(actif=True)

        updated_count = 0
        for etablissement in etablissements:
            old_count = etablissement.etudiants_actuels
            etablissement.mise_a_jour_nombre_etudiants()
            new_count = etablissement.etudiants_actuels

            if old_count != new_count:
                self.stdout.write(
                    f'{etablissement.nom}: {old_count} → {new_count} étudiants'
                )
            updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Mise à jour terminée pour {updated_count} établissements')
        )
