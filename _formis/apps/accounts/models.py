# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
import uuid
import random
import string

class Utilisateur(AbstractUser):
    """Modèle utilisateur personnalisé"""

    ROLES_UTILISATEUR = (
        ('SUPERADMIN', 'Super Administrateur'),
        ('ADMIN', 'Administrateur d\'établissement'),
        ('CHEF_DEPARTEMENT', 'Chef de département'),
        ('ENSEIGNANT', 'Enseignant'),
        ('APPRENANT', 'Apprenant'),
    )

    CHOIX_GENRE = (
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLES_UTILISATEUR, default='APPRENANT')
    matricule = models.CharField(max_length=20, unique=True, null=True, blank=True)

    # Informations personnelles
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    date_naissance = models.DateField(null=True, blank=True, verbose_name="Date de naissance")
    lieu_naissance = models.CharField(max_length=100, null=True, blank=True, verbose_name="Lieu de naissance")
    genre = models.CharField(max_length=1, choices=CHOIX_GENRE, null=True, blank=True)
    telephone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Téléphone")
    adresse = models.TextField(null=True, blank=True, verbose_name="Adresse")

    # Informations académiques/professionnelles
    etablissement = models.ForeignKey(
        'establishments.Etablissement',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Établissement",
    )
    departement = models.ForeignKey(
        'academic.Departement',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="utilisateurs",
        verbose_name="Département"
    )

    departements_intervention = models.ManyToManyField(
        'academic.Departement',
        blank=True,
        related_name='enseignants_intervenants',
        verbose_name="Départements d'intervention"
    )

    # Métadonnées
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='utilisateurs_crees')

    # Photo de profil
    photo_profil = models.ImageField(upload_to='profils/', null=True, blank=True)

    class Meta:
        db_table = 'comptes_utilisateur'
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['-date_creation']

    def save(self, *args, **kwargs):
        """Génération automatique du matricule"""
        if not self.matricule:
            self.matricule = self.generer_matricule()
        if not self.username:
            self.username = self.matricule
        super().save(*args, **kwargs)

    def generer_matricule(self):
        """Génère un matricule unique"""
        annee = timezone.now().year
        prefixe_role = {
            'SUPERADMIN': 'SA',
            'ADMIN': 'AD',
            'CHEF_DEPARTEMENT': 'CD',
            'ENSEIGNANT': 'EN',
            'APPRENANT': 'AP',
        }.get(self.role, 'US')

        # Génère un numéro séquentiel
        dernier_utilisateur = Utilisateur.objects.filter(
            role=self.role,
            matricule__startswith=f"{prefixe_role}{annee}"
        ).order_by('-matricule').first()

        if dernier_utilisateur and dernier_utilisateur.matricule:
            try:
                dernier_numero = int(dernier_utilisateur.matricule[-4:])
                nouveau_numero = dernier_numero + 1
            except (ValueError, IndexError):
                nouveau_numero = 1
        else:
            nouveau_numero = 1

        return f"{prefixe_role}{annee}{nouveau_numero:04d}"

    def get_full_name(self):
        return f"{self.prenom} {self.nom}".strip()

    def get_dashboard_url(self):
        """Retourne l'URL du tableau de bord selon le rôle"""
        urls_tableau_de_bord = {
            'SUPERADMIN': '/dashboard/superadmin/',
            'ADMIN': '/dashboard/admin/',
            'CHEF_DEPARTEMENT': '/dashboard/department_head/',
            'ENSEIGNANT': '/dashboard/teacher/',
            'APPRENANT': '/dashboard/student/',
        }
        return urls_tableau_de_bord.get(self.role, '/dashboard/')

    def peut_etre_chef_departement(self):
        """Vérifie si l'utilisateur peut être nommé chef de département"""
        return self.role in ['ENSEIGNANT', 'CHEF_DEPARTEMENT'] and self.est_actif

    def est_chef_de_departement(self):
        """Vérifie si l'utilisateur est chef d'un département"""
        return hasattr(self, 'departements_diriges') and self.departements_diriges.exists()

    def get_departements_diriges(self):
        """Retourne les départements dirigés par cet utilisateur"""
        if hasattr(self, 'departements_diriges'):
            return self.departements_diriges.all()
        return []

    def peut_gerer_utilisateur(self, utilisateur_cible):
        """
        Vérifie si l'utilisateur peut gérer un autre utilisateur

        Règles:
        - ADMIN: peut gérer tous les utilisateurs de son établissement (SAUF APPRENANT)
        - CHEF_DEPARTEMENT: peut gérer enseignants de son département uniquement
        - Personne ne peut créer/modifier/supprimer des APPRENANTS via l'interface admin
        """
        # Personne ne peut se gérer soi-même (sauf changement de profil personnel)
        if self.id == utilisateur_cible.id:
            return False

        # Les APPRENANTS ne peuvent pas être gérés via l'interface utilisateurs
        if utilisateur_cible.role == 'APPRENANT':
            return False

        # SUPERADMIN peut tout gérer
        if self.role == 'SUPERADMIN':
            return True

        # ADMIN peut gérer les utilisateurs de son établissement (sauf APPRENANTS)
        if self.role == 'ADMIN':
            if utilisateur_cible.etablissement == self.etablissement:
                # ADMIN peut gérer: ADMIN, CHEF_DEPARTEMENT, ENSEIGNANT
                return utilisateur_cible.role in ['ADMIN', 'CHEF_DEPARTEMENT', 'ENSEIGNANT']
            return False

        # CHEF_DEPARTEMENT peut gérer uniquement les ENSEIGNANTS de son département
        if self.role == 'CHEF_DEPARTEMENT':
            if utilisateur_cible.departement == self.departement:
                return utilisateur_cible.role == 'ENSEIGNANT'
            return False

        return False

    def peut_creer_role(self, role_cible):
        """
        Vérifie si l'utilisateur peut créer un utilisateur avec le rôle spécifié

        Règles:
        - ADMIN: peut créer ADMIN, CHEF_DEPARTEMENT, ENSEIGNANT
        - CHEF_DEPARTEMENT: peut créer ENSEIGNANT uniquement
        - APPRENANT: ne peut JAMAIS être créé via l'interface utilisateurs
        """
        # Les APPRENANTS ne peuvent pas être créés via cette interface
        if role_cible == 'APPRENANT':
            return False

        if self.role == 'SUPERADMIN':
            return True

        if self.role == 'ADMIN':
            return role_cible in ['ADMIN', 'CHEF_DEPARTEMENT', 'ENSEIGNANT']

        if self.role == 'CHEF_DEPARTEMENT':
            return role_cible == 'ENSEIGNANT'

        return False

    def peut_gerer_enseignant(self, enseignant):
        """Vérifie si l'utilisateur peut gérer un enseignant spécifique"""
        if enseignant.role != 'ENSEIGNANT':
            return False

        if self.role == 'SUPERADMIN':
            return True

        if self.role == 'ADMIN':
            return enseignant.etablissement == self.etablissement

        if self.role == 'CHEF_DEPARTEMENT':
            return enseignant.departement == self.departement

        return False

    def peut_gerer_etudiant(self, etudiant):
        """Vérifie si l'utilisateur peut gérer un étudiant spécifique"""
        if etudiant.role != 'APPRENANT':
            return False

        if self.role == 'SUPERADMIN':
            return True

        if self.role == 'ADMIN':
            return etudiant.etablissement == self.etablissement

        if self.role == 'CHEF_DEPARTEMENT':
            return etudiant.departement == self.departement

        return False

    def get_role_display(self):
        """Retourne le nom complet du rôle"""
        return dict(self.ROLES_UTILISATEUR).get(self.role, self.role)

    @property
    def unread_notifications_count(self):
        """Retourne le nombre de notifications non lues"""
        if hasattr(self, 'notifications'):
            return self.notifications.filter(read=False).count()
        return 0

    @property
    def unread_messages_count(self):
        """Retourne le nombre de messages non lus"""
        if hasattr(self, 'received_messages'):
            return self.received_messages.filter(read=False).count()
        return 0

    def __str__(self):
        return f"{self.get_full_name()} ({self.matricule})"

