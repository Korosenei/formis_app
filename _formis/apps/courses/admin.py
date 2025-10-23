# apps/courses/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import (
    Module, Matiere, Cours, CahierTexte,
    Ressource, Presence, EmploiDuTemps, CreneauEmploiDuTemps
)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'code', 'niveau', 'coordinateur',
        'credits_ects', 'volume_horaire_total', 'actif'
    ]
    list_filter = [
        'niveau__filiere__departement__etablissement',
        'niveau__filiere__departement',
        'niveau__filiere',
        'niveau',
        'actif',
        'created_at'
    ]
    search_fields = ['nom', 'code', 'description']
    raw_id_fields = ['coordinateur']
    list_select_related = ['niveau', 'coordinateur']

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'code', 'description', 'niveau')
        }),
        ('Coordination', {
            'fields': ('coordinateur',)
        }),
        ('Statut', {
            'fields': ('actif',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'niveau__filiere__departement__etablissement',
            'coordinateur'
        )


@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'code', 'niveau', 'module', 'enseignant_responsable',
        'coefficient', 'credits_ects', 'volume_horaire_total',
        'get_couleur_display', 'actif'
    ]
    list_filter = [
        'niveau__filiere__departement__etablissement',
        'niveau__filiere__departement',
        'niveau__filiere',
        'niveau',
        'module',
        'actif',
        'created_at'
    ]
    search_fields = ['nom', 'code', 'description']
    raw_id_fields = ['enseignant_responsable']
    list_select_related = ['niveau', 'module', 'enseignant_responsable']

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'code', 'description', 'niveau', 'module')
        }),
        ('Enseignement', {
            'fields': ('enseignant_responsable',)
        }),
        ('Volume horaire', {
            'fields': (
                'heures_cours_magistral',
                'heures_travaux_diriges',
                'heures_travaux_pratiques'
            )
        }),
        ('Évaluation', {
            'fields': ('coefficient', 'credits_ects')
        }),
        ('Affichage', {
            'fields': ('couleur',)
        }),
        ('Statut', {
            'fields': ('actif',)
        })
    )

    def get_couleur_display(self, obj):
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            obj.couleur,
            obj.couleur
        )

    get_couleur_display.short_description = 'Couleur'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'niveau__filiere__departement__etablissement',
            'module',
            'enseignant_responsable'
        )


class CahierTexteInline(admin.StackedInline):
    model = CahierTexte
    extra = 0
    max_num = 1
    readonly_fields = ['date_saisie', 'modifie_le']

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ['rempli_par']
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not obj.rempli_par:
            obj.rempli_par = request.user
        super().save_model(request, obj, form, change)


class RessourceInline(admin.TabularInline):
    model = Ressource
    extra = 1
    readonly_fields = ['taille_fichier', 'nombre_telechargements', 'nombre_vues']


class PresenceInline(admin.TabularInline):
    model = Presence
    extra = 0
    readonly_fields = ['date_validation']
    raw_id_fields = ['etudiant', 'valide_par']


