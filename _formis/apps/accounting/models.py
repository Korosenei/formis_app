# apps/accounting/models.py
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from apps.core.models import BaseModel
from decimal import Decimal
import uuid


class CategorieCompte(models.TextChoices):
    """Catégories de comptes comptables selon le plan comptable"""
    ACTIF = 'ACTIF', 'Actif'
    PASSIF = 'PASSIF', 'Passif'
    CHARGES = 'CHARGES', 'Charges'
    PRODUITS = 'PRODUITS', 'Produits'
    TRESORERIE = 'TRESORERIE', 'Trésorerie'


class CompteComptable(BaseModel):
    """Plan comptable de l'établissement"""
    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        related_name='comptes_comptables',
        verbose_name="Établissement"
    )

    numero_compte = models.CharField(
        max_length=20,
        verbose_name="Numéro de compte"
    )
    libelle = models.CharField(
        max_length=200,
        verbose_name="Libellé"
    )
    categorie = models.CharField(
        max_length=20,
        choices=CategorieCompte.choices,
        verbose_name="Catégorie"
    )

    compte_parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sous_comptes',
        verbose_name="Compte parent"
    )

    solde_actuel = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Solde actuel"
    )

    est_actif = models.BooleanField(default=True, verbose_name="Actif")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    class Meta:
        db_table = 'accounting_compte_comptable'
        verbose_name = "Compte comptable"
        verbose_name_plural = "Comptes comptables"
        ordering = ['numero_compte']
        unique_together = ['etablissement', 'numero_compte']

    def __str__(self):
        return f"{self.numero_compte} - {self.libelle}"


class JournalComptable(BaseModel):
    """Journaux comptables (Ventes, Achats, Banque, etc.)"""

    TYPE_JOURNAL = [
        ('VENTES', 'Journal des ventes'),
        ('ACHATS', 'Journal des achats'),
        ('BANQUE', 'Journal de banque'),
        ('CAISSE', 'Journal de caisse'),
        ('OD', 'Opérations diverses'),
    ]

    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        related_name='journaux_comptables',
        verbose_name="Établissement"
    )

    code = models.CharField(max_length=10, verbose_name="Code")
    libelle = models.CharField(max_length=200, verbose_name="Libellé")
    type_journal = models.CharField(
        max_length=20,
        choices=TYPE_JOURNAL,
        verbose_name="Type de journal"
    )

    est_actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'accounting_journal_comptable'
        verbose_name = "Journal comptable"
        verbose_name_plural = "Journaux comptables"
        ordering = ['code']
        unique_together = ['etablissement', 'code']

    def __str__(self):
        return f"{self.code} - {self.libelle}"


class EcritureComptable(BaseModel):
    """Écritures comptables"""

    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        related_name='ecritures_comptables',
        verbose_name="Établissement"
    )

    journal = models.ForeignKey(
        JournalComptable,
        on_delete=models.PROTECT,
        related_name='ecritures',
        verbose_name="Journal"
    )

    numero_piece = models.CharField(
        max_length=50,
        verbose_name="Numéro de pièce"
    )

    date_ecriture = models.DateField(
        default=timezone.now,
        verbose_name="Date d'écriture"
    )

    libelle = models.CharField(
        max_length=255,
        verbose_name="Libellé"
    )

    reference_externe = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Référence externe"
    )

    # Lien vers les paiements/factures
    paiement = models.ForeignKey(
        'payments.Paiement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecritures_comptables',
        verbose_name="Paiement associé"
    )

    facture = models.ForeignKey(
        'Facture',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecritures_comptables',
        verbose_name="Facture associée"
    )

    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('VALIDEE', 'Validée'),
        ('LETTREE', 'Lettrée'),
        ('CLOTUREE', 'Clôturée'),
    ]

    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='BROUILLON',
        verbose_name="Statut"
    )

    saisi_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        related_name='ecritures_saisies',
        verbose_name="Saisi par"
    )

    valide_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecritures_validees',
        verbose_name="Validé par"
    )

    date_validation = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de validation"
    )

    notes = models.TextField(null=True, blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'accounting_ecriture_comptable'
        verbose_name = "Écriture comptable"
        verbose_name_plural = "Écritures comptables"
        ordering = ['-date_ecriture', '-created_at']

    def __str__(self):
        return f"{self.numero_piece} - {self.libelle}"

    @property
    def total_debit(self):
        return self.lignes.aggregate(total=models.Sum('debit'))['total'] or Decimal('0.00')

    @property
    def total_credit(self):
        return self.lignes.aggregate(total=models.Sum('credit'))['total'] or Decimal('0.00')

    @property
    def est_equilibree(self):
        return self.total_debit == self.total_credit


class LigneEcriture(BaseModel):
    """Lignes d'écriture comptable (débit/crédit)"""

    ecriture = models.ForeignKey(
        EcritureComptable,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name="Écriture"
    )

    compte = models.ForeignKey(
        CompteComptable,
        on_delete=models.PROTECT,
        related_name='lignes_ecriture',
        verbose_name="Compte"
    )

    libelle = models.CharField(
        max_length=255,
        verbose_name="Libellé"
    )

    debit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Débit"
    )

    credit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Crédit"
    )

    numero_ligne = models.IntegerField(
        default=1,
        verbose_name="Numéro de ligne"
    )

    class Meta:
        db_table = 'accounting_ligne_ecriture'
        verbose_name = "Ligne d'écriture"
        verbose_name_plural = "Lignes d'écriture"
        ordering = ['ecriture', 'numero_ligne']

    def __str__(self):
        return f"{self.compte.numero_compte} - Débit: {self.debit}, Crédit: {self.credit}"


