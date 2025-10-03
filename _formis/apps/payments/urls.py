# apps/payments/urls.py

from django.urls import path, include
from . import views

app_name = 'payments'

urlpatterns = [

    # Inscription et paiements initiaux
    path('inscription/', include([
        path('initier/', views.initier_inscription_paiement, name='initier_inscription'),
        path('verifier-statut/', views.verifier_statut_inscription, name='verifier_statut_inscription'),
    ])),

    # Paiements LigdiCash
    path('ligdicash/', include([
        path('payer/<uuid:paiement_id>/', views.payer_ligdicash, name='payer_ligdicash'),
        path('success/<uuid:paiement_id>/', views.callback_success, name='callback_success'),
        path('error/<uuid:paiement_id>/', views.callback_error, name='callback_error'),
        path('webhook/', views.webhook_ligdicash, name='webhook_ligdicash'),
    ])),

    # Gestion des tranches
    path('tranches/', include([
        path('payer-suivante/', views.payer_prochaine_tranche, name='payer_prochaine_tranche'),
    ])),

    # Consultation des paiements
    path('detail/<uuid:paiement_id>/', views.detail_paiement, name='detail_paiement'),
]