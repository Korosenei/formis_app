# apps/payments/views.py

import logging
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse, reverse_lazy
from django.core.exceptions import ValidationError
from django.conf import settings

from .models import (
    PlanPaiement, TranchePaiement, InscriptionPaiement,
    Paiement, HistoriquePaiement
)
from .services.ligdicash import ligdicash_service, creer_urls_retour
from apps.enrollment.models import Inscription
from apps.academic.models import Filiere, Niveau

logger = logging.getLogger(__name__)


@login_required
def initier_inscription_paiement(request):
    """
    Vue pour initier le paiement d'inscription
    Accessible depuis le modal d'inscription obligatoire
    """
    if request.method == 'GET':
        # Afficher les options de paiement
        user = request.user

        # Vérifier si l'utilisateur a déjà une inscription active
        inscription_active = Inscription.objects.filter(
            etudiant=user,
            statut='ACTIVE'
        ).first()

        if inscription_active:
            messages.info(request, "Vous êtes déjà inscrit.")
            return redirect('dashboard:student')

        # Récupérer les candidatures approuvées de l'utilisateur
        candidatures_approuvees = user.candidatures.filter(
            statut='APPROUVEE'
        ).select_related('filiere', 'niveau', 'annee_academique')

        if not candidatures_approuvees.exists():
            messages.error(request, "Aucune candidature approuvée trouvée. Veuillez d'abord soumettre une candidature.")
            return redirect('enrollment:candidature_create')

        # Récupérer les plans de paiement disponibles
        plans_disponibles = []
        for candidature in candidatures_approuvees:
            try:
                plan = PlanPaiement.objects.get(
                    filiere=candidature.filiere,
                    niveau=candidature.niveau,
                    annee_academique=candidature.annee_academique,
                    est_actif=True
                )
                plans_disponibles.append({
                    'candidature': candidature,
                    'plan': plan,
                    'montant_unique': plan.get_montant_avec_remise(),
                    'montant_echelonne': plan.get_montant_avec_frais(),
                    'premiere_tranche': plan.tranches.filter(est_premiere_tranche=True).first()
                })
            except PlanPaiement.DoesNotExist:
                logger.warning(f"Aucun plan de paiement trouvé pour {candidature}")

        if not plans_disponibles:
            messages.error(request, "Aucun plan de paiement configuré pour vos formations.")
            return redirect('dashboard:student')

        context = {
            'plans_disponibles': plans_disponibles,
            'user': user
        }

        return render(request, 'payments/initier_inscription.html', context)

    elif request.method == 'POST':
        # Traiter le choix de paiement
        candidature_id = request.POST.get('candidature_id')
        type_paiement = request.POST.get('type_paiement')  # 'UNIQUE' ou 'ECHELONNE'

        if not candidature_id or not type_paiement:
            messages.error(request, "Veuillez sélectionner une option de paiement.")
            return redirect('payments:initier_inscription')

        try:
            with transaction.atomic():
                # Récupérer la candidature
                candidature = get_object_or_404(
                    request.user.candidatures.filter(statut='APPROUVEE'),
                    id=candidature_id
                )

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
                    return redirect('payments:initier_inscription')

                if type_paiement == 'ECHELONNE' and not plan.paiement_echelonne_possible:
                    messages.error(request, "Le paiement échelonné n'est pas autorisé pour cette formation.")
                    return redirect('payments:initier_inscription')

                # Créer l'inscription d'abord
                inscription = Inscription.objects.create(
                    candidature=candidature,
                    etudiant=request.user,
                    frais_scolarite=plan.montant_total,
                    date_debut=timezone.now().date(),
                    statut='PENDING',  # En attente du paiement
                    cree_par=request.user
                )

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
                    montant_total_du=montant_du
                )

                # Déterminer le montant à payer maintenant
                if type_paiement == 'UNIQUE':
                    montant_a_payer = montant_du
                    tranche_a_payer = None
                    description = f"Paiement unique - Inscription {candidature.filiere.nom}"
                else:
                    # Première tranche
                    tranche_a_payer = plan.tranches.filter(est_premiere_tranche=True).first()
                    if not tranche_a_payer:
                        tranche_a_payer = plan.tranches.order_by('numero').first()

                    if not tranche_a_payer:
                        raise ValidationError("Aucune tranche de paiement configurée.")

                    montant_a_payer = tranche_a_payer.get_montant_avec_penalite()
                    description = f"Première tranche - Inscription {candidature.filiere.nom}"

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
                return redirect('payments:payer_ligdicash', paiement_id=paiement.id)

        except Exception as e:
            logger.error(f"Erreur création paiement inscription: {str(e)}")
            messages.error(request, f"Erreur lors de la création du paiement: {str(e)}")
            return redirect('payments:initier_inscription')


