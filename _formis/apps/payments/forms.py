from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import PlanPaiement, TranchePaiement, Paiement, RemboursementPaiement
from apps.academic.models import Filiere, Niveau
from apps.establishments.models import AnneeAcademique


class PlanPaiementForm(forms.ModelForm):
    """Formulaire pour créer/modifier un plan de paiement"""

    class Meta:
        model = PlanPaiement
        fields = [
            'nom', 'description', 'filiere', 'niveau', 'annee_academique',
            'montant_total', 'paiement_unique_possible', 'paiement_echelonne_possible',
            'remise_paiement_unique', 'frais_echelonnement', 'est_actif'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Plan standard Licence 1'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description du plan de paiement...'
            }),
            'filiere': forms.Select(attrs={'class': 'form-select'}),
            'niveau': forms.Select(attrs={'class': 'form-select'}),
            'annee_academique': forms.Select(attrs={'class': 'form-select'}),
            'montant_total': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'remise_paiement_unique': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'frais_echelonnement': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'paiement_unique_possible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'paiement_echelonne_possible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrer les niveaux selon la filière sélectionnée
        if 'filiere' in self.data:
            try:
                filiere_id = int(self.data.get('filiere'))
                self.fields['niveau'].queryset = Niveau.objects.filter(filiere_id=filiere_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.filiere:
            self.fields['niveau'].queryset = self.instance.filiere.niveaux.all()

    def clean(self):
        cleaned_data = super().clean()

        # Validation que au moins une option de paiement est possible
        paiement_unique = cleaned_data.get('paiement_unique_possible')
        paiement_echelonne = cleaned_data.get('paiement_echelonne_possible')

        if not paiement_unique and not paiement_echelonne:
            raise ValidationError("Au moins une option de paiement doit être activée.")

        # Validation de la remise
        remise = cleaned_data.get('remise_paiement_unique', 0)
        if remise > 50:
            raise ValidationError({'remise_paiement_unique': 'La remise ne peut pas dépasser 50%.'})

        return cleaned_data


class TranchePaiementForm(forms.ModelForm):
    """Formulaire pour créer/modifier une tranche de paiement"""

    class Meta:
        model = TranchePaiement
        fields = [
            'numero', 'nom', 'montant', 'date_limite',
            'est_premiere_tranche', 'penalite_retard'
        ]
        widgets = {
            'numero': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Première tranche'
            }),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01'
            }),
            'date_limite': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'est_premiere_tranche': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'penalite_retard': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '50',
                'step': '0.01',
                'placeholder': '0.00'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.plan = kwargs.pop('plan', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        if self.plan:
            # Vérifier que le montant ne dépasse pas le montant total du plan
            montant = cleaned_data.get('montant', 0)
            autres_tranches = self.plan.tranches.exclude(pk=self.instance.pk if self.instance.pk else None)
            total_autres = sum(t.montant for t in autres_tranches)

            if (total_autres + montant) > self.plan.montant_total:
                raise ValidationError({
                    'montant': f'Le total des tranches ne peut pas dépasser {self.plan.montant_total} XOF.'
                })

        return cleaned_data


class InscriptionChoixPaiementForm(forms.Form):
    """Formulaire pour choisir le type de paiement lors de l'inscription"""

    TYPE_PAIEMENT_CHOICES = [
        ('UNIQUE', 'Paiement unique'),
        ('ECHELONNE', 'Paiement échelonné'),
    ]

    candidature_id = forms.UUIDField(widget=forms.HiddenInput())
    type_paiement = forms.ChoiceField(
        choices=TYPE_PAIEMENT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        required=True,
        label="Mode de paiement"
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.candidatures_disponibles = kwargs.pop('candidatures_disponibles', [])
        super().__init__(*args, **kwargs)

        # Si une seule candidature, la pré-sélectionner
        if len(self.candidatures_disponibles) == 1:
            self.fields['candidature_id'].initial = self.candidatures_disponibles[0].id


class PaiementAdminForm(forms.ModelForm):
    """Formulaire administrateur pour gérer les paiements"""

    class Meta:
        model = Paiement
        fields = [
            'inscription_paiement', 'tranche', 'montant', 'frais_transaction',
            'methode_paiement', 'statut', 'description', 'notes_admin'
        ]
        widgets = {
            'inscription_paiement': forms.Select(attrs={'class': 'form-select'}),
            'tranche': forms.Select(attrs={'class': 'form-select'}),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01'
            }),
            'frais_transaction': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01'
            }),
            'methode_paiement': forms.Select(attrs={'class': 'form-select'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'notes_admin': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }


class RemboursementForm(forms.ModelForm):
    """Formulaire pour demander un remboursement"""

    class Meta:
        model = RemboursementPaiement
        fields = ['montant_rembourse', 'motif']
        widgets = {
            'montant_rembourse': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01'
            }),
            'motif': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Expliquez la raison de votre demande de remboursement...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.paiement = kwargs.pop('paiement', None)
        super().__init__(*args, **kwargs)

        if self.paiement:
            # Limiter le montant remboursable au montant du paiement
            self.fields['montant_rembourse'].widget.attrs['max'] = str(self.paiement.montant)

    def clean_montant_rembourse(self):
        montant = self.cleaned_data.get('montant_rembourse')

        if self.paiement and montant > self.paiement.montant:
            raise ValidationError(
                f"Le montant à rembourser ne peut pas dépasser {self.paiement.montant} XOF."
            )

        return montant
