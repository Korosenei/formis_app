# apps/core/dashboard_views.py
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView, ListView, DetailView, UpdateView, FormView
from django.db.models.functions import ExtractMonth
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
import csv
from decimal import Decimal
from io import StringIO
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.urls import reverse_lazy

from apps.core.mixins import RoleRequiredMixin, EstablishmentFilterMixin
from apps.accounts.models import Utilisateur, ProfilApprenant, ProfilEnseignant
from apps.establishments.models import Etablissement, AnneeAcademique, Salle
from apps.academic.models import Departement, Filiere, Niveau, Classe
from apps.courses.models import Matiere, Cours, Presence, Ressource, CahierTexte, MatiereModule, EmploiDuTemps
from apps.enrollment.models import Candidature, Inscription
from apps.evaluations.models import Evaluation, Note
from apps.payments.models import Paiement, PlanPaiement, InscriptionPaiement
from apps.documents.models import DemandeDocument


class DashboardRedirectView(LoginRequiredMixin, TemplateView):
    """Redirige vers le bon dashboard selon le rôle"""

    def get(self, request, *args, **kwargs):
        user = request.user

        if user.role == 'SUPERADMIN':
            return redirect('dashboard:superadmin')
        elif user.role == 'ADMIN':
            return redirect('dashboard:admin')
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
            # Limiter entre 10 et 100
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
            nombre_classes=Count('classes', filter=Q(classes__est_active=True)),  # <-- changed
            nombre_etudiants=Count(
                'classes__apprenants',  # <-- changed
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
        from apps.establishments.models import AnneeAcademique

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
        from apps.establishments.models import AnneeAcademique

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
        from apps.courses.models import Module
        etablissement = self.request.user.etablissement
        queryset = Module.objects.filter(
            niveau__filiere__departement__etablissement=etablissement
        ).select_related(
            'niveau__filiere__departement',
            'coordinateur'
        ).annotate(
            nombre_matieres=Count('matieremodule')
        )

        # Filtres
        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(niveau__filiere__departement_id=departement)

        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(niveau__filiere_id=filiere)

        niveau = self.request.GET.get('niveau')
        if niveau:
            queryset = queryset.filter(niveau_id=niveau)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search)
            )

        return queryset.order_by('niveau__filiere__nom', 'nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'departements': Departement.objects.filter(etablissement=etablissement, est_actif=True),
            'filieres': Filiere.objects.filter(etablissement=etablissement, est_active=True),
            'niveaux': Niveau.objects.filter(filiere__etablissement=etablissement, est_actif=True),
            'current_filters': {
                'departement': self.request.GET.get('departement', ''),
                'filiere': self.request.GET.get('filiere', ''),
                'niveau': self.request.GET.get('niveau', ''),
                'search': self.request.GET.get('search', ''),
            },
        })
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
        from apps.courses.models import Matiere
        queryset = Matiere.objects.all().annotate(
            nombre_modules=Count('matieremodule')
        )

        # Filtres
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search)
            )

        actif = self.request.GET.get('actif')
        if actif:
            queryset = queryset.filter(actif=actif == 'True')

        return queryset.order_by('nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_filters'] = {
            'actif': self.request.GET.get('actif', ''),
            'search': self.request.GET.get('search', ''),
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
        from apps.enrollment.models import Candidature
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

        from apps.academic.models import Filiere, Niveau
        from apps.establishments.models import AnneeAcademique
        from apps.enrollment.models import Candidature

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

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = Cours.objects.filter(
            matiere_module__module__niveau__filiere__departement__etablissement=etablissement
        ).select_related(
            'matiere_module', 'matiere_module__matiere', 'enseignant', 'classe'
        ).distinct()

        # Filtres
        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(
                matiere_module__module__niveau__filiere__departement_id=departement
            )

        enseignant = self.request.GET.get('enseignant')
        if enseignant:
            queryset = queryset.filter(enseignant_id=enseignant)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'departements': Departement.objects.filter(etablissement=etablissement),
            'enseignants': Utilisateur.objects.filter(
                etablissement=etablissement,
                role='ENSEIGNANT'
            ),
            'total_cours': self.get_queryset().count(),
        })

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

        queryset = Evaluation.objects.filter(
            matiere_module__module__niveau__filiere__departement__etablissement=etablissement
        ).select_related(
            'enseignant',
            'matiere_module__matiere',
            'matiere_module__module'
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
            queryset = queryset.filter(matiere_module__matiere_id=matiere)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(titre__icontains=search) |
                Q(matiere_module__matiere__nom__icontains=search)
            )

        return queryset.order_by('-date_debut')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'types_evaluation': Evaluation.TYPE_EVALUATION,
            'statuts': Evaluation.STATUT,
            'enseignants': Utilisateur.objects.filter(
                etablissement=etablissement,
                role='ENSEIGNANT',
                est_actif=True
            ),
            'matieres': Matiere.objects.filter(actif=True),
            'current_filters': {
                'type_evaluation': self.request.GET.get('type_evaluation', ''),
                'statut': self.request.GET.get('statut', ''),
                'enseignant': self.request.GET.get('enseignant', ''),
                'matiere': self.request.GET.get('matiere', ''),
                'search': self.request.GET.get('search', ''),
            },
            'stats': {
                'total': self.get_queryset().count(),
                'programmees': self.get_queryset().filter(statut='PROGRAMMEE').count(),
                'en_cours': self.get_queryset().filter(statut='EN_COURS').count(),
                'terminees': self.get_queryset().filter(statut='TERMINEE').count(),
            }
        })
        return context

