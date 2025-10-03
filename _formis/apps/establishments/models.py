# apps/establishments/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel
from apps.accounts.models import Utilisateur
import uuid

class Localite(BaseModel):
    """Localités (Ville, commune, etc.)"""
    nom = models.CharField(max_length=100, verbose_name="Nom")
    region = models.CharField(max_length=100, null=True, blank=True, verbose_name="Région")
    pays = models.CharField(max_length=100, default="Burkina Faso", verbose_name="Pays")
    code_postal = models.CharField(max_length=10, null=True, blank=True, verbose_name="Code postal")

    class Meta:
        db_table = 'establishments_localite'
        verbose_name = "Localité"
        verbose_name_plural = "Localités"
        ordering = ['nom']

    def __str__(self):
        return self.nom

class TypeEtablissement(BaseModel):
    """Types d'établissements"""
    nom = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(null=True, blank=True, verbose_name="Description")
    code = models.CharField(max_length=10, unique=True, verbose_name="Code")

    structure_academique_defaut = models.CharField(
        max_length=20,
        choices=[
            ('SEMESTRE', 'Semestre'),
            ('TRIMESTRE', 'Trimestre'),
            ('QUADRIMESTRE', 'Quadrimestre'),
        ],
        default='SEMESTRE',
        verbose_name="Structure académique par défaut"
    )

    # Icône pour l'affichage
    icone = models.CharField(
        max_length=50,
        default='fas fa-building',
        verbose_name="Icône FontAwesome"
    )

    actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'establishments_type_etablissement'
        verbose_name = "Type d'établissement"
        verbose_name_plural = "Types d'établissements"
        ordering = ['nom']

    def __str__(self):
        return self.nom

class Etablissement(BaseModel):
    """Établissements de formation"""
    nom = models.CharField(max_length=200, verbose_name="Nom")
    sigle = models.CharField(max_length=20, null=True, blank=True, verbose_name="Sigle")
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")

    type_etablissement = models.ForeignKey(
        TypeEtablissement,
        on_delete=models.CASCADE,
        verbose_name="Type d'établissement"
    )
    localite = models.ForeignKey(
        Localite,
        on_delete=models.CASCADE,
        verbose_name="Localité"
    )

    adresse = models.TextField(verbose_name="Adresse")
    telephone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Téléphone")
    email = models.EmailField(null=True, blank=True, verbose_name="Email")
    site_web = models.URLField(null=True, blank=True, verbose_name="Site web")

    nom_directeur = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nom du directeur")
    numero_enregistrement = models.CharField(max_length=50, null=True, blank=True, verbose_name="Numéro d'enregistrement")
    date_creation = models.DateField(null=True, blank=True, verbose_name="Date de création")

    logo = models.ImageField(upload_to='etablissements/logos/', null=True, blank=True, verbose_name="Logo")
    image_couverture = models.ImageField(upload_to='etablissements/couvertures/', null=True, blank=True,
                                         verbose_name="Image de couverture")

    description = models.TextField(null=True, blank=True, verbose_name="Description")
    mission = models.TextField(null=True, blank=True, verbose_name="Mission")
    vision = models.TextField(null=True, blank=True, verbose_name="Vision")

    actif = models.BooleanField(default=True, verbose_name="Actif")
    public = models.BooleanField(default=True, verbose_name="Visible au public")

    capacite_totale = models.IntegerField(default=0, verbose_name="Capacité totale")
    etudiants_actuels = models.IntegerField(default=0, verbose_name="Étudiants actuels")

    class Meta:
        db_table = 'establishments_etablissement'
        verbose_name = "Établissement"
        verbose_name_plural = "Établissements"
        ordering = ['nom']

    def __str__(self):
        return self.nom

    def taux_occupation(self):
        if self.capacite_totale > 0:
            return (self.etudiants_actuels / self.capacite_totale) * 100
        return 0

    def mise_a_jour_nombre_etudiants(self):
        self.etudiants_actuels = Utilisateur.objects.filter(
            etablissement=self,
            role='APPRENANT',
            is_active=True
        ).count()
        self.save(update_fields=['etudiants_actuels'])

