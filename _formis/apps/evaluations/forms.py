from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.forms.widgets import DateTimeInput, CheckboxSelectMultiple
from django.db.models import Q
from django.forms import MultiValueField, FileField
from .models import Evaluation, Composition, FichierComposition, Note
from apps.courses.models import MatiereModule
from apps.academic.models import Classe
from apps.establishments.models import AnneeAcademique


class DateTimeWidget(DateTimeInput):
    """Widget personnalisé pour les champs datetime"""
    input_type = 'datetime-local'

    def format_value(self, value):
        if value is None:
            return ''
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%dT%H:%M')
        return value

class EvaluationForm(forms.ModelForm):
    """Formulaire de création et modification d'évaluation"""

    class Meta:
        model = Evaluation
        fields = [
            'matiere_module', 'titre', 'description', 'type_evaluation',
            'coefficient', 'note_maximale', 'date_debut', 'date_fin',
            'duree_minutes', 'fichier_evaluation', 'fichier_correction',
            'correction_visible_immediatement', 'date_publication_correction',
            'autorise_retard', 'penalite_retard', 'classes'
        ]
        widgets = {
            'date_debut': DateTimeWidget(attrs={
                'class': 'form-control',
                'required': True
            }),
            'date_fin': DateTimeWidget(attrs={
                'class': 'form-control',
                'required': True
            }),
            'date_publication_correction': DateTimeWidget(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Description détaillée de l\'évaluation (optionnel)...'
            }),
            'titre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Contrôle continu n°1',
                'maxlength': 200
            }),
            'classes': CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'coefficient': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0.1',
                'max': '10',
                'class': 'form-control'
            }),
            'note_maximale': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '1',
                'max': '100',
                'class': 'form-control',
                'value': '20'
            }),
            'penalite_retard': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'max': '100',
                'class': 'form-control',
                'placeholder': '0'
            }),
            'duree_minutes': forms.NumberInput(attrs={
                'min': '1',
                'max': '480',
                'class': 'form-control',
                'placeholder': 'Ex: 120'
            }),
            'matiere_module': forms.Select(attrs={
                'class': 'form-control'
            }),
            'type_evaluation': forms.Select(attrs={
                'class': 'form-control'
            }),
            'fichier_evaluation': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.txt'
            }),
            'fichier_correction': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.txt'
            }),
            'correction_visible_immediatement': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'autorise_retard': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrer les matières selon l'enseignant connecté
        if user and user.role == 'ENSEIGNANT':
            self.fields['matiere_module'].queryset = MatiereModule.objects.filter(
                enseignant=user
            ).select_related('matiere', 'module')

            # Filtrer les classes selon les matières de l'enseignant
            classes_ids = MatiereModule.objects.filter(
                enseignant=user
            ).values_list('module__classes', flat=True)
            self.fields['classes'].queryset = Classe.objects.filter(
                id__in=classes_ids
            ).distinct()
        else:
            self.fields['matiere_module'].queryset = MatiereModule.objects.none()
            self.fields['classes'].queryset = Classe.objects.none()

        # Configuration des champs requis
        self.fields['fichier_evaluation'].required = True
        self.fields['classes'].required = True

        # Labels et textes d'aide personnalisés
        self.fields['date_debut'].label = "Date et heure de début"
        self.fields['date_fin'].label = "Date et heure de fin"
        self.fields['duree_minutes'].help_text = "Durée indicative en minutes (optionnel)"
        self.fields['coefficient'].help_text = "Coefficient de l'évaluation dans la matière"
        self.fields['penalite_retard'].help_text = "Pourcentage de pénalité appliqué en cas de retard"
        self.fields['fichier_evaluation'].help_text = "Formats acceptés: PDF, DOC, DOCX, TXT (Max: 50MB)"
        self.fields['fichier_correction'].help_text = "Correction générale (optionnel)"
        self.fields['date_publication_correction'].help_text = "Laisser vide si correction immédiate"

        # Pré-remplissage pour une nouvelle évaluation
        if not self.instance.pk:
            self.fields['note_maximale'].initial = 20
            self.fields['coefficient'].initial = 1.0
            self.fields['correction_visible_immediatement'].initial = False
            self.fields['autorise_retard'].initial = False

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        correction_visible_immediatement = cleaned_data.get('correction_visible_immediatement')
        date_publication_correction = cleaned_data.get('date_publication_correction')
        autorise_retard = cleaned_data.get('autorise_retard')
        penalite_retard = cleaned_data.get('penalite_retard')
        coefficient = cleaned_data.get('coefficient')
        matiere_module = cleaned_data.get('matiere_module')

        # Validation des dates
        if date_debut and date_fin:
            if date_fin <= date_debut:
                raise ValidationError({
                    'date_fin': "La date de fin doit être postérieure à la date de début."
                })

            # Vérifier que la durée n'est pas trop courte (minimum 5 minutes)
            duree = date_fin - date_debut
            if duree.total_seconds() < 300:  # 5 minutes
                raise ValidationError({
                    'date_fin': "La durée de l'évaluation doit être d'au moins 5 minutes."
                })

            # Vérifier que la date de début n'est pas trop dans le passé (sauf modification)
            if not self.instance.pk and date_debut <= timezone.now():
                raise ValidationError({
                    'date_debut': "La date de début ne peut pas être dans le passé."
                })

        # Validation de la publication de correction
        if not correction_visible_immediatement and not date_publication_correction:
            raise ValidationError(
                "Vous devez soit autoriser la correction visible immédiatement, "
                "soit définir une date de publication de correction."
            )

        # Validation de la date de publication
        if date_publication_correction:
            if date_debut and date_publication_correction < date_debut:
                raise ValidationError({
                    'date_publication_correction':
                        "La date de publication ne peut pas être antérieure au début de l'évaluation."
                })

        # Validation pénalité retard
        if not autorise_retard and penalite_retard and penalite_retard > 0:
            cleaned_data['penalite_retard'] = 0

        # Validation du coefficient par rapport à la matière
        if coefficient and matiere_module:
            # Calculer la somme des coefficients existants pour cette matière
            total_coefficients = Evaluation.objects.filter(
                matiere_module=matiere_module,
                statut__in=['PROGRAMMEE', 'EN_COURS', 'TERMINEE']
            ).exclude(pk=self.instance.pk).aggregate(
                total=models.Sum('coefficient')
            )['total'] or 0

            total_avec_cette_eval = total_coefficients + coefficient
            if total_avec_cette_eval > matiere_module.coefficient:
                raise ValidationError({
                    'coefficient':
                        f"La somme des coefficients ({total_avec_cette_eval}) ne peut pas "
                        f"dépasser le coefficient de la matière ({matiere_module.coefficient})"
                })

        return cleaned_data

    def clean_fichier_evaluation(self):
        fichier = self.cleaned_data.get('fichier_evaluation')
        if fichier:
            # Vérifier la taille (50MB max)
            if fichier.size > 50 * 1024 * 1024:
                raise ValidationError("Le fichier ne doit pas dépasser 50MB.")

            # Vérifier l'extension
            allowed_extensions = ['pdf', 'doc', 'docx', 'txt']
            extension = fichier.name.split('.')[-1].lower()
            if extension not in allowed_extensions:
                raise ValidationError(
                    f"Extension '{extension}' non autorisée. "
                    f"Extensions autorisées: {', '.join(allowed_extensions)}"
                )

        return fichier