class AdminProgrammesView(LoginRequiredMixin, ListView):
    """Gestion des programmes par l'admin"""
    template_name = 'dashboard/admin/programmes.html'
    context_object_name = 'programmes'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etablissement = self.request.user.etablissement

        # Récupérer les classes de l'établissement via les niveaux/filières
        classes_ids = Classe.objects.filter(
            niveau__filiere__etablissement=etablissement
        ).values_list('id', flat=True)

        queryset = EmploiDuTemps.objects.filter(
            classe_id__in=classes_ids
        ).select_related('classe', 'periode_academique', 'cree_par')

        # Filtre par département
        departement = self.request.GET.get('departement')
        if departement:
            departement_classes_ids = Classe.objects.filter(
                niveau__filiere__departement_id=departement
            ).values_list('id', flat=True)
            queryset = queryset.filter(classe_id__in=departement_classes_ids)

        # Filtre par filière
        filiere = self.request.GET.get('filiere')
        if filiere:
            filiere_classes_ids = Classe.objects.filter(
                niveau__filiere_id=filiere
            ).values_list('id', flat=True)
            queryset = queryset.filter(classe_id__in=filiere_classes_ids)

        # Filtre sur l'emploi du temps actuel / publié
        est_actif = self.request.GET.get('est_actif')
        if est_actif:
            queryset = queryset.filter(actuel=est_actif == 'True')

        # Recherche texte
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(classe__nom__icontains=search)
            )

        return queryset.order_by('classe__nom', 'nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'departements': Departement.objects.filter(etablissement=etablissement, est_actif=True),
            'filieres': Filiere.objects.filter(etablissement=etablissement, est_active=True),
            'current_filters': {
                'departement': self.request.GET.get('departement', ''),
                'filiere': self.request.GET.get('filiere', ''),
                'est_actif': self.request.GET.get('est_actif', ''),
                'search': self.request.GET.get('search', ''),
            },
            'total_programmes': self.get_queryset().count(),
        })
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
# VUES CHEF DEPARTEMENT
# ================================
class DepartmentHeadDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord du chef de département"""
    template_name = 'dashboard/department_head/index.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # 🔧 CORRECTION : Utiliser 'departement' au lieu de 'departement'
        departement = user.departement

        # 🔎 Sécurité : s'assurer que departement est bien un objet Departement
        if not departement:
            messages.warning(self.request, "Aucun département assigné")
            return context

        # Vérifier que l'utilisateur est bien chef de ce département
        if not hasattr(user, 'departements_diriges') or not user.departements_diriges.filter(
                id=departement.id).exists():
            messages.error(self.request, "Vous n'êtes pas chef de ce département")
            return context

        # Statistiques du département
        context.update({
            'total_enseignants': self.get_total_enseignants(departement),
            'total_apprenants': self.get_total_apprenants(departement),
            'total_filieres': self.get_total_filieres(departement),
            'total_classes': self.get_total_classes(departement),
            'evaluations_en_cours': self.get_evaluations_en_cours(departement),
            'candidatures_departement': self.get_candidatures_departement(departement),

            # Données pour graphiques
            'repartition_apprenants_filiere': self.get_repartition_apprenants_filiere(departement),
            'stats_evaluations_mois': self.get_stats_evaluations_par_mois(departement),

            # Activités récentes
            'cours_recents': self.get_cours_recents(departement),
            'evaluations_recentes': self.get_evaluations_recentes(departement),

            # 🔧 AJOUT : Passer le département au contexte
            'departement': departement,
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
            matiere_module__module__niveau__filiere__departement=departement,  # 🔧 CORRECTION du chemin
            statut='EN_COURS'
        ).count()

    def get_candidatures_departement(self, departement):
        return Candidature.objects.filter(
            niveau__filiere__departement=departement,
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
            matiere_module__module__niveau__filiere__departement=departement,
            created_at__gte=debut_annee
        ).annotate(
            month=ExtractMonth('created_at')  # Précise bien que c'est le champ Evaluation.created_at
        ).values('month').annotate(count=Count('id'))

        stats = [0] * 12
        for item in evaluations:
            stats[int(item['month']) - 1] = item['count']

        return stats

    def get_cours_recents(self, departement):
        return Cours.objects.filter(
            matiere_module__module__niveau__filiere__departement=departement  # 🔧 CORRECTION du chemin
        ).select_related('matiere_module', 'enseignant').order_by('-created_at')[:5]

    def get_evaluations_recentes(self, departement):
        return Evaluation.objects.filter(
            matiere_module__module__niveau__filiere__departement=departement  # 🔧 CORRECTION du chemin
        ).select_related('matiere_module', 'enseignant').order_by('-created_at')[:5]

class DepartmentHeadTeachersView(LoginRequiredMixin, ListView):
    """Gestion des enseignants du département"""
    template_name = 'dashboard/department_head/teachers.html'
    context_object_name = 'teachers'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        departement = self.request.user.departement
        if not departement:
            return Utilisateur.objects.none()

        queryset = Utilisateur.objects.filter(
            departement=departement,
            role='ENSEIGNANT'
        ).select_related('profil_enseignant')

        # Filtres
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
        context['search_query'] = self.request.GET.get('search', '')
        return context

class DepartmentHeadStudentsView(LoginRequiredMixin, ListView):
    """Gestion des étudiants du département"""
    template_name = 'dashboard/department_head/students.html'
    context_object_name = 'students'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        departement = self.request.user.departement
        if not departement:
            return Utilisateur.objects.none()

        queryset = Utilisateur.objects.filter(
            departement=departement,
            role='APPRENANT'
        ).select_related('profil_apprenant__classe_actuelle')

        # Filtres
        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(
                profil_apprenant__classe_actuelle__niveau__filiere_id=filiere
            )

        return queryset.order_by('-date_creation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        if departement:
            context['filieres'] = Filiere.objects.filter(departement=departement)

        return context

class DepartmentHeadCandidaturesView(LoginRequiredMixin, ListView):
    """Gestion des candidatures"""
    template_name = 'dashboard/department_head/candidatures.html'
    context_object_name = 'candidatures'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'CHEF_DEPARTEMENT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        etablissement = self.request.user.etablissement
        queryset = Candidature.objects.filter(
            niveau__filiere__departement__etablissement=etablissement
        ).select_related('niveau__filiere__departement', 'candidat')

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(niveau__filiere__departement_id=departement)

        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(niveau__filiere_id=filiere)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(numero_candidature__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset.order_by('-date_soumission')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.user.etablissement

        context.update({
            'departements': Departement.objects.filter(etablissement=etablissement),
            'filieres': Filiere.objects.filter(departement__etablissement=etablissement),
            'statuts': Candidature._meta.get_field('statut').choices,
            'current_filters': {
                'statut': self.request.GET.get('statut', ''),
                'departement': self.request.GET.get('departement', ''),
                'filiere': self.request.GET.get('filiere', ''),
                'search': self.request.GET.get('search', ''),
            },
        })

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
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        from apps.courses.models import Module
        departement = self.request.user.departement
        if not departement:
            return Module.objects.none()

        queryset = Module.objects.filter(
            niveau__filiere__departement=departement
        ).select_related(
            'niveau__filiere',
            'coordinateur'
        ).annotate(
            nombre_matieres=Count('matieremodule')
        )

        # Filtres
        filiere = self.request.GET.get('filiere')
        if filiere:
            queryset = queryset.filter(niveau__filiere_id=filiere)

        niveau = self.request.GET.get('niveau')
        if niveau:
            queryset = queryset.filter(niveau_id=niveau)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code__icontains=search)
            )

        return queryset.order_by('niveau__filiere__nom', 'nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        if departement:
            context.update({
                'filieres': Filiere.objects.filter(departement=departement, est_active=True),
                'niveaux': Niveau.objects.filter(filiere__departement=departement, est_actif=True),
                'current_filters': {
                    'filiere': self.request.GET.get('filiere', ''),
                    'niveau': self.request.GET.get('niveau', ''),
                    'search': self.request.GET.get('search', ''),
                },
            })
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
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        departement = self.request.user.departement
        if not departement:
            return Filiere.objects.none()

        queryset = Filiere.objects.filter(
            departement=departement
        ).annotate(
            nombre_niveaux=Count('niveaux', filter=Q(niveaux__est_actif=True)),
            nombre_etudiants=Count('niveaux__classe__profil_apprenant', distinct=True)
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
                Q(code__icontains=search)
            )

        return queryset.order_by('nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'types_filiere': Filiere.TYPES_FILIERE,
            'current_filters': {
                'type_filiere': self.request.GET.get('type_filiere', ''),
                'est_active': self.request.GET.get('est_active', ''),
                'search': self.request.GET.get('search', ''),
            },
        })
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
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        departement = self.request.user.departement
        if not departement:
            return Classe.objects.none()

        queryset = Classe.objects.filter(
            niveau__filiere__departement=departement
        ).select_related(
            'niveau__filiere',
            'professeur_principal',
            'salle_principale'
        ).annotate(
            nombre_etudiants=Count('profil_apprenant', filter=Q(profil_apprenant__utilisateur__est_actif=True))
        )

        # Filtres
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
                Q(code__icontains=search)
            )

        return queryset.order_by('niveau__filiere__nom', 'nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departement = self.request.user.departement

        if departement:
            context.update({
                'filieres': Filiere.objects.filter(departement=departement, est_active=True),
                'niveaux': Niveau.objects.filter(filiere__departement=departement, est_actif=True),
                'current_filters': {
                    'filiere': self.request.GET.get('filiere', ''),
                    'niveau': self.request.GET.get('niveau', ''),
                    'est_active': self.request.GET.get('est_active', ''),
                    'search': self.request.GET.get('search', ''),
                },
            })
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
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        departement = self.request.user.departement
        if not departement:
            return Cours.objects.none()

        return Cours.objects.filter(
            matiere__modules__filiere__departement=departement
        ).select_related('matiere', 'enseignant').distinct().order_by('-date_creation')

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
        if not departement:
            return Evaluation.objects.none()

        return Evaluation.objects.filter(
            cours__matiere__modules__filiere__departement=departement
        ).select_related('cours__matiere', 'cours__enseignant').order_by('-date_creation')

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
    """Tableau de bord enseignant"""
    template_name = 'dashboard/teacher/index.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context.update({
            'mes_cours': self.get_mes_cours(user),
            'evaluations_recentes': self.get_evaluations_recentes(user),
            'prochaines_evaluations': self.get_prochaines_evaluations(user),
            'mes_classes': self.get_mes_classes(user),
            'total_etudiants': self.get_total_etudiants(user),
            'evaluations_a_corriger': self.get_evaluations_a_corriger(user),
        })

        return context

    def get_mes_cours(self, user):
        return Cours.objects.filter(enseignant=user).select_related(
            'matiere_module__matiere', 'classe'
        )[:5]

    def get_evaluations_recentes(self, user):
        return Evaluation.objects.filter(
            matiere_module__enseignant=user
        ).select_related(
            'matiere_module__matiere', 'matiere_module__module'
        ).order_by('-created_at')[:5]

    def get_prochaines_evaluations(self, user):
        return Evaluation.objects.filter(
            matiere_module__enseignant=user,
            date_debut__gt=timezone.now()
        ).order_by('date_debut')[:5]

    def get_mes_classes(self, user):
        return Classe.objects.filter(
            cours__enseignant=user
        ).distinct()

    def get_total_etudiants(self, user):
        return Utilisateur.objects.filter(
            profil_apprenant__classe_actuelle__cours__enseignant=user,
            role='APPRENANT'
        ).distinct().count()

    def get_evaluations_a_corriger(self, user):
        return Evaluation.objects.filter(
            matiere_module__enseignant=user,
            statut='TERMINE'
        ).count()

class TeacherCoursesView(LoginRequiredMixin, ListView):
    """Liste des cours de l'enseignant"""
    template_name = 'dashboard/teacher/courses.html'
    context_object_name = 'courses'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Cours.objects.filter(
            enseignant=self.request.user
        ).select_related('matiere', 'classe')

