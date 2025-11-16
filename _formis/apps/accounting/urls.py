# apps/accounting/urls.py
from django.urls import path
from . import views
from . import exports

app_name = 'accounting'

urlpatterns = [

    # Paiements
    path('paiements/<uuid:pk>/valider/', views.comptable_valider_paiement, name='comptable_paiement_valider'),
    path('paiements/<uuid:pk>/rejeter/', views.comptable_rejeter_paiement, name='comptable_paiement_rejeter'),

    # Factures
    path('factures/creer/', views.ComptableFactureCreateView.as_view(), name='comptable_facture_create'),
    path('factures/<uuid:pk>/', views.ComptableFactureDetailView.as_view(), name='comptable_facture_detail'),
    path('factures/<uuid:pk>/modifier/', views.ComptableFactureUpdateView.as_view(),
         name='comptable_facture_update'),
    path('factures/<uuid:pk>/pdf/', views.comptable_facture_pdf, name='comptable_facture_pdf'),
    path('factures/export/csv/', exports.export_factures_csv, name='comptable_factures_export_csv'),
    path('factures/export/excel/', exports.export_factures_excel, name='comptable_factures_export_excel'),

    # Dépenses
    path('depenses/creer/', views.ComptableDepenseCreateView.as_view(), name='comptable_depense_create'),
    path('depenses/<uuid:pk>/', views.ComptableDepenseDetailView.as_view(), name='comptable_depense_detail'),
    path('depenses/<uuid:pk>/modifier/', views.ComptableDepenseUpdateView.as_view(),
         name='comptable_depense_update'),
    path('depenses/<uuid:pk>/approuver/', views.comptable_depense_approuver, name='comptable_depense_approuver'),
    path('depenses/export/csv/', exports.export_depenses_csv, name='comptable_depenses_export_csv'),

    # Plan comptable
    path('comptes/creer/', views.ComptableCompteCreateView.as_view(), name='comptable_compte_create'),

    # Écritures comptables
    path('ecritures/', views.ComptableEcrituresView.as_view(), name='comptable_ecritures'),
    path('ecritures/creer/', views.ComptableEcritureCreateView.as_view(), name='comptable_ecriture_create'),
    path('ecritures/<uuid:pk>/', views.ComptableEcritureDetailView.as_view(), name='comptable_ecriture_detail'),

    # Rapports
    path('rapports/balance/', views.ComptableRapportBalanceView.as_view(), name='comptable_rapport_balance'),
    path('rapports/balance/export/pdf/', exports.export_balance_pdf, name='comptable_balance_export_pdf'),
    path('rapports/balance/export/excel/', exports.export_balance_excel, name='comptable_balance_export_excel'),
    path('rapports/grand-livre/export/pdf/', exports.export_grand_livre_pdf, name='comptable_grand_livre_export_pdf'),

    # Exercices comptables
    path('exercices/cloture/<uuid:pk>/', views.comptable_cloture_exercice, name='comptable_cloture_exercice'),
]
