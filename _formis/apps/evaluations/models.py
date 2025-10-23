#apps/evaluations/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import BaseModel
from decimal import Decimal
import os

class Evaluation(BaseModel):
    """Modèle pour les évaluations créées par les enseignants"""

    TYPE_EVALUATION = (
        ('DEVOIR', 'Devoir'),
        ('COMPOSITION', 'Composition'),
        ('TP', 'Travaux Pratiques'),
        ('PROJET', 'Projet'),
        ('EXAMEN', 'Examen'),
        ('QUIZ', 'Quiz'),
    )

    STATUT = (
        ('BROUILLON', 'Brouillon'),
        ('PROGRAMMEE', 'Programmée'),
        ('EN_COURS', 'En cours'),
        ('TERMINEE', 'Terminée'),
        ('ANNULEE', 'Annulée'),
    )

    # Relations
    enseignant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='evaluations_creees',
        verbose_name="Enseignant"
    )

    matiere = models.ForeignKey(
        'courses.Matiere',
        on_delete=models.CASCADE,
        related_name='evaluations',
        verbose_name="Matière du module"
    )

    # Informations de base
    titre = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(null=True, blank=True, verbose_name="Description")
    type_evaluation = models.CharField(
        max_length=15,
        choices=TYPE_EVALUATION,
        default='DEVOIR',
        verbose_name="Type d'évaluation"
    )

    # Coefficient et notation
    coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        validators=[MinValueValidator(0.1)],
        verbose_name="Coefficient",
        help_text="Doit respecter le coefficient total de la matière"
    )
    note_maximale = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20.0,
        validators=[MinValueValidator(1)],
        verbose_name="Note maximale"
    )

    # Planning
    date_debut = models.DateTimeField(default=timezone.now, verbose_name="Date et heure de début")
    date_fin = models.DateTimeField(default=timezone.now, verbose_name="Date et heure de fin")
    duree_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Durée en minutes"
    )

    # Fichiers
    fichier_evaluation = models.FileField(
        upload_to='evaluations/sujets/%Y/%m/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png']
        )],
        verbose_name="Fichier d'évaluation"
    )

    fichier_correction = models.FileField(
        upload_to='evaluations/corrections/%Y/%m/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'doc', 'docx', 'txt']
        )],
        verbose_name="Fichier de correction"
    )

    # Paramètres
    correction_visible_immediatement = models.BooleanField(
        default=False,
        verbose_name="Correction visible immédiatement après l'évaluation"
    )
    date_publication_correction = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de publication de la correction"
    )

    autorise_retard = models.BooleanField(
        default=False,
        verbose_name="Autoriser les soumissions en retard"
    )
    penalite_retard = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Pénalité de retard (%)"
    )

    # Statut
    statut = models.CharField(
        max_length=15,
        choices=STATUT,
        default='BROUILLON',
        verbose_name="Statut"
    )

    # Classes concernées
    classes = models.ManyToManyField(
        'academic.Classe',
        related_name='evaluations',
        verbose_name="Classes concernées"
    )

    class Meta:
        db_table = 'evaluation_evaluation'
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.titre} - {self.matiere.nom}"

    def clean(self):
        # Vérifier que la date de fin est après la date de début
        if self.date_debut and self.date_fin and self.date_fin <= self.date_debut:
            raise ValidationError("La date de fin doit être postérieure à la date de début.")

        # Vérifier que le coefficient ne dépasse pas celui de la matière
        if self.matiere:
            total_coefficients = Evaluation.objects.filter(
                matiere=self.matiere,
                enseignant=self.enseignant,
                statut__in=['PROGRAMMEE', 'EN_COURS', 'TERMINEE']
            ).exclude(pk=self.pk).aggregate(
                total=models.Sum('coefficient')
            )['total'] or Decimal('0')

            total_avec_cette_eval = total_coefficients + Decimal(str(self.coefficient))
            coef_matiere = Decimal(str(self.matiere.coefficient))

            if total_avec_cette_eval > coef_matiere:
                raise ValidationError(
                    f"La somme des coefficients ({total_avec_cette_eval}) "
                    f"ne peut pas dépasser le coefficient de la matière ({coef_matiere}). "
                    f"Coefficient disponible : {coef_matiere - total_coefficients}"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def coefficient_restant_matiere(self):
        """Calcule le coefficient restant disponible pour cette matière"""
        if not self.matiere:
            return 0

        total_utilise = Evaluation.objects.filter(
            matiere=self.matiere,
            enseignant=self.enseignant,
            statut__in=['PROGRAMMEE', 'EN_COURS', 'TERMINEE']
        ).exclude(pk=self.pk).aggregate(
            total=models.Sum('coefficient')
        )['total'] or Decimal('0')

        return float(Decimal(str(self.matiere.coefficient)) - total_utilise)

    @property
    def est_active(self):
        """Vérifie si l'évaluation est actuellement active"""
        now = timezone.now()
        return self.date_debut <= now <= self.date_fin and self.statut == 'EN_COURS'

    @property
    def est_terminee(self):
        """Vérifie si l'évaluation est terminée"""
        return timezone.now() > self.date_fin or self.statut == 'TERMINEE'

    @property
    def correction_visible(self):
        """Vérifie si la correction est visible"""
        if not self.fichier_correction:
            return False

        if self.correction_visible_immediatement:
            return self.est_terminee

        if self.date_publication_correction:
            return timezone.now() >= self.date_publication_correction

        return False

    @property
    def taux_soumission(self):
        """Calcule le taux de soumission"""
        total_apprenants = sum(classe.apprenants.count() for classe in self.classes.all())
        if total_apprenants == 0:
            return 0
        compositions_soumises = self.compositions.filter(statut__in=['SOUMISE', 'EN_RETARD', 'CORRIGEE']).count()
        return (compositions_soumises / total_apprenants) * 100

    @property
    def taux_correction(self):
        """Calcule le taux de correction"""
        compositions_soumises = self.compositions.filter(statut__in=['SOUMISE', 'EN_RETARD']).count()
        if compositions_soumises == 0:
            return 100 if self.compositions.filter(statut='CORRIGEE').exists() else 0
        compositions_corrigees = self.compositions.filter(statut='CORRIGEE').count()
        return (compositions_corrigees / compositions_soumises) * 100

class Composition(BaseModel):
    """Modèle pour les compositions des apprenants"""

    STATUT = (
        ('EN_COURS', 'En cours'),
        ('SOUMISE', 'Soumise'),
        ('EN_RETARD', 'En retard'),
        ('CORRIGEE', 'Corrigée'),
    )

    # Relations
    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name='compositions',
        verbose_name="Évaluation"
    )

    apprenant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'APPRENANT'},
        related_name='compositions',
        verbose_name="Apprenant"
    )

    # Timing
    date_debut = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de début"
    )
    date_soumission = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de soumission"
    )

    # Fichiers de composition
    fichiers_composition = models.ManyToManyField(
        'FichierComposition',
        blank=True,
        related_name='compositions',
        verbose_name="Fichiers de composition"
    )

    # Notes et correction
    note_obtenue = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Note obtenue"
    )

    commentaire_correction = models.TextField(
        null=True,
        blank=True,
        verbose_name="Commentaire de correction"
    )

    fichier_correction_personnalise = models.FileField(
        upload_to='evaluations/corrections_personnalisees/%Y/%m/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'txt'])],
        verbose_name="Correction personnalisée"
    )

    # Statut
    statut = models.CharField(
        max_length=15,
        choices=STATUT,
        default='EN_COURS',
        verbose_name="Statut"
    )

    # Métadonnées
    corrigee_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='compositions_corrigees',
        verbose_name="Corrigée par"
    )
    date_correction = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de correction"
    )

    class Meta:
        db_table = 'evaluation_composition'
        verbose_name = "Composition"
        verbose_name_plural = "Compositions"
        unique_together = ['evaluation', 'apprenant']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.apprenant.get_full_name()} - {self.evaluation.titre}"

    @property
    def est_en_retard(self):
        """Vérifie si la composition a été soumise en retard"""
        if not self.date_soumission:
            return timezone.now() > self.evaluation.date_fin
        return self.date_soumission > self.evaluation.date_fin

    # @property
    # def peut_soumettre(self):
    #     """Vérifie si l'apprenant peut encore soumettre"""
    #     if self.statut in ['SOUMISE', 'EN_RETARD', 'CORRIGEE']:
    #         return False
    #
    #     now = timezone.now()
    #     if now > self.evaluation.date_fin:
    #         return self.evaluation.autorise_retard
    #
    #     return self.evaluation.est_active

    @property
    def peut_soumettre(self):
        """
        Vérifie si l'apprenant peut encore soumettre
        uniquement en fonction de la durée de l'évaluation.
        """
        now = timezone.now()
        return self.evaluation.date_debut <= now <= self.evaluation.date_fin

    @property
    def note_avec_penalite(self):
        """Calcule la note avec pénalité de retard si applicable"""
        if not self.note_obtenue:
            return None

        if self.est_en_retard and self.evaluation.penalite_retard > 0:
            penalite = (self.evaluation.penalite_retard / 100) * self.note_obtenue
            return max(0, self.note_obtenue - penalite)

        return self.note_obtenue

    def soumettre(self):
        """Marque la composition comme soumise"""
        self.date_soumission = timezone.now()
        if self.est_en_retard:
            self.statut = 'EN_RETARD'
        else:
            self.statut = 'SOUMISE'
        self.save()