class TeacherLogbookView(RoleRequiredMixin, ListView):
    """Cahier de textes de l'enseignant"""
    model = CahierTexte
    template_name = 'dashboard/teacher/logbook/list.html'
    context_object_name = 'entrees_cahier'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return CahierTexte.objects.filter(
            cours__enseignant=self.request.user
        ).select_related('cours__matiere_module__matiere', 'cours__classe').order_by('-cours__date_prevue')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Mes cours pour ajouter une entrée
        mes_cours = Cours.objects.filter(
            enseignant=enseignant
        ).select_related('matiere_module__matiere', 'classe')

        # Séances récentes sans entrée dans le cahier
        cours_sans_cahier = Cours.objects.filter(
            enseignant=enseignant,
            date_prevue__lte=timezone.now().date(),
            cahier_texte__isnull=True
        ).select_related('matiere_module__matiere', 'classe').order_by('-date_prevue')[:10]

        # Statistiques
        total_entrees = self.get_queryset().count()
        entrees_ce_mois = self.get_queryset().filter(
            cours__date_prevue__gte=timezone.now().replace(day=1)
        ).count()

        # Progression par cours
        progression_cours = {}
        for cours in mes_cours:
            nb_cours_prevus = Cours.objects.filter(
                enseignant=enseignant,
                matiere_module=cours.matiere_module,
                date_prevue__lte=timezone.now().date()
            ).count()

            nb_entrees_cahier = CahierTexte.objects.filter(cours=cours).count()

            if nb_cours_prevus > 0:
                progression_cours[cours] = {
                    'pourcentage': (nb_entrees_cahier / nb_cours_prevus) * 100,
                    'entrees': nb_entrees_cahier,
                    'cours_prevus': nb_cours_prevus,
                }
            else:
                progression_cours[cours] = {
                    'pourcentage': 0,
                    'entrees': nb_entrees_cahier,
                    'cours_prevus': 0,
                }

        context.update({
            'mes_cours': mes_cours,
            'cours_sans_cahier': cours_sans_cahier,
            'total_entrees': total_entrees,
            'entrees_ce_mois': entrees_ce_mois,
            'progression_cours': progression_cours,
        })

        return context

class TeacherScheduleView(RoleRequiredMixin, TemplateView):
    """Emploi du temps de l'enseignant"""
    template_name = 'dashboard/teacher/schedule.html'
    allowed_roles = ['ENSEIGNANT']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Semaine courante ou spécifiée
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # Mes cours de la semaine
        cours_semaine = Cours.objects.filter(
            enseignant=enseignant,
            date_prevue__range=[week_start, week_end]
        ).select_related('matiere_module__matiere', 'classe')

        # Organisation par jour et heure
        emploi_du_temps = {}
        jours_semaine = [
            ('LUNDI', week_start),
            ('MARDI', week_start + timedelta(days=1)),
            ('MERCREDI', week_start + timedelta(days=2)),
            ('JEUDI', week_start + timedelta(days=3)),
            ('VENDREDI', week_start + timedelta(days=4)),
            ('SAMEDI', week_start + timedelta(days=5)),
            ('DIMANCHE', week_start + timedelta(days=6)),
        ]

        for jour_nom, date_jour in jours_semaine:
            emploi_du_temps[jour_nom] = {
                'date': date_jour,
                'cours': []
            }

            # Cours de ce jour
            cours_jour = Cours.objects.filter(
                enseignant=enseignant,
                date_prevue=date_jour
            ).select_related('matiere_module__matiere', 'classe').order_by('heure_debut_prevue')

            emploi_du_temps[jour_nom]['cours'] = cours_jour

        # Prochains cours (3 prochains)
        prochains_cours = Cours.objects.filter(
            enseignant=enseignant,
            date_prevue__gte=today
        ).select_related('matiere_module__matiere', 'classe').order_by('date_prevue', 'heure_debut_prevue')[:3]

        # Statistiques de la semaine
        total_heures_semaine = 0
        total_cours_semaine = 0
        classes_enseignees = set()

        for cours in cours_semaine:
            if cours.heure_fin_prevue and cours.heure_debut_prevue:
                duree = (datetime.combine(today, cours.heure_fin_prevue) -
                         datetime.combine(today, cours.heure_debut_prevue)).total_seconds() / 3600
                total_heures_semaine += duree
            total_cours_semaine += 1
            classes_enseignees.add(cours.classe.nom if cours.classe else 'Non assignée')

        # Cours du jour
        cours_aujourd_hui = Cours.objects.filter(
            enseignant=enseignant,
            date_prevue=today
        ).select_related('matiere_module__matiere', 'classe').order_by('heure_debut_prevue')

        context.update({
            'emploi_du_temps': emploi_du_temps,
            'semaine_courante': {
                'debut': week_start,
                'fin': week_end,
            },
            'prochains_cours': prochains_cours,
            'cours_aujourd_hui': cours_aujourd_hui,
            'statistiques_semaine': {
                'total_heures': round(total_heures_semaine, 1),
                'total_cours': total_cours_semaine,
                'nb_classes': len(classes_enseignees),
                'classes': list(classes_enseignees),
            }
        })

        return context

class TeacherStudentsView(RoleRequiredMixin, ListView):
    """Liste des étudiants de l'enseignant"""
    model = Utilisateur
    template_name = 'dashboard/teacher/students.html'
    context_object_name = 'etudiants'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        enseignant = self.request.user
        return Utilisateur.objects.filter(
            inscriptions__classe_attribuee__cours__enseignant=enseignant,
            role='APPRENANT'
        ).distinct().select_related('etablissement')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Statistiques par étudiant
        for etudiant in context['etudiants']:
            # Moyenne de l'étudiant dans mes cours
            etudiant.moyenne_generale = Note.objects.filter(
                etudiant=etudiant,
                evaluation__cours__enseignant=enseignant,
                statut='PUBLIEE'
            ).aggregate(moyenne=Avg('valeur'))['moyenne'] or 0

            # Taux de présence
            total_presences = Presence.objects.filter(
                etudiant=etudiant,
                seance__cours__enseignant=enseignant
            ).count()

            if total_presences > 0:
                presences = Presence.objects.filter(
                    etudiant=etudiant,
                    seance__cours__enseignant=enseignant,
                    statut__in=['PRESENT', 'RETARD']
                ).count()
                etudiant.taux_presence = (presences / total_presences) * 100
            else:
                etudiant.taux_presence = 0

        return context

class TeacherEvaluationsView(RoleRequiredMixin, ListView):
    """Liste des évaluations de l'enseignant"""
    model = Evaluation
    template_name = 'evaluations/enseignant/list.html'
    context_object_name = 'evaluations'
    paginate_by = 15

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Evaluation.objects.filter(
            matiere_module__enseignant=self.request.user
        ).select_related('matiere_module__matiere', 'matiere_module__module').order_by('-date_debut')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Statistiques des évaluations
        total_evaluations = self.get_queryset().count()
        evaluations_programmees = self.get_queryset().filter(statut='PROGRAMMEE').count()
        evaluations_en_cours = self.get_queryset().filter(statut='EN_COURS').count()
        evaluations_terminees = self.get_queryset().filter(statut='TERMINEE').count()

        # Évaluations à venir dans les 7 prochains jours
        prochaines_evaluations = self.get_queryset().filter(
            date_debut__gte=timezone.now(),
            date_debut__lte=timezone.now() + timedelta(days=7),
            statut='PROGRAMMEE'
        )

        # Notes en attente de correction (notes sans valeur ou avec valeur nulle)
        notes_a_corriger = Note.objects.filter(
            evaluation__matiere_module__enseignant=enseignant,
            valeur__isnull=True  # Correction : utiliser valeur au lieu de statut
        ).count()

        # Mes matières-modules pour créer une nouvelle évaluation
        mes_matiere_modules = MatiereModule.objects.filter(
            enseignant=enseignant
        ).select_related('matiere', 'module')

        context.update({
            'total_evaluations': total_evaluations,
            'evaluations_programmees': evaluations_programmees,
            'evaluations_en_cours': evaluations_en_cours,
            'evaluations_terminees': evaluations_terminees,
            'prochaines_evaluations': prochaines_evaluations,
            'notes_a_corriger': notes_a_corriger,
            'mes_matiere_modules': mes_matiere_modules,
        })

        return context

