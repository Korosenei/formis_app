# apps/enrollment/models.py
from datetime import timedelta

from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from apps.core.models import BaseModel
from decimal import Decimal
import uuid

class PeriodeCandidature(BaseModel):
    """Périodes de candidature"""
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

    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")

    # Filières concernées
    filieres = models.ManyToManyField(
        'academic.Filiere',
        verbose_name="Filières concernées"
    )

    est_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        db_table = 'enrollment_periode_candidature'
        verbose_name = "Période de candidature"
        verbose_name_plural = "Périodes de candidature"
        ordering = ['-date_debut']

    def __str__(self):
        return f"{self.nom} - {self.etablissement.nom}"

    def est_ouverte(self):
        """Vérifie si la période de candidature est ouverte"""
        aujourdhui = timezone.now().date()
        return self.est_active and self.date_debut <= aujourdhui <= self.date_fin

class DocumentRequis(BaseModel):
    """Documents requis pour une candidature"""
    filiere = models.ForeignKey(
        'academic.Filiere',
        on_delete=models.CASCADE,
        related_name='documents_requis',
        verbose_name="Filière"
    )
    niveau = models.ForeignKey(
        'academic.Niveau',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='documents_requis',
        verbose_name="Niveau (optionnel)"
    )

    nom = models.CharField(max_length=200, verbose_name="Nom du document")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    TYPES_DOCUMENT = [
        ('PIECE_IDENTITE', 'Pièce d\'identité'),
        ('ACTE_NAISSANCE', 'Acte de naissance'),
        ('DIPLOME', 'Diplôme'),
        ('RELEVE_NOTES', 'Relevé de notes'),
        ('PHOTO_IDENTITE', 'Photo d\'identité'),
        ('CERTIFICAT_MEDICAL', 'Certificat médical'),
        ('JUSTIFICATIF_DOMICILE', 'Justificatif de domicile'),
        ('LETTRE_RECOMMANDATION', 'Lettre de recommandation'),
        ('LETTRE_MOTIVATION', 'Lettre de motivation'),
        ('CV', 'Curriculum Vitae'),
        ('AUTRE', 'Autre'),
    ]

    type_document = models.CharField(
        max_length=30,
        choices=TYPES_DOCUMENT,
        verbose_name="Type de document"
    )

    est_obligatoire = models.BooleanField(default=True, verbose_name="Obligatoire")
    taille_maximale = models.IntegerField(
        default=5242880,  # 5MB par défaut
        verbose_name="Taille maximale (octets)"
    )
    formats_autorises = models.CharField(
        max_length=100,
        default="pdf,jpg,jpeg,png",
        verbose_name="Formats autorisés",
        help_text="Formats séparés par des virgules"
    )

    ordre_affichage = models.IntegerField(default=0, verbose_name="Ordre d'affichage")

    class Meta:
        db_table = 'enrollment_document_requis'
        verbose_name = "Document requis"
        verbose_name_plural = "Documents requis"
        ordering = ['filiere', 'ordre_affichage', 'nom']

    def __str__(self):
        return f"{self.nom} - {self.filiere.nom}"

