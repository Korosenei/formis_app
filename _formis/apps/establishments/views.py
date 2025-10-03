# establishments/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Avg, Sum
from django.http import JsonResponse, HttpResponse
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timedelta

from .models import (
    Localite, TypeEtablissement, Etablissement, AnneeAcademique,
    BaremeNotation, NiveauNote, ParametresEtablissement, Salle,
    JourFerie, Campus
)
from .forms import (
    LocaliteForm, TypeEtablissementForm, EtablissementForm, AnneeAcademiqueForm,
    BaremeNotationForm, NiveauNoteForm, ParametresEtablissementForm, SalleForm,
    JourFerieForm, CampusForm, EtablissementSearchForm, SalleSearchForm,
    StatistiquesForm, NiveauNoteFormSet
)

""" from academic.models import Filiere, Niveau, Departement
from .models import Candidature, DocumentCandidature, SuiviCandidature """


# Dashboard principal
@login_required
def dashboard_view(request):
    """Vue principale du dashboard des établissements"""
    context = {
        'total_etablissements': Etablissement.objects.filter(actif=True).count(),
        'total_salles': Salle.objects.filter(est_active=True).count(),
        'total_campus': Campus.objects.filter(est_actif=True).count(),
        'etablissements_recents': Etablissement.objects.filter(actif=True).order_by('-created_at')[:5],
        'salles_disponibles': Salle.objects.filter(est_active=True, etat__in=['EXCELLENT', 'BON']).count(),
        'taux_occupation_moyen': Etablissement.objects.filter(actif=True).aggregate(
            avg_taux=Avg('etudiants_actuels')
        )['avg_taux'] or 0,
    }
    return render(request, 'establishments/dashboard.html', context)


