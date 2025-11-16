# apps/accounts/urls.py
from django.urls import path
from . import views
from . import exports

app_name = 'accounts'

urlpatterns = [
    # Authentification
    path('', views.LoginView.as_view(), name='login'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/<str:token>/', views.ResetPasswordView.as_view(), name='reset_password'),

    # Profil personnel
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.EditProfileView.as_view(), name='edit_profile'),
    path('profile/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('upload-profile-photo/', views.upload_profile_photo, name='upload_profile_photo'),

    # === GESTION DES UTILISATEURS (Admin/Chef de département) ===
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/add/', views.UserCreateView.as_view(), name='user_add'),
    path('users/<uuid:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    path('users/<uuid:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('users/<uuid:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/<uuid:pk>/toggle-status/', views.toggle_user_status, name='user_toggle_status'),
    path('users/<uuid:pk>/reset-password/', views.admin_reset_password, name='user_reset_password'),
    path('users/export/csv/', exports.users_export_csv, name='users_export_csv'),
    path('users/export/pdf/', exports.users_export_pdf, name='users_export_pdf'),

    # === GESTION DES COMPTABLES ===
    path('comptables/', views.ComptableListView.as_view(), name='comptable_list'),
    path('comptables/add/', views.ComptableCreateView.as_view(), name='comptable_add'),
    path('comptables/<uuid:pk>/', views.ComptableDetailView.as_view(), name='comptable_detail'),
    path('comptables/<uuid:pk>/edit/', views.ComptableUpdateView.as_view(), name='comptable_edit'),
    # path('comptables/<uuid:pk>/delete/', views.ComptableDeleteView.as_view(), name='comptable_delete'),
    # path('comptables/<uuid:pk>/toggle-status/', views.toggle_comptable_status, name='comptable_toggle_status'),
    path('comptables/export/csv/', exports.comptables_export_csv, name='comptables_export_csv'),
    path('comptables/export/pdf/', exports.comptables_export_pdf, name='comptables_export_pdf'),

    # === GESTION DES CHEFS DE DÉPARTEMENT ===
    path('department-heads/', views.DepartmentHeadListView.as_view(), name='department_heads_list'),
    path('department-heads/nominate/', views.NommerChefDepartementView.as_view(), name='nominate_department_head'),
    path('department-heads/<uuid:pk>/revoke/', views.revoquer_chef_departement, name='revoke_department_head'),
    path('department-heads/export/csv/', exports.department_heads_export_csv, name='department_heads_export_csv'),
    path('department-heads/export/pdf/', exports.department_heads_export_pdf, name='department_heads_export_pdf'),

    # === GESTION DES ENSEIGNANTS ===
    path('teachers/', views.TeacherListView.as_view(), name='teacher_list'),
    path('teachers/add/', views.TeacherCreateView.as_view(), name='teacher_add'),
    path('teachers/<uuid:pk>/', views.TeacherDetailView.as_view(), name='teacher_detail'),
    path('teachers/<uuid:pk>/edit/', views.TeacherUpdateView.as_view(), name='teacher_edit'),
    path('teachers/<uuid:pk>/delete/', views.TeacherDeleteView.as_view(), name='teacher_delete'),
    path('teachers/<uuid:pk>/toggle-status/', views.toggle_teacher_status, name='teacher_toggle_status'),
    path('teachers/export/csv/', exports.teachers_export_csv, name='teachers_export_csv'),
    path('teachers/export/pdf/', exports.teachers_export_pdf, name='teachers_export_pdf'),

    # === GESTION DES ÉTUDIANTS ===
    path('students/', views.StudentListView.as_view(), name='student_list'),
    path('students/add/', views.StudentCreateView.as_view(), name='student_add'),
    path('students/<uuid:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('students/<uuid:pk>/edit/', views.StudentUpdateView.as_view(), name='student_edit'),
    path('students/<uuid:pk>/delete/', views.StudentDeleteView.as_view(), name='student_delete'),
    path('students/<uuid:pk>/toggle-status/', views.toggle_student_status, name='student_toggle_status'),
    path('students/export/csv/', exports.students_export_csv, name='students_export_csv'),
    path('students/export/pdf/', exports.students_export_pdf, name='students_export_pdf'),

    # API endpoints
    path('api/check-email/', views.check_email_availability, name='check_email'),
    path('api/generate-password/', views.generate_password_api, name='generate_password'),
]