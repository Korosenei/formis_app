# apps/courses/models.py
import os

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import F, Sum, ExpressionWrapper, IntegerField
from django.urls import reverse
from django.utils import timezone
from apps.core.models import BaseModel


class Module(BaseModel):
    """Module de formation (regroupement optionnel de matières)"""
    niveau = models.ForeignKey(
        'academic.Niveau',
        on_delete=models.CASCADE,
        related_name='modules',
        verbose_name="Niveau"
    )
    nom = models.CharField(max_length=200, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    coordinateur = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='modules_coordonnes',
        verbose_name="Coordinateur"
    )

    actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'courses_module'
        verbose_name = "Module"
        verbose_name_plural = "Modules"
        ordering = ['niveau', 'nom']
        unique_together = ['niveau', 'code']

    def __str__(self):
        return f"{self.nom} ({self.code})"

    @property
    def volume_horaire_total(self):
        """Calcule le volume horaire total des matières du module via SQL"""
        total = self.matieres.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('heures_cours_magistral') + F('heures_travaux_diriges') + F('heures_travaux_pratiques'),
                    output_field=IntegerField()
                )
            )
        )['total']
        return total or 0

    @property
    def credits_ects(self):
        """Calcule les crédits ECTS du module"""
        return self.matieres.aggregate(
            total=models.Sum('credits_ects')
        )['total'] or 0

class Matiere(BaseModel):
    """Matière/Discipline - élément central du système"""
    nom = models.CharField(max_length=200, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code", unique=True)
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    # Relations académiques
    niveau = models.ForeignKey(
        'academic.Niveau',
        on_delete=models.CASCADE,
        related_name='matieres',
        verbose_name="Niveau"
    )

    module = models.ForeignKey(
        Module,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matieres',
        verbose_name="Module (optionnel)"
    )

    # Enseignant responsable
    enseignant_responsable = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='matieres_responsable',
        verbose_name="Enseignant responsable"
    )

    # Volume horaire
    heures_cours_magistral = models.IntegerField(default=0, verbose_name="Heures CM")
    heures_travaux_diriges = models.IntegerField(default=0, verbose_name="Heures TD")
    heures_travaux_pratiques = models.IntegerField(default=0, verbose_name="Heures TP")

    # Coefficient et crédits
    coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        validators=[MinValueValidator(0.5), MaxValueValidator(10)],
        verbose_name="Coefficient"
    )

    credits_ects = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
        verbose_name="Crédits ECTS"
    )

    # Couleur pour l'affichage
    couleur = models.CharField(max_length=7, default="#3498db", verbose_name="Couleur")

    actif = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        db_table = 'courses_matiere'
        verbose_name = "Matière"
        verbose_name_plural = "Matières"
        ordering = ['niveau', 'nom']
        unique_together = ['niveau', 'code']

    def __str__(self):
        if self.niveau:
            return f"{self.nom} - {self.niveau.nom}"
        return self.nom

    @property
    def volume_horaire_total(self):
        return (self.heures_cours_magistral +
                self.heures_travaux_diriges +
                self.heures_travaux_pratiques)

    @property
    def etablissement(self):
        return self.niveau.filiere.etablissement if self.niveau else None

    @property
    def departement(self):
        return self.niveau.filiere.departement if self.niveau else None

class TypeCours(models.TextChoices):
    CM = 'CM', 'Cours magistral'
    TD = 'TD', 'Travaux dirigés'
    TP = 'TP', 'Travaux pratiques'
    EVALUATION = 'EVALUATION', 'Évaluation'
    RATTRAPAGE = 'RATTRAPAGE', 'Rattrapage'

class StatutCours(models.TextChoices):
    PROGRAMME = 'PROGRAMME', 'Programmé'
    EN_COURS = 'EN_COURS', 'En cours'
    TERMINE = 'TERMINE', 'Terminé'
    ANNULE = 'ANNULE', 'Annulé'
    REPORTE = 'REPORTE', 'Reporté'

