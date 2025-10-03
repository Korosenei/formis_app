# apps/accounts/urls.py
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentification
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/<str:token>/', views.ResetPasswordView.as_view(), name='reset_password'),

    # Profil personnel
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.EditProfileView.as_view(), name='edit_profile'),

    # === GESTION DES UTILISATEURS (Admin/Chef de département) ===
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/add/', views.UserCreateView.as_view(), name='user_add'),
    path('users/<uuid:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    path('users/<uuid:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('users/<uuid:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/<uuid:pk>/toggle-status/', views.toggle_user_status, name='user_toggle_status'),
    path('users/<uuid:pk>/reset-password/', views.admin_reset_password, name='user_reset_password'),
    path('users/export/', views.users_export, name='users_export'),

    # === GESTION DES ENSEIGNANTS ===
    path('teachers/', views.TeacherListView.as_view(), name='teacher_list'),
    path('teachers/add/', views.TeacherCreateView.as_view(), name='teacher_add'),
    path('teachers/<uuid:pk>/', views.TeacherDetailView.as_view(), name='teacher_detail'),
    path('teachers/<uuid:pk>/edit/', views.TeacherUpdateView.as_view(), name='teacher_edit'),
    path('teachers/<uuid:pk>/delete/', views.TeacherDeleteView.as_view(), name='teacher_delete'),
    path('teachers/<uuid:pk>/toggle-status/', views.toggle_teacher_status, name='teacher_toggle_status'),
    path('teachers/export/', views.export_teachers, name='teachers_export'),

    # === GESTION DES ÉTUDIANTS ===
    path('students/', views.StudentListView.as_view(), name='student_list'),
    path('students/add/', views.StudentCreateView.as_view(), name='student_add'),
    path('students/<uuid:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('students/<uuid:pk>/edit/', views.StudentUpdateView.as_view(), name='student_edit'),
    path('students/<uuid:pk>/delete/', views.StudentDeleteView.as_view(), name='student_delete'),
    path('students/<uuid:pk>/toggle-status/', views.toggle_student_status, name='student_toggle_status'),
    path('students/export/', views.export_students, name='students_export'),

    # API endpoints
    path('api/check-email/', views.check_email_availability, name='check_email'),
    path('api/generate-password/', views.generate_password_api, name='generate_password'),
]