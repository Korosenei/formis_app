from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from django.contrib.auth import login, logout
from django.db import transaction
from ..models import Utilisateur, ProfilUtilisateur, ProfilApprenant, ProfilEnseignant
from ..permissions import IsOwnerOrReadOnly, IsSuperAdminOrAdmin, CanManageUser
from .serializers import (
    UtilisateurSerializer, UtilisateurProfileSerializer,
    ProfilUtilisateurSerializer, ProfilApprenantSerializer,
    ProfilEnseignantSerializer, LoginSerializer, ChangePasswordSerializer
)


class CustomAuthToken(ObtainAuthToken):
    """Vue personnalisée pour l'obtention du token d'authentification"""

    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'token': token.key,
            'user_id': user.pk,
            'email': user.email,
            'role': user.role,
            'matricule': user.matricule,
            'full_name': user.get_full_name(),
            'dashboard_url': user.get_dashboard_url()
        })


class UtilisateurViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des utilisateurs"""

    queryset = Utilisateur.objects.all()
    serializer_class = UtilisateurSerializer

    def get_permissions(self):
        if self.action == 'list':
            permission_classes = [permissions.IsAuthenticated, IsSuperAdminOrAdmin]
        elif self.action in ['create', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsSuperAdminOrAdmin]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [permissions.IsAuthenticated, CanManageUser]
        else:
            permission_classes = [permissions.IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in ['retrieve', 'list']:
            return UtilisateurProfileSerializer
        return UtilisateurSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == 'SUPERADMIN':
            return queryset
        elif user.role == 'ADMIN':
            return queryset.filter(etablissement=user.etablissement)
        elif user.role == 'CHEF_DEPARTEMENT':
            return queryset.filter(departement=user.departement)
        else:
            return queryset.filter(id=user.id)

    @action(detail=False, methods=['get', 'put', 'patch'])
    def profile(self, request):
        """Endpoint pour le profil de l'utilisateur connecté"""
        if request.method == 'GET':
            serializer = UtilisateurProfileSerializer(request.user)
            return Response(serializer.data)
        else:
            serializer = UtilisateurSerializer(
                request.user, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Endpoint pour changer le mot de passe"""
        serializer = ChangePasswordSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({'message': 'Mot de passe modifié avec succès.'})

    @action(detail=False, methods=['post'])
    def logout(self, request):
        """Endpoint pour la déconnexion"""
        try:
            request.user.auth_token.delete()
        except:
            pass
        return Response({'message': 'Déconnexion réussie.'})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Endpoint pour activer un utilisateur"""
        user = self.get_object()
        user.est_actif = True
        user.save()
        return Response({'message': 'Utilisateur activé avec succès.'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Endpoint pour désactiver un utilisateur"""
        user = self.get_object()
        user.est_actif = False
        user.save()
        return Response({'message': 'Utilisateur désactivé avec succès.'})


class ProfilUtilisateurViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des profils utilisateurs"""

    serializer_class = ProfilUtilisateurSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return ProfilUtilisateur.objects.filter(utilisateur=self.request.user)

    def perform_create(self, serializer):
        serializer.save(utilisateur=self.request.user)


class ProfilApprenantViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des profils apprenants"""

    serializer_class = ProfilApprenantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPERADMIN', 'ADMIN']:
            return ProfilApprenant.objects.all()
        elif user.role == 'APPRENANT':
            return ProfilApprenant.objects.filter(utilisateur=user)
        return ProfilApprenant.objects.none()


class ProfilEnseignantViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des profils enseignants"""

    serializer_class = ProfilEnseignantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPERADMIN', 'ADMIN']:
            return ProfilEnseignant.objects.all()
        elif user.role == 'ENSEIGNANT':
            return ProfilEnseignant.objects.filter(utilisateur=user)
        return ProfilEnseignant.objects.none()

