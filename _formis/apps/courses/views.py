# apps/courses/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count, Sum, Avg
from django.http import JsonResponse, HttpResponse, FileResponse, Http404

from django.core.paginator import Paginator
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from django.views.decorators.http import require_POST
from django.utils import timezone
import mimetypes

from .models import (
    Module, Matiere, StatutCours, TypeCours, Cours, CahierTexte,
    Ressource, Presence, EmploiDuTemps, CreneauEmploiDuTemps
)
from .forms import (
    ModuleForm, MatiereForm, CoursForm, CoursUpdateForm,
    CahierTexteForm, RessourceForm, PresenceForm, PresenceBulkForm,
    EmploiDuTempsForm, CreneauEmploiDuTempsForm, FiltreCoursForm, RessourceFormSet
)
from apps.establishments.models import Etablissement, AnneeAcademique, Salle
from apps.accounts.models import Utilisateur
from apps.academic.models import Niveau, Filiere, Departement, Classe


class EtablissementFilterMixin:
    """Mixin pour filtrer les objets selon l'établissement de l'utilisateur"""

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(self.request.user, 'etablissement'):
            return self.filter_by_etablissement(queryset)
        return queryset

    def filter_by_etablissement(self, queryset):
        # À override dans chaque vue selon le modèle
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

# ============================================================================
# VUES MODULE
# ============================================================================
class ModuleListView(LoginRequiredMixin, ListView):
    model = Module
    template_name = 'courses/module/list.html'
    context_object_name = 'modules'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = Module.objects.select_related(
            'niveau__filiere__departement',
            'coordinateur'
        ).annotate(
            nombre_matieres=Count('matieres')
        )

        # Filtrage selon le rôle
        if user.role == 'ADMIN':
            queryset = queryset.filter(
                niveau__filiere__etablissement=user.etablissement
            )
        elif user.role == 'CHEF_DEPARTEMENT':
            queryset = queryset.filter(
                niveau__filiere__departement=user.departement
            )
        elif user.role == 'ENSEIGNANT':
            queryset = queryset.filter(
                Q(coordinateur=user) |
                Q(matieres__enseignant_responsable=user)
            ).distinct()

        # Filtres de recherche
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search)
            )

        departement_id = self.request.GET.get('departement')
        if departement_id:
            queryset = queryset.filter(niveau__filiere__departement_id=departement_id)

        filiere_id = self.request.GET.get('filiere')
        if filiere_id:
            queryset = queryset.filter(niveau__filiere_id=filiere_id)

        niveau_id = self.request.GET.get('niveau')
        if niveau_id:
            queryset = queryset.filter(niveau_id=niveau_id)

        return queryset.order_by('niveau__ordre', 'nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.role == 'ADMIN':
            context['departements'] = Departement.objects.filter(
                etablissement=user.etablissement, est_actif=True
            )
            context['filieres'] = Filiere.objects.filter(
                etablissement=user.etablissement, est_active=True
            )
        elif user.role == 'CHEF_DEPARTEMENT':
            context['departements'] = [user.departement]
            context['filieres'] = Filiere.objects.filter(
                departement=user.departement, est_active=True
            )

        context['niveaux'] = Niveau.objects.filter(est_actif=True)
        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'departement': self.request.GET.get('departement', ''),
            'filiere': self.request.GET.get('filiere', ''),
            'niveau': self.request.GET.get('niveau', ''),
        }

        return context

class ModuleCreateView(LoginRequiredMixin, CreateView):
    model = Module
    form_class = ModuleForm
    template_name = 'courses/module/form.html'

    # Contrôle d'accès
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas créer de module. Vérifiez vos permissions.")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    # URL de succès après création
    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_modules')
        else:
            return reverse_lazy('dashboard:department_head_modules')

    # URL pour le bouton annuler
    def get_cancel_url(self):
        return self.get_success_url()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, "Module créé avec succès !")
        return redirect(self.get_success_url())

    # Contexte pour le template
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter un module'
        context['submit_text'] = 'Créer'
        context['cancel_url'] = self.get_cancel_url()
        return context

class ModuleUpdateView(LoginRequiredMixin, UpdateView):
    model = Module
    form_class = ModuleForm
    template_name = 'courses/module/form.html'

    # Contrôle d'accès
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas modifier de module. Vérifiez vos permissions.")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    # URL de succès après création
    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_modules')
        else:
            return reverse_lazy('dashboard:department_head_modules')

    # URL pour le bouton annuler
    def get_cancel_url(self):
        return self.get_success_url()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Module modifié avec succès !")
        return super().form_valid(form)

