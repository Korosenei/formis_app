# apps/core/dashboard_views.py
from django.db import models
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView, ListView, DetailView, UpdateView, FormView
from django.db.models.functions import ExtractMonth
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
import json
import csv
from decimal import Decimal
from decimal import Decimal
import datetime
from io import StringIO
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from datetime import date, datetime
from django.db.models import Avg, Sum, F, IntegerField, Count, Q
from django.utils.timesince import timesince

from apps.core.mixins import RoleRequiredMixin, EstablishmentFilterMixin
from apps.accounts.models import Utilisateur, ProfilApprenant, ProfilEnseignant
from apps.establishments.models import Etablissement, AnneeAcademique, Salle
from apps.academic.models import Departement, Filiere, Niveau, Classe, PeriodeAcademique
from apps.courses.models import Module, Matiere, StatutCours, TypeCours, Cours, Presence, Ressource, CahierTexte, EmploiDuTemps
from apps.enrollment.models import Candidature, Inscription
from apps.evaluations.models import Evaluation, Note
from apps.payments.models import Paiement, PlanPaiement, InscriptionPaiement
from apps.accounting.models import CompteComptable, Depense, Facture, BudgetPrevisionnel, EcritureComptable, ExerciceComptable
from apps.accounting.utils import RapportComptablePDF, ComptabiliteUtils
from apps.documents.models import DemandeDocument

import logging

logger = logging.getLogger(__name__)


class DashboardRedirectView(LoginRequiredMixin, TemplateView):
    """Redirige vers le bon dashboard selon le rôle"""

    def get(self, request, *args, **kwargs):
        user = request.user

        if user.role == 'SUPERADMIN':
            return redirect('dashboard:superadmin')
        elif user.role == 'ADMIN':
            return redirect('dashboard:admin')
        elif user.role == 'COMPTABLE':
            return redirect('dashboard:comptable')
        elif user.role == 'CHEF_DEPARTEMENT':
            return redirect('dashboard:department_head')
        elif user.role == 'ENSEIGNANT':
            return redirect('dashboard:teacher')
        elif user.role == 'APPRENANT':
            return redirect('dashboard:student')
        else:
            messages.error(request, "Rôle utilisateur non reconnu")
            return redirect('accounts:login')


# ================================
# VUES ADMIN
# ================================
class AdminDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord principal de l'administrateur"""
    template_name = 'dashboard/admin/index.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        etablissement = user.etablissement

        # Statistiques générales
        context.update({
            'total_apprenants': self.get_total_apprenants(etablissement),
            'total_enseignants': self.get_total_enseignants(etablissement),
            'total_departements': self.get_total_departements(etablissement),
            'total_classes': self.get_total_classes(etablissement),
            'candidatures_en_attente': self.get_candidatures_en_attente(etablissement),
            'paiements_en_attente': self.get_paiements_en_attente(etablissement),

            # Données pour graphiques
            'stats_inscriptions_mois': self.get_stats_inscriptions_par_mois(etablissement),
            'stats_paiements_mois': self.get_stats_paiements_par_mois(etablissement),
            'repartition_apprenants_departement': self.get_repartition_apprenants_departement(etablissement),

            # Activités récentes
            'candidatures_recentes': self.get_candidatures_recentes(etablissement),
            'paiements_recents': self.get_paiements_recents(etablissement),
            'notifications_count': self.get_notifications_count(user),
        })

        return context

    def get_total_apprenants(self, etablissement):
        return Utilisateur.objects.filter(
            etablissement=etablissement,
            role='APPRENANT',
            est_actif=True
        ).count()

    def get_total_enseignants(self, etablissement):
        return Utilisateur.objects.filter(
            etablissement=etablissement,
            role='ENSEIGNANT',
            est_actif=True
        ).count()

    def get_total_departements(self, etablissement):
        return Departement.objects.filter(etablissement=etablissement).count()

    def get_total_classes(self, etablissement):
        return Classe.objects.filter(
            niveau__filiere__departement__etablissement=etablissement
        ).count()

    def get_candidatures_en_attente(self, etablissement):
        return Candidature.objects.filter(
            niveau__filiere__departement__etablissement=etablissement,
            statut='EN_ATTENTE'
        ).count()

    def get_paiements_en_attente(self, etablissement):
        return Paiement.objects.filter(
            inscription_paiement__inscription__apprenant__etablissement=etablissement,
            statut='EN_ATTENTE'
        ).count()

    def get_stats_inscriptions_par_mois(self, etablissement):
        # Données pour graphique des inscriptions sur 12 mois
        aujourd_hui = timezone.now()
        debut_annee = aujourd_hui.replace(month=1, day=1)

        inscriptions = Inscription.objects.filter(
            apprenant__etablissement=etablissement,
            date_inscription__gte=debut_annee
        ).extra(select={'month': 'EXTRACT(month FROM date_inscription)'}).values('month').annotate(count=Count('id'))

        stats = [0] * 12
        for item in inscriptions:
            stats[int(item['month']) - 1] = item['count']

        return stats

    def get_stats_paiements_par_mois(self, etablissement):
        aujourd_hui = timezone.now()
        debut_annee = aujourd_hui.replace(month=1, day=1)

        paiements = Paiement.objects.filter(
            inscription_paiement__inscription__apprenant__etablissement=etablissement,
            date_paiement__gte=debut_annee,
            statut='CONFIRME'
        ).extra(select={'month': 'EXTRACT(month FROM date_paiement)'}).values('month').annotate(total=Sum('montant'))

        stats = [0] * 12
        for item in paiements:
            stats[int(item['month']) - 1] = float(item['total'] or 0)

        return stats

    def get_repartition_apprenants_departement(self, etablissement):
        # Répartition des apprenants par département
        return list(
            Departement.objects.filter(etablissement=etablissement)
            .annotate(nombre_apprenants=Count('utilisateurs', filter=Q(utilisateurs__role='APPRENANT')))
            .values('nom', 'nombre_apprenants')
        )

    def get_candidatures_recentes(self, etablissement):
        return Candidature.objects.filter(
            niveau__filiere__departement__etablissement=etablissement
        ).select_related('niveau__filiere', 'inscription__apprenant').order_by('-date_soumission')[:5]

    def get_paiements_recents(self, etablissement):
        return Paiement.objects.filter(
            inscription_paiement__inscription__apprenant__etablissement=etablissement
        ).select_related(
            'inscription_paiement__inscription__apprenant'
        ).order_by('-date_paiement')[:5]

    def get_notifications_count(self, user):
        # Nombre de notifications non lues
        return getattr(user, 'unread_notifications_count', 0)

class AdminUsersView(LoginRequiredMixin, ListView):
    """Gestion des utilisateurs par l'admin"""
    template_name = 'dashboard/admin/users.html'
    context_object_name = 'users'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            # Limiter entre 10 et 100
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = Utilisateur.objects.filter(etablissement=etablissement).select_related('departement')

        # Filtres
        role = self.request.GET.get('role')
        if role:
            queryset = queryset.filter(role=role)

        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(departement_id=departement)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(matricule__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset.order_by('-date_creation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'departements': Departement.objects.filter(etablissement=etablissement),
            'roles': Utilisateur.ROLES_UTILISATEUR,
            'current_role': self.request.GET.get('role', ''),
            'current_departement': self.request.GET.get('departement', ''),
            'search_query': self.request.GET.get('search', ''),
            'current_filters': {
                'role': self.request.GET.get('role', ''),
                'departement': self.request.GET.get('departement', ''),
                'search': self.request.GET.get('search', ''),
            },
        })

        return context

class AdminComptablesView(LoginRequiredMixin, ListView):
    """Gestion des comptables par l'admin"""
    template_name = 'dashboard/admin/comptables.html'
    context_object_name = 'comptables'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        """Permet de modifier dynamiquement le nombre d'éléments par page"""
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            # Limiter entre 10 et 100
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = Utilisateur.objects.filter(
            etablissement=etablissement,
            role='COMPTABLE'
        ).select_related('profil_comptable')

        # Filtres
        statut = self.request.GET.get('statut')
        if statut == 'actif':
            queryset = queryset.filter(est_actif=True)
        elif statut == 'inactif':
            queryset = queryset.filter(est_actif=False)

        specialisation = self.request.GET.get('specialisation')
        if specialisation:
            queryset = queryset.filter(profil_comptable__specialisation__icontains=specialisation)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(matricule__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset.order_by('-date_creation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        # Statistiques
        total_comptables = Utilisateur.objects.filter(
            etablissement=etablissement,
            role='COMPTABLE'
        ).count()

        comptables_actifs = Utilisateur.objects.filter(
            etablissement=etablissement,
            role='COMPTABLE',
            est_actif=True
        ).count()

        context.update({
            'total_comptables': total_comptables,
            'comptables_actifs': comptables_actifs,
            'comptables_inactifs': total_comptables - comptables_actifs,
            'current_filters': {
                'statut': self.request.GET.get('statut', ''),
                'specialisation': self.request.GET.get('specialisation', ''),
                'search': self.request.GET.get('search', ''),
            },
        })

        return context

class AdminDepartmentHeadsView(LoginRequiredMixin, ListView):
    """Liste des chefs de département"""
    template_name = 'dashboard/admin/department_heads.html'
    context_object_name = 'chefs_departement'  # Changé de 'department_heads'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etablissement = self.request.user.etablissement

        # Récupérer tous les départements avec leurs chefs
        departements = Departement.objects.filter(
            etablissement=etablissement,
            est_actif=True
        ).select_related('chef').prefetch_related(
            'utilisateurs',
            'filieres'
        ).order_by('nom')

        return departements

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        # Départements sans chef
        depts_sans_chef = Departement.objects.filter(
            etablissement=etablissement,
            est_actif=True,
            chef__isnull=True
        ).count()

        # Total des départements
        total_depts = Departement.objects.filter(
            etablissement=etablissement,
            est_actif=True
        ).count()

        context.update({
            'departements_sans_chef': depts_sans_chef,
            'total_departements': total_depts,
            'can_nominate': depts_sans_chef > 0
        })

        return context

class AdminTeachersView(LoginRequiredMixin, ListView):
    """Gestion des enseignants"""
    template_name = 'dashboard/admin/teachers.html'
    context_object_name = 'teachers'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        """Permet de modifier dynamiquement le nombre d'éléments par page"""
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = Utilisateur.objects.filter(
            etablissement=etablissement,
            role='ENSEIGNANT'
        ).select_related('departement', 'profil_enseignant')

        # Filtres
        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(departement_id=departement)

        specialisation = self.request.GET.get('specialisation')
        if specialisation:
            queryset = queryset.filter(profil_enseignant__specialisation__icontains=specialisation)

        est_permanent = self.request.GET.get('est_permanent')
        if est_permanent:
            queryset = queryset.filter(profil_enseignant__est_permanent=est_permanent == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(matricule__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset.order_by('-date_creation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'departements': Departement.objects.filter(etablissement=etablissement),
            'current_filters': {
                'departement': self.request.GET.get('departement', ''),
                'specialisation': self.request.GET.get('specialisation', ''),
                'est_permanent': self.request.GET.get('est_permanent', ''),
                'search': self.request.GET.get('search', ''),
            },
        })

        return context

class AdminStudentsView(LoginRequiredMixin, ListView):
    """Gestion des étudiants"""
    template_name = 'dashboard/admin/students.html'
    context_object_name = 'students'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        """Permet de modifier dynamiquement le nombre d'éléments par page"""
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = Utilisateur.objects.filter(
            etablissement=etablissement,
            role='APPRENANT'
        ).select_related('departement')

        # Filtres
        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(departement_id=departement)

        classe = self.request.GET.get('classe')
        if classe:
            queryset = queryset.filter(profil_apprenant__classe_actuelle_id=classe)

        statut_paiement = self.request.GET.get('statut_paiement')
        if statut_paiement:
            queryset = queryset.filter(profil_apprenant__statut_paiement=statut_paiement)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(matricule__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset.order_by('-date_creation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'departements': Departement.objects.filter(etablissement=etablissement),
            'classes': Classe.objects.filter(
                niveau__filiere__departement__etablissement=etablissement
            ),
            'statuts_paiement': ProfilApprenant._meta.get_field('statut_paiement').choices,
            'current_filters': {
                'departement': self.request.GET.get('departement', ''),
                'classe': self.request.GET.get('classe', ''),
                'statut_paiement': self.request.GET.get('statut_paiement', ''),
                'search': self.request.GET.get('search', ''),
            },
        })

        return context

class AdminDepartementsView(LoginRequiredMixin, ListView):
    template_name = 'dashboard/admin/departments.html'
    context_object_name = 'departements'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = Departement.objects.filter(
            etablissement=etablissement
        ).select_related('chef').annotate(
            nombre_filieres=Count(
                'filieres',
                filter=Q(filieres__est_active=True),
                distinct=True
            ),
            nombre_enseignants=Count(
                'utilisateurs',
                filter=Q(utilisateurs__role='ENSEIGNANT', utilisateurs__est_actif=True),
                distinct=True
            )
        )

        # Filtres
        est_actif = self.request.GET.get('est_actif')
        if est_actif:
            queryset = queryset.filter(est_actif=est_actif == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search) |
                Q(chef__prenom__icontains=search) |
                Q(chef__nom__icontains=search)
            )

        return queryset.order_by('nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Calcul du nombre de départements actifs
        departements_actifs = self.get_queryset().filter(est_actif=True).count()

        context.update({
            'current_filters': {
                'est_actif': self.request.GET.get('est_actif', ''),
                'search': self.request.GET.get('search', ''),
            },
            'departements_actifs_count': departements_actifs,
        })
        return context

class AdminFilieresView(LoginRequiredMixin, ListView):
    """Gestion des filières par l'admin"""
    template_name = 'dashboard/admin/filieres.html'
    context_object_name = 'filieres'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            # Limiter entre 10 et 100
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = Filiere.objects.filter(
            etablissement=etablissement
        ).select_related('departement').annotate(
            nombre_niveaux=Count('niveaux', filter=Q(niveaux__est_actif=True)),
            nombre_etudiants=Count('niveaux__classes__inscriptions__apprenant', distinct=True)
        )

        # Filtres
        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(departement_id=departement)

        type_filiere = self.request.GET.get('type_filiere')
        if type_filiere:
            queryset = queryset.filter(type_filiere=type_filiere)

        est_active = self.request.GET.get('est_active')
        if est_active:
            queryset = queryset.filter(est_active=est_active == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search) |
                Q(nom_diplome__icontains=search)
            )

        return queryset.order_by('nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'departements': Departement.objects.filter(etablissement=etablissement, est_actif=True),
            'types_filiere': Filiere.TYPES_FILIERE,
            'current_filters': {
                'departement': self.request.GET.get('departement', ''),
                'type_filiere': self.request.GET.get('type_filiere', ''),
                'est_active': self.request.GET.get('est_active', ''),
                'search': self.request.GET.get('search', ''),
            },
        })
        return context

class AdminNiveauxView(LoginRequiredMixin, ListView):
    """Gestion des niveaux par l'admin"""
    template_name = 'dashboard/admin/niveaux.html'
    context_object_name = 'niveaux'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = Niveau.objects.filter(
            filiere__etablissement=etablissement
        ).select_related('filiere__departement').annotate(
            nombre_classes=Count('classes', filter=Q(classes__est_active=True)),
            nombre_etudiants=Count(
                'classes__apprenants',
                filter=Q(classes__apprenants__utilisateur__est_actif=True),
                distinct=True
            )
        )

        # Filtres
        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(filiere_id=filiere)

        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(filiere__departement_id=departement)

        est_actif = self.request.GET.get('est_actif')
        if est_actif:
            queryset = queryset.filter(est_actif=est_actif == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search) |
                Q(filiere__nom__icontains=search)
            )

        return queryset.order_by('filiere__nom', 'ordre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'departements': Departement.objects.filter(etablissement=etablissement, est_actif=True),
            'filieres': Filiere.objects.filter(etablissement=etablissement, est_active=True),
            'current_filters': {
                'filiere': self.request.GET.get('filiere', ''),
                'departement': self.request.GET.get('departement', ''),
                'est_actif': self.request.GET.get('est_actif', ''),
                'search': self.request.GET.get('search', ''),
            },
        })
        return context