# Vues pour les Établissements
class EtablissementListView(LoginRequiredMixin, ListView):
    model = Etablissement
    template_name = 'establishments/etablissement_list.html'
    context_object_name = 'etablissements'
    paginate_by = 20

    def get_queryset(self):
        queryset = Etablissement.objects.select_related('type_etablissement', 'localite')

        # Filtrage basé sur le formulaire de recherche
        form = EtablissementSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data['nom']:
                queryset = queryset.filter(nom__icontains=form.cleaned_data['nom'])
            if form.cleaned_data['type_etablissement']:
                queryset = queryset.filter(type_etablissement=form.cleaned_data['type_etablissement'])
            if form.cleaned_data['localite']:
                queryset = queryset.filter(localite=form.cleaned_data['localite'])
            if form.cleaned_data['actif'] is not None:
                queryset = queryset.filter(actif=form.cleaned_data['actif'])

        return queryset.order_by('nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = EtablissementSearchForm(self.request.GET)
        return context

class EtablissementDetailView(LoginRequiredMixin, DetailView):
    model = Etablissement
    template_name = 'establishments/etablissement_detail.html'
    context_object_name = 'etablissement'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.get_object()

        context.update({
            'salles': etablissement.salle_set.filter(est_active=True).order_by('batiment', 'nom'),
            'campus_list': etablissement.campuses.filter(est_actif=True).order_by('nom'),
            'annees_academiques': etablissement.anneeacademique_set.filter(est_active=True).order_by('-date_debut'),
            'bareme_defaut': etablissement.baremenotation_set.filter(est_defaut=True).first(),
            'jours_feries': etablissement.jourferie_set.filter(
                date_fin__gte=datetime.now().date()
            ).order_by('date_debut')[:5],
        })
        return context

class EtablissementCreateView(LoginRequiredMixin, CreateView):
    model = Etablissement
    form_class = EtablissementForm
    template_name = 'establishments/etablissement_form.html'
    success_url = reverse_lazy('establishments:etablissement_list')

    def form_valid(self, form):
        messages.success(self.request, 'Établissement créé avec succès.')
        return super().form_valid(form)

class EtablissementUpdateView(LoginRequiredMixin, UpdateView):
    model = Etablissement
    form_class = EtablissementForm
    template_name = 'establishments/etablissement_form.html'
    success_url = reverse_lazy('establishments:etablissement_list')

    def form_valid(self, form):
        messages.success(self.request, 'Établissement modifié avec succès.')
        return super().form_valid(form)

class EtablissementDeleteView(LoginRequiredMixin, DeleteView):
    model = Etablissement
    template_name = 'establishments/etablissement_confirm_delete.html'
    success_url = reverse_lazy('establishments:etablissement_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Établissement supprimé avec succès.')
        return super().delete(request, *args, **kwargs)


# Vues pour les Salles
class SalleListView(LoginRequiredMixin, ListView):
    model = Salle
    template_name = 'establishments/salle_list.html'
    context_object_name = 'salles'
    paginate_by = 20

    def get_queryset(self):
        queryset = Salle.objects.select_related('etablissement')

        # Filtrage
        form = SalleSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data['nom']:
                queryset = queryset.filter(nom__icontains=form.cleaned_data['nom'])
            if form.cleaned_data['type_salle']:
                queryset = queryset.filter(type_salle=form.cleaned_data['type_salle'])
            if form.cleaned_data['capacite_min']:
                queryset = queryset.filter(capacite__gte=form.cleaned_data['capacite_min'])
            if form.cleaned_data['batiment']:
                queryset = queryset.filter(batiment__icontains=form.cleaned_data['batiment'])

            # Filtrage par équipements
            equipements = form.cleaned_data.get('equipements', [])
            for equipement in equipements:
                queryset = queryset.filter(**{equipement: True})

        return queryset.order_by('etablissement__nom', 'batiment', 'nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = SalleSearchForm(self.request.GET)
        return context

class SalleDetailView(LoginRequiredMixin, DetailView):
    model = Salle
    template_name = 'establishments/salle_detail.html'
    context_object_name = 'salle'

class SalleCreateView(LoginRequiredMixin, CreateView):
    model = Salle
    form_class = SalleForm
    template_name = 'establishments/salle_form.html'
    success_url = reverse_lazy('establishments:salle_list')

    def form_valid(self, form):
        messages.success(self.request, 'Salle créée avec succès.')
        return super().form_valid(form)

class SalleUpdateView(LoginRequiredMixin, UpdateView):
    model = Salle
    form_class = SalleForm
    template_name = 'establishments/salle_form.html'
    success_url = reverse_lazy('establishments:salle_list')

    def form_valid(self, form):
        messages.success(self.request, 'Salle modifiée avec succès.')
        return super().form_valid(form)


# Vues pour les Campus
class CampusListView(LoginRequiredMixin, ListView):
    model = Campus
    template_name = 'establishments/campus_list.html'
    context_object_name = 'campus_list'
    paginate_by = 20

    def get_queryset(self):
        return Campus.objects.select_related('etablissement', 'localite', 'responsable_campus').order_by(
            'etablissement__nom', 'nom')


class CampusDetailView(LoginRequiredMixin, DetailView):
    model = Campus
    template_name = 'establishments/campus_detail.html'
    context_object_name = 'campus'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campus = self.get_object()
        context['salles'] = campus.etablissement.salle_set.filter(est_active=True).order_by('batiment', 'nom')
        return context


# Vues pour les Années Académiques
class AnneeAcademiqueListView(LoginRequiredMixin, ListView):
    model = AnneeAcademique
    template_name = 'establishments/annee_academique_list.html'
    context_object_name = 'annees'
    paginate_by = 20

    def get_queryset(self):
        return AnneeAcademique.objects.select_related('etablissement').order_by('-date_debut')


class AnneeAcademiqueCreateView(LoginRequiredMixin, CreateView):
    model = AnneeAcademique
    form_class = AnneeAcademiqueForm
    template_name = 'establishments/annee_academique_form.html'
    success_url = reverse_lazy('establishments:annee_academique_list')

    def form_valid(self, form):
        messages.success(self.request, 'Année académique créée avec succès.')
        return super().form_valid(form)


# Vues pour les Barèmes de Notation
class BaremeNotationListView(LoginRequiredMixin, ListView):
    model = BaremeNotation
    template_name = 'establishments/bareme_notation_list.html'
    context_object_name = 'baremes'
    paginate_by = 20

    def get_queryset(self):
        return BaremeNotation.objects.select_related('etablissement').prefetch_related('niveaux_notes').order_by(
            'etablissement__nom', 'nom')


@login_required
def bareme_notation_detail(request, pk):
    """Vue détaillée d'un barème avec ses niveaux"""
    bareme = get_object_or_404(BaremeNotation, pk=pk)
    niveaux = bareme.niveaux_notes.all().order_by('-note_minimale')

    context = {
        'bareme': bareme,
        'niveaux': niveaux,
    }
    return render(request, 'establishments/bareme_notation_detail.html', context)


@login_required
def bareme_notation_create(request):
    """Création d'un barème avec ses niveaux"""
    if request.method == 'POST':
        form = BaremeNotationForm(request.POST)
        formset = NiveauNoteFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            bareme = form.save()
            formset.instance = bareme
            formset.save()
            messages.success(request, 'Barème de notation créé avec succès.')
            return redirect('establishments:bareme_notation_list')
    else:
        form = BaremeNotationForm()
        formset = NiveauNoteFormSet()

    context = {
        'form': form,
        'formset': formset,
        'title': 'Créer un barème de notation'
    }
    return render(request, 'establishments/bareme_notation_form.html', context)


# Vues Ajax
@csrf_exempt
def ajax_salles_by_etablissement(request):
    """Retourne les salles d'un établissement via Ajax"""
    if request.method == 'POST':
        etablissement_id = request.POST.get('etablissement_id')
        salles = Salle.objects.filter(
            etablissement_id=etablissement_id,
            est_active=True
        ).values('id', 'nom', 'capacite', 'type_salle')

        return JsonResponse({
            'success': True,
            'salles': list(salles)
        })

    return JsonResponse({'success': False})


@csrf_exempt
def ajax_campus_by_etablissement(request):
    """Retourne les campus d'un établissement via Ajax"""
    if request.method == 'POST':
        etablissement_id = request.POST.get('etablissement_id')
        campus = Campus.objects.filter(
            etablissement_id=etablissement_id,
            est_actif=True
        ).values('id', 'nom', 'adresse')

        return JsonResponse({
            'success': True,
            'campus': list(campus)
        })

    return JsonResponse({'success': False})


# Vues de statistiques
@login_required
def statistiques_view(request):
    """Vue des statistiques des établissements"""
    form = StatistiquesForm(request.GET)

    # Statistiques générales
    stats = {
        'total_etablissements': Etablissement.objects.filter(actif=True).count(),
        'total_salles': Salle.objects.filter(est_active=True).count(),
        'total_campus': Campus.objects.filter(est_actif=True).count(),
        'capacite_totale': Etablissement.objects.filter(actif=True).aggregate(
            total=Sum('capacite_totale')
        )['total'] or 0,
        'etudiants_totaux': Etablissement.objects.filter(actif=True).aggregate(
            total=Sum('etudiants_actuels')
        )['total'] or 0,
    }

    # Statistiques par type d'établissement
    stats_par_type = TypeEtablissement.objects.annotate(
        nombre_etablissements=Count('etablissement', filter=Q(etablissement__actif=True))
    ).filter(nombre_etablissements__gt=0)

    # Répartition des salles par type
    stats_salles = {}
    for choix in Salle.TYPES_SALLE:
        stats_salles[choix[1]] = Salle.objects.filter(
            type_salle=choix[0],
            est_active=True
        ).count()

    # Top 10 des établissements par capacité
    top_etablissements = Etablissement.objects.filter(actif=True).order_by('-capacite_totale')[:10]

    context = {
        'form': form,
        'stats': stats,
        'stats_par_type': stats_par_type,
        'stats_salles': stats_salles,
        'top_etablissements': top_etablissements,
    }

    return render(request, 'establishments/statistiques.html', context)


# Vue pour l'export de données
@login_required
def export_etablissements(request):
    """Export des établissements en CSV"""
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="etablissements.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Nom', 'Sigle', 'Code', 'Type', 'Localité', 'Adresse',
        'Téléphone', 'Email', 'Capacité totale', 'Étudiants actuels',
        'Taux occupation', 'Actif', 'Public'
    ])

    etablissements = Etablissement.objects.select_related('type_etablissement', 'localite')
    for etab in etablissements:
        writer.writerow([
            etab.nom, etab.sigle, etab.code, etab.type_etablissement.nom,
            etab.localite.nom, etab.adresse, etab.telephone, etab.email,
            etab.capacite_totale, etab.etudiants_actuels,
            f"{etab.taux_occupation():.1f}%", etab.actif, etab.public
        ])

    return response