class Cours(BaseModel):
    """Séance de cours"""
    matiere = models.ForeignKey(
        Matiere,
        on_delete=models.CASCADE,
        related_name='cours',
        verbose_name="Matière"
    )

    classe = models.ForeignKey(
        'academic.Classe',
        on_delete=models.CASCADE,
        related_name='cours',
        verbose_name="Classe"
    )

    enseignant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='cours_enseignes',
        verbose_name="Enseignant"
    )

    periode_academique = models.ForeignKey(
        'academic.PeriodeAcademique',
        on_delete=models.CASCADE,
        related_name='cours',
        verbose_name="Période académique"
    )

    titre = models.CharField(max_length=200, verbose_name="Titre du cours")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    # Type et statut
    type_cours = models.CharField(
        max_length=20,
        choices=TypeCours.choices,
        default=TypeCours.CM,
        verbose_name="Type de cours"
    )

    statut = models.CharField(
        max_length=20,
        choices=StatutCours.choices,
        default=StatutCours.PROGRAMME,
        verbose_name="Statut"
    )

    # Planification
    date_prevue = models.DateField(verbose_name="Date prévue")
    heure_debut_prevue = models.TimeField(verbose_name="Heure de début prévue")
    heure_fin_prevue = models.TimeField(verbose_name="Heure de fin prévue")

    # Réalisation
    date_effective = models.DateField(null=True, blank=True, verbose_name="Date effective")
    heure_debut_effective = models.TimeField(null=True, blank=True)
    heure_fin_effective = models.TimeField(null=True, blank=True)

    # Lieu
    salle = models.ForeignKey(
        'establishments.Salle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cours',
        verbose_name="Salle"
    )

    # Contenu pédagogique
    objectifs = models.TextField(null=True, blank=True, verbose_name="Objectifs")
    contenu = models.TextField(null=True, blank=True, verbose_name="Contenu abordé")

    # Cours en ligne
    cours_en_ligne = models.BooleanField(default=False, verbose_name="Cours en ligne")
    url_streaming = models.URLField(null=True, blank=True, verbose_name="URL streaming")

    # Présence
    presence_prise = models.BooleanField(default=False, verbose_name="Présence prise")

    actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'courses_cours'
        verbose_name = "Cours"
        verbose_name_plural = "Cours"
        ordering = ['-date_prevue', '-heure_debut_prevue']
        indexes = [
            models.Index(fields=['date_prevue', 'classe']),
            models.Index(fields=['enseignant', 'date_prevue']),
        ]

    def __str__(self):
        return f"{self.titre} - {self.classe.nom} ({self.date_prevue})"

    @property
    def duree_prevue(self):
        """Calcule la durée prévue en minutes"""
        if self.heure_debut_prevue and self.heure_fin_prevue:
            debut = timezone.datetime.combine(timezone.now().date(), self.heure_debut_prevue)
            fin = timezone.datetime.combine(timezone.now().date(), self.heure_fin_prevue)
            return int((fin - debut).total_seconds() / 60)
        return 0

class CahierTexte(BaseModel):
    """Cahier de texte pour chaque cours"""
    cours = models.OneToOneField(
        Cours,
        on_delete=models.CASCADE,
        related_name='cahier_texte',
        verbose_name="Cours"
    )

    travail_fait = models.TextField(verbose_name="Travail fait en classe")
    travail_donne = models.TextField(
        null=True,
        blank=True,
        verbose_name="Travail donné aux étudiants"
    )

    date_travail_pour = models.DateField(
        null=True,
        blank=True,
        verbose_name="Travail pour le"
    )

    observations = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observations"
    )

    rempli_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'ENSEIGNANT'},
        verbose_name="Rempli par"
    )

    date_saisie = models.DateTimeField(auto_now_add=True, verbose_name="Date de saisie")
    modifie_le = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        db_table = 'courses_cahier_texte'
        verbose_name = "Cahier de texte"
        verbose_name_plural = "Cahiers de texte"
        ordering = ['-cours__date_prevue']

    def __str__(self):
        return f"Cahier de texte - {self.cours.titre}"

