# apps/payments/urls.py

from django.urls import path, include
from . import views

app_name = 'payments'

urlpatterns = [

    path('students/<uuid:pk>/',  views.AdminStudentPaymentsView.as_view(),  name='admin_student_payments'),

    # Vérification statut et initiation
    path('selection-paiement/', views.selection_paiement, name='selection_paiement'),
    path('inscription/verifier-statut/', views.verifier_statut_inscription, name='verifier_statut'),
    path('inscription/initier/', views.initier_inscription_paiement, name='initier_inscription'),

    # Paiement LigdiCash
    path('ligdicash/payer/<uuid:paiement_id>/', views.payer_ligdicash, name='payer_ligdicash'),

    # Callbacks
    path('callback/success/<uuid:paiement_id>/', views.callback_success, name='callback_success'),
    path('callback/error/<uuid:paiement_id>/', views.callback_error, name='callback_error'),

    # Callbacks publics (sans authentification)
    path('public/callback/success/<uuid:paiement_id>/', views.callback_success_public, name='callback_success_public'),
    path('public/callback/error/<uuid:paiement_id>/', views.callback_error_public, name='callback_error_public'),

    # Webhook
    path('webhook/ligdicash/', views.webhook_ligdicash, name='webhook_ligdicash'),

    # Paiement tranches suivantes
    path('payer-prochaine-tranche/', views.payer_prochaine_tranche, name='payer_prochaine_tranche'),

    # Détail paiement
    path('paiement/<uuid:paiement_id>/', views.detail_paiement, name='detail_paiement'),

    # Consultation des paiements
    path('detail/<uuid:paiement_id>/', views.detail_paiement, name='detail_paiement'),

]