class AdminClassesView(LoginRequiredMixin, ListView):
    """Gestion des classes par l'admin"""
    template_name = 'dashboard/admin/classes.html'
    context_object_name = 'classes'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            # Limiter entre 10 et 100
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = Classe.objects.filter(
            etablissement=etablissement
        ).select_related(
            'niveau__filiere__departement',
            'annee_academique',
            'professeur_principal',
            'salle_principale'
        ).annotate(
            nombre_etudiants=Count('apprenants', filter=Q(apprenants__utilisateur__est_actif=True))
        )

        # Filtres
        annee_academique = self.request.GET.get('annee_academique')
        if annee_academique:
            queryset = queryset.filter(annee_academique_id=annee_academique)

        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(niveau__filiere__departement_id=departement)

        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(niveau__filiere_id=filiere)

        niveau = self.request.GET.get('niveau')
        if niveau:
            queryset = queryset.filter(niveau_id=niveau)

        est_active = self.request.GET.get('est_active')
        if est_active:
            queryset = queryset.filter(est_active=est_active == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search) |
                Q(niveau__filiere__nom__icontains=search)
            )

        return queryset.order_by('-annee_academique__nom', 'nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'annees_academiques': AnneeAcademique.objects.filter(
                etablissement=etablissement
            ).order_by('-nom'),
            'departements': Departement.objects.filter(etablissement=etablissement, est_actif=True),
            'filieres': Filiere.objects.filter(etablissement=etablissement, est_active=True),
            'niveaux': Niveau.objects.filter(filiere__etablissement=etablissement, est_actif=True),
            'current_filters': {
                'annee_academique': self.request.GET.get('annee_academique', ''),
                'departement': self.request.GET.get('departement', ''),
                'filiere': self.request.GET.get('filiere', ''),
                'niveau': self.request.GET.get('niveau', ''),
                'est_active': self.request.GET.get('est_active', ''),
                'search': self.request.GET.get('search', ''),
            },
        })
        return context

class AdminPeriodesView(LoginRequiredMixin, ListView):
    """Gestion des périodes académiques par l'admin"""
    template_name = 'dashboard/admin/periodes.html'
    context_object_name = 'periodes'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = PeriodeAcademique.objects.filter(
            etablissement=etablissement
        ).select_related('annee_academique')

        # Filtres
        annee_academique = self.request.GET.get('annee_academique')
        if annee_academique:
            queryset = queryset.filter(annee_academique_id=annee_academique)

        type_periode = self.request.GET.get('type_periode')
        if type_periode:
            queryset = queryset.filter(type_periode=type_periode)

        est_active = self.request.GET.get('est_active')
        if est_active:
            queryset = queryset.filter(est_active=est_active == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search)
            )

        return queryset.order_by('-annee_academique__nom', 'ordre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'annees_academiques': AnneeAcademique.objects.filter(
                etablissement=etablissement
            ).order_by('-nom'),
            'types_periode': PeriodeAcademique.TYPES_PERIODE,
            'current_filters': {
                'annee_academique': self.request.GET.get('annee_academique', ''),
                'type_periode': self.request.GET.get('type_periode', ''),
                'est_active': self.request.GET.get('est_active', ''),
                'search': self.request.GET.get('search', ''),
            },
        })
        return context

class AdminModulesView(LoginRequiredMixin, ListView):
    """Gestion des modules par l'admin"""
    template_name = 'dashboard/admin/modules.html'
    context_object_name = 'modules'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            # Limiter entre 10 et 100
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        user = self.request.user
        queryset = Module.objects.select_related(
            'niveau__filiere__departement',
            'coordinateur'
        ).annotate(
            nombre_matieres=Count('matieres'),
            total_heures=Sum(
                F('matieres__heures_cours_magistral') +
                F('matieres__heures_travaux_diriges') +
                F('matieres__heures_travaux_pratiques'),
                output_field=IntegerField()
            ),
            credits_ects_total=Sum('matieres__credits_ects')
        )

        # Filtres selon le rôle
        if user.role == 'ADMIN':
            queryset = queryset.filter(niveau__filiere__etablissement=user.etablissement)
        elif user.role == 'CHEF_DEPARTEMENT':
            queryset = queryset.filter(niveau__filiere__departement=user.departement)
        elif user.role == 'ENSEIGNANT':
            queryset = queryset.filter(
                Q(coordinateur=user) | Q(matieres__enseignant_responsable=user)
            ).distinct()

        # Filtres de recherche
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(Q(nom__icontains=search) | Q(code__icontains=search))

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

class AdminMatieresView(LoginRequiredMixin, ListView):
    """Gestion des matières par l'admin"""
    template_name = 'dashboard/admin/matieres.html'
    context_object_name = 'matieres'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            # Limiter entre 10 et 100
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

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
            queryset = queryset.filter(enseignant_responsable=user)

        # Filtres de recherche
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) | Q(code__icontains=search)
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

class AdminCandidaturesView(LoginRequiredMixin, ListView):
    """Gestion des candidatures par l'admin"""
    template_name = 'dashboard/admin/candidatures.html'
    context_object_name = 'candidatures'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etablissement = self.request.user.etablissement

        queryset = Candidature.objects.filter(
            etablissement=etablissement
        ).select_related(
            'filiere__departement',
            'niveau',
            'annee_academique',
            'examine_par'
        ).annotate(
            nombre_documents=Count('documents')
        )

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(filiere_id=filiere)

        niveau = self.request.GET.get('niveau')
        if niveau:
            queryset = queryset.filter(niveau_id=niveau)

        annee = self.request.GET.get('annee_academique')
        if annee:
            queryset = queryset.filter(annee_academique_id=annee)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero_candidature__icontains=search) |
                Q(nom__icontains=search) |
                Q(prenom__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'filieres': Filiere.objects.filter(etablissement=etablissement, est_active=True),
            'niveaux': Niveau.objects.filter(filiere__etablissement=etablissement, est_actif=True),
            'annees_academiques': AnneeAcademique.objects.filter(etablissement=etablissement),
            'statuts': Candidature.STATUTS_CANDIDATURE,
            'current_filters': {
                'statut': self.request.GET.get('statut', ''),
                'filiere': self.request.GET.get('filiere', ''),
                'niveau': self.request.GET.get('niveau', ''),
                'annee_academique': self.request.GET.get('annee_academique', ''),
                'search': self.request.GET.get('search', ''),
            },
            'stats': {
                'total': self.get_queryset().count(),
                'soumises': self.get_queryset().filter(statut='SOUMISE').count(),
                'en_cours': self.get_queryset().filter(statut='EN_COURS_EXAMEN').count(),
                'approuvees': self.get_queryset().filter(statut='APPROUVEE').count(),
            }
        })
        return context

class AdminInscriptionsView(LoginRequiredMixin, ListView):
    """Gestion des inscriptions par l'admin"""
    template_name = 'dashboard/admin/inscriptions.html'
    context_object_name = 'inscriptions'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etablissement = self.request.user.etablissement

        queryset = Inscription.objects.filter(
            candidature__etablissement=etablissement
        ).select_related(
            'apprenant',
            'candidature__filiere',
            'candidature__niveau',
            'classe_assignee',
            'cree_par'
        )

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        statut_paiement = self.request.GET.get('statut_paiement')
        if statut_paiement:
            queryset = queryset.filter(statut_paiement=statut_paiement)

        classe = self.request.GET.get('classe')
        if classe:
            queryset = queryset.filter(classe_assignee_id=classe)

        annee = self.request.GET.get('annee_academique')
        if annee:
            queryset = queryset.filter(candidature__annee_academique_id=annee)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero_inscription__icontains=search) |
                Q(apprenant__nom__icontains=search) |
                Q(apprenant__prenom__icontains=search) |
                Q(candidature__numero_candidature__icontains=search)
            )

        return queryset.order_by('-date_inscription')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'classes': Classe.objects.filter(
                niveau__filiere__etablissement=etablissement,
                est_active=True
            ),
            'annees_academiques': AnneeAcademique.objects.filter(etablissement=etablissement),
            'statuts': Inscription.STATUTS_INSCRIPTION,
            'statuts_paiement': Inscription.STATUTS_PAIEMENT,
            'current_filters': {
                'statut': self.request.GET.get('statut', ''),
                'statut_paiement': self.request.GET.get('statut_paiement', ''),
                'classe': self.request.GET.get('classe', ''),
                'annee_academique': self.request.GET.get('annee_academique', ''),
                'search': self.request.GET.get('search', ''),
            },
            'stats': {
                'total': self.get_queryset().count(),
                'actives': self.get_queryset().filter(statut='ACTIVE').count(),
                'paiement_complet': self.get_queryset().filter(statut_paiement='COMPLETE').count(),
                'paiement_partiel': self.get_queryset().filter(statut_paiement='PARTIAL').count(),
            }
        })
        return context

class AdminPaiementsView(LoginRequiredMixin, ListView):
    """Gestion des paiements par l'admin"""
    template_name = 'dashboard/admin/paiements.html'
    context_object_name = 'paiements'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etablissement = self.request.user.etablissement

        queryset = Paiement.objects.filter(
            inscription_paiement__inscription__candidature__etablissement=etablissement
        ).select_related(
            'inscription_paiement__inscription__apprenant',
            'tranche',
            'traite_par'
        )

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        methode = self.request.GET.get('methode_paiement')
        if methode:
            queryset = queryset.filter(methode_paiement=methode)

        date_debut = self.request.GET.get('date_debut')
        if date_debut:
            queryset = queryset.filter(date_paiement__gte=date_debut)

        date_fin = self.request.GET.get('date_fin')
        if date_fin:
            queryset = queryset.filter(date_paiement__lte=date_fin)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero_transaction__icontains=search) |
                Q(reference_externe__icontains=search) |
                Q(inscription_paiement__inscription__apprenant__nom__icontains=search) |
                Q(inscription_paiement__inscription__apprenant__prenom__icontains=search)
            )

        return queryset.order_by('-date_paiement')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        context.update({
            'statuts': Paiement.STATUTS_PAIEMENT,
            'methodes': Paiement.METHODES_PAIEMENT,
            'current_filters': {
                'statut': self.request.GET.get('statut', ''),
                'methode_paiement': self.request.GET.get('methode_paiement', ''),
                'date_debut': self.request.GET.get('date_debut', ''),
                'date_fin': self.request.GET.get('date_fin', ''),
                'search': self.request.GET.get('search', ''),
            },
            'stats': {
                'total': queryset.count(),
                'total_montant': queryset.filter(statut='CONFIRME').aggregate(
                    total=Sum('montant')
                )['total'] or Decimal('0.00'),
                'en_attente': queryset.filter(statut='EN_ATTENTE').count(),
                'confirmes': queryset.filter(statut='CONFIRME').count(),
            }
        })
        return context

class AdminCoursesView(LoginRequiredMixin, ListView):
    """Gestion des cours par l'admin"""
    template_name = 'dashboard/admin/courses.html'
    context_object_name = 'courses'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            # Limiter entre 10 et 100
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        user = self.request.user
        queryset = Cours.objects.select_related(
            'matiere__niveau__filiere',
            'classe__niveau',
            'enseignant',
            'periode_academique',
            'salle'
        )

        # Filtrage selon le rôle
        if user.role == 'ADMIN':
            queryset = queryset.filter(
                classe__etablissement=user.etablissement
            )
        elif user.role == 'CHEF_DEPARTEMENT':
            queryset = queryset.filter(
                matiere__niveau__filiere__departement=user.departement
            )
        elif user.role == 'ENSEIGNANT':
            queryset = queryset.filter(enseignant=user)
        elif user.role == 'APPRENANT':
            if hasattr(user, 'profil_apprenant') and user.profil_apprenant.classe_actuelle:
                queryset = queryset.filter(
                    classe=user.profil_apprenant.classe_actuelle,
                    date_prevue__gte=timezone.now().date() - timedelta(days=30)
                )
            else:
                queryset = queryset.none()

        # Filtres
        matiere_id = self.request.GET.get('matiere')
        if matiere_id:
            queryset = queryset.filter(matiere_id=matiere_id)

        classe_id = self.request.GET.get('classe')
        if classe_id:
            queryset = queryset.filter(classe_id=classe_id)

        enseignant_id = self.request.GET.get('enseignant')
        if enseignant_id:
            queryset = queryset.filter(enseignant_id=enseignant_id)

        date_debut = self.request.GET.get('date_debut')
        if date_debut:
            queryset = queryset.filter(date_prevue__gte=date_debut)

        date_fin = self.request.GET.get('date_fin')
        if date_fin:
            queryset = queryset.filter(date_prevue__lte=date_fin)

        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        type_cours = self.request.GET.get('type_cours')
        if type_cours:
            queryset = queryset.filter(type_cours=type_cours)

        return queryset.order_by('-date_prevue', '-heure_debut_prevue')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.role in ['ADMIN', 'CHEF_DEPARTEMENT']:
            if user.role == 'ADMIN':
                context['matieres'] = Matiere.objects.filter(
                    niveau__filiere__etablissement=user.etablissement, actif=True
                )
                context['classes'] = Classe.objects.filter(
                    etablissement=user.etablissement, est_active=True
                )
                context['enseignants'] = Utilisateur.objects.filter(
                    etablissement=user.etablissement, role='ENSEIGNANT', est_actif=True
                )
            else:
                context['matieres'] = Matiere.objects.filter(
                    niveau__filiere__departement=user.departement, actif=True
                )
                context['classes'] = Classe.objects.filter(
                    niveau__filiere__departement=user.departement, est_active=True
                )
                context['enseignants'] = Utilisateur.objects.filter(
                    departement=user.departement, role='ENSEIGNANT', est_actif=True
                )

        context['statuts'] = StatutCours.choices
        context['types_cours'] = TypeCours.choices
        context['current_filters'] = {
            'matiere': self.request.GET.get('matiere', ''),
            'classe': self.request.GET.get('classe', ''),
            'enseignant': self.request.GET.get('enseignant', ''),
            'date_debut': self.request.GET.get('date_debut', ''),
            'date_fin': self.request.GET.get('date_fin', ''),
            'statut': self.request.GET.get('statut', ''),
            'type_cours': self.request.GET.get('type_cours', ''),
        }

        return context

class AdminEvaluationsView(LoginRequiredMixin, ListView):
    """Gestion des évaluations par l'admin"""
    template_name = 'dashboard/admin/evaluations.html'
    context_object_name = 'evaluations'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etablissement = self.request.user.etablissement

        # Filtrer par établissement via la matière
        queryset = Evaluation.objects.filter(
            matiere__niveau__filiere__etablissement=etablissement
        ).select_related(
            'enseignant',
            'matiere',
            'matiere__niveau__filiere'
        ).prefetch_related(
            'classes'
        ).annotate(
            nombre_compositions=Count('compositions')
        )

        # Filtres
        type_eval = self.request.GET.get('type_evaluation')
        if type_eval:
            queryset = queryset.filter(type_evaluation=type_eval)

        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        enseignant = self.request.GET.get('enseignant')
        if enseignant:
            queryset = queryset.filter(enseignant_id=enseignant)

        matiere = self.request.GET.get('matiere')
        if matiere:
            queryset = queryset.filter(matiere_id=matiere)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) |
                Q(matiere__nom__icontains=search) |
                Q(enseignant__prenom__icontains=search) |
                Q(enseignant__nom__icontains=search)
            )

        return queryset.order_by('-date_debut')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        # Récupérer les matières de l'établissement
        matieres = Matiere.objects.filter(
            niveau__filiere__etablissement=etablissement,
            actif=True
        ).select_related('niveau__filiere')

        context.update({
            'types_evaluation': Evaluation.TYPE_EVALUATION,
            'statuts': Evaluation.STATUT,
            'enseignants': Utilisateur.objects.filter(
                etablissement=etablissement,
                role='ENSEIGNANT',
                est_actif=True
            ).order_by('nom', 'prenom'),
            'matieres': matieres,
            'current_filters': {
                'type_evaluation': self.request.GET.get('type_evaluation', ''),
                'statut': self.request.GET.get('statut', ''),
                'enseignant': self.request.GET.get('enseignant', ''),
                'matiere': self.request.GET.get('matiere', ''),
                'search': self.request.GET.get('search', ''),
            },
            'stats': {
                'total': self.get_queryset().count(),
                'brouillon': self.get_queryset().filter(statut='BROUILLON').count(),
                'programmees': self.get_queryset().filter(statut='PROGRAMMEE').count(),
                'en_cours': self.get_queryset().filter(statut='EN_COURS').count(),
                'terminees': self.get_queryset().filter(statut='TERMINEE').count(),
            }
        })
        return context

