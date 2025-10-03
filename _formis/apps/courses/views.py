# apps/courses/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from datetime import datetime, timedelta

from .models import (
    Module, Matiere, MatiereModule, Cours, CahierTexte,
    Ressource, Presence, EmploiDuTemps, CreneauHoraire
)
from .forms import (
    ModuleForm, MatiereForm, MatiereModuleForm, CoursForm, CoursUpdateForm,
    CahierTexteForm, RessourceForm, PresenceForm, PresenceBulkForm,
    EmploiDuTempsForm, CreneauHoraireForm, FiltreCoursForm,
    MatiereModuleFormSet, RessourceFormSet, CreneauHoraireFormSet
)


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


# ============== VUES MODULE ==============

class ModuleListView(LoginRequiredMixin, EtablissementFilterMixin, ListView):
    model = Module
    template_name = 'courses/module/list.html'
    context_object_name = 'modules'
    paginate_by = 20

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        return queryset.select_related('niveau__filiere__departement', 'coordinateur')

class ModuleDetailView(LoginRequiredMixin, EtablissementFilterMixin, DetailView):
    model = Module
    template_name = 'courses/module/detail.html'
    context_object_name = 'module'

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['matieres'] = self.object.matieremodule_set.all().select_related('matiere', 'enseignant')
        return context

class ModuleCreateView(LoginRequiredMixin, PermissionRequiredMixin, EtablissementFilterMixin, CreateView):
    model = Module
    form_class = ModuleForm
    template_name = 'courses/module/form.html'
    permission_required = 'courses.add_module'
    success_url = reverse_lazy('courses:module_list')

    def form_valid(self, form):
        messages.success(self.request, 'Module créé avec succès.')
        return super().form_valid(form)

class ModuleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, EtablissementFilterMixin, UpdateView):
    model = Module
    form_class = ModuleForm
    template_name = 'courses/module/form.html'
    permission_required = 'courses.change_module'

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def form_valid(self, form):
        messages.success(self.request, 'Module modifié avec succès.')
        return super().form_valid(form)

class ModuleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, EtablissementFilterMixin, DeleteView):
    model = Module
    template_name = 'courses/module/confirm_delete.html'
    permission_required = 'courses.delete_module'
    success_url = reverse_lazy('courses:module_list')

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Module supprimé avec succès.')
        return super().delete(request, *args, **kwargs)


# ============== VUES MATIERE ==============
class MatiereListView(LoginRequiredMixin, ListView):
    model = Matiere
    template_name = 'courses/matiere/list.html'
    context_object_name = 'matieres'
    paginate_by = 20

    def get_queryset(self):
        queryset = Matiere.objects.all()
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        return queryset.order_by('nom')

class MatiereDetailView(LoginRequiredMixin, DetailView):
    model = Matiere
    template_name = 'courses/matiere/detail.html'
    context_object_name = 'matiere'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modules'] = self.object.matieremodule_set.all().select_related('module__niveau')
        return context

class MatiereCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Matiere
    form_class = MatiereForm
    template_name = 'courses/matiere/form.html'
    permission_required = 'courses.add_matiere'
    success_url = reverse_lazy('courses:matiere_list')

    def form_valid(self, form):
        messages.success(self.request, 'Matière créée avec succès.')
        return super().form_valid(form)

class MatiereUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Matiere
    form_class = MatiereForm
    template_name = 'courses/matiere/form.html'
    permission_required = 'courses.change_matiere'

    def form_valid(self, form):
        messages.success(self.request, 'Matière modifiée avec succès.')
        return super().form_valid(form)


# ============== VUES COURS ==============
class CoursListView(LoginRequiredMixin, EtablissementFilterMixin, ListView):
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

class CoursDetailView(LoginRequiredMixin, EtablissementFilterMixin, DetailView):
    model = Cours
    template_name = 'courses/cours/detail.html'
    context_object_name = 'cours'

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            classe__niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ressources'] = self.object.ressources.all()
        context['presences'] = self.object.presences.all().select_related('etudiant')

        # Vérifier si l'utilisateur peut modifier ce cours
        context['can_edit'] = (
                self.request.user == self.object.enseignant or
                self.request.user.is_superuser or
                self.request.user.has_perm('courses.change_cours')
        )

        # Cahier de texte
        try:
            context['cahier_texte'] = self.object.cahier_texte
        except CahierTexte.DoesNotExist:
            context['cahier_texte'] = None

        return context

