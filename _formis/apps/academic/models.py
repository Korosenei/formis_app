# apps/academic/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel

class Departement(BaseModel):
    """Départements (pour universités et instituts)"""
    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        verbose_name="Établissement"
    )
    nom = models.CharField(max_length=200, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    # Chef de département
    chef = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'CHEF_DEPARTEMENT'},
        related_name='departements_diriges',
        verbose_name="Chef de département"
    )

    # Contact
    telephone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Téléphone")
    email = models.EmailField(null=True, blank=True, verbose_name="Email")
    bureau = models.CharField(max_length=100, null=True, blank=True, verbose_name="Bureau")

    est_actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'academique_departement'
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        ordering = ['nom']
        unique_together = ['etablissement', 'code']

    def __str__(self):
        return f"{self.nom} ({self.etablissement.nom})"

class Filiere(BaseModel):
    """Filières de formation"""
    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        verbose_name="Établissement"
    )
    departement = models.ForeignKey(
        Departement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="filieres",
        verbose_name="Département"
    )

    nom = models.CharField(max_length=200, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    # Durée de formation
    duree_annees = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Durée (années)"
    )

    # Diplôme délivré
    nom_diplome = models.CharField(max_length=200, verbose_name="Nom du diplôme")

    TYPES_FILIERE = [
        ('GENERAL', 'Enseignement général'),
        ('TECHNIQUE', 'Enseignement technique'),
        ('PROFESSIONNEL', 'Formation professionnelle'),
        ('UNIVERSITAIRE', 'Enseignement universitaire'),
        ('CONTINUE', 'Formation continue'),
    ]

    type_filiere = models.CharField(
        max_length=20,
        choices=TYPES_FILIERE,
        verbose_name="Type de filière"
    )

    # Prérequis
    prerequis = models.TextField(null=True, blank=True, verbose_name="Prérequis")

    # Frais de scolarité
    frais_scolarite = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Frais de scolarité"
    )

    # Capacité d'accueil
    capacite_maximale = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Capacité maximale (pour toute la filière)"
    )

    est_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        db_table = 'academique_filiere'
        verbose_name = "Filière"
        verbose_name_plural = "Filières"
        ordering = ['nom']
        unique_together = ['etablissement', 'code']

    def __str__(self):
        return self.nom

class Niveau(BaseModel):
    """Niveaux de formation"""
    filiere = models.ForeignKey(
        Filiere,
        on_delete=models.CASCADE,
        related_name='niveaux',
        verbose_name="Filière"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code")

    # Ordre du niveau dans la filière (1ère année, 2ème année, etc.)
    ordre = models.IntegerField(verbose_name="Ordre")

    description = models.TextField(null=True, blank=True, verbose_name="Description")

    # Frais spécifiques à ce niveau
    frais_scolarite = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Frais de scolarité (si différent de la filière)"
    )

    est_actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'academique_niveau'
        verbose_name = "Niveau"
        verbose_name_plural = "Niveaux"
        ordering = ['filiere', 'ordre']
        unique_together = ['filiere', 'code']

    def __str__(self):
        return f"{self.filiere.nom} - {self.nom}"

