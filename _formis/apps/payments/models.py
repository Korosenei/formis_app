# apps/payments/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from apps.core.models import BaseModel
import uuid

class PlanPaiement(BaseModel):
    """Plan de paiement pour une filière/niveau"""

    filiere = models.ForeignKey(
        'academic.Filiere',
        on_delete=models.CASCADE,
        related_name='plans_paiement',
        verbose_name="Filière"
    )
    niveau = models.ForeignKey(
        'academic.Niveau',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='plans_paiement',
        verbose_name="Niveau (optionnel)"
    )
    annee_academique = models.ForeignKey(
        'establishments.AnneeAcademique',
        on_delete=models.CASCADE,
        verbose_name="Année académique"
    )

    nom = models.CharField(max_length=200, verbose_name="Nom du plan")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    # Montants
    montant_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant total"
    )

    # Options de paiement
    paiement_unique_possible = models.BooleanField(
        default=True,
        verbose_name="Paiement unique autorisé"
    )
    paiement_echelonne_possible = models.BooleanField(
        default=True,
        verbose_name="Paiement échelonné autorisé"
    )

    # Remises
    remise_paiement_unique = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name="Remise paiement unique (%)"
    )

    # Frais supplémentaires
    frais_echelonnement = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Frais d'échelonnement"
    )

    # Statut
    est_actif = models.BooleanField(default=True, verbose_name="Actif")

    # Audit
    cree_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plans_crees',
        verbose_name="Créé par"
    )

    class Meta:
        db_table = 'payments_plan_paiement'
        verbose_name = "Plan de paiement"
        verbose_name_plural = "Plans de paiement"
        ordering = ['filiere__nom', 'niveau__nom']
        unique_together = ['filiere', 'niveau', 'annee_academique']

    def __str__(self):
        niveau_str = f" - {self.niveau.nom}" if self.niveau else ""
        return f"{self.filiere.nom}{niveau_str} ({self.annee_academique.nom})"

    def get_montant_avec_remise(self):
        """Calcule le montant avec remise pour paiement unique"""
        if self.remise_paiement_unique > 0:
            remise = self.montant_total * (self.remise_paiement_unique / 100)
            return self.montant_total - remise
        return self.montant_total

    def get_montant_avec_frais(self):
        """Calcule le montant total avec frais d'échelonnement"""
        return self.montant_total + self.frais_echelonnement

class TranchePaiement(BaseModel):
    """Tranches de paiement d'un plan"""

    plan = models.ForeignKey(
        PlanPaiement,
        on_delete=models.CASCADE,
        related_name='tranches',
        verbose_name="Plan de paiement"
    )

    numero = models.IntegerField(verbose_name="Numéro de tranche")
    nom = models.CharField(max_length=100, verbose_name="Nom de la tranche")

    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant"
    )

    # Dates limites
    date_limite = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date limite de paiement"
    )

    # Ordre de paiement
    est_premiere_tranche = models.BooleanField(
        default=False,
        verbose_name="Première tranche (obligatoire pour inscription)"
    )

    # Pénalités de retard
    penalite_retard = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Pénalité de retard (%)"
    )

    class Meta:
        db_table = 'payments_tranche_paiement'
        verbose_name = "Tranche de paiement"
        verbose_name_plural = "Tranches de paiement"
        ordering = ['plan', 'numero']
        unique_together = ['plan', 'numero']

    def __str__(self):
        return f"{self.plan} - Tranche {self.numero}: {self.nom}"

    def est_en_retard(self):
        """Vérifie si la tranche est en retard"""
        if not self.date_limite:
            return False
        return timezone.now().date() > self.date_limite

    def get_montant_avec_penalite(self):
        """Calcule le montant avec pénalité de retard si applicable"""
        if self.est_en_retard() and self.penalite_retard > 0:
            penalite = self.montant * (self.penalite_retard / 100)
            return self.montant + penalite
        return self.montant