class TeacherGradesView(RoleRequiredMixin, TemplateView):
    """Vue complète pour la gestion des notes"""
    template_name = 'dashboard/teacher/grades/dashboard.html'
    allowed_roles = ['ENSEIGNANT']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Notes non attribuées (sans valeur)
        notes_non_attribuees = Note.objects.filter(
            evaluation__matiere_module__enseignant=enseignant,
            valeur__isnull=True  # Notes sans valeur = à corriger
        ).select_related('etudiant', 'evaluation__matiere_module__matiere').order_by('-created_at')

        # Notes récemment attribuées
        notes_attribuees = Note.objects.filter(
            evaluation__matiere_module__enseignant=enseignant,
            valeur__isnull=False,  # Notes avec valeur = publiées
            updated_at__gte=timezone.now() - timedelta(days=7)
        ).select_related('etudiant', 'evaluation__matiere_module__matiere').order_by('-updated_at')

        # Évaluations en attente de notation (sans aucune note)
        evaluations_a_noter = Evaluation.objects.filter(
            matiere_module__enseignant=enseignant,
            statut='TERMINEE',
            notes__isnull=True
        ).distinct().select_related('matiere_module__matiere', 'matiere_module__module')

        # Évaluations avec notes incomplètes (certaines notes manquantes)
        evaluations_incompletes = []
        evaluations_terminees = Evaluation.objects.filter(
            matiere_module__enseignant=enseignant,
            statut='TERMINEE'
        ).select_related('matiere_module__matiere', 'matiere_module__module')

        for evaluation in evaluations_terminees:
            total_etudiants = evaluation.classes.aggregate(
                total=Count('etudiants', distinct=True)
            )['total'] or 0

            notes_attribuees_count = evaluation.notes.filter(valeur__isnull=False).count()

            if 0 < notes_attribuees_count < total_etudiants:
                evaluations_incompletes.append({
                    'evaluation': evaluation,
                    'notes_attribuees': notes_attribuees_count,
                    'total_etudiants': total_etudiants,
                    'pourcentage': (notes_attribuees_count / total_etudiants) * 100
                })

        # Statistiques générales
        stats = {
            'total_notes_non_attribuees': notes_non_attribuees.count(),
            'total_notes_attribuees_semaine': notes_attribuees.count(),
            'evaluations_a_noter': evaluations_a_noter.count(),
            'evaluations_incompletes': len(evaluations_incompletes),
        }

        # Moyennes par matière
        moyennes_matieres = {}
        mes_matiere_modules = MatiereModule.objects.filter(enseignant=enseignant)

        for matiere_module in mes_matiere_modules:
            key = f"{matiere_module.matiere.nom} - {matiere_module.module.nom}"
            moyenne = Note.objects.filter(
                evaluation__matiere_module=matiere_module,
                valeur__isnull=False  # Seulement les notes attribuées
            ).aggregate(moyenne=Avg('valeur'))['moyenne']

            if moyenne is not None:
                moyennes_matieres[key] = round(moyenne, 2)

        # Alertes
        alertes = []

        # Alertes pour évaluations anciennes non notées
        evaluations_anciennes = Evaluation.objects.filter(
            matiere_module__enseignant=enseignant,
            statut='TERMINEE',
            date_fin__lt=timezone.now() - timedelta(days=7)
        ).exclude(
            notes__valeur__isnull=False  # Évaluations sans aucune note attribuée
        ).distinct()

        if evaluations_anciennes.exists():
            alertes.append({
                'type': 'warning',
                'message': f"{evaluations_anciennes.count()} évaluation(s) terminée(s) il y a plus de 7 jours sans notes attribuées",
                'action_url': 'teacher_evaluations',
            })

        # Alertes pour matières avec moyenne faible
        for matiere_nom, moyenne in moyennes_matieres.items():
            if moyenne < 10:
                alertes.append({
                    'type': 'danger',
                    'message': f"Moyenne faible en {matiere_nom}: {moyenne}/20",
                })

        context.update({
            'notes_non_attribuees': notes_non_attribuees[:10],
            'notes_attribuees': notes_attribuees[:10],
            'evaluations_a_noter': evaluations_a_noter[:5],
            'evaluations_incompletes': evaluations_incompletes[:5],
            'statistiques': stats,
            'moyennes_matieres': moyennes_matieres,
            'alertes': alertes,
        })

        return context

class TeacherGradeEvaluationView(RoleRequiredMixin, TemplateView):
    """Gestion des notes par évaluation"""
    template_name = 'dashboard/teacher/grades/by_evaluation.html'
    allowed_roles = ['ENSEIGNANT']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user
        evaluation_id = self.kwargs.get('evaluation_id')

        try:
            evaluation = Evaluation.objects.get(
                id=evaluation_id,
                cours__enseignant=enseignant
            )

            # Notes de cette évaluation
            notes = Note.objects.filter(
                evaluation=evaluation
            ).select_related('etudiant').order_by('etudiant__nom', 'etudiant__prenoms')

            # Étudiants sans note
            etudiants_avec_note = notes.values_list('etudiant__id', flat=True)

            if evaluation.cours.classe:
                etudiants_sans_note = evaluation.cours.classe.etudiants.exclude(
                    id__in=etudiants_avec_note
                )
            else:
                etudiants_sans_note = []

            # Statistiques de l'évaluation
            if notes.exists():
                stats_evaluation = {
                    'moyenne': notes.aggregate(moyenne=Avg('valeur'))['moyenne'],
                    'note_max': notes.aggregate(max=Max('valeur'))['max'],
                    'note_min': notes.aggregate(min=Min('valeur'))['min'],
                    'nb_notes': notes.count(),
                    'nb_admis': notes.filter(valeur__gte=10).count(),
                    'taux_reussite': (notes.filter(valeur__gte=10).count() / notes.count()) * 100,
                }
            else:
                stats_evaluation = {
                    'moyenne': 0,
                    'note_max': 0,
                    'note_min': 0,
                    'nb_notes': 0,
                    'nb_admis': 0,
                    'taux_reussite': 0,
                }

            context.update({
                'evaluation': evaluation,
                'notes': notes,
                'etudiants_sans_note': etudiants_sans_note,
                'stats_evaluation': stats_evaluation,
            })

        except Evaluation.DoesNotExist:
            context['error'] = "Évaluation non trouvée ou non autorisée"

        return context

class TeacherAttendanceView(RoleRequiredMixin, TemplateView):
    """Gestion des présences par l'enseignant"""
    template_name = 'dashboard/teacher/attendance.html'
    allowed_roles = ['ENSEIGNANT']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Cours récents pour la prise de présence
        cours_recents = Cours.objects.filter(
            enseignant=enseignant,
            date_prevue__lte=timezone.now().date()
        ).select_related('classe', 'matiere').order_by('-date_prevue')[:10]

        # Statistiques de présence par classe
        stats_presence = {}
        for cours in cours_recents:
            if cours.classe not in stats_presence:
                total_etudiants = cours.classe.etudiants.count()
                if total_etudiants > 0:
                    presences = Presence.objects.filter(
                        seance__cours__classe=cours.classe,
                        seance__cours__enseignant=enseignant,
                        statut__in=['PRESENT', 'RETARD']
                    ).count()
                    total_seances = Presence.objects.filter(
                        seance__cours__classe=cours.classe,
                        seance__cours__enseignant=enseignant
                    ).count()

                    if total_seances > 0:
                        stats_presence[cours.classe] = {
                            'taux_presence': (presences / total_seances) * 100,
                            'total_etudiants': total_etudiants
                        }

        # Étudiants avec faible assiduité
        etudiants_absents = Utilisateur.objects.filter(
            inscriptions__classe_attribuee__cours__enseignant=enseignant,
            role='APPRENANT'
        ).annotate(
            taux_presence=Avg(
                Case(
                    When(presences__statut__in=['PRESENT', 'RETARD'], then=100),
                    default=0,
                    output_field=FloatField()
                )
            )
        ).filter(taux_presence__lt=70).distinct()

        context.update({
            'cours_recents': cours_recents,
            'stats_presence': stats_presence,
            'etudiants_absents': etudiants_absents,
        })

        return context

class TeacherResourcesView(RoleRequiredMixin, ListView):
    """Ressources de l'enseignant"""
    model = Ressource
    template_name = 'dashboard/teacher/resources.html'
    context_object_name = 'resources'
    paginate_by = 15

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Ressource.objects.filter(
            cours__enseignant=self.request.user
        ).select_related('cours__matiere', 'cours__classe').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Mes cours pour l'ajout de ressources
        mes_cours = Cours.objects.filter(
            enseignant=enseignant
        ).select_related('matiere', 'classe')

        # Statistiques d'utilisation
        stats_telechargements = Ressource.objects.filter(
            cours__enseignant=enseignant
        ).aggregate(
            total_telechargements=Sum('nb_telechargements'),
            total_ressources=Count('id')
        )

        context.update({
            'mes_cours': mes_cours,
            'stats_telechargements': stats_telechargements,
        })

        return context

