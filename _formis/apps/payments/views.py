# apps/payments/views.py
import json
import logging
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse, reverse_lazy
from django.core.exceptions import ValidationError
from django.conf import settings
import secrets
import string

from .models import (
    PlanPaiement, TranchePaiement, InscriptionPaiement,
    Paiement, HistoriquePaiement
)
from .services.ligdicash import ligdicash_service, creer_urls_retour
from apps.enrollment.models import Candidature, Inscription, DocumentCandidature
from apps.academic.models import Filiere, Niveau
from apps.accounts.models import ProfilUtilisateur, ProfilApprenant, Utilisateur

from apps.enrollment.managers import EmailCandidatureManager

from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string

logger = logging.getLogger(__name__)
User = get_user_model()

class AdminStudentPaymentsView(LoginRequiredMixin, DetailView):
    """Gestion des paiements d'un étudiant par l'admin"""
    model = Utilisateur
    template_name = 'payments/admin_student_payments.html'
    context_object_name = 'student'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Utilisateur.objects.filter(role='APPRENANT')
        if self.request.user.role == 'ADMIN':
            return qs.filter(etablissement=self.request.user.etablissement)
        else:
            return qs.filter(departement=self.request.user.departement)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object

        # Inscription active
        inscription = Inscription.objects.filter(
            apprenant=student,
            statut='ACTIVE'
        ).select_related(
            'candidature__filiere',
            'candidature__niveau'
        ).first()

        context['inscription'] = inscription

        if inscription:
            try:
                # InscriptionPaiement
                inscription_paiement = InscriptionPaiement.objects.get(
                    inscription=inscription
                )
                context['inscription_paiement'] = inscription_paiement
                context['plan_paiement'] = inscription_paiement.plan

                # Paiements
                paiements = Paiement.objects.filter(
                    inscription_paiement=inscription_paiement
                ).order_by('-date_paiement')
                context['paiements'] = paiements

                # 🔹 Créer un dictionnaire {tranche_id: paiement}
                paiements_par_tranche = {p.tranche_id: p for p in paiements}
                context['paiements_par_tranche'] = paiements_par_tranche

                # Statistiques
                context['stats'] = {
                    'total_du': inscription_paiement.montant_total_du,
                    'total_paye': inscription_paiement.montant_total_paye,
                    'solde': inscription_paiement.solde_restant,
                    'pourcentage': inscription_paiement.pourcentage_paye,
                }

                # Prochaine tranche
                context['prochaine_tranche'] = inscription_paiement.get_prochaine_tranche_due()

            except InscriptionPaiement.DoesNotExist:
                context['inscription_paiement'] = None
                context['paiements'] = []
                context['paiements_par_tranche'] = {}
                context['stats'] = {}
                context['prochaine_tranche'] = None

        return context