# Vues pour la gestion des jours fériés
class JourFerieListView(LoginRequiredMixin, ListView):
    model = JourFerie
    template_name = 'establishments/jour_ferie_list.html'
    context_object_name = 'jours_feries'
    paginate_by = 20

    def get_queryset(self):
        return JourFerie.objects.select_related('etablissement').order_by('-date_debut')


class JourFerieCreateView(LoginRequiredMixin, CreateView):
    model = JourFerie
    form_class = JourFerieForm
    template_name = 'establishments/jour_ferie_form.html'
    success_url = reverse_lazy('establishments:jour_ferie_list')

    def form_valid(self, form):
        messages.success(self.request, 'Jour férié/vacances créé avec succès.')
        return super().form_valid(form)


# Vue pour le calendrier des événements
@login_required
def calendrier_view(request):
    """Vue du calendrier des événements de l'établissement"""
    etablissement_id = request.GET.get('etablissement')
    jours_feries = JourFerie.objects.all()

    if etablissement_id:
        jours_feries = jours_feries.filter(etablissement_id=etablissement_id)

    # Formater les données pour le calendrier
    events = []
    for jour in jours_feries:
        events.append({
            'title': jour.nom,
            'start': jour.date_debut.isoformat(),
            'end': jour.date_fin.isoformat() if jour.date_fin != jour.date_debut else None,
            'color': jour.couleur,
            'description': jour.description or '',
            'type': jour.get_type_jour_ferie_display(),
        })

    context = {
        'events': json.dumps(events),
        'etablissements': Etablissement.objects.filter(actif=True),
        'etablissement_selectionne': etablissement_id,
    }

    return render(request, 'establishments/calendrier.html', context)


# Vue pour la carte des établissements
@login_required
def carte_etablissements_view(request):
    """Vue de la carte interactive des établissements"""
    etablissements = Etablissement.objects.filter(actif=True).select_related('localite', 'type_etablissement')

    # Préparer les données pour la carte
    markers = []
    for etab in etablissements:
        # Pour cette démo, on utilise des coordonnées fictives basées sur la localité
        # Dans un vrai projet, vous auriez des coordonnées GPS réelles
        markers.append({
            'nom': etab.nom,
            'type': etab.type_etablissement.nom,
            'localite': etab.localite.nom,
            'adresse': etab.adresse,
            'capacite': etab.capacite_totale,
            'etudiants': etab.etudiants_actuels,
            'taux_occupation': etab.taux_occupation(),
            'lat': 12.3714 + (hash(etab.nom) % 1000) / 10000,  # Exemple autour de Ouagadougou
            'lng': -1.5197 + (hash(etab.code) % 1000) / 10000,
            'url': f"/establishments/etablissement/{etab.pk}/",
        })

    context = {
        'markers': json.dumps(markers),
        'center_lat': 12.3714,
        'center_lng': -1.5197,
    }

    return render(request, 'establishments/carte.html', context)


