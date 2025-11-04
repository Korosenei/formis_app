# apps/payments/urls.py

from django.urls import path, include
from . import views

app_name = 'payments'

urlpatterns = [

    # Vérification statut et initiation
    path('inscription/verifier-statut/', views.verifier_statut_inscription, name='verifier_statut'),
    path('inscription/initier/', views.initier_inscription_paiement, name='initier_inscription'),

    # Paiement LigdiCash
    path('ligdicash/payer/<uuid:paiement_id>/', views.payer_ligdicash, name='payer_ligdicash'),

    # Callbacks
    path('callback/success/<uuid:paiement_id>/', views.callback_success, name='callback_success'),
    path('callback/error/<uuid:paiement_id>/', views.callback_error, name='callback_error'),

    # Webhook
    path('webhook/ligdicash/', views.webhook_ligdicash, name='webhook_ligdicash'),

    # Paiement tranches suivantes
    path('payer-prochaine-tranche/', views.payer_prochaine_tranche, name='payer_prochaine_tranche'),

    # Détail paiement
    path('paiement/<uuid:paiement_id>/', views.detail_paiement, name='detail_paiement'),

    # Paiements LigdiCash
    path('ligdicash/', include([
        path('payer/<uuid:paiement_id>/', views.payer_ligdicash, name='payer_ligdicash'),
        path('success/<uuid:paiement_id>/', views.callback_success, name='callback_success'),
        path('error/<uuid:paiement_id>/', views.callback_error, name='callback_error'),
        # path('webhook/', views.webhook_ligdicash, name='webhook_ligdicash'),
    ])),

    # Gestion des tranches
    path('tranches/', include([
        path('payer-suivante/', views.payer_prochaine_tranche, name='payer_prochaine_tranche'),
    ])),

    # Consultation des paiements
    path('detail/<uuid:paiement_id>/', views.detail_paiement, name='detail_paiement'),


    # Paiements publics (sans authentification)
    path('public/<uuid:paiement_id>/<str:token>/', views.payer_ligdicash_public, name='payer_ligdicash_public'),
    path('public/success/<uuid:paiement_id>/<str:token>/', views.callback_success_public, name='callback_success_public'),
    path('public/error/<uuid:paiement_id>/<str:token>/', views.callback_error_public, name='callback_error_public'),

    path('webhook/ligdicash/', views.webhook_ligdicash, name='webhook_ligdicash'),
]