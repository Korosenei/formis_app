# apps/accounting/views.py
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, FormView, TemplateView
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Sum, F
from datetime import timedelta, timezone
from decimal import Decimal
import datetime

from .forms import FactureForm, DepenseForm, CompteComptableForm, EcritureComptableForm
from .models import (
    Facture, LigneFacture, Depense, CompteComptable,
    EcritureComptable, LigneEcriture, BudgetPrevisionnel, ExerciceComptable
)

from .utils import RapportComptablePDF, ComptabiliteUtils

from apps.academic.models import Departement, Classe
from apps.courses.models import Module, Matiere, StatutCours, TypeCours, Cours, Presence, Ressource, CahierTexte, EmploiDuTemps
from apps.enrollment.models import Candidature, Inscription
from apps.evaluations.models import Evaluation, Note
from apps.payments.models import Paiement, PlanPaiement, InscriptionPaiement


# ============================================================
# VUES DÉTAILS ET CRÉATION
# ============================================================
class ComptableFactureDetailView(LoginRequiredMixin, DetailView):
    """Détail d'une facture"""
    template_name = 'accounting/factures/detail.html'
    context_object_name = 'facture'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Facture.objects.filter(
            etablissement=self.request.user.etablissement
        ).select_related('apprenant', 'inscription').prefetch_related('lignes')

class ComptableFactureCreateView(LoginRequiredMixin, CreateView):
    """Création d'une facture"""
    template_name = 'accounting/factures/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        return FactureForm(
            etablissement=self.request.user.etablissement,
            **self.get_form_kwargs()
        )

    def form_valid(self, form):

        facture = form.save(commit=False)
        facture.etablissement = self.request.user.etablissement
        facture.emise_par = self.request.user

        # Statut selon l'action
        action = self.request.POST.get('action', 'draft')
        if action == 'issue':
            facture.statut = 'EMISE'
        else:
            facture.statut = 'BROUILLON'

        facture.save()

        # Créer les lignes
        descriptions = self.request.POST.getlist('ligne_description[]')
        quantites = self.request.POST.getlist('ligne_quantite[]')
        prix = self.request.POST.getlist('ligne_prix[]')

        for i, desc in enumerate(descriptions):
            if desc.strip():
                LigneFacture.objects.create(
                    facture=facture,
                    description=desc,
                    quantite=Decimal(quantites[i]),
                    prix_unitaire=Decimal(prix[i]),
                    numero_ligne=i + 1
                )

        messages.success(self.request, f"Facture {facture.numero_facture} créée avec succès")
        return redirect('dashboard:comptable_facture_detail', pk=facture.pk)

class ComptableFactureUpdateView(LoginRequiredMixin, UpdateView):
    """Modification d'une facture"""
    template_name = 'accounting/factures/edit.html'
    context_object_name = 'facture'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Facture.objects.filter(
            etablissement=self.request.user.etablissement,
            statut='BROUILLON'
        )

    def get_success_url(self):
        return reverse('dashboard:comptable_facture_detail', kwargs={'pk': self.object.pk})