# Vues pour les types d'établissements
class TypeEtablissementListView(LoginRequiredMixin, ListView):
    model = TypeEtablissement
    template_name = 'establishments/type_etablissement_list.html'
    context_object_name = 'types'
    paginate_by = 20

    def get_queryset(self):
        return TypeEtablissement.objects.annotate(
            nombre_etablissements=Count('etablissement', filter=Q(etablissement__actif=True))
        ).order_by('nom')


class TypeEtablissementCreateView(LoginRequiredMixin, CreateView):
    model = TypeEtablissement
    form_class = TypeEtablissementForm
    template_name = 'establishments/type_etablissement_form.html'
    success_url = reverse_lazy('establishments:type_etablissement_list')

    def form_valid(self, form):
        messages.success(self.request, 'Type d\'établissement créé avec succès.')
        return super().form_valid(form)


# Vues pour les localités
class LocaliteListView(LoginRequiredMixin, ListView):
    model = Localite
    template_name = 'establishments/localite_list.html'
    context_object_name = 'localites'
    paginate_by = 20

    def get_queryset(self):
        return Localite.objects.annotate(
            nombre_etablissements=Count('etablissement', filter=Q(etablissement__actif=True))
        ).order_by('nom')


class LocaliteCreateView(LoginRequiredMixin, CreateView):
    model = Localite
    form_class = LocaliteForm
    template_name = 'establishments/localite_form.html'
    success_url = reverse_lazy('establishments:localite_list')

    def form_valid(self, form):
        messages.success(self.request, 'Localité créée avec succès.')
        return super().form_valid(form)


# Vue pour la recherche globale
@login_required
def recherche_globale_view(request):
    """Vue de recherche globale dans tous les éléments"""
    query = request.GET.get('q', '')
    results = {}

    if query:
        # Recherche dans les établissements
        results['etablissements'] = Etablissement.objects.filter(
            Q(nom__icontains=query) |
            Q(sigle__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query)
        ).select_related('type_etablissement', 'localite')[:10]

        # Recherche dans les salles
        results['salles'] = Salle.objects.filter(
            Q(nom__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query)
        ).select_related('etablissement')[:10]

        # Recherche dans les campus
        results['campus'] = Campus.objects.filter(
            Q(nom__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query) |
            Q(adresse__icontains=query)
        ).select_related('etablissement')[:10]

        # Recherche dans les localités
        results['localites'] = Localite.objects.filter(
            Q(nom__icontains=query) |
            Q(region__icontains=query)
        )[:10]

    context = {
        'query': query,
        'results': results,
        'total_results': sum(len(r) for r in results.values()) if results else 0,
    }

    return render(request, 'establishments/recherche.html', context)


# Vues pour les paramètres d'établissement
@login_required
def parametres_etablissement_view(request, etablissement_id):
    """Vue pour gérer les paramètres d'un établissement"""
    etablissement = get_object_or_404(Etablissement, pk=etablissement_id)

    try:
        parametres = etablissement.parametres
    except ParametresEtablissement.DoesNotExist:
        parametres = ParametresEtablissement(etablissement=etablissement)

    if request.method == 'POST':
        form = ParametresEtablissementForm(request.POST, instance=parametres)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paramètres mis à jour avec succès.')
            return redirect('establishments:etablissement_detail', pk=etablissement_id)
    else:
        form = ParametresEtablissementForm(instance=parametres)

    context = {
        'form': form,
        'etablissement': etablissement,
        'parametres': parametres,
    }

    return render(request, 'establishments/parametres_etablissement.html', context)



# API Views pour les applications mobiles/externes
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def api_annees_academiques(request):
    """API pour récupérer les années académiques actives"""
    try:
        annees = AnneeAcademique.objects.filter(
            est_active=True
        ).order_by('-date_debut')
        
        data = [{
            'id': annee.id,
            'nom': annee.nom,
            'date_debut': annee.date_debut.isoformat() if annee.date_debut else None,
            'date_fin': annee.date_fin.isoformat() if annee.date_fin else None,
            'est_courante': annee.est_courante,
        } for annee in annees]
        
        return JsonResponse({
            'success': True,
            'count': len(data),
            'results': data
        })
        
    except Exception as e:
        logger.error(f"Erreur lors du chargement des années académiques: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur lors du chargement des données'
        }, status=500)


@require_http_methods(["GET"])
def api_etablissements_publics(request):
    """API publique pour lister les établissements"""
    etablissements = Etablissement.objects.filter(actif=True, public=True).select_related(
        'type_etablissement', 'localite'
    )

    data = []
    for etab in etablissements:
        data.append({
            'id': etab.id,
            'nom': etab.nom,
            'sigle': etab.sigle,
            'code': etab.code,
            'type': etab.type_etablissement.nom,
            'localite': etab.localite.nom,
            'adresse': etab.adresse,
            'telephone': etab.telephone,
            'email': etab.email,
            'site_web': etab.site_web,
            'capacite_totale': etab.capacite_totale,
            'logo': etab.logo.url if etab.logo else None,
            'description': etab.description,
        })

    return JsonResponse({
        'success': True,
        'count': len(data),
        'results': data
    })


