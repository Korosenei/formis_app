from rest_framework import permissions


class EnrollmentPermission(permissions.BasePermission):
    """
    Permissions personnalisées pour l'application enrollment
    """

    def has_permission(self, request, view):
        # L'utilisateur doit être authentifié
        if not request.user.is_authenticated:
            return False

        # Les super utilisateurs ont tous les droits
        if request.user.is_superuser:
            return True

        # Vérifier le rôle de l'utilisateur
        user_role = getattr(request.user, 'role', None)

        # Actions en lecture seule
        if request.method in permissions.SAFE_METHODS:
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT', 'ENSEIGNANT', 'APPRENANT']

        # Actions d'écriture
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Seuls les admins et chefs de département peuvent modifier
            if view.__class__.__name__ in ['CandidatureViewSet', 'InscriptionViewSet', 'TransfertViewSet']:
                return user_role in ['ADMIN', 'CHEF_DEPARTMENT']

            # Pour les autres vues, seuls les admins
            return user_role == 'ADMIN'

        return False

    def has_object_permission(self, request, view, obj):
        # Les super utilisateurs ont tous les droits
        if request.user.is_superuser:
            return True

        user_role = getattr(request.user, 'role', None)

        # Lecture seule pour tous les utilisateurs authentifiés avec les bons rôles
        if request.method in permissions.SAFE_METHODS:
            if user_role == 'APPRENANT':
                # Un apprenant ne peut voir que ses propres données
                if hasattr(obj, 'etudiant'):
                    return obj.etudiant == request.user
                elif hasattr(obj, 'candidature') and hasattr(obj.candidature, 'email'):
                    return obj.candidature.email == request.user.email
                return False
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT', 'ENSEIGNANT']

        # Actions d'écriture
        if request.method in ['PUT', 'PATCH', 'DELETE']:
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT']

        return False


class CandidaturePermission(permissions.BasePermission):
    """
    Permissions spécifiques pour les candidatures
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        user_role = getattr(request.user, 'role', None)

        # Actions de lecture
        if request.method in permissions.SAFE_METHODS:
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT', 'ENSEIGNANT']

        # Création de candidature (peut être ouverte aux candidats)
        if request.method == 'POST':
            return True  # Ouvert à tous les utilisateurs authentifiés

        # Modification/suppression
        return user_role in ['ADMIN', 'CHEF_DEPARTMENT']

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        user_role = getattr(request.user, 'role', None)

        # Lecture
        if request.method in permissions.SAFE_METHODS:
            # Un candidat peut voir sa propre candidature
            if hasattr(obj, 'email') and obj.email == request.user.email:
                return True
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT', 'ENSEIGNANT']

        # Modification
        if request.method in ['PUT', 'PATCH']:
            # Un candidat peut modifier sa candidature si elle est en brouillon
            if hasattr(obj, 'email') and obj.email == request.user.email:
                return obj.statut == 'BROUILLON'
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT']

        # Suppression
        return user_role in ['ADMIN', 'CHEF_DEPARTMENT']


class DocumentCandidaturePermission(permissions.BasePermission):
    """
    Permissions spécifiques pour les documents de candidature
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        return True  # Base permission, refined in object permission

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        user_role = getattr(request.user, 'role', None)

        # Lecture
        if request.method in permissions.SAFE_METHODS:
            # Un candidat peut voir ses propres documents
            if obj.candidature.email == request.user.email:
                return True
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT', 'ENSEIGNANT']

        # Ajout/modification de documents
        if request.method in ['POST', 'PUT', 'PATCH']:
            # Un candidat peut ajouter/modifier ses documents si la candidature est en brouillon
            if obj.candidature.email == request.user.email:
                return obj.candidature.statut == 'BROUILLON'
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT']

        # Suppression
        if request.method == 'DELETE':
            # Un candidat peut supprimer ses documents si la candidature est en brouillon
            if obj.candidature.email == request.user.email:
                return obj.candidature.statut == 'BROUILLON'
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT']

        return False


class InscriptionPermission(permissions.BasePermission):
    """
    Permissions spécifiques pour les inscriptions
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        user_role = getattr(request.user, 'role', None)

        # Actions de lecture
        if request.method in permissions.SAFE_METHODS:
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT', 'ENSEIGNANT', 'APPRENANT']

        # Création/modification/suppression
        return user_role in ['ADMIN', 'CHEF_DEPARTMENT']

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        user_role = getattr(request.user, 'role', None)

        # Lecture
        if request.method in permissions.SAFE_METHODS:
            # Un étudiant peut voir sa propre inscription
            if user_role == 'APPRENANT' and obj.etudiant == request.user:
                return True
            return user_role in ['ADMIN', 'CHEF_DEPARTMENT', 'ENSEIGNANT']

        # Modification/suppression
        return user_role in ['ADMIN', 'CHEF_DEPARTMENT']