@login_required
def comptable_facture_pdf(request, pk):
    """Génère le PDF d'une facture"""
    if request.user.role != 'COMPTABLE':
        return HttpResponseForbidden()

    facture = get_object_or_404(
        Facture,
        pk=pk,
        etablissement=request.user.etablissement
    )

    pdf = RapportComptablePDF.generer_facture(facture)

    response = HttpResponse(pdf.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="facture_{facture.numero_facture}.pdf"'

    return response


# ============================================================
# VUES DÉPENSES
# ============================================================
class ComptableDepenseCreateView(LoginRequiredMixin, CreateView):
    """Création d'une dépense"""
    template_name = 'accounting/depenses/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        return DepenseForm(**self.get_form_kwargs())

    def form_valid(self, form):
        depense = form.save(commit=False)
        depense.etablissement = self.request.user.etablissement
        depense.saisi_par = self.request.user
        depense.save()

        messages.success(self.request, f"Dépense {depense.numero_depense} enregistrée")
        return redirect('dashboard:comptable_depense_detail', pk=depense.pk)

class ComptableDepenseDetailView(LoginRequiredMixin, DetailView):
    """Détail d'une dépense"""
    template_name = 'accounting/depenses/detail.html'
    context_object_name = 'depense'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Depense.objects.filter(
            etablissement=self.request.user.etablissement
        )

class ComptableDepenseUpdateView(LoginRequiredMixin, UpdateView):
    """Modification d'une dépense"""
    template_name = 'accounting/depenses/edit.html'
    context_object_name = 'depense'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Depense.objects.filter(
            etablissement=self.request.user.etablissement,
            statut='EN_ATTENTE'
        )

    def get_success_url(self):
        return reverse('dashboard:comptable_depense_detail', kwargs={'pk': self.object.pk})

@login_required
@require_POST
def comptable_depense_approuver(request, pk):
    """Approuver une dépense"""
    if request.user.role != 'COMPTABLE':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    depense = get_object_or_404(
        Depense,
        pk=pk,
        etablissement=request.user.etablissement
    )

    if depense.statut != 'EN_ATTENTE':
        return JsonResponse({
            'success': False,
            'error': 'Cette dépense ne peut pas être approuvée'
        })

    depense.statut = 'APPROUVEE'
    depense.approuve_par = request.user
    depense.date_approbation = timezone.now()
    depense.save()

    messages.success(request, f'Dépense {depense.numero_depense} approuvée')

    return JsonResponse({'success': True})


# ============================================================
# VUES PLAN COMPTABLE
# ============================================================
class ComptableCompteCreateView(LoginRequiredMixin, CreateView):
    """Création d'un compte comptable"""
    template_name = 'accounting/comptes/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        return CompteComptableForm(
            etablissement=self.request.user.etablissement,
            **self.get_form_kwargs()
        )

    def form_valid(self, form):
        compte = form.save(commit=False)
        compte.etablissement = self.request.user.etablissement
        compte.save()

        messages.success(self.request, f"Compte {compte.numero_compte} créé")
        return redirect('dashboard:comptable_comptes')


# ============================================================
# VUES ÉCRITURES COMPTABLES
# ============================================================
class ComptableEcrituresView(LoginRequiredMixin, ListView):
    """Liste des écritures comptables"""
    template_name = 'accounting/ecritures/list.html'
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

class ComptableEcritureCreateView(LoginRequiredMixin, CreateView):
    """Création d'une écriture comptable"""
    template_name = 'accounting/ecritures/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        return EcritureComptableForm(**self.get_form_kwargs())

    def form_valid(self, form):

        ecriture = form.save(commit=False)
        ecriture.etablissement = self.request.user.etablissement
        ecriture.saisi_par = self.request.user
        ecriture.save()

        # Créer les lignes
        comptes = self.request.POST.getlist('ligne_compte[]')
        libelles = self.request.POST.getlist('ligne_libelle[]')
        debits = self.request.POST.getlist('ligne_debit[]')
        credits = self.request.POST.getlist('ligne_credit[]')

        for i, compte_id in enumerate(comptes):
            if compte_id:
                LigneEcriture.objects.create(
                    ecriture=ecriture,
                    compte_id=compte_id,
                    libelle=libelles[i],
                    debit=Decimal(debits[i] or 0),
                    credit=Decimal(credits[i] or 0),
                    numero_ligne=i + 1
                )

        # Vérifier l'équilibre
        if ecriture.est_equilibree:
            messages.success(self.request, f"Écriture {ecriture.numero_piece} créée")
        else:
            messages.warning(
                self.request,
                f"Écriture créée mais non équilibrée (Débit: {ecriture.total_debit}, Crédit: {ecriture.total_credit})"
            )

        return redirect('dashboard:comptable_ecritures')

class ComptableEcritureDetailView(LoginRequiredMixin, DetailView):
    """Détail d'une écriture"""
    model = EcritureComptable
    template_name = 'accounting/ecritures/detail.html'
    context_object_name = 'ecriture'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'COMPTABLE':
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return EcritureComptable.objects.filter(
            etablissement=self.request.user.etablissement
        ).prefetch_related('lignes__compte')

# ============================================================
# VUES RAPPORTS
# ============================================================
class ComptableRapportBalanceView(LoginRequiredMixin, TemplateView):
    """Rapport balance détaillée"""
    template_name = 'accounting/ecritures/balance.html'

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