@require_http_methods(["GET"])
def api_etablissement_detail(request, etablissement_id):
    """API pour les détails d'un établissement"""
    try:
        etab = Etablissement.objects.select_related('type_etablissement', 'localite').get(
            id=etablissement_id, actif=True, public=True
        )
    except Etablissement.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Établissement non trouvé'}, status=404)

    # Récupérer les informations liées
    campus = etab.campuses.filter(est_actif=True)
    salles = etab.salle_set.filter(est_active=True)

    data = {
        'id': etab.id,
        'nom': etab.nom,
        'sigle': etab.sigle,
        'code': etab.code,
        'type': {
            'nom': etab.type_etablissement.nom,
            'code': etab.type_etablissement.code,
            'structure_academique': etab.type_etablissement.structure_academique_defaut,
        },
        'localite': {
            'nom': etab.localite.nom,
            'region': etab.localite.region,
            'pays': etab.localite.pays,
        },
        'contact': {
            'adresse': etab.adresse,
            'telephone': etab.telephone,
            'email': etab.email,
            'site_web': etab.site_web,
        },
        'informations': {
            'nom_directeur': etab.nom_directeur,
            'date_creation': etab.date_creation.isoformat() if etab.date_creation else None,
            'description': etab.description,
            'mission': etab.mission,
            'vision': etab.vision,
        },
        'statistiques': {
            'capacite_totale': etab.capacite_totale,
            'etudiants_actuels': etab.etudiants_actuels,
            'taux_occupation': etab.taux_occupation(),
        },
        'images': {
            'logo': etab.logo.url if etab.logo else None,
            'couverture': etab.image_couverture.url if etab.image_couverture else None,
        },
        'campus': [
            {
                'nom': c.nom,
                'adresse': c.adresse,
                'services': c.get_liste_services(),
            } for c in campus
        ],
        'salles': {
            'total': salles.count(),
            'par_type': {
                type_salle[1]: salles.filter(type_salle=type_salle[0]).count()
                for type_salle in Salle.TYPES_SALLE
            }
        }
    }

    return JsonResponse({
        'success': True,
        'data': data
    })


@require_http_methods(["GET"])
def api_filieres_par_etablissement(request):
    """API pour récupérer les filières d'un établissement"""
    etablissement_id = request.GET.get('etablissement')
    
    if not etablissement_id:
        return JsonResponse({
            'success': False,
            'error': 'Paramètre etablissement requis'
        }, status=400)
    
    try:
        # Vérifier que l'établissement existe et est actif
        etablissement = get_object_or_404(
            Etablissement,
            id=etablissement_id,
            actif=True,
            public=True
        )
        
        # Récupérer les filières via les départements
        filieres = Filiere.objects.filter(
            departement__etablissement=etablissement,
            actif=True
        ).select_related('departement').order_by('nom')
        
        data = [{
            'id': filiere.id,
            'nom': filiere.nom,
            'code': filiere.code,
            'departement': filiere.departement.nom,
            'departement_id': filiere.departement.id,
            'description': filiere.description,
            'duree_formation': getattr(filiere, 'duree_formation', None),
        } for filiere in filieres]
        
        return JsonResponse({
            'success': True,
            'count': len(data),
            'results': data
        })
        
    except Etablissement.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Établissement non trouvé'
        }, status=404)
    except Exception as e:
        logger.error(f"Erreur lors du chargement des filières: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur lors du chargement des données'
        }, status=500)


@require_http_methods(["GET"])
def api_niveaux_par_filiere(request):
    """API pour récupérer les niveaux d'une filière"""
    filiere_id = request.GET.get('filiere')
    
    if not filiere_id:
        return JsonResponse({
            'success': False,
            'error': 'Paramètre filiere requis'
        }, status=400)
    
    try:
        # Vérifier que la filière existe et est active
        filiere = get_object_or_404(Filiere, id=filiere_id, actif=True)
        
        # Récupérer les niveaux de la filière
        niveaux = Niveau.objects.filter(
            filiere=filiere,
            actif=True
        ).order_by('ordre')
        
        data = [{
            'id': niveau.id,
            'nom': niveau.nom,
            'code': niveau.code,
            'ordre': niveau.ordre,
            'description': getattr(niveau, 'description', ''),
            'credits_requis': getattr(niveau, 'credits_requis', None),
            'duree_semestres': getattr(niveau, 'duree_semestres', None),
        } for niveau in niveaux]
        
        return JsonResponse({
            'success': True,
            'count': len(data),
            'results': data
        })
        
    except Filiere.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Filière non trouvée'
        }, status=404)
    except Exception as e:
        logger.error(f"Erreur lors du chargement des niveaux: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur lors du chargement des données'
        }, status=500)


