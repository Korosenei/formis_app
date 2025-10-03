# apps/courses/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Module, Matiere, MatiereModule, Cours, CahierTexte,
    Ressource, Presence, EmploiDuTemps, CreneauHoraire
)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'code', 'niveau', 'get_filiere', 'get_departement',
        'coordinateur', 'credits_ects', 'volume_horaire_total', 'actif'
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
    filter_horizontal = ['prerequis']
    raw_id_fields = ['coordinateur']

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'code', 'description', 'niveau')
        }),
        ('Configuration académique', {
            'fields': ('coordinateur', 'volume_horaire_total', 'credits_ects')
        }),
        ('Prérequis', {
            'fields': ('prerequis',),
            'classes': ('collapse',)
        }),
        ('Statut', {
            'fields': ('actif',)
        })
    )

    def get_filiere(self, obj):
        return obj.filiere.nom if obj.filiere else '-'

    get_filiere.short_description = 'Filière'

    def get_departement(self, obj):
        return obj.departement.nom if obj.departement else '-'

    get_departement.short_description = 'Département'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'niveau__filiere__departement__etablissement',
            'coordinateur'
        )


class MatiereModuleInline(admin.TabularInline):
    model = MatiereModule
    extra = 1
    raw_id_fields = ['enseignant']


@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'code', 'coefficient', 'get_volume_horaire',
        'get_couleur_display', 'actif'
    ]
    list_filter = ['actif', 'created_at']
    search_fields = ['nom', 'code', 'description']
    inlines = [MatiereModuleInline]

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'code', 'description')
        }),
        ('Configuration pédagogique', {
            'fields': ('coefficient', 'couleur')
        }),
        ('Volume horaire', {
            'fields': ('heures_theorie', 'heures_pratique', 'heures_td')
        }),
        ('Statut', {
            'fields': ('actif',)
        })
    )

    def get_volume_horaire(self, obj):
        return f"{obj.volume_horaire_total}h"

    get_volume_horaire.short_description = 'Volume horaire'

    def get_couleur_display(self, obj):
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            obj.couleur,
            obj.couleur
        )

    get_couleur_display.short_description = 'Couleur'


@admin.register(MatiereModule)
class MatiereModuleAdmin(admin.ModelAdmin):
    list_display = [
        'matiere', 'module', 'get_niveau', 'enseignant',
        'coefficient', 'get_volume_horaire'
    ]
    list_filter = [
        'module__niveau__filiere__departement__etablissement',
        'module__niveau__filiere__departement',
        'module__niveau__filiere',
        'module__niveau',
    ]
    search_fields = ['matiere__nom', 'module__nom']
    raw_id_fields = ['enseignant']

    def get_niveau(self, obj):
        return obj.module.niveau.nom

    get_niveau.short_description = 'Niveau'

    def get_volume_horaire(self, obj):
        return f"{obj.volume_horaire_total}h"

    get_volume_horaire.short_description = 'Volume horaire'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'matiere', 'module__niveau', 'enseignant'
        )


