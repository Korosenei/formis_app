# apps/courses/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.utils import timezone
from apps.core.models import BaseModel

class Module(BaseModel):
    """Modules de formation (UE - Unités d'Enseignement)"""
    niveau = models.ForeignKey(
        'academic.Niveau',
        on_delete=models.CASCADE,
        related_name='modules',
        verbose_name="Niveau"
    )

    nom = models.CharField(max_length=200, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    # Prérequis
    prerequis = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        verbose_name="Prérequis"
    )

    # Responsable du module
    coordinateur = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='modules_coordonnes',
        verbose_name="Coordinateur"
    )

    # Volume horaire total et crédits
    volume_horaire_total = models.IntegerField(default=0, verbose_name="Volume horaire total")
    credits_ects = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Crédits ECTS"
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

    def get_absolute_url(self):
        return reverse('courses:module_detail', kwargs={'pk': self.pk})

    @property
    def departement(self):
        """Récupère le département via le niveau"""
        return self.niveau.filiere.departement if self.niveau and self.niveau.filiere else None

    @property
    def filiere(self):
        """Récupère la filière via le niveau"""
        return self.niveau.filiere if self.niveau else None

    @property
    def structure_academique(self):
        """Récupère la structure académique (semestre/trimestre)"""
        return self.niveau.structure_academique if self.niveau else None

class Matiere(BaseModel):
    """Matières/Disciplines"""
    nom = models.CharField(max_length=200, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code", unique=True)
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    # Modules auxquels cette matière appartient
    modules = models.ManyToManyField(
        Module,
        through='MatiereModule',
        blank=True,
        verbose_name="Modules"
    )

    # Couleur pour l'affichage dans les emplois du temps
    couleur = models.CharField(max_length=7, default="#3498db", verbose_name="Couleur")

    actif = models.BooleanField(default=True, verbose_name="Active")

    # Volume horaire par défaut
    heures_theorie = models.IntegerField(default=0, verbose_name="Heures de théorie")
    heures_pratique = models.IntegerField(default=0, verbose_name="Heures de pratique")
    heures_td = models.IntegerField(default=0, verbose_name="Heures de TD")

    # Coefficient de la matière
    coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        verbose_name="Coefficient"
    )

    class Meta:
        db_table = 'courses_matiere'
        verbose_name = "Matière"
        verbose_name_plural = "Matières"
        ordering = ['nom']

    def __str__(self):
        return self.nom

    def get_absolute_url(self):
        return reverse('courses:matiere_detail', kwargs={'pk': self.pk})

    @property
    def volume_horaire_total(self):
        return self.heures_theorie + self.heures_pratique + self.heures_td

class MatiereModule(BaseModel):
    """Table de liaison entre Matière et Module avec informations spécifiques"""
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)

    # Volume horaire spécifique pour ce module
    heures_theorie = models.IntegerField(default=0, verbose_name="Heures de théorie")
    heures_pratique = models.IntegerField(default=0, verbose_name="Heures de pratique")
    heures_td = models.IntegerField(default=0, verbose_name="Heures de TD")

    # Coefficient spécifique dans ce module
    coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        verbose_name="Coefficient dans le module"
    )

    # Enseignant responsable pour cette matière dans ce module
    enseignant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'ENSEIGNANT'},
        related_name='matieres_modules_enseignees',
        verbose_name="Enseignant"
    )

    class Meta:
        db_table = 'courses_matiere_module'
        unique_together = ['matiere', 'module']
        verbose_name = "Matière du module"
        verbose_name_plural = "Matières des modules"

    def __str__(self):
        return f"{self.matiere.nom} dans {self.module.nom}"

    @property
    def volume_horaire_total(self):
        return self.heures_theorie + self.heures_pratique + self.heures_td

class StatutCours(models.TextChoices):
    PROGRAMME = 'PROGRAMME', 'Programmé'
    EN_COURS = 'EN_COURS', 'En cours'
    TERMINE = 'TERMINE', 'Terminé'
    ANNULE = 'ANNULE', 'Annulé'
    REPORTE = 'REPORTE', 'Reporté'

class TypeCours(models.TextChoices):
    COURS = 'COURS', 'Cours magistral'
    TD = 'TD', 'Travaux dirigés'
    TP = 'TP', 'Travaux pratiques'
    EVALUATION = 'EVALUATION', 'Évaluation'
    RATTRAPAGE = 'RATTRAPAGE', 'Rattrapage'

