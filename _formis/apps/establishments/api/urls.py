from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'establishments_api'

urlpatterns = [
    # Localités
    path('localites/', views.LocaliteListCreateAPIView.as_view(), name='localite-list-create'),
    path('localites/<int:pk>/', views.LocaliteRetrieveUpdateDestroyAPIView.as_view(), name='localite-detail'),

    # Types d'établissement
    path('types-etablissement/', views.TypeEtablissementListCreateAPIView.as_view(),
         name='type-etablissement-list-create'),
    path('types-etablissement/<int:pk>/', views.TypeEtablissementRetrieveUpdateDestroyAPIView.as_view(),
         name='type-etablissement-detail'),

    # Établissements
    path('etablissements/', views.EtablissementListAPIView.as_view(), name='etablissement-list'),
    path('etablissements/create/', views.EtablissementCreateAPIView.as_view(), name='etablissement-create'),
    path('etablissements/<int:pk>/', views.EtablissementRetrieveAPIView.as_view(), name='etablissement-detail'),
    path('etablissements/<int:pk>/update/', views.EtablissementUpdateAPIView.as_view(), name='etablissement-update'),
    path('etablissements/<int:pk>/delete/', views.EtablissementDestroyAPIView.as_view(), name='etablissement-delete'),

    # Salles
    path('salles/', views.SalleListCreateAPIView.as_view(), name='salle-list-create'),
    path('salles/<int:pk>/', views.SalleRetrieveUpdateDestroyAPIView.as_view(), name='salle-detail'),

    # Campus
    path('campus/', views.CampusListCreateAPIView.as_view(), name='campus-list-create'),
    path('campus/<int:pk>/', views.CampusRetrieveUpdateDestroyAPIView.as_view(), name='campus-detail'),

    # Années académiques
    path('annees-academiques/', views.AnneeAcademiqueListCreateAPIView.as_view(), name='annee-academique-list-create'),

    # Barèmes de notation
    path('baremes-notation/', views.BaremeNotationListCreateAPIView.as_view(), name='bareme-notation-list-create'),

    # Jours fériés
    path('jours-feries/', views.JourFerieListCreateAPIView.as_view(), name='jour-ferie-list-create'),

    # Statistiques
    path('statistiques/', views.statistiques_api_view, name='statistiques'),
    path('etablissements-par-localite/', views.etablissements_par_localite_api, name='etablissements-par-localite'),
]