class TeacherReportsView(RoleRequiredMixin, TemplateView):
    """Rapports de l'enseignant"""
    template_name = 'dashboard/teacher/reports.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'ENSEIGNANT':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enseignant = self.request.user

        # Rapport de performance par classe
        classes = Classe.objects.filter(cours__enseignant=enseignant).distinct()
        rapports_classes = []

        for classe in classes:
            # Moyenne générale de la classe
            moyenne_classe = Note.objects.filter(
                evaluation__cours__classe=classe,
                evaluation__cours__enseignant=enseignant,
                statut='PUBLIEE'
            ).aggregate(moyenne=Avg('valeur'))['moyenne'] or 0

            # Taux de présence
            total_presences = Presence.objects.filter(
                seance__cours__classe=classe,
                seance__cours__enseignant=enseignant
            ).count()

            if total_presences > 0:
                presences = Presence.objects.filter(
                    seance__cours__classe=classe,
                    seance__cours__enseignant=enseignant,
                    statut__in=['PRESENT', 'RETARD']
                ).count()
                taux_presence = (presences / total_presences) * 100
            else:
                taux_presence = 0

            rapports_classes.append({
                'classe': classe,
                'moyenne_generale': round(moyenne_classe, 2),
                'taux_presence': round(taux_presence, 1),
                'nb_etudiants': classe.etudiants.count(),
            })

        # Évolution mensuelle des notes
        evolution_notes = self.get_monthly_grades_evolution(enseignant)

        context.update({
            'rapports_classes': rapports_classes,
            'evolution_notes': evolution_notes,
        })

        return context

    def get_monthly_grades_evolution(self, enseignant):
        """Évolution des notes sur les 6 derniers mois"""
        from django.db.models import Extract

        six_mois_ago = timezone.now() - timedelta(days=180)

        evolution = Note.objects.filter(
            evaluation__cours__enseignant=enseignant,
            statut='PUBLIEE',
            created_at__gte=six_mois_ago
        ).annotate(
            mois=Extract('created_at', 'month'),
            annee=Extract('created_at', 'year')
        ).values('mois', 'annee').annotate(
            moyenne=Avg('valeur'),
            nb_notes=Count('id')
        ).order_by('annee', 'mois')

        return list(evolution)

# ================================
# VUES APPRENANT
# ================================
class StudentDashboardView(RoleRequiredMixin, TemplateView):
    """Tableau de bord principal de l'apprenant avec gestion complète des paiements"""
    template_name = 'dashboard/student/index.html'
    allowed_roles = ['APPRENANT']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        try:
            # Vérification de l'inscription active
            inscription = Inscription.objects.filter(
                etudiant=etudiant,
                statut='ACTIVE'
            ).select_related(
                'candidature__filiere',
                'candidature__niveau',
                'classe_assignee'
            ).first()

            if inscription:
                # L'étudiant a une inscription active - Charger le dashboard complet
                context['inscription'] = inscription
                context['peut_acceder'] = True

                # Données du dashboard
                dashboard_data = self.get_dashboard_data(etudiant, inscription)
                context.update(dashboard_data)

            else:
                # Pas d'inscription active - Vérifier le statut pour le modal
                context['inscription'] = None
                context['peut_acceder'] = False

                # Données de statut pour le modal JavaScript
                statut_data = self.get_inscription_status_data(etudiant)
                context.update(statut_data)

        except Exception as e:
            # En cas d'erreur, bloquer l'accès et afficher une erreur
            context['inscription'] = None
            context['peut_acceder'] = False
            context['erreur_statut'] = str(e)

        return context

    def get_inscription_status_data(self, etudiant):
        """Récupère les données de statut d'inscription pour le modal"""
        try:
            # Vérifier s'il y a des paiements en cours
            paiements_en_cours = Paiement.objects.filter(
                inscription_paiement__inscription__etudiant=etudiant,
                statut__in=['EN_ATTENTE', 'EN_COURS']
            ).count()

            if paiements_en_cours > 0:
                return {
                    'statut_modal': 'paiement_en_cours',
                    'paiements_en_cours': paiements_en_cours,
                    'message_modal': f"{paiements_en_cours} paiement(s) en cours de traitement"
                }

            # Vérifier les candidatures approuvées
            candidatures_approuvees = etudiant.candidatures.filter(
                statut='APPROUVEE'
            ).count()

            if candidatures_approuvees == 0:
                return {
                    'statut_modal': 'aucune_candidature',
                    'message_modal': "Aucune candidature approuvée trouvée"
                }

            # L'étudiant doit s'inscrire
            return {
                'statut_modal': 'inscription_requise',
                'candidatures_approuvees': candidatures_approuvees,
                'message_modal': "Finalisation d'inscription requise"
            }

        except Exception as e:
            return {
                'statut_modal': 'erreur',
                'message_modal': f"Erreur de vérification: {str(e)}"
            }

    def get_dashboard_data(self, etudiant, inscription):
        """Récupère toutes les données du dashboard pour un étudiant inscrit"""
        try:
            data = {}

            # === COURS ET ACADÉMIQUE ===
            mes_cours = []
            prochain_cours = None

            if inscription.classe_assignee:
                # Cours de l'étudiant
                mes_cours = list(Cours.objects.filter(
                    classe=inscription.classe_assignee
                ).select_related('matiere', 'enseignant')[:5])

                # Prochain cours (simulation - à adapter selon votre modèle de planning)
                try:
                    from apps.courses.models import SeanceCours
                    prochain_cours = SeanceCours.objects.filter(
                        cours__classe=inscription.classe_assignee,
                        date_prevue__gt=timezone.now(),
                        statut='PROGRAMMEE'
                    ).select_related(
                        'cours__matiere', 'cours__enseignant', 'salle'
                    ).order_by('date_prevue').first()
                except ImportError:
                    pass

            data.update({
                'mes_cours': mes_cours,
                'total_cours': len(mes_cours),
                'prochain_cours': prochain_cours,
                'classe_assignee': inscription.classe_assignee,
            })

            # === ÉVALUATIONS ===
            evaluations_a_venir = []
            dernieres_notes = []
            moyenne_generale = 0

            try:
                from apps.evaluation.models import Evaluation, Note

                if inscription.classe_assignee:
                    evaluations_a_venir = list(Evaluation.objects.filter(
                        cours__classe=inscription.classe_assignee,
                        date_evaluation__gte=timezone.now(),
                        statut='PROGRAMMEE'
                    ).select_related('cours__matiere').order_by('date_evaluation')[:5])

                # Dernières notes
                dernieres_notes = list(Note.objects.filter(
                    etudiant=etudiant,
                    statut='PUBLIEE'
                ).select_related(
                    'evaluation__cours__matiere'
                ).order_by('-created_at')[:5])

                # Moyenne générale
                if dernieres_notes:
                    moyenne_generale = Note.objects.filter(
                        etudiant=etudiant,
                        statut='PUBLIEE'
                    ).aggregate(moyenne=Avg('valeur'))['moyenne'] or 0

            except ImportError:
                pass

            data.update({
                'evaluations_a_venir': evaluations_a_venir,
                'dernieres_notes': dernieres_notes,
                'moyenne_generale': round(moyenne_generale, 2),
            })

            # === PRÉSENCE ===
            taux_presence = self.get_taux_presence(etudiant)
            data['taux_presence'] = round(taux_presence, 1)

            # === PAIEMENTS ET FINANCES ===
            inscription_paiement = None
            statut_financier = {}

            try:
                inscription_paiement = InscriptionPaiement.objects.select_related(
                    'plan'
                ).prefetch_related(
                    'paiements'
                ).get(inscription=inscription)

                statut_financier = self.get_statut_financier(inscription_paiement)

            except InscriptionPaiement.DoesNotExist:
                pass

            data.update({
                'inscription_paiement': inscription_paiement,
                'statut_financier': statut_financier,
                # Compatibilité avec le template existant
                'total_paye': statut_financier.get('total_paye', 0),
                'reste_a_payer': statut_financier.get('solde', 0),
                'pourcentage_paye': statut_financier.get('pourcentage', 0),
                'statut_paiement': statut_financier.get('statut_display', 'Non défini'),
            })

            # === NOTIFICATIONS ===
            notifications = self.get_recent_notifications(etudiant, inscription_paiement)
            data['notifications'] = notifications

            # === DATES UTILES ===
            data['today'] = timezone.now().date()

            return data

        except Exception as e:
            return {
                'erreur_donnees': str(e),
                'total_cours': 0,
                'moyenne_generale': 0,
                'taux_presence': 0,
                'statut_paiement': 'Erreur',
                'today': timezone.now().date(),
            }

    def get_taux_presence(self, etudiant):
        """Calcule le taux de présence de l'étudiant"""
        try:
            total_seances = Presence.objects.filter(etudiant=etudiant).count()
            if total_seances == 0:
                return 100  # Nouveau étudiant, considérer comme 100%

            presentes = Presence.objects.filter(
                etudiant=etudiant,
                statut__in=['PRESENT', 'RETARD']
            ).count()

            return (presentes / total_seances) * 100
        except Exception:
            return 0

    def get_statut_financier(self, inscription_paiement):
        """Retourne le statut financier détaillé de l'étudiant"""
        if not inscription_paiement:
            return {}

        try:
            # Calculs de base
            total_du = inscription_paiement.montant_total_du
            total_paye = inscription_paiement.montant_total_paye
            solde = inscription_paiement.solde_restant
            pourcentage = inscription_paiement.pourcentage_paye

            # Prochaine tranche à payer
            prochaine_tranche = inscription_paiement.get_prochaine_tranche_due()

            # Statut textuel pour affichage
            statut_display_map = {
                'COMPLET': 'Soldé',
                'PARTIEL': 'Partiel',
                'EN_ATTENTE': 'En attente',
                'EN_RETARD': 'En retard'
            }

            statut_display = statut_display_map.get(
                inscription_paiement.statut,
                inscription_paiement.get_statut_display()
            )

            # Informations sur les paiements récents
            dernier_paiement = inscription_paiement.paiements.filter(
                statut='CONFIRME'
            ).order_by('-date_confirmation').first()

            return {
                'total_du': total_du,
                'total_paye': total_paye,
                'solde': solde,
                'pourcentage': pourcentage,
                'statut': inscription_paiement.statut,
                'statut_display': statut_display,
                'type_paiement': inscription_paiement.get_type_paiement_display(),
                'prochaine_tranche': prochaine_tranche,
                'dernier_paiement': dernier_paiement,
                'peut_payer_tranche': solde > 0 and prochaine_tranche is not None,
                'est_en_retard': inscription_paiement.statut == 'EN_RETARD',
            }

        except Exception as e:
            return {
                'erreur': str(e),
                'statut_display': 'Erreur',
                'pourcentage': 0
            }

    def get_recent_notifications(self, etudiant, inscription_paiement=None):
        """Génère les notifications récentes pour l'étudiant"""
        notifications = []

        try:
            # Notifications de paiement
            if inscription_paiement:
                # Paiement récent confirmé
                dernier_paiement = inscription_paiement.paiements.filter(
                    statut='CONFIRME'
                ).order_by('-date_confirmation').first()

                if dernier_paiement and dernier_paiement.date_confirmation:
                    if dernier_paiement.date_confirmation >= timezone.now() - timedelta(days=7):
                        notifications.append({
                            'type': 'payment_success',
                            'title': 'Paiement confirmé',
                            'message': f'Paiement de {dernier_paiement.montant} XOF confirmé',
                            'timestamp': dernier_paiement.date_confirmation,
                            'color': '#28a745',
                            'icon': 'fas fa-check-circle'
                        })

                # Tranche à payer bientôt
                prochaine_tranche = inscription_paiement.get_prochaine_tranche_due()
                if prochaine_tranche and prochaine_tranche.date_limite:
                    jours_restants = (prochaine_tranche.date_limite - timezone.now().date()).days
                    if 0 <= jours_restants <= 7:
                        notifications.append({
                            'type': 'payment_reminder',
                            'title': 'Échéance proche',
                            'message': f'Tranche {prochaine_tranche.numero} à payer avant le {prochaine_tranche.date_limite.strftime("%d/%m/%Y")}',
                            'timestamp': timezone.now() - timedelta(hours=1),
                            'color': '#ffc107',
                            'icon': 'fas fa-exclamation-triangle'
                        })

            # Notifications académiques (simulation)
            if len(notifications) < 3:
                notifications.extend([
                    {
                        'type': 'course',
                        'title': 'Nouvelle ressource',
                        'message': 'Un nouveau cours est disponible dans votre matière principale',
                        'timestamp': timezone.now() - timedelta(hours=3),
                        'color': '#667eea',
                        'icon': 'fas fa-book'
                    },
                    {
                        'type': 'schedule',
                        'title': 'Emploi du temps',
                        'message': 'Votre emploi du temps a été mis à jour',
                        'timestamp': timezone.now() - timedelta(days=1),
                        'color': '#36b9cc',
                        'icon': 'fas fa-calendar-alt'
                    }
                ])

            # Limiter à 5 notifications maximum
            return notifications[:5]

        except Exception as e:
            return [{
                'type': 'error',
                'title': 'Erreur notifications',
                'message': f'Impossible de charger les notifications: {str(e)}',
                'timestamp': timezone.now(),
                'color': '#dc3545',
                'icon': 'fas fa-exclamation-circle'
            }]

