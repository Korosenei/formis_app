from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Evaluation, Composition, FichierComposition, Note


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = [
        'titre', 'enseignant', 'matiere', 'type_evaluation',
        'coefficient', 'date_debut', 'date_fin', 'statut', 'nb_compositions'
    ]
    list_filter = [
        'type_evaluation', 'statut', 'date_debut', 'matiere',
        'enseignant'
    ]
    search_fields = ['titre', 'description', 'enseignant__username']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['classes']

    fieldsets = (
        ('Informations de base', {
            'fields': ('enseignant', 'matiere', 'titre', 'description', 'type_evaluation')
        }),
        ('Notation', {
            'fields': ('coefficient', 'note_maximale')
        }),
        ('Planning', {
            'fields': ('date_debut', 'date_fin', 'duree_minutes')
        }),
        ('Fichiers', {
            'fields': ('fichier_evaluation', 'fichier_correction')
        }),
        ('Paramètres de correction', {
            'fields': ('correction_visible_immediatement', 'date_publication_correction')
        }),
        ('Paramètres de retard', {
            'fields': ('autorise_retard', 'penalite_retard')
        }),
        ('Configuration', {
            'fields': ('statut', 'classes')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def est_active(self, obj):
        if obj.est_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    est_active.short_description = 'Active'

    def nb_compositions(self, obj):
        return obj.compositions.count()

    nb_compositions.short_description = 'Nb compositions'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'ENSEIGNANT':
            return qs.filter(enseignant=request.user)
        return qs


@admin.register(Composition)
class CompositionAdmin(admin.ModelAdmin):
    list_display = [
        'apprenant', 'evaluation', 'statut', 'date_debut',
        'date_soumission', 'note_obtenue', 'est_en_retard_display'
    ]
    list_filter = [
        'statut', 'evaluation__type_evaluation', 'date_soumission',
        'evaluation__matiere'
    ]
    search_fields = [
        'apprenant__username', 'apprenant__first_name',
        'apprenant__last_name', 'evaluation__titre'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'date_debut',
        'est_en_retard_display'
    ]

    fieldsets = (
        ('Informations de base', {
            'fields': ('evaluation', 'apprenant', 'statut')
        }),
        ('Timing', {
            'fields': ('date_debut', 'date_soumission', 'est_en_retard_display')
        }),
        ('Correction', {
            'fields': ('note_obtenue', 'commentaire_correction',
                      'fichier_correction_personnalise', 'corrigee_par', 'date_correction')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def est_en_retard_display(self, obj):
        if obj.est_en_retard:
            return format_html('<span style="color: red;">Oui</span>')
        return format_html('<span style="color: green;">Non</span>')
    est_en_retard_display.short_description = 'En retard'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'ENSEIGNANT':
            return qs.filter(evaluation__enseignant=request.user)
        elif request.user.role == 'APPRENANT':
            return qs.filter(apprenant=request.user)
        return qs


@admin.register(FichierComposition)
class FichierCompositionAdmin(admin.ModelAdmin):
    list_display = [
        'nom_original', 'uploade_par', 'taille_formatee',
        'type_mime', 'created_at'
    ]
    list_filter = ['type_mime', 'created_at']
    search_fields = ['nom_original', 'uploade_par__username']
    readonly_fields = ['created_at', 'updated_at', 'taille', 'type_mime']

    def taille_formatee(self, obj):
        if obj.taille < 1024:
            return f"{obj.taille} bytes"
        elif obj.taille < 1024 * 1024:
            return f"{obj.taille / 1024:.1f} KB"
        else:
            return f"{obj.taille / (1024 * 1024):.1f} MB"
    taille_formatee.short_description = 'Taille'


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = [
        'apprenant', 'evaluation', 'valeur', 'note_sur',
        'note_sur_20_display', 'coefficient_pondere', 'attribuee_par'
    ]
    list_filter = [
        'evaluation__type_evaluation', 'evaluation__matiere',
        'date_attribution', 'attribuee_par'
    ]
    search_fields = [
        'apprenant__username', 'apprenant__first_name',
        'apprenant__last_name', 'evaluation__titre'
    ]
    readonly_fields = ['date_attribution', 'note_sur_20_display']

    fieldsets = (
        ('Informations de base', {
            'fields': ('apprenant', 'matiere', 'evaluation', 'composition')
        }),
        ('Note', {
            'fields': ('valeur', 'note_sur', 'note_sur_20_display')
        }),
        ('Métadonnées', {
            'fields': ('attribuee_par', 'date_attribution', 'commentaire')
        })
    )

    def note_sur_20_display(self, obj):
        # CORRECTION : Gérer le cas où note_sur_20 est None
        if obj.note_sur_20 is None:
            return "N/A"
        return f"{obj.note_sur_20:.2f}/20"
    note_sur_20_display.short_description = 'Note sur 20'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'ENSEIGNANT':
            return qs.filter(evaluation__enseignant=request.user)
        elif request.user.role == 'APPRENANT':
            return qs.filter(apprenant=request.user)
        return qs

