# apps/core/dashboard_urls.py
from django.urls import path, include
from . import dashboard_views

app_name = 'dashboard'

urlpatterns = [
    # Redirection selon le rôle
    path('', dashboard_views.DashboardRedirectView.as_view(), name='redirect'),

    # ================================
    # ROUTES ADMIN ÉTABLISSEMENT
    # ================================
    path('admin/', include([
        path('', dashboard_views.AdminDashboardView.as_view(), name='admin'),
        path('periodes/', dashboard_views.AdminPeriodesView.as_view(), name='admin_periodes'),

        # Gestion des utilisateurs
        path('users/', include([
            path('', dashboard_views.AdminUsersView.as_view(), name='admin_users'),
            path('<uuid:pk>/toggle-status/', dashboard_views.admin_toggle_user_status, name='admin_user_toggle_status'),
            path('<uuid:pk>/reset-password/', dashboard_views.admin_reset_user_password,
                 name='admin_user_reset_password'),
            path('export/', dashboard_views.admin_export_users, name='admin_users_export'),
        ])),

        path('comptables/', dashboard_views.AdminComptablesView.as_view(), name='admin_comptables'),

        # Enseignants et Étudiants
        path('department_heads/', dashboard_views.AdminDepartmentHeadsView.as_view(), name='admin_department_heads'),
        path('students/', dashboard_views.AdminStudentsView.as_view(), name='admin_students'),
        path('teachers/', dashboard_views.AdminTeachersView.as_view(), name='admin_teachers'),

        # Candidatures et Inscriptions
        path('candidatures/', dashboard_views.AdminCandidaturesView.as_view(), name='admin_candidatures'),
        path('inscriptions/', dashboard_views.AdminInscriptionsView.as_view(), name='admin_inscriptions'),

        # Paiements
        path('paiements/', include([
            path('', dashboard_views.AdminPaiementsView.as_view(), name='admin_paiements'),
            path('<uuid:pk>/validate/', dashboard_views.admin_validate_payment, name='admin_payment_validate'),
            path('<uuid:pk>/reject/', dashboard_views.admin_reject_payment, name='admin_payment_reject'),
        ])),

        # Structure académique
        path('departments/', dashboard_views.AdminDepartementsView.as_view(), name='admin_departments'),
        path('filieres/', dashboard_views.AdminFilieresView.as_view(), name='admin_filieres'),
        path('niveaux/', dashboard_views.AdminNiveauxView.as_view(), name='admin_niveaux'),
        path('classes/', dashboard_views.AdminClassesView.as_view(), name='admin_classes'),

        # Modules et Matières
        path('modules/', dashboard_views.AdminModulesView.as_view(), name='admin_modules'),
        path('matieres/', dashboard_views.AdminMatieresView.as_view(), name='admin_matieres'),

        # Cours et Évaluations
        path('courses/', dashboard_views.AdminCoursesView.as_view(), name='admin_courses'),
        path('evaluations/', dashboard_views.AdminEvaluationsView.as_view(), name='admin_evaluations'),
        path('cahiers_texte/', dashboard_views.AdminCahiersTexteView.as_view(), name='admin_cahiers_texte'),

        # Emplois du temps et Ressources
        path('emplois_du_temps/', dashboard_views.AdminEmploiDuTempsView.as_view(), name='admin_emplois_du_temps'),
        path('ressources/', dashboard_views.AdminRessourcesView.as_view(), name='admin_ressources'),

        # Salles et Paramètres
        path('salles/', dashboard_views.admin_salles, name='admin_salles'),
        path('reports/', dashboard_views.AdminReportsView.as_view(), name='admin_reports'),
        path('settings/', dashboard_views.AdminSettingsView.as_view(), name='admin_settings'),
    ])),

    # ================================
    # ROUTES COMPTABLE
    # ================================
    path('comptable/', include([
        path('', dashboard_views.ComptableDashboardView.as_view(), name='comptable'),

        # Paiements
        path('paiements/', dashboard_views.ComptablePaiementsView.as_view(), name='comptable_paiements'),

        # Factures
        path('factures/', dashboard_views.ComptableFacturesView.as_view(), name='comptable_factures'),

        # Dépenses
        path('depenses/', dashboard_views.ComptableDepensesView.as_view(), name='comptable_depenses'),

        # Plan comptable
        path('comptes/', dashboard_views.ComptableComptesView.as_view(), name='comptable_comptes'),

        # Écritures comptables
        path('ecritures/', dashboard_views.ComptableEcrituresView.as_view(), name='comptable_ecritures'),

        # Rapports
        path('rapports/', dashboard_views.ComptableRapportsView.as_view(), name='comptable_rapports'),
        path('rapports/balance/', dashboard_views.ComptableRapportBalanceView.as_view(), name='comptable_rapport_balance'),
        path('rapports/bilan/', dashboard_views.comptable_rapport_bilan, name='comptable_rapport_bilan'),
        path('rapports/compte-resultat/', dashboard_views.comptable_rapport_resultat,
             name='comptable_rapport_resultat'),
        path('rapports/tresorerie/', dashboard_views.comptable_rapport_tresorerie, name='comptable_rapport_tresorerie'),

        # Budget
        path('budget/', dashboard_views.ComptableBudgetView.as_view(), name='comptable_budget'),

        # Exercices comptables
        path('exercices/', dashboard_views.ComptableExercicesView.as_view(), name='comptable_exercices'),
    ])),

    # ================================
    # ROUTES CHEF DE DÉPARTEMENT
    # ================================
    path('department_head/', include([
        path('', dashboard_views.DepartmentHeadDashboardView.as_view(), name='department_head'),

        # Gestion des personnes
        path('teachers/', dashboard_views.DepartmentHeadTeachersView.as_view(), name='department_head_teachers'),
        path('students/', dashboard_views.DepartmentHeadStudentsView.as_view(), name='department_head_students'),

        # Candidatures et Inscriptions
        path('candidatures/', dashboard_views.DepartmentHeadCandidaturesView.as_view(),
             name='department_head_candidatures'),
        path('inscriptions/', dashboard_views.DepartmentHeadInscriptionsView.as_view(),
             name='department_head_inscriptions'),

        # Paiements
        path('paiements/', include([
            path('', dashboard_views.DepartmentHeadPaiementsView.as_view(), name='department_head_paiements'),
            path('<uuid:pk>/validate/', dashboard_views.admin_validate_payment,
                 name='department_head_payment_validate'),
            path('<uuid:pk>/reject/', dashboard_views.admin_reject_payment, name='department_head_payment_reject'),
        ])),

        # Structure académique
        path('filieres/', dashboard_views.DepartmentHeadFilieresView.as_view(), name='department_head_filieres'),
        path('niveaux/', dashboard_views.DepartmentHeadNiveauxView.as_view(), name='department_head_niveaux'),
        path('classes/', dashboard_views.DepartmentHeadClassesView.as_view(), name='department_head_classes'),

        # Modules et Matières
        path('modules/', dashboard_views.DepartmentHeadModulesView.as_view(), name='department_head_modules'),
        path('matieres/', dashboard_views.DepartmentHeadMatieresView.as_view(), name='department_head_matieres'),

        # Cours et Évaluations
        path('courses/', dashboard_views.DepartmentHeadCoursesView.as_view(), name='department_head_courses'),
        path('evaluations/', dashboard_views.DepartmentHeadEvaluationsView.as_view(),
             name='department_head_evaluations'),
        path('cahiers_texte/', dashboard_views.DepartmentHeadCahiersTexteView.as_view(),
             name='department_head_cahiers_texte'),

        # Emplois du temps et Ressources
        path('emplois_du_temps/', dashboard_views.DepartmentHeadEmploiDuTempsView.as_view(),
             name='department_head_emplois_du_temps'),
        path('ressources/', dashboard_views.DepartmentHeadRessourcesView.as_view(),
             name='department_head_ressources'),
        path('reports/', dashboard_views.DepartmentHeadReportsView.as_view(), name='department_head_reports'),
    ])),

    # ================================
    # ROUTES ENSEIGNANT
    # ================================
    path('teacher/', include([
        path('', dashboard_views.TeacherDashboardView.as_view(), name='teacher'),

        # Mes cours
        path('courses/', dashboard_views.TeacherCoursesView.as_view(), name='teacher_courses'),

        # Mes étudiants
        path('students/', dashboard_views.TeacherStudentsView.as_view(), name='teacher_students'),

        # Évaluations
        path('evaluations/', include([
            path('', dashboard_views.TeacherEvaluationsView.as_view(), name='teacher_evaluations'),
            path('<uuid:pk>/correction/', dashboard_views.TeacherCorrectionView.as_view(),
                 name='teacher_evaluation_correction'),
        ])),

        # Notes et corrections
        path('corrections/', dashboard_views.TeacherCorrectionView.as_view(), name='teacher_corrections'),

        # Présences
        path('presences/', dashboard_views.TeacherPresencesView.as_view(), name='teacher_presences'),

        # Emploi du temps
        path('emplois_du_temps/', dashboard_views.TeacherEmploiDuTempsView.as_view(),
             name='teacher_emplois_du_temps'),

        # Ressources pédagogiques
        path('resources/', dashboard_views.TeacherResourcesView.as_view(), name='teacher_resources'),

        # Cahier de textes
        path('cahiers_texte/', dashboard_views.TeacherCahiersTexteView.as_view(), name='teacher_cahiers_texte'),

        # Rapports
        path('reports/', dashboard_views.TeacherReportsView.as_view(), name='teacher_reports'),
    ])),

    # ================================
    # ROUTES APPRENANT (ÉTUDIANT)
    # ================================
    path('student/', include([
        path('', dashboard_views.StudentDashboardView.as_view(), name='student'),

        # Mes Cours
        path('courses/', dashboard_views.StudentCoursesView.as_view(), name='student_courses'),

        # Emploi du temps
        path('emplois_du_temps/', dashboard_views.StudentEmploiDuTempsView.as_view(),
             name='student_emplois_du_temps'),

        # Évaluations
        path('evaluations/', dashboard_views.StudentEvaluationsView.as_view(), name='student_evaluations'),

        # Résultats et notes
        path('results/', dashboard_views.StudentResultatsView.as_view(), name='student_resultats'),

        # Présences
        path('presences/', dashboard_views.StudentPresencesView.as_view(), name='student_presences'),

        # Candidatures
        path('candidatures/', dashboard_views.StudentCandidaturesView.as_view(), name='student_candidatures'),

        # Inscriptions
        path('inscriptions/', dashboard_views.StudentInscriptionsView.as_view(), name='student_inscriptions'),

        # Paiements
        path('paiements/', dashboard_views.StudentPaiementsView.as_view(), name='student_paiements'),

        # Ressources
        path('ressources/', dashboard_views.StudentRessourcesView.as_view(), name='student_ressources'),

        # Documents
        path('documents/', dashboard_views.StudentDocumentsView.as_view(), name='student_documents'),
    ])),

    # API endpoints pour AJAX
    path('api/', include([
        path('notifications/mark-read/', dashboard_views.mark_notifications_read,
             name='api_mark_notifications_read'),
        path('statistics/<str:type>/', dashboard_views.api_get_statistics, name='api_get_statistics'),
        path('chart-data/<str:chart_type>/', dashboard_views.api_get_chart_data, name='api_get_chart_data'),
    ])),
]
