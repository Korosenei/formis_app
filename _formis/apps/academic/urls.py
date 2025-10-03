# apps/academic/urls.py

from django.urls import path, include
from . import views

app_name = 'academic'

urlpatterns = [
    # Dashboard académique
    path('dashboard/', views.dashboard_academic, name='dashboard'),

    # URLs pour Départements
    path('departements/', views.DepartementListView.as_view(), name='departement_list'),
    path('departements/nouveau/', views.DepartementCreateView.as_view(), name='departement_create'),
    path('departements/<uuid:pk>/', views.departement_detail, name='departement_detail'),
    path('departements/<uuid:pk>/modifier/', views.DepartementUpdateView.as_view(), name='departement_update'),
    path('departements/<uuid:pk>/supprimer/', views.departement_delete, name='departement_delete'),
    path('departements/<uuid:pk>/toggle-status/', views.departement_toggle_status, name='departement_toggle_status'),

    # URLs pour Filières
    path('filieres/', views.FiliereListView.as_view(), name='filiere_list'),
    path('filieres/nouvelle/', views.FiliereCreateView.as_view(), name='filiere_create'),
    path('filieres/<uuid:pk>/', views.filiere_detail, name='filiere_detail'),
    path('filieres/<uuid:pk>/modifier/', views.FiliereUpdateView.as_view(), name='filiere_update'),
    path('filieres/<uuid:pk>/toggle-status/', views.filiere_toggle_status, name='filiere_toggle_status'),
    path('filieres/<uuid:pk>/duplicate/', views.filiere_duplicate, name='filiere_duplicate'),
    path('filieres/<uuid:pk>/delete/', views.filiere_delete, name='filiere_delete'),

    # URLs pour Niveaux
    path('niveaux/', views.NiveauListView.as_view(), name='niveau_list'),
    path('niveaux/nouveau/', views.NiveauCreateView.as_view(), name='niveau_create'),
    path('niveaux/<uuid:pk>/', views.niveau_detail, name='niveau_detail'),
    path('niveaux/<uuid:pk>/modifier/', views.NiveauUpdateView.as_view(), name='niveau_update'),
    path('niveaux/<uuid:pk>/toggle-status/', views.niveau_toggle_status, name='niveau_toggle_status'),
    path('niveaux/<uuid:pk>/delete/', views.niveau_delete, name='niveau_delete'),

    # ========== CLASSES ==========
    path('classes/', views.ClasseListView.as_view(), name='classe_list'),
    path('classes/nouvelle/', views.ClasseCreateView.as_view(), name='classe_create'),
    path('classes/<uuid:pk>/', views.classe_detail, name='classe_detail'),
    path('classes/<uuid:pk>/modifier/', views.ClasseUpdateView.as_view(), name='classe_update'),
    path('classes/<uuid:pk>/toggle-status/', views.classe_toggle_status, name='classe_toggle_status'),
    path('classes/<uuid:pk>/duplicate/', views.classe_duplicate, name='classe_duplicate'),
    path('classes/<uuid:pk>/delete/', views.classe_delete, name='classe_delete'),

    # URLs pour Périodes académiques
    path('periodes/', views.PeriodeAcademiqueListView.as_view(), name='periode_list'),
    path('periodes/nouvelle/', views.PeriodeAcademiqueCreateView.as_view(), name='periode_create'),
    path('periodes/<uuid:pk>/modifier/', views.PeriodeAcademiqueUpdateView.as_view(), name='periode_update'),

    # URLs pour Programmes
    path('programmes/', views.ProgrammeListView.as_view(), name='programme_list'),
    path('programmes/nouveau/', views.ProgrammeCreateView.as_view(), name='programme_create'),
    path('programmes/<uuid:pk>/', views.programme_detail, name='programme_detail'),
    path('programmes/<uuid:pk>/modifier/', views.ProgrammeUpdateView.as_view(), name='programme_update'),

    # URLs AJAX pour les dépendances dans le formulaire de candidature
    path('ajax/etablissements/', views.ajax_get_etablissements_publics, name='ajax_etablissements'),
    path('ajax/departements/', views.ajax_get_departements, name='ajax_departements'),
    path('ajax/filieres/', views.ajax_get_filieres, name='ajax_filieres'),
    path('ajax/niveaux/', views.ajax_get_niveaux, name='ajax_niveaux'),
    path('ajax/classes/', views.ajax_get_classes, name='ajax_classes'),

    # API publique avec structure logique
    path('api/public/', include([
        path('departements/<uuid:etablissement_id>/',
             views.api_departements_by_etablissementId_publics,
             name='api_departements_by_etablissement'),
        path('filieres/<uuid:departement_id>/',
             views.api_filieres_by_departementId_publics,
             name='api_filieres_by_departement'),
        path('niveaux/<uuid:filiere_id>/',
             views.api_niveaux_by_filiereId_publics,
             name='api_niveaux_by_filiere'),
    ])),
]
