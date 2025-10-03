from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()


class IsSuperAdmin(permissions.BasePermission):
    """Permission pour les super administrateurs"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'SUPERADMIN'


class IsEstablishmentAdmin(permissions.BasePermission):
    """Permission pour les administrateurs d'établissement"""

    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role in ['SUPERADMIN', 'ADMIN'])

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'SUPERADMIN':
            return True

        # L'admin peut seulement gérer son établissement
        if hasattr(obj, 'establishment'):
            return obj.establishment == request.user.establishment

        return False


class IsDepartmentHead(permissions.BasePermission):
    """Permission pour les chefs de département"""

    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role in ['SUPERADMIN', 'ADMIN', 'DEPARTMENT_HEAD'])

    def has_object_permission(self, request, view, obj):
        if request.user.role in ['SUPERADMIN', 'ADMIN']:
            return True

        # Le chef de département peut seulement gérer son département
        if hasattr(obj, 'department'):
            return obj.department == request.user.department

        return False


class IsTeacher(permissions.BasePermission):
    """Permission pour les enseignants"""

    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role in ['SUPERADMIN', 'ADMIN', 'DEPARTMENT_HEAD', 'TEACHER'])


class IsStudent(permissions.BasePermission):
    """Permission pour les étudiants"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'STUDENT'

    def has_object_permission(self, request, view, obj):
        # L'étudiant peut seulement accéder à ses propres données
        if hasattr(obj, 'student'):
            return obj.student == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user

        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Permission pour le propriétaire ou lecture seule"""

    def has_object_permission(self, request, view, obj):
        # Permissions de lecture pour tous
        if request.method in permissions.SAFE_METHODS:
            return True

        # Permissions d'écriture seulement pour le propriétaire
        return obj.created_by == request.user


class CanManageStudents(permissions.BasePermission):
    """Permission pour gérer les étudiants"""

    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role in ['SUPERADMIN', 'ADMIN', 'DEPARTMENT_HEAD', 'TEACHER'])

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'SUPERADMIN':
            return True

        if request.user.role == 'ADMIN':
            # L'admin peut gérer les étudiants de son établissement
            if hasattr(obj, 'establishment'):
                return obj.establishment == request.user.establishment

        elif request.user.role == 'DEPARTMENT_HEAD':
            # Le chef de département peut gérer les étudiants de son département
            if hasattr(obj, 'department'):
                return obj.department == request.user.department

        elif request.user.role == 'TEACHER':
            # L'enseignant peut gérer ses étudiants
            if hasattr(obj, 'assigned_class'):
                # Vérifier si l'enseignant enseigne à cette classe
                return obj.assigned_class.courses.filter(teacher=request.user).exists()

        return False