class FichierComposition(BaseModel):
    """Modèle pour les fichiers de composition uploadés par les apprenants"""

    nom_original = models.CharField(max_length=255, verbose_name="Nom original")
    fichier = models.FileField(
        upload_to='evaluations/compositions/%Y/%m/',
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png']
        )],
        verbose_name="Fichier"
    )
    taille = models.PositiveIntegerField(verbose_name="Taille (bytes)")
    type_mime = models.CharField(max_length=100, verbose_name="Type MIME")

    # Métadonnées
    uploade_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'APPRENANT'},
        related_name='fichiers_composition',
        verbose_name="Uploadé par"
    )

    class Meta:
        db_table = 'evaluation_fichier_composition'
        verbose_name = "Fichier de composition"
        verbose_name_plural = "Fichiers de composition"
        ordering = ['-created_at']

    def __str__(self):
        return self.nom_original

    def save(self, *args, **kwargs):
        if self.fichier:
            self.taille = self.fichier.size
            self.nom_original = self.fichier.name
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Supprimer le fichier physique
        if self.fichier:
            if os.path.isfile(self.fichier.path):
                os.remove(self.fichier.path)
        super().delete(*args, **kwargs)

class Note(BaseModel):
    """Notes attribuées aux apprenants"""

    # Relations
    apprenant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'APPRENANT'},
        related_name='notes',
        verbose_name="Apprenant"
    )

    matiere = models.ForeignKey(
        'courses.matiere',
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name="Matière"
    )

    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name="Évaluation"
    )

    composition = models.OneToOneField(
        Composition,
        on_delete=models.CASCADE,
        related_name='note',
        null=True,
        blank=True,
        verbose_name="Composition"
    )

    # Note
    valeur = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Valeur"
    )

    note_sur = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20.0,
        verbose_name="Note sur"
    )

    # Métadonnées
    attribuee_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='notes_attribuees',
        verbose_name="Attribuée par"
    )

    date_attribution = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date d'attribution"
    )

    commentaire = models.TextField(
        null=True,
        blank=True,
        verbose_name="Commentaire"
    )

    class Meta:
        db_table = 'evaluation_note'
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        unique_together = ['apprenant', 'evaluation']
        ordering = ['-date_attribution']

    def __str__(self):
        return f"{self.apprenant.get_full_name()} - {self.evaluation.titre}: {self.valeur}/{self.note_sur}"

    @property
    def note_sur_20(self):
        """Convertit la note sur 20"""
        if self.note_sur == 20:
            return self.valeur
        return (self.valeur / self.note_sur) * 20

    @property
    def coefficient_pondere(self):
        """Retourne le coefficient de l'évaluation"""
        return self.evaluation.coefficient
