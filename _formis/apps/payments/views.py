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
from apps.accounts.models import ProfilUtilisateur, ProfilApprenant

from apps.enrollment.managers import EmailCandidatureManager

from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string

logger = logging.getLogger(__name__)
User = get_user_model()


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

            # CORRECTION: Même logique de recherche que verifier_statut_inscription
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
def payer_ligdicash(request, paiement_id):
    """
    Initie le paiement via LigdiCash
    """
    paiement = get_object_or_404(
        Paiement.objects.select_related(
            'inscription_paiement__inscription__apprenant'
        ),
        id=paiement_id,
        inscription_paiement__inscription__apprenant=request.user
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
        logger.error(f"Erreur lors de l'initiation du paiement LigdiCash: {str(e)}", exc_info=True)
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
                'inscription_paiement__inscription__apprenant',
                'inscription_paiement__inscription__candidature'
            ),
            id=paiement_id,
            inscription_paiement__inscription__apprenant=request.user
        )

        logger.info(f"Callback success pour paiement {paiement.numero_transaction}")

        inscription = paiement.inscription_paiement.inscription

        # Vérifier le statut auprès de LigdiCash si référence externe existe
        if paiement.reference_externe and paiement.statut != 'CONFIRME':
            logger.info(f"Vérification statut LigdiCash pour {paiement.reference_externe}")

            success, status_data = ligdicash_service.verifier_statut_paiement(
                paiement.reference_externe
            )

            if success and status_data.get('status') == 'CONFIRME':
                logger.info(f"Paiement confirmé par LigdiCash: {paiement.reference_externe}")

                # Confirmer le paiement
                frais = status_data.get('fees', 0)
                paiement.confirmer(
                    reference_externe=paiement.reference_externe,
                    frais=frais
                )

                # Activer l'inscription si c'est le premier paiement
                if inscription.statut == 'PENDING':
                    if paiement.inscription_paiement.est_inscrit_autorise():
                        with transaction.atomic():
                            inscription.statut = 'ACTIVE'
                            inscription.save()

                            logger.info(f"Inscription activée: {inscription.numero_inscription}")

                            # Envoyer un email de confirmation
                            try:
                                EmailCandidatureManager.send_inscription_confirmee(inscription)
                            except Exception as e:
                                logger.error(f"Erreur envoi email confirmation: {str(e)}")

                        messages.success(
                            request,
                            "🎉 Félicitations ! Votre paiement est confirmé et votre inscription est maintenant active."
                        )
                    else:
                        messages.success(
                            request,
                            "Paiement confirmé ! Vous devez compléter les autres tranches pour finaliser l'inscription."
                        )
                else:
                    messages.success(request, "Paiement confirmé avec succès !")

                return render(request, 'payments/success.html', {
                    'paiement': paiement,
                    'inscription': inscription,
                    'inscription_active': inscription.statut == 'ACTIVE'
                })

        # Si le paiement est déjà confirmé
        if paiement.statut == 'CONFIRME':
            logger.info(f"Paiement déjà confirmé: {paiement.numero_transaction}")

            messages.success(request, "Votre paiement a été confirmé avec succès.")
            return render(request, 'payments/success.html', {
                'paiement': paiement,
                'inscription': inscription,
                'inscription_active': inscription.statut == 'ACTIVE'
            })

        # Si on arrive ici, le paiement n'est pas encore confirmé
        logger.warning(f"Paiement non confirmé: {paiement.numero_transaction} - Statut: {paiement.statut}")

        messages.info(
            request,
            "Votre paiement est en cours de traitement. Vous recevrez une confirmation par email."
        )
        return redirect('dashboard:student')

    except Exception as e:
        logger.error(f"Erreur callback success: {str(e)}", exc_info=True)
        messages.error(request, "Une erreur est survenue lors du traitement de votre paiement.")
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
    CRÉE LE COMPTE UTILISATEUR après paiement confirmé
    """
    logger.info("=" * 60)
    logger.info("🔔 RÉCEPTION WEBHOOK LIGDICASH")
    logger.info("=" * 60)

    try:
        # Vérifier le type de contenu
        content_type = request.content_type or ''
        logger.info(f"📋 Content-Type: {content_type}")

        # Gérer différents formats de données
        if 'application/json' in content_type:
            try:
                data = json.loads(request.body)
                logger.info("📦 Données reçues (JSON):")
            except json.JSONDecodeError:
                try:
                    body_str = request.body.decode('utf-8')
                    data = json.loads(body_str)
                    logger.info("📦 Données reçues (JSON string):")
                except:
                    data = request.POST.dict()
                    logger.info("📦 Données reçues (FORM):")
        else:
            data = request.POST.dict()
            logger.info("📦 Données reçues (FORM):")

        logger.info(json.dumps(data, indent=2, ensure_ascii=False))

        # Extraire l'ID du paiement
        paiement_id = (
                data.get('paiement_id') or
                data.get('external_id') or
                (data.get('custom_data', {}).get('paiement_id') if isinstance(data.get('custom_data'), dict) else None)
        )

        logger.info(f"🆔 Paiement ID extrait: {paiement_id}")

        if not paiement_id:
            logger.error("❌ Paiement ID non trouvé dans les données")
            return HttpResponse("Payment ID missing", status=400)

        try:
            paiement = Paiement.objects.select_related(
                'inscription_paiement__inscription__candidature'
            ).get(id=paiement_id)

            inscription_paiement = paiement.inscription_paiement
            inscription = inscription_paiement.inscription
            candidature = inscription.candidature

            logger.info(f"💾 Paiement trouvé: {paiement.numero_transaction}")
            logger.info(f"📧 Candidature: {candidature.email}")

            old_status = paiement.statut

            # Mapper les statuts LigdiCash
            status = str(data.get('status', '')).lower()
            response_code = data.get('response_code', '')

            logger.info(f"📊 Statut LigdiCash: {status} (code: {response_code})")

            # ============================================
            # SI PAIEMENT CONFIRMÉ → CRÉER LE COMPTE
            # ============================================
            if status in ['completed', 'success', 'successful'] or response_code == '00':
                logger.info("✅ PAIEMENT CONFIRMÉ - Création du compte utilisateur...")

                with transaction.atomic():
                    # 1. Mettre à jour le paiement
                    paiement.statut = 'CONFIRME'
                    paiement.date_confirmation = timezone.now()
                    paiement.callback_data = data
                    paiement.save()

                    logger.info(f"✅ Statut paiement mis à jour: {old_status} → CONFIRME")

                    # 2. Mettre à jour l'inscription_paiement
                    inscription_paiement.mettre_a_jour_statut()

                    # 3. Vérifier si le compte existe déjà
                    if not inscription.apprenant:
                        logger.info("👤 Création du compte utilisateur...")

                        # CRÉER LE COMPTE
                        apprenant = create_user_from_candidature(candidature)

                        if apprenant:
                            # Lier l'apprenant à l'inscription
                            inscription.apprenant = apprenant
                            inscription.statut = 'ACTIVE'
                            inscription.save()

                            logger.info(f"[OK] Compte créé: {apprenant.email} - Matricule: {apprenant.matricule}")
                            logger.info(f"[OK] Inscription activée: {inscription.numero_inscription}")

                            # Envoyer email de confirmation
                            try:
                                EmailCandidatureManager.send_inscription_confirmee(inscription)
                                logger.info(f"[OK] Email confirmation envoyé à {apprenant.email}")
                            except Exception as e:
                                logger.error(f"[ERROR] Envoi email: {str(e)}")
                        else:
                            logger.error("[ERROR] Échec création compte utilisateur")
                    else:
                        logger.info(f"[INFO] Compte déjà existant: {inscription.apprenant.email}")

            # ============================================
            # SI PAIEMENT ÉCHOUÉ
            # ============================================
            elif status in ['failed', 'error']:
                paiement.statut = 'ECHEC'
                paiement.callback_data = data
                paiement.save()
                logger.warning(f"❌ Statut mis à jour: {old_status} → ECHEC")

            # ============================================
            # SI PAIEMENT ANNULÉ
            # ============================================
            elif status in ['cancelled', 'canceled']:
                paiement.statut = 'ANNULE'
                paiement.callback_data = data
                paiement.save()
                logger.warning(f"🚫 Statut mis à jour: {old_status} → ANNULE")

            else:
                logger.info(f"📊 Statut non traité: {status}")
                paiement.callback_data = data
                paiement.save()

        except Paiement.DoesNotExist:
            logger.error(f"❌ Paiement non trouvé: {paiement_id}")
            return HttpResponse("Payment not found", status=404)

        logger.info("✅ Webhook traité avec succès")
        logger.info("=" * 60)
        return HttpResponse("OK")

    except Exception as e:
        logger.error(f"❌ Erreur lors du traitement du webhook: {str(e)}", exc_info=True)
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


def payer_ligdicash_public(request, paiement_id, token):
    """
    Vue publique pour payer via LigdiCash
    Accessible sans authentification avec le token de candidature
    """
    try:
        # Récupérer le paiement
        paiement = get_object_or_404(Paiement, id=paiement_id)
        inscription_paiement = paiement.inscription_paiement
        inscription = inscription_paiement.inscription
        candidature = inscription.candidature

        # Vérifier le token
        if candidature.token_inscription != token:
            messages.error(request, "Token invalide")
            return redirect('enrollment:candidature_create')

        # Vérifier que le paiement est en attente
        if paiement.statut != 'EN_ATTENTE':
            messages.info(request, f"Ce paiement a déjà été traité ({paiement.get_statut_display()})")
            return redirect('enrollment:candidature_create')

        # ============================================
        # CONSTRUIRE LES URLs - AVEC HTTPS FORCÉ
        # ============================================

        logger.info("=" * 60)
        logger.info("[DEBUG] CONSTRUCTION DES URLs DE CALLBACK")
        logger.info("=" * 60)

        # Informations de la requête
        host = request.get_host()
        logger.info(f"[DEBUG] request.scheme: {request.scheme}")
        logger.info(f"[DEBUG] request.get_host(): {host}")

        # FORCER HTTPS si ngrok ou domaine public
        if 'ngrok' in host or 'herokuapp' in host or not ('localhost' in host or '127.0.0.1' in host):
            scheme = 'https'
            logger.info("[DEBUG] HTTPS forcé (ngrok ou domaine public détecté)")
        else:
            scheme = request.scheme
            logger.info(f"[DEBUG] Scheme local: {scheme}")

        base_url = f"{scheme}://{host}"
        logger.info(f"[DEBUG] base_url construit: {base_url}")

        # Construire les URLs de callback
        url_succes_path = reverse('payments:callback_success_public', kwargs={
            'paiement_id': paiement_id,
            'token': token
        })
        url_succes = f"{base_url}{url_succes_path}"
        logger.info(f"[DEBUG] url_succes: {url_succes}")

        url_echec_path = reverse('payments:callback_error_public', kwargs={
            'paiement_id': paiement_id,
            'token': token
        })
        url_echec = f"{base_url}{url_echec_path}"
        logger.info(f"[DEBUG] url_echec: {url_echec}")

        url_callback_path = reverse('payments:webhook_ligdicash')
        url_callback = f"{base_url}{url_callback_path}"
        logger.info(f"[DEBUG] url_callback: {url_callback}")

        logger.info("=" * 60)
        logger.info("[DEBUG] RÉSUMÉ DES URLs")
        logger.info("=" * 60)
        logger.info(f"URL Succès : {url_succes}")
        logger.info(f"URL Échec  : {url_echec}")
        logger.info(f"URL Callback: {url_callback}")
        logger.info("=" * 60)

        # Vérifier que les URLs sont complètes
        if not url_succes.startswith('http'):
            logger.error(f"[ERROR] URL succès incomplète: {url_succes}")
            raise ValueError("URL de succès mal formée")

        if not url_echec.startswith('http'):
            logger.error(f"[ERROR] URL échec incomplète: {url_echec}")
            raise ValueError("URL d'échec mal formée")

        if not url_callback.startswith('http'):
            logger.error(f"[ERROR] URL callback incomplète: {url_callback}")
            raise ValueError("URL de callback mal formée")

        # ============================================
        # APPELER L'API LIGDICASH
        # ============================================

        # Préparer les informations
        nom_client = candidature.nom_complet()
        email_client = candidature.email

        logger.info("[DEBUG] Informations client:")
        logger.info(f"  - Nom: {nom_client}")
        logger.info(f"  - Email: {email_client}")
        logger.info(f"  - Montant: {paiement.montant} XOF")
        logger.info(f"  - Description: {paiement.description}")

        success, response = ligdicash_service.creer_paiement_redirection(
            paiement_id=str(paiement.id),
            montant=paiement.montant,
            description=paiement.description or f"Inscription {candidature.filiere.nom}",
            email_client=email_client,
            nom_client=nom_client,
            url_retour_succes=url_succes,
            url_retour_echec=url_echec,
            url_callback=url_callback
        )

        if success:
            # Mettre à jour le paiement
            paiement.statut = 'EN_COURS'
            paiement.reference_externe = response.get('transaction_id')
            paiement.donnees_transaction = response.get('raw_response', {})
            paiement.save()

            payment_url = response.get('payment_url')
            logger.info(f"[OK] Redirection vers LigdiCash: {payment_url}")

            # Rediriger vers LigdiCash
            return redirect(payment_url)
        else:
            # Erreur lors de la création du paiement
            error_message = response.get('error', 'Erreur inconnue')
            error_code = response.get('error_code', 'unknown')
            description = response.get('description', '')

            logger.error(f"[ERROR] Création paiement LigdiCash: {error_message}")
            logger.error(f"[ERROR] Code: {error_code}")
            logger.error(f"[ERROR] Description: {description}")

            # Marquer le paiement comme échoué
            paiement.statut = 'ECHEC'
            paiement.notes_admin = f"Erreur LigdiCash ({error_code}): {error_message}"
            paiement.donnees_transaction = response
            paiement.save()

            # Messages d'erreur détaillés
            if error_code == 'ligdicash_02':
                messages.error(
                    request,
                    "Erreur d'authentification avec LigdiCash. "
                    "Veuillez contacter l'établissement."
                )
            elif error_code == 'ligdicash_08':
                messages.error(
                    request,
                    f"Erreur de configuration du paiement: {description}. "
                    "Les URLs de callback sont invalides. "
                    "Veuillez contacter l'établissement."
                )
            else:
                messages.error(
                    request,
                    f"Impossible de créer le paiement: {error_message}. "
                    "Veuillez réessayer ou contacter l'établissement."
                )

            # Retour à la page d'inscription
            return redirect('enrollment:inscription_avec_token', token=token)

    except Exception as e:
        logger.error(f"[ERROR] payer_ligdicash_public: {str(e)}", exc_info=True)
        messages.error(request, "Une erreur est survenue. Veuillez réessayer.")
        return redirect('enrollment:candidature_create')


# ============================================
# CALLBACKS DE PAIEMENT
# ============================================
def callback_success_public(request, paiement_id, token):
    """
    Callback de succès du paiement LigdiCash (VERSION PUBLIQUE)
    C'EST ICI QU'ON CRÉE LE COMPTE UTILISATEUR
    """
    try:

        paiement = get_object_or_404(Paiement, id=paiement_id)
        inscription_paiement = paiement.inscription_paiement
        inscription = inscription_paiement.inscription
        candidature = inscription.candidature

        # Vérifier le token
        if candidature.token_inscription != token:
            messages.error(request, "Token invalide")
            return redirect('enrollment:candidature_create')

        logger.info(f"[CALLBACK] Paiement {paiement.numero_transaction} - Statut: {paiement.statut}")

        # ============================================
        # SI PAIEMENT CONFIRMÉ: CRÉER LE COMPTE
        # ============================================
        if paiement.statut == 'CONFIRME':
            # Vérifier si le compte existe déjà
            if inscription.apprenant:
                logger.info(f"[INFO] Compte déjà créé: {inscription.apprenant.email}")
                messages.success(
                    request,
                    "Paiement confirmé ! Votre compte est actif. "
                    "Vérifiez votre email pour vos identifiants."
                )
            else:
                # Créer le compte
                with transaction.atomic():
                    apprenant = create_user_from_candidature(candidature)

                    if not apprenant:
                        logger.error("[ERROR] Impossible de créer le compte utilisateur")
                        messages.error(request, "Erreur lors de la création du compte")
                        return redirect('enrollment:candidature_create')

                    logger.info(f"[OK] Compte créé après paiement: {apprenant.email} - {apprenant.matricule}")

                    # Mettre à jour l'inscription
                    inscription.apprenant = apprenant
                    inscription.statut = 'ACTIVE'
                    inscription.save()

                    logger.info(f"[OK] Inscription liée à l'apprenant: {inscription.numero_inscription}")

                    # Envoyer email de confirmation
                    try:
                        EmailCandidatureManager.send_inscription_confirmee(inscription)
                        logger.info(f"[OK] Email confirmation envoyé à {apprenant.email}")
                    except Exception as e:
                        logger.error(f"[ERROR] Envoi email: {str(e)}")

                messages.success(
                    request,
                    "Paiement confirmé ! Votre compte a été créé. "
                    "Vous allez recevoir vos identifiants par email."
                )

            # Afficher la page de succès
            return render(request, 'payments/public/success.html', {
                'paiement': paiement,
                'inscription': inscription,
                'apprenant': inscription.apprenant,
                'candidature': candidature,
                'show_login_link': True
            })

        # ============================================
        # SI PAIEMENT EN ATTENTE
        # ============================================
        elif paiement.statut == 'EN_ATTENTE':
            messages.info(request, "Votre paiement est en cours de traitement...")
            return render(request, 'payments/public/pending.html', {
                'paiement': paiement,
                'candidature': candidature,
                'check_url': request.build_absolute_uri(
                    reverse('payments:callback_success_public', kwargs={
                        'paiement_id': paiement_id,
                        'token': token
                    })
                )
            })

        # ============================================
        # SI PAIEMENT ÉCHOUÉ
        # ============================================
        else:
            messages.error(request, "Le paiement a échoué. Veuillez réessayer.")
            return redirect('enrollment:inscription_nouvelle', token=token)

    except Exception as e:
        logger.error(f"[ERROR] Callback: {str(e)}", exc_info=True)
        messages.error(request, "Une erreur est survenue")
        return redirect('enrollment:candidature_create')

def callback_error_public(request, paiement_id, token):
    """Callback d'erreur de paiement"""
    try:
        paiement = get_object_or_404(Paiement, id=paiement_id)
        candidature = paiement.inscription_paiement.inscription.candidature

        # Vérifier le token
        if candidature.token_inscription != token:
            messages.error(request, "Token invalide")
            return redirect('enrollment:candidature_create')

        # Marquer le paiement comme échoué
        paiement.statut = 'ECHEC'
        paiement.save()

        logger.info(f"[ERROR] Paiement échoué: {paiement.numero_transaction}")

        messages.error(
            request,
            "Le paiement a échoué ou a été annulé. "
            "Vous pouvez réessayer en cliquant sur le bouton ci-dessous."
        )

        return render(request, 'payments/public/error.html', {
            'paiement': paiement,
            'candidature': candidature,
            'retry_url': reverse('enrollment:inscription_nouvelle', kwargs={'token': token})
        })

    except Exception as e:
        logger.error(f"[ERROR] Callback error: {str(e)}", exc_info=True)
        messages.error(request, "Une erreur est survenue")
        return redirect('enrollment:candidature_create')