class CahierTexteInline(admin.StackedInline):
    model = CahierTexte
    extra = 0
    readonly_fields = ['rempli_par', 'date_saisie', 'modifie_le']

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
        'titre', 'get_classe', 'get_matiere', 'enseignant',
        'date_prevue', 'heure_debut_prevue', 'type_cours',
        'statut', 'cours_en_ligne', 'presence_prise'
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
        'date_prevue'
    ]
    search_fields = ['titre', 'description', 'classe__nom', 'enseignant__first_name', 'enseignant__last_name']
    raw_id_fields = ['enseignant']
    date_hierarchy = 'date_prevue'
    inlines = [CahierTexteInline, RessourceInline, PresenceInline]

    fieldsets = (
        ('Informations générales', {
            'fields': ('titre', 'description', 'classe', 'matiere_module', 'enseignant', 'periode_academique')
        }),
        ('Type et statut', {
            'fields': ('type_cours', 'statut')
        }),
        ('Planification prévue', {
            'fields': ('date_prevue', 'heure_debut_prevue', 'heure_fin_prevue', 'salle')
        }),
        ('Réalisation effective', {
            'fields': ('date_effective', 'heure_debut_effective', 'heure_fin_effective'),
            'classes': ('collapse',)
        }),
        ('Contenu pédagogique', {
            'fields': ('objectifs', 'contenu', 'prerequis', 'ressources_utilisees'),
            'classes': ('collapse',)
        }),
        ('Cours en ligne', {
            'fields': ('cours_en_ligne', 'url_streaming', 'streaming_actif'),
            'classes': ('collapse',)
        }),
        ('Observations', {
            'fields': ('notes_enseignant', 'retours_etudiants'),
            'classes': ('collapse',)
        }),
        ('Présence', {
            'fields': ('presence_prise', 'date_prise_presence'),
            'classes': ('collapse',)
        }),
        ('Statut', {
            'fields': ('actif',)
        })
    )

    def get_classe(self, obj):
        return obj.classe.nom

    get_classe.short_description = 'Classe'

    def get_matiere(self, obj):
        return obj.matiere.nom

    get_matiere.short_description = 'Matière'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'classe__niveau__filiere__departement',
            'matiere_module__matiere',
            'enseignant',
            'periode_academique'
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "classe":
            # Filtrer les classes selon l'établissement de l'utilisateur
            if hasattr(request.user, 'etablissement'):
                kwargs["queryset"] = db_field.related_model.objects.filter(
                    niveau__filiere__departement__etablissement=request.user.etablissement
                )
        elif db_field.name == "matiere_module":
            # Filtrer selon la classe sélectionnée
            if request.GET.get('classe'):
                try:
                    classe_id = int(request.GET.get('classe'))
                    kwargs["queryset"] = db_field.related_model.objects.filter(
                        module__niveau=classe_id
                    )
                except (ValueError, TypeError):
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(CahierTexte)
class CahierTexteAdmin(admin.ModelAdmin):
    list_display = [
        'get_cours_titre', 'get_classe', 'get_matiere',
        'rempli_par', 'date_saisie', 'date_travail_pour'
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
        'cours__classe__nom'
    ]
    readonly_fields = ['date_saisie', 'modifie_le']
    raw_id_fields = ['cours', 'rempli_par']
    date_hierarchy = 'date_saisie'

    fieldsets = (
        ('Cours', {
            'fields': ('cours', 'rempli_par')
        }),
        ('Travail réalisé', {
            'fields': ('travail_fait',)
        }),
        ('Travail à faire', {
            'fields': ('travail_donne', 'date_travail_pour')
        }),
        ('Observations', {
            'fields': ('observations',)
        }),
        ('Métadonnées', {
            'fields': ('date_saisie', 'modifie_le'),
            'classes': ('collapse',)
        })
    )

    def get_cours_titre(self, obj):
        return obj.cours.titre

    get_cours_titre.short_description = 'Cours'

    def get_classe(self, obj):
        return obj.cours.classe.nom

    get_classe.short_description = 'Classe'

    def get_matiere(self, obj):
        return obj.cours.matiere.nom

    get_matiere.short_description = 'Matière'

    def save_model(self, request, obj, form, change):
        if not change:  # Nouvel objet
            obj.rempli_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(Ressource)