class AdminCahiersTexteView(LoginRequiredMixin, ListView):
    """Gestion des cahiers de texte par l'admin"""
    template_name = 'dashboard/admin/cahiers_texte.html'
    context_object_name = 'cahiers'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        user = self.request.user
        queryset = CahierTexte.objects.select_related(
            'cours__matiere__niveau__filiere',
            'cours__classe',
            'cours__enseignant',
            'rempli_par'
        ).filter(
            cours__classe__etablissement=user.etablissement
        )

        # Filtres
        classe_id = self.request.GET.get('classe')
        if classe_id:
            queryset = queryset.filter(cours__classe_id=classe_id)

        enseignant_id = self.request.GET.get('enseignant')
        if enseignant_id:
            queryset = queryset.filter(cours__enseignant_id=enseignant_id)

        matiere_id = self.request.GET.get('matiere')
        if matiere_id:
            queryset = queryset.filter(cours__matiere_id=matiere_id)

        date_debut = self.request.GET.get('date_debut')
        if date_debut:
            queryset = queryset.filter(cours__date_prevue__gte=date_debut)

        date_fin = self.request.GET.get('date_fin')
        if date_fin:
            queryset = queryset.filter(cours__date_prevue__lte=date_fin)

        return queryset.order_by('-cours__date_prevue')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['classes'] = Classe.objects.filter(
            etablissement=user.etablissement, est_active=True
        )
        context['enseignants'] = Utilisateur.objects.filter(
            etablissement=user.etablissement, role='ENSEIGNANT', est_actif=True
        )
        context['matieres'] = Matiere.objects.filter(
            niveau__filiere__etablissement=user.etablissement, actif=True
        )
        context['current_filters'] = {
            'classe': self.request.GET.get('classe', ''),
            'enseignant': self.request.GET.get('enseignant', ''),
            'matiere': self.request.GET.get('matiere', ''),
            'date_debut': self.request.GET.get('date_debut', ''),
            'date_fin': self.request.GET.get('date_fin', ''),
        }

        return context

class AdminEmploiDuTempsView(LoginRequiredMixin, ListView):
    """Gestion des programmes par l'admin"""
    template_name = 'dashboard/admin/emplois_du_temps.html'
    context_object_name = 'emplois_du_temps'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = EmploiDuTemps.objects.select_related(
            'classe__niveau__filiere',
            'enseignant',
            'periode_academique',
            'cree_par'
        ).prefetch_related('creneaux')

        # Filtrage selon le rôle
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
            if hasattr(user, 'profil_apprenant') and user.profil_apprenant.classe_actuelle:
                queryset = queryset.filter(
                    classe=user.profil_apprenant.classe_actuelle,
                    publie=True
                )
            else:
                queryset = queryset.none()

        # Filtres
        filter_type = self.request.GET.get('type', 'classe')

        if filter_type == 'classe':
            classe_id = self.request.GET.get('classe')
            if classe_id:
                queryset = queryset.filter(classe_id=classe_id)
        else:
            enseignant_id = self.request.GET.get('enseignant')
            if enseignant_id:
                queryset = queryset.filter(enseignant_id=enseignant_id)

        periode_id = self.request.GET.get('periode')
        if periode_id:
            queryset = queryset.filter(periode_academique_id=periode_id)

        statut = self.request.GET.get('statut')
        if statut == 'publie':
            queryset = queryset.filter(publie=True)
        elif statut == 'non_publie':
            queryset = queryset.filter(publie=False)
        elif statut == 'actuel':
            queryset = queryset.filter(actuel=True)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.role == 'ADMIN':
            context['classes'] = Classe.objects.filter(
                etablissement=user.etablissement, est_active=True
            ).select_related('niveau__filiere')
            context['enseignants'] = Utilisateur.objects.filter(
                etablissement=user.etablissement, role='ENSEIGNANT', est_actif=True
            )
            context['periodes'] = PeriodeAcademique.objects.filter(
                etablissement=user.etablissement, est_active=True
            )
        elif user.role == 'CHEF_DEPARTEMENT':
            context['classes'] = Classe.objects.filter(
                niveau__filiere__departement=user.departement, est_active=True
            ).select_related('niveau__filiere')
            context['enseignants'] = Utilisateur.objects.filter(
                departement=user.departement, role='ENSEIGNANT', est_actif=True
            )
            context['periodes'] = PeriodeAcademique.objects.filter(
                etablissement=user.etablissement, est_active=True
            )

        context['nombre_publies'] = self.get_queryset().filter(publie=True).count()
        context['current_filters'] = {
            'type': self.request.GET.get('type', 'classe'),
            'classe': self.request.GET.get('classe', ''),
            'enseignant': self.request.GET.get('enseignant', ''),
            'periode': self.request.GET.get('periode', ''),
            'statut': self.request.GET.get('statut', ''),
        }

        return context

class AdminRessourcesView(LoginRequiredMixin, ListView):
    """Gestion des ressources par l'admin"""
    template_name = 'dashboard/admin/ressources.html'
    context_object_name = 'ressources'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        user = self.request.user
        queryset = Ressource.objects.select_related(
            'cours__matiere',
            'cours__classe',
            'cours__enseignant'
        ).filter(
            cours__classe__etablissement=user.etablissement
        )

        # Filtres
        type_ressource = self.request.GET.get('type')
        if type_ressource:
            queryset = queryset.filter(type_ressource=type_ressource)

        cours_id = self.request.GET.get('cours')
        if cours_id:
            queryset = queryset.filter(cours_id=cours_id)

        enseignant_id = self.request.GET.get('enseignant')
        if enseignant_id:
            queryset = queryset.filter(cours__enseignant_id=enseignant_id)

        public = self.request.GET.get('public')
        if public:
            queryset = queryset.filter(public=public == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) | Q(description__icontains=search)
            )

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['types_ressource'] = Ressource.TYPES_RESSOURCE
        context['enseignants'] = Utilisateur.objects.filter(
            etablissement=user.etablissement, role='ENSEIGNANT', est_actif=True
        )
        context['current_filters'] = {
            'type': self.request.GET.get('type', ''),
            'cours': self.request.GET.get('cours', ''),
            'enseignant': self.request.GET.get('enseignant', ''),
            'public': self.request.GET.get('public', ''),
            'search': self.request.GET.get('search', ''),
        }

        # Stats
        queryset = self.get_queryset()
        context['total_telechargements'] = queryset.aggregate(Sum('nombre_telechargements'))['nombre_telechargements__sum'] or 0
        context['total_vues'] = queryset.aggregate(Sum('nombre_vues'))['nombre_vues__sum'] or 0

        return context

@login_required
def admin_salles(request):
    """Liste des salles"""
    user = request.user
    etablissement = user.etablissement

    # Récupération des salles
    salles = Salle.objects.filter(etablissement=etablissement)

    # Filtres
    search = request.GET.get('search', '')
    type_salle = request.GET.get('type_salle', '')
    batiment = request.GET.get('batiment', '')
    etat = request.GET.get('etat', '')

    if search:
        salles = salles.filter(
            Q(nom__icontains=search) |
            Q(code__icontains=search) |
            Q(batiment__icontains=search)
        )

    if type_salle:
        salles = salles.filter(type_salle=type_salle)

    if batiment:
        salles = salles.filter(batiment=batiment)

    if etat:
        salles = salles.filter(etat=etat)

    # Statistiques
    stats = {
        'total': salles.count(),
        'actives': salles.filter(est_active=True).count(),
        'capacite_totale': sum(s.capacite for s in salles),
    }

    # Types et états uniques
    types_salle = Salle.TYPES_SALLE
    etats = [
        ('EXCELLENT', 'Excellent'),
        ('BON', 'Bon'),
        ('CORRECT', 'Correct'),
        ('MAUVAIS', 'Mauvais'),
        ('MAINTENANCE', 'En maintenance'),
    ]
    batiments = salles.values_list('batiment', flat=True).distinct().order_by('batiment')

    # Pagination
    paginator = Paginator(salles, 20)
    page_number = request.GET.get('page')
    salles_page = paginator.get_page(page_number)

    context = {
        'salles': salles_page,
        'stats': stats,
        'types_salle': types_salle,
        'etats': etats,
        'batiments': batiments,
        'current_filters': {
            'search': search,
            'type_salle': type_salle,
            'batiment': batiment,
            'etat': etat,
        }
    }

    return render(request, 'dashboard/admin/salles.html', context)

@login_required
def toggle_salle_status(request, salle_id):
    """Active/Désactive une salle"""
    if request.method == 'POST':
        salle = get_object_or_404(Salle, id=salle_id, etablissement=request.user.etablissement)
        salle.est_active = not salle.est_active
        salle.save()

        return JsonResponse({
            'success': True,
            'message': f"Salle {'activée' if salle.est_active else 'désactivée'} avec succès"
        })

    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'})

class AdminSettingsView(LoginRequiredMixin, TemplateView):
    """Paramètres de l'établissement"""
    template_name = 'dashboard/admin/settings.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['etablissement'] = self.request.user.etablissement
        return context

class AdminReportsView(LoginRequiredMixin, TemplateView):
    """Rapports et statistiques pour l'admin"""
    template_name = 'dashboard/admin/reports.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        # Données pour les rapports
        context.update({
            'rapport_inscriptions': self.get_rapport_inscriptions(etablissement),
            'rapport_paiements': self.get_rapport_paiements(etablissement),
            'rapport_evaluations': self.get_rapport_evaluations(etablissement),
        })

        return context

    def get_rapport_inscriptions(self, etablissement):
        # Rapport des inscriptions par période
        return {
            'total_inscriptions': Inscription.objects.filter(
                apprenant__etablissement=etablissement
            ).count(),
            'inscriptions_mois': self.get_inscriptions_par_mois(etablissement),
        }

    def get_rapport_paiements(self, etablissement):
        # Rapport des paiements
        return {
            'total_collecte': Paiement.objects.filter(
                apprenant__etablissement=etablissement,
                statut='VALIDE'
            ).aggregate(total=Sum('montant'))['total'] or 0,
            'paiements_mois': self.get_paiements_par_mois(etablissement),
        }

    def get_rapport_evaluations(self, etablissement):
        # Rapport des évaluations
        return {
            'total_evaluations': Evaluation.objects.filter(
                cours__matiere__modules__filiere__departement__etablissement=etablissement
            ).count(),
        }

