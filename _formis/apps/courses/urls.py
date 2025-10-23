# apps/courses/urls.py

from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # ============== MODULES ==============
    path('modules/', views.ModuleListView.as_view(), name='module_list'),
    path('modules/create/', views.ModuleCreateView.as_view(), name='module_create'),
    path('modules/<uuid:pk>/', views.ModuleDetailView.as_view(), name='module_detail'),
    path('modules/<uuid:pk>/edit/', views.ModuleUpdateView.as_view(), name='module_edit'),
    path('modules/<uuid:pk>/delete/', views.ModuleDeleteView.as_view(), name='module_delete'),

    # ============== MATIÈRES ==============
    path('matieres/', views.MatiereListView.as_view(), name='matiere_list'),
    path('matieres/create/', views.MatiereCreateView.as_view(), name='matiere_create'),
    path('matieres/<uuid:pk>/', views.MatiereDetailView.as_view(), name='matiere_detail'),
    path('matieres/<uuid:pk>/edit/', views.MatiereUpdateView.as_view(), name='matiere_edit'),
    path('matieres/<uuid:pk>/delete/', views.MatiereDeleteView.as_view(), name='matiere_delete'),

    # ============== EMPLOIS DU TEMPS ==============
    path('emplois-du-temps/', views.EmploiDuTempsListView.as_view(), name='emploi_du_temps_list'),
    path('emplois-du-temps/create/', views.EmploiDuTempsCreateView.as_view(), name='emploi_du_temps_create'),
    path('emplois-du-temps/<uuid:pk>/', views.EmploiDuTempsDetailView.as_view(), name='emploi_du_temps_detail'),
    path('emplois-du-temps/<uuid:pk>/edit/', views.EmploiDuTempsUpdateView.as_view(), name='emploi_du_temps_edit'),
    path('emplois-du-temps/<uuid:pk>/delete/', views.EmploiDuTempsDeleteView.as_view(), name='emploi_du_temps_delete'),
    path('emplois-du-temps/<uuid:pk>/publish/', views.emploi_du_temps_publish, name='emploi_du_temps_publish'),
    path('emplois-du-temps/generate/', views.emploi_du_temps_generate, name='emploi_du_temps_generate'),

    # ============== COURS ==============
    path('cours/', views.CoursListView.as_view(), name='cours_list'),
    path('cours/create/', views.CoursCreateView.as_view(), name='cours_create'),
    path('cours/<uuid:pk>/', views.CoursDetailView.as_view(), name='cours_detail'),
    path('cours/<uuid:pk>/edit/', views.CoursUpdateView.as_view(), name='cours_edit'),
    path('cours/<uuid:pk>/delete/', views.CoursDeleteView.as_view(), name='cours_delete'),
    path('cours/<uuid:pk>/start/', views.cours_start, name='cours_start'),
    path('cours/<uuid:pk>/end/', views.cours_end, name='cours_end'),

    # Streaming
    path('cours/<uuid:pk>/streaming/', views.streaming_view, name='cours_streaming'),

    # ============== RESSOURCES ==============
    path('cours/<uuid:cours_id>/ressources/', views.ressource_list, name='ressource_list'),
    path('cours/<uuid:cours_id>/ressources/create/', views.ressource_create, name='ressource_create'),
    path('ressources/<uuid:pk>/', views.ressource_view, name='ressource_view'),
    path('ressources/<uuid:pk>/edit/', views.ressource_update, name='ressource_edit'),
    path('ressources/<uuid:pk>/delete/', views.ressource_delete, name='ressource_delete'),
    path('ressources/<uuid:pk>/download/', views.ressource_download, name='ressource_download'),
    path('ressources/<uuid:pk>/increment-views/', views.ressource_increment_views, name='ressource_increment_views'),

    # ============== CAHIER DE TEXTE ==============
    path('cahiers-texte/', views.cahier_texte_list, name='cahier_texte_list'),
    path('cours/<uuid:cours_id>/cahier-texte/', views.cahier_texte_view, name='cahier_texte_view'),
    path('cours/<uuid:cours_id>/cahier-texte/edit/', views.cahier_texte_create_or_update, name='cahier_texte_edit'),

    # ============== URLS PRESENCE ==============
    path('presences/', views.PresenceListView.as_view(), name='presence_list'),
    path('cours/<uuid:cours_id>/presences/', views.presence_bulk_create, name='presence_bulk_create'),

    # ============== AJAX ==============
    path('ajax/modules-by-niveau/', views.ajax_get_modules_by_niveau, name='ajax_modules_by_niveau'),
    path('ajax/matieres-by-niveau/', views.ajax_get_matieres_by_niveau, name='ajax_matieres_by_niveau'),
    path('ajax/classes-by-niveau/', views.ajax_get_classes_by_niveau, name='ajax_classes_by_niveau'),
    path('ajax/salles-disponibles/', views.ajax_get_salles_disponibles, name='ajax_salles_disponibles'),
    path('ajax/check-conflit/', views.ajax_check_conflit_cours, name='ajax_check_conflit'),

    # ============== EXPORTS ==============
    path('modules/export/', views.export_modules, name='export_modules'),
    path('matieres/export/', views.export_matieres, name='export_matieres'),
    path('cours/export/', views.export_cours, name='export_cours'),
]