# apps/payments/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count
from decimal import Decimal

from .models import (
    PlanPaiement, TranchePaiement, InscriptionPaiement,
    Paiement, HistoriquePaiement, RemboursementPaiement
)


@admin.register(PlanPaiement)
class PlanPaiementAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'filiere', 'niveau', 'annee_academique',
        'montant_total', 'nb_tranches', 'est_actif'
    ]
    list_filter = [
        'est_actif', 'paiement_unique_possible', 'paiement_echelonne_possible',
        'filiere__etablissement', 'annee_academique', 'created_at'
    ]
    search_fields = ['nom', 'filiere__nom', 'niveau__nom', 'description']
    ordering = ['-created_at', 'filiere__nom']

    fieldsets = (
        ('Informations de base', {
            'fields': ('nom', 'description', 'filiere', 'niveau', 'annee_academique')
        }),
        ('Montants', {
            'fields': (
                'montant_total', 'remise_paiement_unique',
                'frais_echelonnement'
            )
        }),
        ('Options de paiement', {
            'fields': (
                'paiement_unique_possible', 'paiement_echelonne_possible'
            )
        }),
        ('Statut', {
            'fields': ('est_actif', 'cree_par')
        })
    )

    readonly_fields = ['cree_par']

    def save_model(self, request, obj, form, change):
        if not change:  # Création
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)

    def nb_tranches(self, obj):
        """Nombre de tranches du plan"""
        return obj.tranches.count()

    nb_tranches.short_description = 'Nb tranches'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('filiere', 'niveau', 'annee_academique', 'cree_par')


class TrancheInline(admin.TabularInline):
    model = TranchePaiement
    extra = 0
    fields = [
        'numero', 'nom', 'montant', 'date_limite',
        'est_premiere_tranche', 'penalite_retard'
    ]
    ordering = ['numero']


@admin.register(TranchePaiement)
class TranchePaiementAdmin(admin.ModelAdmin):
    list_display = [
        'plan', 'numero', 'nom', 'montant',
        'date_limite', 'est_premiere_tranche', 'est_en_retard'
    ]
    list_filter = [
        'est_premiere_tranche', 'date_limite', 'plan__filiere__etablissement',
        'plan__annee_academique'
    ]
    search_fields = ['nom', 'plan__nom', 'plan__filiere__nom']
    ordering = ['plan', 'numero']

    def est_en_retard(self, obj):
        """Indicateur de retard"""
        if obj.est_en_retard():
            return format_html(
                '<span style="color: red;">En retard</span>'
            )
        return format_html(
            '<span style="color: green;">À jour</span>'
        )

    est_en_retard.short_description = 'Statut'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('plan__filiere')


