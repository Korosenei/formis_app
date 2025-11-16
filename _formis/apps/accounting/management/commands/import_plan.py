from django.core.management.base import BaseCommand
from apps.accounting.scripts.import_plan_comptable import importer_plan_base
from apps.establishments.models import Etablissement


class Command(BaseCommand):
    help = "Importer le plan comptable de base"

    def handle(self, *args, **kwargs):
        etab = Etablissement.objects.first()
        importer_plan_base(etab)
        self.stdout.write(self.style.SUCCESS("Import du plan comptable terminé ✔"))
