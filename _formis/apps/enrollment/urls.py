from django.urls import path, include
from django.views.generic import TemplateView
from . import views

app_name = 'enrollment'

urlpatterns = [
    # Dashboard (admin)
    path('', views.enrollment_dashboard, name='dashboard'),

    # URLs publiques (sans authentification requise)
    path('public/', include([
        # Candidature publique - accessible à tous
        path('candidature/create/', views.CandidatureCreateView.as_view(), name='candidature_create'),
        path('candidature/success/', views.CandidatureSuccessView.as_view(), name='candidature_success'),
        path('candidature/<uuid:pk>/', views.CandidatureDetailView.as_view(), name='candidature_detail_public'),
        path('candidature/<uuid:pk>/documents/', views.candidature_documents, name='candidature_documents_public'),
        
        # Page de succès après soumission
        path('candidature/success/', TemplateView.as_view(
            template_name='public/candidature/candidature_success.html'
        ), name='candidature_success'),
        
        # API publique pour récupérer les documents requis
        path('api/candidature/status/<str:numero_candidature>/', views.get_candidature_status, name='candidature_status_api'),
        path('api/documents_by_filiere/<uuid:filiere_id>/',
             views.api_documents_requis_by_filiereId_publics,
             name='api_documents_by_filiere'),
        path('api/documents_by_niveau/<uuid:niveau_id>/',
             views.api_documents_requis_by_niveauId_publics,
             name='api_documents_by_niveau'),
    ])),

    # URLs administratives (authentification requise)
    path('admin/', include([
        # Périodes de candidature
        path('periodes/', views.PeriodeCandidatureListView.as_view(), name='periode_list'),
        path('periodes/create/', views.PeriodeCandidatureCreateView.as_view(), name='periode_create'),

        # Gestion des candidatures (admin)
        path('candidatures/', views.CandidatureListView.as_view(), name='candidature_list'),
        path('candidatures/<uuid:pk>/', views.CandidatureDetailView.as_view(), name='candidature_detail'),
        path('candidatures/<uuid:pk>/edit/', views.CandidatureUpdateView.as_view(), name='candidature_edit'),
        path('candidatures/<uuid:pk>/soumettre/', views.CandidatureSoumettreView.as_view(), name='candidature_submit'),
        path('candidatures/<uuid:pk>/evaluer/', views.CandidatureEvaluerView.as_view(), name='candidature_evaluate'),
        path('candidatures/<uuid:pk>/documents/', views.candidature_documents, name='candidature_documents'),
        path('candidatures/<uuid:candidature_pk>/documents/<uuid:document_pk>/delete/', 
             views.document_delete, name='document_delete'),

        # API pour statistiques
        path('api/statistics/', views.candidature_statistics, name='candidature_statistics'),

        # Inscriptions
        path('inscriptions/', views.InscriptionListView.as_view(), name='inscription_list'),
        path('inscriptions/<uuid:pk>/', views.InscriptionDetailView.as_view(), name='inscription_detail'),
        path('inscriptions/create/', views.InscriptionCreateView.as_view(), name='inscription_create'),

        # Transferts
        path('transferts/', views.TransfertListView.as_view(), name='transfert_list'),
        path('transferts/create/', views.TransfertCreateView.as_view(), name='transfert_create'),
        path('transferts/<uuid:pk>/approve/', views.transfert_approve, name='transfert_approve'),

        # Abandons
        path('abandons/create/', views.AbandonCreateView.as_view(), name='abandon_create'),

        # API pour les statistiques
        path('api/stats/', views.api_stats, name='api_stats'),
    ])),
]