@admin.register(Cours)
class CoursAdmin(admin.ModelAdmin):
    list_display = [
        'titre', 'matiere', 'classe', 'enseignant',
        'date_prevue', 'heure_debut_prevue', 'type_cours',
        'statut', 'cours_en_ligne', 'presence_prise', 'actif'
    ]
    list_filter = [
        'classe__niveau__filiere__departement__etablissement',
        'classe__niveau__filiere__departement',
        'classe__niveau__filiere',
        'classe__niveau',
        'classe',
        'periode_academique',
        'type_cours',
        'statut',
        'cours_en_ligne',
        'presence_prise',
        'actif',
        'date_prevue'
    ]
    search_fields = [
        'titre', 'description', 'classe__nom',
        'enseignant__first_name', 'enseignant__last_name',
        'matiere__nom'
    ]
    raw_id_fields = ['enseignant', 'salle']
    date_hierarchy = 'date_prevue'
    inlines = [CahierTexteInline, RessourceInline, PresenceInline]
    list_select_related = ['matiere', 'classe', 'enseignant', 'periode_academique', 'salle']

    fieldsets = (
        ('Informations générales', {
            'fields': (
                'titre', 'description', 'matiere', 'classe',
                'enseignant', 'periode_academique'
            )
        }),
        ('Type et statut', {
            'fields': ('type_cours', 'statut')
        }),
        ('Planification', {
            'fields': (
                'date_prevue', 'heure_debut_prevue', 'heure_fin_prevue',
                'salle'
            )
        }),
        ('Réalisation effective', {
            'fields': (
                'date_effective', 'heure_debut_effective',
                'heure_fin_effective'
            ),
            'classes': ('collapse',)
        }),
        ('Contenu pédagogique', {
            'fields': ('objectifs', 'contenu'),
            'classes': ('collapse',)
        }),
        ('Cours en ligne', {
            'fields': ('cours_en_ligne', 'url_streaming'),
            'classes': ('collapse',)
        }),
        ('Présence', {
            'fields': ('presence_prise',),
            'classes': ('collapse',)
        }),
        ('Statut', {
            'fields': ('actif',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'classe__niveau__filiere__departement__etablissement',
            'matiere',
            'enseignant',
            'periode_academique',
            'salle'
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "classe":
            # Filtrer les classes selon l'établissement de l'utilisateur
            if hasattr(request.user, 'etablissement'):
                kwargs["queryset"] = db_field.related_model.objects.filter(
                    niveau__filiere__departement__etablissement=request.user.etablissement
                )
        elif db_field.name == "matiere":
            # Filtrer les matières selon l'établissement
            if hasattr(request.user, 'etablissement'):
                kwargs["queryset"] = db_field.related_model.objects.filter(
                    niveau__filiere__departement__etablissement=request.user.etablissement
                )
        elif db_field.name == "salle":
            # Filtrer les salles selon l'établissement
            if hasattr(request.user, 'etablissement'):
                kwargs["queryset"] = db_field.related_model.objects.filter(
                    batiment__etablissement=request.user.etablissement
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(CahierTexte)
class CahierTexteAdmin(admin.ModelAdmin):
    list_display = [
        'cours', 'rempli_par', 'date_saisie', 'date_travail_pour'
    ]
    list_filter = [
        'cours__classe__niveau__filiere__departement__etablissement',
        'cours__classe__niveau__filiere__departement',
        'cours__classe',
        'rempli_par',
        'date_saisie',
        'date_travail_pour'
    ]
    search_fields = [
        'cours__titre', 'travail_fait', 'travail_donne',
        'cours__classe__nom', 'cours__matiere__nom'
    ]
    readonly_fields = ['date_saisie', 'modifie_le']
    raw_id_fields = ['cours', 'rempli_par']
    date_hierarchy = 'date_saisie'
    list_select_related = ['cours', 'rempli_par']

    fieldsets = (
        ('Cours', {
            'fields': ('cours', 'rempli_par')
        }),
        ('Contenu du cours', {
            'fields': ('travail_fait', 'travail_donne', 'date_travail_pour')
        }),
        ('Observations', {
            'fields': ('observations',)
        }),
        ('Métadonnées', {
            'fields': ('date_saisie', 'modifie_le'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Nouvel objet
            obj.rempli_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(Ressource)
class RessourceAdmin(admin.ModelAdmin):
    list_display = [
        'titre', 'cours', 'type_ressource',
        'get_taille_fichier_display', 'obligatoire',
        'telechargeable', 'nombre_telechargements', 'nombre_vues'
    ]
    list_filter = [
        'cours__classe__niveau__filiere__departement__etablissement',
        'type_ressource',
        'obligatoire',
        'telechargeable',
        'public',
        'created_at'
    ]
    search_fields = ['titre', 'description', 'cours__titre']
    readonly_fields = ['taille_fichier', 'nombre_telechargements', 'nombre_vues']
    raw_id_fields = ['cours']
    list_select_related = ['cours']

    fieldsets = (
        ('Informations générales', {
            'fields': ('cours', 'titre', 'description', 'type_ressource')
        }),
        ('Contenu', {
            'fields': ('fichier', 'url')
        }),
        ('Accessibilité', {
            'fields': ('obligatoire', 'telechargeable', 'public')
        }),
        ('Disponibilité', {
            'fields': ('disponible_a_partir_de', 'disponible_jusqua'),
            'classes': ('collapse',)
        }),
        ('Statistiques', {
            'fields': ('taille_fichier', 'nombre_telechargements', 'nombre_vues'),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'cours__classe__niveau__filiere__departement__etablissement'
        )


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = [
        'etudiant', 'cours', 'statut', 'heure_arrivee',
        'valide', 'valide_par', 'date_validation'
    ]
    list_filter = [
        'cours__classe__niveau__filiere__departement__etablissement',
        'cours__classe',
        'statut',
        'valide',
        'cours__date_prevue'
    ]
    search_fields = [
        'etudiant__first_name', 'etudiant__last_name',
        'cours__titre', 'motif_absence'
    ]
    raw_id_fields = ['cours', 'etudiant', 'valide_par']
    readonly_fields = ['date_validation']
    list_select_related = ['cours', 'etudiant', 'valide_par']

    fieldsets = (
        ('Informations générales', {
            'fields': ('cours', 'etudiant', 'statut')
        }),
        ('Détails présence', {
            'fields': ('heure_arrivee',)
        }),
        ('Justification d\'absence', {
            'fields': ('motif_absence', 'document_justificatif'),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': ('valide', 'valide_par', 'date_validation', 'notes_enseignant'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        if obj.valide and not obj.valide_par:
            obj.valide_par = request.user
            obj.date_validation = timezone.now()
        super().save_model(request, obj, form, change)


class CreneauEmploiDuTempsInline(admin.TabularInline):
    model = CreneauEmploiDuTemps
    extra = 1
    raw_id_fields = ['cours']


@admin.register(EmploiDuTemps)
class EmploiDuTempsAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'get_cible', 'periode_academique',
        'semaine_debut', 'semaine_fin', 'publie', 'actuel'
    ]
    list_filter = [
        'periode_academique',
        'publie',
        'actuel',
        'semaine_debut'
    ]
    search_fields = ['nom', 'classe__nom', 'enseignant__first_name', 'enseignant__last_name']
    raw_id_fields = ['classe', 'enseignant', 'cree_par']
    inlines = [CreneauEmploiDuTempsInline]
    list_select_related = ['classe', 'enseignant', 'periode_academique', 'cree_par']

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'periode_academique')
        }),
        ('Cible', {
            'fields': (('classe', 'enseignant'),)
        }),
        ('Période de validité', {
            'fields': ('semaine_debut', 'semaine_fin')
        }),
        ('Statut', {
            'fields': ('publie', 'actuel')
        }),
        ('Création', {
            'fields': ('cree_par',),
            'classes': ('collapse',)
        })
    )

    def get_cible(self, obj):
        if obj.classe:
            return f"Classe: {obj.classe.nom}"
        elif obj.enseignant:
            return f"Enseignant: {obj.enseignant.get_full_name()}"
        return "Non spécifié"

    get_cible.short_description = 'Cible'

    def save_model(self, request, obj, form, change):
        if not change:  # Nouvel objet
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'classe__niveau__filiere__departement__etablissement',
            'enseignant',
            'periode_academique',
            'cree_par'
        )


@admin.register(CreneauEmploiDuTemps)
class CreneauEmploiDuTempsAdmin(admin.ModelAdmin):
    list_display = [
        'emploi_du_temps', 'cours', 'jour_semaine',
        'heure_debut', 'heure_fin'
    ]
    list_filter = [
        'emploi_du_temps__classe__niveau__filiere__departement__etablissement',
        'emploi_du_temps__classe',
        'jour_semaine',
        'emploi_du_temps__periode_academique'
    ]
    search_fields = [
        'emploi_du_temps__nom', 'cours__titre',
        'cours__matiere__nom'
    ]
    raw_id_fields = ['emploi_du_temps', 'cours']
    list_select_related = ['emploi_du_temps', 'cours']

    fieldsets = (
        ('Emploi du temps', {
            'fields': ('emploi_du_temps', 'cours')
        }),
        ('Horaires', {
            'fields': ('jour_semaine', 'heure_debut', 'heure_fin')
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'emploi_du_temps__classe__niveau__filiere__departement__etablissement',
            'cours__matiere'
        )


# Configuration des titres d'administration
admin.site.site_header = "Administration des Cours"
admin.site.site_title = "Gestion des Cours"
admin.site.index_title = "Tableau de bord - Cours"