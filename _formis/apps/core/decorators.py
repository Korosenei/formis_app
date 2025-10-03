from django.shortcuts import get_object_or_404
from django.http import Http404, HttpResponseForbidden
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.utils.decorators import method_decorator
from functools import wraps

from apps.establishments.models import AnneeAcademique
from apps.evaluations.models import Evaluation, Composition, FichierComposition


def role_required(roles):
    """
    Décorateur pour vérifier que l'utilisateur a un des rôles requis.
    roles peut être une liste ou un seul rôle.
    """
    if isinstance(roles, str):
        roles = [roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Authentification requise")

            if not hasattr(request.user, 'role'):
                return HttpResponseForbidden("Rôle utilisateur non défini")

            if request.user.role not in roles:
                messages.error(
                    request,
                    "Vous n'avez pas les permissions nécessaires pour accéder à cette page."
                )
                return HttpResponseForbidden("Permission refusée")

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def enseignant_owns_evaluation(view_func):
    """
    Décorateur pour vérifier que l'enseignant est propriétaire de l'évaluation.
    """

    @wraps(view_func)
    def _wrapped_view(request, pk=None, *args, **kwargs):
        # Récupérer l'ID de l'évaluation depuis les paramètres
        evaluation_id = pk or kwargs.get('pk')

        if not evaluation_id:
            raise Http404("Évaluation non spécifiée")

        evaluation = get_object_or_404(Evaluation, pk=evaluation_id)

        # Vérifier que l'utilisateur est l'enseignant propriétaire
        if evaluation.enseignant != request.user:
            messages.error(
                request,
                "Vous n'êtes pas autorisé à accéder à cette évaluation."
            )
            return HttpResponseForbidden("Accès refusé")

        # Ajouter l'évaluation au contexte de la requête pour éviter une double requête
        request.evaluation = evaluation
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def apprenant_in_evaluation_classes(view_func):
    """
    Décorateur pour vérifier que l'apprenant appartient aux classes de l'évaluation.
    """

    @wraps(view_func)
    def _wrapped_view(request, pk=None, *args, **kwargs):
        # Récupérer l'ID de l'évaluation depuis les paramètres
        evaluation_id = pk or kwargs.get('pk')

        if not evaluation_id:
            raise Http404("Évaluation non spécifiée")

        evaluation = get_object_or_404(Evaluation, pk=evaluation_id)

        # Vérifier que l'apprenant a une classe
        if not hasattr(request.user, 'classe') or not request.user.classe:
            messages.error(
                request,
                "Vous n'êtes assigné à aucune classe."
            )
            return HttpResponseForbidden("Classe non définie")

        # Vérifier que la classe de l'apprenant fait partie des classes de l'évaluation
        if request.user.classe not in evaluation.classes.all():
            messages.error(
                request,
                "Vous n'êtes pas autorisé à accéder à cette évaluation."
            )
            return HttpResponseForbidden("Classe non autorisée")

        # Ajouter l'évaluation au contexte de la requête
        request.evaluation = evaluation
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def check_evaluation_availability(view_func):
    """
    Décorateur pour vérifier la disponibilité d'une évaluation.
    """

    @wraps(view_func)
    def _wrapped_view(request, pk=None, *args, **kwargs):
        from apps.evaluations.utils import EvaluationUtils

        evaluation_id = pk or kwargs.get('pk')

        if not evaluation_id:
            raise Http404("Évaluation non spécifiée")

        evaluation = get_object_or_404(Evaluation, pk=evaluation_id)

        # Vérifier la disponibilité
        disponibilite = EvaluationUtils.verifier_disponibilite_evaluation(evaluation, request.user)

        if not disponibilite['est_disponible']:
            messages.warning(request, disponibilite['raison'])

            # Rediriger selon le contexte
            if request.user.role == 'APPRENANT':
                return HttpResponseForbidden(disponibilite['raison'])
            else:
                # Pour les enseignants, on autorise l'accès mais avec un avertissement
                pass

        request.evaluation = evaluation
        request.disponibilite = disponibilite
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def composition_can_be_modified(view_func):
    """
    Décorateur pour vérifier qu'une composition peut être modifiée.
    """

    @wraps(view_func)
    def _wrapped_view(request, pk=None, *args, **kwargs):
        evaluation_id = pk or kwargs.get('pk')

        if not evaluation_id:
            raise Http404("Évaluation non spécifiée")

        evaluation = get_object_or_404(Evaluation, pk=evaluation_id)

        # Récupérer ou créer la composition
        composition, created = Composition.objects.get_or_create(
            evaluation=evaluation,
            apprenant=request.user
        )

        # Vérifier si la composition peut être modifiée
        if not composition.peut_soumettre:
            messages.error(
                request,
                "Vous ne pouvez plus modifier cette composition."
            )
            return HttpResponseForbidden("Modification non autorisée")

        request.evaluation = evaluation
        request.composition = composition
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def active_academic_year_required(view_func):
    """
    Décorateur pour vérifier qu'une année académique active existe.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            annee_active = AnneeAcademique.objects.get(active=True)
            request.annee_academique_active = annee_active
        except AnneeAcademique.DoesNotExist:
            messages.error(
                request,
                "Aucune année académique active n'est configurée. "
                "Veuillez contacter l'administrateur."
            )
            return HttpResponseForbidden("Année académique non configurée")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def require_evaluation_file_access(file_type):
    """
    Décorateur générique pour vérifier l'accès aux fichiers d'évaluation.
    file_type: 'evaluation', 'correction', ou 'composition'
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, pk=None, *args, **kwargs):
            # Récupérer l'objet selon le type de fichier
            if file_type in ['evaluation', 'correction']:
                evaluation = get_object_or_404(Evaluation, pk=pk)
                obj = evaluation
            elif file_type == 'composition':
                fichier_composition = get_object_or_404(FichierComposition, pk=pk)
                obj = fichier_composition
            else:
                raise Http404("Type de fichier non supporté")

            # Vérifications selon le type d'utilisateur et le type de fichier
            if request.user.role == 'ENSEIGNANT':
                # Enseignant : accès à tous les fichiers de ses évaluations
                if file_type in ['evaluation', 'correction']:
                    if obj.enseignant != request.user:
                        return HttpResponseForbidden("Accès refusé")
                elif file_type == 'composition':
                    # Vérifier que la composition appartient à une évaluation de l'enseignant
                    compositions = obj.compositions.filter(evaluation__enseignant=request.user)
                    if not compositions.exists():
                        return HttpResponseForbidden("Accès refusé")

            elif request.user.role == 'APPRENANT':
                # Apprenant : accès limité
                if file_type in ['evaluation', 'correction']:
                    # Vérifier que l'apprenant est dans les classes de l'évaluation
                    if request.user.classe not in obj.classes.all():
                        return HttpResponseForbidden("Accès refusé")

                    # Pour la correction, vérifier qu'elle est publiée
                    if file_type == 'correction' and not obj.correction_publiee:
                        return HttpResponseForbidden("Correction non publiée")

                elif file_type == 'composition':
                    # Vérifier que l'apprenant est propriétaire du fichier
                    if obj.uploade_par != request.user:
                        return HttpResponseForbidden("Accès refusé")

            else:
                # Autres rôles non autorisés
                return HttpResponseForbidden("Rôle non autorisé")

            # Stocker l'objet dans la requête pour éviter une double requête
            if file_type in ['evaluation', 'correction']:
                request.evaluation = obj
            elif file_type == 'composition':
                request.fichier_composition = obj

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