class AnneeAcademique(BaseModel):
    """Années académiques"""
    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.CASCADE,
        verbose_name="Établissement"
    )
    nom = models.CharField(max_length=20, verbose_name="Nom")  # Ex: "2024-2025"
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")

    # Dates importantes
    debut_inscriptions = models.DateField(null=True, blank=True, verbose_name="Début des inscriptions")
    fin_inscriptions = models.DateField(null=True, blank=True, verbose_name="Fin des inscriptions")
    debut_cours = models.DateField(null=True, blank=True, verbose_name="Début des cours")
    fin_cours = models.DateField(null=True, blank=True, verbose_name="Fin des cours")

    # Périodes d'examens
    debut_examens_premier_semestre = models.DateField(null=True, blank=True, verbose_name="Début examens 1er semestre")
    fin_examens_premier_semestre = models.DateField(null=True, blank=True, verbose_name="Fin examens 1er semestre")
    debut_examens_second_semestre = models.DateField(null=True, blank=True, verbose_name="Début examens 2nd semestre")
    fin_examens_second_semestre = models.DateField(null=True, blank=True, verbose_name="Fin examens 2nd semestre")

    # Vacances
    debut_vacances_hiver = models.DateField(null=True, blank=True, verbose_name="Début vacances hiver")
    fin_vacances_hiver = models.DateField(null=True, blank=True, verbose_name="Fin vacances hiver")
    debut_vacances_ete = models.DateField(null=True, blank=True, verbose_name="Début vacances été")
    fin_vacances_ete = models.DateField(null=True, blank=True, verbose_name="Fin vacances été")

    est_courante = models.BooleanField(default=False, verbose_name="Année courante")
    est_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        db_table = 'establishments_annee_academique'
        verbose_name = "Année académique"
        verbose_name_plural = "Années académiques"
        ordering = ['-date_debut']
        unique_together = ['etablissement', 'nom']

    def save(self, *args, **kwargs):
        if self.est_courante:
            # S'assurer qu'il n'y a qu'une seule année courante par établissement
            AnneeAcademique.objects.filter(
                etablissement=self.etablissement,
                est_courante=True
            ).exclude(id=self.id).update(est_courante=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.etablissement.nom} - {self.nom}"

class BaremeNotation(BaseModel):
    """Barème de notation"""
    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.CASCADE,
        verbose_name="Établissement"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    note_minimale = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Note minimale"
    )
    note_maximale = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20,
        verbose_name="Note maximale"
    )
    note_passage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10,
        verbose_name="Note de passage"
    )

    # Échelle de grades
    est_defaut = models.BooleanField(default=False, verbose_name="Par défaut")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    class Meta:
        db_table = 'establishments_bareme_notation'
        verbose_name = "Barème de notation"
        verbose_name_plural = "Barèmes de notation"
        ordering = ['etablissement', 'nom']

    def save(self, *args, **kwargs):
        if self.est_defaut:
            # S'assurer qu'il n'y a qu'un seul barème par défaut par établissement
            BaremeNotation.objects.filter(
                etablissement=self.etablissement,
                est_defaut=True
            ).exclude(id=self.id).update(est_defaut=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nom} ({self.note_minimale}-{self.note_maximale})"

class NiveauNote(BaseModel):
    """Niveaux de notes (Excellent, Bien, Assez bien, etc.)"""
    bareme_notation = models.ForeignKey(
        BaremeNotation,
        on_delete=models.CASCADE,
        related_name='niveaux_notes',
        verbose_name="Barème"
    )
    nom = models.CharField(max_length=50, verbose_name="Nom")
    note_minimale = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Note minimale")
    note_maximale = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Note maximale")
    couleur = models.CharField(max_length=7, default="#000000", verbose_name="Couleur")  # Code couleur hex
    description = models.CharField(max_length=200, null=True, blank=True, verbose_name="Description")

    # Points pour le GPA/moyenne pondérée
    points_gpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0,
        verbose_name="Points GPA"
    )

    class Meta:
        db_table = 'establishments_niveau_note'
        verbose_name = "Niveau de note"
        verbose_name_plural = "Niveaux de notes"
        ordering = ['-note_minimale']

    def __str__(self):
        return f"{self.nom} ({self.note_minimale}-{self.note_maximale})"

