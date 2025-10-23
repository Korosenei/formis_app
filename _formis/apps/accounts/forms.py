# apps/accounts/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import Utilisateur, ProfilApprenant, ProfilEnseignant, ProfilUtilisateur
from apps.academic.models import Departement
from apps.courses.models import Matiere

class LoginForm(AuthenticationForm):
    """Formulaire de connexion personnalisé"""
    username = forms.CharField(
        label="Matricule ou Email",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Matricule ou email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mot de passe'
        })
    )

class ProfileForm(forms.ModelForm):
    """Formulaire de modification de profil - Version de base (conservée pour compatibilité)"""

    class Meta:
        model = Utilisateur
        fields = [
            'prenom', 'nom', 'email', 'telephone', 'adresse',
            'date_naissance', 'lieu_naissance', 'genre', 'photo_profil'
        ]
        widgets = {
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'date_naissance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'genre': forms.Select(attrs={'class': 'form-select'}),
            'photo_profil': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if Utilisateur.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise ValidationError("Cette adresse email est déjà utilisée.")
        return email

class ForgotPasswordForm(forms.Form):
    """Formulaire pour mot de passe oublié"""
    email = forms.EmailField(
        label="Adresse email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre adresse email',
            'autofocus': True
        })
    )

class ResetPasswordForm(forms.Form):
    """Formulaire de réinitialisation de mot de passe"""
    password = forms.CharField(
        label="Nouveau mot de passe",
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nouveau mot de passe'
        })
    )
    confirm_password = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmer le mot de passe'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password:
            if password != confirm_password:
                raise ValidationError("Les mots de passe ne correspondent pas.")
        return cleaned_data


