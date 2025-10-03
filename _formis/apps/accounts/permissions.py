from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Permission qui permet seulement au propriétaire de modifier ses données"""

    def has_object_permission(self, request, view, obj):
        # Permissions de lecture pour tous les utilisateurs authentifiés
        if request.method in permissions.SAFE_METHODS:
            return True

        # Permissions d'écriture seulement pour le propriétaire
        return obj == request.user


class IsSuperAdminOrAdmin(permissions.BasePermission):
    """Permission pour les super-admins et admins"""

    def has_permission(self, request, view):
        return (
                request.user.is_authenticated and
                request.user.role in ['SUPERADMIN', 'ADMIN']
        )


class CanManageUser(permissions.BasePermission):
    """Permission basée sur la hiérarchie des rôles"""

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        return request.user.peut_gerer_utilisateur(obj)
