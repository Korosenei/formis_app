from django.urls import path, include
from django.views.generic import TemplateView
from . import views

app_name = 'enrollment'

urlpatterns = [
    # ========== PÉRIODES DE CANDIDATURE (Admin) ==========
    path('periodes/', views.PeriodeCandidatureListView.as_view(), name='periode_list'),
    path('periodes/nouvelle/', views.PeriodeCandidatureCreateView.as_view(), name='periode_create'),

    # ========== CANDIDATURES (Public) ==========
    path('candidature/nouvelle/', views.CandidatureCreateView.as_view(), name='candidature_create'),
    path('candidature/success/', views.CandidatureSuccessView.as_view(), name='candidature_success'),
    path('candidature/<uuid:pk>/soumettre/', views.CandidatureSoumettreView.as_view(), name='candidature_soumettre'),

    # Documents publics (pour les candidats)
    path('candidature/<uuid:pk>/documents/', views.candidature_documents, name='candidature_documents_public'),
    path('candidature/<uuid:candidature_pk>/documents/<uuid:document_pk>/delete/', views.document_delete,
         name='document_delete'),

    # ========== GESTION DES CANDIDATURES (Admin/Chef Département) ==========
    path('candidature/<uuid:pk>/evaluer/', views.CandidatureEvaluerView.as_view(), name='candidature_evaluer'),

    # AJAX endpoints pour les modals
    path('candidature/<uuid:pk>/details-ajax/', views.candidature_details_ajax, name='candidature_details_ajax'),
    path('candidature/<uuid:pk>/documents-ajax/', views.candidature_documents_ajax, name='candidature_documents_ajax'),

    # Actions sur les candidatures
    path('candidature/<uuid:pk>/start-exam/', views.candidature_start_exam, name='candidature_start_exam'),
    path('candidature/<uuid:pk>/approve/', views.candidature_approve, name='candidature_approve'),
    path('candidature/<uuid:pk>/reject/', views.candidature_reject, name='candidature_reject'),

    # Export
    path('candidatures/export/', views.export_candidatures, name='export_candidatures'),

    # ========== API PUBLIQUE ==========
    path('api/public/', include([
        path('documents-requis/filiere/<uuid:filiere_id>/',
             views.api_documents_requis_by_filiereId, name='api_documents_requis_filiere'),
        path('documents-requis/niveau/<uuid:niveau_id>/',
             views.api_documents_requis_by_niveauId_publics, name='api_documents_requis_niveau'),
    ])),

    # Inscriptions
    path('inscription/nouvelle/<str:token>/', views.InscriptionAvecPaiementView.as_view(), name='inscription_avec_token'),
    path('inscriptions/', views.InscriptionListView.as_view(), name='inscription_list'),
    path('inscriptions/<uuid:pk>/', views.InscriptionDetailView.as_view(), name='inscription_detail'),
    path('inscriptions/create/', views.InscriptionCreateView.as_view(), name='inscription_create'),
    path('inscriptions/export/', views.export_inscriptions, name='export_inscriptions'),

    # Transferts
    path('transferts/', views.TransfertListView.as_view(), name='transfert_list'),
    path('transferts/create/', views.TransfertCreateView.as_view(), name='transfert_create'),
    path('transferts/<uuid:pk>/approve/', views.transfert_approve, name='transfert_approve'),
]