@login_required
def payer_ligdicash(request, paiement_id):
    """
    Initie le paiement via LigdiCash
    """
    paiement = get_object_or_404(
        Paiement.objects.select_related(
            'inscription_paiement__inscription__etudiant'
        ),
        id=paiement_id,
        inscription_paiement__inscription__etudiant=request.user
    )

    if paiement.statut != 'EN_ATTENTE':
        messages.error(request, "Ce paiement ne peut plus être traité.")
        return redirect('dashboard:student')

    try:
        # Créer les URLs de retour
        urls = creer_urls_retour(request, str(paiement.id))

        # Appeler LigdiCash
        success, response = ligdicash_service.creer_paiement_redirection(
            paiement_id=str(paiement.id),
            montant=paiement.montant,
            description=paiement.description,
            email_client=request.user.email,
            nom_client=request.user.get_full_name(),
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
                details="Redirection vers LigdiCash créée",
                utilisateur=request.user,
                adresse_ip=request.META.get('REMOTE_ADDR'),
                donnees_supplementaires=response
            )

            # Rediriger vers LigdiCash
            payment_url = response.get('payment_url')
            if payment_url:
                return redirect(payment_url)
            else:
                messages.error(request, "URL de paiement non reçue.")
                return redirect('dashboard:student')
        else:
            # Échec de création
            error_msg = response.get('error', 'Erreur inconnue')
            messages.error(request, f"Impossible d'initier le paiement: {error_msg}")

            # Marquer le paiement en échec
            paiement.echec(f"Échec création LigdiCash: {error_msg}")

            return redirect('dashboard:student')

    except Exception as e:
        logger.error(f"Erreur lors de l'initiation du paiement LigdiCash: {str(e)}")
        messages.error(request, "Une erreur est survenue lors de l'initiation du paiement.")
        paiement.echec(f"Erreur technique: {str(e)}")
        return redirect('dashboard:student')