class ParametresEtablissement(BaseModel):
    """Paramètres spécifiques à un établissement"""
    etablissement = models.OneToOneField(
        Etablissement,
        on_delete=models.CASCADE,
        related_name='parametres',
        verbose_name="Établissement"
    )

    # Structure académique
    structure_academique = models.CharField(
        max_length=20,
        choices=[
            ('SEMESTRE', 'Semestre'),
            ('TRIMESTRE', 'Trimestre'),
            ('QUADRIMESTRE', 'Quadrimestre'),
        ],
        default='SEMESTRE',
        verbose_name="Structure académique"
    )

    # Paramètres de notation
    bareme_notation_defaut = models.ForeignKey(
        BaremeNotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Barème par défaut"
    )

    # Paramètres d'inscription
    frais_dossier_requis = models.BooleanField(default=False, verbose_name="Frais de dossier requis")
    montant_frais_dossier = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Montant des frais de dossier"
    )

    # Dates limites d'inscription
    date_limite_inscription_anticipée = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date limite inscription anticipée"
    )
    date_limite_inscription_normale = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date limite inscription normale"
    )
    date_limite_inscription_tardive = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date limite inscription tardive"
    )

    # Paramètres de paiement
    paiement_echelonne_autorise = models.BooleanField(default=True, verbose_name="Paiement échelonné autorisé")
    nombre_maximum_tranches = models.IntegerField(default=3, verbose_name="Nombre maximum de tranches")
    frais_echelonnement = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Frais d'échelonnement"
    )
    taux_penalite_retard = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Taux de pénalité de retard (%)"
    )

    # Paramètres de présence
    taux_presence_minimum = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=75.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Taux de présence minimum (%)"
    )

    # Paramètres de notation
    points_bonus_autorises = models.BooleanField(default=False, verbose_name="Points bonus autorisés")
    points_bonus_maximum = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Points bonus maximum"
    )

    # Paramètres de communication
    notifications_sms = models.BooleanField(default=False, verbose_name="Notifications SMS")
    notifications_email = models.BooleanField(default=True, verbose_name="Notifications email")

    # Paramètres de sécurité
    jours_avant_reset_mot_de_passe = models.IntegerField(
        default=90,
        verbose_name="Jours avant reset mot de passe obligatoire"
    )
    tentatives_connexion_max = models.IntegerField(default=5, verbose_name="Tentatives de connexion max")

    # Paramètres d'évaluation
    examens_rattrapage_autorises = models.BooleanField(default=True, verbose_name="Examens de rattrapage autorisés")
    frais_examen_rattrapage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Frais d'examen de rattrapage"
    )

    # Logo et couleurs personnalisées
    couleur_primaire = models.CharField(max_length=7, default="#007bff", verbose_name="Couleur primaire")
    couleur_secondaire = models.CharField(max_length=7, default="#6c757d", verbose_name="Couleur secondaire")

    class Meta:
        db_table = 'establishments_parametres'
        verbose_name = "Paramètres d'établissement"
        verbose_name_plural = "Paramètres d'établissements"

    def __str__(self):
        return f"Paramètres de {self.etablissement.nom}"