class Classe(BaseModel):
    """Classes (groupes d'étudiants)"""
    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        verbose_name="Établissement"
    )
    niveau = models.ForeignKey(
        Niveau,
        on_delete=models.CASCADE,
        verbose_name="Niveau",
        related_name='classes'
    )
    annee_academique = models.ForeignKey(
        'establishments.AnneeAcademique',
        on_delete=models.CASCADE,
        verbose_name="Année académique"
    )

    nom = models.CharField(max_length=100, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code")

    # Professeur principal
    professeur_principal = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='classes_principales',
        verbose_name="Professeur principal"
    )

    # Salle principale
    salle_principale = models.ForeignKey(
        'establishments.Salle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Salle principale"
    )

    # Capacité et effectif
    capacite_maximale = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Capacité maximale (par classe)"
    )
    effectif_actuel = models.IntegerField(default=0, verbose_name="Effectif actuel")

    est_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        db_table = 'academique_classe'
        verbose_name = "Classe"
        verbose_name_plural = "Classes"
        ordering = ['nom']
        unique_together = ['etablissement', 'annee_academique', 'code']

    def __str__(self):
        return f"{self.nom} - {self.niveau.filiere.nom} ({self.annee_academique.nom})"

    def get_places_disponibles(self):
        """Retourne le nombre de places disponibles dans la classe"""
        if self.capacite_maximale is None:
            return None  # illimité
        return max(0, self.capacite_maximale - (self.effectif_actuel or 0))

    def est_pleine(self):
        """Vérifie si la classe est pleine"""
        return self.capacite_maximale is not None and self.effectif_actuel >= self.capacite_maximale

class PeriodeAcademique(BaseModel):
    """Périodes académiques (semestres, trimestres, etc.)"""
    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        verbose_name="Établissement"
    )
    annee_academique = models.ForeignKey(
        'establishments.AnneeAcademique',
        on_delete=models.CASCADE,
        verbose_name="Année académique"
    )

    nom = models.CharField(max_length=100, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code")

    TYPES_PERIODE = [
        ('SEMESTRE', 'Semestre'),
        ('TRIMESTRE', 'Trimestre'),
        ('QUADRIMESTRE', 'Quadrimestre'),
    ]

    type_periode = models.CharField(
        max_length=20,
        choices=TYPES_PERIODE,
        verbose_name="Type de période"
    )

    # Ordre dans l'année (1er semestre, 2ème semestre, etc.)
    ordre = models.IntegerField(verbose_name="Ordre")

    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")

    # Dates importantes
    date_limite_inscription = models.DateField(null=True, blank=True, verbose_name="Limite d'inscription")
    date_debut_examens = models.DateField(null=True, blank=True, verbose_name="Début des examens")
    date_fin_examens = models.DateField(null=True, blank=True, verbose_name="Fin des examens")
    date_publication_resultats = models.DateField(null=True, blank=True, verbose_name="Publication des résultats")

    est_courante = models.BooleanField(default=False, verbose_name="Période courante")
    est_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        db_table = 'academique_periode'
        verbose_name = "Période académique"
        verbose_name_plural = "Périodes académiques"
        ordering = ['annee_academique', 'ordre']
        unique_together = ['etablissement', 'annee_academique', 'code']

    def save(self, *args, **kwargs):
        if self.est_courante:
            # S'assurer qu'il n'y a qu'une seule période courante par établissement
            PeriodeAcademique.objects.filter(
                etablissement=self.etablissement,
                est_courante=True
            ).exclude(id=self.id).update(est_courante=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nom} - {self.annee_academique.nom}"

class Programme(BaseModel):
    """Programme/Curriculum d'une filière"""
    filiere = models.OneToOneField(
        Filiere,
        on_delete=models.CASCADE,
        related_name='programme',
        verbose_name="Filière"
    )

    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(verbose_name="Description")

    # Objectifs pédagogiques
    objectifs = models.TextField(verbose_name="Objectifs pédagogiques")

    # Compétences à acquérir
    competences = models.TextField(verbose_name="Compétences à acquérir")

    # Débouchés
    debouches = models.TextField(
        null=True,
        blank=True,
        verbose_name="Débouchés professionnels"
    )

    # Nombre total de crédits requis
    credits_totaux = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Total des crédits"
    )

    # Date de dernière révision
    date_derniere_revision = models.DateField(verbose_name="Dernière révision")

    # Validé par
    approuve_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Approuvé par"
    )
    date_approbation = models.DateField(null=True, blank=True, verbose_name="Date d'approbation")

    est_actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'academique_programme'
        verbose_name = "Programme"
        verbose_name_plural = "Programmes"

    def __str__(self):
        return f"Programme {self.filiere.nom}"
