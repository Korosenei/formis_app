# apps/courses/urls.py

from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # ============== URLS DASHBOARD ==============
    path('dashboard/enseignant/', views.dashboard_enseignant, name='dashboard_enseignant'),
    path('dashboard/etudiant/', views.dashboard_etudiant, name='dashboard_etudiant'),

    # ============== URLS MODULE ==============
    path('modules/', views.ModuleListView.as_view(), name='module_list'),
    path('modules/create/', views.ModuleCreateView.as_view(), name='module_create'),
    path('modules/<uuid:pk>/', views.ModuleDetailView.as_view(), name='module_detail'),
    path('modules/<uuid:pk>/edit/', views.ModuleUpdateView.as_view(), name='module_edit'),
    path('modules/<uuid:pk>/delete/', views.ModuleDeleteView.as_view(), name='module_delete'),

    # ============== URLS MATIERE ==============
    path('matieres/', views.MatiereListView.as_view(), name='matiere_list'),
    path('matieres/create/', views.MatiereCreateView.as_view(), name='matiere_create'),
    path('matieres/<uuid:pk>/', views.MatiereDetailView.as_view(), name='matiere_detail'),
    path('matieres/<uuid:pk>/edit/', views.MatiereUpdateView.as_view(), name='matiere_edit'),

    # ============== URLS COURS ==============
    path('', views.CoursListView.as_view(), name='cours_list'),
    path('cours/create/', views.CoursCreateView.as_view(), name='cours_create'),
    path('cours/<uuid:pk>/', views.CoursDetailView.as_view(), name='cours_detail'),
    path('cours/<uuid:pk>/edit/', views.CoursUpdateView.as_view(), name='cours_edit'),
    path('cours/<uuid:pk>/streaming/', views.streaming_view, name='cours_streaming'),

    # ============== URLS CAHIER DE TEXTE ==============
    path('cahier-texte/', views.CahierTexteListView.as_view(), name='cahier_texte_list'),
    path('cours/<uuid:cours_id>/cahier-texte/', views.cahier_texte_create_or_update, name='cahier_texte_form'),

    # ============== URLS PRESENCE ==============
    path('presences/', views.PresenceListView.as_view(), name='presence_list'),
    path('cours/<uuid:cours_id>/presences/', views.presence_bulk_create, name='presence_bulk_create'),

    # ============== URLS RESSOURCE ==============
    path('cours/<uuid:cours_id>/ressources/create/', views.RessourceCreateView.as_view(), name='ressource_create'),
    path('ressources/<uuid:pk>/edit/', views.RessourceUpdateView.as_view(), name='ressource_edit'),
    path('ressources/<uuid:pk>/download/', views.ressource_download, name='ressource_download'),

    # ============== URLS EMPLOI DU TEMPS ==============
    path('emplois-du-temps/', views.EmploiDuTempsListView.as_view(), name='emploi_du_temps_list'),
    path('emplois-du-temps/create/', views.EmploiDuTempsCreateView.as_view(), name='emploi_du_temps_create'),
    path('emplois-du-temps/<uuid:pk>/', views.EmploiDuTempsDetailView.as_view(), name='emploi_du_temps_detail'),
    path('emplois-du-temps/<uuid:pk>/edit/', views.EmploiDuTempsUpdateView.as_view(), name='emploi_du_temps_edit'),

    # ============== URLS CRENEAU HORAIRE ==============
    path('emplois-du-temps/<uuid:emploi_du_temps_id>/creneaux/create/',
         views.CreneauHoraireCreateView.as_view(), name='creneau_create'),

    # ============== URLS AJAX ==============
    path('ajax/matiere-modules/', views.ajax_get_matiere_modules, name='ajax_matiere_modules'),
    path('ajax/classes/', views.ajax_get_classes, name='ajax_classes'),
]