class CompositionUploadForm(forms.Form):
    """Formulaire d'upload de fichiers de composition"""

    fichiers = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.doc,.docx,.txt,.jpg,.jpeg,.png'
        }),
        help_text="Formats acceptés: PDF, DOC, DOCX, TXT, JPG, PNG (Max: 10MB par fichier)",
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forcer l'attribut multiple dans le HTML
        self.fields['fichiers'].widget.attrs['multiple'] = True

    def clean_fichiers(self):
        # Récupérer tous les fichiers
        fichiers = self.files.getlist('fichiers')

        if not fichiers:
            raise ValidationError("Vous devez sélectionner au moins un fichier.")

        # Vérifications pour chaque fichier
        max_size = 10 * 1024 * 1024  # 10MB
        max_files = 10  # Maximum 10 fichiers
        allowed_extensions = ['pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png']

        if len(fichiers) > max_files:
            raise ValidationError(f"Vous ne pouvez pas uploader plus de {max_files} fichiers.")

        for fichier in fichiers:
            # Vérifier la taille
            if fichier.size > max_size:
                raise ValidationError(
                    f"Le fichier '{fichier.name}' dépasse la taille maximale de 10MB."
                )

            # Vérifier l'extension
            extension = fichier.name.split('.')[-1].lower() if '.' in fichier.name else ''
            if extension not in allowed_extensions:
                raise ValidationError(
                    f"Le fichier '{fichier.name}' a une extension non autorisée. "
                    f"Extensions autorisées: {', '.join(allowed_extensions)}"
                )

            # Vérifier que le nom n'est pas vide
            if not fichier.name.strip():
                raise ValidationError("Nom de fichier invalide.")

        return fichiers