@login_required
def callback_success(request, paiement_id):
    """
    Callback de succès depuis LigdiCash
    """
    try:
        paiement = get_object_or_404(
            Paiement.objects.select_related(
                'inscription_paiement__inscription'
            ),
            id=paiement_id,
            inscription_paiement__inscription__etudiant=request.user
        )

        # Vérifier le statut auprès de LigdiCash
        if paiement.reference_externe:
            success, status_data = ligdicash_service.verifier_statut_paiement(
                paiement.reference_externe
            )

            if success and status_data.get('status') == 'CONFIRME':
                # Confirmer le paiement
                frais = status_data.get('fees', 0)
                paiement.confirmer(
                    reference_externe=paiement.reference_externe,
                    frais=frais
                )

                # Activer l'inscription si c'est le premier paiement suffisant
                inscription = paiement.inscription_paiement.inscription
                if inscription.statut == 'PENDING':
                    if paiement.inscription_paiement.est_inscrit_autorise():
                        inscription.statut = 'ACTIVE'
                        inscription.save()

                        messages.success(
                            request,
                            "Paiement confirmé ! Votre inscription est maintenant active."
                        )
                    else:
                        messages.success(
                            request,
                            "Paiement confirmé ! Vous devez compléter les autres tranches."
                        )
                else:
                    messages.success(request, "Paiement confirmé avec succès !")

                return render(request, 'payments/success.html', {
                    'paiement': paiement,
                    'inscription': inscription
                })

        # Si on arrive ici, le paiement n'est pas encore confirmé
        messages.info(request, "Paiement en cours de traitement. Vous recevrez une confirmation.")
        return redirect('dashboard:student')

    except Exception as e:
        logger.error(f"Erreur callback success: {str(e)}")
        messages.error(request, "Une erreur est survenue lors du traitement du paiement.")
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
            inscription_paiement__inscription__etudiant=request.user
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
    Webhook pour recevoir les notifications de LigdiCash
    """
    try:
        import json

        # Récupérer les données du webhook
        if request.content_type == 'application/json':
            webhook_data = json.loads(request.body)
        else:
            webhook_data = dict(request.POST)

        logger.info(f"Webhook LigdiCash reçu: {webhook_data}")

        # Traiter le callback
        success, processed_data = ligdicash_service.traiter_callback(webhook_data)

        if not success:
            logger.error(f"Erreur traitement webhook: {processed_data.get('error')}")
            return HttpResponse("Error processing webhook", status=400)

        paiement_id = processed_data.get('paiement_id')
        if not paiement_id:
            logger.error("Aucun paiement_id dans le webhook")
            return HttpResponse("Missing payment ID", status=400)

        # Récupérer le paiement
        try:
            paiement = Paiement.objects.select_related(
                'inscription_paiement__inscription'
            ).get(id=paiement_id)
        except Paiement.DoesNotExist:
            logger.error(f"Paiement non trouvé: {paiement_id}")
            return HttpResponse("Payment not found", status=404)

        # Mettre à jour selon le statut
        nouveau_statut = processed_data.get('status')
        ancien_statut = paiement.statut

        if nouveau_statut == 'CONFIRME' and ancien_statut != 'CONFIRME':
            # Confirmer le paiement
            frais = processed_data.get('fees', 0)
            paiement.confirmer(frais=frais)

            # Activer l'inscription si nécessaire
            inscription = paiement.inscription_paiement.inscription
            if inscription.statut == 'PENDING':
                if paiement.inscription_paiement.est_inscrit_autorise():
                    inscription.statut = 'ACTIVE'
                    inscription.save()

            logger.info(f"Paiement confirmé via webhook: {paiement_id}")

        elif nouveau_statut in ['ECHEC', 'ANNULE']:
            # Marquer comme échoué
            paiement.statut = nouveau_statut
            paiement.save()

            logger.info(f"Paiement {nouveau_statut.lower()} via webhook: {paiement_id}")

        # Créer l'historique
        HistoriquePaiement.objects.create(
            paiement=paiement,
            type_action='MODIFICATION',
            ancien_statut=ancien_statut,
            nouveau_statut=nouveau_statut,
            details=f"Mise à jour via webhook LigdiCash",
            donnees_supplementaires=processed_data,
            adresse_ip=request.META.get('REMOTE_ADDR')
        )

        return HttpResponse("OK", status=200)

    except Exception as e:
        logger.error(f"Erreur webhook LigdiCash: {str(e)}")
        return HttpResponse("Internal server error", status=500)



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
            etudiant=request.user,
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
            'inscription_paiement__inscription__etudiant',
            'tranche', 'traite_par'
        ).prefetch_related('historique__utilisateur'),
        id=paiement_id,
        inscription_paiement__inscription__etudiant=request.user
    )

    context = {
        'paiement': paiement,
        'historique': paiement.historique.order_by('-created_at')
    }

    return render(request, 'payments/detail_paiement.html', context)


@login_required
def verifier_statut_inscription(request):
    """
    API pour vérifier si l'utilisateur peut accéder au dashboard
    Utilisée par le modal d'inscription obligatoire
    """
    user = request.user

    # Vérifier si l'utilisateur a une inscription active
    inscription_active = Inscription.objects.filter(
        etudiant=user,
        statut='ACTIVE'
    ).first()

    if inscription_active:
        return JsonResponse({
            'peut_acceder': True,
            'message': 'Inscription active trouvée',
            'inscription_id': inscription_active.id
        })

    # Vérifier si l'utilisateur a des paiements en cours
    paiements_en_cours = Paiement.objects.filter(
        inscription_paiement__inscription__etudiant=user,
        statut__in=['EN_ATTENTE', 'EN_COURS']
    ).count()

    if paiements_en_cours > 0:
        return JsonResponse({
            'peut_acceder': False,
            'message': 'Paiement en cours de traitement',
            'paiements_en_cours': paiements_en_cours,
            'action_requise': 'attendre'
        })

    # Vérifier les candidatures approuvées
    candidatures_approuvees = user.candidatures.filter(
        statut='APPROUVEE'
    ).count()

    if candidatures_approuvees == 0:
        return JsonResponse({
            'peut_acceder': False,
            'message': 'Aucune candidature approuvée',
            'action_requise': 'candidater'
        })

    # L'utilisateur doit s'inscrire
    return JsonResponse({
        'peut_acceder': False,
        'message': 'Inscription requise',
        'candidatures_approuvees': candidatures_approuvees,
        'action_requise': 'inscrire'
    })