class StudentCoursesView(RoleRequiredMixin, ListView):
    """Liste des cours de l'apprenant"""
    model = Cours
    template_name = 'dashboard/student/courses.html'
    context_object_name = 'cours'
    allowed_roles = ['APPRENANT']
    paginate_by = 10

    def get_queryset(self):
        etudiant = self.request.user
        inscription = etudiant.inscriptions.filter(statut='ACTIVE').first()
        
        if inscription:
            return Cours.objects.filter(
                classe=inscription.classe_attribuee
            ).select_related('matiere', 'enseignant').order_by('matiere__nom')
        
        return Cours.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user
        
        # Progression par cours
        for cours in context['cours']:
            # Calcul de progression (à personnaliser selon votre logique)
            cours.progression = self.get_course_progress(etudiant, cours)
            cours.statut = self.get_course_status(etudiant, cours)
            
        return context

    def get_course_progress(self, etudiant, cours):
        """Calcule la progression de l'étudiant dans un cours"""
        # Logique de progression basée sur les présences, évaluations, etc.
        total_seances = cours.seances.count()
        presences = Presence.objects.filter(
            etudiant=etudiant,
            seance__cours=cours,
            statut__in=['PRESENT', 'RETARD']
        ).count()
        
        if total_seances > 0:
            return (presences / total_seances) * 100
        return 0

    def get_course_status(self, etudiant, cours):
        """Détermine le statut du cours pour l'étudiant"""
        progression = self.get_course_progress(etudiant, cours)
        
        if progression >= 70:
            return 'success'
        elif progression >= 50:
            return 'warning'
        else:
            return 'danger'

class StudentScheduleView(RoleRequiredMixin, TemplateView):
    """Emploi du temps de l'apprenant"""
    template_name = 'dashboard/student/schedule.html'
    allowed_roles = ['APPRENANT']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user
        
        inscription = etudiant.inscriptions.filter(statut='ACTIVE').first()
        if inscription:
            # Emploi du temps de la semaine
            context['emploi_du_temps'] = self.get_weekly_schedule(inscription.classe_attribuee)
            context['prochains_cours'] = self.get_upcoming_courses(inscription.classe_attribuee)
            
        return context

    def get_weekly_schedule(self, classe):
        """Récupère l'emploi du temps de la semaine"""
        # À adapter selon votre modèle d'emploi du temps
        cours = Cours.objects.filter(classe=classe).select_related('matiere', 'enseignant')
        
        # Organiser par jour et heure
        emploi_du_temps = {}
        for cours_item in cours:
            # Logique pour organiser les cours par créneaux horaires
            pass
            
        return emploi_du_temps

    def get_upcoming_courses(self, classe):
        """Récupère les prochains cours"""
        today = timezone.now().date()
        return Cours.objects.filter(
            classe=classe,
            seances__date_prevue__gte=today
        ).select_related('matiere', 'enseignant').order_by('seances__date_prevue')[:3]

class StudentEvaluationsView(RoleRequiredMixin, TemplateView):
    """Évaluations de l'apprenant"""
    template_name = 'evaluations/apprenant/list.html'
    allowed_roles = ['APPRENANT']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        inscription = etudiant.inscriptions.filter(statut='ACTIVE').first()
        if inscription:
            # Évaluations à venir
            evaluations_a_venir = Evaluation.objects.filter(
                cours__classe=inscription.classe_attribuee,
                date_debut__gte=timezone.now(),
                statut='PROGRAMMEE'
            ).select_related('cours__matiere').order_by('date_debut')

            # Évaluations en cours
            evaluations_en_cours = Evaluation.objects.filter(
                cours__classe=inscription.classe_attribuee,
                date_debut__lte=timezone.now(),
                date_fin__gte=timezone.now(),
                statut='EN_COURS'
            ).select_related('cours__matiere')

            # Évaluations terminées
            evaluations_terminees = Evaluation.objects.filter(
                cours__classe=inscription.classe_attribuee,
                date_fin__lt=timezone.now(),
                statut='TERMINEE'
            ).select_related('cours__matiere').order_by('-date_fin')[:10]

            context.update({
                'evaluations_a_venir': evaluations_a_venir,
                'evaluations_en_cours': evaluations_en_cours,
                'evaluations_terminees': evaluations_terminees,
            })

        return context