# ================================
# VUES COMPTABLE
# ================================
class ComptableDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord du comptable"""
    template_name = 'dashboard/comptable/index.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        # Période actuelle (mois en cours)
        today = timezone.now().date()
        debut_mois = today.replace(day=1)

        context.update({
            # Statistiques générales
            'total_recettes_mois': self.get_recettes_mois(etablissement, debut_mois),
            'total_depenses_mois': self.get_depenses_mois(etablissement, debut_mois),
            'solde_tresorerie': self.get_solde_tresorerie(etablissement),
            'factures_impayees': self.get_factures_impayees(etablissement),
            'depenses_en_attente': self.get_depenses_en_attente(etablissement),

            # Paiements en attente de validation
            'paiements_en_attente': self.get_paiements_en_attente(etablissement),

            # Graphiques
            'evolution_recettes_depenses': self.get_evolution_recettes_depenses(etablissement),
            'repartition_depenses': self.get_repartition_depenses(etablissement),
            'top_payeurs': self.get_top_payeurs(etablissement),

            # Activités récentes
            'paiements_recents': self.get_paiements_recents(etablissement),
            'depenses_recentes': self.get_depenses_recentes(etablissement),
            'factures_recentes': self.get_factures_recentes(etablissement),
        })

        return context

    def get_recettes_mois(self, etablissement, debut_mois):
        return Paiement.objects.filter(
            inscription_paiement__inscription__apprenant__etablissement=etablissement,
            date_paiement__gte=debut_mois,
            statut='CONFIRME'
        ).aggregate(total=models.Sum('montant'))['total'] or Decimal('0.00')

    def get_depenses_mois(self, etablissement, debut_mois):
        return Depense.objects.filter(
            etablissement=etablissement,
            date_depense__gte=debut_mois,
            statut='PAYEE'
        ).aggregate(total=models.Sum('montant'))['total'] or Decimal('0.00')

    def get_solde_tresorerie(self, etablissement):

        comptes_tresorerie = CompteComptable.objects.filter(
            etablissement=etablissement,
            categorie='TRESORERIE',
            est_actif=True
        )
        return comptes_tresorerie.aggregate(
            total=models.Sum('solde_actuel')
        )['total'] or Decimal('0.00')

    def get_factures_impayees(self, etablissement):
        return Facture.objects.filter(
            etablissement=etablissement,
            statut__in=['EMISE', 'PARTIELLE']
        ).count()

    def get_depenses_en_attente(self, etablissement):
        return Depense.objects.filter(
            etablissement=etablissement,
            statut='EN_ATTENTE'
        ).count()

    def get_paiements_en_attente(self, etablissement):
        return Paiement.objects.filter(
            inscription_paiement__inscription__apprenant__etablissement=etablissement,
            statut='EN_ATTENTE'
        ).select_related(
            'inscription_paiement__inscription__apprenant'
        ).order_by('-date_paiement')[:10]

    def get_evolution_recettes_depenses(self, etablissement):

        # 12 derniers mois
        today = timezone.now().date()
        debut_periode = today - timedelta(days=365)

        # Recettes par mois
        recettes = Paiement.objects.filter(
            inscription_paiement__inscription__apprenant__etablissement=etablissement,
            date_paiement__gte=debut_periode,
            statut='CONFIRME'
        ).annotate(
            mois=ExtractMonth('date_paiement')
        ).values('mois').annotate(
            total=models.Sum('montant')
        ).order_by('mois')

        # Dépenses par mois
        depenses = Depense.objects.filter(
            etablissement=etablissement,
            date_depense__gte=debut_periode,
            statut='PAYEE'
        ).annotate(
            mois=ExtractMonth('date_depense')
        ).values('mois').annotate(
            total=models.Sum('montant')
        ).order_by('mois')

        recettes_par_mois = [0] * 12
        depenses_par_mois = [0] * 12

        for r in recettes:
            recettes_par_mois[int(r['mois']) - 1] = float(r['total'])

        for d in depenses:
            depenses_par_mois[int(d['mois']) - 1] = float(d['total'])

        return {
            'recettes': recettes_par_mois,
            'depenses': depenses_par_mois
        }

    def get_repartition_depenses(self, etablissement):

        return list(
            Depense.objects.filter(
                etablissement=etablissement,
                statut='PAYEE'
            ).values('categorie').annotate(
                total=models.Sum('montant')
            ).order_by('-total')[:10]
        )

    def get_top_payeurs(self, etablissement):

        today = timezone.now().date()
        debut_annee = today.replace(month=1, day=1)

        return list(
            Paiement.objects.filter(
                inscription_paiement__inscription__apprenant__etablissement=etablissement,
                date_paiement__gte=debut_annee,
                statut='CONFIRME'
            ).values(
                'inscription_paiement__inscription__apprenant__prenom',
                'inscription_paiement__inscription__apprenant__nom'
            ).annotate(
                total=models.Sum('montant')
            ).order_by('-total')[:10]
        )

    def get_paiements_recents(self, etablissement):
        return Paiement.objects.filter(
            inscription_paiement__inscription__apprenant__etablissement=etablissement
        ).select_related(
            'inscription_paiement__inscription__apprenant'
        ).order_by('-date_paiement')[:10]

    def get_depenses_recentes(self, etablissement):
        return Depense.objects.filter(
            etablissement=etablissement
        ).order_by('-date_depense')[:10]

    def get_factures_recentes(self, etablissement):
        return Facture.objects.filter(
            etablissement=etablissement
        ).select_related('apprenant').order_by('-date_emission')[:10]

class ComptablePaiementsView(LoginRequiredMixin, ListView):
    """Liste des paiements à valider"""
    template_name = 'dashboard/comptable/paiements.html'
    context_object_name = 'paiements'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Paiement.objects.filter(
            inscription_paiement__inscription__apprenant__etablissement=self.request.user.etablissement
        ).select_related(
            'inscription_paiement__inscription__apprenant',
            'tranche'
        )

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        else:
            # Par défaut, afficher les paiements en attente
            qs = qs.filter(statut='EN_ATTENTE')

        return qs.order_by('-date_paiement')

class ComptableFacturesView(LoginRequiredMixin, ListView):
    model = Facture
    template_name = 'dashboard/comptable/factures.html'
    context_object_name = 'factures'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Facture.objects.filter(
            etablissement=self.request.user.etablissement
        ).select_related('apprenant', 'inscription')

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        type_facture = self.request.GET.get('type')
        if type_facture:
            qs = qs.filter(type_facture=type_facture)

        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(
                Q(numero_facture__icontains=search) |
                Q(apprenant__nom__icontains=search) |
                Q(apprenant__prenom__icontains=search)
            )

        return qs.order_by('-date_emission')

class ComptableDepensesView(LoginRequiredMixin, ListView):
    """Liste des dépenses"""
    model = Depense
    template_name = 'dashboard/comptable/depenses.html'
    context_object_name = 'depenses'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Depense.objects.filter(
            etablissement=self.request.user.etablissement
        )

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        categorie = self.request.GET.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)

        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(
                Q(numero_depense__icontains=search) |
                Q(fournisseur__icontains=search) |
                Q(description__icontains=search)
            )

        return qs.order_by('-date_depense')

class ComptableEcrituresView(LoginRequiredMixin, ListView):
    """Liste des écritures comptables"""
    template_name = 'dashboard/comptable/ecritures.html'
    context_object_name = 'ecritures'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = EcritureComptable.objects.filter(
            etablissement=self.request.user.etablissement
        ).select_related('journal').order_by('-date_ecriture')

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        journal = self.request.GET.get('journal')
        if journal:
            qs = qs.filter(journal_id=journal)

        date_debut = self.request.GET.get('date_debut')
        date_fin = self.request.GET.get('date_fin')
        if date_debut and date_fin:
            qs = qs.filter(date_ecriture__range=[date_debut, date_fin])

        return qs

class ComptableComptesView(LoginRequiredMixin, ListView):
    """Liste des comptes comptables"""
    template_name = 'dashboard/comptable/comptes.html'
    context_object_name = 'comptes'
    paginate_by = 50

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = CompteComptable.objects.filter(
            etablissement=self.request.user.etablissement
        ).order_by('numero_compte')

        # Filtres
        categorie = self.request.GET.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)

        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(
                Q(numero_compte__icontains=search) |
                Q(libelle__icontains=search)
            )

        return qs

class ComptableRapportBalanceView(LoginRequiredMixin, TemplateView):
    """Rapport balance détaillée"""
    template_name = 'dashboard/comptable/balance.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date_debut = self.request.GET.get('date_debut')
        date_fin = self.request.GET.get('date_fin')

        if date_debut and date_fin:
            from datetime import datetime
            date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
            date_fin = datetime.strptime(date_fin, '%Y-%m-%d').date()

            balance = ComptabiliteUtils.generer_balance(
                self.request.user.etablissement,
                date_debut,
                date_fin
            )

            context['balance'] = balance
            context['date_debut'] = date_debut
            context['date_fin'] = date_fin

        return context

class ComptableRapportsView(LoginRequiredMixin, TemplateView):
    """Rapports comptables"""
    template_name = 'dashboard/comptable/rapports.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        # Période sélectionnée
        date_debut = self.request.GET.get('date_debut')
        date_fin = self.request.GET.get('date_fin')

        if not date_debut or not date_fin:
            # Par défaut : mois en cours
            today = timezone.now().date()
            date_debut = today.replace(day=1)
            date_fin = today
        else:
            date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
            date_fin = datetime.strptime(date_fin, '%Y-%m-%d').date()

        context.update({
            'date_debut': date_debut,
            'date_fin': date_fin,
            'rapport_recettes': self.get_rapport_recettes(etablissement, date_debut, date_fin),
            'rapport_depenses': self.get_rapport_depenses(etablissement, date_debut, date_fin),
            'rapport_tresorerie': self.get_rapport_tresorerie(etablissement),
            'rapport_impayés': self.get_rapport_impayes(etablissement),
        })

        return context

    def get_rapport_recettes(self, etablissement, date_debut, date_fin):

        paiements = Paiement.objects.filter(
            inscription_paiement__inscription__apprenant__etablissement=etablissement,
            date_paiement__range=[date_debut, date_fin],
            statut='CONFIRME'
        )

        return {
            'total': paiements.aggregate(total=models.Sum('montant'))['total'] or Decimal('0.00'),
            'nombre': paiements.count(),
            'par_methode': list(
                paiements.values('methode_paiement').annotate(
                    total=models.Sum('montant'),
                    nombre=Count('id')
                )
            )
        }

    def get_rapport_depenses(self, etablissement, date_debut, date_fin):

        depenses = Depense.objects.filter(
            etablissement=etablissement,
            date_depense__range=[date_debut, date_fin],
            statut='PAYEE'
        )

        return {
            'total': depenses.aggregate(total=models.Sum('montant'))['total'] or Decimal('0.00'),
            'nombre': depenses.count(),
            'par_categorie': list(
                depenses.values('categorie').annotate(
                    total=models.Sum('montant'),
                    nombre=Count('id')
                ).order_by('-total')
            )
        }

    def get_rapport_tresorerie(self, etablissement):

        comptes = CompteComptable.objects.filter(
            etablissement=etablissement,
            categorie='TRESORERIE',
            est_actif=True
        )

        return {
            'solde_total': comptes.aggregate(total=models.Sum('solde_actuel'))['total'] or Decimal('0.00'),
            'par_compte': list(comptes.values('numero_compte', 'libelle', 'solde_actuel'))
        }

    def get_rapport_impayes(self, etablissement):

        factures_impayees = Facture.objects.filter(
            etablissement=etablissement,
            statut__in=['EMISE', 'PARTIELLE']
        )

        return {
            'nombre': factures_impayees.count(),
            'montant_total': factures_impayees.aggregate(
                total=models.Sum(F('montant_ttc') - F('montant_paye'))
            )['total'] or Decimal('0.00'),
            'par_apprenant': list(
                factures_impayees.values(
                    'apprenant__nom',
                    'apprenant__prenom'
                ).annotate(
                    total_impaye=models.Sum(F('montant_ttc') - F('montant_paye')),
                    nombre_factures=Count('id')
                ).order_by('-total_impaye')[:20]
            )
        }

@login_required
def comptable_rapport_bilan(request):
    """Génère le bilan comptable"""
    if request.user.role != 'COMPTABLE':
        return HttpResponseForbidden()

    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    format_export = request.GET.get('format', 'view')

    # Vérification dates
    if not date_debut or not date_fin:
        messages.error(request, "Dates requises")
        return redirect('dashboard:comptable_rapports')

    # Conversion dates
    import datetime

    date_debut = datetime.datetime.strptime(date_debut, '%Y-%m-%d').date()
    date_fin = datetime.datetime.strptime(date_fin, '%Y-%m-%d').date()

    # Récupération comptes
    comptes_actif = CompteComptable.objects.filter(
        etablissement=request.user.etablissement,
        categorie='ACTIF',
        est_actif=True
    )

    comptes_passif = CompteComptable.objects.filter(
        etablissement=request.user.etablissement,
        categorie='PASSIF',
        est_actif=True
    )

    # Structure du bilan
    bilan_data = {
        'actif': [],
        'passif': [],
        'total_actif': Decimal('0.00'),
        'total_passif': Decimal('0.00'),
    }

    # ACTIF
    for compte in comptes_actif:
        solde = ComptabiliteUtils.calculer_solde_compte(compte, date_debut, date_fin)
        if solde != 0:
            bilan_data['actif'].append({
                'compte': compte,
                'solde': solde,
                'solde_abs': abs(solde)
            })
            bilan_data['total_actif'] += solde

    # PASSIF
    for compte in comptes_passif:
        solde = ComptabiliteUtils.calculer_solde_compte(compte, date_debut, date_fin)
        if solde != 0:
            bilan_data['passif'].append({
                'compte': compte,
                'solde': solde,
                'solde_abs': abs(solde)
            })
            bilan_data['total_passif'] += solde

    # Calcul écart en valeur absolue
    ecart = bilan_data['total_actif'] - bilan_data['total_passif']
    bilan_data['ecart'] = abs(ecart)

    context = {
        'bilan': bilan_data,
        'date_debut': date_debut,
        'date_fin': date_fin,
    }

    # Export PDF
    if format_export == 'pdf':
        messages.info(request, "Export PDF en développement")
        return redirect('dashboard:comptable_rapports')

    return render(request, 'dashboard/comptable/bilan.html', context)

@login_required
def comptable_rapport_resultat(request):
    """Génère le compte de résultat"""
    if request.user.role != 'COMPTABLE':
        return HttpResponseForbidden()

    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    if not date_debut or not date_fin:
        messages.error(request, "Dates requises")
        return redirect('dashboard:comptable_rapports')

    # Conversion dates
    import datetime

    date_debut = datetime.datetime.strptime(date_debut, '%Y-%m-%d').date()
    date_fin = datetime.datetime.strptime(date_fin, '%Y-%m-%d').date()

    # Charges
    comptes_charges = CompteComptable.objects.filter(
        etablissement=request.user.etablissement,
        categorie='CHARGES',
        est_actif=True
    )

    # Produits
    comptes_produits = CompteComptable.objects.filter(
        etablissement=request.user.etablissement,
        categorie='PRODUITS',
        est_actif=True
    )

    resultat_data = {
        'charges': [],
        'produits': [],
        'total_charges': Decimal('0.00'),
        'total_produits': Decimal('0.00')
    }

    for compte in comptes_charges:
        solde = ComptabiliteUtils.calculer_solde_compte(compte, date_debut, date_fin)
        if solde != 0:
            montant_abs = abs(solde)
            resultat_data['charges'].append({
                'compte': compte,
                'montant': montant_abs
            })
            resultat_data['total_charges'] += montant_abs

    for compte in comptes_produits:
        solde = ComptabiliteUtils.calculer_solde_compte(compte, date_debut, date_fin)
        if solde != 0:
            montant_abs = abs(solde)
            resultat_data['produits'].append({
                'compte': compte,
                'montant': montant_abs
            })
            resultat_data['total_produits'] += montant_abs

    # Résultat net
    resultat_data['resultat'] = resultat_data['total_produits'] - resultat_data['total_charges']

    context = {
        'resultat': resultat_data,
        'date_debut': date_debut,
        'date_fin': date_fin,
    }

    return render(request, 'dashboard/comptable/resultat.html', context)

@login_required
def comptable_rapport_tresorerie(request):
    """État de trésorerie"""
    if request.user.role != 'COMPTABLE':
        return HttpResponseForbidden()

    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    if not date_debut or not date_fin:
        messages.error(request, "Dates requises")
        return redirect('dashboard:comptable_rapports')


    import datetime
    date_debut = datetime.datetime.strptime(date_debut, '%Y-%m-%d').date()
    date_fin = datetime.datetime.strptime(date_fin, '%Y-%m-%d').date()

    comptes_tresorerie = CompteComptable.objects.filter(
        etablissement=request.user.etablissement,
        categorie='TRESORERIE',
        est_actif=True
    )

    tresorerie_data = {
        'comptes': [],
        'total': Decimal('0.00')
    }

    for compte in comptes_tresorerie:
        solde = ComptabiliteUtils.calculer_solde_compte(compte, date_debut, date_fin)
        tresorerie_data['comptes'].append({
            'compte': compte,
            'solde': solde
        })
        tresorerie_data['total'] += solde

    context = {
        'tresorerie': tresorerie_data,
        'date_debut': date_debut,
        'date_fin': date_fin,
    }

    return render(request, 'dashboard/comptable/tresorerie.html', context)

class ComptableBudgetView(LoginRequiredMixin, ListView):
    """Gestion du budget"""
    template_name = 'dashboard/comptable/budget.html'
    context_object_name = 'budgets'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return BudgetPrevisionnel.objects.filter(
            etablissement=self.request.user.etablissement
        ).select_related('exercice').order_by('-exercice__date_debut', 'type_budget')

class ComptableExercicesView(LoginRequiredMixin, ListView):
    """Liste des exercices comptables"""
    template_name = 'dashboard/comptable/exercices.html'
    context_object_name = 'exercices'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ExerciceComptable.objects.filter(
            etablissement=self.request.user.etablissement
        ).order_by('-date_debut')


# ================================
# VUES CHEF DEPARTEMENT
# ================================
class DepartmentHeadDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord du chef de département"""
    template_name = 'dashboard/department_head/index.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        context.update({
            'departement': departement,
            'total_enseignants': self.get_total_enseignants(departement),
            'total_apprenants': self.get_total_apprenants(departement),
            'total_filieres': self.get_total_filieres(departement),
            'total_classes': self.get_total_classes(departement),
            'evaluations_en_cours': self.get_evaluations_en_cours(departement),
            'candidatures_departement': self.get_candidatures_departement(departement),

            # Graphiques
            'repartition_apprenants_filiere': self.get_repartition_apprenants_filiere(departement),
            'stats_evaluations_mois': self.get_stats_evaluations_par_mois(departement),

            # Activités récentes
            'cours_recents': self.get_cours_recents(departement),
            'evaluations_recentes': self.get_evaluations_recentes(departement),
        })

        return context

    def get_total_enseignants(self, departement):
        return Utilisateur.objects.filter(
            departement=departement,
            role='ENSEIGNANT',
            est_actif=True
        ).count()

    def get_total_apprenants(self, departement):
        return Utilisateur.objects.filter(
            departement=departement,
            role='APPRENANT',
            est_actif=True
        ).count()

    def get_total_filieres(self, departement):
        return Filiere.objects.filter(departement=departement).count()

    def get_total_classes(self, departement):
        return Classe.objects.filter(
            niveau__filiere__departement=departement
        ).count()

    def get_evaluations_en_cours(self, departement):
        return Evaluation.objects.filter(
            matiere__niveau__filiere__departement=departement,
            statut='EN_COURS'
        ).count()

    def get_candidatures_departement(self, departement):
        return Candidature.objects.filter(
            filiere__departement=departement,
            statut='EN_ATTENTE'
        ).count()

    def get_repartition_apprenants_filiere(self, departement):
        return list(
            Filiere.objects.filter(departement=departement).annotate(
                nombre_apprenants=Count(
                    'niveaux__classes__apprenants',
                    filter=Q(niveaux__classes__apprenants__utilisateur__est_actif=True),
                    distinct=True
                )
            ).values('nom', 'nombre_apprenants')
        )

    def get_stats_evaluations_par_mois(self, departement):
        aujourd_hui = timezone.now()
        debut_annee = aujourd_hui.replace(month=1, day=1)

        evaluations = Evaluation.objects.filter(
            matiere__niveau__filiere__departement=departement,
            created_at__gte=debut_annee
        ).annotate(
            month=ExtractMonth('created_at')
        ).values('month').annotate(count=Count('id'))

        stats = [0] * 12
        for item in evaluations:
            stats[int(item['month']) - 1] = item['count']

        return stats

    def get_cours_recents(self, departement):
        return Cours.objects.filter(
            matiere__niveau__filiere__departement=departement
        ).select_related('matiere', 'enseignant', 'classe').order_by('-created_at')[:5]

    def get_evaluations_recentes(self, departement):
        return Evaluation.objects.filter(
            matiere__niveau__filiere__departement=departement
        ).select_related('matiere', 'enseignant').order_by('-created_at')[:5]

