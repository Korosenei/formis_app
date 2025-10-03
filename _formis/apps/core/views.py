# apps/public/views.py
from django.shortcuts import render
from django.views.generic import TemplateView, ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

# Import des modèles des établissements
from apps.establishments.models import Etablissement, TypeEtablissement, Localite


class HomeView(TemplateView):
    """Vue pour la page d'accueil publique"""
    template_name = 'public/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Récupérer les établissements actifs pour l'affichage public
        featured_establishments = Etablissement.objects.filter(
            actif=True
        ).select_related(
            'type_etablissement', 
            'localite'
        ).order_by('-created_at')[:6]  # Limiter à 6 établissements
        
        context.update({
            'featured_establishments': featured_establishments,
            'total_establishments': Etablissement.objects.filter(actif=True).count(),
            'establishment_types': TypeEtablissement.objects.filter(actif=True).count(),
        })
        
        return context

class EstablishmentListView(ListView):
    """Vue pour afficher la liste complète des établissements publics"""
    model = Etablissement
    template_name = 'public/establishment/establishment_list.html'
    context_object_name = 'establishments'
    paginate_by = 12
    
    def get_queryset(self):
        return Etablissement.objects.filter(
            actif=True
        ).select_related(
            'type_etablissement', 
            'localite'
        ).order_by('nom')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['establishment_types'] = TypeEtablissement.objects.filter(actif=True)
        context['localities'] = Localite.objects.all().order_by('nom')
        return context

class EstablishmentDetailView(DetailView):
    """Vue pour les détails d'un établissement"""
    model = Etablissement
    template_name = 'public/establishment/establishment_detail.html'
    context_object_name = 'establishment'
    
    def get_queryset(self):
        return Etablissement.objects.filter(actif=True).select_related(
            'type_etablissement', 
            'localite'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        establishment = self.get_object()
        
        # Ajouter les informations supplémentaires
        context.update({
            'campus_list': establishment.campuses.filter(est_actif=True) if hasattr(establishment, 'campuses') else [],
            'salles': establishment.salle_set.filter(est_active=True).order_by('nom') if hasattr(establishment, 'salle_set') else [],
            'related_establishments': Etablissement.objects.filter(
                actif=True,
                localite=establishment.localite
            ).exclude(pk=establishment.pk)[:3],
        })
        
        return context

class ApplicationFormView(TemplateView):
    """Vue pour le formulaire de candidature"""
    template_name = 'public/candidature.html'

class ContactView(TemplateView):
    """Vue pour la page de contact"""
    template_name = 'public/contact.html'

class AboutView(TemplateView):
    """Vue pour la page à propos"""
    template_name = 'public/about.html'