class StudentResultsView(RoleRequiredMixin, ListView):
    """Notes et résultats de l'apprenant - Vue complète"""
    model = Note
    template_name = 'dashboard/student/results.html'
    context_object_name = 'notes'
    allowed_roles = ['APPRENANT']
    paginate_by = 20

    def get_queryset(self):
        return Note.objects.filter(
            etudiant=self.request.user,
            statut='PUBLIEE'
        ).select_related('evaluation__cours__matiere').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        # Moyennes par matière
        moyennes_matieres = Note.objects.filter(
            etudiant=etudiant,
            statut='PUBLIEE'
        ).values(
            'evaluation__cours__matiere__nom'
        ).annotate(
            moyenne=Avg('valeur'),
            nb_notes=Count('id')
        ).order_by('evaluation__cours__matiere__nom')

        # Moyenne générale
        moyenne_generale = Note.objects.filter(
            etudiant=etudiant,
            statut='PUBLIEE'
        ).aggregate(moyenne=Avg('valeur'))['moyenne'] or 0

        # Statistiques
        total_notes = Note.objects.filter(etudiant=etudiant, statut='PUBLIEE').count()
        notes_au_dessus_10 = Note.objects.filter(
            etudiant=etudiant,
            statut='PUBLIEE',
            valeur__gte=10
        ).count()

        # Calcul du rang dans la classe
        inscription = etudiant.inscriptions.filter(statut='ACTIVE').first()
        rang_classe = 1
        moyenne_classe = 0

        if inscription:
            # Toutes les moyennes des étudiants de la classe
            moyennes_classe = []
            etudiants_classe = inscription.classe_attribuee.etudiants.all()

            for etudiant_classe in etudiants_classe:
                moy = Note.objects.filter(
                    etudiant=etudiant_classe,
                    statut='PUBLIEE'
                ).aggregate(moyenne=Avg('valeur'))['moyenne'] or 0
                moyennes_classe.append(moy)

            if moyennes_classe:
                moyenne_classe = sum(moyennes_classe) / len(moyennes_classe)
                moyennes_classe.sort(reverse=True)
                try:
                    rang_classe = moyennes_classe.index(moyenne_generale) + 1
                except ValueError:
                    rang_classe = len(moyennes_classe)

        # Évolution des notes (progression)
        notes_chronologiques = Note.objects.filter(
            etudiant=etudiant,
            statut='PUBLIEE'
        ).order_by('created_at')

        progression = 0
        if notes_chronologiques.count() >= 2:
            # Comparer les moyennes des 3 dernières notes avec les 3 précédentes
            dernieres_notes = list(notes_chronologiques[-3:])
            notes_precedentes = list(
                notes_chronologiques[-6:-3] if notes_chronologiques.count() >= 6 else notes_chronologiques[:-3])

            if dernieres_notes and notes_precedentes:
                moy_recente = sum([n.valeur for n in dernieres_notes]) / len(dernieres_notes)
                moy_precedente = sum([n.valeur for n in notes_precedentes]) / len(notes_precedentes)
                progression = moy_recente - moy_precedente

        context.update({
            'moyennes_matieres': moyennes_matieres,
            'moyenne_generale': round(moyenne_generale, 2),
            'total_notes': total_notes,
            'notes_au_dessus_10': notes_au_dessus_10,
            'rang_classe': rang_classe,
            'moyenne_classe': round(moyenne_classe, 2),
            'progression': round(progression, 2),
        })

        return context