class InscriptionPaiement(BaseModel):
    """Lien entre une inscription et son plan de paiement"""

    inscription = models.OneToOneField(
        'enrollment.Inscription',
        on_delete=models.CASCADE,
        related_name='plan_paiement_inscription',
        verbose_name="Inscription"
    )

    plan = models.ForeignKey(
        PlanPaiement,
        on_delete=models.CASCADE,
        related_name='inscriptions',
        verbose_name="Plan de paiement"
    )

    TYPES_PAIEMENT = [
        ('UNIQUE', 'Paiement unique'),
        ('ECHELONNE', 'Paiement échelonné'),
    ]

    type_paiement = models.CharField(
        max_length=20,
        choices=TYPES_PAIEMENT,
        verbose_name="Type de paiement choisi"
    )

    montant_total_du = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant total dû"
    )

    montant_total_paye = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Montant total payé"
    )

    STATUTS_PAIEMENT = [
        ('EN_ATTENTE', 'En attente'),
        ('PARTIEL', 'Partiel'),
        ('COMPLET', 'Complet'),
        ('EN_RETARD', 'En retard'),
    ]

    statut = models.CharField(
        max_length=20,
        choices=STATUTS_PAIEMENT,
        default='EN_ATTENTE',
        verbose_name="Statut"
    )

    # Dates importantes
    date_premier_paiement = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date du premier paiement"
    )
    date_solde = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de solde"
    )

    class Meta:
        db_table = 'payments_inscription_paiement'
        verbose_name = "Paiement d'inscription"
        verbose_name_plural = "Paiements d'inscriptions"
        ordering = ['-created_at']

    def __str__(self):
        return f"Paiement {self.inscription.apprenant.get_full_name()} - {self.get_type_paiement_display()}"

    @property
    def solde_restant(self):
        """Calcule le solde restant"""
        montant_total_du = self.montant_total_du or Decimal('0.00')
        montant_total_paye = self.montant_total_paye or Decimal('0.00')
        return montant_total_du - montant_total_paye

    @property
    def pourcentage_paye(self):
        """Calcule le pourcentage payé"""
        montant_total_du = self.montant_total_du or Decimal('0.00')
        montant_total_paye = self.montant_total_paye or Decimal('0.00')

        if montant_total_du == 0:
            return 0
        return round((montant_total_paye / montant_total_du) * 100, 2)

    def est_inscrit_autorise(self):
        """Vérifie si l'étudiant peut s'inscrire (première tranche payée)"""
        if self.type_paiement == 'UNIQUE':
            return self.statut == 'COMPLET'
        else:
            # Vérifier que la première tranche est payée
            premiere_tranche = self.plan.tranches.filter(est_premiere_tranche=True).first()
            if premiere_tranche:
                return self.paiements.filter(
                    tranche=premiere_tranche,
                    statut='CONFIRME'
                ).exists()
            return self.montant_total_paye > 0

    def get_prochaine_tranche_due(self):
        """Retourne la prochaine tranche à payer"""
        if self.type_paiement != 'ECHELONNE':
            return None

        tranches_payees = self.paiements.filter(
            statut='CONFIRME'
        ).values_list('tranche_id', flat=True)

        return self.plan.tranches.exclude(
            id__in=tranches_payees
        ).order_by('numero').first()

    def mettre_a_jour_statut(self):
        """Met à jour le statut selon les paiements"""
        if self.solde_restant <= 0:
            self.statut = 'COMPLET'
            if not self.date_solde:
                self.date_solde = timezone.now()
        elif self.montant_total_paye > 0:
            # Vérifier si en retard
            prochaine_tranche = self.get_prochaine_tranche_due()
            if prochaine_tranche and prochaine_tranche.est_en_retard():
                self.statut = 'EN_RETARD'
            else:
                self.statut = 'PARTIEL'
        else:
            self.statut = 'EN_ATTENTE'

        self.save()

