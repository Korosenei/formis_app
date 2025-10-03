from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomAuthToken, UtilisateurViewSet, ProfilUtilisateurViewSet,
    ProfilApprenantViewSet, ProfilEnseignantViewSet
)

router = DefaultRouter()
router.register(r'users', UtilisateurViewSet)
router.register(r'profiles', ProfilUtilisateurViewSet, basename='profile')
router.register(r'student-profiles', ProfilApprenantViewSet, basename='student-profile')
router.register(r'teacher-profiles', ProfilEnseignantViewSet, basename='teacher-profile')

urlpatterns = [
    path('auth/login/', CustomAuthToken.as_view(), name='api_login'),
    path('', include(router.urls)),
]