class Facture(BaseModel):
    """Factures de scolarité et autres"""

    TYPE_FACTURE = [
        ('SCOLARITE', 'Frais de scolarité'),
        ('INSCRIPTION', 'Frais d\'inscription'),
        ('EXAMEN', 'Frais d\'examen'),
        ('FOURNITURES', 'Fournitures'),
        ('AUTRES', 'Autres'),
    ]

    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        related_name='factures',
        verbose_name="Établissement"
    )

    numero_facture = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Numéro de facture"
    )

    type_facture = models.CharField(
        max_length=20,
        choices=TYPE_FACTURE,
        verbose_name="Type de facture"
    )

    # Client
    apprenant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'APPRENANT'},
        related_name='factures',
        verbose_name="Apprenant"
    )

    inscription = models.ForeignKey(
        'enrollment.Inscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='factures',
        verbose_name="Inscription"
    )

    # Dates
    date_emission = models.DateField(
        default=timezone.now,
        verbose_name="Date d'émission"
    )
    date_echeance = models.DateField(
        verbose_name="Date d'échéance"
    )

    # Montants
    montant_ht = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant HT"
    )

    taux_tva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Taux TVA (%)"
    )

    montant_tva = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Montant TVA"
    )

    montant_ttc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Montant TTC"
    )

    montant_paye = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Montant payé"
    )

    # Statut
    STATUT_FACTURE = [
        ('BROUILLON', 'Brouillon'),
        ('EMISE', 'Émise'),
        ('PARTIELLE', 'Payée partiellement'),
        ('PAYEE', 'Payée'),
        ('ANNULEE', 'Annulée'),
    ]

    statut = models.CharField(
        max_length=20,
        choices=STATUT_FACTURE,
        default='BROUILLON',
        verbose_name="Statut"
    )

    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Description"
    )

    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Notes internes"
    )

    emise_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        related_name='factures_emises',
        verbose_name="Émise par"
    )

    class Meta:
        db_table = 'accounting_facture'
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ['-date_emission']

    def __str__(self):
        return f"{self.numero_facture} - {self.apprenant.get_full_name()}"

    def save(self, *args, **kwargs):
        # Calcul automatique des montants
        if not self.montant_tva:
            self.montant_tva = self.montant_ht * (self.taux_tva / 100)
        if not self.montant_ttc:
            self.montant_ttc = self.montant_ht + self.montant_tva

        # Générer le numéro de facture
        if not self.numero_facture:
            self.numero_facture = self.generer_numero_facture()

        super().save(*args, **kwargs)

    def generer_numero_facture(self):
        annee = timezone.now().year
        dernier = Facture.objects.filter(
            etablissement=self.etablissement,
            numero_facture__startswith=f"FAC{annee}"
        ).order_by('-numero_facture').first()

        if dernier:
            dernier_num = int(dernier.numero_facture[-6:])
            nouveau_num = dernier_num + 1
        else:
            nouveau_num = 1

        return f"FAC{annee}{nouveau_num:06d}"

    @property
    def solde_restant(self):
        return self.montant_ttc - self.montant_paye

    @property
    def est_payee(self):
        return self.montant_paye >= self.montant_ttc


class LigneFacture(BaseModel):
    """Lignes de détail d'une facture"""

    facture = models.ForeignKey(
        Facture,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name="Facture"
    )

    description = models.CharField(
        max_length=255,
        verbose_name="Description"
    )

    quantite = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Quantité"
    )

    prix_unitaire = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Prix unitaire"
    )

    montant = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Montant"
    )

    numero_ligne = models.IntegerField(
        default=1,
        verbose_name="Numéro de ligne"
    )

    class Meta:
        db_table = 'accounting_ligne_facture'
        verbose_name = "Ligne de facture"
        verbose_name_plural = "Lignes de facture"
        ordering = ['facture', 'numero_ligne']

    def save(self, *args, **kwargs):
        self.montant = self.quantite * self.prix_unitaire
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} - {self.montant}"


