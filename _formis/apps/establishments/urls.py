from django.urls import path, include
from . import views

app_name = 'establishments'

# URLs principales
urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),

    # Établissements
    path('etablissements/', views.EtablissementListView.as_view(), name='etablissement_list'),
    path('etablissements/create/', views.EtablissementCreateView.as_view(), name='etablissement_create'),
    path('etablissements/<int:pk>/', views.EtablissementDetailView.as_view(), name='etablissement_detail'),
    path('etablissements/<int:pk>/edit/', views.EtablissementUpdateView.as_view(), name='etablissement_edit'),
    path('etablissements/<int:pk>/delete/', views.EtablissementDeleteView.as_view(), name='etablissement_delete'),
    path('etablissements/<int:etablissement_id>/parametres/', views.parametres_etablissement_view,
         name='etablissement_parametres'),
    path('etablissements/<int:etablissement_id>/rapport-pdf/', views.rapport_etablissement_pdf,
         name='etablissement_rapport_pdf'),

    # Types d'établissements
    path('types/', views.TypeEtablissementListView.as_view(), name='type_etablissement_list'),
    path('types/create/', views.TypeEtablissementCreateView.as_view(), name='type_etablissement_create'),

    # Localités
    path('localites/', views.LocaliteListView.as_view(), name='localite_list'),
    path('localites/create/', views.LocaliteCreateView.as_view(), name='localite_create'),

    # Salles
    path('salles/', views.SalleListView.as_view(), name='salle_list'),
    path('salles/create/', views.SalleCreateView.as_view(), name='salle_create'),
    path('salles/<int:pk>/', views.SalleDetailView.as_view(), name='salle_detail'),
    path('salles/<int:pk>/edit/', views.SalleUpdateView.as_view(), name='salle_edit'),

    # Campus
    path('campus/', views.CampusListView.as_view(), name='campus_list'),
    path('campus/<int:pk>/', views.CampusDetailView.as_view(), name='campus_detail'),

    # Années académiques
    path('annees-academiques/', views.AnneeAcademiqueListView.as_view(), name='annee_academique_list'),
    path('annees-academiques/create/', views.AnneeAcademiqueCreateView.as_view(), name='annee_academique_create'),

    # Barèmes de notation
    path('baremes/', views.BaremeNotationListView.as_view(), name='bareme_notation_list'),
    path('baremes/<int:pk>/', views.bareme_notation_detail, name='bareme_notation_detail'),
    path('baremes/create/', views.bareme_notation_create, name='bareme_notation_create'),

    # Jours fériés
    path('jours-feries/', views.JourFerieListView.as_view(), name='jour_ferie_list'),
    path('jours-feries/create/', views.JourFerieCreateView.as_view(), name='jour_ferie_create'),

    # Vues utilitaires
    path('statistiques/', views.statistiques_view, name='statistiques'),
    path('calendrier/', views.calendrier_view, name='calendrier'),
    path('carte/', views.carte_etablissements_view, name='carte'),
    path('recherche/', views.recherche_globale_view, name='recherche'),
    path('export/etablissements/', views.export_etablissements, name='export_etablissements'),
    path('mise-a-jour-etudiants/', views.mise_a_jour_etudiants_view, name='mise_a_jour_etudiants'),

    # URLs Ajax
    path('ajax/salles-by-etablissement/', views.ajax_salles_by_etablissement, name='ajax_salles_by_etablissement'),
    path('ajax/campus-by-etablissement/', views.ajax_campus_by_etablissement, name='ajax_campus_by_etablissement'),

    # URLs API
    path('api/public/', include([
        path('annees-academiques/', views.api_annees_academiques, name='api_annees-academiques_publics'),
        path('etablissements/', views.api_etablissements_publics, name='api_etablissements_publics'),
        path('etablissements/<int:etablissement_id>/', views.api_etablissement_detail, name='api_etablissement_detail'),
    ])),
]
