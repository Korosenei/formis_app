from django.urls import path
from . import views

app_name = 'evaluations'

urlpatterns = [

    # ========== URLs POUR LES ENSEIGNANTS ==========

    # Liste et gestion des évaluations
    path('enseignant/', views.evaluations_enseignant, name='list_enseignant'),
    path('enseignant/creer/', views.creer_evaluation, name='create'),
    path('enseignant/<int:pk>/', views.detail_evaluation_enseignant, name='detail_enseignant'),
    path('enseignant/<int:pk>/modifier/', views.modifier_evaluation, name='edit'),
    path('enseignant/<int:pk>/supprimer/', views.supprimer_evaluation, name='delete'),

    # Correction des compositions
    path('composition/<int:pk>/corriger/', views.corriger_composition, name='corriger_composition'),
    path('evaluation/<int:pk>/correction-masse/', views.correction_en_masse, name='correction_en_masse'),
    path('evaluation/<int:pk>/publier-correction/', views.publier_correction, name='publier_correction'),

    # Statistiques enseignant
    path('evaluation/<int:pk>/statistiques/', views.statistiques_evaluation, name='statistiques'),

    # ========== URLs POUR LES APPRENANTS ==========

    # Liste et consultation des évaluations
    path('apprenant/', views.evaluations_apprenant, name='list_apprenant'),
    path('apprenant/<int:pk>/', views.detail_evaluation_apprenant, name='detail_apprenant'),

    # Composition des évaluations
    path('evaluation/<int:pk>/upload/', views.upload_composition, name='upload_composition'),
    path('evaluation/<int:pk>/soumettre/', views.soumettre_composition, name='soumettre_composition'),
    path('fichier-composition/<int:pk>/supprimer/', views.supprimer_fichier_composition,
         name='supprimer_fichier_composition'),

    # Notes de l'apprenant
    path('apprenant/notes/', views.mes_notes, name='mes_notes'),

    # ========== URLs COMMUNES (TÉLÉCHARGEMENTS ET VISUALISATION) ==========

    # Téléchargement des fichiers
    path('evaluation/<int:pk>/fichier/', views.telecharger_fichier_evaluation, name='telecharger_evaluation'),
    path('evaluation/<int:pk>/correction/', views.telecharger_fichier_correction, name='telecharger_correction'),
    path('fichier-composition/<int:pk>/telecharger/', views.telecharger_fichier_composition,
         name='telecharger_composition'),

    # Visualisation des fichiers
    path('voir/<str:type_fichier>/<int:pk>/', views.voir_fichier, name='voir_fichier'),

    # ========== APIs AJAX ==========

    # API pour récupérer le temps restant d'une évaluation
    # path('api/evaluation/<int:pk>/temps-restant/', views.api_temps_restant, name='api_temps_restant'),
    #
    # # API pour les statistiques d'une évaluation
    # path('api/evaluation/<int:pk>/statistiques/', views.api_statistiques_evaluation, name='api_statistiques'),
    #
    # # API pour mettre à jour le statut d'une évaluation
    # path('api/evaluation/<int:pk>/statut/', views.api_mettre_a_jour_statut, name='api_statut'),
    #
    # # API pour vérifier la disponibilité d'une évaluation
    # path('api/evaluation/<int:pk>/disponibilite/', views.api_verifier_disponibilite, name='api_disponibilite'),

    # ========== MOYENNES ET CLASSEMENTS ==========

    # Moyennes par module
    path('module/<int:module_id>/moyennes/', views.moyennes_module, name='moyennes_module'),

    # Classement d'un module
    # path('module/<int:module_id>/classement/', views.classement_module, name='classement_module'),
    #
    # # Moyennes générales d'un apprenant
    # path('apprenant/<int:apprenant_id>/moyennes/', views.moyennes_apprenant, name='moyennes_apprenant'),
    #
    # # ========== GESTION DES NOTES ==========
    #
    # # Création et modification de notes individuelles
    # path('note/creer/<int:composition_id>/', views.creer_note, name='creer_note'),
    # path('note/<int:pk>/modifier/', views.modifier_note, name='modifier_note'),
    # path('note/<int:pk>/supprimer/', views.supprimer_note, name='supprimer_note'),
    #
    # # Import/Export de notes
    # path('evaluation/<int:pk>/importer-notes/', views.importer_notes, name='importer_notes'),
    # path('evaluation/<int:pk>/exporter-notes/', views.exporter_notes, name='exporter_notes'),
    #
    # # ========== RAPPORTS ET STATISTIQUES ==========
    #
    # # Rapport détaillé d'une évaluation
    # path('evaluation/<int:pk>/rapport/', views.rapport_evaluation, name='rapport_evaluation'),
    #
    # # Statistiques globales pour un enseignant
    # path('enseignant/statistiques/', views.statistiques_enseignant, name='statistiques_enseignant'),
    #
    # # Bulletin de notes d'un apprenant
    # path('apprenant/<int:apprenant_id>/bulletin/', views.bulletin_apprenant, name='bulletin_apprenant'),
    #
    # # ========== ACTIONS EN MASSE ==========
    #
    # # Actions en masse sur les évaluations
    # path('evaluations/actions-masse/', views.actions_masse_evaluations, name='actions_masse_evaluations'),
    #
    # # Recalcul des moyennes
    # path('moyennes/recalculer/', views.recalculer_moyennes, name='recalculer_moyennes'),
    #
    # # ========== ARCHIVAGE ET HISTORIQUE ==========
    #
    # # Archiver une évaluation
    # path('evaluation/<int:pk>/archiver/', views.archiver_evaluation, name='archiver_evaluation'),
    #
    # # Historique des évaluations
    # path('historique/', views.historique_evaluations, name='historique'),
    #
    # # ========== NOTIFICATIONS ET ALERTES ==========
    #
    # # Notifications pour les évaluations à venir
    # path('notifications/evaluations/', views.notifications_evaluations, name='notifications_evaluations'),
    #
    # # Alertes pour les corrections en retard
    # path('alertes/corrections/', views.alertes_corrections, name='alertes_corrections'),

]