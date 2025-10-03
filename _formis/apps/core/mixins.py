from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy


class RoleRequiredMixin(LoginRequiredMixin):
    """Mixin pour vérifier les rôles d'utilisateur"""
    required_roles = []
    redirect_field_name = 'next'
    login_url = reverse_lazy('accounts:login')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if not request.user.est_actif:
            messages.error(request, "Votre compte est désactivé. Contactez l'administration.")
            return redirect('accounts:login')
        
        if self.required_roles and request.user.role not in self.required_roles:
            messages.error(request, "Vous n'avez pas les permissions nécessaires pour accéder à cette page.")
            return redirect(request.user.get_dashboard_url())
        
        return super().dispatch(request, *args, **kwargs)


class SuperAdminRequiredMixin(RoleRequiredMixin):
    """Mixin pour les super administrateurs"""
    required_roles = ['SUPERADMIN']


class AdminRequiredMixin(RoleRequiredMixin):
    """Mixin pour les administrateurs d'établissement"""
    required_roles = ['SUPERADMIN', 'ADMIN']


class ChefDepartementRequiredMixin(RoleRequiredMixin):
    """Mixin pour les chefs de département"""
    required_roles = ['SUPERADMIN', 'ADMIN', 'CHEF_DEPARTEMENT']


class EnseignantRequiredMixin(RoleRequiredMixin):
    """Mixin pour les enseignants"""
    required_roles = ['SUPERADMIN', 'ADMIN', 'CHEF_DEPARTEMENT', 'ENSEIGNANT']


class ApprenantRequiredMixin(RoleRequiredMixin):
    """Mixin pour les apprenants"""
    required_roles = ['APPRENANT']


class EstablishmentFilterMixin:
    """Mixin pour filtrer par établissement"""

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.request.user.role == 'SUPERADMIN':
            return queryset

        if self.request.user.role == 'ADMIN':
            return queryset.filter(establishment=self.request.user.establishment)

        elif self.request.user.role == 'DEPARTMENT_HEAD':
            return queryset.filter(
                establishment=self.request.user.establishment,
                department=self.request.user.department
            )

        return queryset.none()


class AuditMixin:
    """Mixin pour l'audit des modifications"""

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class StaffRequiredMixin(RoleRequiredMixin):
    """Mixin pour le personnel (tous sauf apprenant)"""
    required_roles = ['SUPERADMIN', 'ADMIN', 'CHEF_DEPARTEMENT', 'ENSEIGNANT']


class SameUserOrStaffMixin(LoginRequiredMixin):
    """Mixin pour accéder à ses propres données ou être staff"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Vérifier si l'utilisateur peut accéder à cette ressource
        if hasattr(self, 'get_object'):
            obj = self.get_object()
            if hasattr(obj, 'utilisateur'):
                # Si l'objet a un champ utilisateur
                if obj.utilisateur != request.user and not request.user.role in ['SUPERADMIN', 'ADMIN']:
                    messages.error(request, "Vous ne pouvez accéder qu'à vos propres données.")
                    return redirect(request.user.get_dashboard_url())
            elif hasattr(obj, 'user'):
                # Si l'objet a un champ user
                if obj.user != request.user and not request.user.role in ['SUPERADMIN', 'ADMIN']:
                    messages.error(request, "Vous ne pouvez accéder qu'à vos propres données.")
                    return redirect(request.user.get_dashboard_url())
            elif obj != request.user and not request.user.role in ['SUPERADMIN', 'ADMIN']:
                # Si l'objet est l'utilisateur lui-même
                messages.error(request, "Vous ne pouvez accéder qu'à vos propres données.")
                return redirect(request.user.get_dashboard_url())
        
        return super().dispatch(request, *args, **kwargs)


class EstablishmentAccessMixin(RoleRequiredMixin):
    """Mixin pour vérifier l'accès à un établissement"""
    
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(response, 'status_code'):
            return response
        
        # Si super admin, accès total
        if request.user.role == 'SUPERADMIN':
            return super().dispatch(request, *args, **kwargs)
        
        # Vérifier l'accès à l'établissement
        if hasattr(self, 'get_object'):
            obj = self.get_object()
            if hasattr(obj, 'etablissement') and obj.etablissement != request.user.etablissement:
                messages.error(request, "Vous n'avez pas accès à cet établissement.")
                return redirect(request.user.get_dashboard_url())
        
        return super().dispatch(request, *args, **kwargs)


# Décorateurs pour les vues fonctionnelles
from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


def role_required(roles):
    """Décorateur pour vérifier les rôles"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            if not request.user.est_actif:
                messages.error(request, "Votre compte est désactivé.")
                return redirect('accounts:login')
            
            if request.user.role not in roles:
                messages.error(request, "Vous n'avez pas les permissions nécessaires.")
                return redirect(request.user.get_dashboard_url())
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def superadmin_required(view_func):
    """Décorateur pour super admin uniquement"""
    return role_required(['SUPERADMIN'])(view_func)


def admin_required(view_func):
    """Décorateur pour admin et super admin"""
    return role_required(['SUPERADMIN', 'ADMIN'])(view_func)


def staff_required(view_func):
    """Décorateur pour le personnel"""
    return role_required(['SUPERADMIN', 'ADMIN', 'CHEF_DEPARTEMENT', 'ENSEIGNANT'])(view_func)