@login_required
def comptable_rapport_bilan(request):
    """Génère le bilan comptable"""
    if request.user.role != 'COMPTABLE':
        return HttpResponseForbidden()

    import datetime

    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    format_export = request.GET.get('format', 'view')

    if not date_debut or not date_fin:
        messages.error(request, "Dates requises")
        return redirect('dashboard:comptable_rapports')

    date_debut = datetime.datetime.strptime(date_debut, '%Y-%m-%d').date()
    date_fin = datetime.datetime.strptime(date_fin, '%Y-%m-%d').date()

    # Générer le bilan

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

    bilan_data = {
        'actif': [],
        'passif': [],
        'total_actif': Decimal('0.00'),
        'total_passif': Decimal('0.00')
    }

    for compte in comptes_actif:
        solde = ComptabiliteUtils.calculer_solde_compte(compte, date_debut, date_fin)
        if solde != 0:
            bilan_data['actif'].append({
                'compte': compte,
                'solde': solde
            })
            bilan_data['total_actif'] += solde

    for compte in comptes_passif:
        solde = ComptabiliteUtils.calculer_solde_compte(compte, date_debut, date_fin)
        if solde != 0:
            bilan_data['passif'].append({
                'compte': compte,
                'solde': solde
            })
            bilan_data['total_passif'] += solde

    context = {
        'bilan': bilan_data,
        'date_debut': date_debut,
        'date_fin': date_fin,
    }

    if format_export == 'pdf':
        # TODO: Générer PDF
        messages.info(request, "Export PDF en développement")
        return redirect('dashboard:comptable_rapports')

    return render(request, 'accounting/rapports/bilan.html', context)

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
            resultat_data['charges'].append({
                'compte': compte,
                'montant': abs(solde)
            })
            resultat_data['total_charges'] += abs(solde)

    for compte in comptes_produits:
        solde = ComptabiliteUtils.calculer_solde_compte(compte, date_debut, date_fin)
        if solde != 0:
            resultat_data['produits'].append({
                'compte': compte,
                'montant': abs(solde)
            })
            resultat_data['total_produits'] += abs(solde)

    resultat_data['resultat'] = resultat_data['total_produits'] - resultat_data['total_charges']

    context = {
        'resultat': resultat_data,
        'date_debut': date_debut,
        'date_fin': date_fin,
    }

    return render(request, 'accounting/rapports/resultat.html', context)

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

    return render(request, 'accounting/rapports/tresorerie.html', context)


# ============================================================
# VUES EXERCICES COMPTABLES
# ============================================================
@login_required
@require_POST
def comptable_cloture_exercice(request, pk):
    """Clôturer un exercice comptable"""
    if request.user.role != 'COMPTABLE':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    exercice = get_object_or_404(
        ExerciceComptable,
        pk=pk,
        etablissement=request.user.etablissement
    )

    if exercice.est_cloture:
        return JsonResponse({
            'success': False,
            'error': 'Cet exercice est déjà clôturé'
        })

    exercice.est_cloture = True
    exercice.date_cloture = timezone.now()
    exercice.cloture_par = request.user
    exercice.save()

    messages.success(request, f'Exercice {exercice.libelle} clôturé')

    return JsonResponse({'success': True})

@login_required
@require_POST
def comptable_valider_paiement(request, paiement_id):
    """Valider un paiement"""
    if request.user.role != 'COMPTABLE':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    paiement = get_object_or_404(
        Paiement,
        id=paiement_id,
        inscription_paiement__inscription__apprenant__etablissement=request.user.etablissement
    )

    if paiement.statut != 'EN_ATTENTE':
        return JsonResponse({
            'success': False,
            'error': 'Ce paiement ne peut pas être validé'
        })

    paiement.statut = 'CONFIRME'
    paiement.traite_par = request.user
    paiement.date_confirmation = timezone.now()
    paiement.save()

    messages.success(request, f'Paiement {paiement.numero_transaction} validé avec succès')

    return JsonResponse({'success': True})

@login_required
@require_POST
def comptable_rejeter_paiement(request, paiement_id):
    """Rejeter un paiement"""
    if request.user.role != 'COMPTABLE':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    paiement = get_object_or_404(
        Paiement,
        id=paiement_id,
        inscription_paiement__inscription__apprenant__etablissement=request.user.etablissement
    )

    motif = request.POST.get('motif', '')

    if not motif:
        return JsonResponse({
            'success': False,
            'error': 'Veuillez fournir un motif de rejet'
        })

    paiement.statut = 'ECHEC'
    paiement.traite_par = request.user
    paiement.notes_admin = f"Rejeté par {request.user.get_full_name()}: {motif}"
    paiement.save()

    messages.warning(request, f'Paiement {paiement.numero_transaction} rejeté')

    return JsonResponse({'success': True})