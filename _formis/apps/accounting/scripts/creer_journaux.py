from apps.accounting.models import JournalComptable
from apps.establishments.models import Etablissement


def creer_journaux(etablissement):
    journaux = [
        ('VE', 'Journal des ventes', 'VENTES'),
        ('AC', 'Journal des achats', 'ACHATS'),
        ('BQ', 'Journal de banque', 'BANQUE'),
        ('CA', 'Journal de caisse', 'CAISSE'),
        ('OD', 'Opérations diverses', 'OD'),
    ]

    for code, libelle, type_j in journaux:
        JournalComptable.objects.get_or_create(
            etablissement=etablissement,
            code=code,
            defaults={
                'libelle': libelle,
                'type_journal': type_j,
                'est_actif': True
            }
        )

    print(f"✅ Journaux créés pour {etablissement.nom}")


etablissement = Etablissement.objects.first()
creer_journaux(etablissement)