class Candidature(BaseModel):
    """Candidatures"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    token_inscription = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Token d'inscription"
    )
    token_inscription_expire = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date d'expiration du token"
    )

    # Informations de base
    numero_candidature = models.CharField(max_length=20, unique=True, verbose_name="Numéro de candidature")

    # Établissement et formation
    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        verbose_name="Établissement"
    )
    filiere = models.ForeignKey(
        'academic.Filiere',
        on_delete=models.CASCADE,
        verbose_name="Filière"
    )
    niveau = models.ForeignKey(
        'academic.Niveau',
        on_delete=models.CASCADE,
        verbose_name="Niveau"
    )
    annee_academique = models.ForeignKey(
        'establishments.AnneeAcademique',
        on_delete=models.CASCADE,
        verbose_name="Année académique"
    )

    # Informations personnelles du candidat
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    date_naissance = models.DateField(verbose_name="Date de naissance")
    lieu_naissance = models.CharField(max_length=100, verbose_name="Lieu de naissance")

    CHOIX_GENRE = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    genre = models.CharField(max_length=1, choices=CHOIX_GENRE, verbose_name="Genre")

    # Informations de contact
    telephone = models.CharField(max_length=20, verbose_name="Téléphone")
    email = models.EmailField(verbose_name="Email")
    adresse = models.TextField(verbose_name="Adresse")

    # Informations parentales/tuteur
    nom_pere = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nom du père")
    telephone_pere = models.CharField(max_length=20, null=True, blank=True, verbose_name="Téléphone du père")
    nom_mere = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nom de la mère")
    telephone_mere = models.CharField(max_length=20, null=True, blank=True, verbose_name="Téléphone de la mère")
    nom_tuteur = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nom du tuteur")
    telephone_tuteur = models.CharField(max_length=20, null=True, blank=True, verbose_name="Téléphone du tuteur")

    # Informations académiques
    ecole_precedente = models.CharField(max_length=200, null=True, blank=True, verbose_name="École précédente")
    dernier_diplome = models.CharField(max_length=200, null=True, blank=True, verbose_name="Dernier diplôme")
    annee_obtention = models.IntegerField(null=True, blank=True, verbose_name="Année d'obtention")

    # Statut de la candidature
    STATUTS_CANDIDATURE = [
        ('BROUILLON', 'Brouillon'),
        ('SOUMISE', 'Soumise'),
        ('EN_COURS_EXAMEN', 'En cours d\'examen'),
        ('APPROUVEE', 'Approuvée'),
        ('REJETEE', 'Rejetée'),
        ('ANNULEE', 'Annulée'),
        ('EXPIREE', 'Expirée'),
    ]

    statut = models.CharField(
        max_length=20,
        choices=STATUTS_CANDIDATURE,
        default='BROUILLON',
        verbose_name="Statut"
    )

    # Dates importantes
    date_soumission = models.DateTimeField(null=True, blank=True, verbose_name="Date de soumission")
    date_examen = models.DateTimeField(null=True, blank=True, verbose_name="Date d'examen")
    date_decision = models.DateTimeField(null=True, blank=True, verbose_name="Date de décision")

    # Examinateur et décision
    examine_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role__in': ['ADMIN', 'CHEF_DEPARTMENT']},
        related_name='candidatures_examinees',
        verbose_name="Examiné par"
    )

    motif_rejet = models.TextField(null=True, blank=True, verbose_name="Motif de rejet")
    notes_approbation = models.TextField(null=True, blank=True, verbose_name="Notes d'approbation")

    # Frais de candidature
    frais_dossier_requis = models.BooleanField(default=False, verbose_name="Frais de dossier requis")
    montant_frais_dossier = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Montant des frais de dossier"
    )
    frais_dossier_payes = models.BooleanField(default=False, verbose_name="Frais de dossier payés")
    date_paiement_frais = models.DateTimeField(null=True, blank=True, verbose_name="Date de paiement des frais")

    def generer_token_inscription(self):
        """Génère un token unique pour l'inscription"""
        import secrets
        self.token_inscription = secrets.token_urlsafe(32)
        # Token valide 30 jours
        self.token_inscription_expire = timezone.now() + timedelta(days=30)
        self.save(update_fields=['token_inscription', 'token_inscription_expire'])
        return self.token_inscription

    def token_est_valide(self):
        """Vérifie si le token est encore valide"""
        if not self.token_inscription or not self.token_inscription_expire:
            return False
        return timezone.now() < self.token_inscription_expire


    def save(self, *args, **kwargs):
        # Générer le numéro uniquement si toutes les infos sont présentes
        if (
            not self.numero_candidature 
            and self.etablissement 
            and self.filiere 
            and self.annee_academique
        ):
            self.numero_candidature = self.generer_numero_candidature()

        super().save(*args, **kwargs)

    def generer_numero_candidature(self):
        """Génère un numéro de candidature unique"""
        if not (self.etablissement and self.filiere and self.annee_academique):
            # Retourne un code temporaire si les infos ne sont pas encore là
            return f"CAND-TEMP-{uuid.uuid4().hex[:6].upper()}"

        annee = self.annee_academique.nom.split('-')[0]
        code_etablissement = self.etablissement.code
        code_filiere = self.filiere.code

        count = Candidature.objects.filter(
            etablissement=self.etablissement,
            filiere=self.filiere,
            annee_academique=self.annee_academique
        ).count() + 1

        return f"CAND{annee}{code_etablissement}{code_filiere}{count:04d}"

    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()

    def peut_etre_soumise(self):
        """Vérifie si la candidature peut être soumise"""
        if self.statut != 'BROUILLON':
            return False, "La candidature n'est pas en brouillon"

        # Vérifier que tous les documents obligatoires sont fournis
        documents_requis = DocumentRequis.objects.filter(
            filiere=self.filiere,
            est_obligatoire=True
        ).filter(
            models.Q(niveau=self.niveau) | models.Q(niveau__isnull=True)
        )

        for doc_requis in documents_requis:
            if not self.documents.filter(type_document=doc_requis.type_document).exists():
                return False, f"Document requis manquant: {doc_requis.nom}"

        return True, "OK"

    def soumettre(self):
        """Soumet la candidature"""
        peut_soumettre, message = self.peut_etre_soumise()
        if not peut_soumettre:
            raise ValueError(message)

        # Vérifier s'il n'y a pas déjà une candidature soumise/approuvée pour le même candidat
        candidatures_existantes = Candidature.objects.filter(
            email=self.email,
            etablissement=self.etablissement,
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique=self.annee_academique
        ).exclude(pk=self.pk).filter(
            statut__in=['SOUMISE', 'EN_COURS_EXAMEN', 'APPROUVEE']
        )

        if candidatures_existantes.exists():
            raise ValueError("Vous avez déjà une candidature active pour cette formation.")

        # Supprimer/Annuler les autres candidatures en brouillon du même candidat
        autres_brouillons = Candidature.objects.filter(
            email=self.email,
            statut='BROUILLON'
        ).exclude(pk=self.pk)

        # Les marquer comme annulées au lieu de les supprimer
        autres_brouillons.update(statut='ANNULEE')

        # Soumettre la candidature actuelle
        self.statut = 'SOUMISE'
        self.date_soumission = timezone.now()
        self.save()

    class Meta:
        db_table = 'enrollment_candidature'
        verbose_name = "Candidature"
        verbose_name_plural = "Candidatures"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['etablissement', 'statut']),
            models.Index(fields=['filiere', 'niveau', 'annee_academique']),
            models.Index(fields=['email', 'statut']),
        ]
        # Contrainte d'unicité pour éviter les doublons
        constraints = [
            models.UniqueConstraint(
                fields=['email', 'etablissement', 'filiere', 'niveau', 'annee_academique'],
                condition=models.Q(statut__in=['SOUMISE', 'EN_COURS_EXAMEN', 'APPROUVEE']),
                name='unique_candidature_active'
            )
        ]

    def __str__(self):
        return f"{self.numero_candidature} - {self.nom_complet()}"