class Paiement(BaseModel):
    """Transaction de paiement"""

    # Références
    inscription_paiement = models.ForeignKey(
        InscriptionPaiement,
        on_delete=models.CASCADE,
        related_name='paiements',
        verbose_name="Plan de paiement d'inscription"
    )

    tranche = models.ForeignKey(
        TranchePaiement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='paiements',
        verbose_name="Tranche (si applicable)"
    )

    # Identifiants de transaction
    numero_transaction = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Numéro de transaction"
    )
    reference_externe = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Référence externe (LigdiCash)"
    )

    # Montants
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant"
    )
    frais_transaction = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Frais de transaction"
    )
    montant_net = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant net reçu"
    )

    # Méthode de paiement
    METHODES_PAIEMENT = [
        ('LIGDICASH', 'LigdiCash'),
        ('ESPECES', 'Espèces'),
        ('CHEQUE', 'Chèque'),
        ('VIREMENT', 'Virement bancaire'),
        ('AUTRE', 'Autre'),
    ]

    methode_paiement = models.CharField(
        max_length=20,
        choices=METHODES_PAIEMENT,
        default='LIGDICASH',
        verbose_name="Méthode de paiement"
    )

    # Statuts
    STATUTS_PAIEMENT = [
        ('EN_ATTENTE', 'En attente'),
        ('EN_COURS', 'En cours de traitement'),
        ('CONFIRME', 'Confirmé'),
        ('ECHEC', 'Échec'),
        ('ANNULE', 'Annulé'),
        ('REMBOURSE', 'Remboursé'),
    ]

    statut = models.CharField(
        max_length=20,
        choices=STATUTS_PAIEMENT,
        default='EN_ATTENTE',
        verbose_name="Statut"
    )

    # Dates importantes
    date_paiement = models.DateTimeField(auto_now_add=True, verbose_name="Date de paiement")
    date_confirmation = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de confirmation"
    )
    date_echeance = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date d'échéance"
    )

    # Informations complémentaires
    description = models.TextField(null=True, blank=True, verbose_name="Description")
    notes_admin = models.TextField(null=True, blank=True, verbose_name="Notes administratives")

    # Données de la transaction (JSON)
    donnees_transaction = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Données de transaction"
    )

    # Traitement
    traite_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role__in': ['ADMIN', 'CHEF_DEPARTEMENT']},
        related_name='paiements_traites',
        verbose_name="Traité par"
    )

    class Meta:
        db_table = 'payments_paiement'
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ['-date_paiement']
        indexes = [
            models.Index(fields=['statut', 'date_paiement']),
            models.Index(fields=['inscription_paiement', 'statut']),
            models.Index(fields=['reference_externe']),
        ]

    def save(self, *args, **kwargs):
        # Générer le numéro de transaction si absent
        if not self.numero_transaction:
            self.numero_transaction = self.generer_numero_transaction()

        # Calculer le montant net
        self.montant_net = self.montant - self.frais_transaction

        super().save(*args, **kwargs)

        # Mettre à jour le total payé de l'inscription
        if self.statut == 'CONFIRME':
            self.mettre_a_jour_inscription()

    def generer_numero_transaction(self):
        """Génère un numéro de transaction unique"""
        from django.utils import timezone

        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_suffix = str(uuid.uuid4()).replace('-', '')[:6].upper()
        return f"PAY{timestamp}{random_suffix}"

    def mettre_a_jour_inscription(self):
        """Met à jour les totaux de l'inscription"""
        inscription = self.inscription_paiement

        # Recalculer le total payé
        total_paye = inscription.paiements.filter(
            statut='CONFIRME'
        ).aggregate(total=models.Sum('montant'))['total'] or Decimal('0.00')

        inscription.montant_total_paye = total_paye

        # Définir la date du premier paiement
        if not inscription.date_premier_paiement:
            inscription.date_premier_paiement = self.date_confirmation or self.date_paiement

        inscription.save()
        inscription.mettre_a_jour_statut()

    def confirmer(self, reference_externe=None, frais=None):
        """Confirme le paiement"""
        self.statut = 'CONFIRME'
        self.date_confirmation = timezone.now()

        if reference_externe:
            self.reference_externe = reference_externe

        if frais is not None:
            self.frais_transaction = Decimal(str(frais))
            self.montant_net = self.montant - self.frais_transaction

        self.save()

    def echec(self, motif=None):
        """Marque le paiement comme échoué"""
        self.statut = 'ECHEC'
        if motif:
            self.notes_admin = motif
        self.save()

    def annuler(self, motif=None):
        """Annule le paiement"""
        self.statut = 'ANNULE'
        if motif:
            self.notes_admin = motif
        self.save()

    def __str__(self):
        return f"{self.numero_transaction} - {self.montant}€ ({self.get_statut_display()})"

class HistoriquePaiement(BaseModel):
    """Historique des modifications de paiement"""

    paiement = models.ForeignKey(
        Paiement,
        on_delete=models.CASCADE,
        related_name='historique',
        verbose_name="Paiement"
    )

    TYPES_ACTION = [
        ('CREATION', 'Création'),
        ('MODIFICATION', 'Modification'),
        ('CONFIRMATION', 'Confirmation'),
        ('ECHEC', 'Échec'),
        ('ANNULATION', 'Annulation'),
        ('REMBOURSEMENT', 'Remboursement'),
    ]

    type_action = models.CharField(
        max_length=20,
        choices=TYPES_ACTION,
        verbose_name="Type d'action"
    )

    ancien_statut = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Ancien statut"
    )
    nouveau_statut = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Nouveau statut"
    )

    details = models.TextField(null=True, blank=True, verbose_name="Détails")
    donnees_supplementaires = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Données supplémentaires"
    )

    utilisateur = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Utilisateur"
    )

    adresse_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Adresse IP"
    )

    class Meta:
        db_table = 'payments_historique_paiement'
        verbose_name = "Historique de paiement"
        verbose_name_plural = "Historiques de paiements"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.paiement.numero_transaction} - {self.get_type_action_display()}"

class RemboursementPaiement(BaseModel):
    """Remboursements de paiement"""

    paiement_original = models.OneToOneField(
        Paiement,
        on_delete=models.CASCADE,
        related_name='remboursement',
        verbose_name="Paiement original"
    )

    montant_rembourse = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant remboursé"
    )

    motif = models.TextField(verbose_name="Motif du remboursement")

    STATUTS_REMBOURSEMENT = [
        ('DEMANDE', 'Demandé'),
        ('APPROUVE', 'Approuvé'),
        ('TRAITE', 'Traité'),
        ('REJETE', 'Rejeté'),
    ]

    statut = models.CharField(
        max_length=20,
        choices=STATUTS_REMBOURSEMENT,
        default='DEMANDE',
        verbose_name="Statut"
    )

    date_demande = models.DateTimeField(auto_now_add=True, verbose_name="Date de demande")
    date_traitement = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de traitement"
    )

    demande_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='remboursements_demandes',
        verbose_name="Demandé par"
    )

    traite_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='remboursements_traites',
        verbose_name="Traité par"
    )

    notes = models.TextField(null=True, blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'payments_remboursement_paiement'
        verbose_name = "Remboursement"
        verbose_name_plural = "Remboursements"
        ordering = ['-date_demande']

    def __str__(self):
        return f"Remboursement {self.paiement_original.numero_transaction} - {self.montant_rembourse}"