class PasswordResetToken(models.Model):
    """Token pour la réinitialisation de mot de passe"""
    user = models.OneToOneField(
        'Utilisateur',
        on_delete=models.CASCADE,
        related_name='reset_token'
    )
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        db_table = 'comptes_password_reset_token'
        verbose_name = "Token de réinitialisation"
        verbose_name_plural = "Tokens de réinitialisation"

    def is_expired(self):
        return timezone.now() > self.expires_at or self.used

    def mark_as_used(self):
        self.used = True
        self.save()

class ProfilUtilisateur(models.Model):
    """Profil étendu de l'utilisateur"""
    utilisateur = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, related_name='profil')

    # Informations de contact d'urgence
    nom_contact_urgence = models.CharField(max_length=100, null=True, blank=True)
    telephone_contact_urgence = models.CharField(max_length=20, null=True, blank=True)
    relation_contact_urgence = models.CharField(max_length=50, null=True, blank=True)

    # Informations médicales (optionnel)
    groupe_sanguin = models.CharField(max_length=5, null=True, blank=True)
    conditions_medicales = models.TextField(null=True, blank=True)

    # Préférences
    langue = models.CharField(max_length=10, default='fr')
    fuseau_horaire = models.CharField(max_length=50, default='UTC')
    recevoir_notifications = models.BooleanField(default=True)
    recevoir_notifications_email = models.BooleanField(default=True)

    class Meta:
        db_table = 'comptes_profil_utilisateur'
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        return f"Profil de {self.utilisateur.get_full_name()}"