class DepartmentHeadTeachersView(LoginRequiredMixin, ListView):
    """Gestion des enseignants du département - Vue optimisée"""
    model = Utilisateur
    template_name = 'dashboard/department_head/teachers.html'
    context_object_name = 'teachers'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Utilisateur.objects.filter(
            departement=departement,
            role='ENSEIGNANT'
        ).select_related(
            'profil_enseignant',
            'departement'
        ).prefetch_related(
            'matieres_responsable',
            'cours_enseignes'
        )

        # Filtre par statut
        est_actif = self.request.GET.get('est_actif')
        if est_actif:
            queryset = queryset.filter(est_actif=est_actif == 'True')

        # Filtre par type
        est_permanent = self.request.GET.get('est_permanent')
        if est_permanent:
            queryset = queryset.filter(
                profil_enseignant__est_permanent=est_permanent == 'True'
            )

        # Filtre par spécialisation
        specialisation = self.request.GET.get('specialisation')
        if specialisation:
            queryset = queryset.filter(
                profil_enseignant__specialisation__icontains=specialisation
            )

        # Recherche textuelle
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(matricule__icontains=search) |
                Q(email__icontains=search) |
                Q(profil_enseignant__specialisation__icontains=search)
            )

        # Tri
        sort_by = self.request.GET.get('sort', '-date_creation')
        valid_sorts = [
            'nom', '-nom', 'prenom', '-prenom',
            'date_creation', '-date_creation',
            'email', '-email'
        ]
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-date_creation')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        # Statistiques
        context['stats'] = {
            'total': Utilisateur.objects.filter(
                departement=departement,
                role='ENSEIGNANT'
            ).count(),
            'actifs': Utilisateur.objects.filter(
                departement=departement,
                role='ENSEIGNANT',
                est_actif=True
            ).count(),
            'permanents': Utilisateur.objects.filter(
                departement=departement,
                role='ENSEIGNANT',
                profil_enseignant__est_permanent=True
            ).count(),
            'vacataires': Utilisateur.objects.filter(
                departement=departement,
                role='ENSEIGNANT',
                profil_enseignant__est_permanent=False
            ).count(),
        }

        # Filtres actifs
        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'est_actif': self.request.GET.get('est_actif', ''),
            'est_permanent': self.request.GET.get('est_permanent', ''),
            'specialisation': self.request.GET.get('specialisation', ''),
            'sort': self.request.GET.get('sort', '-date_creation'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        # Spécialisations disponibles
        context['specialisations'] = ProfilEnseignant.objects.filter(
            utilisateur__departement=departement
        ).exclude(
            specialisation__isnull=True
        ).exclude(
            specialisation=''
        ).values_list(
            'specialisation', flat=True
        ).distinct().order_by('specialisation')

        context['departement'] = departement
        context['page_title'] = f"Enseignants - {departement.nom}"

        return context

class DepartmentHeadStudentsView(LoginRequiredMixin, ListView):
    """Gestion des étudiants du département - Vue optimisée"""
    model = Utilisateur
    template_name = 'dashboard/department_head/students.html'
    context_object_name = 'students'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Utilisateur.objects.filter(
            departement=departement,
            role='APPRENANT'
        ).select_related(
            'profil_apprenant__classe_actuelle',
            'profil_apprenant__classe_actuelle__niveau__filiere'
        )

        # Filtre par filière
        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(
                profil_apprenant__classe_actuelle__niveau__filiere_id=filiere
            )

        # Filtre par classe
        classe = self.request.GET.get('classe')
        if classe:
            queryset = queryset.filter(
                profil_apprenant__classe_actuelle_id=classe
            )

        # Filtre par statut de paiement
        statut_paiement = self.request.GET.get('statut_paiement')
        if statut_paiement:
            queryset = queryset.filter(
                profil_apprenant__statut_paiement=statut_paiement
            )

        # Filtre par statut actif
        est_actif = self.request.GET.get('est_actif')
        if est_actif:
            queryset = queryset.filter(est_actif=est_actif == 'True')

        # Recherche textuelle
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(matricule__icontains=search) |
                Q(email__icontains=search)
            )

        # Tri
        sort_by = self.request.GET.get('sort', '-date_creation')
        valid_sorts = [
            'nom', '-nom', 'prenom', '-prenom',
            'date_creation', '-date_creation',
            'matricule', '-matricule'
        ]
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-date_creation')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        # Statistiques
        context['stats'] = {
            'total': Utilisateur.objects.filter(
                departement=departement,
                role='APPRENANT'
            ).count(),
            'actifs': Utilisateur.objects.filter(
                departement=departement,
                role='APPRENANT',
                est_actif=True
            ).count(),
            'paiement_complet': Utilisateur.objects.filter(
                departement=departement,
                role='APPRENANT',
                profil_apprenant__statut_paiement='COMPLETE'
            ).count(),
            'paiement_partiel': Utilisateur.objects.filter(
                departement=departement,
                role='APPRENANT',
                profil_apprenant__statut_paiement='PARTIAL'
            ).count(),
        }

        # Filtres
        context['filieres'] = Filiere.objects.filter(
            departement=departement,
            est_active=True
        ).order_by('nom')

        context['classes'] = Classe.objects.filter(
            niveau__filiere__departement=departement,
            est_active=True
        ).select_related('niveau__filiere').order_by('nom')

        context['statuts_paiement'] = ProfilApprenant._meta.get_field('statut_paiement').choices

        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'filiere': self.request.GET.get('filiere', ''),
            'classe': self.request.GET.get('classe', ''),
            'statut_paiement': self.request.GET.get('statut_paiement', ''),
            'est_actif': self.request.GET.get('est_actif', ''),
            'sort': self.request.GET.get('sort', '-date_creation'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        context['departement'] = departement
        context['page_title'] = f"Étudiants - {departement.nom}"

        return context

class DepartmentHeadCandidaturesView(LoginRequiredMixin, ListView):
    """Gestion des candidatures du département"""
    template_name = 'dashboard/department_head/candidatures.html'
    context_object_name = 'candidatures'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Candidature.objects.filter(
            filiere__departement=departement
        ).select_related(
            'filiere',
            'niveau',
            'annee_academique',
            'examine_par'
        ).annotate(
            nombre_documents=Count('documents')
        )

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(filiere_id=filiere)

        niveau = self.request.GET.get('niveau')
        if niveau:
            queryset = queryset.filter(niveau_id=niveau)

        annee = self.request.GET.get('annee_academique')
        if annee:
            queryset = queryset.filter(annee_academique_id=annee)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero_candidature__icontains=search) |
                Q(nom__icontains=search) |
                Q(prenom__icontains=search) |
                Q(email__icontains=search)
            )

        # Tri
        sort_by = self.request.GET.get('sort', '-date_soumission')
        valid_sorts = [
            'date_soumission', '-date_soumission',
            'nom', '-nom',
            'statut', '-statut'
        ]
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-date_soumission')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        # Statistiques
        context['stats'] = {
            'total': self.get_queryset().count(),
            'en_attente': self.get_queryset().filter(statut='EN_ATTENTE').count(),
            'en_cours': self.get_queryset().filter(statut='EN_COURS_EXAMEN').count(),
            'approuvees': self.get_queryset().filter(statut='APPROUVEE').count(),
            'rejetees': self.get_queryset().filter(statut='REJETEE').count(),
        }

        context['filieres'] = Filiere.objects.filter(
            departement=departement,
            est_active=True
        ).order_by('nom')

        context['niveaux'] = Niveau.objects.filter(
            filiere__departement=departement,
            est_actif=True
        ).select_related('filiere').order_by('ordre')

        context['annees_academiques'] = AnneeAcademique.objects.filter(
            etablissement=departement.etablissement
        ).order_by('-nom')

        context['statuts'] = Candidature.STATUTS_CANDIDATURE

        context['current_filters'] = {
            'statut': self.request.GET.get('statut', ''),
            'filiere': self.request.GET.get('filiere', ''),
            'niveau': self.request.GET.get('niveau', ''),
            'annee_academique': self.request.GET.get('annee_academique', ''),
            'search': self.request.GET.get('search', ''),
            'sort': self.request.GET.get('sort', '-date_soumission'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        context['departement'] = departement
        context['page_title'] = f"Candidatures - {departement.nom}"

        return context

class DepartmentHeadInscriptionsView(LoginRequiredMixin, ListView):
    """Gestion des inscriptions du département"""
    template_name = 'dashboard/department_head/inscriptions.html'
    context_object_name = 'inscriptions'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Inscription.objects.filter(
            candidature__filiere__departement=departement
        ).select_related(
            'apprenant',
            'candidature__filiere',
            'candidature__niveau',
            'classe_assignee',
            'cree_par'
        )

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        statut_paiement = self.request.GET.get('statut_paiement')
        if statut_paiement:
            queryset = queryset.filter(statut_paiement=statut_paiement)

        classe = self.request.GET.get('classe')
        if classe:
            queryset = queryset.filter(classe_assignee_id=classe)

        annee = self.request.GET.get('annee_academique')
        if annee:
            queryset = queryset.filter(candidature__annee_academique_id=annee)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero_inscription__icontains=search) |
                Q(apprenant__nom__icontains=search) |
                Q(apprenant__prenom__icontains=search) |
                Q(candidature__numero_candidature__icontains=search)
            )

        # Tri
        sort_by = self.request.GET.get('sort', '-date_inscription')
        valid_sorts = [
            'date_inscription', '-date_inscription',
            'apprenant__nom', '-apprenant__nom',
            'statut', '-statut'
        ]
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-date_inscription')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        # Statistiques
        context['stats'] = {
            'total': self.get_queryset().count(),
            'actives': self.get_queryset().filter(statut='ACTIVE').count(),
            'paiement_complet': self.get_queryset().filter(statut_paiement='COMPLETE').count(),
            'paiement_partiel': self.get_queryset().filter(statut_paiement='PARTIAL').count(),
        }

        context['classes'] = Classe.objects.filter(
            niveau__filiere__departement=departement,
            est_active=True
        ).select_related('niveau__filiere').order_by('nom')

        context['annees_academiques'] = AnneeAcademique.objects.filter(
            etablissement=departement.etablissement
        ).order_by('-nom')

        context['statuts'] = Inscription.STATUTS_INSCRIPTION
        context['statuts_paiement'] = Inscription.STATUTS_PAIEMENT

        context['current_filters'] = {
            'statut': self.request.GET.get('statut', ''),
            'statut_paiement': self.request.GET.get('statut_paiement', ''),
            'classe': self.request.GET.get('classe', ''),
            'annee_academique': self.request.GET.get('annee_academique', ''),
            'search': self.request.GET.get('search', ''),
            'sort': self.request.GET.get('sort', '-date_inscription'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        context['departement'] = departement
        context['page_title'] = f"Inscriptions - {departement.nom}"

        return context

class DepartmentHeadPaiementsView(LoginRequiredMixin, ListView):
    """Gestion des paiements du département"""
    template_name = 'dashboard/department_head/paiements.html'
    context_object_name = 'paiements'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Paiement.objects.filter(
            inscription_paiement__inscription__candidature__filiere__departement=departement
        ).select_related(
            'inscription_paiement__inscription__apprenant',
            'tranche',
            'traite_par'
        )

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        methode = self.request.GET.get('methode_paiement')
        if methode:
            queryset = queryset.filter(methode_paiement=methode)

        date_debut = self.request.GET.get('date_debut')
        if date_debut:
            queryset = queryset.filter(date_paiement__gte=date_debut)

        date_fin = self.request.GET.get('date_fin')
        if date_fin:
            queryset = queryset.filter(date_paiement__lte=date_fin)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero_transaction__icontains=search) |
                Q(reference_externe__icontains=search) |
                Q(inscription_paiement__inscription__apprenant__nom__icontains=search) |
                Q(inscription_paiement__inscription__apprenant__prenom__icontains=search)
            )

        # Tri
        sort_by = self.request.GET.get('sort', '-date_paiement')
        valid_sorts = [
            'date_paiement', '-date_paiement',
            'montant', '-montant',
            'statut', '-statut'
        ]
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-date_paiement')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        # Statistiques
        context['stats'] = {
            'total': queryset.count(),
            'total_montant': queryset.filter(statut='CONFIRME').aggregate(
                total=Sum('montant')
            )['total'] or Decimal('0.00'),
            'en_attente': queryset.filter(statut='EN_ATTENTE').count(),
            'confirmes': queryset.filter(statut='CONFIRME').count(),
        }

        context['statuts'] = Paiement.STATUTS_PAIEMENT
        context['methodes'] = Paiement.METHODES_PAIEMENT

        context['current_filters'] = {
            'statut': self.request.GET.get('statut', ''),
            'methode_paiement': self.request.GET.get('methode_paiement', ''),
            'date_debut': self.request.GET.get('date_debut', ''),
            'date_fin': self.request.GET.get('date_fin', ''),
            'search': self.request.GET.get('search', ''),
            'sort': self.request.GET.get('sort', '-date_paiement'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        context['departement'] = self.request.user.departement
        context['page_title'] = f"Paiements - {self.request.user.departement.nom}"

        return context

class DepartmentHeadFilieresView(LoginRequiredMixin, ListView):
    """Gestion des filières du département"""
    template_name = 'dashboard/department_head/filieres.html'
    context_object_name = 'filieres'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Filiere.objects.filter(
            departement=departement
        ).annotate(
            nombre_niveaux=Count('niveaux', filter=Q(niveaux__est_actif=True)),
            nombre_etudiants=Count(
                'niveaux__classes__apprenants',
                filter=Q(niveaux__classes__apprenants__utilisateur__est_actif=True),
                distinct=True
            )
        )

        # Filtres
        type_filiere = self.request.GET.get('type_filiere')
        if type_filiere:
            queryset = queryset.filter(type_filiere=type_filiere)

        est_active = self.request.GET.get('est_active')
        if est_active:
            queryset = queryset.filter(est_active=est_active == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search) |
                Q(nom_diplome__icontains=search)
            )

        # Tri
        sort_by = self.request.GET.get('sort', 'nom')
        valid_sorts = ['nom', '-nom', 'code', '-code', 'nombre_etudiants', '-nombre_etudiants']
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('nom')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        # Statistiques
        context['stats'] = {
            'total': self.get_queryset().count(),
            'actives': self.get_queryset().filter(est_active=True).count(),
            'inactives': self.get_queryset().filter(est_active=False).count(),
        }

        context['types_filiere'] = Filiere.TYPES_FILIERE

        context['current_filters'] = {
            'type_filiere': self.request.GET.get('type_filiere', ''),
            'est_active': self.request.GET.get('est_active', ''),
            'search': self.request.GET.get('search', ''),
            'sort': self.request.GET.get('sort', 'nom'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        context['departement'] = departement
        context['page_title'] = f"Filières - {departement.nom}"

        return context

class DepartmentHeadNiveauxView(LoginRequiredMixin, ListView):
    """Gestion des niveaux du département"""
    template_name = 'dashboard/department_head/niveaux.html'
    context_object_name = 'niveaux'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Niveau.objects.filter(
            filiere__departement=departement
        ).select_related(
            'filiere'
        ).annotate(
            nombre_classes=Count('classes', filter=Q(classes__est_active=True)),
            nombre_etudiants=Count(
                'classes__apprenants',
                filter=Q(classes__apprenants__utilisateur__est_actif=True),
                distinct=True
            )
        )

        # Filtres
        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(filiere_id=filiere)

        est_actif = self.request.GET.get('est_actif')
        if est_actif:
            queryset = queryset.filter(est_actif=est_actif == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search) |
                Q(filiere__nom__icontains=search)
            )

        # Tri
        sort_by = self.request.GET.get('sort', 'ordre')
        valid_sorts = [
            'ordre', '-ordre',
            'nom', '-nom',
            'nombre_etudiants', '-nombre_etudiants'
        ]
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('filiere__nom', 'ordre')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        # Statistiques
        context['stats'] = {
            'total': self.get_queryset().count(),
            'actifs': self.get_queryset().filter(est_actif=True).count(),
            'total_classes': self.get_queryset().aggregate(
                total=Sum('nombre_classes')
            )['total'] or 0,
        }

        context['filieres'] = Filiere.objects.filter(
            departement=departement,
            est_active=True
        ).order_by('nom')

        context['current_filters'] = {
            'filiere': self.request.GET.get('filiere', ''),
            'est_actif': self.request.GET.get('est_actif', ''),
            'search': self.request.GET.get('search', ''),
            'sort': self.request.GET.get('sort', 'ordre'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        context['departement'] = departement
        context['page_title'] = f"Niveaux - {departement.nom}"

        return context

class DepartmentHeadClassesView(LoginRequiredMixin, ListView):
    """Gestion des classes du département"""
    template_name = 'dashboard/department_head/classes.html'
    context_object_name = 'classes'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Classe.objects.filter(
            niveau__filiere__departement=departement
        ).select_related(
            'niveau__filiere',
            'annee_academique',
            'professeur_principal',
            'salle_principale'
        ).annotate(
            nombre_etudiants=Count(
                'apprenants',
                filter=Q(apprenants__utilisateur__est_actif=True)
            )
        )

        # Filtres
        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(niveau__filiere_id=filiere)

        niveau = self.request.GET.get('niveau')
        if niveau:
            queryset = queryset.filter(niveau_id=niveau)

        annee_academique = self.request.GET.get('annee_academique')
        if annee_academique:
            queryset = queryset.filter(annee_academique_id=annee_academique)

        est_active = self.request.GET.get('est_active')
        if est_active:
            queryset = queryset.filter(est_active=est_active == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search)
            )

        # Tri
        sort_by = self.request.GET.get('sort', 'nom')
        valid_sorts = ['nom', '-nom', 'nombre_etudiants', '-nombre_etudiants']
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('niveau__filiere__nom', 'nom')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        # Statistiques
        context['stats'] = {
            'total': self.get_queryset().count(),
            'actives': self.get_queryset().filter(est_active=True).count(),
            'total_etudiants': self.get_queryset().aggregate(
                total=Sum('nombre_etudiants')
            )['total'] or 0,
        }

        context['filieres'] = Filiere.objects.filter(
            departement=departement,
            est_active=True
        ).order_by('nom')

        context['niveaux'] = Niveau.objects.filter(
            filiere__departement=departement,
            est_actif=True
        ).select_related('filiere').order_by('ordre')

        context['annees_academiques'] = AnneeAcademique.objects.filter(
            etablissement=departement.etablissement
        ).order_by('-nom')

        context['current_filters'] = {
            'filiere': self.request.GET.get('filiere', ''),
            'niveau': self.request.GET.get('niveau', ''),
            'annee_academique': self.request.GET.get('annee_academique', ''),
            'est_active': self.request.GET.get('est_active', ''),
            'search': self.request.GET.get('search', ''),
            'sort': self.request.GET.get('sort', 'nom'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        context['departement'] = departement
        context['page_title'] = f"Classes - {departement.nom}"

        return context

class DepartmentHeadModulesView(LoginRequiredMixin, ListView):
    """Gestion des modules du département"""
    template_name = 'dashboard/department_head/modules.html'
    context_object_name = 'modules'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Module.objects.filter(
            niveau__filiere__departement=departement
        ).select_related(
            'niveau__filiere',
            'coordinateur'
        ).annotate(
            nombre_matieres=Count('matieres'),
            total_heures=Sum(
                F('matieres__heures_cours_magistral') +
                F('matieres__heures_travaux_diriges') +
                F('matieres__heures_travaux_pratiques'),
                output_field=IntegerField()
            ),
            credits_ects_total=Sum('matieres__credits_ects')
        )

        # Filtres
        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(niveau__filiere_id=filiere)

        niveau = self.request.GET.get('niveau')
        if niveau:
            queryset = queryset.filter(niveau_id=niveau)

        actif = self.request.GET.get('actif')
        if actif:
            queryset = queryset.filter(actif=actif == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search)
            )

        # Tri
        sort_by = self.request.GET.get('sort', 'niveau__ordre')
        valid_sorts = ['nom', '-nom', 'niveau__ordre', '-niveau__ordre', 'nombre_matieres', '-nombre_matieres']
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by, 'nom')
        else:
            queryset = queryset.order_by('niveau__ordre', 'nom')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        # Statistiques
        context['stats'] = {
            'total': self.get_queryset().count(),
            'actifs': self.get_queryset().filter(actif=True).count(),
            'total_matieres': self.get_queryset().aggregate(
                total=Sum('nombre_matieres')
            )['total'] or 0,
        }

        context['filieres'] = Filiere.objects.filter(
            departement=departement,
            est_active=True
        ).order_by('nom')

        context['niveaux'] = Niveau.objects.filter(
            filiere__departement=departement,
            est_actif=True
        ).select_related('filiere').order_by('ordre')

        context['current_filters'] = {
            'filiere': self.request.GET.get('filiere', ''),
            'niveau': self.request.GET.get('niveau', ''),
            'actif': self.request.GET.get('actif', ''),
            'search': self.request.GET.get('search', ''),
            'sort': self.request.GET.get('sort', 'niveau__ordre'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        context['departement'] = departement
        context['page_title'] = f"Modules - {departement.nom}"

        return context

class DepartmentHeadMatieresView(LoginRequiredMixin, ListView):
    """Gestion des matières du département"""
    template_name = 'dashboard/department_head/matieres.html'
    context_object_name = 'matieres'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Matiere.objects.filter(
            niveau__filiere__departement=departement
        ).select_related(
            'niveau__filiere',
            'module',
            'enseignant_responsable'
        )

        # Filtres
        niveau = self.request.GET.get('niveau')
        if niveau:
            queryset = queryset.filter(niveau_id=niveau)

        module = self.request.GET.get('module')
        if module == 'sans_module':
            queryset = queryset.filter(module__isnull=True)
        elif module:
            queryset = queryset.filter(module_id=module)

        actif = self.request.GET.get('actif')
        if actif:
            queryset = queryset.filter(actif=actif == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search)
            )

        # Tri
        sort_by = self.request.GET.get('sort', 'niveau__ordre')
        valid_sorts = [
            'nom', '-nom',
            'code', '-code',
            'niveau__ordre', '-niveau__ordre'
        ]
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by, 'nom')
        else:
            queryset = queryset.order_by('niveau__ordre', 'nom')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        # Statistiques
        context['stats'] = {
            'total': self.get_queryset().count(),
            'actives': self.get_queryset().filter(actif=True).count(),
        }

        context['niveaux'] = Niveau.objects.filter(
            filiere__departement=departement,
            est_actif=True
        ).select_related('filiere').order_by('ordre')

        context['modules'] = Module.objects.filter(
            niveau__filiere__departement=departement,
            actif=True
        ).select_related('niveau__filiere').order_by('nom')

        context['current_filters'] = {
            'niveau': self.request.GET.get('niveau', ''),
            'module': self.request.GET.get('module', ''),
            'actif': self.request.GET.get('actif', ''),
            'search': self.request.GET.get('search', ''),
            'sort': self.request.GET.get('sort', 'niveau__ordre'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        context['departement'] = departement
        context['page_title'] = f"Matières - {departement.nom}"

        return context

class DepartmentHeadCoursesView(LoginRequiredMixin, ListView):
    """Gestion des cours du département"""
    template_name = 'dashboard/department_head/courses.html'
    context_object_name = 'courses'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')

        if not request.user.departement:
            messages.error(request, "Aucun département assigné")
            return redirect('dashboard:redirect')

        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Cours.objects.filter(
            matiere__niveau__filiere__departement=departement
        ).select_related(
            'matiere__niveau__filiere',
            'classe__niveau',
            'enseignant',
            'periode_academique',
            'salle'
        )

        # Filtres
        matiere_id = self.request.GET.get('matiere')
        if matiere_id:
            queryset = queryset.filter(matiere_id=matiere_id)

        classe_id = self.request.GET.get('classe')
        if classe_id:
            queryset = queryset.filter(classe_id=classe_id)

        enseignant_id = self.request.GET.get('enseignant')
        if enseignant_id:
            queryset = queryset.filter(enseignant_id=enseignant_id)

        date_debut = self.request.GET.get('date_debut')
        if date_debut:
            queryset = queryset.filter(date_prevue__gte=date_debut)

        date_fin = self.request.GET.get('date_fin')
        if date_fin:
            queryset = queryset.filter(date_prevue__lte=date_fin)

        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        type_cours = self.request.GET.get('type_cours')
        if type_cours:
            queryset = queryset.filter(type_cours=type_cours)

        # Tri
        sort_by = self.request.GET.get('sort', '-date_prevue')
        valid_sorts = [
            'date_prevue', '-date_prevue',
            'matiere__nom', '-matiere__nom',
            'classe__nom', '-classe__nom'
        ]
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-date_prevue', '-heure_debut_prevue')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        context['matieres'] = Matiere.objects.filter(
            niveau__filiere__departement=departement,
            actif=True
        ).select_related('niveau__filiere').order_by('nom')

        context['classes'] = Classe.objects.filter(
            niveau__filiere__departement=departement,
            est_active=True
        ).select_related('niveau__filiere').order_by('nom')

        context['enseignants'] = Utilisateur.objects.filter(
            departement=departement,
            role='ENSEIGNANT',
            est_actif=True
        ).order_by('nom', 'prenom')

        context['statuts'] = StatutCours.choices
        context['types_cours'] = TypeCours.choices

        context['current_filters'] = {
            'matiere': self.request.GET.get('matiere', ''),
            'classe': self.request.GET.get('classe', ''),
            'enseignant': self.request.GET.get('enseignant', ''),
            'date_debut': self.request.GET.get('date_debut', ''),
            'date_fin': self.request.GET.get('date_fin', ''),
            'statut': self.request.GET.get('statut', ''),
            'type_cours': self.request.GET.get('type_cours', ''),
            'sort': self.request.GET.get('sort', '-date_prevue'),
            'per_page': self.request.GET.get('per_page', '20'),
        }

        context['departement'] = departement
        context['page_title'] = f"Cours - {departement.nom}"

        return context

class DepartmentHeadCahiersTexteView(LoginRequiredMixin, ListView):
    """Gestion des cahiers de texte du département"""
    template_name = 'dashboard/department_head/cahiers_texte.html'
    context_object_name = 'cahiers'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement
        queryset = CahierTexte.objects.select_related(
            'cours__matiere__niveau__filiere',
            'cours__classe',
            'cours__enseignant',
            'rempli_par'
        ).filter(
            cours__matiere__niveau__filiere__departement=departement
        )

        # Filtres
        classe_id = self.request.GET.get('classe')
        if classe_id:
            queryset = queryset.filter(cours__classe_id=classe_id)

        enseignant_id = self.request.GET.get('enseignant')
        if enseignant_id:
            queryset = queryset.filter(cours__enseignant_id=enseignant_id)

        matiere_id = self.request.GET.get('matiere')
        if matiere_id:
            queryset = queryset.filter(cours__matiere_id=matiere_id)

        date_debut = self.request.GET.get('date_debut')
        if date_debut:
            queryset = queryset.filter(cours__date_prevue__gte=date_debut)

        date_fin = self.request.GET.get('date_fin')
        if date_fin:
            queryset = queryset.filter(cours__date_prevue__lte=date_fin)

        return queryset.order_by('-cours__date_prevue')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        context['classes'] = Classe.objects.filter(
            niveau__filiere__departement=departement, est_active=True
        )
        context['enseignants'] = Utilisateur.objects.filter(
            departement=departement, role='ENSEIGNANT', est_actif=True
        )
        context['matieres'] = Matiere.objects.filter(
            niveau__filiere__departement=departement, actif=True
        )
        context['current_filters'] = {
            'classe': self.request.GET.get('classe', ''),
            'enseignant': self.request.GET.get('enseignant', ''),
            'matiere': self.request.GET.get('matiere', ''),
            'date_debut': self.request.GET.get('date_debut', ''),
            'date_fin': self.request.GET.get('date_fin', ''),
        }
        context['departement'] = departement

        return context

class DepartmentHeadEvaluationsView(LoginRequiredMixin, ListView):
    """Gestion des évaluations du département"""
    template_name = 'dashboard/department_head/evaluations.html'
    context_object_name = 'evaluations'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        departement = self.request.user.departement

        queryset = Evaluation.objects.filter(
            matiere__niveau__filiere__departement=departement
        ).select_related(
            'enseignant',
            'matiere',
            'matiere__niveau__filiere'
        ).prefetch_related('classes').annotate(
            nombre_compositions=Count('compositions')
        )

        # Filtres
        type_eval = self.request.GET.get('type_evaluation')
        if type_eval:
            queryset = queryset.filter(type_evaluation=type_eval)

        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        enseignant = self.request.GET.get('enseignant')
        if enseignant:
            queryset = queryset.filter(enseignant_id=enseignant)

        matiere = self.request.GET.get('matiere')
        if matiere:
            queryset = queryset.filter(matiere_id=matiere)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) |
                Q(matiere__nom__icontains=search) |
                Q(enseignant__prenom__icontains=search) |
                Q(enseignant__nom__icontains=search)
            )

        return queryset.order_by('-date_debut')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        context['types_evaluation'] = Evaluation.TYPE_EVALUATION
        context['statuts'] = Evaluation.STATUT
        context['enseignants'] = Utilisateur.objects.filter(
            departement=departement, role='ENSEIGNANT', est_actif=True
        )
        context['matieres'] = Matiere.objects.filter(
            niveau__filiere__departement=departement, actif=True
        )
        context['current_filters'] = {
            'type_evaluation': self.request.GET.get('type_evaluation', ''),
            'statut': self.request.GET.get('statut', ''),
            'enseignant': self.request.GET.get('enseignant', ''),
            'matiere': self.request.GET.get('matiere', ''),
            'search': self.request.GET.get('search', ''),
        }
        context['departement'] = departement

        return context

class DepartmentHeadEmploiDuTempsView(LoginRequiredMixin, ListView):
    """Gestion des emplois du temps du département"""
    template_name = 'dashboard/department_head/emplois_du_temps.html'
    context_object_name = 'emplois_du_temps'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        departement = self.request.user.departement
        queryset = EmploiDuTemps.objects.select_related(
            'classe__niveau__filiere',
            'enseignant',
            'periode_academique',
            'cree_par'
        ).prefetch_related('creneaux').filter(
            Q(classe__niveau__filiere__departement=departement) |
            Q(enseignant__departement=departement)
        )

        # Filtres
        filter_type = self.request.GET.get('type', 'classe')
        if filter_type == 'classe':
            classe_id = self.request.GET.get('classe')
            if classe_id:
                queryset = queryset.filter(classe_id=classe_id)
        else:
            enseignant_id = self.request.GET.get('enseignant')
            if enseignant_id:
                queryset = queryset.filter(enseignant_id=enseignant_id)

        periode_id = self.request.GET.get('periode')
        if periode_id:
            queryset = queryset.filter(periode_academique_id=periode_id)

        statut = self.request.GET.get('statut')
        if statut == 'publie':
            queryset = queryset.filter(publie=True)
        elif statut == 'non_publie':
            queryset = queryset.filter(publie=False)
        elif statut == 'actuel':
            queryset = queryset.filter(actuel=True)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        context['classes'] = Classe.objects.filter(
            niveau__filiere__departement=departement, est_active=True
        ).select_related('niveau__filiere')
        context['enseignants'] = Utilisateur.objects.filter(
            departement=departement, role='ENSEIGNANT', est_actif=True
        )
        context['periodes'] = PeriodeAcademique.objects.filter(
            etablissement=departement.etablissement, est_active=True
        )
        context['nombre_publies'] = self.get_queryset().filter(publie=True).count()
        context['current_filters'] = {
            'type': self.request.GET.get('type', 'classe'),
            'classe': self.request.GET.get('classe', ''),
            'enseignant': self.request.GET.get('enseignant', ''),
            'periode': self.request.GET.get('periode', ''),
            'statut': self.request.GET.get('statut', ''),
        }
        context['departement'] = departement

        return context

class DepartmentHeadRessourcesView(LoginRequiredMixin, ListView):
    """Gestion des ressources du département"""
    template_name = 'dashboard/department_head/ressources.html'
    context_object_name = 'ressources'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 20)
        try:
            per_page = int(per_page)
            if per_page not in [10, 20, 50, 100]:
                per_page = 20
        except (ValueError, TypeError):
            per_page = 20
        return per_page

    def get_queryset(self):
        departement = self.request.user.departement
        queryset = Ressource.objects.select_related(
            'cours__matiere',
            'cours__classe',
            'cours__enseignant'
        ).filter(
            cours__matiere__niveau__filiere__departement=departement
        )

        # Filtres
        type_ressource = self.request.GET.get('type')
        if type_ressource:
            queryset = queryset.filter(type_ressource=type_ressource)

        cours_id = self.request.GET.get('cours')
        if cours_id:
            queryset = queryset.filter(cours_id=cours_id)

        enseignant_id = self.request.GET.get('enseignant')
        if enseignant_id:
            queryset = queryset.filter(cours__enseignant_id=enseignant_id)

        public = self.request.GET.get('public')
        if public:
            queryset = queryset.filter(public=public == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) | Q(description__icontains=search)
            )

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        context['types_ressource'] = Ressource.TYPES_RESSOURCE
        context['enseignants'] = Utilisateur.objects.filter(
            departement=departement, role='ENSEIGNANT', est_actif=True
        )
        context['current_filters'] = {
            'type': self.request.GET.get('type', ''),
            'cours': self.request.GET.get('cours', ''),
            'enseignant': self.request.GET.get('enseignant', ''),
            'public': self.request.GET.get('public', ''),
            'search': self.request.GET.get('search', ''),
        }

        # Stats
        queryset = self.get_queryset()
        context['total_telechargements'] = queryset.aggregate(Sum('nombre_telechargements'))['nombre_telechargements__sum'] or 0
        context['total_vues'] = queryset.aggregate(Sum('nombre_vues'))['nombre_vues__sum'] or 0
        context['departement'] = departement

        return context