@admin.register(InscriptionPaiement)
class InscriptionPaiementAdmin(admin.ModelAdmin):
    list_display = [
        'inscription', 'plan', 'type_paiement', 'montant_total_du',
        'montant_total_paye', 'solde_restant', 'statut', 'pourcentage_paye'
    ]
    list_filter = [
        'type_paiement', 'statut', 'plan__filiere__etablissement',
        'plan__annee_academique', 'created_at'
    ]
    search_fields = [
        'inscription__etudiant__nom', 'inscription__etudiant__prenom',
        'inscription__numero_inscription', 'plan__nom'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Inscription', {
            'fields': ('inscription', 'plan', 'type_paiement')
        }),
        ('Montants', {
            'fields': (
                'montant_total_du', 'montant_total_paye',
                'solde_restant', 'pourcentage_paye'
            )
        }),
        ('Statut et dates', {
            'fields': (
                'statut', 'date_premier_paiement', 'date_solde'
            )
        })
    )

    readonly_fields = [
        'solde_restant', 'pourcentage_paye', 'montant_total_paye',
        'date_premier_paiement', 'date_solde'
    ]

    def solde_restant(self, obj):
        """Affiche le solde restant avec couleur"""
        solde = obj.solde_restant
        if solde <= 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{}€ (Soldé)</span>',
                solde
            )
        elif solde > 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">{}€</span>',
                solde
            )

    solde_restant.short_description = 'Solde restant'

    def pourcentage_paye(self, obj):
        """Affiche le pourcentage payé avec barre de progression"""
        pourcentage = obj.pourcentage_paye
        if pourcentage >= 100:
            color = 'green'
        elif pourcentage >= 50:
            color = 'orange'
        else:
            color = 'red'

        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">'
            '{}%'
            '</div></div>',
            min(pourcentage, 100), color, pourcentage
        )

    pourcentage_paye.short_description = 'Progression'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'inscription__etudiant', 'plan__filiere'
        )


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = [
        'numero_transaction', 'inscription_etudiant', 'montant',
        'methode_paiement', 'statut', 'date_paiement', 'tranche_info'
    ]
    list_filter = [
        'statut', 'methode_paiement', 'date_paiement',
        'inscription_paiement__plan__filiere__etablissement'
    ]
    search_fields = [
        'numero_transaction',
        'reference_externe',
        'inscription_paiement__inscription__apprenant__nom',
        'inscription_paiement__inscription__apprenant__prenom'
    ]
    ordering = ['-date_paiement']

    fieldsets = (
        ('Transaction', {
            'fields': (
                'numero_transaction', 'reference_externe',
                'inscription_paiement', 'tranche'
            )
        }),
        ('Montants', {
            'fields': ('montant', 'frais_transaction', 'montant_net')
        }),
        ('Paiement', {
            'fields': (
                'methode_paiement', 'statut', 'date_paiement',
                'date_confirmation', 'date_echeance'
            )
        }),
        ('Informations complémentaires', {
            'fields': ('description', 'notes_admin', 'traite_par'),
            'classes': ['collapse']
        }),
        ('Données techniques', {
            'fields': ('donnees_transaction',),
            'classes': ['collapse']
        })
    )

    readonly_fields = [
        'numero_transaction', 'montant_net', 'date_paiement'
    ]

    actions = ['confirmer_paiements', 'marquer_echec']

    def inscription_etudiant(self, obj):
        """Nom de l'étudiant lié au paiement"""
        if obj.inscription_paiement and obj.inscription_paiement.inscription:
            apprenant = obj.inscription_paiement.inscription.apprenant
            return f"{apprenant.get_full_name()}"
        return "-"

    inscription_etudiant.short_description = 'Étudiant'

    def tranche_info(self, obj):
        """Informations sur la tranche payée"""
        if obj.tranche:
            return f"T{obj.tranche.numero}: {obj.tranche.nom}"
        return "Paiement unique"

    tranche_info.short_description = 'Tranche'

    def confirmer_paiements(self, request, queryset):
        """Action pour confirmer plusieurs paiements"""
        count = 0
        for paiement in queryset.filter(statut='EN_ATTENTE'):
            paiement.confirmer()
            count += 1

        self.message_user(
            request,
            f'{count} paiement(s) confirmé(s) avec succès.'
        )

    confirmer_paiements.short_description = "Confirmer les paiements sélectionnés"

    def marquer_echec(self, request, queryset):
        """Action pour marquer des paiements en échec"""
        count = queryset.filter(statut__in=['EN_ATTENTE', 'EN_COURS']).update(
            statut='ECHEC'
        )

        self.message_user(
            request,
            f'{count} paiement(s) marqué(s) en échec.'
        )

    marquer_echec.short_description = "Marquer en échec"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'inscription_paiement__inscription__apprenant',  # <--- correction ici
            'tranche',
            'traite_par'
        )

class HistoriqueInline(admin.TabularInline):
    model = HistoriquePaiement
    extra = 0
    readonly_fields = ['created_at', 'utilisateur', 'adresse_ip']
    fields = [
        'type_action', 'ancien_statut', 'nouveau_statut',
        'details', 'utilisateur', 'created_at'
    ]
    ordering = ['-created_at']


