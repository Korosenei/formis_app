# apps/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, ProfilUtilisateur, ProfilApprenant, ProfilEnseignant


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    """Administration personnalisée pour le modèle Utilisateur"""

    list_display = (
        'matricule', 'get_full_name', 'email', 'role',
        'etablissement', 'est_actif', 'date_creation'
    )
    list_filter = ('role', 'est_actif', 'genre', 'etablissement')
    search_fields = ('matricule', 'email', 'prenom', 'nom')
    ordering = ('-date_creation',)

    fieldsets = (
        ('Informations d\'authentification', {
            'fields': ('username', 'email', 'password')
        }),
        ('Informations personnelles', {
            'fields': (
                'matricule', 'prenom', 'nom', 'date_naissance',
                'lieu_naissance', 'genre', 'telephone', 'adresse',
                'photo_profil'
            )
        }),
        ('Informations académiques/professionnelles', {
            'fields': ('role', 'etablissement', 'departement')
        }),
        ('Permissions', {
            'fields': ('est_actif', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_mise_a_jour', 'cree_par'),
            'classes': ('collapse',)
        })
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'prenom', 'nom', 'email', 'role',
                'etablissement', 'password1', 'password2'
            )
        }),
    )

    readonly_fields = ('matricule', 'date_creation', 'date_mise_a_jour')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.role == 'ADMIN':
            queryset = queryset.filter(etablissement=request.user.etablissement)
        elif request.user.role == 'CHEF_DEPARTEMENT':
            queryset = queryset.filter(departement=request.user.departement)
        return queryset

@admin.register(ProfilUtilisateur)
class ProfilUtilisateurAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'langue', 'fuseau_horaire', 'recevoir_notifications')
    list_filter = ('langue', 'recevoir_notifications', 'recevoir_notifications_email')
    search_fields = ('utilisateur__prenom', 'utilisateur__nom', 'utilisateur__email')

@admin.register(ProfilApprenant)
class ProfilApprenantAdmin(admin.ModelAdmin):
    list_display = (
        'utilisateur', 'niveau_actuel', 'classe_actuelle',
        'statut_paiement', 'annee_academique'
    )
    list_filter = ('statut_paiement', 'niveau_actuel', 'classe_actuelle')
    search_fields = ('utilisateur__prenom', 'utilisateur__nom')

@admin.register(ProfilEnseignant)
class ProfilEnseignantAdmin(admin.ModelAdmin):
    list_display = (
        'utilisateur', 'id_employe', 'specialisation',
        'est_permanent', 'date_embauche'
    )
    list_filter = ('est_permanent', 'est_principal', 'date_embauche')
    search_fields = ('utilisateur__prenom', 'utilisateur__nom', 'specialisation')
    filter_horizontal = ('matieres',)