class DocumentCandidature(BaseModel):
    """Documents fournis avec une candidature"""
    candidature = models.ForeignKey(
        Candidature,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name="Candidature"
    )

    type_document = models.CharField(
        max_length=30,
        choices=DocumentRequis.TYPES_DOCUMENT,
        verbose_name="Type de document"
    )

    nom = models.CharField(max_length=200, verbose_name="Nom du document")
    description = models.TextField(null=True, blank=True, verbose_name="Description")

    fichier = models.FileField(upload_to='candidature/documents/', verbose_name="Fichier")
    taille_fichier = models.BigIntegerField(verbose_name="Taille du fichier")
    format_fichier = models.CharField(max_length=10, verbose_name="Format du fichier")

    # Validation du document
    est_valide = models.BooleanField(default=False, verbose_name="Validé")
    valide_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role__in': ['ADMIN', 'CHEF_DEPARTMENT']},
        related_name='documents_valides',
        verbose_name="Validé par"
    )
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name="Date de validation")
    notes_validation = models.TextField(null=True, blank=True, verbose_name="Notes de validation")

    class Meta:
        db_table = 'enrollment_document_candidature'
        verbose_name = "Document de candidature"
        verbose_name_plural = "Documents de candidature"
        ordering = ['candidature', 'type_document']

    def save(self, *args, **kwargs):
        if self.fichier:
            self.taille_fichier = self.fichier.size
            self.format_fichier = self.fichier.name.split('.')[-1].lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.candidature.numero_candidature} - {self.nom}"