class CorrectionForm(forms.ModelForm):
    """Formulaire de correction d'une composition"""

    class Meta:
        model = Composition
        fields = ['commentaire_correction', 'fichier_correction_personnalise']
        widgets = {
            'commentaire_correction': forms.Textarea(attrs={
                'rows': 6,
                'class': 'form-control',
                'placeholder': 'Commentaires détaillés sur la composition de l\'étudiant...'
            }),
            'fichier_correction_personnalise': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.txt'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['commentaire_correction'].label = "Commentaires"
        self.fields['fichier_correction_personnalise'].label = "Correction personnalisée"
        self.fields['fichier_correction_personnalise'].help_text = (
            "Correction spécifique pour cet étudiant (optionnel) - Formats: PDF, DOC, DOCX, TXT"
        )

    def clean_fichier_correction_personnalise(self):
        fichier = self.cleaned_data.get('fichier_correction_personnalise')
        if fichier:
            # Vérifier la taille (20MB max)
            if fichier.size > 20 * 1024 * 1024:
                raise ValidationError("Le fichier de correction ne doit pas dépasser 20MB.")

            # Vérifier l'extension
            allowed_extensions = ['pdf', 'doc', 'docx', 'txt']
            extension = fichier.name.split('.')[-1].lower()
            if extension not in allowed_extensions:
                raise ValidationError(
                    f"Extension '{extension}' non autorisée pour la correction. "
                    f"Extensions autorisées: {', '.join(allowed_extensions)}"
                )

        return fichier

class NoteForm(forms.ModelForm):
    """Formulaire d'attribution de note"""

    class Meta:
        model = Note
        fields = ['valeur', 'note_sur', 'commentaire']
        widgets = {
            'valeur': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'class': 'form-control form-control-lg text-center',
                'placeholder': '0.00'
            }),
            'note_sur': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '1',
                'class': 'form-control',
                'readonly': True
            }),
            'commentaire': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Commentaire sur la note attribuée (optionnel)...'
            })
        }

    def __init__(self, *args, evaluation=None, **kwargs):
        super().__init__(*args, **kwargs)

        if evaluation:
            # Pré-remplir avec la note maximale de l'évaluation
            self.fields['note_sur'].initial = evaluation.note_maximale
            self.fields['valeur'].widget.attrs['max'] = str(evaluation.note_maximale)

        self.fields['valeur'].label = "Note obtenue"
        self.fields['note_sur'].label = "Note sur"
        self.fields['commentaire'].label = "Commentaire"
        self.fields['commentaire'].required = False

    def clean(self):
        cleaned_data = super().clean()
        valeur = cleaned_data.get('valeur')
        note_sur = cleaned_data.get('note_sur')

        if valeur is not None and note_sur is not None:
            if valeur > note_sur:
                raise ValidationError({
                    'valeur': "La note ne peut pas être supérieure à la note maximale."
                })
            if valeur < 0:
                raise ValidationError({
                    'valeur': "La note ne peut pas être négative."
                })

        return cleaned_data


