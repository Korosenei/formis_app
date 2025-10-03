from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Departement, Filiere, Niveau, Classe, PeriodeAcademique, Programme
from apps.accounts.models import Utilisateur


class DepartementForm(forms.ModelForm):
    """Formulaire de département"""

    class Meta:
        model = Departement
        fields = ['nom', 'code', 'description', 'chef', 'telephone', 'email', 'bureau', 'est_actif']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Département Informatique'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: DEPT-INFO'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description du département...'
            }),
            'chef': forms.Select(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+226 XX XX XX XX'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemple.com'
            }),
            'bureau': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Bâtiment A, 2ème étage'
            }),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filtrer les chefs de département de l'établissement
        if self.user:
            self.fields['chef'].queryset = Utilisateur.objects.filter(
                etablissement=self.user.etablissement,
                role='CHEF_DEPARTEMENT',
                est_actif=True
            )

        # Marquer les champs obligatoires
        self.fields['nom'].required = True
        self.fields['code'].required = True

class FiliereForm(forms.ModelForm):
    """Formulaire de filière"""

    class Meta:
        model = Filiere
        fields = [
            'departement', 'nom', 'code', 'description', 'duree_annees',
            'nom_diplome', 'type_filiere', 'prerequis', 'frais_scolarite',
            'capacite_maximale', 'est_active'
        ]
        widgets = {
            'departement': forms.Select(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Licence en Informatique'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: LIC-INFO'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description de la filière...'
            }),
            'duree_annees': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10
            }),
            'nom_diplome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Licence Professionnelle'
            }),
            'type_filiere': forms.Select(attrs={'class': 'form-control'}),
            'prerequis': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Prérequis pour intégrer la filière...'
            }),
            'frais_scolarite': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'capacite_maximale': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Nombre total de places'
            }),
            'est_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filtrer les départements de l'établissement
        if self.user:
            self.fields['departement'].queryset = Departement.objects.filter(
                etablissement=self.user.etablissement,
                est_actif=True
            )

        # Marquer les champs obligatoires
        self.fields['nom'].required = True
        self.fields['code'].required = True
        self.fields['duree_annees'].required = True
        self.fields['nom_diplome'].required = True
        self.fields['type_filiere'].required = True

class NiveauForm(forms.ModelForm):
    """Formulaire de niveau"""

    class Meta:
        model = Niveau
        fields = ['filiere', 'nom', 'code', 'ordre', 'description', 'frais_scolarite', 'est_actif']
        widgets = {
            'filiere': forms.Select(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 1ère année'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: L1'
            }),
            'ordre': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': '1'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'frais_scolarite': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filtrer les filières de l'établissement
        if self.user:
            self.fields['filiere'].queryset = Filiere.objects.filter(
                etablissement=self.user.etablissement,
                est_active=True
            )

class ClasseForm(forms.ModelForm):
    """Formulaire de classe"""

    class Meta:
        model = Classe
        fields = [
            'niveau', 'annee_academique', 'nom', 'code',
            'professeur_principal', 'salle_principale',
            'capacite_maximale', 'est_active'
        ]
        widgets = {
            'niveau': forms.Select(attrs={'class': 'form-control'}),
            'annee_academique': forms.Select(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: L1-INFO-A'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: L1INFA'
            }),
            'professeur_principal': forms.Select(attrs={'class': 'form-control'}),
            'salle_principale': forms.Select(attrs={'class': 'form-control'}),
            'capacite_maximale': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'est_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            from apps.establishments.models import AnneeAcademique, Salle

            # Filtrer par établissement
            self.fields['niveau'].queryset = Niveau.objects.filter(
                filiere__etablissement=self.user.etablissement,
                est_actif=True
            )
            self.fields['annee_academique'].queryset = AnneeAcademique.objects.filter(
                etablissement=self.user.etablissement
            )
            self.fields['professeur_principal'].queryset = Utilisateur.objects.filter(
                etablissement=self.user.etablissement,
                role='ENSEIGNANT',
                est_actif=True
            )
            self.fields['salle_principale'].queryset = Salle.objects.filter(
                etablissement=self.user.etablissement,
                est_disponible=True
            )

class PeriodeAcademiqueForm(forms.ModelForm):
    class Meta:
        model = PeriodeAcademique
        fields = [
            'etablissement', 'annee_academique', 'nom', 'code', 'type_periode',
            'ordre', 'date_debut', 'date_fin', 'date_limite_inscription',
            'date_debut_examens', 'date_fin_examens', 'date_publication_resultats',
            'est_courante', 'est_active'
        ]
        widgets = {
            'etablissement': forms.Select(attrs={'class': 'form-select'}),
            'annee_academique': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'type_periode': forms.Select(attrs={'class': 'form-select'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_limite_inscription': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_debut_examens': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin_examens': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_publication_resultats': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'est_courante': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'est_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        
        if date_debut and date_fin:
            if date_debut >= date_fin:
                raise ValidationError("La date de début doit être antérieure à la date de fin.")
        
        # Validation des dates d'examens
        date_debut_examens = cleaned_data.get('date_debut_examens')
        date_fin_examens = cleaned_data.get('date_fin_examens')
        
        if date_debut_examens and date_fin_examens:
            if date_debut_examens >= date_fin_examens:
                raise ValidationError(
                    "La date de début des examens doit être antérieure à la date de fin des examens."
                )
        
        return cleaned_data

class ProgrammeForm(forms.ModelForm):
    class Meta:
        model = Programme
        fields = [
            'filiere', 'nom', 'description', 'objectifs', 'competences',
            'debouches', 'credits_totaux', 'date_derniere_revision',
            'approuve_par', 'date_approbation', 'est_actif'
        ]
        widgets = {
            'filiere': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'objectifs': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'competences': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'debouches': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'credits_totaux': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'date_derniere_revision': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'approuve_par': forms.Select(attrs={'class': 'form-select'}),
            'date_approbation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_date_approbation(self):
        date_approbation = self.cleaned_data.get('date_approbation')
        approuve_par = self.cleaned_data.get('approuve_par')
        
        if date_approbation and not approuve_par:
            raise ValidationError(
                "Si une date d'approbation est fournie, l'approbateur doit être spécifié."
            )
        
        if approuve_par and not date_approbation:
            raise ValidationError(
                "Si un approbateur est spécifié, la date d'approbation doit être fournie."
            )
        
        return date_approbation


# Formulaires de recherche et de filtrage
class DepartementFilterForm(forms.Form):
    etablissement = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Tous les établissements"
    )
    est_actif = forms.ChoiceField(
        choices=[('', 'Tous'), ('True', 'Actifs'), ('False', 'Inactifs')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher par nom, code ou email...'
        })
    )

    def __init__(self, *args, **kwargs):
        from apps.establishments.models import Etablissement
        super().__init__(*args, **kwargs)
        self.fields['etablissement'].queryset = Etablissement.objects.filter(actif=True)

class FiliereFilterForm(forms.Form):
    etablissement = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Tous les établissements"
    )
    type_filiere = forms.ChoiceField(
        choices=[('', 'Tous les types')] + Filiere.TYPES_FILIERE,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    est_active = forms.ChoiceField(
        choices=[('', 'Toutes'), ('True', 'Actives'), ('False', 'Inactives')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher par nom, code ou diplôme...'
        })
    )

    def __init__(self, *args, **kwargs):
        from apps.establishments.models import Etablissement
        super().__init__(*args, **kwargs)
        self.fields['etablissement'].queryset = Etablissement.objects.filter(est_actif=True)