class ModuleDetailView(LoginRequiredMixin, DetailView):
    model = Module
    template_name = 'courses/module/detail.html'
    context_object_name = 'module'

    def get_queryset(self):
        user = self.request.user
        queryset = Module.objects.select_related(
            'niveau__filiere__departement',
            'coordinateur'
        ).prefetch_related('matieres__enseignant_responsable')

        if user.role == 'ADMIN':
            queryset = queryset.filter(
                niveau__filiere__etablissement=user.etablissement
            )
        elif user.role == 'CHEF_DEPARTEMENT':
            queryset = queryset.filter(
                niveau__filiere__departement=user.departement
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        module = self.object

        # Agrégation unique pour toutes les statistiques
        agg = module.matieres.aggregate(
            volume_horaire_cm=Sum('heures_cours_magistral'),
            volume_horaire_td=Sum('heures_travaux_diriges'),
            volume_horaire_tp=Sum('heures_travaux_pratiques'),
            credits_total=Sum('credits_ects')
        )

        volume_cm = agg['volume_horaire_cm'] or 0
        volume_td = agg['volume_horaire_td'] or 0
        volume_tp = agg['volume_horaire_tp'] or 0
        credits_total = agg['credits_total'] or 0

        context['stats'] = {
            'nombre_matieres': module.matieres.count(),
            'volume_horaire_cm': volume_cm,
            'volume_horaire_td': volume_td,
            'volume_horaire_tp': volume_tp,
            'volume_horaire_total': volume_cm + volume_td + volume_tp,
            'credits_total': credits_total,
        }

        return context

class ModuleDeleteView(LoginRequiredMixin, DeleteView):
    model = Module

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas supprimer ce module. Vérifiez vos permissions.")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    # URL de succès après création
    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_modules')
        else:
            return reverse_lazy('dashboard:department_head_modules')

    # URL pour le bouton annuler
    def get_cancel_url(self):
        return self.get_success_url()

    def get_error_redirect(self):
        return self.get_cancel_url()

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Module supprimé avec succès !")
        return super().delete(request, *args, **kwargs)


# ============================================================================
# VUES MATIERE
# ============================================================================
class MatiereListView(LoginRequiredMixin, ListView):
    model = Matiere
    template_name = 'courses/matiere/list.html'
    context_object_name = 'matieres'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = Matiere.objects.select_related(
            'niveau__filiere__departement',
            'module',
            'enseignant_responsable'
        )

        # Filtrage selon le rôle
        if user.role == 'ADMIN':
            queryset = queryset.filter(
                niveau__filiere__etablissement=user.etablissement
            )
        elif user.role == 'CHEF_DEPARTEMENT':
            queryset = queryset.filter(
                niveau__filiere__departement=user.departement
            )
        elif user.role == 'ENSEIGNANT':
            queryset = queryset.filter(
                enseignant_responsable=user
            )

        # Filtres de recherche
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search)
            )

        niveau_id = self.request.GET.get('niveau')
        if niveau_id:
            queryset = queryset.filter(niveau_id=niveau_id)

        module_id = self.request.GET.get('module')
        if module_id == 'sans_module':
            queryset = queryset.filter(module__isnull=True)
        elif module_id:
            queryset = queryset.filter(module_id=module_id)

        actif = self.request.GET.get('actif')
        if actif:
            queryset = queryset.filter(actif=actif == 'True')

        return queryset.order_by('niveau__ordre', 'nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.role == 'ADMIN':
            context['niveaux'] = Niveau.objects.filter(
                filiere__etablissement=user.etablissement,
                est_actif=True
            ).select_related('filiere')
            context['modules'] = Module.objects.filter(
                niveau__filiere__etablissement=user.etablissement,
                actif=True
            )
        elif user.role == 'CHEF_DEPARTEMENT':
            context['niveaux'] = Niveau.objects.filter(
                filiere__departement=user.departement,
                est_actif=True
            ).select_related('filiere')
            context['modules'] = Module.objects.filter(
                niveau__filiere__departement=user.departement,
                actif=True
            )

        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'niveau': self.request.GET.get('niveau', ''),
            'module': self.request.GET.get('module', ''),
            'actif': self.request.GET.get('actif', ''),
        }

        return context

class MatiereCreateView(LoginRequiredMixin, CreateView):
    model = Matiere
    form_class = MatiereForm
    template_name = 'courses/matiere/form.html'

    # Contrôle d'accès
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas créer de matière. Vérifiez vos permissions.")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    # URL de succès après création
    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_matieres')
        else:
            return reverse_lazy('dashboard:department_head_matieres')

    # URL pour le bouton annuler
    def get_cancel_url(self):
        return self.get_success_url()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, "Matière créée avec succès !")
        return redirect(self.get_success_url())

    # Contexte pour le template
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter une matière'
        context['submit_text'] = 'Créer'
        context['cancel_url'] = self.get_cancel_url()
        return context

class MatiereUpdateView(LoginRequiredMixin, UpdateView):
    model = Matiere
    form_class = MatiereForm
    template_name = 'courses/matiere/form.html'

    # Contrôle d'accès
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas créer de matière. Vérifiez vos permissions.")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    # URL de succès après création
    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_matieres')
        else:
            return reverse_lazy('dashboard:department_head_matieres')

    # URL pour le bouton annuler
    def get_cancel_url(self):
        return self.get_success_url()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Matière modifiée avec succès !")
        return super().form_valid(form)

