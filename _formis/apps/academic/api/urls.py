
from django.urls import path
from . import views

app_name = 'academic_api'

urlpatterns = [
    # Départements
    path('departements/', views.DepartementListCreateAPIView.as_view(), name='departement_list_create'),
    path('departements/<int:pk>/', views.DepartementRetrieveUpdateDestroyAPIView.as_view(), name='departement_detail'),
    
    # Filières
    path('filieres/', views.FiliereListCreateAPIView.as_view(), name='filiere_list_create'),
    path('filieres/<int:pk>/', views.FiliereRetrieveUpdateDestroyAPIView.as_view(), name='filiere_detail'),
    
    # Niveaux
    path('niveaux/', views.NiveauListCreateAPIView.as_view(), name='niveau_list_create'),
    path('niveaux/<int:pk>/', views.NiveauRetrieveUpdateDestroyAPIView.as_view(), name='niveau_detail'),
    
    # Classes
    path('classes/', views.ClasseListCreateAPIView.as_view(), name='classe_list_create'),
    path('classes/<int:pk>/', views.ClasseRetrieveUpdateDestroyAPIView.as_view(), name='classe_detail'),
    
    # Périodes académiques
    path('periodes/', views.PeriodeAcademiqueListCreateAPIView.as_view(), name='periode_list_create'),
    path('periodes/<int:pk>/', views.PeriodeAcademiqueRetrieveUpdateDestroyAPIView.as_view(), name='periode_detail'),
    
    # Programmes
    path('programmes/', views.ProgrammeListCreateAPIView.as_view(), name='programme_list_create'),
    path('programmes/<int:pk>/', views.ProgrammeRetrieveUpdateDestroyAPIView.as_view(), name='programme_detail'),
    
        # Endpoints utilitaires
    path('utils/departements/<uuid:etablissement_id>/', views.departements_by_etablissement, name='departements_by_etablissement'),
    path('utils/filieres/<int:etablissement_id>/', views.filieres_by_etablissement, name='filieres_by_etablissement'),
    path('utils/niveaux/<int:filiere_id>/', views.niveaux_by_filiere, name='niveaux_by_filiere'),
    path('utils/classes/<int:niveau_id>/', views.classes_by_niveau, name='classes_by_niveau'),
    
    # Statistiques et opérations en lot
    path('stats/', views.academic_statistics, name='academic_statistics'),
    path('bulk-update-status/', views.bulk_update_status, name='bulk_update_status'),
]
