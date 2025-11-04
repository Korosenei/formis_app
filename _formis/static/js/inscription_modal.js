// static/js/inscription_modal.js

(function() {
    'use strict';

    // ========== GESTION DU MODAL ==========

    function showModal() {
        const modal = document.getElementById('inscriptionModal');
        if (modal) {
            modal.classList.add('active');
            document.body.classList.add('modal-open');
            document.body.style.overflow = 'hidden';
        }
    }

    function closeModal() {
        const modal = document.getElementById('inscriptionModal');
        if (modal) {
            modal.classList.remove('active');
            document.body.classList.remove('modal-open');
            document.body.style.overflow = 'auto';
        }
    }

    function shakeModal() {
        const container = document.querySelector('.modal-container');
        if (container) {
            container.style.animation = 'none';
            setTimeout(() => {
                container.style.animation = 'shake 0.5s ease';
            }, 10);
        }
    }

    // Empêcher la fermeture du modal
    document.getElementById('inscriptionModal')?.addEventListener('click', function(e) {
        if (e.target === this) {
            e.stopPropagation();
            shakeModal();
        }
    });

    // Empêcher ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const modal = document.getElementById('inscriptionModal');
            if (modal && modal.classList.contains('active')) {
                e.preventDefault();
                e.stopPropagation();
                shakeModal();
            }
        }
    }, true);

    // ========== INITIALISATION ==========

    window.initInscriptionModal = async function() {
        try {
            console.log('🚀 Initialisation modal inscription');
            showModal();

            const response = await fetch('/payments/inscription/verifier-statut/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            if (!response.ok) throw new Error('Erreur vérification');

            const data = await response.json();
            console.log('📊 Statut:', data);

            if (data.peut_acceder) {
                console.log('✅ Accès autorisé - Rechargement');
                closeModal();
                window.location.reload();
                return;
            }

            afficherEtape(data);

        } catch (error) {
            console.error('❌ Erreur:', error);
            afficherErreur('Impossible de vérifier le statut de l\'inscription');
        }
    };

    function afficherEtape(data) {
        // Masquer toutes les étapes
        document.querySelectorAll('.modal-step').forEach(step => {
            step.style.display = 'none';
        });

        // Afficher l'étape appropriée
        switch(data.action_requise) {
            case 'attendre':
                afficherPaiementEnCours(data);
                break;
            case 'inscrire':
                afficherInscriptionRequise(data);
                break;
            default:
                afficherErreur(data.message || 'Statut inconnu');
        }
    }

    // ========== ÉTAPE: PAIEMENT EN COURS ==========

    function afficherPaiementEnCours(data) {
        document.getElementById('modalTitle').textContent = 'Paiement en cours';
        document.getElementById('modalSubtitle').textContent = 'Vérification en cours';
        document.getElementById('step_payment_pending').style.display = 'block';

        // Compte à rebours
        let countdown = 30;
        const countdownElement = document.getElementById('countdown-value');

        const interval = setInterval(() => {
            countdown--;
            if (countdownElement) {
                countdownElement.textContent = countdown;
            }
        }, 1000);

        // Auto-refresh
        setTimeout(() => {
            clearInterval(interval);
            window.location.reload();
        }, 30000);
    }

    // ========== ÉTAPE: INSCRIPTION REQUISE ==========

    async function afficherInscriptionRequise(data) {
        document.getElementById('modalTitle').textContent = 'Finaliser l\'inscription';
        document.getElementById('modalSubtitle').textContent = 'Choisissez votre plan de paiement';

        try {
            const response = await fetch('/payments/inscription/initier/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            const inscriptionData = await response.json();

            if (inscriptionData.success && inscriptionData.plans_disponibles?.length > 0) {
                afficherPlans(inscriptionData.plans_disponibles);
                document.getElementById('step_inscription_required').style.display = 'block';
            } else {
                afficherErreur('Aucun plan de paiement disponible');
            }

        } catch (error) {
            console.error('Erreur:', error);
            afficherErreur('Impossible de charger les plans de paiement');
        }
    }

    function afficherPlans(plans) {
        if (plans.length === 0) return;

        const planData = plans[0];
        const candidature = planData.candidature;
        const plan = planData.plan;

        // Remplir les infos candidature
        document.getElementById('info_etablissement').textContent = candidature.etablissement_nom;
        document.getElementById('info_filiere').textContent = candidature.filiere_nom;
        document.getElementById('info_niveau').textContent = candidature.niveau_nom;
        document.getElementById('info_annee').textContent = candidature.annee_academique_nom;
        document.getElementById('selected_candidature_id').value = candidature.id;

        // Afficher les plans
        if (plan.paiement_unique_possible) {
            afficherPlanUnique(plan, planData.montant_unique);
        }

        if (plan.paiement_echelonne_possible) {
            afficherPlanEchelonne(plan, planData.montant_echelonne, planData.premiere_tranche);
        }
    }

    function afficherPlanUnique(plan, montantUnique) {
        const card = document.getElementById('plan_unique_card');
        card.style.display = 'block';

        const montantOriginal = plan.montant_total;
        const remise = montantOriginal - montantUnique;

        document.getElementById('plan_unique_original').textContent = formatMontant(montantOriginal);
        document.getElementById('plan_unique_final').textContent = formatMontant(montantUnique);

        if (remise > 0) {
            document.getElementById('plan_unique_savings').style.display = 'flex';
            document.getElementById('plan_unique_savings_amount').textContent = formatMontant(remise);
        }
    }

    function afficherPlanEchelonne(plan, montantTotal, premiereTranche) {
        const card = document.getElementById('plan_echelonne_card');
        card.style.display = 'block';

        document.getElementById('plan_echelonne_total').textContent = formatMontant(montantTotal);
        document.getElementById('plan_echelonne_premiere').textContent = formatMontant(premiereTranche.montant);
        document.getElementById('plan_echelonne_frais').textContent = formatMontant(plan.frais_echelonnement);

        if (plan.tranches && plan.tranches.length > 0) {
            const tranchesList = document.getElementById('tranches_list');
            tranchesList.innerHTML = '<h6>Détail des tranches</h6>';

            plan.tranches.forEach(tranche => {
                const item = document.createElement('div');
                item.className = 'tranche-item';
                item.innerHTML = `
                    <span class="tranche-label">Tranche ${tranche.numero} - ${tranche.nom}</span>
                    <span class="tranche-amount">${formatMontant(tranche.montant)} XOF</span>
                `;
                tranchesList.appendChild(item);
            });
        }
    }

    // ========== ÉTAPE: ERREUR ==========

    function afficherErreur(message) {
        document.getElementById('modalTitle').textContent = 'Erreur';
        document.getElementById('modalSubtitle').textContent = 'Une erreur est survenue';
        document.getElementById('error_message').textContent = message;
        document.getElementById('step_error').style.display = 'block';
    }

    // ========== ACTIONS ==========

    window.checkPaymentStatus = async function() {
        const btn = event.target;
        const originalText = btn.innerHTML;

        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Vérification...';

        try {
            const response = await fetch('/payments/inscription/verifier-statut/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            const data = await response.json();

            if (data.peut_acceder) {
                window.location.reload();
            } else {
                alert(data.message || 'Le paiement est toujours en cours');
            }
        } catch (error) {
            console.error('Erreur:', error);
            alert('Erreur lors de la vérification');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    };

    // ========== FORMULAIRE ==========

    document.getElementById('inscriptionForm')?.addEventListener('submit', function(e) {
        const selectedPlan = document.querySelector('input[name="type_paiement"]:checked');

        if (!selectedPlan) {
            e.preventDefault();
            alert('Veuillez sélectionner un plan de paiement');
            return false;
        }

        const btn = document.getElementById('btnProceedPayment');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Redirection...';
    });

    // ========== UTILITAIRES ==========

    function formatMontant(montant) {
        return new Intl.NumberFormat('fr-FR').format(montant);
    }

    // Debug
    window.debugModal = function() {
        const modal = document.getElementById('inscriptionModal');
        console.log('Modal:', modal ? 'Présent' : 'Absent');
        if (modal) console.log('Visible:', modal.classList.contains('active'));
    };

})();