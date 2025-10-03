from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import Utilisateur, ProfilApprenant, ProfilEnseignant, ProfilUtilisateur


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


class TeacherProfileForm(BasicProfileForm):
    """Formulaire étendu pour les enseignants"""

    # Champs du profil enseignant
    specialisation = forms.CharField(max_length=100, required=False,
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))
    qualifications = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    # Champs du profil utilisateur
    nom_contact_urgence = forms.CharField(max_length=100, required=False,
                                          widget=forms.TextInput(attrs={'class': 'form-control'}))
    telephone_contact_urgence = forms.CharField(max_length=20, required=False,
                                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    relation_contact_urgence = forms.CharField(max_length=50, required=False,
                                               widget=forms.TextInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Charger les données du profil enseignant
        if self.instance and hasattr(self.instance, 'profil_enseignant'):
            profil = self.instance.profil_enseignant
            self.fields['specialisation'].initial = profil.specialisation
            self.fields['qualifications'].initial = profil.qualifications

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

            # Sauvegarder le profil enseignant
            profil_enseignant, created = ProfilEnseignant.objects.get_or_create(utilisateur=user)
            profil_enseignant.specialisation = self.cleaned_data.get('specialisation')
            profil_enseignant.qualifications = self.cleaned_data.get('qualifications')
            profil_enseignant.save()

            # Sauvegarder le profil utilisateur
            profil_user, created = ProfilUtilisateur.objects.get_or_create(utilisateur=user)
            profil_user.nom_contact_urgence = self.cleaned_data.get('nom_contact_urgence')
            profil_user.telephone_contact_urgence = self.cleaned_data.get('telephone_contact_urgence')
            profil_user.relation_contact_urgence = self.cleaned_data.get('relation_contact_urgence')
            profil_user.save()

        return user
