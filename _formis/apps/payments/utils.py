# apps/payments/utils.py

from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from .models import Paiement, InscriptionPaiement


def calculer_statistiques_paiements(etablissement=None, annee_academique=None):
    """Calcule les statistiques de paiements pour un établissement/année"""

    queryset = Paiement.objects.all()

    if etablissement:
        queryset = queryset.filter(
            inscription_paiement__inscription__candidature__etablissement=etablissement
        )

    if annee_academique:
        queryset = queryset.filter(
            inscription_paiement__plan__annee_academique=annee_academique
        )

    # Statistiques générales
    stats = {
        'total_paiements': queryset.count(),
        'paiements_confirmes': queryset.filter(statut='CONFIRME').count(),
        'paiements_en_cours': queryset.filter(statut__in=['EN_ATTENTE', 'EN_COURS']).count(),
        'paiements_echecs': queryset.filter(statut='ECHEC').count(),

        # Montants
        'montant_total_collecte': queryset.filter(statut='CONFIRME').aggregate(
            total=Sum('montant')
        )['total'] or Decimal('0'),

        'montant_en_attente': queryset.filter(
            statut__in=['EN_ATTENTE', 'EN_COURS']
        ).aggregate(total=Sum('montant'))['total'] or Decimal('0'),
    }

    # Calcul du taux de réussite
    if stats['total_paiements'] > 0:
        stats['taux_reussite'] = round(
            (stats['paiements_confirmes'] / stats['total_paiements']) * 100, 2
        )
    else:
        stats['taux_reussite'] = 0

    return stats


def generer_rapport_paiements_mensuel(mois, annee, etablissement=None):
    """Génère un rapport mensuel des paiements"""

    from datetime import datetime, timedelta

    debut_mois = datetime(annee, mois, 1)
    fin_mois = debut_mois.replace(month=mois + 1) if mois < 12 else debut_mois.replace(year=annee + 1, month=1)

    queryset = Paiement.objects.filter(
        date_paiement__gte=debut_mois,
        date_paiement__lt=fin_mois
    )

    if etablissement:
        queryset = queryset.filter(
            inscription_paiement__inscription__candidature__etablissement=etablissement
        )

    rapport = {
        'periode': f"{debut_mois.strftime('%B %Y')}",
        'debut_mois': debut_mois,
        'fin_mois': fin_mois,
        'statistiques': calculer_statistiques_paiements_periode(queryset),
        'paiements_par_jour': {},
        'methodes_paiement': {},
        'filieres_top': {},
    }

    # Répartition par jour
    for i in range(1, 32):
        try:
            date_jour = debut_mois.replace(day=i)
            if date_jour >= fin_mois:
                break

            paiements_jour = queryset.filter(
                date_paiement__date=date_jour.date()
            )

            rapport['paiements_par_jour'][i] = {
                'nombre': paiements_jour.count(),
                'montant': paiements_jour.filter(statut='CONFIRME').aggregate(
                    total=Sum('montant')
                )['total'] or Decimal('0')
            }
        except ValueError:
            break

    # Répartition par méthode de paiement
    for methode, nom in Paiement.METHODES_PAIEMENT:
        count = queryset.filter(methode_paiement=methode).count()
        if count > 0:
            rapport['methodes_paiement'][nom] = count

    return rapport


def calculer_statistiques_paiements_periode(queryset):
    """Calcule les statistiques pour une période donnée"""

    return {
        'total': queryset.count(),
        'confirmes': queryset.filter(statut='CONFIRME').count(),
        'en_cours': queryset.filter(statut__in=['EN_ATTENTE', 'EN_COURS']).count(),
        'echecs': queryset.filter(statut='ECHEC').count(),
        'montant_total': queryset.filter(statut='CONFIRME').aggregate(
            total=Sum('montant')
        )['total'] or Decimal('0'),
        'montant_moyen': queryset.filter(statut='CONFIRME').aggregate(
            moyenne=Sum('montant')
        )['moyenne'] or Decimal('0'),
    }


def verifier_coherence_paiements():
    """Vérifie la cohérence des données de paiement"""

    problemes = []

    # Vérifier les inscriptions avec des totaux incohérents
    inscriptions = InscriptionPaiement.objects.all()

    for inscription in inscriptions:
        total_calcule = inscription.paiements.filter(
            statut='CONFIRME'
        ).aggregate(total=Sum('montant'))['total'] or Decimal('0')

        if total_calcule != inscription.montant_total_paye:
            problemes.append({
                'type': 'INCOHERENCE_TOTAL',
                'inscription_id': inscription.id,
                'total_enregistre': inscription.montant_total_paye,
                'total_calcule': total_calcule,
                'difference': inscription.montant_total_paye - total_calcule
            })

    # Vérifier les paiements sans référence externe pour LigdiCash
    paiements_ligdi_sans_ref = Paiement.objects.filter(
        methode_paiement='LIGDICASH',
        statut__in=['CONFIRME', 'EN_COURS'],
        reference_externe__isnull=True
    )

    for paiement in paiements_ligdi_sans_ref:
        problemes.append({
            'type': 'REFERENCE_MANQUANTE',
            'paiement_id': paiement.id,
            'numero_transaction': paiement.numero_transaction
        })

    return problemes


def corriger_totaux_paiements():
    """Corrige les totaux de paiements incohérents"""

    corrections = 0

    for inscription in InscriptionPaiement.objects.all():
        total_reel = inscription.paiements.filter(
            statut='CONFIRME'
        ).aggregate(total=Sum('montant'))['total'] or Decimal('0')

        if total_reel != inscription.montant_total_paye:
            inscription.montant_total_paye = total_reel
            inscription.save()
            inscription.mettre_a_jour_statut()
            corrections += 1

    return corrections


# Signal pour mettre à jour automatiquement les totaux
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


@receiver(post_save, sender=Paiement)
def mettre_a_jour_total_paiement(sender, instance, **kwargs):
    """Met à jour le total payé lors de la confirmation d'un paiement"""
    if instance.statut == 'CONFIRME':
        instance.mettre_a_jour_inscription()


@receiver(post_delete, sender=Paiement)
def recalculer_total_apres_suppression(sender, instance, **kwargs):
    """Recalcule le total après suppression d'un paiement"""
    if instance.inscription_paiement:
        instance.inscription_paiement.mettre_a_jour_statut()