class EvaluationSearchForm(forms.Form):
    """Formulaire de recherche et filtrage des évaluations"""

    STATUT_CHOICES = [('', 'Tous les statuts')] + list(Evaluation.STATUT)  # Correction ici
    TYPE_CHOICES = [('', 'Tous les types')] + list(Evaluation.TYPE_EVALUATION)  # Correction ici

    titre = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher par titre...'
        })
    )

    type_evaluation = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    statut = forms.ChoiceField(
        choices=STATUT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    matiere = forms.ModelChoiceField(
        queryset=MatiereModule.objects.none(),
        required=False,
        empty_label="Toutes les matières",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    classe = forms.ModelChoiceField(
        queryset=Classe.objects.none(),
        required=False,
        empty_label="Toutes les classes",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label="À partir du"
    )

    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label="Jusqu'au"
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user and user.role == 'ENSEIGNANT':
            # Filtrer selon les matières de l'enseignant
            self.fields['matiere'].queryset = MatiereModule.objects.filter(
                enseignant=user
            ).select_related('matiere', 'module')

            # Filtrer les classes selon les matières de l'enseignant
            classes_ids = MatiereModule.objects.filter(
                enseignant=user
            ).values_list('module__classes', flat=True)
            self.fields['classe'].queryset = Classe.objects.filter(
                id__in=classes_ids
            ).distinct()
        elif user and user.role == 'APPRENANT':
            # Pour les apprenants, limiter aux matières de leur classe
            if hasattr(user, 'classe') and user.classe:
                self.fields['matiere'].queryset = MatiereModule.objects.filter(
                    module__classes=user.classe
                ).select_related('matiere', 'module')
                self.fields['classe'].queryset = Classe.objects.filter(id=user.classe.id)
            else:
                self.fields['matiere'].queryset = MatiereModule.objects.none()
                self.fields['classe'].queryset = Classe.objects.none()
        else:
            self.fields['matiere'].queryset = MatiereModule.objects.all()
            self.fields['classe'].queryset = Classe.objects.all()


class PublierCorrectionForm(forms.ModelForm):
    """Formulaire pour publier la correction d'une évaluation"""

    class Meta:
        model = Evaluation
        fields = ['fichier_correction', 'date_publication_correction', 'correction_visible_immediatement']
        widgets = {
            'date_publication_correction': DateTimeWidget(attrs={
                'class': 'form-control'
            }),
            'fichier_correction': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.txt'
            }),
            'correction_visible_immediatement': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['fichier_correction'].required = True
        self.fields['fichier_correction'].label = "Fichier de correction"
        self.fields['fichier_correction'].help_text = (
            "Correction générale de l'évaluation - Formats: PDF, DOC, DOCX, TXT"
        )

        self.fields['date_publication_correction'].label = "Date de publication"
        self.fields['date_publication_correction'].help_text = (
            "Laisser vide pour publier immédiatement après l'évaluation"
        )

        self.fields['correction_visible_immediatement'].label = (
            "Correction visible immédiatement après l'évaluation"
        )

        # Date par défaut: maintenant
        if not self.instance.date_publication_correction:
            self.fields['date_publication_correction'].initial = timezone.now()

    def clean(self):
        cleaned_data = super().clean()
        correction_visible_immediatement = cleaned_data.get('correction_visible_immediatement')
        date_publication_correction = cleaned_data.get('date_publication_correction')

        # Au moins une option doit être choisie
        if not correction_visible_immediatement and not date_publication_correction:
            raise ValidationError(
                "Vous devez soit rendre la correction visible immédiatement, "
                "soit définir une date de publication."
            )

        return cleaned_data

class BulkNoteForm(forms.Form):
    """Formulaire pour la saisie en masse de notes"""

    def __init__(self, *args, compositions=None, evaluation=None, **kwargs):
        super().__init__(*args, **kwargs)

        if compositions and evaluation:
            for composition in compositions:
                field_name = f'note_{composition.id}'
                self.fields[field_name] = forms.DecimalField(
                    max_digits=5,
                    decimal_places=2,
                    min_value=0,
                    max_value=evaluation.note_maximale,
                    required=False,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control form-control-sm text-center',
                        'step': '0.01',
                        'placeholder': f'/{evaluation.note_maximale}'
                    })
                )

                comment_field_name = f'commentaire_{composition.id}'
                self.fields[comment_field_name] = forms.CharField(
                    required=False,
                    widget=forms.Textarea(attrs={
                        'class': 'form-control form-control-sm',
                        'rows': 2,
                        'placeholder': 'Commentaire...'
                    })
                )

                # Pré-remplir si une note existe déjà
                try:
                    note_existante = Note.objects.get(
                        apprenant=composition.apprenant,
                        evaluation=evaluation
                    )
                    self.fields[field_name].initial = note_existante.valeur
                    self.fields[comment_field_name].initial = note_existante.commentaire
                except Note.DoesNotExist:
                    pass

class ImportNotesForm(forms.Form):
    """Formulaire d'import de notes via fichier CSV"""

    fichier_csv = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        }),
        help_text="Fichier CSV avec colonnes: nom, prénom, note, commentaire"
    )

    separateur = forms.ChoiceField(
        choices=[
            (',', 'Virgule (,)'),
            (';', 'Point-virgule (;)'),
            ('\t', 'Tabulation')
        ],
        initial=';',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    ecraser_notes_existantes = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Cocher pour remplacer les notes existantes"
    )

    def clean_fichier_csv(self):
        fichier = self.cleaned_data.get('fichier_csv')

        if fichier:
            # Vérifier l'extension
            if not fichier.name.endswith('.csv'):
                raise ValidationError("Seuls les fichiers CSV sont autorisés.")

            # Vérifier la taille (5MB max)
            if fichier.size > 5 * 1024 * 1024:
                raise ValidationError("Le fichier CSV ne doit pas dépasser 5MB.")

        return fichier

class StatistiquesForm(forms.Form):
    """Formulaire pour filtrer les statistiques"""

    annee_academique = forms.ModelChoiceField(
        queryset=AnneeAcademique.objects.all(),
        required=False,
        empty_label="Toutes les années",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    type_evaluation = forms.ChoiceField(
        choices=[('', 'Tous les types')] + list(Evaluation.TYPE_EVALUATION),  # Correction ici
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    matiere = forms.ModelChoiceField(
        queryset=MatiereModule.objects.none(),
        required=False,
        empty_label="Toutes les matières",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Année académique active par défaut
        try:
            annee_active = AnneeAcademique.objects.get(active=True)
            self.fields['annee_academique'].initial = annee_active
        except AnneeAcademique.DoesNotExist:
            pass

        if user and user.role == 'ENSEIGNANT':
            self.fields['matiere'].queryset = MatiereModule.objects.filter(
                enseignant=user
            ).select_related('matiere', 'module')
        else:
            self.fields['matiere'].queryset = MatiereModule.objects.all()
