from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Localite, TypeEtablissement, Etablissement, AnneeAcademique,
    BaremeNotation, NiveauNote, ParametresEtablissement, Salle,
    JourFerie, Campus
)


@admin.register(Localite)
class LocaliteAdmin(admin.ModelAdmin):
    list_display = ('nom', 'region', 'pays', 'code_postal', 'created_at')
    list_filter = ('region', 'pays')
    search_fields = ('nom', 'region', 'code_postal')
    ordering = ('nom',)
    list_per_page = 25


@admin.register(TypeEtablissement)
class TypeEtablissementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code', 'structure_academique_defaut', 'actif', 'created_at')
    list_filter = ('structure_academique_defaut', 'actif')
    search_fields = ('nom', 'code', 'description')
    ordering = ('nom',)
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


class ParametresEtablissementInline(admin.StackedInline):
    model = ParametresEtablissement
    extra = 0
    fieldsets = (
        ('Structure Académique', {
            'fields': ('structure_academique', 'bareme_notation_defaut')
        }),
        ('Inscription', {
            'fields': (
                'frais_dossier_requis', 'montant_frais_dossier',
                'date_limite_inscription_anticipée', 'date_limite_inscription_normale',
                'date_limite_inscription_tardive'
            )
        }),
        ('Paiement', {
            'fields': (
                'paiement_echelonne_autorise', 'nombre_maximum_tranches',
                'frais_echelonnement', 'taux_penalite_retard'
            )
        }),
        ('Paramètres Académiques', {
            'fields': (
                'taux_presence_minimum', 'points_bonus_autorises',
                'points_bonus_maximum', 'examens_rattrapage_autorises',
                'frais_examen_rattrapage'
            )
        }),
        ('Communication', {
            'fields': ('notifications_sms', 'notifications_email')
        }),
        ('Sécurité', {
            'fields': ('jours_avant_reset_mot_de_passe', 'tentatives_connexion_max')
        }),
        ('Personnalisation', {
            'fields': ('couleur_primaire', 'couleur_secondaire')
        })
    )


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = (
        'nom', 'sigle', 'code', 'type_etablissement', 'localite',
        'taux_occupation_display', 'actif', 'public'
    )
    list_filter = ('type_etablissement', 'localite', 'actif', 'public')
    search_fields = ('nom', 'sigle', 'code', 'adresse')
    ordering = ('nom',)
    readonly_fields = ('created_at', 'updated_at', 'taux_occupation_display', 'logo_preview')

    fieldsets = (
        ('Informations Générales', {
            'fields': ('nom', 'sigle', 'code', 'type_etablissement', 'localite')
        }),
        ('Contact', {
            'fields': ('adresse', 'telephone', 'email', 'site_web')
        }),
        ('Direction', {
            'fields': ('nom_directeur', 'numero_enregistrement', 'date_creation')
        }),
        ('Images', {
            'fields': ('logo', 'logo_preview', 'image_couverture')
        }),
        ('Description', {
            'fields': ('description', 'mission', 'vision')
        }),
        ('Paramètres', {
            'fields': ('capacite_totale', 'etudiants_actuels', 'actif', 'public')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    inlines = [ParametresEtablissementInline]

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="height: 50px;"/>', obj.logo.url)
        return "Pas de logo"

    logo_preview.short_description = "Aperçu du logo"

    def taux_occupation_display(self, obj):
        taux = obj.taux_occupation()
        color = 'red' if taux > 90 else 'orange' if taux > 75 else 'green'
        return format_html(
            '<span style="color: {};">{}%</span>',
            color, f"{taux:.1f}"
        )

    taux_occupation_display.short_description = "Taux d'occupation"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'type_etablissement', 'localite'
        )

    actions = ['activer_etablissements', 'desactiver_etablissements', 'mise_a_jour_etudiants']

    def activer_etablissements(self, request, queryset):
        queryset.update(actif=True)
        self.message_user(request, f"{queryset.count()} établissements activés.")

    activer_etablissements.short_description = "Activer les établissements sélectionnés"

    def desactiver_etablissements(self, request, queryset):
        queryset.update(actif=False)
        self.message_user(request, f"{queryset.count()} établissements désactivés.")

    desactiver_etablissements.short_description = "Désactiver les établissements sélectionnés"

    def mise_a_jour_etudiants(self, request, queryset):
        count = 0
        for etablissement in queryset:
            etablissement.mise_a_jour_nombre_etudiants()
            count += 1
        self.message_user(request, f"Nombre d'étudiants mis à jour pour {count} établissements.")

    mise_a_jour_etudiants.short_description = "Mettre à jour le nombre d'étudiants"


@admin.register(AnneeAcademique)
class AnneeAcademiqueAdmin(admin.ModelAdmin):
    list_display = (
        'nom', 'etablissement', 'date_debut', 'date_fin',
        'est_courante', 'est_active'
    )
    list_filter = ('est_courante', 'est_active', 'etablissement')
    search_fields = ('nom', 'etablissement__nom')
    ordering = ('-date_debut',)
    date_hierarchy = 'date_debut'

    fieldsets = (
        ('Informations Générales', {
            'fields': ('etablissement', 'nom', 'date_debut', 'date_fin', 'est_courante', 'est_active')
        }),
        ('Inscriptions', {
            'fields': ('debut_inscriptions', 'fin_inscriptions')
        }),
        ('Cours', {
            'fields': ('debut_cours', 'fin_cours')
        }),
        ('Examens', {
            'fields': (
                'debut_examens_premier_semestre', 'fin_examens_premier_semestre',
                'debut_examens_second_semestre', 'fin_examens_second_semestre'
            )
        }),
        ('Vacances', {
            'fields': (
                'debut_vacances_hiver', 'fin_vacances_hiver',
                'debut_vacances_ete', 'fin_vacances_ete'
            )
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('etablissement')


class NiveauNoteInline(admin.TabularInline):
    model = NiveauNote
    extra = 1
    ordering = ['-note_minimale']


@admin.register(BaremeNotation)
class BaremeNotationAdmin(admin.ModelAdmin):
    list_display = (
        'nom', 'etablissement', 'note_minimale', 'note_maximale',
        'note_passage', 'est_defaut'
    )
    list_filter = ('etablissement', 'est_defaut')
    search_fields = ('nom', 'etablissement__nom')
    ordering = ('etablissement', 'nom')

    inlines = [NiveauNoteInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('etablissement')


@admin.register(NiveauNote)
class NiveauNoteAdmin(admin.ModelAdmin):
    list_display = (
        'nom', 'bareme_notation', 'note_minimale', 'note_maximale',
        'points_gpa', 'couleur_display'
    )
    list_filter = ('bareme_notation__etablissement', 'bareme_notation')
    search_fields = ('nom', 'bareme_notation__nom')
    ordering = ('bareme_notation', '-note_minimale')

    def couleur_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
            obj.couleur
        )

    couleur_display.short_description = "Couleur"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('bareme_notation__etablissement')


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    list_display = (
        'nom', 'code', 'etablissement', 'type_salle', 'capacite',
        'batiment', 'etage', 'etat', 'est_active'
    )
    list_filter = ('etablissement', 'type_salle', 'etat', 'est_active', 'batiment')
    search_fields = ('nom', 'code', 'batiment', 'description')
    ordering = ('etablissement', 'batiment', 'etage', 'nom')

    fieldsets = (
        ('Informations Générales', {
            'fields': ('etablissement', 'nom', 'code', 'type_salle')
        }),
        ('Localisation', {
            'fields': ('batiment', 'etage', 'capacite')
        }),
        ('Dimensions', {
            'fields': ('longueur', 'largeur'),
            'classes': ('collapse',)
        }),
        ('Équipements', {
            'fields': (
                'projecteur', 'ordinateur', 'climatisation',
                'wifi', 'tableau_blanc', 'systeme_audio'
            )
        }),
        ('État', {
            'fields': ('etat', 'accessible_pmr', 'est_active')
        }),
        ('Descriptions', {
            'fields': ('description', 'notes'),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('etablissement')

    def surface_display(self, obj):
        surface = obj.surface
        return f"{surface} m²" if surface else "Non définie"

    surface_display.short_description = "Surface"


@admin.register(JourFerie)
class JourFerieAdmin(admin.ModelAdmin):
    list_display = (
        'nom', 'etablissement', 'date_debut', 'date_fin',
        'type_jour_ferie', 'duree_jours', 'est_recurrent'
    )
    list_filter = ('etablissement', 'type_jour_ferie', 'est_recurrent')
    search_fields = ('nom', 'etablissement__nom')
    ordering = ('-date_debut',)
    date_hierarchy = 'date_debut'

    fieldsets = (
        ('Informations Générales', {
            'fields': ('etablissement', 'nom', 'type_jour_ferie')
        }),
        ('Dates', {
            'fields': ('date_debut', 'date_fin')
        }),
        ('Récurrence', {
            'fields': ('est_recurrent', 'modele_recurrence'),
            'classes': ('collapse',)
        }),
        ('Impact', {
            'fields': ('affecte_cours', 'affecte_examens', 'affecte_inscriptions')
        }),
        ('Affichage', {
            'fields': ('couleur', 'description'),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('etablissement')


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = (
        'nom', 'code', 'etablissement', 'localite',
        'est_campus_principal', 'responsable_campus', 'est_actif'
    )
    list_filter = ('etablissement', 'est_campus_principal', 'est_actif')
    search_fields = ('nom', 'code', 'etablissement__nom', 'adresse')
    ordering = ('etablissement', 'nom')

    fieldsets = (
        ('Informations Générales', {
            'fields': ('etablissement', 'nom', 'code', 'est_campus_principal')
        }),
        ('Localisation', {
            'fields': ('adresse', 'localite', 'latitude', 'longitude')
        }),
        ('Services', {
            'fields': (
                'bibliotheque', 'cafeteria', 'parking', 'internat',
                'installations_sportives', 'infirmerie'
            )
        }),
        ('Contact', {
            'fields': ('telephone', 'email', 'responsable_campus')
        }),
        ('Informations Complémentaires', {
            'fields': ('superficie_totale', 'description', 'est_actif'),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'etablissement', 'localite', 'responsable_campus'
        )


# Configuration des titres de l'admin
admin.site.site_header = "Administration des Établissements"
admin.site.site_title = "Gestion Établissements"
admin.site.index_title = "Panneau d'administration"