@admin.register(HistoriquePaiement)
class HistoriquePaiementAdmin(admin.ModelAdmin):
    list_display = [
        'paiement', 'type_action', 'ancien_statut',
        'nouveau_statut', 'utilisateur', 'created_at'
    ]
    list_filter = [
        'type_action', 'ancien_statut', 'nouveau_statut', 'created_at'
    ]
    search_fields = [
        'paiement__numero_transaction',
        'utilisateur__nom', 'utilisateur__prenom', 'details'
    ]
    ordering = ['-created_at']

    readonly_fields = ['created_at', 'adresse_ip']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'paiement', 'utilisateur'
        )


@admin.register(RemboursementPaiement)
class RemboursementPaiementAdmin(admin.ModelAdmin):
    list_display = [
        'paiement_original', 'montant_rembourse', 'statut',
        'date_demande', 'demande_par', 'traite_par'
    ]
    list_filter = [
        'statut', 'date_demande', 'date_traitement'
    ]
    search_fields = [
        'paiement_original__numero_transaction',
        'motif', 'demande_par__nom', 'traite_par__nom'
    ]
    ordering = ['-date_demande']

    fieldsets = (
        ('Paiement original', {
            'fields': ('paiement_original', 'montant_rembourse')
        }),
        ('Demande', {
            'fields': ('motif', 'demande_par', 'date_demande')
        }),
        ('Traitement', {
            'fields': ('statut', 'traite_par', 'date_traitement', 'notes')
        })
    )

    readonly_fields = ['date_demande', 'date_traitement']

    actions = ['approuver_remboursements', 'rejeter_remboursements']

    def approuver_remboursements(self, request, queryset):
        """Action pour approuver des remboursements"""
        count = queryset.filter(statut='DEMANDE').update(
            statut='APPROUVE',
            traite_par=request.user,
            date_traitement=timezone.now()
        )

        self.message_user(
            request,
            f'{count} remboursement(s) approuvé(s).'
        )

    approuver_remboursements.short_description = "Approuver les remboursements"

    def rejeter_remboursements(self, request, queryset):
        """Action pour rejeter des remboursements"""
        count = queryset.filter(statut='DEMANDE').update(
            statut='REJETE',
            traite_par=request.user,
            date_traitement=timezone.now()
        )

        self.message_user(
            request,
            f'{count} remboursement(s) rejeté(s).'
        )

    rejeter_remboursements.short_description = "Rejeter les remboursements"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'paiement_original', 'demande_par', 'traite_par'
        )


# Configuration de l'admin
admin.site.site_header = "FORMIS - Administration des Paiements"
admin.site.site_title = "FORMIS Paiements"
admin.site.index_title = "Gestion des Paiements"

# Ajout des inline aux autres modèles si nécessaire
try:
    from apps.enrollment.admin import InscriptionAdmin
    from apps.enrollment.models import Inscription


    class PaiementInline(admin.TabularInline):
        model = InscriptionPaiement
        extra = 0
        readonly_fields = [
            'montant_total_paye', 'solde_restant', 'statut'
        ]
        fields = [
            'plan', 'type_paiement', 'montant_total_du',
            'montant_total_paye', 'solde_restant', 'statut'
        ]

        def solde_restant(self, obj):
            return f"{obj.solde_restant}€"

        solde_restant.short_description = 'Solde'


    # Ajouter l'inline à InscriptionAdmin si elle existe
    if hasattr(InscriptionAdmin, 'inlines'):
        InscriptionAdmin.inlines = list(InscriptionAdmin.inlines) + [PaiementInline]
    else:
        InscriptionAdmin.inlines = [PaiementInline]

except ImportError:
    # L'admin des inscriptions n'existe pas encore
    pass

# Personnalisation du plan avec ses tranches
PlanPaiementAdmin.inlines = [TrancheInline]

# Personnalisation du paiement avec son historique  
PaiementAdmin.inlines = [HistoriqueInline]