@require_http_methods(["GET"])
def api_documents_requis(request):
    """API pour récupérer les documents requis selon la filière/niveau"""
    filiere_id = request.GET.get('filiere')
    niveau_id = request.GET.get('niveau')
    
    if not filiere_id:
        return JsonResponse({
            'success': False,
            'error': 'Paramètre filiere requis'
        }, status=400)
    
    try:
        filiere = get_object_or_404(Filiere, id=filiere_id, actif=True)
        niveau = None
        
        if niveau_id:
            niveau = get_object_or_404(Niveau, id=niveau_id, actif=True, filiere=filiere)
        
        # Documents de base requis pour toutes les candidatures
        documents_base = [
            {
                'type_document': 'photo_identite',
                'nom': 'Photo d\'identité',
                'est_obligatoire': True,
                'formats_autorises': 'jpg,jpeg,png',
                'taille_maximale': 2 * 1024 * 1024,  # 2MB
                'description': 'Photo d\'identité récente (format passeport), fond blanc'
            },
            {
                'type_document': 'acte_naissance',
                'nom': 'Acte de naissance',
                'est_obligatoire': True,
                'formats_autorises': 'pdf,jpg,jpeg,png',
                'taille_maximale': 5 * 1024 * 1024,  # 5MB
                'description': 'Copie légalisée de l\'acte de naissance (moins de 3 mois)'
            },
            {
                'type_document': 'diplome_precedent',
                'nom': 'Dernier diplôme obtenu',
                'est_obligatoire': True,
                'formats_autorises': 'pdf,jpg,jpeg,png',
                'taille_maximale': 5 * 1024 * 1024,  # 5MB
                'description': 'Copie légalisée du dernier diplôme obtenu avec relevé de notes'
            }
        ]
        
        # Documents spécifiques selon la filière
        documents_specifiques = []
        
        # Logique conditionnelle basée sur la filière
        filiere_nom_lower = filiere.nom.lower()
        
        # Filières techniques/informatique
        if any(terme in filiere_nom_lower for terme in ['informatique', 'génie', 'technique', 'ingénieur']):
            documents_specifiques.extend([
                {
                    'type_document': 'cv',
                    'nom': 'Curriculum Vitae',
                    'est_obligatoire': True,
                    'formats_autorises': 'pdf',
                    'taille_maximale': 3 * 1024 * 1024,
                    'description': 'CV détaillé mentionnant vos compétences techniques'
                },
                {
                    'type_document': 'portfolio',
                    'nom': 'Portfolio de projets',
                    'est_obligatoire': False,
                    'formats_autorises': 'pdf,zip',
                    'taille_maximale': 10 * 1024 * 1024,
                    'description': 'Portfolio de vos réalisations et projets (optionnel mais recommandé)'
                }
            ])
        
        # Filières médicales/santé
        elif any(terme in filiere_nom_lower for terme in ['médecine', 'santé', 'infirmier', 'pharmacie']):
            documents_specifiques.append({
                'type_document': 'certificat_medical',
                'nom': 'Certificat médical d\'aptitude',
                'est_obligatoire': True,
                'formats_autorises': 'pdf,jpg,jpeg,png',
                'taille_maximale': 3 * 1024 * 1024,
                'description': 'Certificat médical attestant de votre aptitude à suivre la formation'
            })
        
        # Filières artistiques/créatives
        elif any(terme in filiere_nom_lower for terme in ['art', 'design', 'communication', 'multimédia']):
            documents_specifiques.append({
                'type_document': 'portfolio',
                'nom': 'Portfolio créatif',
                'est_obligatoire': True,
                'formats_autorises': 'pdf,zip',
                'taille_maximale': 15 * 1024 * 1024,
                'description': 'Portfolio présentant vos créations et réalisations artistiques'
            })
        
        # Documents supplémentaires selon le niveau
        if niveau and niveau.ordre > 1:  # Pour les niveaux supérieurs
            documents_specifiques.append({
                'type_document': 'lettre_motivation',
                'nom': 'Lettre de motivation',
                'est_obligatoire': True,
                'formats_autorises': 'pdf',
                'taille_maximale': 2 * 1024 * 1024,
                'description': 'Lettre expliquant vos motivations pour cette formation'
            })
        
        # Combiner tous les documents
        tous_documents = documents_base + documents_specifiques
        
        return JsonResponse({
            'success': True,
            'count': len(tous_documents),
            'results': tous_documents,
            'filiere_info': {
                'nom': filiere.nom,
                'code': filiere.code,
                'departement': filiere.departement.nom
            },
            'niveau_info': {
                'nom': niveau.nom,
                'ordre': niveau.ordre
            } if niveau else None
        })
        
    except (Filiere.DoesNotExist, Niveau.DoesNotExist) as e:
        return JsonResponse({
            'success': False,
            'error': 'Filière ou niveau non trouvé'
        }, status=404)
    except Exception as e:
        logger.error(f"Erreur lors du chargement des documents requis: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur lors du chargement des données'
        }, status=500)


