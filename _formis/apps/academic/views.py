#academic/views.py
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Departement, Filiere, Niveau, Classe, PeriodeAcademique, Programme
from .forms import ( DepartementForm, FiliereForm, NiveauForm,ClasseForm, PeriodeAcademiqueForm, ProgrammeForm, DepartementFilterForm, FiliereFilterForm
)


# ============ VUES POUR DEPARTEMENT ============
class DepartementListView(LoginRequiredMixin, ListView):
    model = Departement
    template_name = 'academic/departement/list.html'
    context_object_name = 'departements'
    paginate_by = 20

    def get_queryset(self):
        queryset = Departement.objects.select_related(
            'etablissement', 'chef'
        ).annotate(
            nombre_filieres=Count('filiere')
        )

        # Filtrage
        form = DepartementFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data['etablissement']:
                queryset = queryset.filter(etablissement=form.cleaned_data['etablissement'])

            if form.cleaned_data['est_actif']:
                queryset = queryset.filter(est_actif=form.cleaned_data['est_actif'] == 'True')

            if form.cleaned_data['search']:
                search = form.cleaned_data['search']
                queryset = queryset.filter(
                    Q(nom__icontains=search) |
                    Q(code__icontains=search) |
                    Q(email__icontains=search)
                )

        return queryset.order_by('nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = DepartementFilterForm(self.request.GET)
        context['title'] = 'Départements'
        return context

class DepartementCreateView(LoginRequiredMixin, CreateView):
    model = Departement
    form_class = DepartementForm
    template_name = 'academic/departement/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN']:
            messages.error(request, "Permission non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_departments')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_departments')

    def form_valid(self, form):
        # Lier automatiquement le département à l'établissement de l'utilisateur connecté
        if not self.request.user.etablissement:
            messages.error(self.request, "Impossible de créer le département : aucun établissement associé à votre compte.")
            return redirect('dashboard:redirect')

        form.instance.etablissement = self.request.user.etablissement

        messages.success(self.request, 'Département créé avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nouveau Département'
        context['submit_text'] = 'Créer'
        context['cancel_url'] = self.get_cancel_url()
        return context

class DepartementUpdateView(LoginRequiredMixin, UpdateView):
    model = Departement
    form_class = DepartementForm
    template_name = 'academic/departement/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Permission non autorisé")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_departments')
        else:
            return reverse_lazy('dashboard:department_head_departments')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_departments')
        else:
            return reverse_lazy('dashboard:department_head_departments')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_departments')
        else:
            return redirect('dashboard:department_head_departments')

    def form_valid(self, form):
        messages.success(self.request, 'Département modifié avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier {self.object.nom}'
        context['submit_text'] = 'Modifier'
        context['cancel_url'] = self.get_cancel_url()
        return context

@login_required
@login_required
def departement_detail(request, pk):
    departement = get_object_or_404(
        Departement.objects.select_related('chef', 'etablissement').annotate(
            nombre_filieres=Count('filieres', filter=Q(filieres__est_active=True), distinct=True),
            nombre_enseignants=Count('utilisateurs', filter=Q(utilisateurs__role='ENSEIGNANT', utilisateurs__est_actif=True), distinct=True)
        ),
        pk=pk,
        etablissement=request.user.etablissement
    )

    # Récupération des filières et enseignants sans doublons
    filieres = departement.filieres.filter(est_active=True).distinct()[:5]
    enseignants = departement.utilisateurs.filter(role='ENSEIGNANT', est_actif=True).distinct()[:10]

    cancel_url = reverse_lazy('dashboard:admin_departments') if request.user.role == 'ADMIN' else reverse_lazy('dashboard:department_head_departments')

    context = {
        'departement': departement,
        'filieres': filieres,
        'enseignants': enseignants,
        'title': departement.nom,
        'cancel_url': cancel_url
    }

    return render(request, 'academic/departement/detail.html', context)

@login_required
@require_http_methods(["POST"])
def departement_delete(request, pk):
    # Vérification des permissions
    if request.user.role not in ['ADMIN']:
        messages.error(request, "Permission non autorisée")
        return redirect('dashboard:redirect')

    departement = get_object_or_404(Departement, pk=pk)

    # Vérification que l'admin ne peut supprimer que dans son établissement
    if departement.etablissement != request.user.etablissement:
        messages.error(request, "Permission non autorisée")
        return redirect('dashboard:redirect')

    # Vérifier s'il y a des filières associées
    if departement.filiere_set.exists():
        messages.error(
            request,
            'Impossible de supprimer ce département car il contient des filières.'
        )
    else:
        nom = departement.nom
        departement.delete()
        messages.success(request, f'Département "{nom}" supprimé avec succès.')

    # Redirection après suppression
    if request.user.role == 'ADMIN':
        return redirect('dashboard:admin_departments')

@login_required
@require_http_methods(["POST"])
def departement_toggle_status(request, pk):
    """Active/désactive un département"""
    if request.user.role != 'ADMIN':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    departement = get_object_or_404(Departement, pk=pk, etablissement=request.user.etablissement)
    departement.est_actif = not departement.est_actif
    departement.save()

    return JsonResponse({
        'success': True,
        'est_actif': departement.est_actif,
        'message': f'Département {"activé" if departement.est_actif else "désactivé"} avec succès'
    })


# ============ VUES POUR FILIERE ============
class FiliereListView(LoginRequiredMixin, ListView):
    model = Filiere
    template_name = 'academic/filiere/list.html'
    context_object_name = 'filieres'
    paginate_by = 20

    def get_queryset(self):
        queryset = Filiere.objects.select_related(
            'etablissement', 'departement'
        ).annotate(
            nombre_niveaux=Count('niveaux'),
            nombre_classes=Count('niveaux__classe')
        )

        # Filtrage
        form = FiliereFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data['etablissement']:
                queryset = queryset.filter(etablissement=form.cleaned_data['etablissement'])

            if form.cleaned_data['type_filiere']:
                queryset = queryset.filter(type_filiere=form.cleaned_data['type_filiere'])

            if form.cleaned_data['est_active']:
                queryset = queryset.filter(est_active=form.cleaned_data['est_active'] == 'True')

            if form.cleaned_data['search']:
                search = form.cleaned_data['search']
                queryset = queryset.filter(
                    Q(nom__icontains=search) |
                    Q(code__icontains=search) |
                    Q(nom_diplome__icontains=search)
                )

        return queryset.order_by('nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = FiliereFilterForm(self.request.GET)
        context['title'] = 'Filières'
        return context

class FiliereCreateView(LoginRequiredMixin, CreateView):
    model = Filiere
    form_class = FiliereForm
    template_name = 'academic/filiere/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Permission non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_filieres')
        else:
            return reverse_lazy('dashboard:department_head_filieres')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_filieres')
        else:
            return reverse_lazy('dashboard:department_head_filieres')

    def form_valid(self, form):
        # Associer automatiquement la filière à l'établissement de l'utilisateur
        if not self.request.user.etablissement:
            messages.error(self.request, "Impossible de créer la filière : aucun établissement associé à votre compte.")
            return redirect('dashboard:redirect')

        form.instance.etablissement = self.request.user.etablissement
        messages.success(self.request, 'Filière créée avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nouvelle Filière'
        context['submit_text'] = 'Créer'
        context['cancel_url'] = self.get_cancel_url()
        return context

class FiliereUpdateView(LoginRequiredMixin, UpdateView):
    model = Filiere
    form_class = FiliereForm
    template_name = 'academic/filiere/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Permission non autorisé")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_filieres')
        else:
            return reverse_lazy('dashboard:department_head_filieres')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_filieres')
        else:
            return reverse_lazy('dashboard:department_head_filieres')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_filieres')
        else:
            return redirect('dashboard:department_head_filieres')

    def form_valid(self, form):
        messages.success(self.request, 'Filière modifiée avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier {self.object.nom}'
        context['submit_text'] = 'Modifier'
        context['cancel_url'] = self.get_cancel_url()
        return context

@login_required
def filiere_detail(request, pk):
    # filiere = get_object_or_404(
    #     Filiere.objects.select_related('etablissement', 'departement'),
    #     pk=pk
    # )
    #
    # niveaux = filiere.niveaux.filter(est_actif=True).order_by('ordre').annotate(
    #     nombre_classes=Count('classe')
    # )
    filiere = get_object_or_404(
        Filiere.objects.select_related('departement', 'etablissement').annotate(
            nombre_niveaux=Count('niveaux'),
            nombre_etudiants=Count('niveaux__classes__apprenants', distinct=True)
        ),
        pk=pk,
        etablissement=request.user.etablissement
    )

    niveaux = filiere.niveaux.all().order_by('ordre')
    for niveau in niveaux:
        niveau.nombre_classes = niveau.classes.count()

    # Statistiques
    stats = {
        'nombre_niveaux': niveaux.count(),
        'nombre_classes_total': sum(niveau.nombre_classes for niveau in niveaux),
    }

    def get_cancel_url():
        if request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_filieres')
        else:
            return reverse_lazy('dashboard:department_head_filieres')

    context = {
        'filiere': filiere,
        'niveaux': niveaux,
        'stats': stats,
        'title': filiere.nom,
        'cancel_url': get_cancel_url()
    }

    return render(request, 'academic/filiere/detail.html', context)

@login_required
@require_http_methods(["POST"])
def filiere_toggle_status(request, pk):
    """Active/désactive une filière"""
    if request.user.role != 'ADMIN':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    filiere = get_object_or_404(Filiere, pk=pk, etablissement=request.user.etablissement)
    filiere.est_active = not filiere.est_active
    filiere.save()

    return JsonResponse({
        'success': True,
        'est_active': filiere.est_active,
        'message': f'Filière {"activée" if filiere.est_active else "désactivée"} avec succès'
    })

@login_required
@require_http_methods(["POST"])
def filiere_duplicate(request, pk):
    """Duplique une filière"""
    if request.user.role != 'ADMIN':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    filiere = get_object_or_404(Filiere, pk=pk, etablissement=request.user.etablissement)

    # Créer la copie
    filiere.pk = None
    filiere.code = f"{filiere.code}-COPIE"
    filiere.nom = f"{filiere.nom} (Copie)"
    filiere.save()

    return JsonResponse({
        'success': True,
        'message': 'Filière dupliquée avec succès',
        'new_id': str(filiere.id)
    })

@login_required
@require_http_methods(["DELETE"])
def filiere_delete(request, pk):
    """Supprime une filière"""
    if request.user.role != 'ADMIN':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    filiere = get_object_or_404(Filiere, pk=pk, etablissement=request.user.etablissement)

    # Vérifier s'il y a des niveaux associés
    if filiere.niveaux.exists():
        return JsonResponse({
            'success': False,
            'error': 'Impossible de supprimer cette filière car elle contient des niveaux'
        })

    nom = filiere.nom
    filiere.delete()

    return JsonResponse({
        'success': True,
        'message': f'Filière "{nom}" supprimée avec succès'
    })


# ============ VUES POUR NIVEAU ============
class NiveauListView(LoginRequiredMixin, ListView):
    model = Niveau
    template_name = 'academic/niveau/list.html'
    context_object_name = 'niveaux'
    paginate_by = 20

    def get_queryset(self):
        queryset = Niveau.objects.select_related(
            'filiere__etablissement', 'filiere__departement'
        ).annotate(
            nombre_classes=Count('classe')
        )

        # Filtrage par filière si spécifié
        filiere_id = self.request.GET.get('filiere')
        if filiere_id:
            queryset = queryset.filter(filiere_id=filiere_id)

        return queryset.order_by('filiere__nom', 'ordre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Niveaux'

        # Si on filtre par filière, ajouter la filière au contexte
        filiere_id = self.request.GET.get('filiere')
        if filiere_id:
            try:
                context['filiere'] = Filiere.objects.get(id=filiere_id)
            except Filiere.DoesNotExist:
                pass

        return context

class NiveauCreateView(LoginRequiredMixin, CreateView):
    model = Niveau
    form_class = NiveauForm
    template_name = 'academic/niveau/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Permission non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_niveaux')
        else:
            return reverse_lazy('dashboard:department_head_niveaux')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_niveaux')
        else:
            return reverse_lazy('dashboard:department_head_niveaux')

    def form_valid(self, form):
        messages.success(self.request, 'Niveau créé avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nouveau Niveau'
        context['submit_text'] = 'Créer'
        context['cancel_url'] = self.get_cancel_url()
        return context

class NiveauUpdateView(LoginRequiredMixin, UpdateView):
    model = Niveau
    form_class = NiveauForm
    template_name = 'academic/niveau/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Permission non autorisé")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_niveaux')
        else:
            return reverse_lazy('dashboard:department_head_niveaux')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_niveaux')
        else:
            return reverse_lazy('dashboard:department_head_niveaux')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_niveaux')
        else:
            return redirect('dashboard:department_head_niveaux')

    def form_valid(self, form):
        messages.success(self.request, 'Niveau modifié avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier {self.object.nom}'
        context['submit_text'] = 'Modifier'
        context['cancel_url'] = self.get_cancel_url()
        return context

@login_required
def niveau_detail(request, pk):
    if request.user.role != 'ADMIN':
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    niveau = get_object_or_404(
        Niveau.objects.select_related(
            'filiere__departement',
            'filiere__etablissement'
        ).annotate(
            nombre_classes=Count('classes', filter=Q(classes__est_active=True)),
            nombre_etudiants=Count(
                'classes__apprenants',
                filter=Q(classes__apprenants__utilisateur__est_actif=True),
                distinct=True
            )
        ),
        pk=pk,
        filiere__etablissement=request.user.etablissement
    )

    # Classes du niveau (10 premières)
    classes = niveau.classes.select_related(
        'annee_academique',
        'professeur_principal',
        'salle_principale'
    ).annotate(
        nombre_etudiants=Count(
            'apprenants',
            filter=Q(apprenants__utilisateur__est_actif=True)
        )
    ).filter(est_active=True)[:10]

    def get_cancel_url():
        if request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_niveaux')
        else:
            return reverse_lazy('dashboard:department_head_niveaux')

    context = {
        'niveau': niveau,
        'classes': classes,
        'title': niveau.nom,
        'cancel_url': get_cancel_url()
    }

    return render(request, 'academic/niveau/detail.html', context)

@login_required
@require_http_methods(["POST"])
def niveau_toggle_status(request, pk):
    """Active/désactive un niveau"""
    if request.user.role != 'ADMIN':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    niveau = get_object_or_404(
        Niveau,
        pk=pk,
        filiere__etablissement=request.user.etablissement
    )
    niveau.est_actif = not niveau.est_actif
    niveau.save()

    return JsonResponse({
        'success': True,
        'est_actif': niveau.est_actif,
        'message': f'Niveau {"activé" if niveau.est_actif else "désactivé"} avec succès'
    })

@login_required
@require_http_methods(["DELETE"])
def niveau_delete(request, pk):
    """Supprime un niveau"""
    if request.user.role != 'ADMIN':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    niveau = get_object_or_404(
        Niveau,
        pk=pk,
        filiere__etablissement=request.user.etablissement
    )

    # Vérifier s'il y a des classes associées
    if niveau.classes.exists():
        return JsonResponse({
            'success': False,
            'error': 'Impossible de supprimer ce niveau car il contient des classes'
        })

    nom = niveau.nom
    niveau.delete()

    return JsonResponse({
        'success': True,
        'message': f'Niveau "{nom}" supprimé avec succès'
    })

# ============ VUES POUR CLASSE ============
class ClasseListView(LoginRequiredMixin, ListView):
    model = Classe
    template_name = 'academic/classe/list.html'
    context_object_name = 'classes'
    paginate_by = 20

    def get_queryset(self):
        queryset = Classe.objects.select_related(
            'etablissement', 'niveau__filiere', 'annee_academique',
            'professeur_principal', 'salle_principale'
        )

        # Filtrage
        etablissement_id = self.request.GET.get('etablissement')
        if etablissement_id:
            queryset = queryset.filter(etablissement_id=etablissement_id)

        filiere_id = self.request.GET.get('filiere')
        if filiere_id:
            queryset = queryset.filter(niveau__filiere_id=filiere_id)

        annee_id = self.request.GET.get('annee')
        if annee_id:
            queryset = queryset.filter(annee_academique_id=annee_id)

        return queryset.order_by('nom')

    def get_context_data(self, **kwargs):
        from apps.establishments.models import Etablissement, AnneeAcademique

        context = super().get_context_data(**kwargs)
        context['title'] = 'Classes'
        context['etablissements'] = Etablissement.objects.filter(est_actif=True)
        context['filieres'] = Filiere.objects.filter(est_active=True)
        context['annees'] = AnneeAcademique.objects.filter(est_active=True)

        return context

class ClasseCreateView(LoginRequiredMixin, CreateView):
    model = Classe
    form_class = ClasseForm
    template_name = 'academic/classe/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Permission non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_classes')
        else:
            return reverse_lazy('dashboard:department_head_classes')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_classes')
        else:
            return reverse_lazy('dashboard:department_head_classes')

    def form_valid(self, form):
        messages.success(self.request, 'Classe créée avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nouvelle Classe'
        context['submit_text'] = 'Créer'
        context['cancel_url'] = self.get_cancel_url()
        return context

class ClasseUpdateView(LoginRequiredMixin, UpdateView):
    model = Classe
    form_class = ClasseForm
    template_name = 'academic/classe/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Permission non autorisé")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_classes')
        else:
            return reverse_lazy('dashboard:department_head_classes')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_classes')
        else:
            return reverse_lazy('dashboard:department_head_classes')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_classes')
        else:
            return redirect('dashboard:department_head_classes')

    def form_valid(self, form):
        messages.success(self.request, 'Classe modifiée avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier {self.object.nom}'
        context['submit_text'] = 'Modifier'
        context['cancel_url'] = self.get_cancel_url()
        return context

@login_required
def classe_detail(request, pk):
    classe = get_object_or_404(
        Classe.objects.select_related(
            'etablissement', 'niveau__filiere', 'annee_academique',
            'professeur_principal', 'salle_principale'
        ),
        pk=pk
    )

    # Statistiques de la classe
    stats = {
        'places_disponibles': classe.get_places_disponibles(),
        'taux_occupation': (classe.effectif_actuel / classe.capacite_maximale * 100) if classe.capacite_maximale > 0 else 0,
        'est_pleine': classe.est_pleine(),
    }

    def get_cancel_url():
        if request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_classes')
        else:
            return reverse_lazy('dashboard:department_head_classes')

    context = {
        'classe': classe,
        'stats': stats,
        'title': classe.nom,
        'cancel_url': get_cancel_url()
    }

    return render(request, 'academic/classe/detail.html', context)

@login_required
@require_http_methods(["POST"])
def classe_toggle_status(request, pk):
    """Active/désactive une classe"""
    if request.user.role != 'ADMIN':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    classe = get_object_or_404(Classe, pk=pk, etablissement=request.user.etablissement)
    classe.est_active = not classe.est_active
    classe.save()

    return JsonResponse({
        'success': True,
        'est_active': classe.est_active,
        'message': f'Classe {"activée" if classe.est_active else "désactivée"} avec succès'
    })

@login_required
@require_http_methods(["POST"])
def classe_duplicate(request, pk):
    """Duplique une classe"""
    if request.user.role != 'ADMIN':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    classe = get_object_or_404(Classe, pk=pk, etablissement=request.user.etablissement)

    # Créer la copie
    classe.pk = None
    classe.code = f"{classe.code}-COPIE"
    classe.nom = f"{classe.nom} (Copie)"
    classe.effectif_actuel = 0  # Réinitialiser l'effectif
    classe.save()

    return JsonResponse({
        'success': True,
        'message': 'Classe dupliquée avec succès',
        'new_id': str(classe.id)
    })

@login_required
@require_http_methods(["DELETE"])
def classe_delete(request, pk):
    """Supprime une classe"""
    if request.user.role != 'ADMIN':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    classe = get_object_or_404(Classe, pk=pk, etablissement=request.user.etablissement)

    # Vérifier s'il y a des étudiants inscrits
    if classe.apprenants.exists():
        return JsonResponse({
            'success': False,
            'error': 'Impossible de supprimer cette classe car elle contient des étudiants'
        })

    nom = classe.nom
    classe.delete()

    return JsonResponse({
        'success': True,
        'message': f'Classe "{nom}" supprimée avec succès'
    })


# ============ VUES POUR PERIODE ACADEMIQUE ============
class PeriodeAcademiqueListView(LoginRequiredMixin, ListView):
    model = PeriodeAcademique
    template_name = 'academic/periode/list.html'
    context_object_name = 'periodes'
    paginate_by = 20

    def get_queryset(self):
        queryset = PeriodeAcademique.objects.select_related(
            'etablissement', 'annee_academique'
        )

        # Filtrage
        etablissement_id = self.request.GET.get('etablissement')
        if etablissement_id:
            queryset = queryset.filter(etablissement_id=etablissement_id)

        annee_id = self.request.GET.get('annee')
        if annee_id:
            queryset = queryset.filter(annee_academique_id=annee_id)

        return queryset.order_by('-annee_academique__nom', 'ordre')

    def get_context_data(self, **kwargs):
        from apps.establishments.models import Etablissement, AnneeAcademique

        context = super().get_context_data(**kwargs)
        context['title'] = 'Périodes académiques'
        context['etablissements'] = Etablissement.objects.filter(est_actif=True)
        context['annees'] = AnneeAcademique.objects.filter(est_active=True)

        return context

class PeriodeAcademiqueCreateView(LoginRequiredMixin, CreateView):
    model = PeriodeAcademique
    form_class = PeriodeAcademiqueForm
    template_name = 'academic/periode/form.html'
    success_url = reverse_lazy('academic:periode_list')

    def form_valid(self, form):
        messages.success(self.request, 'Période académique créée avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Créer une période académique'
        context['submit_text'] = 'Créer'
        return context

class PeriodeAcademiqueUpdateView(LoginRequiredMixin, UpdateView):
    model = PeriodeAcademique
    form_class = PeriodeAcademiqueForm
    template_name = 'academic/periode/form.html'
    success_url = reverse_lazy('academic:periode_list')

    def form_valid(self, form):
        messages.success(self.request, 'Période académique modifiée avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier {self.object.nom}'
        context['submit_text'] = 'Modifier'
        return context


# ============ VUES POUR PROGRAMME ============
class ProgrammeListView(LoginRequiredMixin, ListView):
    model = Programme
    template_name = 'academic/programme/list.html'
    context_object_name = 'programmes'
    paginate_by = 20

    def get_queryset(self):
        queryset = Programme.objects.select_related(
            'filiere__etablissement', 'filiere__departement', 'approuve_par'
        )

        # Filtrage
        etablissement_id = self.request.GET.get('etablissement')
        if etablissement_id:
            queryset = queryset.filter(filiere__etablissement_id=etablissement_id)

        return queryset.order_by('filiere__nom')

    def get_context_data(self, **kwargs):
        from apps.establishments.models import Etablissement

        context = super().get_context_data(**kwargs)
        context['title'] = 'Programmes'
        context['etablissements'] = Etablissement.objects.filter(est_actif=True)

        return context

class ProgrammeCreateView(LoginRequiredMixin, CreateView):
    model = Programme
    form_class = ProgrammeForm
    template_name = 'academic/programme/form.html'
    success_url = reverse_lazy('academic:programme_list')

    def form_valid(self, form):
        messages.success(self.request, 'Programme créé avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Créer un programme'
        context['submit_text'] = 'Créer'
        return context

class ProgrammeUpdateView(LoginRequiredMixin, UpdateView):
    model = Programme
    form_class = ProgrammeForm
    template_name = 'academic/programme/form.html'
    success_url = reverse_lazy('academic:programme_list')

    def form_valid(self, form):
        messages.success(self.request, 'Programme modifié avec succès.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier {self.object.nom}'
        context['submit_text'] = 'Modifier'
        return context

@login_required
def programme_detail(request, pk):
    programme = get_object_or_404(
        Programme.objects.select_related(
            'filiere__etablissement', 'filiere__departement', 'approuve_par'
        ),
        pk=pk
    )

    context = {
        'programme': programme,
        'title': programme.nom
    }

    return render(request, 'academic/programme/detail.html', context)


# API Views public
@require_http_methods(["GET"])
def api_departements_by_etablissementId_publics(request, etablissement_id):
    """API pour récupérer les départements d'un établissement public"""
    try:
        # Vérifier que l'établissement existe
        from apps.establishments.models import Etablissement
        etablissement = Etablissement.objects.get(id=etablissement_id)

        # Vérifications optionnelles (adaptez à vos champs)
        if hasattr(etablissement, 'actif') and not etablissement.actif:
            return JsonResponse({
                'success': False,
                'error': 'Établissement non actif'
            }, status=404)

        if hasattr(etablissement, 'public') and not etablissement.public:
            return JsonResponse({
                'success': False,
                'error': 'Établissement non public'
            }, status=404)

        departements = Departement.objects.filter(
            etablissement_id=etablissement_id,
            est_actif=True
        ).select_related('chef').annotate(
            nombre_filieres=Count('filiere')
        ).order_by('nom')

        data = [{
            'id': str(dept.id),
            'nom': dept.nom,
            'code': dept.code,
            'description': dept.description,
            'chef': {
                'id': str(dept.chef.id) if dept.chef else None,
                'nom': dept.chef.get_full_name() if dept.chef else None,
                'email': dept.chef.email if dept.chef else None,
            } if dept.chef else None,
            'email': dept.email,
            'telephone': dept.telephone,
            'nombre_filieres': dept.nombre_filieres,
        } for dept in departements]

        return JsonResponse({
            'success': True,
            'etablissement': {
                'id': str(etablissement.id),
                'nom': etablissement.nom,
                'sigle': etablissement.sigle
            },
            'count': len(data),
            'results': data
        })

    except Etablissement.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Établissement non trouvé'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors du chargement des départements: {str(e)}'
        }, status=500)

@require_http_methods(["GET"])
def api_filieres_by_departementId_publics(request, departement_id):
    """API pour récupérer les filières d'un département public"""
    try:
        # Vérifier que le département existe
        departement = Departement.objects.select_related('etablissement').get(
            id=departement_id,
            est_actif=True
        )

        # Vérifications optionnelles sur l'établissement
        if hasattr(departement.etablissement, 'actif') and not departement.etablissement.actif:
            return JsonResponse({
                'success': False,
                'error': 'Établissement non actif'
            }, status=404)

        if hasattr(departement.etablissement, 'public') and not departement.etablissement.public:
            return JsonResponse({
                'success': False,
                'error': 'Établissement non public'
            }, status=404)

        filieres = Filiere.objects.filter(
            departement_id=departement_id,
            est_active=True
        ).annotate(
            nombre_niveaux=Count('niveaux'),
            nombre_classes=Count('niveaux__classe')
        ).order_by('nom')

        data = [{
            'id': str(filiere.id),
            'nom': filiere.nom,
            'code': filiere.code,
            'type_filiere': filiere.get_type_filiere_display() if hasattr(filiere,
                                                                          'get_type_filiere_display') else filiere.type_filiere,
            'nom_diplome': filiere.nom_diplome,
            'duree_annees': filiere.duree_annees,
            'description': filiere.description,
            'prerequis': filiere.prerequis,
            'frais_scolarite': float(filiere.frais_scolarite) if filiere.frais_scolarite else None,
            'capacite_maximale': filiere.capacite_maximale,
            'nombre_niveaux': filiere.nombre_niveaux,
            'nombre_classes': filiere.nombre_classes,
        } for filiere in filieres]

        return JsonResponse({
            'success': True,
            'departement': {
                'id': str(departement.id),
                'nom': departement.nom,
                'code': departement.code,
                'etablissement': {
                    'id': str(departement.etablissement.id),
                    'nom': departement.etablissement.nom,
                    'sigle': departement.etablissement.sigle
                }
            },
            'count': len(data),
            'results': data
        })

    except Departement.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Département non trouvé'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors du chargement des filières: {str(e)}'
        }, status=500)

@require_http_methods(["GET"])
def api_niveaux_by_filiereId_publics(request, filiere_id):
    """API pour récupérer les niveaux d'une filière publique"""
    try:
        # Vérifier que la filière existe
        filiere = Filiere.objects.select_related('etablissement', 'departement').get(
            id=filiere_id,
            est_active=True
        )

        # Vérifications optionnelles sur l'établissement
        if hasattr(filiere.etablissement, 'actif') and not filiere.etablissement.actif:
            return JsonResponse({
                'success': False,
                'error': 'Établissement non actif'
            }, status=404)

        if hasattr(filiere.etablissement, 'public') and not filiere.etablissement.public:
            return JsonResponse({
                'success': False,
                'error': 'Établissement non public'
            }, status=404)

        niveaux = Niveau.objects.filter(
            filiere_id=filiere_id,
            est_actif=True
        ).annotate(
            nombre_classes=Count('classe')
        ).order_by('ordre')

        data = [{
            'id': str(niveau.id),
            'nom': niveau.nom,
            'code': niveau.code,
            'ordre': niveau.ordre,
            'description': niveau.description,
            'frais_scolarite': float(niveau.frais_scolarite) if niveau.frais_scolarite else None,
            'nombre_classes': niveau.nombre_classes,
        } for niveau in niveaux]

        return JsonResponse({
            'success': True,
            'filiere': {
                'id': str(filiere.id),
                'nom': filiere.nom,
                'code': filiere.code,
                'nom_diplome': filiere.nom_diplome,
                'departement': {
                    'id': str(filiere.departement.id),
                    'nom': filiere.departement.nom,
                    'code': filiere.departement.code
                } if filiere.departement else None,
                'etablissement': {
                    'id': str(filiere.etablissement.id),
                    'nom': filiere.etablissement.nom,
                    'sigle': filiere.etablissement.sigle
                }
            },
            'count': len(data),
            'results': data
        })

    except Filiere.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Filière non trouvée'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors du chargement des niveaux: {str(e)}'
        }, status=500)

@login_required
def api_classes_by_filiere(request):
    """API pour récupérer les classes d'une filière"""
    filiere_id = request.GET.get('filiere_id')
    niveau_id = request.GET.get('niveau_id')

    if not filiere_id:
        return JsonResponse({'classes': []})

    queryset = Classe.objects.filter(filiere_id=filiere_id)

    if niveau_id:
        queryset = queryset.filter(niveau_id=niveau_id)

    classes = queryset.values('id', 'nom', 'code')
    return JsonResponse({'classes': list(classes)})


# ============ VUES AJAX ============
@login_required
def ajax_get_departements(request):
    """Retourne les départements d'un établissement en JSON"""
    etablissement_id = request.GET.get('etablissement_id')
    departements = []

    if etablissement_id:
        departements = list(
            Departement.objects.filter(
                etablissement_id=etablissement_id,
                est_actif=True
            ).values('id', 'nom')
        )

    return JsonResponse({'departements': departements})

@login_required
def ajax_get_niveaux(request):
    """Retourne les niveaux d'une filière en JSON"""
    filiere_id = request.GET.get('filiere_id')
    niveaux = []

    if filiere_id:
        niveaux = list(
            Niveau.objects.filter(
                filiere_id=filiere_id,
                est_actif=True
            ).values('id', 'nom', 'ordre').order_by('ordre')
        )

    return JsonResponse({'niveaux': niveaux})


# ============ DASHBOARD/STATISTIQUES ============
@login_required
def dashboard_academic(request):
    """Dashboard académique avec statistiques générales"""

    # Statistiques générales
    stats = {
        'total_departements': Departement.objects.filter(est_actif=True).count(),
        'total_filieres': Filiere.objects.filter(est_active=True).count(),
        'total_niveaux': Niveau.objects.filter(est_actif=True).count(),
        'total_classes': Classe.objects.filter(est_active=True).count(),
    }

    # Top 5 filières par nombre d'étudiants (basé sur les classes)
    top_filieres = Filiere.objects.filter(est_active=True).annotate(
        total_etudiants=Sum('niveaux__classe__effectif_actuel')
    ).order_by('-total_etudiants')[:5]

    # Classes avec le plus d'étudiants
    classes_pleines = Classe.objects.filter(
        est_active=True,
        effectif_actuel__gte=models.F('capacite_maximale') * 0.9
    ).select_related('niveau__filiere')[:10]

    # Statistiques par type de filière
    stats_par_type = Filiere.objects.filter(est_active=True).values(
        'type_filiere'
    ).annotate(
        count=Count('id'),
        total_etudiants=Sum('niveaux__classe__effectif_actuel')
    ).order_by('-count')

    context = {
        'title': 'Dashboard Académique',
        'stats': stats,
        'top_filieres': top_filieres,
        'classes_pleines': classes_pleines,
        'stats_par_type': stats_par_type,
    }

    return render(request, 'academic/dashboard.html', context)


# Vues AJAX pour les dépendances
@csrf_exempt
@require_http_methods(["GET", "POST"])
def ajax_get_departements(request):
    """Retourne les départements d'un établissement via Ajax"""
    etablissement_id = request.GET.get('etablissement_id') or request.POST.get('etablissement_id')

    if not etablissement_id:
        return JsonResponse({'success': False, 'error': 'ID établissement requis'})

    try:
        departements = Departement.objects.filter(
            etablissement_id=etablissement_id,
            est_actif=True
        ).values('id', 'nom', 'code').order_by('nom')

        return JsonResponse({
            'success': True,
            'departements': list(departements)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_http_methods(["GET", "POST"])
def ajax_get_filieres(request):
    """Retourne les filières d'un établissement ou département via Ajax"""
    etablissement_id = request.GET.get('etablissement_id') or request.POST.get('etablissement_id')
    departement_id = request.GET.get('departement_id') or request.POST.get('departement_id')

    if not etablissement_id:
        return JsonResponse({'success': False, 'error': 'ID établissement requis'})

    try:
        # Filtrer par établissement
        filieres = Filiere.objects.filter(
            etablissement_id=etablissement_id,
            est_active=True
        )

        # Filtrer par département si spécifié
        if departement_id and departement_id != '':
            filieres = filieres.filter(departement_id=departement_id)

        filieres_data = filieres.values(
            'id', 'nom', 'code', 'type_filiere', 'duree_annees',
            'nom_diplome', 'frais_scolarite'
        ).order_by('nom')

        return JsonResponse({
            'success': True,
            'filieres': list(filieres_data)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_http_methods(["GET", "POST"])
def ajax_get_niveaux(request):
    """Retourne les niveaux d'une filière via Ajax"""
    filiere_id = request.GET.get('filiere_id') or request.POST.get('filiere_id')

    if not filiere_id:
        return JsonResponse({'success': False, 'error': 'ID filière requis'})

    try:
        niveaux = Niveau.objects.filter(
            filiere_id=filiere_id,
            est_actif=True
        ).values('id', 'nom', 'code', 'ordre', 'frais_scolarite').order_by('ordre')

        return JsonResponse({
            'success': True,
            'niveaux': list(niveaux)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_http_methods(["GET", "POST"])
def ajax_get_classes(request):
    """Retourne les classes d'un niveau pour une année académique via Ajax"""
    niveau_id = request.GET.get('niveau_id') or request.POST.get('niveau_id')
    annee_id = request.GET.get('annee_id') or request.POST.get('annee_id')

    if not niveau_id:
        return JsonResponse({'success': False, 'error': 'ID niveau requis'})

    try:
        # Si pas d'année spécifiée, prendre l'année courante
        if not annee_id:
            annee_courante = AnneeAcademique.objects.filter(
                est_courante=True
            ).first()
            if annee_courante:
                annee_id = annee_courante.id

        classes = Classe.objects.filter(
            niveau_id=niveau_id,
            est_active=True
        )

        if annee_id:
            classes = classes.filter(annee_academique_id=annee_id)

        classes_data = []
        for classe in classes:
            classes_data.append({
                'id': classe.id,
                'nom': classe.nom,
                'code': classe.code,
                'capacite_maximale': classe.capacite_maximale,
                'effectif_actuel': classe.effectif_actuel,
                'places_disponibles': classe.get_places_disponibles(),
                'est_pleine': classe.est_pleine()
            })

        return JsonResponse({
            'success': True,
            'classes': classes_data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_http_methods(["GET"])
def ajax_get_etablissements_publics(request):
    """Retourne les établissements publics actifs pour la candidature"""
    try:
        etablissements = Etablissement.objects.filter(
            actif=True,
            public=True  # Uniquement les établissements publics pour les candidatures
        ).values(
            'id', 'nom', 'sigle', 'code', 'adresse',
            'type_etablissement__nom', 'localite__nom'
        ).order_by('nom')

        return JsonResponse({
            'success': True,
            'etablissements': list(etablissements)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