class DepartmentHeadReportsView(LoginRequiredMixin, TemplateView):
    """Rapports du département"""
    template_name = 'dashboard/department_head/reports.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        if departement:
            context.update({
                'departement': departement,
                'statistiques_departement': self.get_statistiques_departement(departement),
            })

        return context

    def get_statistiques_departement(self, departement):
        return {
            'total_enseignants': Utilisateur.objects.filter(
                departement=departement,
                role='ENSEIGNANT'
            ).count(),
            'total_apprenants': Utilisateur.objects.filter(
                departement=departement,
                role='APPRENANT'
            ).count(),
            'total_cours': Cours.objects.filter(
                matiere__modules__filiere__departement=departement
            ).count(),
        }

# ================================
# VUES ENSEIGNANT
# ================================
class TeacherDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord de l'enseignant"""
    template_name = 'dashboard/teacher/index.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Statistiques
        context['total_cours'] = Cours.objects.filter(
            enseignant=enseignant, actif=True
        ).count()

        context['cours_aujourdhui'] = Cours.objects.filter(
            enseignant=enseignant,
            date_prevue=timezone.now().date(),
            actif=True
        ).count()

        context['evaluations_en_cours'] = Evaluation.objects.filter(
            enseignant=enseignant,
            statut='EN_COURS'
        ).count()

        context['corrections_en_attente'] = Evaluation.objects.filter(
            enseignant=enseignant,
            compositions__statut__in=['SOUMISE', 'EN_RETARD']
        ).distinct().count()

        # Cours à venir
        context['cours_a_venir'] = Cours.objects.filter(
            enseignant=enseignant,
            date_prevue__gte=timezone.now().date(),
            actif=True
        ).select_related('matiere', 'classe', 'salle').order_by('date_prevue', 'heure_debut_prevue')[:5]

        # Évaluations récentes
        context['evaluations_recentes'] = Evaluation.objects.filter(
            enseignant=enseignant
        ).select_related('matiere').order_by('-date_debut')[:5]

        return context

