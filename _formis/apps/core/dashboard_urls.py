# apps/core/dashboard_urls.py
from django.urls import path, include
from . import dashboard_views

app_name = 'dashboard'

urlpatterns = [
    # Redirection selon le rôle
    path('', dashboard_views.DashboardRedirectView.as_view(), name='redirect'),

    # ================================
    # ROUTES SUPERADMIN
    # ================================
    # path('superadmin/', include([
    #     path('', dashboard_views.SuperAdminDashboardView.as_view(), name='superadmin'),
    #     path('establishments/', dashboard_views.SuperAdminEstablishmentsView.as_view(), name='superadmin_establishments'),
    #     path('users/', dashboard_views.SuperAdminUsersView.as_view(), name='superadmin_users'),
    #     path('system/', dashboard_views.SuperAdminSystemView.as_view(), name='superadmin_system'),
    #     path('analytics/', dashboard_views.SuperAdminAnalyticsView.as_view(), name='superadmin_analytics'),
    # ])),

    # ================================
    # ROUTES ADMIN ÉTABLISSEMENT
    # ================================
    path('admin/', include([
        path('', dashboard_views.AdminDashboardView.as_view(), name='admin'),
        path('periodes/', dashboard_views.AdminPeriodesView.as_view(), name='admin_periodes'),
        path('users/', include([
            path('', dashboard_views.AdminUsersView.as_view(), name='admin_users'),
            # path('create/', dashboard_views.AdminUserCreateView.as_view(), name='admin_user_create'),
            # path('<uuid:pk>/', dashboard_views.AdminUserDetailView.as_view(), name='admin_user_detail'),
            # path('<uuid:pk>/edit/', dashboard_views.AdminUserEditView.as_view(), name='admin_user_edit'),
            path('<uuid:pk>/toggle-status/', dashboard_views.admin_toggle_user_status, name='admin_user_toggle_status'),
            path('<uuid:pk>/reset-password/', dashboard_views.admin_reset_user_password,
                 name='admin_user_reset_password'),
            path('export/', dashboard_views.admin_export_users, name='admin_users_export'),
        ])),
        path('students/', dashboard_views.AdminStudentsView.as_view(), name='admin_students'),
        path('teachers/', dashboard_views.AdminTeachersView.as_view(), name='admin_teachers'),
        path('candidatures/', dashboard_views.AdminCandidaturesView.as_view(), name='admin_candidatures'),
        path('inscriptions/', dashboard_views.AdminInscriptionsView.as_view(), name='admin_inscriptions'),
        path('paiements/', include([
            path('', dashboard_views.AdminPaiementsView.as_view(), name='admin_paiements'),
            # path('<uuid:pk>/', dashboard_views.AdminPaymentDetailView.as_view(), name='admin_payment_detail'),
            path('<uuid:pk>/validate/', dashboard_views.admin_validate_payment, name='admin_payment_validate'),
            path('<uuid:pk>/reject/', dashboard_views.admin_reject_payment, name='admin_payment_reject'),
            # path('<uuid:pk>/refund/', dashboard_views.admin_refund_payment, name='admin_payment_refund'),
            # path('<uuid:pk>/receipt/print/', dashboard_views.admin_print_receipt, name='admin_payment_receipt_print'),
            # path('<uuid:pk>/receipt/send/', dashboard_views.admin_send_receipt, name='admin_payment_receipt_send'),
            # path('bulk-validate/', dashboard_views.admin_bulk_validate_payments, name='admin_payments_bulk_validate'),
            # path('bulk-reject/', dashboard_views.admin_bulk_reject_payments, name='admin_payments_bulk_reject'),
            # path('reports/', dashboard_views.AdminPaymentReportsView.as_view(), name='admin_payment_reports'),
            # path('export/', dashboard_views.admin_export_payments, name='admin_payments_export'),
        ])),
        path('departments/', dashboard_views.AdminDepartementsView.as_view(), name='admin_departments'),
        path('filieres/', dashboard_views.AdminFilieresView.as_view(), name='admin_filieres'),
        path('niveaux/', dashboard_views.AdminNiveauxView.as_view(), name='admin_niveaux'),
        path('classes/', dashboard_views.AdminClassesView.as_view(), name='admin_classes'),
        path('modules/', dashboard_views.AdminModulesView.as_view(), name='admin_modules'),
        path('matieres/', dashboard_views.AdminMatieresView.as_view(), name='admin_matieres'),
        path('courses/', dashboard_views.AdminCoursesView.as_view(), name='admin_courses'),
        path('evaluations/', dashboard_views.AdminEvaluationsView.as_view(), name='admin_evaluations'),
        path('programmes/', dashboard_views.AdminProgrammesView.as_view(), name='admin_programmes'),
        path('salles/', dashboard_views.admin_salles, name='admin_salles'),
        path('reports/', dashboard_views.AdminReportsView.as_view(), name='admin_reports'),
        path('settings/', dashboard_views.AdminSettingsView.as_view(), name='admin_settings'),

        # Documents et génération
        # path('documents/', include([
        #     path('', dashboard_views.AdminDocumentsView.as_view(), name='admin_documents'),
        #     path('generate/', dashboard_views.AdminGenerateDocumentsView.as_view(), name='admin_generate_documents'),
        #     path('templates/', dashboard_views.AdminDocumentTemplatesView.as_view(), name='admin_document_templates'),
        # ])),
    ])),

    # ================================
    # ROUTES CHEF DE DÉPARTEMENT
    # ================================
    path('department-head/', include([
        path('', dashboard_views.DepartmentHeadDashboardView.as_view(), name='department_head'),
        path('teachers/', dashboard_views.DepartmentHeadTeachersView.as_view(), name='department_head_teachers'),
        path('students/', dashboard_views.DepartmentHeadStudentsView.as_view(), name='department_head_students'),
        path('candidatures/', dashboard_views.DepartmentHeadCandidaturesView.as_view(), name='department_head_candidatures'),
        path('payments/', include([
            # path('', dashboard_views.DepartmentHeadPaymentsView.as_view(), name='department_head_payments'),
            path('<uuid:pk>/validate/', dashboard_views.admin_validate_payment, name='department_head_payment_validate'),
            path('<uuid:pk>/reject/', dashboard_views.admin_reject_payment, name='department_head_payment_reject'),
        ])),
        path('filieres/', dashboard_views.DepartmentHeadFilieresView.as_view(), name='department_head_filieres'),
        # path('niveaux/', dashboard_views.DepartmentHeadNiveauxView.as_view(), name='department_head_niveaux'),
        path('classes/', dashboard_views.DepartmentHeadClassesView.as_view(), name='department_head_classes'),
        path('modules/', dashboard_views.DepartmentHeadModulesView.as_view(), name='department_head_modules'),
        # path('matieres/', dashboard_views.DepartmentHeadMatieresView.as_view(), name='department_head_matieres'),
        path('courses/', dashboard_views.DepartmentHeadCoursesView.as_view(), name='department_head_courses'),
        path('evaluations/', dashboard_views.DepartmentHeadEvaluationsView.as_view(), name='department_head_evaluations'),
        # path('programmes/', dashboard_views.DepartmentHeadProgrammesView.as_view(), name='department_head_programmes'),
        path('reports/', dashboard_views.DepartmentHeadReportsView.as_view(), name='department_head_reports'),

    ])),

    # ================================
    # ROUTES ENSEIGNANT
    # ================================
    path('teacher/', include([
        path('', dashboard_views.TeacherDashboardView.as_view(), name='teacher'),

        # Mes cours
        path('courses/', include([
            path('', dashboard_views.TeacherCoursesView.as_view(), name='teacher_courses'),
            # path('<int:pk>/', dashboard_views.TeacherCourseDetailView.as_view(), name='teacher_course_detail'),
            # path('<int:pk>/students/', dashboard_views.TeacherCourseStudentsView.as_view(), name='teacher_course_students'),
            # path('<int:pk>/resources/', dashboard_views.TeacherCourseResourcesView.as_view(), name='teacher_course_resources'),
        ])),

        # Mes étudiants
        path('students/', include([
            path('', dashboard_views.TeacherStudentsView.as_view(), name='teacher_students'),
            # path('<uuid:pk>/', dashboard_views.TeacherStudentDetailView.as_view(), name='teacher_student_detail'),
            # path('<uuid:pk>/grades/', dashboard_views.TeacherStudentGradesView.as_view(), name='teacher_student_grades'),
        ])),

        # Évaluations
        path('evaluations/', include([
            path('', dashboard_views.TeacherEvaluationsView.as_view(), name='teacher_evaluations'),
            # path('create/', dashboard_views.TeacherEvaluationCreateView.as_view(), name='teacher_evaluation_create'),
            # path('<uuid:pk>/', dashboard_views.TeacherEvaluationDetailView.as_view(), name='teacher_evaluation_detail'),
            # path('<uuid:pk>/edit/', dashboard_views.TeacherEvaluationEditView.as_view(), name='teacher_evaluation_edit'),
            path('<uuid:pk>/grades/', dashboard_views.TeacherGradeEvaluationView.as_view(), name='teacher_grade_evaluation'),
            # path('<uuid:pk>/results/', dashboard_views.TeacherEvaluationResultsView.as_view(), name='teacher_evaluation_results'),
        ])),

        # Présences
        path('attendance/', include([
            path('', dashboard_views.TeacherAttendanceView.as_view(), name='teacher_attendance'),
            # path('take/', dashboard_views.TeacherTakeAttendanceView.as_view(), name='teacher_take_attendance'),
            # path('reports/', dashboard_views.TeacherAttendanceReportsView.as_view(), name='teacher_attendance_reports'),
        ])),

        # Emploi du temps
        path('schedule/', include([
            path('', dashboard_views.TeacherScheduleView.as_view(), name='teacher_schedule'),
            # path('week/<int:year>/<int:week>/', dashboard_views.TeacherWeeklyScheduleView.as_view(), name='teacher_weekly_schedule'),
        ])),

        # Ressources pédagogiques
        path('resources/', include([
            path('', dashboard_views.TeacherResourcesView.as_view(), name='teacher_resources'),
            # path('upload/', dashboard_views.TeacherUploadResourceView.as_view(), name='teacher_upload_resource'),
            # path('<int:pk>/edit/', dashboard_views.TeacherEditResourceView.as_view(), name='teacher_edit_resource'),
            # path('<int:pk>/delete/', dashboard_views.teacher_delete_resource, name='teacher_delete_resource'),
        ])),

        # Cahier de textes
        path('logbook/', include([
            path('', dashboard_views.TeacherLogbookView.as_view(), name='teacher_logbook'),
            # path('add-entry/', dashboard_views.TeacherAddLogbookEntryView.as_view(), name='teacher_add_logbook_entry'),
            # path('<int:pk>/edit-entry/', dashboard_views.TeacherEditLogbookEntryView.as_view(), name='teacher_edit_logbook_entry'),
        ])),

        # Rapports enseignant
        path('reports/', include([
            path('', dashboard_views.TeacherReportsView.as_view(), name='teacher_reports'),
            # path('student-progress/', dashboard_views.TeacherStudentProgressReportsView.as_view(), name='teacher_student_progress_reports'),
            # path('course-performance/', dashboard_views.TeacherCoursePerformanceReportsView.as_view(), name='teacher_course_performance_reports'),
        ])),
    ])),

    # ================================
    # ROUTES APPRENANT (ÉTUDIANT)
    # ================================
    path('student/', include([
        path('', dashboard_views.StudentDashboardView.as_view(), name='student'),

        # Mes Cours
        path('courses/', include([
            path('', dashboard_views.StudentCoursesView.as_view(), name='student_courses'),
            # path('<int:pk>/', dashboard_views.StudentCourseDetailView.as_view(), name='student_course_detail'),
            # path('<int:pk>/resources/', dashboard_views.StudentCourseResourcesView.as_view(), name='student_course_resources'),
            # path('<int:pk>/progress/', dashboard_views.StudentCourseProgressView.as_view(), name='student_course_progress'),
        ])),

        # Emploi du temps
        path('schedule/', include([
            path('', dashboard_views.StudentScheduleView.as_view(), name='student_schedule'),
            # path('week/<int:year>/<int:week>/', dashboard_views.StudentWeeklyScheduleView.as_view(), name='student_weekly_schedule'),
            # path('export/', dashboard_views.student_export_schedule, name='student_export_schedule'),
        ])),

        # Évaluations
        path('evaluations/', include([
            path('', dashboard_views.StudentEvaluationsView.as_view(), name='student_evaluations'),
            # path('<int:pk>/', dashboard_views.StudentEvaluationDetailView.as_view(), name='student_evaluation_detail'),
            # path('<int:pk>/submit/', dashboard_views.StudentSubmitEvaluationView.as_view(), name='student_submit_evaluation'),
            # path('calendar/', dashboard_views.StudentEvaluationsCalendarView.as_view(), name='student_evaluations_calendar'),
            # path('upcoming/', dashboard_views.StudentUpcomingEvaluationsView.as_view(), name='student_upcoming_evaluations'),
        ])),

        # Résultats et notes
        path('results/', include([
            path('', dashboard_views.StudentResultsView.as_view(), name='student_resultats'),
            # path('semester/<int:semester_id>/', dashboard_views.StudentSemesterResultsView.as_view(), name='student_semester_results'),
            # path('annual/', dashboard_views.StudentAnnualResultsView.as_view(), name='student_annual_results'),
            # path('transcript/', dashboard_views.StudentTranscriptView.as_view(), name='student_transcript'),
        ])),

        # Présences
        path('attendances/', include([
            path('', dashboard_views.StudentAttendanceView.as_view(), name='student_attendances'),
            # path('course/<int:course_id>/', dashboard_views.StudentCourseAttendanceView.as_view(), name='student_course_attendance'),
            # path('reports/', dashboard_views.StudentAttendanceReportsView.as_view(), name='student_attendance_reports'),
        ])),

        # Paiements
        path('payments/', include([
            path('', dashboard_views.StudentPaymentsView.as_view(), name='student_paiements'),
            # path('<uuid:pk>/', dashboard_views.StudentPaymentDetailView.as_view(), name='student_payment_detail'),
            # path('make-payment/', dashboard_views.StudentMakePaymentView.as_view(), name='student_make_payment'),
            # path('history/', dashboard_views.StudentPaymentHistoryView.as_view(), name='student_payment_history'),
            # path('receipts/', dashboard_views.StudentPaymentReceiptsView.as_view(), name='student_payment_receipts'),
        ])),

        # Ressources
        path('resources/', include([
            path('', dashboard_views.StudentResourcesView.as_view(), name='student_resources'),
            # path('course/<int:course_id>/', dashboard_views.StudentCourseResourcesView.as_view(), name='student_course_resources_detail'),
            # path('download/<int:resource_id>/', dashboard_views.student_download_resource, name='student_download_resource'),
        ])),

        # Documents académiques
        path('documents/', include([
            path('', dashboard_views.StudentDocumentsView.as_view(), name='student_documents'),
            # path('certificates/', dashboard_views.StudentCertificatesView.as_view(), name='student_certificates'),
            # path('transcripts/', dashboard_views.StudentTranscriptsView.as_view(), name='student_transcripts'),
            # path('request/', dashboard_views.StudentDocumentRequestView.as_view(), name='student_document_request'),
        ])),

        # Profil et paramètres
        path('profile/', include([
            path('', dashboard_views.StudentProfileView.as_view(), name='student_profil'),
            # path('edit/', dashboard_views.StudentEditProfileView.as_view(), name='student_edit_profile'),
            # path('change-password/', dashboard_views.StudentChangePasswordView.as_view(), name='student_change_password'),
            # path('notifications/', dashboard_views.StudentNotificationSettingsView.as_view(), name='student_notification_settings'),
        ])),

        # Candidature et inscription
        # path('candidatures/', include([
        #     path('status/', dashboard_views.StudentCandidatureStatusView.as_view(), name='student_candidature_status'),
        #     path('documents/', dashboard_views.StudentCandidatureDocumentsView.as_view(), name='student_candidature_documents'),
        #     path('history/', dashboard_views.StudentCandidatureHistoryView.as_view(), name='student_candidature_history'),
        # ])),
    ])),

    # ================================
    # ROUTES COMMUNES
    # ================================
    path('profile/', dashboard_views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', dashboard_views.EditProfileView.as_view(), name='edit_profile'),
    path('profile/change-password/', dashboard_views.ChangePasswordView.as_view(), name='change_password'),
    path('upload-profile-photo/', dashboard_views.upload_profile_photo, name='upload_profile_photo'),

    # path('change-password/', dashboard_views.ChangePasswordView.as_view(), name='change_password'),
    # path('notifications/', dashboard_views.NotificationsView.as_view(), name='notifications'),
    # path('messages/', dashboard_views.MessagesView.as_view(), name='messages'),

    # API endpoints pour AJAX
    path('api/', include([
        path('notifications/mark-read/', dashboard_views.mark_notifications_read, name='api_mark_notifications_read'),
        # path('search/users/', dashboard_views.api_search_users, name='api_search_users'),
        path('statistics/<str:type>/', dashboard_views.api_get_statistics, name='api_get_statistics'),
        path('chart-data/<str:chart_type>/', dashboard_views.api_get_chart_data, name='api_get_chart_data'),
    ])),
]