class Salle(BaseModel):
    """Salles de classe et autres espaces"""
    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.CASCADE,
        verbose_name="Établissement"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code")

    TYPES_SALLE = [
        ('SALLE_CLASSE', 'Salle de classe'),
        ('LABORATOIRE', 'Laboratoire'),
        ('BIBLIOTHEQUE', 'Bibliothèque'),
        ('AMPHITHEATRE', 'Amphithéâtre'),
        ('SALLE_INFORMATIQUE', 'Salle informatique'),
        ('SALLE_CONFERENCE', 'Salle de conférence'),
        ('SALLE_SPORT', 'Salle de sport'),
        ('CAFETERIA', 'Cafétéria'),
        ('BUREAU', 'Bureau'),
        ('STOCKAGE', 'Stockage'),
        ('AUTRE', 'Autre'),
    ]

    type_salle = models.CharField(
        max_length=20,
        choices=TYPES_SALLE,
        default='SALLE_CLASSE',
        verbose_name="Type de salle"
    )

    capacite = models.IntegerField(verbose_name="Capacité")
    etage = models.CharField(max_length=20, null=True, blank=True, verbose_name="Étage")
    batiment = models.CharField(max_length=100, null=True, blank=True, verbose_name="Bâtiment")

    # Dimensions
    longueur = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Longueur (m)"
    )
    largeur = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Largeur (m)"
    )

    # Équipements
    projecteur = models.BooleanField(default=False, verbose_name="Projecteur")
    ordinateur = models.BooleanField(default=False, verbose_name="Ordinateur")
    climatisation = models.BooleanField(default=False, verbose_name="Climatisation")
    wifi = models.BooleanField(default=False, verbose_name="WiFi")
    tableau_blanc = models.BooleanField(default=True, verbose_name="Tableau blanc")
    systeme_audio = models.BooleanField(default=False, verbose_name="Système audio")

    # État
    accessible_pmr = models.BooleanField(default=True, verbose_name="Accessible PMR")
    etat = models.CharField(
        max_length=20,
        choices=[
            ('EXCELLENT', 'Excellent'),
            ('BON', 'Bon'),
            ('CORRECT', 'Correct'),
            ('MAUVAIS', 'Mauvais'),
            ('MAINTENANCE', 'En maintenance'),
        ],
        default='BON',
        verbose_name="État"
    )

    description = models.TextField(null=True, blank=True, verbose_name="Description")
    notes = models.TextField(null=True, blank=True, verbose_name="Notes")
    est_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        db_table = 'establishments_salle'
        verbose_name = "Salle"
        verbose_name_plural = "Salles"
        ordering = ['batiment', 'etage', 'nom']
        unique_together = ['etablissement', 'code']

    @property
    def surface(self):
        """Calcule la surface de la salle"""
        if self.longueur and self.largeur:
            return self.longueur * self.largeur
        return None

    def get_liste_equipements(self):
        """Retourne la liste des équipements disponibles"""
        equipements = []
        if self.projecteur:
            equipements.append("Projecteur")
        if self.ordinateur:
            equipements.append("Ordinateur")
        if self.climatisation:
            equipements.append("Climatisation")
        if self.wifi:
            equipements.append("WiFi")
        if self.tableau_blanc:
            equipements.append("Tableau blanc")
        if self.systeme_audio:
            equipements.append("Système audio")
        return equipements

    def __str__(self):
        return f"{self.nom} ({self.etablissement.nom})"