class Ressource(BaseModel):
    """Ressources pédagogiques liées à un cours"""
    cours = models.ForeignKey(
        Cours,
        on_delete=models.CASCADE,
        related_name='ressources',
        verbose_name="Cours"
    )

    titre = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    TYPES_RESSOURCE = [
        ('PDF', 'Document PDF'),
        ('DOC', 'Document Word'),
        ('PPT', 'Présentation PowerPoint'),
        ('VIDEO', 'Vidéo'),
        ('AUDIO', 'Audio'),
        ('IMAGE', 'Image'),
        ('LINK', 'Lien web'),
        ('OTHER', 'Autre'),
    ]

    type_ressource = models.CharField(
        max_length=20,
        choices=TYPES_RESSOURCE,
        verbose_name="Type de ressource"
    )

    # Fichier ou URL
    fichier = models.FileField(
        upload_to='ressources_cours/',
        null=True,
        blank=True,
        verbose_name="Fichier"
    )
    url = models.URLField(null=True, blank=True, verbose_name="URL")

    # Taille du fichier
    taille_fichier = models.BigIntegerField(null=True, blank=True, verbose_name="Taille du fichier")

    # Accessibilité
    obligatoire = models.BooleanField(default=False, verbose_name="Obligatoire")
    telechargeable = models.BooleanField(default=True, verbose_name="Téléchargeable")
    public = models.BooleanField(default=False, verbose_name="Public")

    # Dates de disponibilité
    disponible_a_partir_de = models.DateTimeField(null=True, blank=True, verbose_name="Disponible à partir de")
    disponible_jusqua = models.DateTimeField(null=True, blank=True, verbose_name="Disponible jusqu'à")

    # Statistiques
    nombre_telechargements = models.IntegerField(default=0, verbose_name="Nombre de téléchargements")
    nombre_vues = models.IntegerField(default=0, verbose_name="Nombre de vues")

    class Meta:
        db_table = 'courses_ressource'
        verbose_name = "Ressource"
        verbose_name_plural = "Ressources"
        ordering = ['cours', 'titre']

    def save(self, *args, **kwargs):
        if self.fichier:
            self.taille_fichier = self.fichier.size
        super().save(*args, **kwargs)

    def get_taille_fichier_display(self):
        """Retourne la taille du fichier dans un format lisible"""
        if not self.taille_fichier:
            return "N/A"

        if self.taille_fichier < 1024:
            return f"{self.taille_fichier} B"
        elif self.taille_fichier < 1024 * 1024:
            return f"{self.taille_fichier / 1024:.1f} KB"
        elif self.taille_fichier < 1024 * 1024 * 1024:
            return f"{self.taille_fichier / (1024 * 1024):.1f} MB"
        else:
            return f"{self.taille_fichier / (1024 * 1024 * 1024):.1f} GB"

    @property
    def nom_fichier(self):
        """Retourne uniquement le nom du fichier sans le chemin complet"""
        return os.path.basename(self.fichier.name) if self.fichier else None

    def __str__(self):
        return f"{self.cours.titre} - {self.titre}"

class Presence(BaseModel):
    """Présences aux cours"""
    cours = models.ForeignKey(
        Cours,
        on_delete=models.CASCADE,
        related_name='presences',
        verbose_name="Cours"
    )
    etudiant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'ETUDIANT'},
        verbose_name="Étudiant"
    )

    STATUTS_PRESENCE = [
        ('PRESENT', 'Présent'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Retard'),
        ('EXCUSED', 'Absent excusé'),
        ('JUSTIFIED', 'Absence justifiée'),
    ]

    statut = models.CharField(
        max_length=20,
        choices=STATUTS_PRESENCE,
        default='PRESENT',
        verbose_name="Statut"
    )

    # Heure d'arrivée (pour les retards)
    heure_arrivee = models.TimeField(null=True, blank=True, verbose_name="Heure d'arrivée")

    # Justification d'absence
    motif_absence = models.TextField(null=True, blank=True, verbose_name="Motif d'absence")
    document_justificatif = models.FileField(
        upload_to='presences/justifications/',
        null=True,
        blank=True,
        verbose_name="Document justificatif"
    )

    # Validation
    valide = models.BooleanField(default=False, verbose_name="Validé")
    valide_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='presences_validees',
        verbose_name="Validé par"
    )
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name="Date de validation")
    notes_enseignant = models.TextField(null=True, blank=True, verbose_name="Notes de l'enseignant")

    class Meta:
        db_table = 'courses_presence'
        verbose_name = "Présence"
        verbose_name_plural = "Présences"
        ordering = ['cours', 'etudiant']
        unique_together = ['cours', 'etudiant']

    def __str__(self):
        return f"{self.etudiant.get_full_name()} - {self.cours.titre} ({self.get_statut_display()})"