# Décorateurs pour les vues basées sur les classes
class RoleRequiredMixin:
    """Mixin pour les vues basées sur les classes avec vérification de rôle"""
    roles_required = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Authentification requise")

        if not hasattr(request.user, 'role'):
            return HttpResponseForbidden("Rôle utilisateur non défini")

        if self.roles_required and request.user.role not in self.roles_required:
            messages.error(
                request,
                "Vous n'avez pas les permissions nécessaires pour accéder à cette page."
            )
            return HttpResponseForbidden("Permission refusée")

        return super().dispatch(request, *args, **kwargs)


class EnseignantOwnsEvaluationMixin:
    """Mixin pour vérifier que l'enseignant est propriétaire de l'évaluation"""

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'role') or request.user.role != 'ENSEIGNANT':
            return HttpResponseForbidden("Rôle enseignant requis")

        # Récupérer l'évaluation depuis la vue
        evaluation = self.get_object()

        if evaluation.enseignant != request.user:
            messages.error(
                request,
                "Vous n'êtes pas autorisé à accéder à cette évaluation."
            )
            return HttpResponseForbidden("Accès refusé")

        return super().dispatch(request, *args, **kwargs)


class ApprenantInEvaluationClassesMixin:
    """Mixin pour vérifier que l'apprenant est dans les classes de l'évaluation"""

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'role') or request.user.role != 'APPRENANT':
            return HttpResponseForbidden("Rôle apprenant requis")

        if not hasattr(request.user, 'classe') or not request.user.classe:
            messages.error(request, "Vous n'êtes assigné à aucune classe.")
            return HttpResponseForbidden("Classe non définie")

        evaluation = self.get_object()

        if request.user.classe not in evaluation.classes.all():
            messages.error(
                request,
                "Vous n'êtes pas autorisé à accéder à cette évaluation."
            )
            return HttpResponseForbidden("Classe non autorisée")

        return super().dispatch(request, *args, **kwargs)


def evaluation_file_access_required(file_type):
    """
    Décorateur alternatif avec un nom plus court pour la compatibilité
    """
    return require_evaluation_file_access(file_type)