class JourFerie(BaseModel):
    """Jours fériés et vacances"""
    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.CASCADE,
        verbose_name="Établissement"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")

    TYPES_JOUR_FERIE = [
        ('PUBLIC', 'Jour férié public'),
        ('RELIGIEUX', 'Fête religieuse'),
        ('SCOLAIRE', 'Vacances scolaires'),
        ('EXAMEN', 'Période d\'examens'),
        ('PAUSE', 'Pause pédagogique'),
        ('MAINTENANCE', 'Maintenance'),
        ('AUTRE', 'Autre'),
    ]

    type_jour_ferie = models.CharField(
        max_length=20,
        choices=TYPES_JOUR_FERIE,
        verbose_name="Type"
    )

    description = models.TextField(null=True, blank=True, verbose_name="Description")
    est_recurrent = models.BooleanField(default=False, verbose_name="Récurrent")

    # Paramètres de récurrence
    modele_recurrence = models.CharField(
        max_length=20,
        choices=[
            ('ANNUEL', 'Annuel'),
            ('MENSUEL', 'Mensuel'),
            ('HEBDOMADAIRE', 'Hebdomadaire'),
        ],
        null=True,
        blank=True,
        verbose_name="Modèle de récurrence"
    )

    # Classes concernées (si vide = toutes les classes)
    affecte_cours = models.BooleanField(default=True, verbose_name="Affecte les cours")
    affecte_examens = models.BooleanField(default=True, verbose_name="Affecte les examens")
    affecte_inscriptions = models.BooleanField(default=False, verbose_name="Affecte les inscriptions")

    # Couleur pour l'affichage dans le calendrier
    couleur = models.CharField(max_length=7, default="#dc3545", verbose_name="Couleur")

    class Meta:
        db_table = 'establishments_jour_ferie'
        verbose_name = "Jour férié/Vacances"
        verbose_name_plural = "Jours fériés/Vacances"
        ordering = ['date_debut']

    @property
    def duree_jours(self):
        """Durée en jours"""
        return (self.date_fin - self.date_debut).days + 1

    def __str__(self):
        if self.date_debut == self.date_fin:
            return f"{self.nom} ({self.date_debut})"
        return f"{self.nom} ({self.date_debut} - {self.date_fin})"

class Campus(BaseModel):
    """Campus d'un établissement"""
    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.CASCADE,
        related_name='campuses',
        verbose_name="Établissement"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    code = models.CharField(max_length=20, verbose_name="Code")

    # Localisation
    adresse = models.TextField(verbose_name="Adresse")
    localite = models.ForeignKey(
        Localite,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Localité"
    )

    # Coordonnées GPS
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Latitude"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Longitude"
    )

    # Informations générales
    description = models.TextField(null=True, blank=True, verbose_name="Description")
    superficie_totale = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Superficie totale (m²)"
    )

    # Services disponibles
    bibliotheque = models.BooleanField(default=False, verbose_name="Bibliothèque")
    cafeteria = models.BooleanField(default=False, verbose_name="Cafétéria")
    parking = models.BooleanField(default=False, verbose_name="Parking")
    internat = models.BooleanField(default=False, verbose_name="Internat")
    installations_sportives = models.BooleanField(default=False, verbose_name="Installations sportives")
    infirmerie = models.BooleanField(default=False, verbose_name="Infirmerie")

    # Contact
    telephone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Téléphone")
    email = models.EmailField(null=True, blank=True, verbose_name="Email")

    # Responsable du campus
    responsable_campus = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role__in': ['ADMIN', 'CHEF_DEPARTEMENT']},
        verbose_name="Responsable du campus"
    )

    est_campus_principal = models.BooleanField(default=False, verbose_name="Campus principal")
    est_actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'establishments_campus'
        verbose_name = "Campus"
        verbose_name_plural = "Campus"
        ordering = ['etablissement', 'nom']
        unique_together = ['etablissement', 'code']

    def save(self, *args, **kwargs):
        if self.est_campus_principal:
            # S'assurer qu'il n'y a qu'un seul campus principal par établissement
            Campus.objects.filter(
                etablissement=self.etablissement,
                est_campus_principal=True
            ).exclude(id=self.id).update(est_campus_principal=False)
        super().save(*args, **kwargs)

    def get_liste_services(self):
        """Retourne la liste des services disponibles"""
        services = []
        if self.bibliotheque:
            services.append("Bibliothèque")
        if self.cafeteria:
            services.append("Cafétéria")
        if self.parking:
            services.append("Parking")
        if self.internat:
            services.append("Internat")
        if self.installations_sportives:
            services.append("Installations sportives")
        if self.infirmerie:
            services.append("Infirmerie")
        return services

    def __str__(self):
        return f"{self.nom} - {self.etablissement.nom}"

