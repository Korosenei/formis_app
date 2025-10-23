from django.urls import path
from . import views

app_name = 'evaluations'

urlpatterns = [

    # ========== URLs POUR LES ENSEIGNANTS ==========
    # Liste et gestion des évaluations
    path('enseignant/', views.evaluations_enseignant, name='list_enseignant'),
    path('enseignant/creer/', views.creer_evaluation, name='evaluation_create'),
    path('enseignant/<uuid:pk>/', views.detail_evaluation_enseignant, name='evaluation_detail_enseignant'),
    path('enseignant/<uuid:pk>/modifier/', views.modifier_evaluation, name='evaluation_edit'),
    path('enseignant/<uuid:pk>/supprimer/', views.supprimer_evaluation, name='evaluation_delete'),

    # Correction des compositions
    path('composition/<uuid:pk>/corriger/', views.corriger_composition, name='corriger_composition'),
    path('evaluation/<uuid:pk>/correction_masse/', views.correction_en_masse, name='correction_en_masse'),
    path('evaluation/<uuid:pk>/publier_correction/', views.publier_correction, name='publier_correction'),

    # Statistiques enseignant
    path('evaluation/<uuid:pk>/statistiques/', views.statistiques_evaluation, name='statistiques'),
    path('enseignant/statistiques/', views.statistiques_enseignant, name='statistiques_enseignant'),


    # ========== URLs POUR LES APPRENANTS ==========
    # Liste et consultation des évaluations
    path('apprenant/', views.evaluations_apprenant, name='list_apprenant'),
    path('apprenant/<uuid:pk>/', views.detail_evaluation_apprenant, name='evaluation_detail_apprenant'),

    # Composition des évaluations
    path('evaluation/<uuid:pk>/upload/', views.upload_composition, name='upload_composition'),
    path('evaluation/<uuid:pk>/soumettre/', views.soumettre_composition, name='soumettre_composition'),
    path('fichier-composition/<uuid:pk>/supprimer/', views.supprimer_fichier_composition,
         name='supprimer_fichier_composition'),

    # Notes de l'apprenant
    path('apprenant/notes/', views.mes_notes, name='mes_notes'),
    path('apprenant/<uuid:apprenant_id>/bulletin/', views.bulletin_apprenant, name='bulletin_apprenant'),


    # ========== URLs COMMUNES (TÉLÉCHARGEMENTS ET VISUALISATION) ==========
    # Téléchargement des fichiers
    path('evaluation/<uuid:pk>/fichier/', views.telecharger_fichier_evaluation, name='telecharger_evaluation'),
    path('evaluation/<uuid:pk>/correction/', views.telecharger_fichier_correction, name='telecharger_correction'),
    path('fichier_composition/<uuid:pk>/telecharger/', views.telecharger_fichier_composition,
         name='telecharger_composition'),

    # Visualisation des fichiers
    path('voir/<str:type_fichier>/<uuid:pk>/', views.voir_fichier, name='voir_fichier'),


    # ========== APIs AJAX ==========
    # API pour récupérer le temps restant d'une évaluation
    path('api/evaluation/<uuid:pk>/temps-restant/', views.api_temps_restant, name='api_temps_restant'),

    # # API pour les statistiques d'une évaluation
    path('api/evaluation/<uuid:pk>/statistiques/', views.api_statistiques_evaluation, name='api_statistiques'),

    # # API pour mettre à jour le statut d'une évaluation
    path('api/evaluation/<uuid:pk>/statut/', views.api_mettre_a_jour_statut, name='api_statut'),


    # ========== GESTION DES NOTES ==========
    # Création et modification de notes individuelles
    path('note/creer/<int:composition_id>/', views.creer_note, name='creer_note'),
    path('note/<uuid:pk>/modifier/', views.modifier_note, name='modifier_note'),
    path('note/<uuid:pk>/supprimer/', views.supprimer_note, name='supprimer_note'),

    # Import/Export de notes
    path('evaluation/<uuid:pk>/importer-notes/', views.importer_notes, name='importer_notes'),
    path('evaluation/<uuid:pk>/exporter-notes/', views.exporter_notes, name='exporter_notes'),


    # ========== RAPPORTS ET STATISTIQUES ==========
    # Rapport détaillé d'une évaluation
    path('evaluation/<uuid:pk>/rapport/', views.rapport_evaluation, name='rapport_evaluation'),


    # ========== ACTIONS EN MASSE ==========
    # Actions en masse sur les évaluations
    path('evaluations/actions-masse/', views.actions_masse_evaluations, name='actions_masse_evaluations'),


    # ========== MOYENNES ==========
    # Moyennes par module (si applicable)
    # path('module/<int:module_id>/moyennes/', views.moyennes_module, name='moyennes_module'),

]