# ================================
# NOUVEAUX FORMULAIRES DE PROFIL
# ================================
class BasicProfileForm(forms.ModelForm):
    """Formulaire de base pour tous les profils (version améliorée)"""

    class Meta:
        model = Utilisateur
        fields = [
            'prenom', 'nom', 'email', 'telephone',
            'date_naissance', 'lieu_naissance', 'genre',
            'adresse', 'photo_profil'
        ]
        widgets = {
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'date_naissance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'genre': forms.Select(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'photo_profil': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Champs obligatoires
        self.fields['prenom'].required = True
        self.fields['nom'].required = True
        self.fields['email'].required = True

    def clean_email(self):
        """Valider l'unicité de l'email"""
        email = self.cleaned_data.get('email')
        if email:
            # Exclure l'utilisateur actuel
            qs = Utilisateur.objects.filter(email=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("Cette adresse email est déjà utilisée.")

        return email

    def clean_photo_profil(self):
        """Valider la photo de profil"""
        photo = self.cleaned_data.get('photo_profil')

        if photo:
            # Vérifier la taille (max 5 MB)
            if hasattr(photo, 'size') and photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError("La photo ne doit pas dépasser 5 MB.")

            # Vérifier le type
            if hasattr(photo, 'content_type'):
                valid_types = ['image/jpeg', 'image/png', 'image/jpg']
                if photo.content_type not in valid_types:
                    raise forms.ValidationError("Format non supporté. Utilisez JPG ou PNG.")

        return photo

class StudentProfileForm(BasicProfileForm):
    """Formulaire étendu pour les apprenants"""

    # Champs du profil apprenant
    nom_pere = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    telephone_pere = forms.CharField(max_length=20, required=False,
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))
    profession_pere = forms.CharField(max_length=100, required=False,
                                      widget=forms.TextInput(attrs={'class': 'form-control'}))

    nom_mere = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    telephone_mere = forms.CharField(max_length=20, required=False,
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))
    profession_mere = forms.CharField(max_length=100, required=False,
                                      widget=forms.TextInput(attrs={'class': 'form-control'}))

    nom_tuteur = forms.CharField(max_length=100, required=False,
                                 widget=forms.TextInput(attrs={'class': 'form-control'}))
    telephone_tuteur = forms.CharField(max_length=20, required=False,
                                       widget=forms.TextInput(attrs={'class': 'form-control'}))
    relation_tuteur = forms.CharField(max_length=50, required=False,
                                      widget=forms.TextInput(attrs={'class': 'form-control'}))

    # Champs du profil utilisateur
    nom_contact_urgence = forms.CharField(max_length=100, required=False,
                                          widget=forms.TextInput(attrs={'class': 'form-control'}))
    telephone_contact_urgence = forms.CharField(max_length=20, required=False,
                                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    relation_contact_urgence = forms.CharField(max_length=50, required=False,
                                               widget=forms.TextInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Charger les données du profil apprenant
        if self.instance and hasattr(self.instance, 'profil_apprenant'):
            profil = self.instance.profil_apprenant
            self.fields['nom_pere'].initial = profil.nom_pere
            self.fields['telephone_pere'].initial = profil.telephone_pere
            self.fields['profession_pere'].initial = profil.profession_pere
            self.fields['nom_mere'].initial = profil.nom_mere
            self.fields['telephone_mere'].initial = profil.telephone_mere
            self.fields['profession_mere'].initial = profil.profession_mere
            self.fields['nom_tuteur'].initial = profil.nom_tuteur
            self.fields['telephone_tuteur'].initial = profil.telephone_tuteur
            self.fields['relation_tuteur'].initial = profil.relation_tuteur

        # Charger les données du profil utilisateur
        if self.instance and hasattr(self.instance, 'profil'):
            profil_user = self.instance.profil
            self.fields['nom_contact_urgence'].initial = profil_user.nom_contact_urgence
            self.fields['telephone_contact_urgence'].initial = profil_user.telephone_contact_urgence
            self.fields['relation_contact_urgence'].initial = profil_user.relation_contact_urgence

    def save(self, commit=True):
        """Sauvegarder l'utilisateur et ses profils"""
        user = super().save(commit=False)

        if commit:
            user.save()

            # Sauvegarder le profil apprenant
            profil_apprenant, created = ProfilApprenant.objects.get_or_create(utilisateur=user)
            profil_apprenant.nom_pere = self.cleaned_data.get('nom_pere')
            profil_apprenant.telephone_pere = self.cleaned_data.get('telephone_pere')
            profil_apprenant.profession_pere = self.cleaned_data.get('profession_pere')
            profil_apprenant.nom_mere = self.cleaned_data.get('nom_mere')
            profil_apprenant.telephone_mere = self.cleaned_data.get('telephone_mere')
            profil_apprenant.profession_mere = self.cleaned_data.get('profession_mere')
            profil_apprenant.nom_tuteur = self.cleaned_data.get('nom_tuteur')
            profil_apprenant.telephone_tuteur = self.cleaned_data.get('telephone_tuteur')
            profil_apprenant.relation_tuteur = self.cleaned_data.get('relation_tuteur')
            profil_apprenant.save()

            # Sauvegarder le profil utilisateur
            profil_user, created = ProfilUtilisateur.objects.get_or_create(utilisateur=user)
            profil_user.nom_contact_urgence = self.cleaned_data.get('nom_contact_urgence')
            profil_user.telephone_contact_urgence = self.cleaned_data.get('telephone_contact_urgence')
            profil_user.relation_contact_urgence = self.cleaned_data.get('relation_contact_urgence')
            profil_user.save()

        return user

class TeacherProfileForm(forms.ModelForm):
    """Formulaire étendu pour les enseignants"""

    # Champs de base
    prenom = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    nom = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    telephone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    date_naissance = forms.DateField(required=False,
                                     widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    lieu_naissance = forms.CharField(max_length=100, required=False,
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))
    genre = forms.ChoiceField(choices=[('', '---')] + list(Utilisateur.CHOIX_GENRE), required=False,
                              widget=forms.Select(attrs={'class': 'form-control'}))
    adresse = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
    photo_profil = forms.ImageField(required=False,
                                    widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}))

    # Département principal
    departement = forms.ModelChoiceField(
        queryset=Departement.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Département principal"
    )

    # NOUVEAU: Départements d'intervention
    departements_intervention = forms.ModelMultipleChoiceField(
        queryset=Departement.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Départements d'intervention",
        help_text="Sélectionnez les départements où cet enseignant peut intervenir"
    )

    # Champs du profil enseignant
    id_employe = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    date_embauche = forms.DateField(required=False,
                                    widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    specialisation = forms.CharField(max_length=100, required=False,
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))
    qualifications = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))

    # NOUVEAU: Type d'enseignant
    type_enseignant = forms.ChoiceField(
        choices=ProfilEnseignant.TYPE_ENSEIGNANT,
        required=True,
        initial='VACATAIRE',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Type d'enseignant"
    )

    est_principal = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Enseignant principal"
    )

    # NOUVEAU: Chef de département
    est_chef_departement = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_est_chef_departement'}),
        label="Nommer comme chef de département"
    )

    # NOUVEAU: Département à diriger (affiché si est_chef_departement = True)
    departement_a_diriger = forms.ModelChoiceField(
        queryset=Departement.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_departement_a_diriger'}),
        label="Département à diriger",
        help_text="Seuls les départements sans chef sont affichés"
    )

    # Matières
    matieres = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Matières enseignées"
    )

    class Meta:
        model = Utilisateur
        fields = []

    def __init__(self, *args, **kwargs):
        self.etablissement = kwargs.pop('etablissement', None)
        super().__init__(*args, **kwargs)

        # Charger les données existantes
        if self.instance and self.instance.pk:
            self.fields['prenom'].initial = self.instance.prenom
            self.fields['nom'].initial = self.instance.nom
            self.fields['email'].initial = self.instance.email
            self.fields['telephone'].initial = self.instance.telephone
            self.fields['date_naissance'].initial = self.instance.date_naissance
            self.fields['lieu_naissance'].initial = self.instance.lieu_naissance
            self.fields['genre'].initial = self.instance.genre
            self.fields['adresse'].initial = self.instance.adresse
            self.fields['departement'].initial = self.instance.departement

            # Départements d'intervention
            self.fields['departements_intervention'].initial = self.instance.departements_intervention.all()

            # Charger le profil enseignant
            if hasattr(self.instance, 'profil_enseignant'):
                profil = self.instance.profil_enseignant
                self.fields['id_employe'].initial = profil.id_employe
                self.fields['date_embauche'].initial = profil.date_embauche
                self.fields['specialisation'].initial = profil.specialisation
                self.fields['qualifications'].initial = profil.qualifications
                self.fields['type_enseignant'].initial = profil.type_enseignant
                self.fields['est_principal'].initial = profil.est_principal
                self.fields['est_chef_departement'].initial = profil.est_chef_departement
                self.fields['matieres'].initial = profil.matieres.all()

                # Si déjà chef de département
                if profil.est_chef_departement:
                    depts_diriges = self.instance.departements_diriges.all()
                    if depts_diriges.exists():
                        self.fields['departement_a_diriger'].initial = depts_diriges.first()

        # Configurer les querysets selon l'établissement
        if self.etablissement:
            self.fields['departement'].queryset = Departement.objects.filter(
                etablissement=self.etablissement,
                est_actif=True
            )

            self.fields['departements_intervention'].queryset = Departement.objects.filter(
                etablissement=self.etablissement,
                est_actif=True
            )

            # Départements sans chef (pour nomination)
            departements_sans_chef = Departement.objects.filter(
                etablissement=self.etablissement,
                est_actif=True,
                chef__isnull=True
            )

            # Si modification et déjà chef, ajouter son département actuel
            if self.instance and self.instance.pk and hasattr(self.instance, 'profil_enseignant'):
                if self.instance.profil_enseignant.est_chef_departement:
                    depts_diriges = self.instance.departements_diriges.all()
                    departements_sans_chef = departements_sans_chef | depts_diriges

            self.fields['departement_a_diriger'].queryset = departements_sans_chef

            # Matières de l'établissement
            self.fields['matieres'].queryset = Matiere.objects.filter(
                niveau__filiere__etablissement=self.etablissement
            ).distinct()

    def clean_email(self):
        """Valider l'unicité de l'email"""
        email = self.cleaned_data.get('email')
        if email:
            qs = Utilisateur.objects.filter(email=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Cette adresse email est déjà utilisée.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        est_chef = cleaned_data.get('est_chef_departement')
        dept_a_diriger = cleaned_data.get('departement_a_diriger')

        # Si nommé chef de département, un département doit être sélectionné
        if est_chef and not dept_a_diriger:
            raise ValidationError({
                'departement_a_diriger': 'Veuillez sélectionner le département à diriger.'
            })

        # Le département d'intervention doit inclure le département principal
        dept_principal = cleaned_data.get('departement')
        depts_intervention = cleaned_data.get('departements_intervention')

        if dept_principal and depts_intervention:
            if dept_principal not in depts_intervention:
                # Ajouter automatiquement le département principal
                cleaned_data['departements_intervention'] = list(depts_intervention) + [dept_principal]

        return cleaned_data

    def save(self, commit=True):
        """Sauvegarder l'utilisateur et ses profils"""
        # Créer/modifier l'utilisateur
        if self.instance and self.instance.pk:
            user = self.instance
        else:
            user = Utilisateur()
            user.etablissement = self.etablissement
            user.role = 'ENSEIGNANT'  # Par défaut

        # Données de base
        user.prenom = self.cleaned_data['prenom']
        user.nom = self.cleaned_data['nom']
        user.email = self.cleaned_data['email']
        user.telephone = self.cleaned_data.get('telephone')
        user.date_naissance = self.cleaned_data.get('date_naissance')
        user.lieu_naissance = self.cleaned_data.get('lieu_naissance')
        user.genre = self.cleaned_data.get('genre')
        user.adresse = self.cleaned_data.get('adresse')
        user.departement = self.cleaned_data['departement']

        if self.cleaned_data.get('photo_profil'):
            user.photo_profil = self.cleaned_data['photo_profil']

        if commit:
            user.save()

            # Départements d'intervention
            depts_intervention = self.cleaned_data.get('departements_intervention', [])
            user.departements_intervention.set(depts_intervention)

            # Profil enseignant
            profil, created = ProfilEnseignant.objects.get_or_create(utilisateur=user)
            profil.id_employe = self.cleaned_data.get('id_employe')
            profil.date_embauche = self.cleaned_data.get('date_embauche')
            profil.specialisation = self.cleaned_data.get('specialisation')
            profil.qualifications = self.cleaned_data.get('qualifications')
            profil.type_enseignant = self.cleaned_data['type_enseignant']
            profil.est_principal = self.cleaned_data.get('est_principal', False)
            profil.est_chef_departement = self.cleaned_data.get('est_chef_departement', False)
            profil.save()

            # Matières
            matieres = self.cleaned_data.get('matieres', [])
            profil.matieres.set(matieres)

            # Gestion du chef de département
            if profil.est_chef_departement:
                dept_a_diriger = self.cleaned_data.get('departement_a_diriger')
                if dept_a_diriger:
                    # Retirer l'ancien chef si existant
                    if dept_a_diriger.chef and dept_a_diriger.chef != user:
                        ancien_chef = dept_a_diriger.chef
                        if hasattr(ancien_chef, 'profil_enseignant'):
                            ancien_chef.profil_enseignant.est_chef_departement = False
                            ancien_chef.profil_enseignant.save()

                    # Nommer le nouveau chef
                    dept_a_diriger.chef = user
                    dept_a_diriger.save()

                    # Changer le rôle en CHEF_DEPARTEMENT
                    user.role = 'CHEF_DEPARTEMENT'
                    user.save()
            else:
                # Si décoché, retirer de tous les départements dirigés
                for dept in user.departements_diriges.all():
                    dept.chef = None
                    dept.save()

                # Revenir au rôle ENSEIGNANT si plus chef de rien
                if user.role == 'CHEF_DEPARTEMENT':
                    user.role = 'ENSEIGNANT'
                    user.save()

        return user

class NommerChefDepartementForm(forms.Form):
    """Formulaire pour nommer un chef de département"""

    departement = forms.ModelChoiceField(
        queryset=Departement.objects.none(),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control form-select-lg',
            'id': 'id_departement'
        }),
        label="Département",
        help_text="Seuls les départements sans chef actuel sont affichés"
    )

    enseignant = forms.ModelChoiceField(
        queryset=Utilisateur.objects.none(),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control form-select-lg',
            'id': 'id_enseignant'
        }),
        label="Enseignant",
        help_text="Sélectionnez l'enseignant à nommer chef de département"
    )

    def __init__(self, *args, **kwargs):
        self.etablissement = kwargs.pop('etablissement', None)
        super().__init__(*args, **kwargs)

        if self.etablissement:
            # Départements sans chef
            self.fields['departement'].queryset = Departement.objects.filter(
                etablissement=self.etablissement,
                est_actif=True,
                chef__isnull=True
            ).order_by('nom')

            # Enseignants actifs (ENSEIGNANT ou CHEF_DEPARTEMENT)
            # Afficher le type d'enseignant dans le label
            enseignants = Utilisateur.objects.filter(
                etablissement=self.etablissement,
                role__in=['ENSEIGNANT', 'CHEF_DEPARTEMENT'],
                est_actif=True
            ).select_related('profil_enseignant', 'departement').order_by('nom', 'prenom')

            self.fields['enseignant'].queryset = enseignants

            # Personnaliser l'affichage
            self.fields['enseignant'].label_from_instance = lambda obj: (
                f"{obj.get_full_name()} ({obj.matricule}) - "
                f"{obj.departement.nom if obj.departement else 'Sans département'} - "
                f"{'Permanent' if hasattr(obj, 'profil_enseignant') and obj.profil_enseignant.type_enseignant == 'PERMANENT' else 'Vacataire'}"
            )

    def clean(self):
        cleaned_data = super().clean()
        enseignant = cleaned_data.get('enseignant')
        departement = cleaned_data.get('departement')

        if enseignant and departement:
            # Vérifier si l'enseignant n'est pas déjà chef d'un autre département
            autres_depts = enseignant.departements_diriges.exclude(id=departement.id)
            if autres_depts.exists():
                raise ValidationError(
                    f"{enseignant.get_full_name()} est déjà chef du département "
                    f"{autres_depts.first().nom}. Un enseignant ne peut diriger qu'un seul département."
                )

        return cleaned_data

    def save(self):
        """Nommer le chef de département"""
        departement = self.cleaned_data['departement']
        enseignant = self.cleaned_data['enseignant']

        # Retirer l'ancien chef si existant
        if departement.chef:
            ancien_chef = departement.chef
            if hasattr(ancien_chef, 'profil_enseignant'):
                # Vérifier s'il n'est pas chef d'autres départements
                if not ancien_chef.departements_diriges.exclude(id=departement.id).exists():
                    ancien_chef.profil_enseignant.est_chef_departement = False
                    ancien_chef.profil_enseignant.save()
                    ancien_chef.role = 'ENSEIGNANT'
                    ancien_chef.save()

        # Assigner le nouveau chef
        departement.chef = enseignant
        departement.save()

        # Mettre à jour le profil enseignant
        profil, created = ProfilEnseignant.objects.get_or_create(utilisateur=enseignant)
        profil.est_chef_departement = True
        profil.save()

        # Mettre à jour le rôle
        enseignant.role = 'CHEF_DEPARTEMENT'
        enseignant.save()

        # Ajouter le département aux départements d'intervention s'il n'y est pas
        if not enseignant.departements_intervention.filter(id=departement.id).exists():
            enseignant.departements_intervention.add(departement)

        return enseignant