class Cours(BaseModel):
    """Cours/Séances - Unifié"""
    classe = models.ForeignKey(
        'academic.Classe',
        on_delete=models.CASCADE,
        verbose_name="Classe"
    )
    matiere_module = models.ForeignKey(
        MatiereModule,
        on_delete=models.CASCADE,
        verbose_name="Matière/Module"
    )
    enseignant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'ENSEIGNANT'},
        verbose_name="Enseignant"
    )
    periode_academique = models.ForeignKey(
        'academic.PeriodeAcademique',
        on_delete=models.CASCADE,
        verbose_name="Période académique"
    )

    titre = models.CharField(max_length=200, verbose_name="Titre du cours")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    # Type et statut
    type_cours = models.CharField(
        max_length=20,
        choices=TypeCours.choices,
        default=TypeCours.COURS,
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

    # Réalisation effective
    date_effective = models.DateField(null=True, blank=True, verbose_name="Date effective")
    heure_debut_effective = models.TimeField(null=True, blank=True, verbose_name="Heure de début effective")
    heure_fin_effective = models.TimeField(null=True, blank=True, verbose_name="Heure de fin effective")

    # Lieu
    salle = models.ForeignKey(
        'establishments.Salle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Salle"
    )

    # Objectifs et contenu
    objectifs = models.TextField(null=True, blank=True, verbose_name="Objectifs")
    contenu = models.TextField(null=True, blank=True, verbose_name="Contenu abordé")
    prerequis = models.TextField(null=True, blank=True, verbose_name="Prérequis")

    # Support cours en ligne
    cours_en_ligne = models.BooleanField(default=False, verbose_name="Cours en ligne")
    url_streaming = models.URLField(null=True, blank=True, verbose_name="URL de streaming")
    streaming_actif = models.BooleanField(default=False, verbose_name="Streaming actif")

    # Ressources utilisées
    ressources_utilisees = models.TextField(null=True, blank=True, verbose_name="Ressources utilisées")

    # Observations
    notes_enseignant = models.TextField(null=True, blank=True, verbose_name="Notes de l'enseignant")
    retours_etudiants = models.TextField(null=True, blank=True, verbose_name="Retours des étudiants")

    # Présence
    presence_prise = models.BooleanField(default=False, verbose_name="Présence prise")
    date_prise_presence = models.DateTimeField(null=True, blank=True, verbose_name="Date de prise de présence")

    actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'courses_cours'
        verbose_name = "Cours"
        verbose_name_plural = "Cours"
        ordering = ['-date_prevue', '-heure_debut_prevue']

    def __str__(self):
        return f"{self.titre} - {self.classe.nom} ({self.date_prevue})"

    def get_absolute_url(self):
        return reverse('courses:cours_detail', kwargs={'pk': self.pk})

    @property
    def matiere(self):
        return self.matiere_module.matiere

    @property
    def module(self):
        return self.matiere_module.module

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
    """Emplois du temps"""
    classe = models.ForeignKey(
        'academic.Classe',
        on_delete=models.CASCADE,
        verbose_name="Classe"
    )
    periode_academique = models.ForeignKey(
        'academic.PeriodeAcademique',
        on_delete=models.CASCADE,
        verbose_name="Période académique"
    )

    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    # Dates de validité
    valide_a_partir_du = models.DateField(verbose_name="Valide à partir du")
    valide_jusqua = models.DateField(verbose_name="Valide jusqu'au")

    # Statut
    publie = models.BooleanField(default=False, verbose_name="Publié")
    actuel = models.BooleanField(default=False, verbose_name="Emploi du temps actuel")

    # Créé par
    cree_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Créé par"
    )

    class Meta:
        db_table = 'courses_emploi_du_temps'
        verbose_name = "Emploi du temps"
        verbose_name_plural = "Emplois du temps"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.actuel:
            # S'assurer qu'il n'y a qu'un seul emploi du temps actuel par classe
            EmploiDuTemps.objects.filter(
                classe=self.classe,
                actuel=True
            ).exclude(id=self.id).update(actuel=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Emploi du temps {self.classe.nom} - {self.nom}"

class CreneauHoraire(BaseModel):
    """Créneaux horaires de l'emploi du temps"""
    emploi_du_temps = models.ForeignKey(
        EmploiDuTemps,
        on_delete=models.CASCADE,
        related_name='creneaux',
        verbose_name="Emploi du temps"
    )

    JOURS_SEMAINE = [
        ('LUNDI', 'Lundi'),
        ('MARDI', 'Mardi'),
        ('MERCREDI', 'Mercredi'),
        ('JEUDI', 'Jeudi'),
        ('VENDREDI', 'Vendredi'),
        ('SAMEDI', 'Samedi'),
    ]

    jour = models.CharField(max_length=10, choices=JOURS_SEMAINE, verbose_name="Jour")
    heure_debut = models.TimeField(verbose_name="Heure de début")
    heure_fin = models.TimeField(verbose_name="Heure de fin")

    # Matière et enseignant
    matiere_module = models.ForeignKey(
        MatiereModule,
        on_delete=models.CASCADE,
        verbose_name="Matière/Module"
    )
    enseignant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'ENSEIGNANT'},
        verbose_name="Enseignant"
    )

    # Salle
    salle = models.ForeignKey(
        'establishments.Salle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Salle"
    )

    # Type de cours
    type_cours = models.CharField(
        max_length=20,
        choices=TypeCours.choices,
        default=TypeCours.COURS,
        verbose_name="Type de cours"
    )

    # Récurrence
    recurrent = models.BooleanField(default=True, verbose_name="Récurrent")

    # Dates d'exception
    dates_exception = models.TextField(
        null=True,
        blank=True,
        verbose_name="Dates d'exception",
        help_text="Dates où ce créneau n'a pas lieu (format: YYYY-MM-DD, séparées par des virgules)"
    )

    class Meta:
        db_table = 'courses_creneau_horaire'
        verbose_name = "Créneau horaire"
        verbose_name_plural = "Créneaux horaires"
        ordering = ['jour', 'heure_debut']
        unique_together = ['emploi_du_temps', 'jour', 'heure_debut', 'heure_fin']

    def __str__(self):
        return f"{self.jour} {self.heure_debut}-{self.heure_fin} : {self.matiere_module.matiere.nom}"

    @property
    def matiere(self):
        return self.matiere_module.matiere

    @property
    def module(self):
        return self.matiere_module.module