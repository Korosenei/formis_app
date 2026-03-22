
from django.db import models, transaction
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
from django.views.decorators.http import require_POST, require_http_methods
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
from django.db.models import Prefetch

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


class DashboardRedirect(LoginRequiredMixin, TemplateView):
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
class AdminDashboard(LoginRequiredMixin, TemplateView):
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


# ================================
# VUES COMPTABLE
# ================================
class ComptableDashboard(LoginRequiredMixin, TemplateView):
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


# ================================
# VUES CHEF DEPARTEMENT
# ================================
class DepartmentHeadDashboard(LoginRequiredMixin, TemplateView):
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


# ================================
# VUES ENSEIGNANT
# ================================
class TeacherDashboard(LoginRequiredMixin, TemplateView):
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


# ================================
# VUES APPRENANT
# ================================
class StudentDashboard(LoginRequiredMixin, TemplateView):
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