class RessourceAdmin(admin.ModelAdmin):
    list_display = [
        'titre', 'get_cours', 'type_ressource',
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

    def get_cours(self, obj):
        return obj.cours.titre

    get_cours.short_description = 'Cours'


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = [
        'get_etudiant', 'get_cours', 'get_classe',
        'statut', 'heure_arrivee', 'valide', 'valide_par'
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

    def get_etudiant(self, obj):
        return obj.etudiant.get_full_name()

    get_etudiant.short_description = 'Étudiant'

    def get_cours(self, obj):
        return obj.cours.titre

    get_cours.short_description = 'Cours'

    def get_classe(self, obj):
        return obj.cours.classe.nom

    get_classe.short_description = 'Classe'

    def save_model(self, request, obj, form, change):
        if obj.valide and not obj.valide_par:
            obj.valide_par = request.user
            obj.date_validation = timezone.now()
        super().save_model(request, obj, form, change)


class CreneauHoraireInline(admin.TabularInline):
    model = CreneauHoraire
    extra = 1
    raw_id_fields = ['enseignant']


@admin.register(EmploiDuTemps)
class EmploiDuTempsAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'classe', 'get_filiere', 'periode_academique',
        'valide_a_partir_du', 'valide_jusqua', 'publie', 'actuel'
    ]
    list_filter = [
        'classe__niveau__filiere__departement__etablissement',
        'classe__niveau__filiere__departement',
        'classe__niveau__filiere',
        'periode_academique',
        'publie',
        'actuel'
    ]
    search_fields = ['nom', 'description', 'classe__nom']
    raw_id_fields = ['cree_par']
    inlines = [CreneauHoraireInline]

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'description', 'classe', 'periode_academique')
        }),
        ('Validité', {
            'fields': ('valide_a_partir_du', 'valide_jusqua')
        }),
        ('Statut', {
            'fields': ('publie', 'actuel')
        }),
        ('Métadonnées', {
            'fields': ('cree_par',),
            'classes': ('collapse',)
        })
    )

    def get_filiere(self, obj):
        return obj.classe.niveau.filiere.nom

    get_filiere.short_description = 'Filière'

    def save_model(self, request, obj, form, change):
        if not change:  # Nouvel objet
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(CreneauHoraire)
class CreneauHoraireAdmin(admin.ModelAdmin):
    list_display = [
        'get_emploi_du_temps', 'jour', 'heure_debut', 'heure_fin',
        'get_matiere', 'enseignant', 'salle', 'type_cours', 'recurrent'
    ]
    list_filter = [
        'emploi_du_temps__classe__niveau__filiere__departement__etablissement',
        'emploi_du_temps__classe',
        'jour',
        'type_cours',
        'recurrent'
    ]
    search_fields = [
        'emploi_du_temps__nom', 'matiere_module__matiere__nom',
        'enseignant__first_name', 'enseignant__last_name'
    ]
    raw_id_fields = ['emploi_du_temps', 'enseignant']

    fieldsets = (
        ('Emploi du temps', {
            'fields': ('emploi_du_temps',)
        }),
        ('Horaires', {
            'fields': ('jour', 'heure_debut', 'heure_fin')
        }),
        ('Cours', {
            'fields': ('matiere_module', 'enseignant', 'type_cours')
        }),
        ('Lieu', {
            'fields': ('salle',)
        }),
        ('Récurrence', {
            'fields': ('recurrent', 'dates_exception'),
            'classes': ('collapse',)
        })
    )

    def get_emploi_du_temps(self, obj):
        return f"{obj.emploi_du_temps.classe.nom} - {obj.emploi_du_temps.nom}"

    get_emploi_du_temps.short_description = 'Emploi du temps'

    def get_matiere(self, obj):
        return obj.matiere_module.matiere.nom

    get_matiere.short_description = 'Matière'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "matiere_module":
            # Filtrer selon l'emploi du temps sélectionné
            if request.GET.get('emploi_du_temps'):
                try:
                    edt_id = int(request.GET.get('emploi_du_temps'))
                    edt = EmploiDuTemps.objects.get(id=edt_id)
                    kwargs["queryset"] = db_field.related_model.objects.filter(
                        module__niveau=edt.classe.niveau
                    )
                except (ValueError, TypeError, EmploiDuTemps.DoesNotExist):
                    pass
        elif db_field.name == "salle":
            # Filtrer selon l'établissement
            if hasattr(request.user, 'etablissement'):
                kwargs["queryset"] = db_field.related_model.objects.filter(
                    batiment__etablissement=request.user.etablissement
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# Configuration des titres d'administration
admin.site.site_header = "Administration des Cours"
admin.site.site_title = "Gestion des Cours"
admin.site.index_title = "Tableau de bord - Cours"