class StudentAttendanceView(RoleRequiredMixin, ListView):
    """Présences de l'apprenant - Vue complète"""
    model = Presence
    template_name = 'dashboard/student/attendance.html'
    context_object_name = 'presences'
    allowed_roles = ['APPRENANT']
    paginate_by = 50

    def get_queryset(self):
        return Presence.objects.filter(
            etudiant=self.request.user
        ).select_related('seance__cours__matiere', 'seance__cours__enseignant').order_by('-seance__date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user

        # Statistiques générales
        total_seances = Presence.objects.filter(etudiant=etudiant).count()
        presences = Presence.objects.filter(etudiant=etudiant, statut='PRESENT').count()
        absences = Presence.objects.filter(etudiant=etudiant, statut='ABSENT').count()
        retards = Presence.objects.filter(etudiant=etudiant, statut='RETARD').count()

        taux_presence = (presences / total_seances * 100) if total_seances > 0 else 0

        # Présences par matière
        presences_par_matiere = Presence.objects.filter(
            etudiant=etudiant
        ).values(
            'seance__cours__matiere__nom'
        ).annotate(
            total=Count('id'),
            presents=Count('id', filter=Q(statut='PRESENT')),
            absents=Count('id', filter=Q(statut='ABSENT')),
            retards=Count('id', filter=Q(statut='RETARD'))
        ).order_by('seance__cours__matiere__nom')

        # Calcul du taux par matière
        for matiere in presences_par_matiere:
            if matiere['total'] > 0:
                matiere['taux_presence'] = (matiere['presents'] + matiere['retards']) / matiere['total'] * 100
            else:
                matiere['taux_presence'] = 0

        # Alertes
        alertes = []
        for matiere in presences_par_matiere:
            if matiere['taux_presence'] < 70:  # Seuil minimum
                alertes.append({
                    'type': 'danger',
                    'message': f"Votre taux de présence en {matiere['seance__cours__matiere__nom']} ({matiere['taux_presence']:.0f}%) est en dessous du minimum requis (70%)"
                })

        # Vérifier les retards consécutifs
        retards_consecutifs = self.get_consecutive_tardiness(etudiant)
        if retards_consecutifs >= 3:
            alertes.append({
                'type': 'warning',
                'message': f"{retards_consecutifs} retards consécutifs détectés. Merci de respecter les horaires."
            })

        context.update({
            'total_seances': total_seances,
            'presences': presences,
            'absences': absences,
            'retards': retards,
            'taux_presence': round(taux_presence, 1),
            'presences_par_matiere': presences_par_matiere,
            'alertes': alertes,
        })

        return context

    def get_consecutive_tardiness(self, etudiant):
        """Compte les retards consécutifs récents"""
        dernieres_presences = Presence.objects.filter(
            etudiant=etudiant
        ).order_by('-seance__date')[:10]

        retards_consecutifs = 0
        for presence in dernieres_presences:
            if presence.statut == 'RETARD':
                retards_consecutifs += 1
            else:
                break

        return retards_consecutifs

class StudentPaymentsView(LoginRequiredMixin, ListView):
    """Vue mise à jour pour les paiements de l'étudiant"""
    template_name = 'dashboard/student/payments.html'
    context_object_name = 'paiements'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        # Vérifier que l'utilisateur est un apprenant
        if request.user.role != 'APPRENANT':
            messages.error(request, "Accès non autorisé.")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Paiement.objects.filter(
            inscription_paiement__inscription__etudiant=self.request.user
        ).select_related(
            'inscription_paiement__plan',
            'tranche',
            'traite_par'
        ).order_by('-date_paiement')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Récupérer l'inscription active
        inscription_active = Inscription.objects.filter(
            etudiant=self.request.user,
            statut='ACTIVE'
        ).select_related('plan_paiement_inscription__plan').first()

        if inscription_active:
            inscription_paiement = getattr(inscription_active, 'plan_paiement_inscription', None)

            if inscription_paiement:
                context.update({
                    'inscription_paiement': inscription_paiement,
                    'prochaine_tranche': inscription_paiement.get_prochaine_tranche_due(),
                    'peut_payer_tranche': inscription_paiement.solde_restant > 0,
                    'plan_actif': inscription_paiement.plan,
                })

        return context

class StudentResourcesView(RoleRequiredMixin, ListView):
    """Ressources pédagogiques de l'apprenant"""
    model = Ressource
    template_name = 'dashboard/student/resources.html'
    context_object_name = 'resources'
    allowed_roles = ['APPRENANT']
    paginate_by = 20

    def get_queryset(self):
        etudiant = self.request.user
        inscription = etudiant.inscriptions.filter(statut='ACTIVE').first()
        
        if inscription:
            queryset = Ressource.objects.filter(
                cours__classe=inscription.classe_attribuee,
                statut='PUBLIE'
            ).select_related('cours__matiere', 'cours__enseignant')
            
            # Filtres
            matiere = self.request.GET.get('matiere')
            type_fichier = self.request.GET.get('type_fichier')
            recherche = self.request.GET.get('recherche')
            
            if matiere:
                queryset = queryset.filter(cours__matiere__id=matiere)
            
            if type_fichier:
                queryset = queryset.filter(type_fichier=type_fichier)
            
            if recherche:
                queryset = queryset.filter(
                    Q(titre__icontains=recherche) |
                    Q(description__icontains=recherche)
                )
            
            return queryset.order_by('-created_at')
        
        return Ressource.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user
        inscription = etudiant.inscriptions.filter(statut='ACTIVE').first()
        
        if inscription:
            # Matières disponibles pour le filtre
            matieres = Matiere.objects.filter(
                cours__classe=inscription.classe_attribuee
            ).distinct().order_by('nom')
            
            context['matieres'] = matieres
            
        # Types de fichiers pour le filtre
        context['types_fichiers'] = Ressource.TYPE_FICHIER_CHOICES
        
        return context

class StudentDocumentsView(RoleRequiredMixin, TemplateView):
    """Documents administratifs de l'apprenant"""
    template_name = 'dashboard/student/documents.html'
    allowed_roles = ['APPRENANT']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user
        
        # Demandes de documents
        demandes = DemandeDocument.objects.filter(
            etudiant=etudiant
        ).order_by('-date_demande')
        
        # Types de documents disponibles
        types_documents = [
            {
                'code': 'CARTE_ETUDIANT',
                'nom': 'Carte Étudiant',
                'description': 'Téléchargez votre carte d\'étudiant officielle',
                'icon': 'fas fa-id-card',
                'disponible': True
            },
            {
                'code': 'RELEVE_NOTES',
                'nom': 'Relevé de Notes',
                'description': 'Bulletin de notes du semestre en cours',
                'icon': 'fas fa-receipt',
                'disponible': True
            },
            {
                'code': 'ATTESTATION_SCOLARITE',
                'nom': 'Attestation de Scolarité',
                'description': 'Certificat prouvant votre inscription',
                'icon': 'fas fa-certificate',
                'disponible': True
            },
            {
                'code': 'RECU_PAIEMENT',
                'nom': 'Reçus de Paiement',
                'description': 'Tous vos reçus de paiement',
                'icon': 'fas fa-file-invoice',
                'disponible': True
            },
            {
                'code': 'RELEVE_PRESENCE',
                'nom': 'Relevé de Présences',
                'description': 'Historique détaillé de vos présences',
                'icon': 'fas fa-calendar-check',
                'disponible': True
            },
            {
                'code': 'DIPLOME',
                'nom': 'Diplôme',
                'description': 'Disponible après obtention',
                'icon': 'fas fa-graduation-cap',
                'disponible': False
            }
        ]
        
        context.update({
            'demandes': demandes,
            'types_documents': types_documents,
        })
        
        return context

class StudentProfileView(RoleRequiredMixin, TemplateView):
    """Profil de l'apprenant"""
    template_name = 'dashboard/student/profile.html'
    allowed_roles = ['APPRENANT']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etudiant = self.request.user
        
        inscription = etudiant.inscriptions.filter(statut='ACTIVE').first()
        
        context.update({
            'etudiant': etudiant,
            'inscription': inscription,
        })
        
        return context

    def post(self, request, *args, **kwargs):
        """Mise à jour du profil"""
        etudiant = request.user
        
        # Mise à jour des informations modifiables
        email = request.POST.get('email')
        telephone = request.POST.get('telephone')
        adresse = request.POST.get('adresse')
        
        if email:
            etudiant.email = email
        if telephone:
            etudiant.telephone = telephone
        if adresse:
            etudiant.adresse = adresse
            
        etudiant.save()
        
        messages.success(request, "Votre profil a été mis à jour avec succès.")
        return redirect('dashboard:student_profile')


# ================================
# VUES PROFIL COMMUNES
# ================================
class ProfileView(LoginRequiredMixin, TemplateView):
    """Vue du profil utilisateur"""
    template_name = 'dashboard/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['user'] = user

        # ✅ Calculer l’âge si date_naissance existe
        if user.date_naissance:
            context['age_str'] = timesince(user.date_naissance, now=date.today()).split(",")[0]
            today = date.today()
            context['age_years'] = today.year - user.date_naissance.year - (
                (today.month, today.day) < (user.date_naissance.month, user.date_naissance.day)
            )
        else:
            context['age_str'] = None
            context['age_years'] = None

        # ================================
        # 👤 Profil APPRENANT
        # ================================
        if user.role == 'APPRENANT':
            try:
                profil_apprenant = user.profil_apprenant
                context['profil_apprenant'] = profil_apprenant

                # Inscription active
                inscription = Inscription.objects.filter(
                    etudiant=user,
                    statut='ACTIVE'
                ).select_related(
                    'candidature__filiere',
                    'candidature__niveau',
                    'classe_assignee'
                ).first()
                context['inscription'] = inscription

                # 📚 Statistiques académiques
                if inscription and inscription.classe_assignee:
                    context['total_cours'] = Cours.objects.filter(
                        classe=inscription.classe_assignee
                    ).count()

                    total_presences = Presence.objects.filter(etudiant=user).count()
                    if total_presences > 0:
                        presences_valides = Presence.objects.filter(
                            etudiant=user,
                            statut__in=['PRESENT', 'RETARD']
                        ).count()
                        context['taux_presence'] = round((presences_valides / total_presences) * 100, 1)
                    else:
                        context['taux_presence'] = 100

                    # 📊 Moyenne générale
                    try:
                        from apps.evaluations.models import Note
                        notes = Note.objects.filter(
                            etudiant=user,
                            statut='PUBLIEE'
                        ).aggregate(moyenne=models.Avg('valeur'))
                        context['moyenne_generale'] = round(notes['moyenne'] or 0, 2)
                    except:
                        context['moyenne_generale'] = 0

                # 💳 Paiement
                try:
                    inscription_paiement = InscriptionPaiement.objects.get(inscription=inscription)
                    context['inscription_paiement'] = inscription_paiement
                    context['statut_paiement'] = inscription_paiement.get_statut_display()
                    context['pourcentage_paye'] = inscription_paiement.pourcentage_paye
                except:
                    pass

            except ProfilApprenant.DoesNotExist:
                pass

        # ================================
        # 👨‍🏫 Profil ENSEIGNANT
        # ================================
        elif user.role == 'ENSEIGNANT':
            try:
                profil_enseignant = user.profil_enseignant
                context['profil_enseignant'] = profil_enseignant

                context['mes_cours'] = Cours.objects.filter(
                    enseignant=user
                ).select_related('matiere', 'classe').count()

                context['mes_classes'] = Classe.objects.filter(
                    cours__enseignant=user
                ).distinct().count()

                context['total_etudiants'] = Utilisateur.objects.filter(
                    profil_apprenant__classe_actuelle__cours__enseignant=user,
                    role='APPRENANT'
                ).distinct().count()

                context['evaluations_creees'] = Evaluation.objects.filter(
                    enseignant=user
                ).count()

            except ProfilEnseignant.DoesNotExist:
                pass

        # ================================
        # 🛠️ Profil ADMIN ou CHEF_DEPARTEMENT
        # ================================
        elif user.role in ['ADMIN', 'CHEF_DEPARTEMENT']:
            if user.role == 'ADMIN':
                etablissement = user.etablissement
                context['total_users'] = Utilisateur.objects.filter(
                    etablissement=etablissement
                ).count()
                context['total_departements'] = Departement.objects.filter(
                    etablissement=etablissement
                ).count()

                # ✅ Ajoutés pour éviter les erreurs
                context['total_enseignants'] = Utilisateur.objects.filter(
                    etablissement=etablissement,
                    role='ENSEIGNANT'
                ).count()
                context['total_apprenants'] = Utilisateur.objects.filter(
                    etablissement=etablissement,
                    role='APPRENANT'
                ).count()

            else:  # CHEF_DEPARTEMENT
                departement = user.departement
                context['total_enseignants'] = Utilisateur.objects.filter(
                    departement=departement,
                    role='ENSEIGNANT'
                ).count()
                context['total_apprenants'] = Utilisateur.objects.filter(
                    departement=departement,
                    role='APPRENANT'
                ).count()

        # ================================
        # 🔎 Profil utilisateur étendu
        # ================================
        try:
            context['profil_utilisateur'] = user.profil
        except:
            pass

        # 📅 Dernière activité
        context['derniere_activite'] = user.last_login or user.date_creation

        return context

class EditProfileView(LoginRequiredMixin, UpdateView):
    """Vue de modification du profil"""
    model = Utilisateur
    template_name = 'dashboard/edit_profile.html'
    success_url = reverse_lazy('dashboard:profile')

    def get_object(self):
        return self.request.user

    def get_form_class(self):
        """Retourne le formulaire selon le rôle"""
        user = self.request.user

        if user.role == 'APPRENANT':
            from apps.accounts.forms import StudentProfileForm
            return StudentProfileForm
        elif user.role == 'ENSEIGNANT':
            from apps.accounts.forms import TeacherProfileForm
            return TeacherProfileForm
        else:
            from apps.accounts.forms import BasicProfileForm
            return BasicProfileForm

    def form_valid(self, form):
        messages.success(self.request, "Votre profil a été mis à jour avec succès.")

        # Si c'est une requête AJAX
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Profil mis à jour avec succès'
            })

        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier mon profil'
        context['is_modal'] = self.request.GET.get('modal') == '1'
        return context

class ChangePasswordView(LoginRequiredMixin, FormView):
    """Vue de changement de mot de passe"""
    template_name = 'dashboard/change_password.html'
    form_class = PasswordChangeForm
    success_url = reverse_lazy('dashboard:profile')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save()
        # Maintenir la session après changement de mot de passe
        update_session_auth_hash(self.request, user)

        messages.success(
            self.request,
            "Votre mot de passe a été modifié avec succès."
        )

        # Si c'est une requête AJAX
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Mot de passe modifié avec succès'
            })

        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Changer mon mot de passe'
        context['is_modal'] = self.request.GET.get('modal') == '1'
        return context

@login_required
def upload_profile_photo(request):
    if request.method == 'POST' and request.FILES.get('photo'):
        request.user.photo = request.FILES['photo']
        request.user.save()
        return redirect('profile')  # ou le nom de ta page profil
    return redirect('profile')
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