class TeacherCoursesView(LoginRequiredMixin, ListView):
    """Mes cours (enseignant)"""
    template_name = 'dashboard/teacher/courses.html'
    context_object_name = 'courses'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Cours.objects.filter(
            enseignant=self.request.user
        ).select_related(
            'matiere__niveau__filiere',
            'classe',
            'salle'
        )

        # Filtres
        matiere_id = self.request.GET.get('matiere')
        if matiere_id:
            queryset = queryset.filter(matiere_id=matiere_id)

        classe_id = self.request.GET.get('classe')
        if classe_id:
            queryset = queryset.filter(classe_id=classe_id)

        date_debut = self.request.GET.get('date_debut')
        if date_debut:
            queryset = queryset.filter(date_prevue__gte=date_debut)

        date_fin = self.request.GET.get('date_fin')
        if date_fin:
            queryset = queryset.filter(date_prevue__lte=date_fin)

        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        return queryset.order_by('-date_prevue', '-heure_debut_prevue')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        context['matieres'] = Matiere.objects.filter(
            enseignant_responsable=enseignant, actif=True
        )
        context['classes'] = Classe.objects.filter(
            cours__enseignant=enseignant
        ).distinct()
        context['statuts'] = StatutCours.choices
        context['current_filters'] = {
            'matiere': self.request.GET.get('matiere', ''),
            'classe': self.request.GET.get('classe', ''),
            'date_debut': self.request.GET.get('date_debut', ''),
            'date_fin': self.request.GET.get('date_fin', ''),
            'statut': self.request.GET.get('statut', ''),
        }

        return context

class TeacherCahiersTexteView(LoginRequiredMixin, ListView):
    """Cahiers de texte de l'enseignant"""
    template_name = 'dashboard/teacher/cahiers_texte.html'
    context_object_name = 'cahiers'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = CahierTexte.objects.filter(
            cours__enseignant=self.request.user
        ).select_related(
            'cours__matiere',
            'cours__classe',
            'rempli_par'
        )

        # Filtres
        classe_id = self.request.GET.get('classe')
        if classe_id:
            queryset = queryset.filter(cours__classe_id=classe_id)

        date_debut = self.request.GET.get('date_debut')
        if date_debut:
            queryset = queryset.filter(cours__date_prevue__gte=date_debut)

        date_fin = self.request.GET.get('date_fin')
        if date_fin:
            queryset = queryset.filter(cours__date_prevue__lte=date_fin)

        return queryset.order_by('-cours__date_prevue')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        context['classes'] = Classe.objects.filter(
            cours__enseignant=enseignant
        ).distinct()
        context['current_filters'] = {
            'classe': self.request.GET.get('classe', ''),
            'date_debut': self.request.GET.get('date_debut', ''),
            'date_fin': self.request.GET.get('date_fin', ''),
        }

        return context

class TeacherEvaluationsView(LoginRequiredMixin, ListView):
    """Mes évaluations (enseignant)"""
    template_name = 'dashboard/teacher/evaluations.html'
    context_object_name = 'evaluations'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Evaluation.objects.filter(
            enseignant=self.request.user
        ).select_related(
            'matiere__niveau__filiere'
        ).prefetch_related('classes').annotate(
            nombre_compositions=Count('compositions'),
            nombre_corrections=Count('compositions', filter=Q(compositions__statut='CORRIGEE'))
        )

        # Filtres
        type_eval = self.request.GET.get('type_evaluation')
        if type_eval:
            queryset = queryset.filter(type_evaluation=type_eval)

        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        matiere = self.request.GET.get('matiere')
        if matiere:
            queryset = queryset.filter(matiere_id=matiere)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) |
                Q(matiere__nom__icontains=search)
            )

        return queryset.order_by('-date_debut')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        context['types_evaluation'] = Evaluation.TYPE_EVALUATION
        context['statuts'] = Evaluation.STATUT
        context['matieres'] = Matiere.objects.filter(
            enseignant_responsable=enseignant, actif=True
        )
        context['current_filters'] = {
            'type_evaluation': self.request.GET.get('type_evaluation', ''),
            'statut': self.request.GET.get('statut', ''),
            'matiere': self.request.GET.get('matiere', ''),
            'search': self.request.GET.get('search', ''),
        }

        return context

class TeacherCorrectionView(LoginRequiredMixin, ListView):
    """Corriger une évaluation"""
    model = Evaluation
    template_name = 'dashboard/teacher/correction.html'
    context_object_name = 'evaluation'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Evaluation.objects.filter(enseignant=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evaluation = self.object

        context['compositions'] = evaluation.compositions.select_related(
            'apprenant'
        ).order_by('apprenant__nom', 'apprenant__prenom')

        return context

class TeacherPresencesView(LoginRequiredMixin, ListView):
    """Gestion des présences"""
    template_name = 'dashboard/teacher/presences.html'
    context_object_name = 'presences'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Presence.objects.filter(
            cours__enseignant=self.request.user
        ).select_related(
            'cours__matiere',
            'cours__classe',
            'etudiant'
        )

        # Filtres
        cours_id = self.request.GET.get('cours')
        if cours_id:
            queryset = queryset.filter(cours_id=cours_id)

        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        return queryset.order_by('-cours__date_prevue')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuts_presence'] = Presence.STATUTS_PRESENCE
        return context

class TeacherStudentsView(LoginRequiredMixin, ListView):
    """Mes étudiants (enseignant)"""
    template_name = 'dashboard/teacher/students.html'
    context_object_name = 'students'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        enseignant = self.request.user

        queryset = Utilisateur.objects.filter(
            role='APPRENANT',
            profil_apprenant__classe_actuelle__cours__enseignant=enseignant,
            est_actif=True
        ).select_related(
            'profil_apprenant__classe_actuelle__niveau__filiere'
        ).distinct()

        # Filtres
        classe_id = self.request.GET.get('classe')
        if classe_id:
            queryset = queryset.filter(profil_apprenant__classe_actuelle_id=classe_id)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(matricule__icontains=search)
            )

        return queryset.order_by('nom', 'prenom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        context['classes'] = Classe.objects.filter(
            cours__enseignant=enseignant
        ).distinct()
        context['current_filters'] = {
            'classe': self.request.GET.get('classe', ''),
            'search': self.request.GET.get('search', ''),
        }

        return context

class TeacherEmploiDuTempsView(LoginRequiredMixin, TemplateView):
    """Emploi du temps de l'enseignant"""
    template_name = 'dashboard/teacher/emplois_du_temps.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Emploi du temps actuel
        context['emploi_du_temps'] = EmploiDuTemps.objects.filter(
            enseignant=enseignant,
            actuel=True,
            publie=True
        ).first()

        # Cours de la semaine
        today = timezone.now().date()
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)

        context['cours_semaine'] = Cours.objects.filter(
            enseignant=enseignant,
            date_prevue__range=[start_week, end_week],
            actif=True
        ).select_related('matiere', 'classe', 'salle').order_by('date_prevue', 'heure_debut_prevue')

        return context

class TeacherResourcesView(LoginRequiredMixin, ListView):
    """Mes ressources pédagogiques"""
    template_name = 'dashboard/teacher/ressources.html'
    context_object_name = 'ressources'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Ressource.objects.filter(
            cours__enseignant=self.request.user
        ).select_related('cours__matiere', 'cours__classe')

        # Filtres
        type_ressource = self.request.GET.get('type')
        if type_ressource:
            queryset = queryset.filter(type_ressource=type_ressource)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) | Q(description__icontains=search)
            )

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['types_ressource'] = Ressource.TYPES_RESSOURCE
        context['current_filters'] = {
            'type': self.request.GET.get('type', ''),
            'search': self.request.GET.get('search', ''),
        }

        return context

class TeacherReportsView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/teacher/reports.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            from django.shortcuts import redirect
            from django.contrib import messages
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Récupérer toutes les évaluations du professeur
        evaluations = Evaluation.objects.filter(enseignant=enseignant)

        report_data = []

        for eval in evaluations:
            # Classes concernées
            classes = eval.classes.all()
            classes_data = []

            for classe in classes:
                # Nombre d'apprenants dans la classe
                nb_apprenants = classe.apprenants.count()  # <-- corrigé ici

                # Notes des apprenants de cette classe pour cette évaluation
                notes = Note.objects.filter(
                    evaluation=eval,
                    apprenant__inscription__classe_assignee=classe
                )

                moyenne_classe = notes.aggregate(moyenne=Avg('valeur'))['moyenne'] or 0
                repartition_notes = notes.values('valeur').annotate(count=Count('id')).order_by('valeur')

                # Taux de soumission et de correction
                total_compositions = eval.compositions.filter(apprenant__inscription__classe_assignee=classe)
                nb_soumises = total_compositions.filter(statut__in=['SOUMISE', 'EN_RETARD', 'CORRIGEE']).count()
                nb_corrigees = total_compositions.filter(statut='CORRIGEE').count()

                taux_soumission = (nb_soumises / nb_apprenants * 100) if nb_apprenants else 0
                taux_correction = (nb_corrigees / nb_soumises * 100) if nb_soumises else 0

                classes_data.append({
                    'classe': classe,
                    'nb_apprenants': nb_apprenants,
                    'moyenne_classe': round(moyenne_classe, 2),
                    'repartition_notes': repartition_notes,
                    'taux_soumission': round(taux_soumission, 2),
                    'taux_correction': round(taux_correction, 2),
                })

            report_data.append({
                'evaluation': eval,
                'classes_data': classes_data,
                'taux_soumission_global': round(eval.taux_soumission, 2),
                'taux_correction_global': round(eval.taux_correction, 2),
            })

        context['report_data'] = report_data
        return context

# ================================
# VUES APPRENANT
# ================================
class StudentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/student/index.html'
    allowed_roles = ['APPRENANT']

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        try:
            # Vérification de l'inscription active
            inscription = Inscription.objects.filter(
                apprenant=etudiant,
                statut='ACTIVE'
            ).select_related(
                'candidature__filiere',
                'candidature__niveau',
                'candidature__etablissement',
                'candidature__annee_academique',
                'classe_assignee'
            ).first()

            if inscription:
                context['inscription'] = inscription
                context['peut_acceder'] = True
                context['afficher_modal'] = False

                # Récupérer les données du dashboard
                context.update(self.get_dashboard_data(etudiant, inscription))
            else:
                # Pas d'inscription active - Afficher le modal
                context['inscription'] = None
                context['peut_acceder'] = False
                context['afficher_modal'] = True

                # Récupérer les informations pour le modal
                statut_info = self.get_inscription_status_data(etudiant)
                context.update(statut_info)

        except Exception as e:
            logger.error(f"Erreur chargement dashboard apprenant: {str(e)}", exc_info=True)
            context['inscription'] = None
            context['peut_acceder'] = False
            context['afficher_modal'] = True
            context['statut_modal'] = 'erreur'
            context['message_modal'] = str(e)

        return context

    def get_inscription_status_data(self, etudiant):
        """Récupère les données pour déterminer l'état d'inscription"""

        # Vérifier les inscriptions en attente (paiement en cours)
        inscription_pending = Inscription.objects.filter(
            apprenant=etudiant,
            statut='PENDING'
        ).select_related('candidature').first()

        if inscription_pending:
            # Vérifier les paiements en cours pour cette inscription
            paiements_en_cours = Paiement.objects.filter(
                inscription_paiement__inscription=inscription_pending,
                statut__in=['EN_ATTENTE', 'EN_COURS']
            ).count()

            if paiements_en_cours > 0:
                return {
                    'statut_modal': 'paiement_en_cours',
                    'message_modal': f'Votre paiement est en cours de traitement. Veuillez patienter.',
                    'paiements_en_cours': paiements_en_cours,
                    'inscription_pending': inscription_pending,
                }

        # Vérifier les candidatures approuvées sans inscription
        candidatures_approuvees = Candidature.objects.filter(
            email=etudiant.email,
            statut='APPROUVEE'
        ).exclude(
            inscription__isnull=False
        ).count()

        if candidatures_approuvees == 0:
            # Aucune candidature approuvée
            return {
                'statut_modal': 'aucune_candidature',
                'message_modal': 'Vous devez soumettre et faire approuver une candidature avant de vous inscrire.',
                'candidatures_approuvees': 0,
                'paiements_en_cours': 0,
            }

        # Candidature approuvée mais pas d'inscription
        return {
            'statut_modal': 'inscription_requise',
            'message_modal': 'Veuillez finaliser votre inscription en effectuant le paiement.',
            'candidatures_approuvees': candidatures_approuvees,
            'paiements_en_cours': 0,
        }

    def get_dashboard_data(self, etudiant, inscription):
        """Récupère les données du dashboard pour un étudiant inscrit"""
        context = {}

        # Classe et cours
        classe = inscription.classe_assignee
        context['classe_assignee'] = classe

        if classe:
            # Cours de la classe
            mes_cours = Cours.objects.filter(
                classe=classe
            ).select_related('matiere', 'enseignant').order_by('matiere__nom')
            context['mes_cours'] = mes_cours
            context['total_cours'] = mes_cours.count()

            # Prochain cours
            prochain_cours = EmploiDuTemps.objects.filter(
                classe=classe,
                date_prevue__gte=timezone.now()
            ).select_related(
                'cours__matiere', 'cours__enseignant', 'salle'
            ).order_by('date_prevue').first()
            context['prochain_cours'] = prochain_cours
            context['today'] = timezone.now().date()

            # Évaluations à venir
            evaluations_a_venir = Evaluation.objects.filter(
                cours__classe=classe,
                date_evaluation__gte=timezone.now(),
                est_publiee=True
            ).select_related('cours__matiere').order_by('date_evaluation')[:5]
            context['evaluations_a_venir'] = evaluations_a_venir

            # Dernières notes
            dernieres_notes = Note.objects.filter(
                apprenant=etudiant,
                evaluation__cours__classe=classe
            ).select_related(
                'evaluation__cours__matiere'
            ).order_by('-created_at')[:5]
            context['dernieres_notes'] = dernieres_notes

            # Calcul de la moyenne générale
            notes_valeurs = Note.objects.filter(
                apprenant=etudiant,
                evaluation__cours__classe=classe
            ).values_list('valeur', flat=True)

            if notes_valeurs:
                moyenne = sum(notes_valeurs) / len(notes_valeurs)
                context['moyenne_generale'] = round(moyenne, 2)
            else:
                context['moyenne_generale'] = 0
        else:
            context['mes_cours'] = []
            context['total_cours'] = 0
            context['prochain_cours'] = None
            context['evaluations_a_venir'] = []
            context['dernieres_notes'] = []
            context['moyenne_generale'] = 0

        # Taux de présence (simplifié)
        context['taux_presence'] = 85  # Placeholder

        # Situation financière
        try:
            inscription_paiement = InscriptionPaiement.objects.get(
                inscription=inscription
            )

            statut_financier = {
                'pourcentage': inscription_paiement.pourcentage_paye,
                'total_paye': inscription_paiement.montant_total_paye,
                'solde': inscription_paiement.solde_restant,
                'statut_display': inscription_paiement.get_statut_display(),
                'est_en_retard': inscription_paiement.statut == 'EN_RETARD',
                'peut_payer_tranche': inscription_paiement.type_paiement == 'ECHELONNE'
                                      and inscription_paiement.solde_restant > 0
            }

            context['inscription_paiement'] = inscription_paiement
            context['statut_financier'] = statut_financier
        except InscriptionPaiement.DoesNotExist:
            context['inscription_paiement'] = None
            context['statut_financier'] = {
                'pourcentage': 0,
                'total_paye': 0,
                'solde': inscription.frais_scolarite,
                'statut_display': 'Non configuré',
                'est_en_retard': False,
                'peut_payer_tranche': False
            }

        context['notifications'] = []

        return context

class StudentCoursesView(LoginRequiredMixin, ListView):
    """Mes cours (étudiant)"""
    template_name = 'dashboard/student/courses.html'
    context_object_name = 'courses'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etudiant = self.request.user

        try:
            classe_actuelle = etudiant.profil_apprenant.classe_actuelle
        except:
            return Cours.objects.none()

        queryset = Cours.objects.filter(
            classe=classe_actuelle,
            actif=True
        ).select_related(
            'matiere__niveau__filiere',
            'enseignant',
            'salle'
        )

        # Filtres
        matiere_id = self.request.GET.get('matiere')
        if matiere_id:
            queryset = queryset.filter(matiere_id=matiere_id)

        date_debut = self.request.GET.get('date_debut')
        if date_debut:
            queryset = queryset.filter(date_prevue__gte=date_debut)

        date_fin = self.request.GET.get('date_fin')
        if date_fin:
            queryset = queryset.filter(date_prevue__lte=date_fin)

        return queryset.order_by('-date_prevue', '-heure_debut_prevue')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        try:
            classe_actuelle = etudiant.profil_apprenant.classe_actuelle
            context['matieres'] = Matiere.objects.filter(
                cours__classe=classe_actuelle
            ).distinct()
        except:
            context['matieres'] = []

        context['current_filters'] = {
            'matiere': self.request.GET.get('matiere', ''),
            'date_debut': self.request.GET.get('date_debut', ''),
            'date_fin': self.request.GET.get('date_fin', ''),
        }

        return context