class ProfilApprenant(models.Model):
    """Profil spécifique aux apprenants"""
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='profil_apprenant',
        limit_choices_to={'role': 'APPRENANT'}
    )

    # Informations académiques
    niveau_actuel = models.ForeignKey(
        'academic.Niveau',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    classe_actuelle = models.ForeignKey(
        'academic.Classe',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='apprenants'
    )
    annee_academique = models.ForeignKey(
        'establishments.AnneeAcademique',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # Statut de paiement
    statut_paiement = models.CharField(
        max_length=20,
        choices=[
            ('EN_ATTENTE', 'En attente'),
            ('PARTIEL', 'Partiel'),
            ('COMPLET', 'Complet'),
        ],
        default='EN_ATTENTE'
    )

    # Informations parentales
    nom_pere = models.CharField(max_length=100, null=True, blank=True)
    telephone_pere = models.CharField(max_length=20, null=True, blank=True)
    profession_pere = models.CharField(max_length=100, null=True, blank=True)

    nom_mere = models.CharField(max_length=100, null=True, blank=True)
    telephone_mere = models.CharField(max_length=20, null=True, blank=True)
    profession_mere = models.CharField(max_length=100, null=True, blank=True)

    nom_tuteur = models.CharField(max_length=100, null=True, blank=True)
    telephone_tuteur = models.CharField(max_length=20, null=True, blank=True)
    relation_tuteur = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'comptes_profil_apprenant'
        verbose_name = "Profil apprenant"
        verbose_name_plural = "Profils apprenants"

    def __str__(self):
        return f"Profil apprenant de {self.utilisateur.get_full_name()}"

class ProfilEnseignant(models.Model):
    """Profil spécifique aux enseignants"""
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='profil_enseignant',
        limit_choices_to={'role__in': ['ENSEIGNANT', 'CHEF_DEPARTEMENT']}
    )

    # Informations professionnelles
    id_employe = models.CharField(max_length=20, unique=True, null=True, blank=True)
    date_embauche = models.DateField(null=True, blank=True)
    specialisation = models.CharField(max_length=100, null=True, blank=True)
    qualifications = models.TextField(null=True, blank=True)

    # NOUVEAU: Type d'enseignant
    TYPE_ENSEIGNANT = [
        ('PERMANENT', 'Permanent'),
        ('VACATAIRE', 'Vacataire'),
    ]
    type_enseignant = models.CharField(
        max_length=20,
        choices=TYPE_ENSEIGNANT,
        default='VACATAIRE',
        verbose_name="Type d'enseignant"
    )

    # Statut (conservé pour compatibilité)
    est_permanent = models.BooleanField(default=False)
    est_principal = models.BooleanField(default=False)

    # NOUVEAU: Indicateur chef de département
    est_chef_departement = models.BooleanField(
        default=False,
        verbose_name="Est chef de département"
    )

    # Matières enseignées
    matieres = models.ManyToManyField('courses.Matiere', blank=True)

    class Meta:
        db_table = 'comptes_profil_enseignant'
        verbose_name = "Profil enseignant"
        verbose_name_plural = "Profils enseignants"

    def save(self, *args, **kwargs):
        # Synchroniser est_permanent avec type_enseignant
        self.est_permanent = (self.type_enseignant == 'PERMANENT')

        # Synchroniser le rôle de l'utilisateur si chef de département
        if self.est_chef_departement and self.utilisateur.role == 'ENSEIGNANT':
            self.utilisateur.role = 'CHEF_DEPARTEMENT'
            self.utilisateur.save()
        elif not self.est_chef_departement and self.utilisateur.role == 'CHEF_DEPARTEMENT':
            # Vérifier s'il n'est plus chef d'aucun département
            if not self.utilisateur.departements_diriges.exists():
                self.utilisateur.role = 'ENSEIGNANT'
                self.utilisateur.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Profil enseignant de {self.utilisateur.get_full_name()}"