class Inscription(BaseModel):
    """Inscriptions (après approbation de candidature)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    candidature = models.OneToOneField(
        Candidature,
        on_delete=models.CASCADE,
        related_name='inscription',
        verbose_name="Candidature"
    )

    apprenant = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'APPRENANT'},
        related_name='inscriptions',
        verbose_name="Apprenant",
        null=True,
        blank=True
    )

    # Informations de l'inscription
    numero_inscription = models.CharField(max_length=20, unique=True, verbose_name="Numéro d'inscription")
    date_inscription = models.DateField(auto_now_add=True, verbose_name="Date d'inscription")

    # Classe assignée
    classe_assignee = models.ForeignKey(
        'academic.Classe',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inscriptions',
        verbose_name="Classe assignée"
    )

    # Statut de l'inscription
    STATUTS_INSCRIPTION = [
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspendue'),
        ('TRANSFERRED', 'Transférée'),
        ('WITHDRAWN', 'Abandonnée'),
        ('GRADUATED', 'Diplômé'),
        ('EXPELLED', 'Exclu'),
    ]

    statut = models.CharField(
        max_length=20,
        choices=STATUTS_INSCRIPTION,
        default='ACTIVE',
        verbose_name="Statut"
    )

    # Dates importantes
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin_prevue = models.DateField(verbose_name="Date de fin prévue")
    date_fin_reelle = models.DateField(null=True, blank=True, verbose_name="Date de fin réelle")

    # Frais de scolarité
    frais_scolarite = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Frais de scolarité"
    )

    # Statut de paiement
    STATUTS_PAIEMENT = [
        ('PENDING', 'En attente'),
        ('PARTIAL', 'Partiel'),
        ('COMPLETE', 'Complet'),
        ('OVERDUE', 'En retard'),
    ]

    statut_paiement = models.CharField(
        max_length=20,
        choices=STATUTS_PAIEMENT,
        default='PENDING',
        verbose_name="Statut de paiement"
    )

    # Montants
    total_paye = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Montant total payé"
    )
    solde = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Solde restant"
    )

    # Informations complémentaires
    notes = models.TextField(null=True, blank=True, verbose_name="Notes")

    # Créé par
    cree_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Créé par"
    )

    class Meta:
        db_table = 'enrollment_inscription'
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
        ordering = ['-date_inscription']
        indexes = [
            models.Index(fields=['apprenant', 'statut']),
            models.Index(fields=['classe_assignee', 'statut']),
        ]

    def save(self, *args, **kwargs):
        if not self.numero_inscription:
            self.numero_inscription = self.generer_numero_inscription()

        # Calculer le solde seulement si apprenant existe
        if self.apprenant:
            self.solde = self.frais_scolarite - self.total_paye

            # Mettre à jour le statut de paiement
            if self.solde <= 0:
                self.statut_paiement = 'COMPLETE'
            elif self.total_paye > 0:
                self.statut_paiement = 'PARTIAL'
            else:
                self.statut_paiement = 'PENDING'

        super().save(*args, **kwargs)

    def generer_numero_inscription(self):
        """Génère un numéro d'inscription unique"""
        annee = self.date_debut.year
        code_etablissement = self.candidature.etablissement.code

        # Compte le nombre d'inscriptions pour cet établissement cette année
        count = Inscription.objects.filter(
            candidature__etablissement=self.candidature.etablissement,
            date_debut__year=annee
        ).count() + 1

        return f"INS{annee}{code_etablissement}{count:05d}"

    def __str__(self):
        if self.apprenant:
            return f"{self.numero_inscription} - {self.apprenant.get_full_name()}"
        else:
            return f"{self.numero_inscription} - En attente de paiement"