class CoursCreateView(LoginRequiredMixin, PermissionRequiredMixin, EtablissementFilterMixin, CreateView):
    model = Cours
    form_class = CoursForm
    template_name = 'courses/cours/form.html'
    permission_required = 'courses.add_cours'

    def get_initial(self):
        initial = super().get_initial()
        # Si c'est un enseignant, pré-remplir avec ses informations
        if self.request.user.role == 'ENSEIGNANT':
            initial['enseignant'] = self.request.user
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Cours créé avec succès.')
        return super().form_valid(form)

class CoursUpdateView(LoginRequiredMixin, PermissionRequiredMixin, EtablissementFilterMixin, UpdateView):
    model = Cours
    form_class = CoursUpdateForm
    template_name = 'courses/cours/form.html'
    permission_required = 'courses.change_cours'

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            classe__niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Vérifier que l'enseignant ne peut modifier que ses propres cours
        if (self.request.user.role == 'ENSEIGNANT' and
                self.request.user != obj.enseignant and
                not self.request.user.is_superuser):
            raise Http404("Vous ne pouvez modifier que vos propres cours.")
        return obj

    def form_valid(self, form):
        messages.success(self.request, 'Cours modifié avec succès.')
        return super().form_valid(form)


# ============== VUES CAHIER DE TEXTE ==============
@login_required
def cahier_texte_create_or_update(request, cours_id):
    """Vue pour créer ou modifier un cahier de texte"""
    cours = get_object_or_404(Cours, id=cours_id)

    # Vérifier les permissions
    if (request.user.role == 'ENSEIGNANT' and
            request.user != cours.enseignant and
            not request.user.is_superuser):
        raise Http404("Vous ne pouvez modifier que vos propres cours.")

    try:
        cahier_texte = cours.cahier_texte
    except CahierTexte.DoesNotExist:
        cahier_texte = None

    if request.method == 'POST':
        form = CahierTexteForm(
            request.POST,
            instance=cahier_texte,
            cours=cours,
            user=request.user
        )
        if form.is_valid():
            cahier_texte = form.save(commit=False)
            cahier_texte.cours = cours
            cahier_texte.rempli_par = request.user
            cahier_texte.save()
            messages.success(request, 'Cahier de texte enregistré avec succès.')
            return redirect('courses:cours_detail', pk=cours.id)
    else:
        form = CahierTexteForm(
            instance=cahier_texte,
            cours=cours,
            user=request.user
        )

    return render(request, 'courses/cahier_texte/form.html', {
        'form': form,
        'cours': cours,
        'cahier_texte': cahier_texte
    })

class CahierTexteListView(LoginRequiredMixin, EtablissementFilterMixin, ListView):
    model = CahierTexte
    template_name = 'courses/cahier_texte/list.html'
    context_object_name = 'cahiers'
    paginate_by = 20

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            cours__classe__niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrage par enseignant
        if self.request.user.role == 'ENSEIGNANT':
            queryset = queryset.filter(rempli_par=self.request.user)

        return queryset.select_related('cours__classe', 'cours__matiere_module__matiere', 'rempli_par')


# ============== VUES PRESENCE ==============
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


# ============== VUES RESSOURCE ==============
class RessourceCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Ressource
    form_class = RessourceForm
    template_name = 'courses/ressource/form.html'
    permission_required = 'courses.add_ressource'

    def get_initial(self):
        initial = super().get_initial()
        cours_id = self.kwargs.get('cours_id')
        if cours_id:
            initial['cours'] = cours_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cours_id = self.kwargs.get('cours_id')
        if cours_id:
            context['cours'] = get_object_or_404(Cours, id=cours_id)
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Ressource ajoutée avec succès.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('courses:cours_detail', kwargs={'pk': self.object.cours.pk})

class RessourceUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Ressource
    form_class = RessourceForm
    template_name = 'courses/ressource/form.html'
    permission_required = 'courses.change_ressource'

    def form_valid(self, form):
        messages.success(self.request, 'Ressource modifiée avec succès.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('courses:cours_detail', kwargs={'pk': self.object.cours.pk})


@login_required
def ressource_download(request, pk):
    """Vue pour télécharger une ressource"""
    ressource = get_object_or_404(Ressource, pk=pk)

    # Vérifier les permissions d'accès
    if not ressource.public:
        # Vérifier si l'utilisateur appartient à la classe du cours
        if request.user.role == 'APPRENANT':
            if not request.user.inscriptions.filter(classe=ressource.cours.classe).exists():
                raise Http404("Vous n'avez pas accès à cette ressource.")
        elif request.user.role == 'ENSEIGNANT':
            if request.user != ressource.cours.enseignant:
                raise Http404("Vous n'avez pas accès à cette ressource.")

    # Vérifier la disponibilité
    now = timezone.now()
    if ressource.disponible_a_partir_de and now < ressource.disponible_a_partir_de:
        messages.error(request, "Cette ressource n'est pas encore disponible.")
        return redirect('courses:cours_detail', pk=ressource.cours.pk)

    if ressource.disponible_jusqua and now > ressource.disponible_jusqua:
        messages.error(request, "Cette ressource n'est plus disponible.")
        return redirect('courses:cours_detail', pk=ressource.cours.pk)

    # Incrémenter les statistiques
    if ressource.telechargeable:
        ressource.nombre_telechargements += 1
    else:
        ressource.nombre_vues += 1
    ressource.save(update_fields=['nombre_telechargements', 'nombre_vues'])

    if ressource.fichier:
        response = HttpResponse(
            ressource.fichier.read(),
            content_type='application/octet-stream'
        )
        response['Content-Disposition'] = f'attachment; filename="{ressource.fichier.name}"'
        return response
    elif ressource.url:
        return redirect(ressource.url)
    else:
        raise Http404("Aucun fichier ou URL disponible.")


# ============== VUES EMPLOI DU TEMPS ==============
class EmploiDuTempsListView(LoginRequiredMixin, EtablissementFilterMixin, ListView):
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

class EmploiDuTempsDetailView(LoginRequiredMixin, EtablissementFilterMixin, DetailView):
    model = EmploiDuTemps
    template_name = 'courses/emploi_du_temps/detail.html'
    context_object_name = 'emploi_du_temps'

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            classe__niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Organiser les créneaux par jour de la semaine
        creneaux = self.object.creneaux.all().select_related(
            'matiere_module__matiere', 'enseignant', 'salle'
        ).order_by('jour', 'heure_debut')

        # Grouper par jour
        creneaux_par_jour = {}
        for creneau in creneaux:
            jour = creneau.jour
            if jour not in creneaux_par_jour:
                creneaux_par_jour[jour] = []
            creneaux_par_jour[jour].append(creneau)

        context['creneaux_par_jour'] = creneaux_par_jour
        context['jours_semaine'] = CreneauHoraire.JOURS_SEMAINE

        return context

class EmploiDuTempsCreateView(LoginRequiredMixin, PermissionRequiredMixin, EtablissementFilterMixin, CreateView):
    model = EmploiDuTemps
    form_class = EmploiDuTempsForm
    template_name = 'courses/emploi_du_temps/form.html'
    permission_required = 'courses.add_emploidutemps'

    def form_valid(self, form):
        form.instance.cree_par = self.request.user
        messages.success(self.request, 'Emploi du temps créé avec succès.')
        return super().form_valid(form)

class EmploiDuTempsUpdateView(LoginRequiredMixin, PermissionRequiredMixin, EtablissementFilterMixin, UpdateView):
    model = EmploiDuTemps
    form_class = EmploiDuTempsForm
    template_name = 'courses/emploi_du_temps/form.html'
    permission_required = 'courses.change_emploidutemps'

    def filter_by_etablissement(self, queryset):
        return queryset.filter(
            classe__niveau__filiere__departement__etablissement=self.request.user.etablissement
        )

    def form_valid(self, form):
        messages.success(self.request, 'Emploi du temps modifié avec succès.')
        return super().form_valid(form)


# ============== VUES CRENEAU HORAIRE ==============
class CreneauHoraireCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = CreneauHoraire
    form_class = CreneauHoraireForm
    template_name = 'courses/creneau/form.html'
    permission_required = 'courses.add_creneauhoraire'

    def get_initial(self):
        initial = super().get_initial()
        emploi_du_temps_id = self.kwargs.get('emploi_du_temps_id')
        if emploi_du_temps_id:
            initial['emploi_du_temps'] = emploi_du_temps_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        emploi_du_temps_id = self.kwargs.get('emploi_du_temps_id')
        if emploi_du_temps_id:
            context['emploi_du_temps'] = get_object_or_404(EmploiDuTemps, id=emploi_du_temps_id)
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Créneau horaire créé avec succès.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('courses:emploi_du_temps_detail', kwargs={'pk': self.object.emploi_du_temps.pk})


# ============== VUES AJAX ET API ==============

@csrf_exempt
def ajax_get_matiere_modules(request):
    """Récupère les matières-modules d'un niveau via AJAX"""
    if request.method == 'GET':
        niveau_id = request.GET.get('niveau_id')
        if niveau_id:
            matiere_modules = MatiereModule.objects.filter(
                module__niveau_id=niveau_id
            ).select_related('matiere', 'module')

            data = [{
                'id': mm.id,
                'text': f"{mm.matiere.nom} ({mm.module.nom})"
            } for mm in matiere_modules]

            return JsonResponse({'results': data})

    return JsonResponse({'results': []})

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

@login_required
def streaming_view(request, cours_id):
    """Vue pour afficher le streaming d'un cours"""
    cours = get_object_or_404(Cours, id=cours_id)

    # Vérifier les permissions d'accès au streaming
    if not cours.cours_en_ligne or not cours.streaming_actif:
        messages.error(request, "Le streaming n'est pas disponible pour ce cours.")
        return redirect('courses:cours_detail', pk=cours.pk)

    # Vérifier l'accès selon le rôle
    has_access = False
    if request.user.role == 'ENSEIGNANT' and request.user == cours.enseignant:
        has_access = True
    elif request.user.role == 'APPRENANT':
        # Vérifier si l'étudiant est inscrit à la classe
        has_access = request.user.inscriptions.filter(classe=cours.classe).exists()
    elif request.user.is_superuser:
        has_access = True

    if not has_access:
        messages.error(request, "Vous n'avez pas accès au streaming de ce cours.")
        return redirect('courses:cours_detail', pk=cours.pk)

    return render(request, 'courses/streaming/view.html', {
        'cours': cours
    })


# ============== DASHBOARD ET STATISTIQUES ==============

@login_required
def dashboard_enseignant(request):
    """Dashboard pour les enseignants"""
    if request.user.role != 'ENSEIGNANT':
        return redirect('accounts:dashboard')

    # Cours du jour
    aujourd_hui = timezone.now().date()
    cours_aujourd_hui = Cours.objects.filter(
        enseignant=request.user,
        date_prevue=aujourd_hui
    ).select_related('classe', 'matiere_module__matiere').order_by('heure_debut_prevue')

    # Cours de la semaine
    debut_semaine = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    fin_semaine = debut_semaine + timedelta(days=6)
    cours_semaine = Cours.objects.filter(
        enseignant=request.user,
        date_prevue__range=[debut_semaine, fin_semaine]
    ).count()

    # Présences à valider
    presences_a_valider = Presence.objects.filter(
        cours__enseignant=request.user,
        valide=False,
        statut__in=['EXCUSED', 'JUSTIFIED']
    ).count()

    # Cahiers de texte non remplis
    cours_sans_cahier = Cours.objects.filter(
        enseignant=request.user,
        date_prevue__lt=aujourd_hui,
        cahier_texte__isnull=True
    ).count()

    context = {
        'cours_aujourd_hui': cours_aujourd_hui,
        'cours_semaine': cours_semaine,
        'presences_a_valider': presences_a_valider,
        'cours_sans_cahier': cours_sans_cahier,
    }

    return render(request, 'courses/dashboard/enseignant.html', context)


@login_required
def dashboard_etudiant(request):
    """Dashboard pour les étudiants"""
    if request.user.role != 'APPRENANT':
        return redirect('accounts:dashboard')

    # Récupérer les classes de l'étudiant
    classes = request.user.inscriptions.all().values_list('classe', flat=True)

    # Cours du jour
    aujourd_hui = timezone.now().date()
    cours_aujourd_hui = Cours.objects.filter(
        classe__in=classes,
        date_prevue=aujourd_hui
    ).select_related('matiere_module__matiere', 'enseignant').order_by('heure_debut_prevue')

    # Emplois du temps actuels
    emplois_du_temps = EmploiDuTemps.objects.filter(
        classe__in=classes,
        actuel=True,
        publie=True
    )

    # Ressources récentes
    ressources_recentes = Ressource.objects.filter(
        cours__classe__in=classes,
        public=True
    ).order_by('-created_at')[:5]

    # Statistiques de présence de l'étudiant
    total_cours = Presence.objects.filter(etudiant=request.user).count()
    presences = Presence.objects.filter(etudiant=request.user, statut='PRESENT').count()
    taux_presence = (presences / total_cours * 100) if total_cours > 0 else 0

    context = {
        'cours_aujourd_hui': cours_aujourd_hui,
        'emplois_du_temps': emplois_du_temps,
        'ressources_recentes': ressources_recentes,
        'taux_presence': taux_presence,
        'total_cours': total_cours,
    }

    return render(request, 'courses/dashboard/etudiant.html', context)