class Depense(BaseModel):
    """Dépenses de l'établissement"""

    CATEGORIES_DEPENSE = [
        ('SALAIRES', 'Salaires et charges'),
        ('FOURNITURES', 'Fournitures et matériel'),
        ('LOYER', 'Loyer et charges locatives'),
        ('ELECTRICITE', 'Électricité'),
        ('EAU', 'Eau'),
        ('INTERNET', 'Internet et télécommunications'),
        ('ENTRETIEN', 'Entretien et réparations'),
        ('ASSURANCES', 'Assurances'),
        ('TAXES', 'Taxes et impôts'),
        ('TRANSPORT', 'Transport'),
        ('MARKETING', 'Marketing et publicité'),
        ('FORMATION', 'Formation du personnel'),
        ('AUTRES', 'Autres dépenses'),
    ]

    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        related_name='depenses',
        verbose_name="Établissement"
    )

    numero_depense = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Numéro de dépense"
    )

    categorie = models.CharField(
        max_length=20,
        choices=CATEGORIES_DEPENSE,
        verbose_name="Catégorie"
    )

    date_depense = models.DateField(
        default=timezone.now,
        verbose_name="Date de dépense"
    )

    fournisseur = models.CharField(
        max_length=200,
        verbose_name="Fournisseur"
    )

    description = models.TextField(verbose_name="Description")

    montant = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant"
    )

    mode_paiement = models.CharField(
        max_length=50,
        verbose_name="Mode de paiement"
    )

    numero_piece = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Numéro de pièce justificative"
    )

    piece_justificative = models.FileField(
        upload_to='accounting/depenses/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Pièce justificative"
    )

    STATUT_DEPENSE = [
        ('EN_ATTENTE', 'En attente'),
        ('APPROUVEE', 'Approuvée'),
        ('PAYEE', 'Payée'),
        ('REJETEE', 'Rejetée'),
    ]

    statut = models.CharField(
        max_length=20,
        choices=STATUT_DEPENSE,
        default='EN_ATTENTE',
        verbose_name="Statut"
    )

    saisi_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        related_name='depenses_saisies',
        verbose_name="Saisi par"
    )

    approuve_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='depenses_approuvees',
        verbose_name="Approuvé par"
    )

    date_approbation = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date d'approbation"
    )

    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Notes"
    )

    class Meta:
        db_table = 'accounting_depense'
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"
        ordering = ['-date_depense']

    def __str__(self):
        return f"{self.numero_depense} - {self.fournisseur} - {self.montant}"

    def save(self, *args, **kwargs):
        if not self.numero_depense:
            self.numero_depense = self.generer_numero_depense()
        super().save(*args, **kwargs)

    def generer_numero_depense(self):
        annee = timezone.now().year
        dernier = Depense.objects.filter(
            etablissement=self.etablissement,
            numero_depense__startswith=f"DEP{annee}"
        ).order_by('-numero_depense').first()

        if dernier:
            dernier_num = int(dernier.numero_depense[-6:])
            nouveau_num = dernier_num + 1
        else:
            nouveau_num = 1

        return f"DEP{annee}{nouveau_num:06d}"


class ExerciceComptable(BaseModel):
    """Exercices comptables"""

    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        related_name='exercices_comptables',
        verbose_name="Établissement"
    )

    libelle = models.CharField(
        max_length=100,
        verbose_name="Libellé"
    )

    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")

    est_cloture = models.BooleanField(
        default=False,
        verbose_name="Clôturé"
    )

    date_cloture = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de clôture"
    )

    cloture_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Clôturé par"
    )

    class Meta:
        db_table = 'accounting_exercice_comptable'
        verbose_name = "Exercice comptable"
        verbose_name_plural = "Exercices comptables"
        ordering = ['-date_debut']

    def __str__(self):
        return f"{self.libelle} ({self.date_debut} - {self.date_fin})"


class BudgetPrevisionnel(BaseModel):
    """Budget prévisionnel"""

    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        related_name='budgets',
        verbose_name="Établissement"
    )

    exercice = models.ForeignKey(
        ExerciceComptable,
        on_delete=models.CASCADE,
        related_name='budgets',
        verbose_name="Exercice comptable"
    )

    libelle = models.CharField(
        max_length=200,
        verbose_name="Libellé"
    )

    montant_previsionnel = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Montant prévisionnel"
    )

    montant_realise = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Montant réalisé"
    )

    TYPE_BUDGET = [
        ('RECETTES', 'Recettes'),
        ('DEPENSES', 'Dépenses'),
    ]

    type_budget = models.CharField(
        max_length=20,
        choices=TYPE_BUDGET,
        verbose_name="Type de budget"
    )

    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Notes"
    )

    class Meta:
        db_table = 'accounting_budget_previsionnel'
        verbose_name = "Budget prévisionnel"
        verbose_name_plural = "Budgets prévisionnels"
        ordering = ['exercice', 'type_budget']

    def __str__(self):
        return f"{self.libelle} - {self.exercice}"

    @property
    def taux_realisation(self):
        if self.montant_previsionnel > 0:
            return (self.montant_realise / self.montant_previsionnel) * 100
        return 0

    @property
    def ecart(self):
        return self.montant_realise - self.montant_previsionnel