class MatiereDetailView(LoginRequiredMixin, DetailView):
    model = Matiere
    template_name = 'courses/matiere/detail.html'
    context_object_name = 'matiere'

    def get_queryset(self):
        user = self.request.user
        queryset = Matiere.objects.select_related(
            'niveau__filiere__departement',
            'module',
            'enseignant_responsable'
        )

        if user.role == 'ADMIN':
            queryset = queryset.filter(
                niveau__filiere__etablissement=user.etablissement
            )
        elif user.role == 'CHEF_DEPARTEMENT':
            queryset = queryset.filter(
                niveau__filiere__departement=user.departement
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        matiere = self.object

        # Statistiques des cours
        context['stats_cours'] = {
            'total': Cours.objects.filter(matiere=matiere).count(),
            'programmes': Cours.objects.filter(matiere=matiere, statut=StatutCours.PROGRAMME).count(),
            'termines': Cours.objects.filter(matiere=matiere, statut=StatutCours.TERMINE).count(),
        }

        # Classes utilisant cette matière
        context['classes'] = Classe.objects.filter(
            cours__matiere=matiere
        ).distinct()

        return context

class MatiereDeleteView(LoginRequiredMixin, DeleteView):
    model = Matiere

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas supprimer ce module. Vérifiez vos permissions.")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    # URL de succès après création
    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_matieres')
        else:
            return reverse_lazy('dashboard:department_head_matieres')

    # URL pour le bouton annuler
    def get_cancel_url(self):
        return self.get_success_url()

    def get_error_redirect(self):
        return self.get_cancel_url()

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Matière supprimée avec succès !")
        return super().delete(request, *args, **kwargs)


# ============================================================================
#  VUES EMPLOI DU TEMPS
# ============================================================================
class EmploiDuTempsListView(LoginRequiredMixin, ListView):
    model = EmploiDuTemps
    template_name = 'courses/emploi_du_temps/list.html'
    context_object_name = 'emplois_du_temps'
    paginate_by = 20

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            classe__niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrage par classe
        classe = self.request.GET.get('classe')
        if classe:
            queryset = queryset.filter(classe_id=classe)

        return queryset.select_related('classe', 'periode_academique').order_by('-created_at')

class EmploiDuTempsDetailView(LoginRequiredMixin, DetailView):
    model = EmploiDuTemps
    template_name = 'courses/emploi_du_temps/detail.html'
    context_object_name = 'emploi_du_temps'

    def get_queryset(self):
        user = self.request.user
        queryset = EmploiDuTemps.objects.select_related(
            'classe__niveau__filiere',
            'enseignant',
            'periode_academique'
        ).prefetch_related(
            'creneaux__cours__matiere',
            'creneaux__cours__enseignant',
            'creneaux__cours__salle'
        )

        if user.role == 'ADMIN':
            queryset = queryset.filter(
                Q(classe__etablissement=user.etablissement) |
                Q(enseignant__etablissement=user.etablissement)
            )
        elif user.role == 'CHEF_DEPARTEMENT':
            queryset = queryset.filter(
                Q(classe__niveau__filiere__departement=user.departement) |
                Q(enseignant__departement=user.departement)
            )
        elif user.role == 'ENSEIGNANT':
            queryset = queryset.filter(enseignant=user, publie=True)
        elif user.role == 'APPRENANT':
            if hasattr(user, 'profil_apprenant'):
                queryset = queryset.filter(
                    classe=user.profil_apprenant.classe_actuelle,
                    publie=True
                )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        edt = self.object

        # Générer les jours de la semaine
        start_date = edt.semaine_debut
        days = []
        for i in range(6):  # Lundi à Samedi
            day_date = start_date + timedelta(days=i)
            days.append({
                'num': i,
                'name': ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'][i],
                'date': day_date
            })
        context['days'] = days
        context['hours'] = range(8, 19)

        # Statistiques
        creneaux = edt.creneaux.all()
        total_minutes = 0
        for creneau in creneaux:
            start = datetime.combine(datetime.today(), creneau.heure_debut)
            end = datetime.combine(datetime.today(), creneau.heure_fin)
            total_minutes += (end - start).seconds / 60

        context['total_heures'] = int(total_minutes / 60)
        context['nombre_matieres'] = creneaux.values('cours__matiere').distinct().count()
        context['nombre_enseignants'] = creneaux.values('cours__enseignant').distinct().count()

        return context

class EmploiDuTempsCreateView(LoginRequiredMixin, CreateView):
    model = EmploiDuTemps
    form_class = EmploiDuTempsForm
    template_name = 'courses/emploi_du_temps/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.cree_par = self.request.user
        messages.success(self.request, "Emploi du temps créé avec succès !")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('courses:emploi_du_temps_detail', kwargs={'pk': self.object.pk})

class EmploiDuTempsUpdateView(LoginRequiredMixin, UpdateView):
    model = EmploiDuTemps
    form_class = EmploiDuTempsForm
    template_name = 'courses/emploi_du_temps/form.html'

    def form_valid(self, form):
        messages.success(self.request, 'Emploi du temps modifié avec succès.')
        return super().form_valid(form)

class EmploiDuTempsDeleteView(LoginRequiredMixin, DeleteView):
    model = EmploiDuTemps
    success_url = reverse_lazy('courses:emploi_du_temps_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Emploi du temps supprimé avec succès !")
        return super().delete(request, *args, **kwargs)

@login_required
def emploi_du_temps_publish(request, pk):
    """Publier un emploi du temps"""
    edt = get_object_or_404(EmploiDuTemps, pk=pk)

    # Vérifier les permissions
    user = request.user
    if user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        return JsonResponse({'success': False, 'message': 'Permission refusée'})

    if request.method == 'POST':
        edt.publie = True
        edt.save()
        messages.success(request, "Emploi du temps publié avec succès !")
        return JsonResponse({'success': True})

    return JsonResponse({'success': False})

@login_required
def emploi_du_temps_generate(request):
    """Générer automatiquement un emploi du temps"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Méthode non autorisée'})

    user = request.user
    if user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        return JsonResponse({'success': False, 'message': 'Permission refusée'})

    try:
        # Récupérer les paramètres
        filter_type = request.POST.get('type')
        classe_id = request.POST.get('classe_id')
        enseignant_id = request.POST.get('enseignant_id')
        periode_id = request.POST.get('periode_id')
        semaine_debut = datetime.strptime(request.POST.get('semaine_debut'), '%Y-%m-%d').date()
        nb_semaines = int(request.POST.get('nb_semaines', 1))

        # Calculer la fin de semaine
        semaine_fin = semaine_debut + timedelta(days=(nb_semaines * 7) - 1)

        # Créer l'emploi du temps
        if filter_type == 'classe':
            classe = get_object_or_404(Classe, pk=classe_id)
            nom = f"EDT {classe.nom} - Semaine du {semaine_debut.strftime('%d/%m/%Y')}"
            edt = EmploiDuTemps.objects.create(
                classe=classe,
                periode_academique_id=periode_id,
                nom=nom,
                semaine_debut=semaine_debut,
                semaine_fin=semaine_fin,
                cree_par=user
            )
            # Récupérer les cours de la classe
            cours_list = Cours.objects.filter(
                classe=classe,
                periode_academique_id=periode_id,
                date_prevue__range=[semaine_debut, semaine_fin],
                actif=True
            ).select_related('matiere')
        else:
            enseignant = get_object_or_404(Utilisateur, pk=enseignant_id)
            nom = f"EDT {enseignant.get_full_name()} - Semaine du {semaine_debut.strftime('%d/%m/%Y')}"
            edt = EmploiDuTemps.objects.create(
                enseignant=enseignant,
                periode_academique_id=periode_id,
                nom=nom,
                semaine_debut=semaine_debut,
                semaine_fin=semaine_fin,
                cree_par=user
            )
            # Récupérer les cours de l'enseignant
            cours_list = Cours.objects.filter(
                enseignant=enseignant,
                periode_academique_id=periode_id,
                date_prevue__range=[semaine_debut, semaine_fin],
                actif=True
            ).select_related('matiere')

        # Créer les créneaux
        for cours in cours_list:
            jour_semaine = cours.date_prevue.weekday()  # 0 = Lundi
            if jour_semaine < 6:  # Pas le dimanche
                CreneauEmploiDuTemps.objects.create(
                    emploi_du_temps=edt,
                    cours=cours,
                    jour_semaine=jour_semaine,
                    heure_debut=cours.heure_debut_prevue,
                    heure_fin=cours.heure_fin_prevue
                )

        return JsonResponse({
            'success': True,
            'edt_id': str(edt.id),
            'message': f'Emploi du temps généré avec {edt.creneaux.count()} cours'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erreur lors de la génération : {str(e)}'
        })


# ============================================================================
# VUES COURS
# ============================================================================
class CoursListView(LoginRequiredMixin, ListView):
    model = Cours
    template_name = 'courses/cours/list.html'
    context_object_name = 'cours'
    paginate_by = 20

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            classe__niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrage par enseignant si c'est un enseignant
        if self.request.user.role == 'ENSEIGNANT':
            queryset = queryset.filter(enseignant=self.request.user)

        # Filtres de recherche
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) |
                Q(description__icontains=search) |
                Q(classe__nom__icontains=search)
            )

        # Filtres avancés
        classe = self.request.GET.get('classe')
        if classe:
            queryset = queryset.filter(classe_id=classe)

        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        type_cours = self.request.GET.get('type_cours')
        if type_cours:
            queryset = queryset.filter(type_cours=type_cours)

        return queryset.select_related(
            'classe', 'matiere_module__matiere', 'enseignant', 'salle'
        ).order_by('-date_prevue', '-heure_debut_prevue')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtre_form'] = FiltreCoursForm(
            data=self.request.GET or None,
            user=self.request.user
        )
        return context

class CoursCreateView(LoginRequiredMixin, CreateView):
    model = Cours
    form_class = CoursForm
    template_name = 'courses/cours/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Cours créé avec succès !")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('courses:cours_detail', kwargs={'pk': self.object.pk})

class CoursUpdateView(LoginRequiredMixin, UpdateView):
    model = Cours
    form_class = CoursForm
    template_name = 'courses/cours/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Cours modifié avec succès !")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('courses:cours_detail', kwargs={'pk': self.object.pk})

class CoursDetailView(LoginRequiredMixin, DetailView):
    model = Cours
    template_name = 'courses/cours/detail.html'
    context_object_name = 'cours'

    def get_queryset(self):
        user = self.request.user
        queryset = Cours.objects.select_related(
            'matiere__module',
            'classe__niveau__filiere',
            'enseignant',
            'periode_academique',
            'salle'
        ).prefetch_related('ressources')

        if user.role == 'ADMIN':
            queryset = queryset.filter(classe__etablissement=user.etablissement)
        elif user.role == 'CHEF_DEPARTEMENT':
            queryset = queryset.filter(matiere__niveau__filiere__departement=user.departement)
        elif user.role == 'ENSEIGNANT':
            queryset = queryset.filter(enseignant=user)

        return queryset

class CoursDeleteView(LoginRequiredMixin, DeleteView):
    model = Cours

    # Contrôle d'accès
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas supprimer. Vérifiez vos permissions.")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_courses')
        else:
            return reverse_lazy('dashboard:department_head_courses')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Cours supprimé avec succès !")
        return super().delete(request, *args, **kwargs)

@login_required
def cours_start(request, pk):
    """Démarrer un cours"""
    cours = get_object_or_404(Cours, pk=pk)

    if request.user != cours.enseignant:
        return JsonResponse({'success': False, 'message': 'Permission refusée'})

    if request.method == 'POST':
        cours.statut = StatutCours.EN_COURS
        cours.date_effective = timezone.now().date()
        cours.heure_debut_effective = timezone.now().time()
        cours.save()

        return JsonResponse({'success': True, 'message': 'Cours démarré'})

    return JsonResponse({'success': False})

@login_required
def cours_end(request, pk):
    """Terminer un cours"""
    cours = get_object_or_404(Cours, pk=pk)

    if request.user != cours.enseignant:
        return JsonResponse({'success': False, 'message': 'Permission refusée'})

    if request.method == 'POST':
        cours.statut = StatutCours.TERMINE
        cours.heure_fin_effective = timezone.now().time()
        cours.save()

        return JsonResponse({'success': True, 'message': 'Cours terminé'})

    return JsonResponse({'success': False})

@login_required
def streaming_view(request, pk):
    """Vue pour afficher le streaming d'un cours"""
    cours = get_object_or_404(Cours, pk=pk)

    # Vérifier les permissions d'accès au streaming
    if not cours.cours_en_ligne or not cours.url_streaming:
        messages.error(request, "Le streaming n'est pas disponible pour ce cours.")
        return redirect('courses:cours_detail', pk=cours.pk)

    # Vérifier l'accès selon le rôle
    has_access = False
    user = request.user

    if user.role == 'ENSEIGNANT' and user == cours.enseignant:
        has_access = True
    elif user.role == 'APPRENANT':
        # Vérifier si l'étudiant est dans la classe
        if hasattr(user, 'profil_apprenant'):
            has_access = user.profil_apprenant.classe_actuelle == cours.classe
    elif user.role in ['ADMIN', 'CHEF_DEPARTEMENT']:
        has_access = True

    if not has_access:
        messages.error(request, "Vous n'avez pas accès au streaming de ce cours.")
        return redirect('courses:cours_detail', pk=cours.pk)

    return render(request, 'courses/streaming/view.html', {
        'cours': cours
    })


# ============================================================================
# VUES CAHIER DE TEXTE
# ============================================================================
@login_required
def cahier_texte_view(request, cours_id):
    """Afficher le cahier de texte d'un cours"""
    cours = get_object_or_404(Cours, pk=cours_id)

    # Vérifier les permissions
    user = request.user
    has_access = False

    if user.role == 'ENSEIGNANT' and user == cours.enseignant:
        has_access = True
    elif user.role == 'APPRENANT':
        if hasattr(user, 'profil_apprenant'):
            has_access = user.profil_apprenant.classe_actuelle == cours.classe
    elif user.role in ['ADMIN', 'CHEF_DEPARTEMENT']:
        has_access = True

    if not has_access:
        messages.error(request, "Vous n'avez pas accès à ce cahier de texte.")
        return redirect('courses:cours_list')

    # Récupérer ou créer le cahier de texte
    cahier = None
    if hasattr(cours, 'cahier_texte'):
        cahier = cours.cahier_texte

    return render(request, 'courses/cahier_texte/detail.html', {
        'cours': cours,
        'cahier': cahier
    })

@login_required
def cahier_texte_create_or_update(request, cours_id):
    """Créer ou mettre à jour le cahier de texte"""
    cours = get_object_or_404(Cours, pk=cours_id)

    # Seul l'enseignant peut créer/modifier
    if request.user != cours.enseignant:
        messages.error(request, "Seul l'enseignant peut modifier le cahier de texte.")
        return redirect('courses:cours_detail', pk=cours.pk)

    # Récupérer ou créer
    cahier = None
    if hasattr(cours, 'cahier_texte'):
        cahier = cours.cahier_texte

    if request.method == 'POST':
        travail_fait = request.POST.get('travail_fait')
        travail_donne = request.POST.get('travail_donne')
        date_travail_pour = request.POST.get('date_travail_pour')
        observations = request.POST.get('observations')

        if cahier:
            # Mettre à jour
            cahier.travail_fait = travail_fait
            cahier.travail_donne = travail_donne
            cahier.observations = observations
            if date_travail_pour:
                cahier.date_travail_pour = date_travail_pour
            cahier.save()
            messages.success(request, "Cahier de texte mis à jour avec succès.")
        else:
            # Créer
            cahier = CahierTexte.objects.create(
                cours=cours,
                travail_fait=travail_fait,
                travail_donne=travail_donne,
                observations=observations,
                date_travail_pour=date_travail_pour if date_travail_pour else None,
                rempli_par=request.user
            )
            messages.success(request, "Cahier de texte créé avec succès.")

        return redirect('courses:cahier_texte_view', cours_id=cours.pk)

    return render(request, 'courses/cahier_texte/form.html', {
        'cours': cours,
        'cahier': cahier
    })

@login_required
def cahier_texte_list(request):
    """Liste des cahiers de texte"""
    user = request.user

    if user.role == 'ENSEIGNANT':
        # Cours de l'enseignant ayant un cahier de texte
        cours_list = Cours.objects.filter(
            enseignant=user,
            cahier_texte__isnull=False
        ).select_related('cahier_texte', 'matiere', 'classe').order_by('-date_prevue')

    elif user.role == 'APPRENANT':
        if hasattr(user, 'profil_apprenant') and user.profil_apprenant.classe_actuelle:
            # Cours de la classe ayant un cahier de texte
            cours_list = Cours.objects.filter(
                classe=user.profil_apprenant.classe_actuelle,
                cahier_texte__isnull=False
            ).select_related('cahier_texte', 'matiere', 'enseignant').order_by('-date_prevue')
        else:
            cours_list = Cours.objects.none()

    elif user.role in ['ADMIN', 'CHEF_DEPARTEMENT']:
        # Tous les cours avec cahier de texte
        cours_list = Cours.objects.filter(
            cahier_texte__isnull=False
        ).select_related('cahier_texte', 'matiere', 'classe', 'enseignant').order_by('-date_prevue')
    else:
        cours_list = Cours.objects.none()

    return render(request, 'courses/cahier_texte/list.html', {
        'cours_list': cours_list
    })


# ============================================================================
# VUES PRESENCE
# ============================================================================
@login_required
def presence_bulk_create(request, cours_id):
    """Vue pour la prise de présence en lot"""
    cours = get_object_or_404(Cours, id=cours_id)

    # Vérifier les permissions
    if (request.user.role == 'ENSEIGNANT' and
            request.user != cours.enseignant and
            not request.user.is_superuser):
        raise Http404("Vous ne pouvez prendre les présences que pour vos propres cours.")

    if request.method == 'POST':
        form = PresenceBulkForm(request.POST, cours=cours)
        if form.is_valid():
            with transaction.atomic():
                etudiants = cours.classe.get_etudiants()
                for etudiant in etudiants:
                    statut = form.cleaned_data.get(f'statut_{etudiant.id}')
                    heure_arrivee = form.cleaned_data.get(f'heure_{etudiant.id}')
                    motif = form.cleaned_data.get(f'motif_{etudiant.id}')

                    # Créer ou mettre à jour la présence
                    presence, created = Presence.objects.get_or_create(
                        cours=cours,
                        etudiant=etudiant,
                        defaults={'statut': statut}
                    )

                    if not created:
                        presence.statut = statut

                    presence.heure_arrivee = heure_arrivee if statut == 'LATE' else None
                    presence.motif_absence = motif if statut in ['ABSENT', 'EXCUSED', 'JUSTIFIED'] else None
                    presence.save()

                # Marquer la présence comme prise
                cours.presence_prise = True
                cours.date_prise_presence = timezone.now()
                cours.save()

            messages.success(request, 'Présences enregistrées avec succès.')
            return redirect('courses:cours_detail', pk=cours.id)
    else:
        form = PresenceBulkForm(cours=cours)

    return render(request, 'courses/presence/bulk_form.html', {
        'form': form,
        'cours': cours,
        'etudiants': cours.classe.get_etudiants()
    })

class PresenceListView(LoginRequiredMixin, EtablissementFilterMixin, ListView):
    model = Presence
    template_name = 'courses/presence/list.html'
    context_object_name = 'presences'
    paginate_by = 50

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            cours__classe__niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrage par rôle
        if self.request.user.role == 'ENSEIGNANT':
            queryset = queryset.filter(cours__enseignant=self.request.user)
        elif self.request.user.role == 'ETUDIANT':
            queryset = queryset.filter(etudiant=self.request.user)

        # Filtres
        cours = self.request.GET.get('cours')
        if cours:
            queryset = queryset.filter(cours_id=cours)

        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        return queryset.select_related('cours', 'etudiant').order_by('-cours__date_prevue')


# ============================================================================
# VUES RESSOURCES
# ============================================================================
@login_required
def ressource_create(request, cours_id):
    """Créer une nouvelle ressource (enseignant)"""
    cours = get_object_or_404(Cours, pk=cours_id)

    if request.user != cours.enseignant and request.user.role not in ['ADMIN']:
        messages.error(request, "Vous n'êtes pas autorisé à ajouter des ressources.")
        return redirect('courses:cours_detail', pk=cours.pk)

    if request.method == 'POST':
        titre = request.POST.get('titre')
        description = request.POST.get('description')
        type_ressource = request.POST.get('type_ressource')
        fichier = request.FILES.get('fichier')
        url = request.POST.get('url')
        obligatoire = request.POST.get('obligatoire') == 'on'
        telechargeable = request.POST.get('telechargeable') == 'on'
        public = request.POST.get('public') == 'on'
        disponible_a_partir_de = request.POST.get('disponible_a_partir_de')
        disponible_jusqua = request.POST.get('disponible_jusqua')

        ressource = Ressource.objects.create(
            cours=cours,
            titre=titre,
            description=description,
            type_ressource=type_ressource,
            fichier=fichier,
            url=url,
            obligatoire=obligatoire,
            telechargeable=telechargeable,
            public=public,
            disponible_a_partir_de=disponible_a_partir_de if disponible_a_partir_de else None,
            disponible_jusqua=disponible_jusqua if disponible_jusqua else None
        )

        messages.success(request, "Ressource ajoutée avec succès.")
        return redirect('courses:cours_detail', pk=cours.pk)

    return render(request, 'courses/ressource/form.html', {
        'cours': cours
    })

@login_required
def ressource_update(request, pk):
    """Modifier une ressource"""
    ressource = get_object_or_404(Ressource, pk=pk)
    cours = ressource.cours

    if request.user != cours.enseignant and request.user.role not in ['ADMIN']:
        messages.error(request, "Vous n'êtes pas autorisé à modifier cette ressource.")
        return redirect('courses:cours_detail', pk=cours.pk)

    if request.method == 'POST':
        ressource.titre = request.POST.get('titre')
        ressource.description = request.POST.get('description')
        ressource.type_ressource = request.POST.get('type_ressource')

        if request.FILES.get('fichier'):
            ressource.fichier = request.FILES.get('fichier')

        ressource.url = request.POST.get('url')
        ressource.obligatoire = request.POST.get('obligatoire') == 'on'
        ressource.telechargeable = request.POST.get('telechargeable') == 'on'
        ressource.public = request.POST.get('public') == 'on'

        disponible_a_partir_de = request.POST.get('disponible_a_partir_de')
        disponible_jusqua = request.POST.get('disponible_jusqua')

        ressource.disponible_a_partir_de = disponible_a_partir_de if disponible_a_partir_de else None
        ressource.disponible_jusqua = disponible_jusqua if disponible_jusqua else None

        ressource.save()

        messages.success(request, "Ressource modifiée avec succès.")
        return redirect('courses:cours_detail', pk=cours.pk)

    return render(request, 'courses/ressource/form.html', {
        'cours': cours,
        'ressource': ressource
    })

@login_required
def ressource_delete(request, pk):
    """Supprimer une ressource"""
    ressource = get_object_or_404(Ressource, pk=pk)
    cours = ressource.cours

    if request.user != cours.enseignant and request.user.role not in ['ADMIN']:
        messages.error(request, "Vous n'êtes pas autorisé à supprimer cette ressource.")
        return redirect('courses:cours_detail', pk=cours.pk)

    if request.method == 'POST':
        ressource.delete()
        messages.success(request, "Ressource supprimée avec succès.")
        return redirect('courses:cours_detail', pk=cours.pk)

    return render(request, 'courses/ressource/confirm_delete.html', {
        'ressource': ressource,
        'cours': cours
    })

@login_required
def ressource_view(request, pk):
    """Afficher une ressource dans le lecteur intégré"""
    ressource = get_object_or_404(Ressource, pk=pk)
    cours = ressource.cours

    # Vérifier les permissions
    has_access = False
    user = request.user

    if user.role == 'ENSEIGNANT' and user == cours.enseignant:
        has_access = True
    elif user.role == 'APPRENANT':
        if hasattr(user, 'profil_apprenant'):
            has_access = user.profil_apprenant.classe_actuelle == cours.classe
    elif user.role in ['ADMIN', 'CHEF_DEPARTEMENT']:
        has_access = True

    # Vérifier si la ressource est publique
    if ressource.public:
        has_access = True

    # Vérifier les dates de disponibilité
    now = timezone.now()
    if ressource.disponible_a_partir_de and now < ressource.disponible_a_partir_de:
        has_access = False
        messages.warning(request,
                         f"Cette ressource sera disponible à partir du {ressource.disponible_a_partir_de.strftime('%d/%m/%Y à %H:%M')}")

    if ressource.disponible_jusqua and now > ressource.disponible_jusqua:
        has_access = False
        messages.warning(request, "Cette ressource n'est plus disponible.")

    if not has_access:
        messages.error(request, "Vous n'avez pas accès à cette ressource.")
        return redirect('courses:cours_detail', pk=cours.pk)

    return render(request, 'courses/ressource/view.html', {
        'ressource': ressource,
        'cours': cours
    })

@login_required
def ressource_download(request, pk):
    """Télécharger une ressource"""
    ressource = get_object_or_404(Ressource, pk=pk)
    cours = ressource.cours

    # Vérifier les permissions
    has_access = False
    user = request.user

    if user.role == 'ENSEIGNANT' and user == cours.enseignant:
        has_access = True
    elif user.role == 'APPRENANT':
        if hasattr(user, 'profil_apprenant'):
            has_access = user.profil_apprenant.classe_actuelle == cours.classe
    elif user.role in ['ADMIN', 'CHEF_DEPARTEMENT']:
        has_access = True

    if ressource.public:
        has_access = True

    if not has_access or not ressource.telechargeable:
        messages.error(request, "Vous ne pouvez pas télécharger cette ressource.")
        return redirect('courses:cours_detail', pk=cours.pk)

    # Incrémenter le compteur de téléchargements
    ressource.nombre_telechargements += 1
    ressource.save(update_fields=['nombre_telechargements'])

    # Télécharger le fichier
    if ressource.fichier:
        response = FileResponse(ressource.fichier.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{ressource.fichier.name}"'
        return response
    elif ressource.url:
        return redirect(ressource.url)
    else:
        messages.error(request, "Fichier introuvable.")
        return redirect('courses:cours_detail', pk=cours.pk)

@require_POST
@login_required
def ressource_increment_views(request, pk):
    """Incrémenter le compteur de vues d'une ressource"""
    ressource = get_object_or_404(Ressource, pk=pk)
    ressource.nombre_vues += 1
    ressource.save(update_fields=['nombre_vues'])
    return JsonResponse({'success': True, 'views': ressource.nombre_vues})

@login_required
def ressource_list(request, cours_id):
    """Liste des ressources d'un cours"""
    cours = get_object_or_404(Cours, pk=cours_id)

    # Vérifier les permissions
    user = request.user
    has_access = False

    if user.role == 'ENSEIGNANT' and user == cours.enseignant:
        has_access = True
        # L'enseignant voit toutes les ressources
        ressources = cours.ressources.all()
    elif user.role == 'APPRENANT':
        if hasattr(user, 'profil_apprenant') and user.profil_apprenant.classe_actuelle == cours.classe:
            has_access = True
            # Les étudiants ne voient que les ressources disponibles
            now = timezone.now()
            ressources = cours.ressources.filter(
                disponible_a_partir_de__lte=now,
                disponible_jusqua__gte=now
            ) | cours.ressources.filter(
                disponible_a_partir_de__isnull=True,
                disponible_jusqua__isnull=True
            )
    elif user.role in ['ADMIN', 'CHEF_DEPARTEMENT']:
        has_access = True
        ressources = cours.ressources.all()

    if not has_access:
        messages.error(request, "Accès refusé.")
        return redirect('courses:cours_list')

    return render(request, 'courses/ressource/list.html', {
        'cours': cours,
        'ressources': ressources
    })


# ============================================================================
# VUES AJAX ET API
# ============================================================================
@login_required
def ajax_get_modules_by_niveau(request):
    """Récupérer les modules d'un niveau donné"""
    niveau_id = request.GET.get('niveau_id')
    if not niveau_id:
        return JsonResponse({'modules': []})

    modules = Module.objects.filter(
        niveau_id=niveau_id,
        actif=True
    ).values('id', 'nom', 'code')

    return JsonResponse({'modules': list(modules)})

@login_required
def ajax_get_matieres_by_niveau(request):
    """Récupérer les matières d'un niveau donné"""
    niveau_id = request.GET.get('niveau_id')
    if not niveau_id:
        return JsonResponse({'matieres': []})

    matieres = Matiere.objects.filter(
        niveau_id=niveau_id,
        actif=True
    ).values('id', 'nom', 'code', 'couleur')

    return JsonResponse({'matieres': list(matieres)})

@login_required
def ajax_get_classes_by_niveau(request):
    """Récupérer les classes d'un niveau donné"""
    niveau_id = request.GET.get('niveau_id')
    if not niveau_id:
        return JsonResponse({'classes': []})

    classes = Classe.objects.filter(
        niveau_id=niveau_id,
        est_active=True
    ).values('id', 'nom', 'code')

    return JsonResponse({'classes': list(classes)})

@login_required
def ajax_get_salles_disponibles(request):
    """Vérifier les salles disponibles pour un créneau"""
    date = request.GET.get('date')
    heure_debut = request.GET.get('heure_debut')
    heure_fin = request.GET.get('heure_fin')

    if not all([date, heure_debut, heure_fin]):
        return JsonResponse({'salles': []})

    # Récupérer les salles occupées
    cours_conflits = Cours.objects.filter(
        date_prevue=date,
        heure_debut_prevue__lt=heure_fin,
        heure_fin_prevue__gt=heure_debut,
        salle__isnull=False
    ).values_list('salle_id', flat=True)

    # Salles disponibles
    user = request.user
    if user.role == 'ADMIN':
        salles = Salle.objects.filter(
            etablissement=user.etablissement,
            est_disponible=True
        ).exclude(id__in=cours_conflits)
    else:
        salles = Salle.objects.filter(
            est_disponible=True
        ).exclude(id__in=cours_conflits)

    salles_data = list(salles.values('id', 'nom', 'code', 'capacite'))

    return JsonResponse({'salles': salles_data})

@login_required
def ajax_check_conflit_cours(request):
    """Vérifier s'il y a des conflits pour un cours"""
    classe_id = request.GET.get('classe_id')
    enseignant_id = request.GET.get('enseignant_id')
    salle_id = request.GET.get('salle_id')
    date = request.GET.get('date')
    heure_debut = request.GET.get('heure_debut')
    heure_fin = request.GET.get('heure_fin')
    cours_id = request.GET.get('cours_id')  # Pour exclure le cours en cours de modification

    conflits = []

    # Vérifier conflit classe
    if classe_id:
        cours_classe = Cours.objects.filter(
            classe_id=classe_id,
            date_prevue=date,
            heure_debut_prevue__lt=heure_fin,
            heure_fin_prevue__gt=heure_debut
        )
        if cours_id:
            cours_classe = cours_classe.exclude(id=cours_id)

        if cours_classe.exists():
            conflits.append({
                'type': 'classe',
                'message': 'La classe a déjà un cours à ce créneau'
            })

    # Vérifier conflit enseignant
    if enseignant_id:
        cours_enseignant = Cours.objects.filter(
            enseignant_id=enseignant_id,
            date_prevue=date,
            heure_debut_prevue__lt=heure_fin,
            heure_fin_prevue__gt=heure_debut
        )
        if cours_id:
            cours_enseignant = cours_enseignant.exclude(id=cours_id)

        if cours_enseignant.exists():
            conflits.append({
                'type': 'enseignant',
                'message': "L'enseignant a déjà un cours à ce créneau"
            })

    # Vérifier conflit salle
    if salle_id:
        cours_salle = Cours.objects.filter(
            salle_id=salle_id,
            date_prevue=date,
            heure_debut_prevue__lt=heure_fin,
            heure_fin_prevue__gt=heure_debut
        )
        if cours_id:
            cours_salle = cours_salle.exclude(id=cours_id)

        if cours_salle.exists():
            conflits.append({
                'type': 'salle',
                'message': 'La salle est déjà occupée à ce créneau'
            })

    return JsonResponse({
        'has_conflit': len(conflits) > 0,
        'conflits': conflits
    })

@csrf_exempt
def ajax_get_classes(request):
    """Récupère les classes d'une filière via AJAX"""
    if request.method == 'GET':
        filiere_id = request.GET.get('filiere_id')
        if filiere_id:
            classes = request.user.etablissement.classes.filter(
                niveau__filiere_id=filiere_id
            ).select_related('niveau')

            data = [{
                'id': classe.id,
                'text': f"{classe.nom} ({classe.niveau.nom})"
            } for classe in classes]

            return JsonResponse({'results': data})

    return JsonResponse({'results': []})


# ============================================================================
# VUES D'EXPORT
# ============================================================================
@login_required
def export_modules(request):
    """Exporter la liste des modules en CSV"""
    import csv
    from django.utils.encoding import smart_str

    user = request.user

    # Récupérer les modules selon le rôle
    if user.role == 'ADMIN':
        modules = Module.objects.filter(
            niveau__filiere__etablissement=user.etablissement
        ).select_related('niveau__filiere__departement', 'coordinateur')
    elif user.role == 'CHEF_DEPARTEMENT':
        modules = Module.objects.filter(
            niveau__filiere__departement=user.departement
        ).select_related('niveau__filiere__departement', 'coordinateur')
    else:
        return HttpResponse("Permission refusée", status=403)

    # Créer la réponse CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="modules.csv"'
    response.write('\ufeff')  # BOM UTF-8

    writer = csv.writer(response)
    writer.writerow([
        'Code', 'Nom', 'Département', 'Filière', 'Niveau',
        'Coordinateur', 'Volume horaire', 'Crédits ECTS', 'Statut'
    ])

    for module in modules:
        writer.writerow([
            smart_str(module.code),
            smart_str(module.nom),
            smart_str(module.niveau.filiere.departement.nom if module.niveau.filiere.departement else ''),
            smart_str(module.niveau.filiere.nom),
            smart_str(module.niveau.nom),
            smart_str(module.coordinateur.get_full_name() if module.coordinateur else ''),
            module.volume_horaire_total,
            module.credits_ects,
            'Actif' if module.actif else 'Inactif'
        ])

    return response

@login_required
def export_matieres(request):
    """Exporter la liste des matières en CSV"""
    import csv
    from django.utils.encoding import smart_str

    user = request.user

    # Récupérer les matières selon le rôle
    if user.role == 'ADMIN':
        matieres = Matiere.objects.filter(
            niveau__filiere__etablissement=user.etablissement
        ).select_related('niveau__filiere', 'module', 'enseignant_responsable')
    elif user.role == 'CHEF_DEPARTEMENT':
        matieres = Matiere.objects.filter(
            niveau__filiere__departement=user.departement
        ).select_related('niveau__filiere', 'module', 'enseignant_responsable')
    else:
        return HttpResponse("Permission refusée", status=403)

    # Créer la réponse CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="matieres.csv"'
    response.write('\ufeff')  # BOM UTF-8

    writer = csv.writer(response)
    writer.writerow([
        'Code', 'Nom', 'Filière', 'Niveau', 'Module',
        'Enseignant responsable', 'CM', 'TD', 'TP', 'Volume total',
        'Coefficient', 'Crédits ECTS', 'Statut'
    ])

    for matiere in matieres:
        writer.writerow([
            smart_str(matiere.code),
            smart_str(matiere.nom),
            smart_str(matiere.niveau.filiere.nom),
            smart_str(matiere.niveau.nom),
            smart_str(matiere.module.nom if matiere.module else ''),
            smart_str(matiere.enseignant_responsable.get_full_name() if matiere.enseignant_responsable else ''),
            matiere.heures_cours_magistral,
            matiere.heures_travaux_diriges,
            matiere.heures_travaux_pratiques,
            matiere.volume_horaire_total,
            matiere.coefficient,
            matiere.credits_ects,
            'Active' if matiere.actif else 'Inactive'
        ])

    return response

@login_required
def export_cours(request):
    """Exporter la liste des cours en CSV"""
    import csv
    from django.utils.encoding import smart_str

    user = request.user

    # Récupérer les cours selon le rôle
    if user.role == 'ADMIN':
        cours_list = Cours.objects.filter(
            classe__etablissement=user.etablissement
        ).select_related('matiere', 'classe', 'enseignant', 'salle')
    elif user.role == 'CHEF_DEPARTEMENT':
        cours_list = Cours.objects.filter(
            matiere__niveau__filiere__departement=user.departement
        ).select_related('matiere', 'classe', 'enseignant', 'salle')
    elif user.role == 'ENSEIGNANT':
        cours_list = Cours.objects.filter(
            enseignant=user
        ).select_related('matiere', 'classe', 'salle')
    else:
        return HttpResponse("Permission refusée", status=403)

    # Créer la réponse CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="cours.csv"'
    response.write('\ufeff')  # BOM UTF-8

    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Heure début', 'Heure fin', 'Matière', 'Type',
        'Classe', 'Enseignant', 'Salle', 'Statut'
    ])

    for cours in cours_list:
        writer.writerow([
            cours.date_prevue.strftime('%d/%m/%Y'),
            cours.heure_debut_prevue.strftime('%H:%M'),
            cours.heure_fin_prevue.strftime('%H:%M'),
            smart_str(cours.matiere.nom),
            smart_str(cours.get_type_cours_display()),
            smart_str(cours.classe.nom),
            smart_str(cours.enseignant.get_full_name()),
            smart_str(cours.salle.code if cours.salle else ''),
            smart_str(cours.get_statut_display())
        ])

    return response
    kwargs

    def form_valid(self, form):
        messages.success(self.request, "Module créé avec succès !")
        return super().form_valid(form)