class StudentEmploiDuTempsView(LoginRequiredMixin, TemplateView):
    """Emploi du temps de l'étudiant"""
    template_name = 'dashboard/student/emplois_du_temps.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        try:
            classe_actuelle = etudiant.profil_apprenant.classe_actuelle

            # Emploi du temps actuel
            context['emploi_du_temps'] = EmploiDuTemps.objects.filter(
                classe=classe_actuelle,
                actuel=True,
                publie=True
            ).first()

            # Cours de la semaine
            today = timezone.now().date()
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)

            context['cours_semaine'] = Cours.objects.filter(
                classe=classe_actuelle,
                date_prevue__range=[start_week, end_week],
                actif=True
            ).select_related('matiere', 'enseignant', 'salle').order_by('date_prevue', 'heure_debut_prevue')
        except:
            context['emploi_du_temps'] = None
            context['cours_semaine'] = []

        return context

class StudentEvaluationsView(LoginRequiredMixin, ListView):
    """Mes évaluations (étudiant)"""
    template_name = 'dashboard/student/evaluations.html'
    context_object_name = 'evaluations'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etudiant = self.request.user

        try:
            classe_actuelle = etudiant.profil_apprenant.classe_actuelle
        except:
            return Evaluation.objects.none()

        queryset = Evaluation.objects.filter(
            classes=classe_actuelle
        ).select_related(
            'matiere__niveau__filiere',
            'enseignant'
        ).prefetch_related(
            'compositions'
        )

        # Filtres
        type_eval = self.request.GET.get('type_evaluation')
        if type_eval:
            queryset = queryset.filter(type_evaluation=type_eval)

        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        matiere = self.request.GET.get('matiere')
        if matiere:
            queryset = queryset.filter(matiere_id=matiere)

        return queryset.order_by('-date_debut')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        context['types_evaluation'] = Evaluation.TYPE_EVALUATION
        context['statuts'] = Evaluation.STATUT

        try:
            classe_actuelle = etudiant.profil_apprenant.classe_actuelle
            context['matieres'] = Matiere.objects.filter(
                evaluations__classes=classe_actuelle
            ).distinct()
        except:
            context['matieres'] = []

        context['current_filters'] = {
            'type_evaluation': self.request.GET.get('type_evaluation', ''),
            'statut': self.request.GET.get('statut', ''),
            'matiere': self.request.GET.get('matiere', ''),
        }

        return context

class StudentResultatsView(LoginRequiredMixin, ListView):
    """Notes et résultats de l'étudiant"""
    template_name = 'dashboard/student/resultats.html'
    context_object_name = 'notes'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Note.objects.filter(
            apprenant=self.request.user
        ).select_related(
            'matiere__niveau__filiere',
            'evaluation',
            'attribuee_par'
        )

        # Filtres
        matiere_id = self.request.GET.get('matiere')
        if matiere_id:
            queryset = queryset.filter(matiere_id=matiere_id)

        return queryset.order_by('-date_attribution')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        # Moyenne générale
        notes = Note.objects.filter(apprenant=etudiant)
        if notes.exists():
            total_points = sum(
                float(note.note_sur_20) * float(note.evaluation.coefficient)
                for note in notes
            )
            total_coefficients = sum(
                float(note.evaluation.coefficient)
                for note in notes
            )
            context['moyenne_generale'] = round(total_points / total_coefficients, 2) if total_coefficients > 0 else 0
        else:
            context['moyenne_generale'] = 0

        context['matieres'] = Matiere.objects.filter(
            notes__apprenant=etudiant
        ).distinct()

        context['current_filters'] = {
            'matiere': self.request.GET.get('matiere', ''),
        }

        return context

class StudentPresencesView(LoginRequiredMixin, ListView):
    """Présences de l'étudiant"""
    template_name = 'dashboard/student/presences.html'
    context_object_name = 'presences'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Presence.objects.filter(
            etudiant=self.request.user
        ).select_related(
            'cours__matiere',
            'cours__classe',
            'cours__enseignant'
        )

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        return queryset.order_by('-cours__date_prevue')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        # Statistiques de présence
        total_cours = Presence.objects.filter(etudiant=etudiant).count()
        presences = Presence.objects.filter(etudiant=etudiant, statut='PRESENT').count()

        context['taux_presence'] = round((presences / total_cours * 100), 2) if total_cours > 0 else 0
        context['total_absences'] = Presence.objects.filter(etudiant=etudiant, statut='ABSENT').count()
        context['total_retards'] = Presence.objects.filter(etudiant=etudiant, statut='LATE').count()

        context['statuts_presence'] = Presence.STATUTS_PRESENCE
        context['current_filters'] = {
            'statut': self.request.GET.get('statut', ''),
        }

        return context

class StudentCandidaturesView(LoginRequiredMixin, ListView):
    """Mes candidatures"""
    template_name = 'dashboard/student/candidatures.html'
    context_object_name = 'candidatures'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Candidature.objects.filter(
            email=self.request.user.email
        ).select_related(
            'filiere__departement',
            'niveau',
            'annee_academique'
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        context['total'] = qs.count()
        context['en_attente'] = qs.filter(statut="SOUMISE").count()
        context['en_cours'] = qs.filter(statut="EN_COURS_EXAMEN").count()
        context['approuvees'] = qs.filter(statut="APPROUVEE").count()
        context['rejettees'] = qs.filter(statut="REJETEE").count()
        return context

class StudentInscriptionsView(LoginRequiredMixin, ListView):
    """Mes inscriptions"""
    template_name = 'dashboard/student/inscriptions.html'
    context_object_name = 'inscriptions'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Inscription.objects.filter(
            apprenant=self.request.user
        ).select_related(
            'candidature__filiere',
            'candidature__niveau',
            'classe_assignee'
        ).order_by('-date_inscription')

class StudentPaiementsView(LoginRequiredMixin, ListView):
    """Mes paiements"""
    template_name = 'dashboard/student/paiements.html'
    context_object_name = 'paiements'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Paiement.objects.filter(
            inscription_paiement__inscription__apprenant=self.request.user
        ).select_related(
            'inscription_paiement__inscription',
            'tranche'
        ).order_by('-date_paiement')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        # Inscription active
        inscription_active = Inscription.objects.filter(
            apprenant=etudiant,
            statut='ACTIVE'
        ).first()

        if inscription_active:
            try:
                plan_paiement = inscription_active.plan_paiement_inscription
                context['inscription_active'] = inscription_active
                context['plan_paiement'] = plan_paiement
                context['solde_restant'] = plan_paiement.solde_restant
                context['pourcentage_paye'] = plan_paiement.pourcentage_paye
            except:
                context['inscription_active'] = inscription_active
                context['plan_paiement'] = None

        return context

class StudentRessourcesView(LoginRequiredMixin, ListView):
    """Ressources pédagogiques de l'étudiant"""
    template_name = 'dashboard/student/ressources.html'
    context_object_name = 'ressources'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etudiant = self.request.user

        try:
            classe_actuelle = etudiant.profil_apprenant.classe_actuelle
        except:
            return Ressource.objects.none()

        queryset = Ressource.objects.filter(
            Q(cours__classe=classe_actuelle) | Q(public=True)
        ).select_related(
            'cours__matiere',
            'cours__enseignant'
        )

        # Filtres
        type_ressource = self.request.GET.get('type')
        if type_ressource:
            queryset = queryset.filter(type_ressource=type_ressource)

        matiere_id = self.request.GET.get('matiere')
        if matiere_id:
            queryset = queryset.filter(cours__matiere_id=matiere_id)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) | Q(description__icontains=search)
            )

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        context['types_ressource'] = Ressource.TYPES_RESSOURCE

        try:
            classe_actuelle = etudiant.profil_apprenant.classe_actuelle
            context['matieres'] = Matiere.objects.filter(
                cours__classe=classe_actuelle
            ).distinct()
        except:
            context['matieres'] = []

        context['current_filters'] = {
            'type': self.request.GET.get('type', ''),
            'matiere': self.request.GET.get('matiere', ''),
            'search': self.request.GET.get('search', ''),
        }

        return context

class StudentDocumentsView(LoginRequiredMixin, ListView):
    """Documents de l'étudiant"""
    template_name = 'dashboard/student/documents.html'
    context_object_name = 'demandes'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return DemandeDocument.objects.filter(
            demandeur=self.request.user
        ).order_by('-date_demande')


# ================================
# VUES AJAX ET API
# ================================
class StudentNotificationsAPIView(RoleRequiredMixin, TemplateView):
    """API pour récupérer les notifications de l'apprenant"""
    allowed_roles = ['APPRENANT']
    
    def get(self, request, *args, **kwargs):
        etudiant = request.user
        
        # Simuler des notifications (à adapter selon votre modèle)
        notifications = [
            {
                'id': 1,
                'type': 'resource',
                'title': 'Nouvelle ressource disponible',
                'message': 'Prof. TRAORÉ a ajouté un nouveau cours de Mathématiques',
                'timestamp': timezone.now().isoformat(),
                'read': False
            },
            {
                'id': 2,
                'type': 'grade',
                'title': 'Note publiée',
                'message': 'Votre note de Physique est disponible (16/20)',
                'timestamp': (timezone.now() - timedelta(days=1)).isoformat(),
                'read': False
            },
            {
                'id': 3,
                'type': 'evaluation',
                'title': 'Rappel évaluation',
                'message': 'Contrôle de Mathématiques dans 3 jours',
                'timestamp': (timezone.now() - timedelta(days=2)).isoformat(),
                'read': True
            }
        ]
        
        return JsonResponse({
            'notifications': notifications,
            'unread_count': len([n for n in notifications if not n['read']])
        })

class StudentStatsAPIView(RoleRequiredMixin, TemplateView):
    """API pour récupérer les statistiques de l'apprenant"""
    allowed_roles = ['APPRENANT']
    
    def get(self, request, *args, **kwargs):
        etudiant = request.user
        
        inscription = etudiant.inscriptions.filter(statut='ACTIVE').first()
        
        stats = {}
        
        if inscription:
            # Cours actifs
            cours_actifs = Cours.objects.filter(classe=inscription.classe_attribuee).count()
            
            # Moyenne générale
            moyenne_generale = Note.objects.filter(
                etudiant=etudiant,
                statut='PUBLIEE'
            ).aggregate(moyenne=Avg('valeur'))['moyenne'] or 0
            
            # Taux de présence
            total_seances = Presence.objects.filter(etudiant=etudiant).count()
            presences = Presence.objects.filter(
                etudiant=etudiant,
                statut__in=['PRESENT', 'RETARD']
            ).count()
            taux_presence = (presences / total_seances * 100) if total_seances > 0 else 0
            
            # Évaluations à venir
            evaluations_a_venir = Evaluation.objects.filter(
                cours__classe=inscription.classe_attribuee,
                date_debut__gte=timezone.now(),
                statut='PROGRAMMEE'
            ).count()
            
            stats = {
                'cours_actifs': cours_actifs,
                'moyenne_generale': round(moyenne_generale, 2),
                'taux_presence': round(taux_presence, 1),
                'evaluations_a_venir': evaluations_a_venir
            }
        
        return JsonResponse(stats)


# ================================
# VUES UTILITAIRES
# ================================
def download_document(request, document_type, document_id=None):
    """Téléchargement de documents"""
    if not request.user.is_authenticated or request.user.role != 'APPRENANT':
        return redirect('accounts:login')
    
    etudiant = request.user
    
    # Logique de génération/téléchargement selon le type de document
    if document_type == 'CARTE_ETUDIANT':
        # Générer la carte étudiant
        pass
    elif document_type == 'RELEVE_NOTES':
        # Générer le relevé de notes
        pass
    elif document_type == 'ATTESTATION_SCOLARITE':
        # Générer l'attestation
        pass
    # ... autres types
    
    # Retourner le fichier généré
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{document_type}.pdf"'
    
    # Contenu du document (à implémenter)
    
    return response

def change_password(request):
    """Changement de mot de passe"""
    if request.method == 'POST' and request.user.role == 'APPRENANT':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(current_password):
            messages.error(request, "Mot de passe actuel incorrect.")
        elif new_password != confirm_password:
            messages.error(request, "Les nouveaux mots de passe ne correspondent pas.")
        elif len(new_password) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
        else:
            request.user.set_password(new_password)
            request.user.save()
            messages.success(request, "Mot de passe modifié avec succès.")
            
    return redirect('dashboard:student_profile')


# ================================
# FONCTIONS AJAX ET API
# ================================
@login_required
@require_POST
def admin_toggle_user_status(request, pk):
    """Toggle le statut d'un utilisateur"""
    try:
        user = get_object_or_404(Utilisateur, pk=pk)
        if request.user.peut_gerer_utilisateur(user):
            data = json.loads(request.body)
            user.est_actif = data.get('active', False)
            user.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def admin_reset_user_password(request, pk):
    """Réinitialise le mot de passe d'un utilisateur"""
    try:
        user = get_object_or_404(Utilisateur, pk=pk)
        if request.user.peut_gerer_utilisateur(user):
            # Générer un nouveau mot de passe
            new_password = get_random_string(8)
            user.set_password(new_password)
            user.save()

            # Envoyer par email (à implémenter)
            # send_password_reset_email(user, new_password)

            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def admin_export_users(request):
    """Exporte la liste des utilisateurs"""
    if request.user.role != 'ADMIN':
        raise Http404

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="utilisateurs.csv"'

    writer = csv.writer(response)
    writer.writerow(['Matricule', 'Nom', 'Prénom', 'Email', 'Rôle', 'Département', 'Statut', 'Date création'])

    users = Utilisateur.objects.filter(etablissement=request.user.etablissement)
    for user in users:
        writer.writerow([
            user.matricule,
            user.nom,
            user.prenom,
            user.email,
            user.get_role_display(),
            user.departement.nom if user.departement else '',
            'Actif' if user.est_actif else 'Inactif',
            user.date_creation.strftime('%d/%m/%Y')
        ])

    return response

@login_required
@require_POST
def admin_validate_payment(request, pk):
    """Valide un paiement"""
    try:
        payment = get_object_or_404(Paiement, pk=pk)
        if request.user.etablissement == payment.apprenant.etablissement:
            payment.statut = 'VALIDE'
            payment.date_validation = timezone.now()
            payment.validé_par = request.user
            payment.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def admin_reject_payment(request, pk):
    """Rejette un paiement"""
    try:
        payment = get_object_or_404(Paiement, pk=pk)
        if request.user.etablissement == payment.apprenant.etablissement:
            data = json.loads(request.body)
            payment.statut = 'REJETE'
            payment.raison_rejet = data.get('reason', '')
            payment.date_rejet = timezone.now()
            payment.rejeté_par = request.user
            payment.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def mark_notifications_read(request):
    """Marque les notifications comme lues"""
    if request.method == 'POST':
        # Marquer toutes les notifications comme lues
        # notification_ids = request.POST.get('notification_ids', '').split(',')
        # Notification.objects.filter(
        #     user=request.user,
        #     id__in=notification_ids
        # ).update(read=True)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@login_required
def api_get_statistics(request, type):
    """API pour récupérer des statistiques"""
    if type == 'payments':
        # Retourner les statistiques de paiements
        data = {
            'total_collecte': 5000000,
            'paiements_mois': [500000, 600000, 750000, 650000, 800000, 900000],
        }
        return JsonResponse(data)

    elif type == 'students':
        # Retourner les statistiques d'étudiants
        data = {
            'total_students': 1250,
            'new_this_month': 45,
            'active_percentage': 95,
        }
        return JsonResponse(data)

    return JsonResponse({'error': 'Invalid statistics type'}, status=400)

@login_required
def api_get_chart_data(request, chart_type):
    """API pour récupérer les données des graphiques"""
    if chart_type == 'revenue':
        data = {
            'labels': ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun'],
            'datasets': [{
                'label': 'Revenus',
                'data': [2500000, 3200000, 2800000, 3500000, 4100000, 3800000],
                'borderColor': '#4e73df',
                'backgroundColor': 'rgba(78, 115, 223, 0.1)',
            }]
        }
        return JsonResponse(data)

    return JsonResponse({'error': 'Invalid chart type'}, status=400)