class HistoriqueInscription(BaseModel):
    """Historique des changements d'inscription"""
    inscription = models.ForeignKey(
        Inscription,
        on_delete=models.CASCADE,
        related_name='historique',
        verbose_name="Inscription"
    )

    TYPES_ACTION = [
        ('CREATION', 'Création'),
        ('CHANGEMENT_STATUT', 'Changement de statut'),
        ('CHANGEMENT_CLASSE', 'Changement de classe'),
        ('SUSPENSION', 'Suspension'),
        ('REACTIVATION', 'Réactivation'),
        ('TRANSFERT', 'Transfert'),
        ('ABANDON', 'Abandon'),
        ('DIPLOME', 'Diplômé'),
        ('EXCLUSION', 'Exclusion'),
    ]

    type_action = models.CharField(
        max_length=20,
        choices=TYPES_ACTION,
        verbose_name="Type d'action"
    )

    ancienne_valeur = models.CharField(max_length=200, null=True, blank=True, verbose_name="Ancienne valeur")
    nouvelle_valeur = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nouvelle valeur")

    motif = models.TextField(null=True, blank=True, verbose_name="Motif")

    # Effectué par
    effectue_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Effectué par"
    )

    class Meta:
        db_table = 'enrollment_historique'
        verbose_name = "Historique d'inscription"
        verbose_name_plural = "Historiques d'inscriptions"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.inscription.numero_inscription} - {self.get_type_action_display()}"

class Transfert(BaseModel):
    """Transferts d'étudiants"""
    inscription = models.ForeignKey(
        Inscription,
        on_delete=models.CASCADE,
        related_name='transferts',
        verbose_name="Inscription"
    )

    # Origine
    classe_origine = models.ForeignKey(
        'academic.Classe',
        on_delete=models.CASCADE,
        related_name='transferts_depuis',
        verbose_name="Classe d'origine"
    )

    # Destination
    classe_destination = models.ForeignKey(
        'academic.Classe',
        on_delete=models.CASCADE,
        related_name='transferts_vers',
        verbose_name="Classe de destination"
    )

    # Dates
    date_transfert = models.DateField(verbose_name="Date de transfert")
    date_effet = models.DateField(verbose_name="Date d'effet")

    # Motif
    motif = models.TextField(verbose_name="Motif du transfert")

    STATUTS_TRANSFERT = [
        ('PENDING', 'En attente'),
        ('APPROVED', 'Approuvé'),
        ('REJECTED', 'Rejeté'),
        ('COMPLETED', 'Terminé'),
    ]

    statut = models.CharField(
        max_length=20,
        choices=STATUTS_TRANSFERT,
        default='PENDING',
        verbose_name="Statut"
    )

    # Validation
    demande_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transferts_demandes',
        verbose_name="Demandé par"
    )

    approuve_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transferts_approuves',
        verbose_name="Approuvé par"
    )

    date_approbation = models.DateTimeField(null=True, blank=True, verbose_name="Date d'approbation")
    notes_approbation = models.TextField(null=True, blank=True, verbose_name="Notes d'approbation")

    class Meta:
        db_table = 'enrollment_transfert'
        verbose_name = "Transfert"
        verbose_name_plural = "Transferts"
        ordering = ['-date_transfert']

    def __str__(self):
        return f"Transfert {self.inscription.apprenant.nom_complet()} : {self.classe_origine.nom} → {self.classe_destination.nom}"