class EmploiDuTemps(BaseModel):
    """Emploi du temps généré"""
    # Cible de l'emploi du temps
    classe = models.ForeignKey(
        'academic.Classe',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='emplois_du_temps',
        verbose_name="Classe"
    )

    enseignant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='emplois_du_temps',
        verbose_name="Enseignant"
    )

    periode_academique = models.ForeignKey(
        'academic.PeriodeAcademique',
        on_delete=models.CASCADE,
        related_name='emplois_du_temps',
        verbose_name="Période académique"
    )

    nom = models.CharField(max_length=200, verbose_name="Nom")

    # Période de validité
    semaine_debut = models.DateField(verbose_name="Début de semaine")
    semaine_fin = models.DateField(verbose_name="Fin de semaine")

    # Statut
    publie = models.BooleanField(default=False, verbose_name="Publié")
    actuel = models.BooleanField(default=False, verbose_name="Actuel")

    # Créé par
    cree_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emplois_du_temps_crees',
        verbose_name="Créé par"
    )

    class Meta:
        db_table = 'courses_emploi_du_temps'
        verbose_name = "Emploi du temps"
        verbose_name_plural = "Emplois du temps"
        ordering = ['-semaine_debut']

    def __str__(self):
        if self.classe:
            return f"EDT {self.classe.nom} - Semaine du {self.semaine_debut}"
        return f"EDT {self.enseignant.get_full_name()} - Semaine du {self.semaine_debut}"

    def save(self, *args, **kwargs):
        if self.actuel:
            # Un seul emploi du temps actuel par cible
            if self.classe:
                EmploiDuTemps.objects.filter(
                    classe=self.classe, actuel=True
                ).exclude(id=self.id).update(actuel=False)
            elif self.enseignant:
                EmploiDuTemps.objects.filter(
                    enseignant=self.enseignant, actuel=True
                ).exclude(id=self.id).update(actuel=False)
        super().save(*args, **kwargs)

class CreneauEmploiDuTemps(BaseModel):
    """Créneau dans un emploi du temps"""
    emploi_du_temps = models.ForeignKey(
        EmploiDuTemps,
        on_delete=models.CASCADE,
        related_name='creneaux',
        verbose_name="Emploi du temps"
    )

    cours = models.ForeignKey(
        Cours,
        on_delete=models.CASCADE,
        related_name='creneaux_edt',
        verbose_name="Cours"
    )

    JOURS = [
        (0, 'Lundi'),
        (1, 'Mardi'),
        (2, 'Mercredi'),
        (3, 'Jeudi'),
        (4, 'Vendredi'),
        (5, 'Samedi'),
    ]

    jour_semaine = models.IntegerField(choices=JOURS, verbose_name="Jour")
    heure_debut = models.TimeField(verbose_name="Heure de début")
    heure_fin = models.TimeField(verbose_name="Heure de fin")

    class Meta:
        db_table = 'courses_creneau_emploi_du_temps'
        verbose_name = "Créneau emploi du temps"
        verbose_name_plural = "Créneaux emploi du temps"
        ordering = ['jour_semaine', 'heure_debut']

    def __str__(self):
        return f"{self.get_jour_semaine_display()} {self.heure_debut}-{self.heure_fin}"