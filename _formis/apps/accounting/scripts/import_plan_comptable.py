# scripts/import_plan_comptable.py
from apps.accounting.models import CompteComptable
from apps.establishments.models import Etablissement


def importer_plan_base(etablissement):
    comptes = [
        # CLASSE 1 - COMPTES DE CAPITAUX
        ('10', 'Capital', 'PASSIF'),
        ('11', 'Réserves', 'PASSIF'),
        ('12', 'Report à nouveau', 'PASSIF'),
        ('13', 'Résultat de l\'exercice', 'PASSIF'),
        ('16', 'Emprunts et dettes assimilées', 'PASSIF'),

        # CLASSE 2 - COMPTES D'IMMOBILISATIONS
        ('20', 'Immobilisations incorporelles', 'ACTIF'),
        ('21', 'Immobilisations corporelles', 'ACTIF'),
        ('23', 'Immobilisations en cours', 'ACTIF'),
        ('24', 'Immobilisations financières', 'ACTIF'),

        # CLASSE 3 - COMPTES DE STOCKS
        ('30', 'Stocks de marchandises', 'ACTIF'),
        ('31', 'Matières premières', 'ACTIF'),
        ('32', 'Fournitures', 'ACTIF'),

        # CLASSE 4 - COMPTES DE TIERS
        ('40', 'Fournisseurs', 'PASSIF'),
        ('41', 'Clients', 'ACTIF'),
        ('42', 'Personnel', 'PASSIF'),
        ('43', 'Sécurité sociale', 'PASSIF'),
        ('44', 'État et collectivités publiques', 'PASSIF'),

        # CLASSE 5 - COMPTES FINANCIERS
        ('51', 'Banques', 'TRESORERIE'),
        ('53', 'Caisse', 'TRESORERIE'),
        ('54', 'Régies d\'avances', 'TRESORERIE'),

        # CLASSE 6 - COMPTES DE CHARGES
        ('60', 'Achats', 'CHARGES'),
        ('61', 'Services extérieurs', 'CHARGES'),
        ('62', 'Autres services extérieurs', 'CHARGES'),
        ('63', 'Impôts et taxes', 'CHARGES'),
        ('64', 'Charges de personnel', 'CHARGES'),
        ('65', 'Autres charges', 'CHARGES'),
        ('66', 'Charges financières', 'CHARGES'),
        ('67', 'Charges exceptionnelles', 'CHARGES'),

        # CLASSE 7 - COMPTES DE PRODUITS
        ('70', 'Ventes', 'PRODUITS'),
        ('71', 'Production stockée', 'PRODUITS'),
        ('72', 'Production immobilisée', 'PRODUITS'),
        ('73', 'Prestations de services', 'PRODUITS'),
        ('74', 'Subventions d\'exploitation', 'PRODUITS'),
        ('75', 'Autres produits', 'PRODUITS'),
        ('76', 'Produits financiers', 'PRODUITS'),
        ('77', 'Produits exceptionnels', 'PRODUITS'),

        # COMPTES SPÉCIFIQUES ÉTABLISSEMENT
        ('720', 'Frais de scolarité', 'PRODUITS'),
        ('721', 'Frais d\'inscription', 'PRODUITS'),
        ('722', 'Frais d\'examen', 'PRODUITS'),
        ('640', 'Salaires enseignants', 'CHARGES'),
        ('641', 'Salaires personnel administratif', 'CHARGES'),
    ]

    for numero, libelle, categorie in comptes:
        CompteComptable.objects.get_or_create(
            etablissement=etablissement,
            numero_compte=numero,
            defaults={
                'libelle': libelle,
                'categorie': categorie,
                'est_actif': True
            }
        )

    print(f"✅ Plan comptable importé pour {etablissement.nom}")


# Exécution
etablissement = Etablissement.objects.first()
importer_plan_base(etablissement)