
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Departement, Filiere, Niveau, Classe, 
    PeriodeAcademique, Programme
)


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'code', 'etablissement', 'chef', 
        'telephone', 'email', 'est_actif', 'created_at'
    ]
    list_filter = ['etablissement', 'est_actif', 'created_at']
    search_fields = ['nom', 'code', 'description']
    list_editable = ['est_actif']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('etablissement', 'nom', 'code', 'description')
        }),
        ('Direction', {
            'fields': ('chef',)
        }),
        ('Contact', {
            'fields': ('telephone', 'email', 'bureau')
        }),
        ('Statut', {
            'fields': ('est_actif',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'etablissement', 'chef'
        )


@admin.register(Filiere)
class FiliereAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'code', 'etablissement', 'departement', 
        'type_filiere', 'duree_annees', 'frais_scolarite',
        'capacite_maximale', 'est_active'
    ]
    list_filter = [
        'etablissement', 'departement', 'type_filiere', 
        'est_active', 'created_at'
    ]
    search_fields = ['nom', 'code', 'description', 'nom_diplome']
    list_editable = ['est_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('etablissement', 'departement', 'nom', 'code', 'description')
        }),
        ('Formation', {
            'fields': ('type_filiere', 'duree_annees', 'nom_diplome', 'prerequis')
        }),
        ('Gestion', {
            'fields': ('frais_scolarite', 'capacite_maximale')
        }),
        ('Statut', {
            'fields': ('est_active',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'etablissement', 'departement'
        )


@admin.register(Niveau)
class NiveauAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'code', 'filiere', 'ordre', 
        'frais_scolarite', 'est_actif'
    ]
    list_filter = ['filiere__etablissement', 'filiere', 'est_actif']
    search_fields = ['nom', 'code', 'description']
    list_editable = ['ordre', 'est_actif']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['filiere', 'ordre']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('filiere', 'nom', 'code', 'ordre', 'description')
        }),
        ('Frais', {
            'fields': ('frais_scolarite',),
            'description': 'Si différent des frais de la filière'
        }),
        ('Statut', {
            'fields': ('est_actif',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'code', 'niveau', 'etablissement', 
        'annee_academique', 'professeur_principal',
        'effectif_actuel', 'capacite_maximale',
        'places_disponibles', 'est_active'
    ]
    list_filter = [
        'etablissement', 'niveau__filiere', 'annee_academique',
        'est_active', 'created_at'
    ]
    search_fields = ['nom', 'code']
    list_editable = ['est_active']
    readonly_fields = ['created_at', 'updated_at', 'places_disponibles']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('etablissement', 'niveau', 'annee_academique', 'nom', 'code')
        }),
        ('Encadrement', {
            'fields': ('professeur_principal', 'salle_principale')
        }),
        ('Effectif', {
            'fields': ('capacite_maximale', 'effectif_actuel', 'places_disponibles')
        }),
        ('Statut', {
            'fields': ('est_active',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def places_disponibles(self, obj):
        places = obj.get_places_disponibles()
        
        if places is None:  # Cas illimité
            return format_html('<span style="color: blue;">Illimité</span>')

        color = 'green' if places > 5 else 'orange' if places > 0 else 'red'
        return format_html(
            '<span style="color: {};">{}</span>',
            color, places
    )
    places_disponibles.short_description = "Places disponibles"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'etablissement', 'niveau', 'niveau__filiere',
            'annee_academique', 'professeur_principal'
        )


@admin.register(PeriodeAcademique)
class PeriodeAcademiqueAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'code', 'etablissement', 'annee_academique',
        'type_periode', 'ordre', 'date_debut', 'date_fin',
        'est_courante', 'est_active'
    ]
    list_filter = [
        'etablissement', 'annee_academique', 'type_periode',
        'est_courante', 'est_active', 'date_debut'
    ]
    search_fields = ['nom', 'code']
    list_editable = ['est_courante', 'est_active']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['annee_academique', 'ordre']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('etablissement', 'annee_academique', 'nom', 'code', 'type_periode', 'ordre')
        }),
        ('Périodes', {
            'fields': ('date_debut', 'date_fin')
        }),
        ('Dates importantes', {
            'fields': (
                'date_limite_inscription', 'date_debut_examens',
                'date_fin_examens', 'date_publication_resultats'
            ),
            'classes': ('collapse',)
        }),
        ('Statut', {
            'fields': ('est_courante', 'est_active')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'etablissement', 'annee_academique'
        )


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'filiere', 'credits_totaux',
        'date_derniere_revision', 'approuve_par',
        'date_approbation', 'est_actif'
    ]
    list_filter = [
        'filiere__etablissement', 'filiere', 'est_actif',
        'date_derniere_revision', 'date_approbation'
    ]
    search_fields = ['nom', 'description', 'objectifs', 'competences']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('filiere', 'nom', 'description')
        }),
        ('Contenu pédagogique', {
            'fields': ('objectifs', 'competences', 'debouches', 'credits_totaux')
        }),
        ('Validation', {
            'fields': ('date_derniere_revision', 'approuve_par', 'date_approbation')
        }),
        ('Statut', {
            'fields': ('est_actif',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'filiere', 'filiere__etablissement', 'approuve_par'
        )