def create_user_from_candidature(candidature):
    """
    Créer un compte utilisateur APPRENANT depuis une candidature
    APPELÉ UNIQUEMENT APRÈS PAIEMENT CONFIRMÉ
    """
    try:
        # Vérifier si l'utilisateur existe déjà
        if User.objects.filter(email=candidature.email).exists():
            logger.info(f"Compte existe déjà pour {candidature.email}")
            return User.objects.get(email=candidature.email)

        # Générer un mot de passe aléatoire sécurisé
        password = get_random_string(12)

        with transaction.atomic():
            # Récupérer la photo d'identité
            photo_profil = None
            try:
                doc_photo = DocumentCandidature.objects.filter(
                    candidature=candidature,
                    type_document='PHOTO_IDENTITE'
                ).first()

                if doc_photo and doc_photo.fichier:
                    photo_profil = doc_photo.fichier
            except Exception as e:
                logger.error(f"Erreur récupération photo: {str(e)}")

            # 1. Créer l'utilisateur
            user = User.objects.create_user(
                email=candidature.email,
                username=candidature.email,
                prenom=candidature.prenom,
                nom=candidature.nom,
                role='APPRENANT',
                etablissement=candidature.etablissement,
                departement=candidature.filiere.departement,
                date_naissance=candidature.date_naissance,
                lieu_naissance=candidature.lieu_naissance,
                genre=candidature.genre,
                telephone=candidature.telephone,
                adresse=candidature.adresse,
                photo_profil=photo_profil,
                est_actif=True
            )

            user.set_password(password)
            user.save()

            logger.info(f"[OK] Utilisateur créé: {user.email} - Matricule: {user.matricule}")

            # 2. Créer le ProfilUtilisateur
            ProfilUtilisateur.objects.get_or_create(
                utilisateur=user,
                defaults={
                    'recevoir_notifications': True,
                    'recevoir_notifications_email': True,
                    'langue': 'fr',
                    'fuseau_horaire': 'Africa/Ouagadougou',
                }
            )

            # 3. Créer le ProfilApprenant
            ProfilApprenant.objects.create(
                utilisateur=user,
                niveau_actuel=candidature.niveau,
                annee_academique=candidature.annee_academique,
                classe_actuelle=None,  # Sera assigné plus tard
                statut_paiement='PARTIEL',  # Première tranche payée
                nom_pere=candidature.nom_pere or '',
                telephone_pere=candidature.telephone_pere or '',
                nom_mere=candidature.nom_mere or '',
                telephone_mere=candidature.telephone_mere or '',
                nom_tuteur=candidature.nom_tuteur or '',
                telephone_tuteur=candidature.telephone_tuteur or '',
            )

            # 4. Envoyer les informations de connexion
            try:
                EmailCandidatureManager.send_account_created(
                    user,
                    password,
                    candidature.etablissement
                )
                logger.info(f"[OK] Email identifiants envoyé à {user.email}")
            except Exception as e:
                logger.error(f"[ERROR] Envoi email identifiants: {str(e)}")

            return user

    except Exception as e:
        logger.error(f"[ERROR] Création compte: {str(e)}", exc_info=True)
        return None