# class Bourse(BaseModel):
#     """Bourses et aides financières"""
#     inscription = models.ForeignKey(
#         Inscription,
#         on_delete=models.CASCADE,
#         related_name='bourses',
#         verbose_name="Inscription"
#     )
#
#     nom = models.CharField(max_length=200, verbose_name="Nom de la bourse")
#     description = models.TextField(null=True, blank=True, verbose_name="Description")
#
#     TYPES_BOURSE = [
#         ('MERITE', 'Bourse au mérite'),
#         ('SOCIALE', 'Bourse sociale'),
#         ('SPORTIVE', 'Bourse sportive'),
#         ('AIDE_PARTIELLE', 'Aide partielle'),
#         ('COMPLETE', 'Bourse complète'),
#         ('ETAT', 'Bourse d\'État'),
#         ('PRIVEE', 'Bourse privée'),
#     ]
#
#     type_bourse = models.CharField(
#         max_length=20,
#         choices=TYPES_BOURSE,
#         verbose_name="Type de bourse"
#     )
#
#     # Montant
#     montant = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         verbose_name="Montant"
#     )
#
#     TYPES_MONTANT = [
#         ('FIXED', 'Montant fixe'),
#         ('PERCENTAGE', 'Pourcentage'),
#     ]
#
#     type_montant = models.CharField(
#         max_length=20,
#         choices=TYPES_MONTANT,
#         default='FIXED',
#         verbose_name="Type de montant"
#     )
#
#     # Période de validité
#     date_debut = models.DateField(verbose_name="Date de début")
#     date_fin = models.DateField(verbose_name="Date de fin")
#
#     # Conditions
#     conditions = models.TextField(null=True, blank=True, verbose_name="Conditions")
#     moyenne_minimale = models.DecimalField(
#         max_digits=4,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         verbose_name="Moyenne minimale requise"
#     )
#
#     # Statut
#     STATUTS_BOURSE = [
#         ('ACTIVE', 'Active'),
#         ('SUSPENDED', 'Suspendue'),
#         ('TERMINATED', 'Terminée'),
#         ('CANCELLED', 'Annulée'),
#     ]
#
#     statut = models.CharField(
#         max_length=20,
#         choices=STATUTS_BOURSE,
#         default='ACTIVE',
#         verbose_name="Statut"
#     )
#
#     # Organisme accordeur
#     organisme = models.CharField(max_length=200, null=True, blank=True, verbose_name="Organisme sponsor")
#
#     # Validation
#     approuve_par = models.ForeignKey(
#         'accounts.Utilisateur',
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         verbose_name="Approuvé par"
#     )
#     date_approbation = models.DateField(null=True, blank=True, verbose_name="Date d'approbation")
#
#     class Meta:
#         db_table = 'enrollment_bourse'
#         verbose_name = "Bourse"
#         verbose_name_plural = "Bourses"
#         ordering = ['-date_debut']
#
#     def calculer_montant_reduction(self, frais_scolarite):
#         """Calcule le montant de réduction selon le type"""
#         if self.type_montant == 'PERCENTAGE':
#             return frais_scolarite * (self.montant / 100)
#         return self.montant
#
#     def est_active_pour_date(self, date):
#         """Vérifie si la bourse est active à une date donnée"""
#         return (self.statut == 'ACTIVE' and
#                 self.date_debut <= date <= self.date_fin)
#
#     def __str__(self):
#         return f"{self.nom} - {self.inscription.apprenant.nom_complet()}"

class Abandon(BaseModel):
    """Abandons/Retraits d'inscription"""
    inscription = models.OneToOneField(
        Inscription,
        on_delete=models.CASCADE,
        related_name='abandon',
        verbose_name="Inscription"
    )

    date_abandon = models.DateField(verbose_name="Date d'abandon")
    date_effet = models.DateField(verbose_name="Date d'effet")

    TYPES_ABANDON = [
        ('VOLONTAIRE', 'Volontaire'),
        ('ECHEC_ACADEMIQUE', 'Échec académique'),
        ('DIFFICULTES_FINANCIERES', 'Difficultés financières'),
        ('DISCIPLINAIRE', 'Disciplinaire'),
        ('RAISONS_MEDICALES', 'Raisons médicales'),
        ('TRANSFERT', 'Transfert'),
        ('AUTRE', 'Autre'),
    ]

    type_abandon = models.CharField(
        max_length=30,
        choices=TYPES_ABANDON,
        verbose_name="Type d'abandon"
    )

    motif = models.TextField(verbose_name="Motif détaillé")

    # Remboursement
    eligible_remboursement = models.BooleanField(default=False, verbose_name="Éligible au remboursement")
    montant_remboursable = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Montant remboursable"
    )
    remboursement_traite = models.BooleanField(default=False, verbose_name="Remboursement traité")
    date_remboursement = models.DateField(null=True, blank=True, verbose_name="Date de remboursement")

    # Documents à retourner
    documents_retournes = models.BooleanField(default=False, verbose_name="Documents retournés")
    materiel_retourne = models.BooleanField(default=False, verbose_name="Matériel retourné")

    # Validation
    traite_par = models.ForeignKey(
        'accounts.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Traité par"
    )

    class Meta:
        db_table = 'enrollment_abandon'
        verbose_name = "Abandon"
        verbose_name_plural = "Abandons"
        ordering = ['-date_abandon']

    def __str__(self):
        return f"Abandon {self.inscription.apprenant.nom_complet()} - {self.date_abandon}"