@login_required
def admin_initiate_student_payment(request, student_id):
    """
    Admin/Chef Département initie un paiement pour un étudiant
    Cette vue redirige vers le flow de paiement LigdiCash
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        return JsonResponse({'error': 'Non autorisé'}, status=403)

    student = get_object_or_404(Utilisateur, id=student_id, role='APPRENANT')

    # Vérifier permissions
    if request.user.role == 'ADMIN':
        if student.etablissement != request.user.etablissement:
            return JsonResponse({'error': 'Non autorisé'}, status=403)
    else:
        if student.departement != request.user.departement:
            return JsonResponse({'error': 'Non autorisé'}, status=403)

    # Récupérer l'inscription active
    inscription = Inscription.objects.filter(
        apprenant=student,
        statut='ACTIVE'
    ).select_related('plan_paiement_inscription__plan').first()

    if not inscription:
        return JsonResponse({
            'success': False,
            'message': 'Aucune inscription active pour cet étudiant'
        })

    inscription_paiement = inscription.plan_paiement_inscription

    # Vérifier s'il reste un solde
    if inscription_paiement.solde_restant <= 0:
        return JsonResponse({
            'success': False,
            'message': 'Tous les paiements sont déjà effectués'
        })

    # Récupérer la prochaine tranche
    prochaine_tranche = inscription_paiement.get_prochaine_tranche_due()

    if not prochaine_tranche:
        return JsonResponse({
            'success': False,
            'message': 'Aucune tranche de paiement disponible'
        })

    # Vérifier qu'il n'y a pas déjà un paiement en cours
    paiement_en_cours = Paiement.objects.filter(
        inscription_paiement=inscription_paiement,
        tranche=prochaine_tranche,
        statut__in=['EN_ATTENTE', 'EN_COURS']
    ).first()

    if paiement_en_cours:
        return JsonResponse({
            'success': True,
            'message': 'Un paiement est déjà en cours',
            'paiement_id': str(paiement_en_cours.id),
            'redirect_url': reverse('payments:payer_ligdicash', kwargs={'paiement_id': paiement_en_cours.id})
        })

    # Créer le paiement
    with transaction.atomic():
        paiement = Paiement.objects.create(
            inscription_paiement=inscription_paiement,
            tranche=prochaine_tranche,
            montant=prochaine_tranche.get_montant_avec_penalite(),
            methode_paiement='LIGDICASH',
            statut='EN_ATTENTE',
            description=f"Tranche {prochaine_tranche.numero} - {prochaine_tranche.nom} (Initié par {request.user.get_full_name()})",
            date_echeance=prochaine_tranche.date_limite,
            traite_par=request.user
        )

        HistoriquePaiement.objects.create(
            paiement=paiement,
            type_action='CREATION',
            nouveau_statut='EN_ATTENTE',
            details=f"Paiement créé par {request.user.get_full_name()} pour {student.get_full_name()}",
            utilisateur=request.user,
            adresse_ip=request.META.get('REMOTE_ADDR')
        )

    logger.info(f"[ADMIN] Paiement {paiement.numero_transaction} créé par {request.user.email} pour {student.email}")

    return JsonResponse({
        'success': True,
        'message': 'Paiement créé avec succès',
        'paiement_id': str(paiement.id),
        'redirect_url': reverse('payments:payer_ligdicash', kwargs={'paiement_id': paiement.id})
    })

@login_required
def verifier_statut_inscription(request):
    """
    Vérifie le statut d'inscription avec gestion des PENDING orphelins
    """
    user = request.user

    logger.info(f"🔍 Vérification statut pour {user.email} (Matricule: {user.matricule})")

    try:
        # ========== ÉTAPE 1: Inscription ACTIVE ==========
        inscription_active = Inscription.objects.filter(
            apprenant=user,
            statut='ACTIVE'
        ).select_related('candidature', 'classe_assignee').first()

        if inscription_active:
            logger.info(f"✅ Inscription ACTIVE: {inscription_active.numero_inscription}")
            return JsonResponse({
                'peut_acceder': True,
                'message': 'Inscription active',
                'inscription_id': str(inscription_active.id),
                'numero_inscription': inscription_active.numero_inscription
            })

        # ========== ÉTAPE 2: Inscription PENDING ==========
        inscription_pending = Inscription.objects.filter(
            apprenant=user,
            statut='PENDING'
        ).select_related('candidature').first()

        if inscription_pending:
            logger.info(f"⏳ Inscription PENDING: {inscription_pending.numero_inscription}")

            # Vérifier les paiements
            paiements_en_cours = Paiement.objects.filter(
                inscription_paiement__inscription=inscription_pending,
                statut__in=['EN_ATTENTE', 'EN_COURS']
            )

            paiements_count = paiements_en_cours.count()

            if paiements_count > 0:
                logger.info(f"💳 {paiements_count} paiement(s) en cours")

                # Vérifier si les paiements sont récents (< 1 heure)
                from django.utils import timezone
                from datetime import timedelta

                paiements_recents = paiements_en_cours.filter(
                    created_at__gte=timezone.now() - timedelta(hours=1)
                )

                if paiements_recents.exists():
                    return JsonResponse({
                        'peut_acceder': False,
                        'message': 'Paiement en cours de traitement',
                        'action_requise': 'attendre',
                        'paiements_en_cours': paiements_count,
                        'inscription_pending': {
                            'id': str(inscription_pending.id),
                            'numero': inscription_pending.numero_inscription
                        }
                    })
                else:
                    # Paiements anciens bloqués - Nettoyer et permettre nouvelle tentative
                    logger.warning(
                        f"⚠️ Paiements PENDING anciens détectés - Nettoyage pour {user.email}"
                    )

                    # Marquer les vieux paiements comme expirés
                    paiements_en_cours.update(
                        statut='ANNULE',
                        notes_admin='Paiement expiré automatiquement après 1 heure'
                    )

                    # Permettre une nouvelle tentative
                    logger.info("✅ Nettoyage effectué - Nouvelle tentative possible")

            # Pas de paiements en cours ou nettoyés
            # → Supprimer l'inscription PENDING orpheline et permettre nouvelle tentative
            logger.warning(
                f"⚠️ Inscription PENDING sans paiement actif - Suppression pour {user.email}"
            )

            try:
                # Supprimer l'InscriptionPaiement associé
                InscriptionPaiement.objects.filter(inscription=inscription_pending).delete()

                # Supprimer l'inscription
                inscription_pending.delete()

                logger.info("✅ Inscription PENDING orpheline supprimée")
            except Exception as e:
                logger.error(f"❌ Erreur suppression inscription PENDING: {str(e)}")

        # ========== ÉTAPE 3: Chercher candidatures APPROUVEES ==========
        logger.info(f"🔍 Recherche candidatures APPROUVEES")
        logger.info(f"   Email: {user.email}")
        logger.info(f"   Matricule: {user.matricule}")

        candidatures_approuvees = None
        methode_recherche = None

        # MÉTHODE 1: Par EMAIL
        candidatures_approuvees = Candidature.objects.filter(
            email=user.email,
            statut='APPROUVEE',
            etablissement=user.etablissement  # ← AJOUT: Filtrer par établissement
        ).exclude(
            inscription__isnull=False
        )

        if candidatures_approuvees.exists():
            methode_recherche = "email"
            logger.info(f"✅ Par email: {candidatures_approuvees.count()} candidature(s)")

        # MÉTHODE 2: Par IDENTITÉ
        if not candidatures_approuvees or not candidatures_approuvees.exists():
            logger.warning(f"⚠️ Recherche par IDENTITÉ...")

            candidatures_approuvees = Candidature.objects.filter(
                prenom__iexact=user.prenom,
                nom__iexact=user.nom,
                etablissement=user.etablissement,
                statut='APPROUVEE'
            )

            if user.date_naissance:
                candidatures_approuvees = candidatures_approuvees.filter(
                    date_naissance=user.date_naissance
                )

            candidatures_approuvees = candidatures_approuvees.exclude(
                inscription__isnull=False
            )

            if candidatures_approuvees.exists():
                methode_recherche = "identite"
                logger.info(f"✅ Par identité: {candidatures_approuvees.count()} candidature(s)")

                # Mettre à jour les emails
                for candidature in candidatures_approuvees:
                    ancien_email = candidature.email
                    candidature.email = user.email
                    candidature.save(update_fields=['email'])
                    logger.info(f"   📧 Email MAJ: {ancien_email} → {user.email}")

        candidatures_approuvees = candidatures_approuvees.select_related(
            'filiere', 'niveau', 'annee_academique', 'etablissement'
        ) if candidatures_approuvees else Candidature.objects.none()

        nombre_candidatures = candidatures_approuvees.count()

        logger.info(f"📊 RÉSULTAT: {nombre_candidatures} candidature(s) - Méthode: {methode_recherche}")

        if nombre_candidatures == 0:
            logger.warning(f"❌ AUCUNE candidature trouvée")

            # Debug: Afficher les candidatures disponibles
            toutes_approuvees = Candidature.objects.filter(
                etablissement=user.etablissement,
                statut='APPROUVEE'
            ).exclude(inscription__isnull=False)[:5]

            logger.info(f"📝 Candidatures disponibles dans l'établissement:")
            for c in toutes_approuvees:
                logger.info(
                    f"   - {c.numero_candidature}: {c.prenom} {c.nom} ({c.email})"
                )

            return JsonResponse({
                'peut_acceder': False,
                'message': 'Aucune candidature approuvée trouvée.',
                'action_requise': 'candidater',
                'candidatures_approuvees': 0,
                'debug_info': {
                    'email': user.email,
                    'matricule': user.matricule,
                    'etablissement': user.etablissement.nom
                }
            })

        # ========== ÉTAPE 4: Inscription requise ==========
        logger.info(f"✅ {nombre_candidatures} candidature(s) prête(s)")

        for c in candidatures_approuvees:
            logger.info(f"   - {c.numero_candidature}: {c.filiere.nom} - {c.niveau.nom}")

        return JsonResponse({
            'peut_acceder': False,
            'message': 'Veuillez finaliser votre inscription en effectuant le paiement.',
            'action_requise': 'inscrire',
            'candidatures_approuvees': nombre_candidatures
        })

    except Exception as e:
        logger.error(f"❌ Erreur vérification: {str(e)}", exc_info=True)
        return JsonResponse({
            'peut_acceder': False,
            'message': f'Erreur: {str(e)}',
            'action_requise': 'erreur',
            'error': str(e)
        }, status=500)

@login_required
def initier_inscription_paiement(request):
    """
    Vue pour initier le paiement d'inscription
    """
    if request.method == 'GET':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            user = request.user
            logger.info(f"📥 Requête AJAX initier_inscription pour {user.email}")

            # Vérifier si déjà inscrit
            inscription_active = Inscription.objects.filter(
                apprenant=user,
                statut='ACTIVE'
            ).first()

            if inscription_active:
                logger.info(f"✅ Utilisateur déjà inscrit: {inscription_active.numero_inscription}")
                return JsonResponse({
                    'success': False,
                    'message': 'Vous êtes déjà inscrit.',
                    'redirect': reverse('dashboard:student')
                })

            candidatures_approuvees = Candidature.objects.filter(
                email=user.email,
                statut='APPROUVEE'
            ).exclude(
                inscription__isnull=False
            )

            # Si rien trouvé par email, chercher par nom/prénom
            if not candidatures_approuvees.exists():
                logger.warning(f"⚠️ Aucune candidature par email, recherche par nom/prénom...")

                candidatures_approuvees = Candidature.objects.filter(
                    prenom__iexact=user.prenom,
                    nom__iexact=user.nom,
                    statut='APPROUVEE'
                )

                if user.date_naissance:
                    candidatures_approuvees = candidatures_approuvees.filter(
                        date_naissance=user.date_naissance
                    )

                candidatures_approuvees = candidatures_approuvees.exclude(
                    inscription__isnull=False
                )

                # Mettre à jour l'email
                if candidatures_approuvees.exists():
                    for candidature in candidatures_approuvees:
                        candidature.email = user.email
                        candidature.save()

            candidatures_approuvees = candidatures_approuvees.select_related(
                'filiere', 'niveau', 'annee_academique', 'etablissement'
            )

            if not candidatures_approuvees.exists():
                logger.warning(f"❌ Aucune candidature approuvée pour {user.email}")
                return JsonResponse({
                    'success': False,
                    'message': 'Aucune candidature approuvée disponible pour inscription.',
                    'action_requise': 'candidater'
                })

            # Récupérer les plans de paiement
            plans_disponibles = []
            for candidature in candidatures_approuvees:
                try:
                    plan = PlanPaiement.objects.get(
                        filiere=candidature.filiere,
                        niveau=candidature.niveau,
                        annee_academique=candidature.annee_academique,
                        est_actif=True
                    )

                    logger.info(f"📋 Plan trouvé pour {candidature.filiere.nom} - {candidature.niveau.nom}")

                    # Récupérer les tranches
                    tranches = list(plan.tranches.order_by('numero').values(
                        'id', 'numero', 'nom', 'montant', 'date_limite',
                        'est_premiere_tranche'
                    ))

                    for tranche in tranches:
                        if tranche['date_limite']:
                            tranche['date_limite'] = tranche['date_limite'].strftime('%d/%m/%Y')
                        tranche['id'] = str(tranche['id'])

                    premiere_tranche = plan.tranches.filter(
                        est_premiere_tranche=True
                    ).first()

                    if not premiere_tranche:
                        premiere_tranche = plan.tranches.order_by('numero').first()

                    plans_disponibles.append({
                        'candidature': {
                            'id': str(candidature.id),
                            'numero': candidature.numero_candidature,
                            'etablissement_nom': candidature.etablissement.nom,
                            'filiere_nom': candidature.filiere.nom,
                            'niveau_nom': candidature.niveau.nom,
                            'annee_academique_nom': candidature.annee_academique.nom,
                        },
                        'plan': {
                            'id': str(plan.id),
                            'montant_total': float(plan.montant_total),
                            'remise_paiement_unique': float(plan.remise_paiement_unique),
                            'frais_echelonnement': float(plan.frais_echelonnement),
                            'paiement_unique_possible': plan.paiement_unique_possible,
                            'paiement_echelonne_possible': plan.paiement_echelonne_possible,
                            'tranches': tranches
                        },
                        'montant_unique': float(plan.get_montant_avec_remise()),
                        'montant_echelonne': float(plan.get_montant_avec_frais()),
                        'premiere_tranche': {
                            'id': str(premiere_tranche.id),
                            'montant': float(premiere_tranche.montant),
                            'nom': premiere_tranche.nom
                        } if premiere_tranche else None
                    })

                except PlanPaiement.DoesNotExist:
                    logger.warning(f"⚠️ Aucun plan de paiement pour candidature {candidature.numero_candidature}")
                    continue
                except Exception as e:
                    logger.error(f"❌ Erreur traitement plan: {str(e)}")
                    continue

            if not plans_disponibles:
                logger.warning(f"❌ Aucun plan de paiement configuré")
                return JsonResponse({
                    'success': False,
                    'message': 'Aucun plan de paiement configuré pour vos candidatures approuvées.',
                })

            logger.info(f"✅ {len(plans_disponibles)} plan(s) disponible(s)")

            return JsonResponse({
                'success': True,
                'plans_disponibles': plans_disponibles
            })

        return redirect('dashboard:student')

    elif request.method == 'POST':
        # Traiter le choix de paiement
        candidature_id = request.POST.get('candidature_id')
        type_paiement = request.POST.get('type_paiement')

        logger.info(f"Initiation inscription: candidature_id={candidature_id}, type={type_paiement}")

        if not candidature_id or not type_paiement:
            messages.error(request, "Veuillez sélectionner une option de paiement.")
            return redirect('dashboard:student')

        if type_paiement not in ['UNIQUE', 'ECHELONNE']:
            messages.error(request, "Type de paiement invalide.")
            return redirect('dashboard:student')

        try:
            with transaction.atomic():
                # Récupérer la candidature
                candidature = get_object_or_404(
                    Candidature.objects.select_related(
                        'filiere', 'niveau', 'annee_academique', 'etablissement'
                    ),
                    id=candidature_id,
                    email=request.user.email,
                    statut='APPROUVEE'
                )

                # Vérifier qu'il n'existe pas déjà une inscription pour cette candidature
                if hasattr(candidature, 'inscription'):
                    messages.warning(request, "Une inscription existe déjà pour cette candidature.")
                    return redirect('dashboard:student')

                # Récupérer le plan de paiement
                plan = get_object_or_404(
                    PlanPaiement,
                    filiere=candidature.filiere,
                    niveau=candidature.niveau,
                    annee_academique=candidature.annee_academique,
                    est_actif=True
                )

                # Vérifier que le type de paiement est autorisé
                if type_paiement == 'UNIQUE' and not plan.paiement_unique_possible:
                    messages.error(request, "Le paiement unique n'est pas autorisé pour cette formation.")
                    return redirect('dashboard:student')

                if type_paiement == 'ECHELONNE' and not plan.paiement_echelonne_possible:
                    messages.error(request, "Le paiement échelonné n'est pas autorisé pour cette formation.")
                    return redirect('dashboard:student')

                # Créer l'inscription avec statut PENDING
                inscription = Inscription.objects.create(
                    candidature=candidature,
                    apprenant=request.user,
                    frais_scolarite=plan.montant_total,
                    date_debut=timezone.now().date(),
                    date_fin_prevue=candidature.annee_academique.date_fin,
                    statut='PENDING',  # En attente du paiement
                    cree_par=request.user
                )

                logger.info(f"Inscription créée: {inscription.numero_inscription} (statut: PENDING)")

                # Calculer le montant selon le type
                if type_paiement == 'UNIQUE':
                    montant_du = plan.get_montant_avec_remise()
                else:
                    montant_du = plan.get_montant_avec_frais()

                # Créer le lien inscription-paiement
                inscription_paiement = InscriptionPaiement.objects.create(
                    inscription=inscription,
                    plan=plan,
                    type_paiement=type_paiement,
                    montant_total_du=montant_du,
                    statut='EN_ATTENTE'
                )

                logger.info(f"InscriptionPaiement créé: {inscription_paiement.id}")

                # Déterminer le montant à payer maintenant
                if type_paiement == 'UNIQUE':
                    montant_a_payer = montant_du
                    tranche_a_payer = None
                    description = f"Paiement unique - Inscription {candidature.filiere.nom} {candidature.niveau.nom}"
                else:
                    # Première tranche
                    tranche_a_payer = plan.tranches.filter(
                        est_premiere_tranche=True
                    ).first()

                    if not tranche_a_payer:
                        tranche_a_payer = plan.tranches.order_by('numero').first()

                    if not tranche_a_payer:
                        raise ValidationError("Aucune tranche de paiement configurée pour ce plan.")

                    montant_a_payer = tranche_a_payer.get_montant_avec_penalite()
                    description = f"Tranche 1 - Inscription {candidature.filiere.nom} {candidature.niveau.nom}"

                # Créer le paiement
                paiement = Paiement.objects.create(
                    inscription_paiement=inscription_paiement,
                    tranche=tranche_a_payer,
                    montant=montant_a_payer,
                    methode_paiement='LIGDICASH',
                    statut='EN_ATTENTE',
                    description=description,
                    date_echeance=tranche_a_payer.date_limite if tranche_a_payer else None
                )

                logger.info(f"Paiement créé: {paiement.numero_transaction}")

                # Créer l'historique
                HistoriquePaiement.objects.create(
                    paiement=paiement,
                    type_action='CREATION',
                    nouveau_statut='EN_ATTENTE',
                    details=f"Paiement créé pour inscription - Type: {type_paiement}",
                    utilisateur=request.user,
                    adresse_ip=request.META.get('REMOTE_ADDR')
                )

                # Rediriger vers le paiement LigdiCash
                messages.info(request, "Vous allez être redirigé vers la plateforme de paiement.")
                return redirect('payments:payer_ligdicash', paiement_id=paiement.id)

        except Candidature.DoesNotExist:
            logger.error(f"Candidature non trouvée: {candidature_id}")
            messages.error(request, "Candidature non trouvée.")
            return redirect('dashboard:student')
        except PlanPaiement.DoesNotExist:
            logger.error(f"Plan de paiement non trouvé pour candidature {candidature_id}")
            messages.error(request, "Aucun plan de paiement configuré pour cette formation.")
            return redirect('dashboard:student')
        except Exception as e:
            logger.error(f"Erreur création inscription/paiement: {str(e)}", exc_info=True)
            messages.error(request, f"Erreur lors de la création du paiement: {str(e)}")
            return redirect('dashboard:student')

@login_required
def admin_initiate_payment(request, student_id):
    """Initier un paiement pour un étudiant (par ADMIN)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        return JsonResponse({'error': 'Non autorisé'}, status=403)

    student = get_object_or_404(Utilisateur, id=student_id, role='APPRENANT')

    # Récupérer l'inscription active
    inscription = Inscription.objects.filter(
        apprenant=student,
        statut='ACTIVE'
    ).select_related('plan_paiement_inscription').first()

    if not inscription:
        return JsonResponse({
            'success': False,
            'message': 'Aucune inscription active'
        })

    inscription_paiement = inscription.plan_paiement_inscription

    if inscription_paiement.solde_restant <= 0:
        return JsonResponse({
            'success': False,
            'message': 'Tous les paiements sont effectués'
        })

    # Prochaine tranche
    prochaine_tranche = inscription_paiement.get_prochaine_tranche_due()

    if not prochaine_tranche:
        return JsonResponse({
            'success': False,
            'message': 'Aucune tranche de paiement trouvée'
        })

    # Vérifier s'il n'y a pas déjà un paiement en cours
    paiement_en_cours = Paiement.objects.filter(
        inscription_paiement=inscription_paiement,
        tranche=prochaine_tranche,
        statut__in=['EN_ATTENTE', 'EN_COURS']
    ).first()

    if paiement_en_cours:
        return JsonResponse({
            'success': False,
            'message': 'Un paiement est déjà en cours',
            'paiement_id': str(paiement_en_cours.id)
        })

    # Créer le paiement
    with transaction.atomic():
        paiement = Paiement.objects.create(
            inscription_paiement=inscription_paiement,
            tranche=prochaine_tranche,
            montant=prochaine_tranche.get_montant_avec_penalite(),
            methode_paiement='LIGDICASH',
            statut='EN_ATTENTE',
            description=f"Tranche {prochaine_tranche.numero} - {prochaine_tranche.nom}",
            date_echeance=prochaine_tranche.date_limite,
            traite_par=request.user
        )

        HistoriquePaiement.objects.create(
            paiement=paiement,
            type_action='CREATION',
            nouveau_statut='EN_ATTENTE',
            details=f"Paiement créé par {request.user.get_full_name()}",
            utilisateur=request.user,
            adresse_ip=request.META.get('REMOTE_ADDR')
        )

    return JsonResponse({
        'success': True,
        'message': 'Paiement créé avec succès',
        'paiement_id': str(paiement.id),
        'redirect_url': f'/payments/ligdicash/payer/{paiement.id}/'
    })

