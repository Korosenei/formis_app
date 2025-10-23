from functools import wraps
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import Http404
from .models import Evaluation, Composition
from apps.establishments.models import AnneeAcademique


def role_required(roles):
    """Vérifie que l'utilisateur a un des rôles requis"""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')

            if request.user.role not in roles:
                messages.error(request, "Vous n'avez pas les permissions nécessaires")
                return redirect('dashboard:redirect')

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def enseignant_owns_evaluation(view_func):
    """Vérifie que l'enseignant est propriétaire de l'évaluation"""

    @wraps(view_func)
    def wrapper(request, pk, *args, **kwargs):
        evaluation = get_object_or_404(Evaluation, pk=pk)

        if evaluation.enseignant != request.user:
            messages.error(request, "Vous n'êtes pas autorisé à accéder à cette évaluation")
            return redirect('evaluations:list_enseignant')

        return view_func(request, pk, *args, **kwargs)

    return wrapper


def apprenant_in_evaluation_classes(view_func):
    """Vérifie que l'apprenant est dans une des classes de l'évaluation"""

    @wraps(view_func)
    def wrapper(request, pk, *args, **kwargs):
        evaluation = get_object_or_404(Evaluation, pk=pk)

        if not hasattr(request.user, 'profil_apprenant'):
            messages.error(request, "Profil apprenant non trouvé")
            return redirect('dashboard:redirect')

        classe_actuelle = request.user.profil_apprenant.classe_actuelle

        if classe_actuelle not in evaluation.classes.all():
            messages.error(request, "Vous n'avez pas accès à cette évaluation")
            return redirect('evaluations:list_apprenant')

        return view_func(request, pk, *args, **kwargs)

    return wrapper


def check_evaluation_availability(view_func):
    """Vérifie que l'évaluation est disponible pour soumission"""

    @wraps(view_func)
    def wrapper(request, pk, *args, **kwargs):
        evaluation = get_object_or_404(Evaluation, pk=pk)

        if not evaluation.est_active:
            messages.warning(request, "Cette évaluation n'est pas active")
            return redirect('evaluations:detail_apprenant', pk=pk)

        return view_func(request, pk, *args, **kwargs)

    return wrapper


def composition_can_be_modified(view_func):
    """Vérifie que la composition peut encore être modifiée"""

    @wraps(view_func)
    def wrapper(request, pk, *args, **kwargs):
        composition = get_object_or_404(Composition, pk=pk)

        if not composition.peut_soumettre:
            messages.error(request, "Vous ne pouvez plus modifier cette composition")
            return redirect('evaluations:detail_apprenant', pk=composition.evaluation.pk)

        return view_func(request, pk, *args, **kwargs)

    return wrapper


def active_academic_year_required(view_func):
    """Vérifie qu'une année académique est active"""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        try:
            annee_active = AnneeAcademique.objects.get(est_active=True)
        except AnneeAcademique.DoesNotExist:
            messages.error(request, "Aucune année académique active")
            return redirect('dashboard:redirect')

        return view_func(request, *args, **kwargs)

    return wrapper


def require_evaluation_file_access(view_func):
    """Vérifie les droits d'accès aux fichiers d'évaluation"""

    @wraps(view_func)
    def wrapper(request, pk, type_fichier, *args, **kwargs):
        evaluation = get_object_or_404(Evaluation, pk=pk)

        # Enseignant propriétaire
        if request.user.role == 'ENSEIGNANT':
            if evaluation.enseignant != request.user:
                raise Http404

        # Apprenant de la classe
        elif request.user.role == 'APPRENANT':
            if hasattr(request.user, 'profil_apprenant'):
                classe = request.user.profil_apprenant.classe_actuelle
                if classe not in evaluation.classes.all():
                    raise Http404
            else:
                raise Http404

        else:
            raise Http404

        return view_func(request, pk, type_fichier, *args, **kwargs)

    return wrapper