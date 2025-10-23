# apps/courses/forms.py

from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    Module, Matiere, Cours, CahierTexte,
    Ressource, Presence, EmploiDuTemps, CreneauEmploiDuTemps,
    StatutCours, TypeCours
)
from apps.academic.models import Niveau, Classe, PeriodeAcademique
from apps.accounts.models import Utilisateur


class FilteredModelChoiceField(forms.ModelChoiceField):
    """Champ de choix de modèle avec filtrage dynamique"""

    def __init__(self, queryset, filter_field=None, parent_field=None, **kwargs):
        self.filter_field = filter_field
        self.parent_field = parent_field
        super().__init__(queryset, **kwargs)

    def filter_queryset(self, parent_value):
        """Filtre le queryset basé sur la valeur du champ parent"""
        if self.filter_field and parent_value:
            filter_dict = {self.filter_field: parent_value}
            return self.queryset.filter(**filter_dict)
        return self.queryset

class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ['niveau', 'nom', 'code', 'description', 'coordinateur', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du module'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'niveau': forms.Select(attrs={'class': 'form-select'}),
            'coordinateur': forms.Select(attrs={'class': 'form-select'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            # Filtrer les niveaux selon le rôle
            if user.role == 'ADMIN':
                self.fields['niveau'].queryset = Niveau.objects.filter(
                    filiere__etablissement=user.etablissement,
                    est_actif=True
                ).select_related('filiere')

                self.fields['coordinateur'].queryset = Utilisateur.objects.filter(
                    etablissement=user.etablissement,
                    role='ENSEIGNANT',
                    est_actif=True
                )

            elif user.role == 'CHEF_DEPARTEMENT':
                self.fields['niveau'].queryset = Niveau.objects.filter(
                    filiere__departement=user.departement,
                    est_actif=True
                ).select_related('filiere')

                self.fields['coordinateur'].queryset = Utilisateur.objects.filter(
                    departement=user.departement,
                    role='ENSEIGNANT',
                    est_actif=True
                )

class MatiereForm(forms.ModelForm):
    class Meta:
        model = Matiere
        fields = [
            'niveau', 'module', 'nom', 'code', 'description',
            'enseignant_responsable', 'heures_cours_magistral',
            'heures_travaux_diriges', 'heures_travaux_pratiques',
            'coefficient', 'credits_ects', 'couleur', 'actif'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'niveau': forms.Select(attrs={'class': 'form-select'}),
            'module': forms.Select(attrs={'class': 'form-select'}),
            'enseignant_responsable': forms.Select(attrs={'class': 'form-select'}),
            'heures_cours_magistral': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'heures_travaux_diriges': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'heures_travaux_pratiques': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0.5'}),
            'credits_ects': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Gestion des niveaux selon rôle
        if user:
            if user.role == 'ADMIN':
                self.fields['niveau'].queryset = Niveau.objects.filter(
                    filiere__etablissement=user.etablissement,
                    est_actif=True
                ).select_related('filiere')

                self.fields['enseignant_responsable'].queryset = Utilisateur.objects.filter(
                    etablissement=user.etablissement,
                    role='ENSEIGNANT',
                    est_actif=True
                )

            elif user.role == 'CHEF_DEPARTEMENT':
                self.fields['niveau'].queryset = Niveau.objects.filter(
                    filiere__departement=user.departement,
                    est_actif=True
                ).select_related('filiere')

                self.fields['enseignant_responsable'].queryset = Utilisateur.objects.filter(
                    departement=user.departement,
                    role='ENSEIGNANT',
                    est_actif=True
                )

        # Module optionnel
        self.fields['module'].required = False
        self.fields['module'].empty_label = "Aucun module"
        self.fields['module'].queryset = Module.objects.none()

        # Si UpdateView, remplir les modules correspondant au niveau existant
        if self.instance.pk and getattr(self.instance, 'niveau_id', None):
            self.fields['module'].queryset = Module.objects.filter(
                niveau_id=self.instance.niveau_id,
                actif=True
            )

    def clean(self):
        cleaned_data = super().clean()
        niveau = cleaned_data.get('niveau')
        module = cleaned_data.get('module')

        # Vérifier que le module correspond au niveau sélectionné
        if module and niveau and module.niveau != niveau:
            raise forms.ValidationError(
                "Le module sélectionné n'appartient pas au niveau choisi."
            )

        return cleaned_data

class CoursForm(forms.ModelForm):
    class Meta:
        model = Cours
        fields = [
            'matiere', 'classe', 'enseignant', 'periode_academique',
            'titre', 'description', 'type_cours', 'date_prevue',
            'heure_debut_prevue', 'heure_fin_prevue', 'salle',
            'objectifs', 'cours_en_ligne', 'url_streaming'
        ]
        widgets = {
            'matiere': forms.Select(attrs={'class': 'form-select'}),
            'classe': forms.Select(attrs={'class': 'form-select'}),
            'enseignant': forms.Select(attrs={'class': 'form-select'}),
            'periode_academique': forms.Select(attrs={'class': 'form-select'}),
            'titre': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'type_cours': forms.Select(attrs={'class': 'form-select'}),
            'date_prevue': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'heure_debut_prevue': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fin_prevue': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'salle': forms.Select(attrs={'class': 'form-select'}),
            'objectifs': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cours_en_ligne': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'url_streaming': forms.URLInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            if user.role == 'ADMIN':
                self.fields['matiere'].queryset = Matiere.objects.filter(
                    niveau__filiere__etablissement=user.etablissement,
                    actif=True
                ).select_related('niveau')

                self.fields['classe'].queryset = Classe.objects.filter(
                    etablissement=user.etablissement,
                    est_active=True
                ).select_related('niveau')

                self.fields['enseignant'].queryset = Utilisateur.objects.filter(
                    etablissement=user.etablissement,
                    role='ENSEIGNANT',
                    est_actif=True
                )

                self.fields['periode_academique'].queryset = PeriodeAcademique.objects.filter(
                    etablissement=user.etablissement,
                    est_active=True
                )

            elif user.role == 'CHEF_DEPARTEMENT':
                self.fields['matiere'].queryset = Matiere.objects.filter(
                    niveau__filiere__departement=user.departement,
                    actif=True
                ).select_related('niveau')

                self.fields['classe'].queryset = Classe.objects.filter(
                    niveau__filiere__departement=user.departement,
                    est_active=True
                ).select_related('niveau')

                self.fields['enseignant'].queryset = Utilisateur.objects.filter(
                    departement=user.departement,
                    role='ENSEIGNANT',
                    est_actif=True
                )

                self.fields['periode_academique'].queryset = PeriodeAcademique.objects.filter(
                    etablissement=user.etablissement,
                    est_active=True
                )

class EmploiDuTempsForm(forms.ModelForm):
    class Meta:
        model = EmploiDuTemps
        fields = [
            'classe', 'enseignant', 'periode_academique',
            'nom', 'semaine_debut', 'semaine_fin',
            'publie', 'actuel'
        ]
        widgets = {
            'classe': forms.Select(attrs={'class': 'form-select'}),
            'enseignant': forms.Select(attrs={'class': 'form-select'}),
            'periode_academique': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'semaine_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'semaine_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'publie': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'actuel': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Soit classe, soit enseignant (pas les deux)
        self.fields['classe'].required = False
        self.fields['enseignant'].required = False

        if user:
            if user.role == 'ADMIN':
                self.fields['classe'].queryset = Classe.objects.filter(
                    etablissement=user.etablissement,
                    est_active=True
                )
                self.fields['enseignant'].queryset = Utilisateur.objects.filter(
                    etablissement=user.etablissement,
                    role='ENSEIGNANT',
                    est_actif=True
                )
                self.fields['periode_academique'].queryset = PeriodeAcademique.objects.filter(
                    etablissement=user.etablissement,
                    est_active=True
                )

            elif user.role == 'CHEF_DEPARTEMENT':
                self.fields['classe'].queryset = Classe.objects.filter(
                    niveau__filiere__departement=user.departement,
                    est_active=True
                )
                self.fields['enseignant'].queryset = Utilisateur.objects.filter(
                    departement=user.departement,
                    role='ENSEIGNANT',
                    est_actif=True
                )
                self.fields['periode_academique'].queryset = PeriodeAcademique.objects.filter(
                    etablissement=user.etablissement,
                    est_active=True
                )

    def clean(self):
        cleaned_data = super().clean()
        classe = cleaned_data.get('classe')
        enseignant = cleaned_data.get('enseignant')

        if not classe and not enseignant:
            raise forms.ValidationError(
                "Vous devez sélectionner soit une classe, soit un enseignant."
            )

        if classe and enseignant:
            raise forms.ValidationError(
                "Vous ne pouvez pas sélectionner à la fois une classe et un enseignant."
            )

        return cleaned_data


class CoursUpdateForm(CoursForm):
    """Formulaire de mise à jour avec champs supplémentaires"""

    class Meta(CoursForm.Meta):
        fields = CoursForm.Meta.fields + [
            'date_effective', 'heure_debut_effective', 'heure_fin_effective',
            'presence_prise'
        ]
        widgets = dict(CoursForm.Meta.widgets, **{
            'date_effective': forms.DateInput(attrs={'type': 'date'}),
            'heure_debut_effective': forms.TimeInput(attrs={'type': 'time'}),
            'heure_fin_effective': forms.TimeInput(attrs={'type': 'time'}),
        })

class CahierTexteForm(forms.ModelForm):
    class Meta:
        model = CahierTexte
        fields = [
            'cours', 'travail_fait', 'travail_donne',
            'date_travail_pour', 'observations'
        ]
        widgets = {
            'travail_fait': forms.Textarea(attrs={'rows': 4, 'required': True}),
            'travail_donne': forms.Textarea(attrs={'rows': 3}),
            'date_travail_pour': forms.DateInput(attrs={'type': 'date'}),
            'observations': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        cours = kwargs.pop('cours', None)
        super().__init__(*args, **kwargs)

        if cours:
            self.fields['cours'].initial = cours
            self.fields['cours'].widget = forms.HiddenInput()
        elif user and hasattr(user, 'etablissement'):
            # Filtrer les cours selon l'établissement et l'enseignant
            self.fields['cours'].queryset = Cours.objects.filter(
                classe__niveau__filiere__departement__etablissement=user.etablissement,
                enseignant=user
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.rempli_par_id:
            # L'utilisateur sera assigné dans la vue
            pass
        if commit:
            instance.save()
        return instance

class RessourceForm(forms.ModelForm):
    class Meta:
        model = Ressource
        fields = [
            'cours', 'titre', 'description', 'type_ressource',
            'fichier', 'url', 'obligatoire', 'telechargeable',
            'public', 'disponible_a_partir_de', 'disponible_jusqua'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'disponible_a_partir_de': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
            'disponible_jusqua': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        cours = kwargs.pop('cours', None)
        super().__init__(*args, **kwargs)

        if cours:
            self.fields['cours'].initial = cours
            self.fields['cours'].widget = forms.HiddenInput()
        elif user and hasattr(user, 'etablissement'):
            self.fields['cours'].queryset = Cours.objects.filter(
                classe__niveau__filiere__departement__etablissement=user.etablissement
            )

    def clean(self):
        cleaned_data = super().clean()
        fichier = cleaned_data.get('fichier')
        url = cleaned_data.get('url')
        type_ressource = cleaned_data.get('type_ressource')

        # Au moins un fichier ou une URL doit être fourni
        if not fichier and not url:
            raise ValidationError("Vous devez fournir soit un fichier, soit une URL.")

        # Si c'est un lien web, l'URL est obligatoire
        if type_ressource == 'LINK' and not url:
            raise ValidationError("Une URL est obligatoire pour un lien web.")

        return cleaned_data

class PresenceForm(forms.ModelForm):
    class Meta:
        model = Presence
        fields = [
            'cours', 'etudiant', 'statut', 'heure_arrivee',
            'motif_absence', 'document_justificatif', 'valide', 'notes_enseignant'
        ]
        widgets = {
            'heure_arrivee': forms.TimeInput(attrs={'type': 'time'}),
            'motif_absence': forms.Textarea(attrs={'rows': 3}),
            'notes_enseignant': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        cours = kwargs.pop('cours', None)
        super().__init__(*args, **kwargs)

        if cours:
            self.fields['cours'].initial = cours
            self.fields['cours'].widget = forms.HiddenInput()
            # Filtrer les étudiants de la classe du cours
            self.fields['etudiant'].queryset = self.fields['etudiant'].queryset.filter(
                classe_inscrite=cours.classe,
                role='ETUDIANT'
            ).distinct()

    def clean(self):
        cleaned_data = super().clean()
        statut = cleaned_data.get('statut')
        heure_arrivee = cleaned_data.get('heure_arrivee')
        motif_absence = cleaned_data.get('motif_absence')

        # Si retard, heure d'arrivée obligatoire
        if statut == 'LATE' and not heure_arrivee:
            raise ValidationError("L'heure d'arrivée est obligatoire pour un retard.")

        # Si absence, motif recommandé
        if statut in ['ABSENT', 'EXCUSED', 'JUSTIFIED'] and not motif_absence:
            self.add_error('motif_absence', "Un motif d'absence est recommandé.")

        return cleaned_data

class PresenceBulkForm(forms.Form):
    """Formulaire pour la prise de présence en lot"""

    def __init__(self, *args, **kwargs):
        cours = kwargs.pop('cours', None)
        super().__init__(*args, **kwargs)

        if cours:
            # Récupérer les étudiants de la classe
            etudiants = cours.classe.etudiants.all()
            for etudiant in etudiants:
                # Récupérer la présence existante si elle existe
                try:
                    presence = Presence.objects.get(cours=cours, etudiant=etudiant)
                    initial_statut = presence.statut
                    initial_heure = presence.heure_arrivee
                    initial_motif = presence.motif_absence
                except Presence.DoesNotExist:
                    initial_statut = 'PRESENT'
                    initial_heure = None
                    initial_motif = ''

                # Champ statut pour chaque étudiant
                self.fields[f'statut_{etudiant.id}'] = forms.ChoiceField(
                    choices=Presence.STATUTS_PRESENCE,
                    initial=initial_statut,
                    label=etudiant.get_full_name(),
                    widget=forms.Select(attrs={'class': 'form-control'})
                )

                # Champ heure d'arrivée pour les retards
                self.fields[f'heure_{etudiant.id}'] = forms.TimeField(
                    required=False,
                    initial=initial_heure,
                    widget=forms.TimeInput(attrs={
                        'type': 'time',
                        'class': 'form-control'
                    })
                )

                # Champ motif d'absence
                self.fields[f'motif_{etudiant.id}'] = forms.CharField(
                    required=False,
                    initial=initial_motif,
                    widget=forms.Textarea(attrs={
                        'rows': 2,
                        'class': 'form-control',
                        'placeholder': 'Motif d\'absence...'
                    })
                )

class CreneauEmploiDuTempsForm(forms.ModelForm):
    class Meta:
        model = CreneauEmploiDuTemps
        fields = [
            'emploi_du_temps', 'cours', 'jour_semaine',
            'heure_debut', 'heure_fin'
        ]
        widgets = {
            'heure_debut': forms.TimeInput(attrs={'type': 'time'}),
            'heure_fin': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        emploi_du_temps = kwargs.pop('emploi_du_temps', None)
        super().__init__(*args, **kwargs)

        if emploi_du_temps:
            self.fields['emploi_du_temps'].initial = emploi_du_temps
            self.fields['emploi_du_temps'].widget = forms.HiddenInput()

            # Filtrer les cours selon la cible de l'emploi du temps
            if emploi_du_temps.classe:
                self.fields['cours'].queryset = Cours.objects.filter(
                    classe=emploi_du_temps.classe
                )
            elif emploi_du_temps.enseignant:
                self.fields['cours'].queryset = Cours.objects.filter(
                    enseignant=emploi_du_temps.enseignant
                )

        if user and hasattr(user, 'etablissement'):
            self.fields['cours'].queryset = self.fields['cours'].queryset.filter(
                classe__niveau__filiere__departement__etablissement=user.etablissement
            )

    def clean(self):
        cleaned_data = super().clean()
        heure_debut = cleaned_data.get('heure_debut')
        heure_fin = cleaned_data.get('heure_fin')
        emploi_du_temps = cleaned_data.get('emploi_du_temps')
        jour_semaine = cleaned_data.get('jour_semaine')
        cours = cleaned_data.get('cours')

        # Vérifier que l'heure de fin est après l'heure de début
        if heure_debut and heure_fin and heure_fin <= heure_debut:
            raise ValidationError("L'heure de fin doit être après l'heure de début.")

        # Vérifier les conflits d'horaires
        if emploi_du_temps and jour_semaine and heure_debut and heure_fin:
            conflits = CreneauEmploiDuTemps.objects.filter(
                emploi_du_temps=emploi_du_temps,
                jour_semaine=jour_semaine,
                heure_debut__lt=heure_fin,
                heure_fin__gt=heure_debut
            )
            if self.instance.pk:
                conflits = conflits.exclude(pk=self.instance.pk)

            if conflits.exists():
                raise ValidationError("Il y a un conflit d'horaires avec un autre créneau.")

        # Vérifier que le cours correspond à la cible de l'emploi du temps
        if cours and emploi_du_temps:
            if emploi_du_temps.classe and cours.classe != emploi_du_temps.classe:
                raise ValidationError("Le cours sélectionné ne correspond pas à la classe de l'emploi du temps.")
            elif emploi_du_temps.enseignant and cours.enseignant != emploi_du_temps.enseignant:
                raise ValidationError("Le cours sélectionné ne correspond pas à l'enseignant de l'emploi du temps.")

        return cleaned_data

class FiltreCoursForm(forms.Form):
    """Formulaire de filtrage pour les cours"""
    etablissement = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Tous les établissements",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    departement = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Tous les départements",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    filiere = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Toutes les filières",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    niveau = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Tous les niveaux",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    classe = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Toutes les classes",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    enseignant = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Tous les enseignants",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    matiere = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Toutes les matières",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    type_cours = forms.ChoiceField(
        choices=[('', 'Tous les types')] + TypeCours.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    statut = forms.ChoiceField(
        choices=[('', 'Tous les statuts')] + StatutCours.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Initialiser les querysets
        from apps.establishments.models import Etablissement
        from apps.academic.models import Departement, Filiere, Niveau, Classe
        from apps.accounts.models import Utilisateur

        if user and hasattr(user, 'etablissement'):
            # Filtrer selon l'établissement de l'utilisateur
            self.fields['etablissement'].queryset = Etablissement.objects.filter(
                id=user.etablissement.id
            )
            self.fields['departement'].queryset = Departement.objects.filter(
                etablissement=user.etablissement
            )
            self.fields['filiere'].queryset = Filiere.objects.filter(
                departement__etablissement=user.etablissement
            )
            self.fields['niveau'].queryset = Niveau.objects.filter(
                filiere__departement__etablissement=user.etablissement
            )
            self.fields['classe'].queryset = Classe.objects.filter(
                niveau__filiere__departement__etablissement=user.etablissement
            )
            self.fields['enseignant'].queryset = Utilisateur.objects.filter(
                etablissement=user.etablissement,
                role='ENSEIGNANT'
            )
            self.fields['matiere'].queryset = Matiere.objects.filter(
                niveau__filiere__departement__etablissement=user.etablissement
            )
        else:
            # Pour un super utilisateur, afficher tous les éléments
            self.fields['etablissement'].queryset = Etablissement.objects.all()
            self.fields['departement'].queryset = Departement.objects.all()
            self.fields['filiere'].queryset = Filiere.objects.all()
            self.fields['niveau'].queryset = Niveau.objects.all()
            self.fields['classe'].queryset = Classe.objects.all()
            self.fields['enseignant'].queryset = Utilisateur.objects.filter(
                role='ENSEIGNANT'
            )
            self.fields['matiere'].queryset = Matiere.objects.all()


# Formsets pour les relations inline
RessourceFormSet = inlineformset_factory(
    Cours, Ressource, form=RessourceForm,
    fields=['titre', 'description', 'type_ressource', 'fichier', 'url', 'obligatoire'],
    extra=1, can_delete=True
)

CreneauEmploiDuTempsFormSet = inlineformset_factory(
    EmploiDuTemps, CreneauEmploiDuTemps, form=CreneauEmploiDuTempsForm,
    fields=['cours', 'jour_semaine', 'heure_debut', 'heure_fin'],
    extra=1, can_delete=True
)