@login_required
def student_payments_modal(request, student_id):
    """Modal des paiements d'un étudiant"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        return JsonResponse({'error': 'Non autorisé'}, status=403)

    student = get_object_or_404(Utilisateur, id=student_id, role='APPRENANT')

    # Récupérer l'inscription active
    inscription = Inscription.objects.filter(
        apprenant=student,
        statut='ACTIVE'
    ).select_related(
        'plan_paiement_inscription__plan'
    ).first()

    if not inscription:
        return JsonResponse({
            'success': False,
            'message': 'Aucune inscription active trouvée'
        })

    inscription_paiement = inscription.plan_paiement_inscription

    # Paiements existants
    paiements = Paiement.objects.filter(
        inscription_paiement=inscription_paiement
    ).select_related('tranche').order_by('-date_paiement')

    # Prochaine tranche due
    prochaine_tranche = inscription_paiement.get_prochaine_tranche_due()

    data = {
        'etudiant': {
            'id': str(student.id),
            'nom_complet': student.get_full_name(),
            'matricule': student.matricule,
        },
        'inscription': {
            'numero': inscription.numero_inscription,
            'frais_total': float(inscription.frais_scolarite),
            'total_paye': float(inscription.total_paye),
            'solde': float(inscription.solde),
            'statut_paiement': inscription.get_statut_paiement_display(),
            'type_paiement': inscription_paiement.get_type_paiement_display(),
        },
        'paiements': [
            {
                'id': str(p.id),
                'numero': p.numero_transaction,
                'montant': float(p.montant),
                'date': p.date_paiement.strftime('%d/%m/%Y %H:%M'),
                'statut': p.get_statut_display(),
                'methode': p.get_methode_paiement_display(),
                'tranche': p.tranche.nom if p.tranche else 'Unique',
            }
            for p in paiements
        ],
        'prochaine_tranche': {
            'id': str(prochaine_tranche.id),
            'nom': prochaine_tranche.nom,
            'montant': float(prochaine_tranche.montant),
            'date_limite': prochaine_tranche.date_limite.strftime('%d/%m/%Y') if prochaine_tranche.date_limite else '',
        } if prochaine_tranche else None,
        'peut_payer': inscription.solde > 0,
    }

    return JsonResponse({'success': True, 'data': data})


@login_required
def selection_paiement(request):
    """
    Vue pour sélectionner le mode de paiement
    """
    user = request.user

    # Récupérer les candidatures approuvées
    candidatures_approuvees = Candidature.objects.filter(
        email=user.email,
        statut='APPROUVEE'
    ).exclude(inscription__isnull=False)

    if not candidatures_approuvees.exists():
        messages.error(request, "Aucune candidature approuvée disponible.")
        return redirect('dashboard:student')

    # Récupérer les plans de paiement
    plans_disponibles = []
    for candidature in candidatures_approuvees:
        try:
            plan = PlanPaiement.objects.get(
                filiere=candidature.filiere,
                niveau=candidature.niveau,
                annee_academique=candidature.annee_academique,
                est_actif=True
            )

            # Récupérer les tranches
            tranches = plan.tranches.order_by('numero')

            premiere_tranche = plan.tranches.filter(
                est_premiere_tranche=True
            ).first() or plan.tranches.order_by('numero').first()

            plans_disponibles.append({
                'candidature': candidature,
                'plan': plan,
                'tranches': tranches,
                'montant_unique': plan.get_montant_avec_remise(),
                'montant_echelonne': plan.get_montant_avec_frais(),
                'premiere_tranche': premiere_tranche
            })

        except PlanPaiement.DoesNotExist:
            continue

    if not plans_disponibles:
        messages.error(request, "Aucun plan de paiement configuré pour vos formations.")
        return redirect('dashboard:student')

    context = {
        'plans_disponibles': plans_disponibles
    }

    return render(request, 'payments/selection_paiement.html', context)

@login_required
def payer_ligdicash(request, paiement_id):
    """
    Initie le paiement via LigdiCash
    """
    paiement = get_object_or_404(
        Paiement.objects.select_related(
            'inscription_paiement__inscription__apprenant',
            'traite_par'
        ),
        id=paiement_id
    )

    # Vérifier les permissions
    apprenant = paiement.inscription_paiement.inscription.apprenant

    if request.user.role == 'APPRENANT':
        if apprenant != request.user:
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:student')
    elif request.user.role in ['ADMIN', 'CHEF_DEPARTEMENT']:
        # ... vérifications admin
        pass
    else:
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    if paiement.statut not in ['EN_ATTENTE', 'ECHEC']:
        messages.warning(request, "Ce paiement ne peut plus être traité")
        return redirect('dashboard:redirect')

    try:
        # Utiliser les URLs PUBLIQUES car LigdiCash redirige sans auth
        urls = creer_urls_retour(request, str(paiement.id), use_public_urls=True)

        # Nom et email pour LigdiCash
        nom_client = apprenant.get_full_name()
        email_client = apprenant.email

        # Appeler LigdiCash
        success, response = ligdicash_service.creer_paiement_redirection(
            paiement_id=str(paiement.id),
            montant=paiement.montant,
            description=paiement.description,
            email_client=email_client,
            nom_client=nom_client,
            url_retour_succes=urls['success'],
            url_retour_echec=urls['error'],
            url_callback=urls['callback']
        )

        if success:
            # Mettre à jour le paiement
            paiement.statut = 'EN_COURS'
            paiement.reference_externe = response.get('transaction_id')
            paiement.donnees_transaction = response.get('raw_response', {})
            paiement.save()

            # Historique
            HistoriquePaiement.objects.create(
                paiement=paiement,
                type_action='MODIFICATION',
                ancien_statut='EN_ATTENTE',
                nouveau_statut='EN_COURS',
                details=f"Redirection LigdiCash créée par {request.user.get_full_name()}",
                utilisateur=request.user,
                adresse_ip=request.META.get('REMOTE_ADDR'),
                donnees_supplementaires=response
            )

            # Rediriger vers LigdiCash
            payment_url = response.get('payment_url')
            if payment_url:
                return redirect(payment_url)
            else:
                messages.error(request, "URL de paiement non reçue")
                return redirect('dashboard:redirect')
        else:
            # Échec
            error_msg = response.get('error', 'Erreur inconnue')
            messages.error(request, f"Impossible d'initier le paiement: {error_msg}")
            paiement.echec(f"Échec création LigdiCash: {error_msg}")
            return redirect('dashboard:redirect')

    except Exception as e:
        logger.error(f"Erreur paiement LigdiCash: {str(e)}", exc_info=True)
        messages.error(request, "Une erreur est survenue")
        paiement.echec(f"Erreur technique: {str(e)}")
        return redirect('dashboard:redirect')


@login_required
def callback_success(request, paiement_id):
    """
    Callback de succès depuis LigdiCash
    Peut contenir des paramètres GET (token, etc.)
    """
    try:
        # Extraire le token du paramètre GET si présent
        token = request.GET.get('token')
        if token:
            logger.info(f"📎 Token reçu dans callback: {token[:20]}...")

        paiement = get_object_or_404(
            Paiement.objects.select_related(
                'inscription_paiement__inscription__apprenant'
            ),
            id=paiement_id
        )

        # Vérifier que l'utilisateur est bien le propriétaire du paiement
        if paiement.inscription_paiement.inscription.apprenant != request.user:
            messages.error(request, "Accès non autorisé.")
            return redirect('dashboard:student')

        logger.info(f"✅ Callback success pour paiement {paiement.numero_transaction}")
        logger.info(f"   Statut actuel: {paiement.statut}")

        inscription = paiement.inscription_paiement.inscription

        # Si le paiement est déjà confirmé
        if paiement.statut == 'CONFIRME':
            logger.info(f"✅ Paiement déjà confirmé")

            if inscription.statut == 'ACTIVE':
                messages.success(request, "🎉 Votre inscription est active !")
            else:
                messages.success(request, "✅ Paiement confirmé !")

            return render(request, 'payments/success.html', {
                'paiement': paiement,
                'inscription': inscription,
                'inscription_active': inscription.statut == 'ACTIVE'
            })

        # Si paiement en attente, vérifier avec LigdiCash
        if paiement.statut in ['EN_COURS', 'EN_ATTENTE'] and paiement.reference_externe:
            logger.info(f"🔍 Vérification statut LigdiCash")

            try:
                success, status_data = ligdicash_service.verifier_statut_paiement(
                    paiement.reference_externe
                )

                if success and status_data.get('status') == 'CONFIRME':
                    logger.info(f"✅ Paiement confirmé")

                    with transaction.atomic():
                        # Confirmer le paiement
                        frais = status_data.get('fees', 0)
                        paiement.confirmer(
                            reference_externe=paiement.reference_externe,
                            frais=frais
                        )

                        # Activer l'inscription si nécessaire
                        if inscription.statut == 'PENDING':
                            if paiement.inscription_paiement.est_inscrit_autorise():
                                inscription.statut = 'ACTIVE'
                                inscription.save()

                                logger.info(f"✅ Inscription activée")

                                # Envoyer email
                                try:
                                    from apps.enrollment.managers import EmailCandidatureManager
                                    EmailCandidatureManager.send_inscription_confirmee(inscription)
                                except Exception as e:
                                    logger.error(f"❌ Erreur envoi email: {str(e)}")

                                messages.success(
                                    request,
                                    "🎉 Félicitations ! Votre paiement est confirmé et votre inscription est maintenant active."
                                )
                            else:
                                messages.success(
                                    request,
                                    "Paiement confirmé ! Complétez les autres tranches pour finaliser."
                                )
                        else:
                            messages.success(request, "Paiement confirmé avec succès !")

                    return render(request, 'payments/success.html', {
                        'paiement': paiement,
                        'inscription': inscription,
                        'inscription_active': inscription.statut == 'ACTIVE'
                    })

                else:
                    # Paiement pas encore confirmé
                    messages.info(
                        request,
                        "Votre paiement est en cours de traitement..."
                    )
                    return render(request, 'payments/pending.html', {
                        'paiement': paiement,
                        'inscription': inscription
                    })

            except Exception as e:
                logger.error(f"❌ Erreur vérification: {str(e)}")
                messages.info(
                    request,
                    "Paiement en cours de traitement..."
                )
                return render(request, 'payments/pending.html', {
                    'paiement': paiement,
                    'inscription': inscription
                })

        # Autres cas
        messages.info(
            request,
            "Votre paiement est en cours de traitement..."
        )
        return render(request, 'payments/pending.html', {
            'paiement': paiement,
            'inscription': inscription
        })

    except Exception as e:
        logger.error(f"❌ Erreur callback: {str(e)}", exc_info=True)
        messages.error(request, "Une erreur est survenue.")
        return redirect('dashboard:student')

@login_required
def callback_error(request, paiement_id):
    """
    Callback d'erreur depuis LigdiCash
    """
    try:
        paiement = get_object_or_404(
            Paiement,
            id=paiement_id,
            inscription_paiement__inscription__apprenant=request.user
        )

        # Marquer le paiement comme échoué
        motif = request.GET.get('error', 'Paiement annulé ou échoué')
        paiement.echec(motif)

        messages.error(request, f"Paiement échoué: {motif}")

        return render(request, 'payments/error.html', {
            'paiement': paiement,
            'error_message': motif
        })

    except Exception as e:
        logger.error(f"Erreur callback error: {str(e)}")
        messages.error(request, "Une erreur est survenue.")
        return redirect('dashboard:student')

@csrf_exempt
@require_http_methods(["POST"])
def webhook_ligdicash(request):
    """
    🔔 WEBHOOK LIGDICASH
    Reçoit les notifications automatiques de LigdiCash
    MET À JOUR LE STATUT DU PAIEMENT ET ACTIVE L'INSCRIPTION SI CONFIRMÉ
    """
    logger.info("=" * 60)
    logger.info("🔔 WEBHOOK LIGDICASH - STATUT PAIEMENT")
    logger.info("=" * 60)

    try:
        # Parser les données
        content_type = request.content_type or ''

        if 'application/json' in content_type:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                body_str = request.body.decode('utf-8')
                data = json.loads(body_str)
        else:
            data = request.POST.dict()

        logger.info(f"📦 Données reçues: {json.dumps(data, indent=2)}")

        # Extraire l'ID du paiement
        paiement_id = (
                data.get('paiement_id') or
                data.get('external_id') or
                data.get('transaction_id') or
                (data.get('custom_data', {}).get('paiement_id')
                 if isinstance(data.get('custom_data'), dict) else None)
        )

        logger.info(f"🆔 Paiement ID extrait: {paiement_id}")

        if not paiement_id:
            logger.error("❌ Paiement ID non trouvé")
            return HttpResponse("Payment ID missing", status=400)

        try:
            paiement = Paiement.objects.select_related(
                'inscription_paiement__inscription__candidature',
                'inscription_paiement__inscription__apprenant'
            ).get(id=paiement_id)

            inscription_paiement = paiement.inscription_paiement
            inscription = inscription_paiement.inscription

            logger.info(f"💾 Paiement trouvé: {paiement.numero_transaction}")
            logger.info(f"📊 Statut actuel: {paiement.statut}")
            logger.info(f"👤 Apprenant: {inscription.apprenant.email if inscription.apprenant else 'Non assigné'}")

            old_status = paiement.statut
            status = str(data.get('status', '')).lower()
            response_code = data.get('response_code', '')

            logger.info(f"📊 Statut LigdiCash: {status} (code: {response_code})")

            with transaction.atomic():
                # SI PAIEMENT CONFIRMÉ
                if status in ['completed', 'success', 'successful', 'paid'] or response_code == '00':
                    logger.info("✅ PAIEMENT CONFIRMÉ")

                    # 1. Mettre à jour le paiement
                    paiement.statut = 'CONFIRME'
                    paiement.date_confirmation = timezone.now()
                    paiement.reference_externe = data.get('transaction_id') or paiement.reference_externe
                    paiement.frais_transaction = Decimal(str(data.get('fees', 0)))
                    paiement.donnees_transaction = data
                    paiement.save()

                    logger.info(f"✅ Statut paiement mis à jour: {old_status} → CONFIRME")

                    # 2. Mettre à jour l'inscription paiement
                    inscription_paiement.mettre_a_jour_statut()

                    # 3. ACTIVER L'INSCRIPTION si c'est le premier paiement
                    if inscription.statut == 'PENDING':
                        if paiement.inscription_paiement.est_inscrit_autorise():
                            inscription.statut = 'ACTIVE'
                            inscription.save()
                            logger.info(f"✅ Inscription activée: {inscription.numero_inscription}")

                            # Envoyer email de confirmation d'inscription
                            try:
                                EmailCandidatureManager.send_inscription_confirmee(inscription)
                                logger.info(f"📧 Email confirmation envoyé à {inscription.apprenant.email}")
                            except Exception as e:
                                logger.error(f"❌ Erreur envoi email: {str(e)}")

                    # 4. Créer l'historique
                    HistoriquePaiement.objects.create(
                        paiement=paiement,
                        type_action='CONFIRMATION',
                        ancien_statut=old_status,
                        nouveau_statut='CONFIRME',
                        details=f"Paiement confirmé via webhook LigdiCash",
                        donnees_supplementaires=data
                    )

                # SI PAIEMENT ÉCHOUÉ
                elif status in ['failed', 'error', 'rejected']:
                    paiement.statut = 'ECHEC'
                    paiement.donnees_transaction = data
                    paiement.save()
                    logger.warning(f"❌ Statut mis à jour: {old_status} → ECHEC")

                # SI PAIEMENT ANNULÉ
                elif status in ['cancelled', 'canceled']:
                    paiement.statut = 'ANNULE'
                    paiement.donnees_transaction = data
                    paiement.save()
                    logger.warning(f"🚫 Statut mis à jour: {old_status} → ANNULE")

                # AUTRES STATUTS
                else:
                    paiement.donnees_transaction = data
                    paiement.save()
                    logger.info(f"📊 Statut non traité: {status}")

        except Paiement.DoesNotExist:
            logger.error(f"❌ Paiement non trouvé: {paiement_id}")
            return HttpResponse("Payment not found", status=404)

        logger.info("✅ Webhook traité avec succès")
        return HttpResponse("OK")

    except Exception as e:
        logger.error(f"❌ Erreur webhook: {str(e)}", exc_info=True)
        return HttpResponse(f"Error: {str(e)}", status=500)

@login_required
def payer_prochaine_tranche(request):
    """
    Initie le paiement de la prochaine tranche due
    """
    if request.method != 'POST':
        messages.error(request, "Méthode non autorisée.")
        return redirect('dashboard:student_paiements')

    try:
        # Récupérer l'inscription active
        inscription = get_object_or_404(
            Inscription.objects.select_related('plan_paiement_inscription__plan'),
            apprenant=request.user,
            statut='ACTIVE'
        )

        inscription_paiement = inscription.plan_paiement_inscription

        # Vérifier qu'il y a un solde
        if inscription_paiement.solde_restant <= 0:
            messages.info(request, "Tous les paiements sont déjà effectués.")
            return redirect('dashboard:student_paiements')

        # Récupérer la prochaine tranche
        prochaine_tranche = inscription_paiement.get_prochaine_tranche_due()

        if not prochaine_tranche:
            messages.error(request, "Aucune tranche de paiement trouvée.")
            return redirect('dashboard:student_paiements')

        # Vérifier qu'il n'y a pas déjà un paiement en cours pour cette tranche
        paiement_en_cours = Paiement.objects.filter(
            inscription_paiement=inscription_paiement,
            tranche=prochaine_tranche,
            statut__in=['EN_ATTENTE', 'EN_COURS']
        ).first()

        if paiement_en_cours:
            messages.info(request, "Un paiement est déjà en cours pour cette tranche.")
            return redirect('payments:payer_ligdicash', paiement_id=paiement_en_cours.id)

        # Créer le nouveau paiement
        with transaction.atomic():
            paiement = Paiement.objects.create(
                inscription_paiement=inscription_paiement,
                tranche=prochaine_tranche,
                montant=prochaine_tranche.get_montant_avec_penalite(),
                methode_paiement='LIGDICASH',
                statut='EN_ATTENTE',
                description=f"Tranche {prochaine_tranche.numero} - {prochaine_tranche.nom}",
                date_echeance=prochaine_tranche.date_limite
            )

            # Historique
            HistoriquePaiement.objects.create(
                paiement=paiement,
                type_action='CREATION',
                nouveau_statut='EN_ATTENTE',
                details=f"Paiement tranche {prochaine_tranche.numero} créé",
                utilisateur=request.user,
                adresse_ip=request.META.get('REMOTE_ADDR')
            )

        # Rediriger vers LigdiCash
        return redirect('payments:payer_ligdicash', paiement_id=paiement.id)

    except Exception as e:
        logger.error(f"Erreur création paiement tranche: {str(e)}")
        messages.error(request, "Erreur lors de la création du paiement.")
        return redirect('dashboard:student_paiements')

@login_required
def detail_paiement(request, paiement_id):
    """
    Détail d'un paiement
    """
    paiement = get_object_or_404(
        Paiement.objects.select_related(
            'inscription_paiement__inscription__apprenant',
            'tranche', 'traite_par'
        ).prefetch_related('historique__utilisateur'),
        id=paiement_id,
        inscription_paiement__inscription__apprenant=request.user
    )

    context = {
        'paiement': paiement,
        'historique': paiement.historique.order_by('-created_at')
    }

    return render(request, 'payments/detail_paiement.html', context)


def callback_success_public(request, paiement_id):
    """
    Callback de succès PUBLIC - Pour les cas où l'utilisateur n'est pas connecté
    """
    try:
        token = request.GET.get('token')
        if not token:
            messages.error(request, "Token manquant.")
            return redirect('accounts:login')

        paiement = get_object_or_404(Paiement, id=paiement_id)
        inscription = paiement.inscription_paiement.inscription

        # Ici vous pourriez vérifier le token si nécessaire
        # Pour l'instant, on affiche juste une page d'information

        context = {
            'paiement': paiement,
            'inscription': inscription,
            'token': token,
            'est_connecte': request.user.is_authenticated
        }

        if paiement.statut == 'CONFIRME':
            return render(request, 'payments/public/success.html', context)
        else:
            return render(request, 'payments/public/pending.html', context)

    except Exception as e:
        logger.error(f"Erreur callback public: {str(e)}")
        messages.error(request, "Une erreur est survenue.")
        return redirect('accounts:login')


def callback_error_public(request, paiement_id):
    """
    Callback d'erreur PUBLIC
    """
    try:
        token = request.GET.get('token')
        paiement = get_object_or_404(Paiement, id=paiement_id)

        return render(request, 'payments/public/error.html', {
            'paiement': paiement,
            'token': token,
            'error_message': request.GET.get('error', 'Paiement échoué')
        })

    except Exception as e:
        logger.error(f"Erreur callback error public: {str(e)}")
        return redirect('accounts:login')