from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Page d'accueil publique
    path('', views.HomeView.as_view(), name='home'),

    # Pages publiques
    path('establishments/', views.EstablishmentListView.as_view(), name='establishment_list'),
    path('establishments/<uuid:pk>/', views.EstablishmentDetailView.as_view(), name='establishment_detail'),
    path('apply/', views.ApplicationFormView.as_view(), name='apply'),
    path('contact/', views.ContactView.as_view(), name='contact'),
    path('about/', views.AboutView.as_view(), name='about'),
]
