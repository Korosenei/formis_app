# apps/courses/forms.py

from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    Module, Matiere, MatiereModule, Cours, CahierTexte,
    Ressource, Presence, EmploiDuTemps, CreneauHoraire,
    StatutCours, TypeCours
)


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
        fields = [
            'nom', 'code', 'description', 'niveau',
            'coordinateur', 'volume_horaire_total', 'credits_ects',
            'prerequis', 'actif'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'prerequis': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and hasattr(user, 'etablissement'):
            # Filtrer les niveaux selon l'établissement
            self.fields['niveau'].queryset = self.fields['niveau'].queryset.filter(
                filiere__departement__etablissement=user.etablissement
            )

            # Filtrer les coordinateurs (enseignants de l'établissement)
            self.fields['coordinateur'].queryset = self.fields['coordinateur'].queryset.filter(
                etablissement=user.etablissement,
                role='ENSEIGNANT'
            )

        # Widget pour les prérequis avec filtrage
        if self.instance.pk:
            self.fields['prerequis'].queryset = Module.objects.filter(
                niveau=self.instance.niveau
            ).exclude(pk=self.instance.pk)

    def clean(self):
        cleaned_data = super().clean()
        niveau = cleaned_data.get('niveau')
        code = cleaned_data.get('code')

        # Vérifier l'unicité du code dans le niveau
        if niveau and code:
            existing = Module.objects.filter(niveau=niveau, code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("Ce code existe déjà pour ce niveau.")

        return cleaned_data

class MatiereForm(forms.ModelForm):
    class Meta:
        model = Matiere
        fields = [
            'nom', 'code', 'description', 'couleur',
            'heures_theorie', 'heures_pratique', 'heures_td',
            'coefficient', 'actif'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'couleur': forms.TextInput(attrs={'type': 'color'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            existing = Matiere.objects.filter(code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("Ce code de matière existe déjà.")
        return code

class MatiereModuleForm(forms.ModelForm):
    class Meta:
        model = MatiereModule
        fields = [
            'matiere', 'module', 'heures_theorie', 'heures_pratique',
            'heures_td', 'coefficient', 'enseignant'
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and hasattr(user, 'etablissement'):
            # Filtrer les modules selon l'établissement
            self.fields['module'].queryset = Module.objects.filter(
                niveau__filiere__departement__etablissement=user.etablissement
            )

            # Filtrer les enseignants
            self.fields['enseignant'].queryset = self.fields['enseignant'].queryset.filter(
                etablissement=user.etablissement,
                role='ENSEIGNANT'
            )

    def clean(self):
        cleaned_data = super().clean()
        matiere = cleaned_data.get('matiere')
        module = cleaned_data.get('module')

        if matiere and module:
            existing = MatiereModule.objects.filter(matiere=matiere, module=module)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("Cette matière est déjà associée à ce module.")

        return cleaned_data

class CoursForm(forms.ModelForm):
    class Meta:
        model = Cours
        fields = [
            'titre', 'description', 'classe', 'matiere_module', 'enseignant',
            'periode_academique', 'type_cours', 'statut', 'date_prevue',
            'heure_debut_prevue', 'heure_fin_prevue', 'salle', 'objectifs',
            'contenu', 'prerequis', 'cours_en_ligne', 'url_streaming',
            'ressources_utilisees', 'actif'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'date_prevue': forms.DateInput(attrs={'type': 'date'}),
            'heure_debut_prevue': forms.TimeInput(attrs={'type': 'time'}),
            'heure_fin_prevue': forms.TimeInput(attrs={'type': 'time'}),
            'objectifs': forms.Textarea(attrs={'rows': 3}),
            'contenu': forms.Textarea(attrs={'rows': 4}),
            'prerequis': forms.Textarea(attrs={'rows': 2}),
            'ressources_utilisees': forms.Textarea(attrs={'rows': 3}),
            'url_streaming': forms.URLInput(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and hasattr(user, 'etablissement'):
            self.fields['classe'].queryset = self.fields['classe'].queryset.filter(
                etablissement=user.etablissement
            )
            # # self.fields['enseignant'].queryset = self.fields['enseignant'].queryset.filter(
            # #     etablissement=user.etablissement,
            # #     role='ENSEIGNANT'
            # # )
            # # self.fields['periode_academique'].queryset = self.fields['periode_academique'].queryset.filter(
            # #     etablissement=user.etablissement
            # # )
            # # self.fields['salle'].queryset = self.fields['salle'].queryset.filter(
            # #     batiment__etablissement=user.etablissement
            # # )

        # Ajouter du JavaScript pour le filtrage dynamique
        self.fields['classe'].widget.attrs.update({
            'onchange': 'filterMatiereModule(this.value)'
        })

    def clean(self):
        cleaned_data = super().clean()
        heure_debut = cleaned_data.get('heure_debut_prevue')
        heure_fin = cleaned_data.get('heure_fin_prevue')
        cours_en_ligne = cleaned_data.get('cours_en_ligne')
        url_streaming = cleaned_data.get('url_streaming')

        # Vérifier que l'heure de fin est après l'heure de début
        if heure_debut and heure_fin and heure_fin <= heure_debut:
            raise ValidationError("L'heure de fin doit être après l'heure de début.")

        # Vérifier l'URL de streaming si cours en ligne
        if cours_en_ligne and not url_streaming:
            raise ValidationError("L'URL de streaming est obligatoire pour un cours en ligne.")

        return cleaned_data


class CoursUpdateForm(CoursForm):
    """Formulaire de mise à jour avec champs supplémentaires"""

    class Meta(CoursForm.Meta):
        fields = CoursForm.Meta.fields + [
            'date_effective', 'heure_debut_effective', 'heure_fin_effective',
            'streaming_actif', 'notes_enseignant', 'retours_etudiants'
        ]
        widgets = dict(CoursForm.Meta.widgets, **{
            'date_effective': forms.DateInput(attrs={'type': 'date'}),
            'heure_debut_effective': forms.TimeInput(attrs={'type': 'time'}),
            'heure_fin_effective': forms.TimeInput(attrs={'type': 'time'}),
            'notes_enseignant': forms.Textarea(attrs={'rows': 3}),
            'retours_etudiants': forms.Textarea(attrs={'rows': 3}),
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
            etudiants = cours.classe.get_etudiants()
            for etudiant in etudiants:
                # Récupérer la présence existante si elle existe
                try:
                    presence = Presence.objects.get(cours=cours, etudiant=etudiant)
                    initial_statut = presence.statut
                    initial_heure = presence.heure_arrivee
                except Presence.DoesNotExist:
                    initial_statut = 'PRESENT'
                    initial_heure = None

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
                    widget=forms.Textarea(attrs={
                        'rows': 2,
                        'class': 'form-control'
                    })
                )


class EmploiDuTempsForm(forms.ModelForm):
    class Meta:
        model = EmploiDuTemps
        fields = [
            'nom', 'description', 'classe', 'periode_academique',
            'valide_a_partir_du', 'valide_jusqua', 'publie', 'actuel'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'valide_a_partir_du': forms.DateInput(attrs={'type': 'date'}),
            'valide_jusqua': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and hasattr(user, 'etablissement'):
            self.fields['classe'].queryset = self.fields['classe'].queryset.filter(
                niveau__filiere__departement__etablissement=user.etablissement
            )
            self.fields['periode_academique'].queryset = self.fields['periode_academique'].queryset.filter(
                etablissement=user.etablissement
            )

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('valide_a_partir_du')
        date_fin = cleaned_data.get('valide_jusqua')

        if date_debut and date_fin and date_fin <= date_debut:
            raise ValidationError("La date de fin doit être après la date de début.")

        return cleaned_data


class CreneauHoraireForm(forms.ModelForm):
    class Meta:
        model = CreneauHoraire
        fields = [
            'emploi_du_temps', 'jour', 'heure_debut', 'heure_fin',
            'matiere_module', 'enseignant', 'salle', 'type_cours',
            'recurrent', 'dates_exception'
        ]
        widgets = {
            'heure_debut': forms.TimeInput(attrs={'type': 'time'}),
            'heure_fin': forms.TimeInput(attrs={'type': 'time'}),
            'dates_exception': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Format: YYYY-MM-DD, séparées par des virgules'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        emploi_du_temps = kwargs.pop('emploi_du_temps', None)
        super().__init__(*args, **kwargs)

        if emploi_du_temps:
            self.fields['emploi_du_temps'].initial = emploi_du_temps
            self.fields['emploi_du_temps'].widget = forms.HiddenInput()

            # Filtrer les matières-modules selon la classe de l'emploi du temps
            self.fields['matiere_module'].queryset = MatiereModule.objects.filter(
                module__niveau=emploi_du_temps.classe.niveau
            )

        if user and hasattr(user, 'etablissement'):
            self.fields['enseignant'].queryset = self.fields['enseignant'].queryset.filter(
                etablissement=user.etablissement,
                role='ENSEIGNANT'
            )
            self.fields['salle'].queryset = self.fields['salle'].queryset.filter(
                batiment__etablissement=user.etablissement
            )

    def clean(self):
        cleaned_data = super().clean()
        heure_debut = cleaned_data.get('heure_debut')
        heure_fin = cleaned_data.get('heure_fin')
        emploi_du_temps = cleaned_data.get('emploi_du_temps')
        jour = cleaned_data.get('jour')
        enseignant = cleaned_data.get('enseignant')
        salle = cleaned_data.get('salle')

        # Vérifier que l'heure de fin est après l'heure de début
        if heure_debut and heure_fin and heure_fin <= heure_debut:
            raise ValidationError("L'heure de fin doit être après l'heure de début.")

        # Vérifier les conflits d'horaires pour la même classe
        if emploi_du_temps and jour and heure_debut and heure_fin:
            conflits = CreneauHoraire.objects.filter(
                emploi_du_temps=emploi_du_temps,
                jour=jour,
                heure_debut__lt=heure_fin,
                heure_fin__gt=heure_debut
            )
            if self.instance.pk:
                conflits = conflits.exclude(pk=self.instance.pk)

            if conflits.exists():
                raise ValidationError("Il y a un conflit d'horaires avec un autre créneau de cette classe.")

        # Vérifier la disponibilité de l'enseignant
        if enseignant and jour and heure_debut and heure_fin:
            conflits_enseignant = CreneauHoraire.objects.filter(
                enseignant=enseignant,
                jour=jour,
                heure_debut__lt=heure_fin,
                heure_fin__gt=heure_debut
            )
            if self.instance.pk:
                conflits_enseignant = conflits_enseignant.exclude(pk=self.instance.pk)

            if conflits_enseignant.exists():
                raise ValidationError("L'enseignant n'est pas disponible à cet horaire.")

        # Vérifier la disponibilité de la salle
        if salle and jour and heure_debut and heure_fin:
            conflits_salle = CreneauHoraire.objects.filter(
                salle=salle,
                jour=jour,
                heure_debut__lt=heure_fin,
                heure_fin__gt=heure_debut
            )
            if self.instance.pk:
                conflits_salle = conflits_salle.exclude(pk=self.instance.pk)

            if conflits_salle.exists():
                raise ValidationError("La salle n'est pas disponible à cet horaire.")

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

        # Initialiser les querysets vides
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


# Formsets pour les relations inline
MatiereModuleFormSet = inlineformset_factory(
    Module, MatiereModule, form=MatiereModuleForm,
    fields=['matiere', 'heures_theorie', 'heures_pratique', 'heures_td', 'coefficient', 'enseignant'],
    extra=1, can_delete=True
)

RessourceFormSet = inlineformset_factory(
    Cours, Ressource, form=RessourceForm,
    fields=['titre', 'description', 'type_ressource', 'fichier', 'url', 'obligatoire'],
    extra=1, can_delete=True
)

CreneauHoraireFormSet = inlineformset_factory(
    EmploiDuTemps, CreneauHoraire, form=CreneauHoraireForm,
    fields=['jour', 'heure_debut', 'heure_fin', 'matiere_module', 'enseignant', 'salle', 'type_cours'],
    extra=1, can_delete=True
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
            'motif_absence', 'document_justificatif', 'notes_enseignant'
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
                inscriptions__classe=cours.classe,
                role='APPRENANT'
            )