def candidature_create_view(request):
    """Vue pour afficher le formulaire de candidature"""
    context = {
        'title': 'Nouvelle candidature',
        'page_description': 'Formulaire de candidature pour rejoindre un établissement'
    }
    return render(request, 'public/candidature/create.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def candidature_submit_api(request):
    """API pour soumettre une nouvelle candidature"""
    try:
        with transaction.atomic():
            # Récupération des données du formulaire
            data = request.POST
            files = request.FILES
            
            # Validation des champs obligatoires
            champs_requis = [
                'nom', 'prenom', 'date_naissance', 'lieu_naissance',
                'genre', 'telephone', 'email', 'adresse',
                'etablissement', 'annee_academique', 'filiere', 'niveau'
            ]
            
            for champ in champs_requis:
                if not data.get(champ):
                    return JsonResponse({
                        'success': False,
                        'error': f'Le champ {champ} est obligatoire'
                    }, status=400)
            
            # Vérifier que l'établissement, filière et niveau existent
            try:
                etablissement = Etablissement.objects.get(
                    id=data['etablissement'],
                    actif=True,
                    public=True
                )
                annee_academique = AnneeAcademique.objects.get(
                    id=data['annee_academique'],
                    est_active=True
                )
                filiere = Filiere.objects.get(
                    id=data['filiere'],
                    actif=True
                )
                niveau = Niveau.objects.get(
                    id=data['niveau'],
                    actif=True,
                    filiere=filiere
                )
            except (Etablissement.DoesNotExist, AnneeAcademique.DoesNotExist, 
                    Filiere.DoesNotExist, Niveau.DoesNotExist):
                return JsonResponse({
                    'success': False,
                    'error': 'Données de formation invalides'
                }, status=400)
            
            # Vérifier si une candidature existe déjà pour cette combinaison
            candidature_existante = Candidature.objects.filter(
                email=data['email'],
                etablissement=etablissement,
                filiere=filiere,
                niveau=niveau,
                annee_academique=annee_academique
            ).exclude(statut__in=['REFUSEE', 'ANNULEE']).first()
            
            if candidature_existante:
                return JsonResponse({
                    'success': False,
                    'error': 'Une candidature existe déjà pour cette formation avec cette adresse email'
                }, status=400)
            
            # Créer la candidature
            candidature = Candidature.objects.create(
                # Informations personnelles
                nom=data['nom'].strip().upper(),
                prenom=data['prenom'].strip().title(),
                date_naissance=data['date_naissance'],
                lieu_naissance=data['lieu_naissance'].strip().title(),
                genre=data['genre'],
                telephone=data['telephone'].strip(),
                email=data['email'].strip().lower(),
                adresse=data['adresse'].strip(),
                
                # Informations familiales (optionnelles)
                nom_pere=data.get('nom_pere', '').strip().title() if data.get('nom_pere') else None,
                telephone_pere=data.get('telephone_pere', '').strip() if data.get('telephone_pere') else None,
                nom_mere=data.get('nom_mere', '').strip().title() if data.get('nom_mere') else None,
                telephone_mere=data.get('telephone_mere', '').strip() if data.get('telephone_mere') else None,
                nom_tuteur=data.get('nom_tuteur', '').strip().title() if data.get('nom_tuteur') else None,
                telephone_tuteur=data.get('telephone_tuteur', '').strip() if data.get('telephone_tuteur') else None,
                
                # Formation
                etablissement=etablissement,
                annee_academique=annee_academique,
                filiere=filiere,
                niveau=niveau,
                
                # Informations académiques antérieures
                ecole_precedente=data.get('ecole_precedente', '').strip() if data.get('ecole_precedente') else None,
                dernier_diplome=data.get('dernier_diplome', '').strip() if data.get('dernier_diplome') else None,
                annee_obtention=int(data['annee_obtention']) if data.get('annee_obtention') else None,
            )
            
            # Traitement des documents
            documents_ajoutes = 0
            for key, file in files.items():
                if key.startswith('document_'):
                    type_document = key.replace('document_', '')
                    
                    # Validation du fichier
                    if file.size > 10 * 1024 * 1024:  # 10MB max
                        continue  # Skip les fichiers trop volumineux
                    
                    # Créer le document
                    document = DocumentCandidature.objects.create(
                        candidature=candidature,
                        type_document=type_document,
                        nom_document=file.name,
                        fichier=file,
                        est_obligatoire=True  # Par défaut, à ajuster selon la logique
                    )
                    documents_ajoutes += 1
                    
                    # Ajouter au suivi
                    SuiviCandidature.objects.create(
                        candidature=candidature,
                        action='document_ajoute',
                        description=f'Document "{document.get_type_document_display()}" ajouté: {file.name}'
                    )
            
            # Créer l'entrée de suivi initial
            SuiviCandidature.objects.create(
                candidature=candidature,
                action='creation',
                description=f'Candidature créée pour {filiere.nom} - {niveau.nom} à {etablissement.nom}'
            )
            
            # Envoi d'email de confirmation (optionnel)
            try:
                send_mail(
                    subject=f'Confirmation de candidature - {candidature.numero_candidature}',
                    message=f'''
Bonjour {candidature.prenom} {candidature.nom},

Votre candidature a été soumise avec succès.

Numéro de candidature: {candidature.numero_candidature}
Formation: {filiere.nom} - {niveau.nom}
Établissement: {etablissement.nom}

Vous recevrez une réponse dans les plus brefs délais.

Cordialement,
L'équipe FORMIS
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[candidature.email],
                    fail_silently=True
                )
            except Exception as e:
                logger.warning(f"Erreur envoi email confirmation: {e}")
            
            return JsonResponse({
                'success': True,
                'message': 'Candidature soumise avec succès',
                'data': {
                    'id': candidature.id,
                    'numero_candidature': candidature.numero_candidature,
                    'statut': candidature.get_statut_display(),
                    'documents_ajoutes': documents_ajoutes
                }
            })
            
    except Exception as e:
        logger.error(f"Erreur lors de la soumission de candidature: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur lors de la soumission de votre candidature'
        }, status=500)


def candidature_detail_view(request, candidature_id):
    """Vue pour afficher les détails d'une candidature"""
    candidature = get_object_or_404(Candidature, id=candidature_id)
    
    context = {
        'candidature': candidature,
        'documents': candidature.documents.all(),
        'historique': candidature.historique.all()[:10],  # 10 dernières actions
        'title': f'Candidature {candidature.numero_candidature}'
    }
    
    return render(request, 'enrollment/candidature_detail.html', context)


# Vue de statistiques pour le tableau de bord admin
@login_required
def candidatures_stats_api(request):
    """API pour les statistiques des candidatures"""
    from django.db.models import Count, Q
    from django.utils import timezone
    
    # Statistiques générales
    stats = {
        'totaux': {
            'total_candidatures': Candidature.objects.count(),
            'en_attente': Candidature.objects.filter(statut='EN_ATTENTE').count(),
            'en_cours': Candidature.objects.filter(statut='EN_COURS').count(),
            'acceptees': Candidature.objects.filter(statut='ACCEPTEE').count(),
            'refusees': Candidature.objects.filter(statut='REFUSEE').count(),
        },
        'ce_mois': {},
        'par_etablissement': [],
        'par_filiere': []
    }
    
    # Statistiques du mois en cours
    debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    candidatures_mois = Candidature.objects.filter(date_creation__gte=debut_mois)
    
    stats['ce_mois'] = {
        'total': candidatures_mois.count(),
        'en_attente': candidatures_mois.filter(statut='EN_ATTENTE').count(),
        'acceptees': candidatures_mois.filter(statut='ACCEPTEE').count(),
    }
    
    # Par établissement
    etablissements_stats = Etablissement.objects.annotate(
        nb_candidatures=Count('candidature')
    ).filter(nb_candidatures__gt=0).order_by('-nb_candidatures')[:10]
    
    for etab in etablissements_stats:
        stats['par_etablissement'].append({
            'nom': etab.nom,
            'total': etab.nb_candidatures,
            'en_attente': etab.candidature_set.filter(statut='EN_ATTENTE').count(),
        })
    
    return JsonResponse({
        'success': True,
        'data': stats
    })

# Vues utilitaires
@login_required
def mise_a_jour_etudiants_view(request):
    """Vue pour mettre à jour le nombre d'étudiants de tous les établissements"""
    if request.method == 'POST':
        etablissements = Etablissement.objects.filter(actif=True)
        count = 0

        for etablissement in etablissements:
            etablissement.mise_a_jour_nombre_etudiants()
            count += 1

        messages.success(request, f'Nombre d\'étudiants mis à jour pour {count} établissements.')
        return redirect('establishments:dashboard')

    return render(request, 'establishments/mise_a_jour_etudiants.html')


@login_required
def rapport_etablissement_pdf(request, etablissement_id):
    """Génère un rapport PDF pour un établissement"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO

    etablissement = get_object_or_404(Etablissement, pk=etablissement_id)

    # Créer le PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Titre
    title = Paragraph(f"Rapport - {etablissement.nom}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 20))

    # Informations générales
    info_data = [
        ['Nom', etablissement.nom],
        ['Sigle', etablissement.sigle or 'N/A'],
        ['Code', etablissement.code],
        ['Type', etablissement.type_etablissement.nom],
        ['Localité', etablissement.localite.nom],
        ['Capacité totale', str(etablissement.capacite_totale)],
        ['Étudiants actuels', str(etablissement.etudiants_actuels)],
        ['Taux d\'occupation', f"{etablissement.taux_occupation():.1f}%"],
    ]

    info_table = Table(info_data)
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(info_table)
    story.append(Spacer(1, 20))

    # Statistiques des salles
    salles = etablissement.salle_set.filter(est_active=True)
    if salles.exists():
        story.append(Paragraph("Statistiques des Salles", styles['Heading2']))

        salles_data = [['Type de salle', 'Nombre', 'Capacité totale']]
        for type_salle in Salle.TYPES_SALLE:
            salles_type = salles.filter(type_salle=type_salle[0])
            if salles_type.exists():
                capacite_totale = sum(s.capacite for s in salles_type)
                salles_data.append([type_salle[1], str(salles_type.count()), str(capacite_totale)])

        if len(salles_data) > 1:
            salles_table = Table(salles_data)
            salles_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(salles_table)

    # Construire le PDF
    doc.build(story)

    # Retourner la réponse
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_{etablissement.code}.pdf"'

    return response
