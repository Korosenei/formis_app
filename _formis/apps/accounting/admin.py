# apps/accounting/admin.py
from django.contrib import admin
from .models import (
    CompteComptable, JournalComptable, EcritureComptable, LigneEcriture,
    Facture, LigneFacture, Depense, ExerciceComptable, BudgetPrevisionnel
)


@admin.register(CompteComptable)
class CompteComptableAdmin(admin.ModelAdmin):
    list_display = ['numero_compte', 'libelle', 'categorie', 'solde_actuel', 'est_actif']
    list_filter = ['categorie', 'est_actif', 'etablissement']
    search_fields = ['numero_compte', 'libelle']
    ordering = ['numero_compte']


class LigneEcritureInline(admin.TabularInline):
    model = LigneEcriture
    extra = 2
    fields = ['compte', 'libelle', 'debit', 'credit']


@admin.register(EcritureComptable)
class EcritureComptableAdmin(admin.ModelAdmin):
    list_display = ['numero_piece', 'date_ecriture', 'libelle', 'total_debit', 'total_credit', 'statut']
    list_filter = ['statut', 'journal', 'date_ecriture']
    search_fields = ['numero_piece', 'libelle']
    inlines = [LigneEcritureInline]
    date_hierarchy = 'date_ecriture'


class LigneFactureInline(admin.TabularInline):
    model = LigneFacture
    extra = 1


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ['numero_facture', 'apprenant', 'type_facture', 'montant_ttc', 'statut', 'date_emission']
    list_filter = ['statut', 'type_facture', 'date_emission']
    search_fields = ['numero_facture', 'apprenant__nom', 'apprenant__prenom']
    inlines = [LigneFactureInline]
    date_hierarchy = 'date_emission'
    readonly_fields = ['numero_facture', 'montant_tva', 'montant_ttc']


@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    list_display = ['numero_depense', 'fournisseur', 'categorie', 'montant', 'statut', 'date_depense']
    list_filter = ['statut', 'categorie', 'date_depense']
    search_fields = ['numero_depense', 'fournisseur', 'description']
    date_hierarchy = 'date_depense'
    readonly_fields = ['numero_depense']


@admin.register(ExerciceComptable)
class ExerciceComptableAdmin(admin.ModelAdmin):
    list_display = ['libelle', 'date_debut', 'date_fin', 'est_cloture']
    list_filter = ['est_cloture', 'etablissement']
    date_hierarchy = 'date_debut'


@admin.register(BudgetPrevisionnel)
class BudgetPrevisionnelAdmin(admin.ModelAdmin):
    list_display = ['libelle', 'exercice', 'type_budget', 'montant_previsionnel', 'montant_realise', 'taux_realisation']
    list_filter = ['type_budget', 'exercice']
    search_fields = ['libelle']
