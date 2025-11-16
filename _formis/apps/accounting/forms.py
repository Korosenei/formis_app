# apps/accounting/forms.py
from django import forms
from .models import (
    Facture, LigneFacture, Depense, CompteComptable,
    EcritureComptable, LigneEcriture, BudgetPrevisionnel, ExerciceComptable
)
from apps.accounts.models import Utilisateur
from apps.enrollment.models import Inscription


class FactureForm(forms.ModelForm):
    """Formulaire de création/édition de facture"""

    class Meta:
        model = Facture
        fields = [
            'type_facture', 'apprenant', 'inscription',
            'date_emission', 'date_echeance',
            'montant_ht', 'taux_tva', 'description', 'notes'
        ]
        widgets = {
            'type_facture': forms.Select(attrs={'class': 'form-select'}),
            'apprenant': forms.Select(attrs={'class': 'form-select'}),
            'inscription': forms.Select(attrs={'class': 'form-select'}),
            'date_emission': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_echeance': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'montant_ht': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'taux_tva': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        etablissement = kwargs.pop('etablissement', None)
        super().__init__(*args, **kwargs)

        if etablissement:
            # Filtrer les apprenants par établissement
            self.fields['apprenant'].queryset = Utilisateur.objects.filter(
                etablissement=etablissement,
                role='APPRENANT',
                est_actif=True
            )

            # Filtrer les inscriptions par établissement
            self.fields['inscription'].queryset = Inscription.objects.filter(
                apprenant__etablissement=etablissement,
                statut='ACTIVE'
            ).select_related('apprenant')

class LigneFactureFormSet(forms.BaseInlineFormSet):
    """FormSet pour les lignes de facture"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.fields['description'].widget.attrs.update({'class': 'form-control'})
            form.fields['quantite'].widget.attrs.update({'class': 'form-control', 'step': '0.01'})
            form.fields['prix_unitaire'].widget.attrs.update({'class': 'form-control', 'step': '0.01'})

class DepenseForm(forms.ModelForm):
    """Formulaire de saisie de dépense"""

    class Meta:
        model = Depense
        fields = [
            'categorie', 'fournisseur', 'date_depense',
            'description', 'montant', 'mode_paiement',
            'numero_piece', 'piece_justificative', 'notes'
        ]
        widgets = {
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'fournisseur': forms.TextInput(attrs={'class': 'form-control'}),
            'date_depense': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'mode_paiement': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_piece': forms.TextInput(attrs={'class': 'form-control'}),
            'piece_justificative': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class CompteComptableForm(forms.ModelForm):
    """Formulaire de création de compte comptable"""

    class Meta:
        model = CompteComptable
        fields = [
            'numero_compte', 'libelle', 'categorie',
            'compte_parent', 'description'
        ]
        widgets = {
            'numero_compte': forms.TextInput(attrs={'class': 'form-control'}),
            'libelle': forms.TextInput(attrs={'class': 'form-control'}),
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'compte_parent': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        etablissement = kwargs.pop('etablissement', None)
        super().__init__(*args, **kwargs)

        if etablissement:
            self.fields['compte_parent'].queryset = CompteComptable.objects.filter(
                etablissement=etablissement,
                est_actif=True
            )

class EcritureComptableForm(forms.ModelForm):
    """Formulaire de saisie d'écriture comptable"""

    class Meta:
        model = EcritureComptable
        fields = [
            'journal', 'numero_piece', 'date_ecriture',
            'libelle', 'reference_externe', 'notes'
        ]
        widgets = {
            'journal': forms.Select(attrs={'class': 'form-select'}),
            'numero_piece': forms.TextInput(attrs={'class': 'form-control'}),
            'date_ecriture': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'libelle': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_externe': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class LigneEcritureForm(forms.ModelForm):
    """Formulaire de ligne d'écriture"""

    class Meta:
        model = LigneEcriture
        fields = ['compte', 'libelle', 'debit', 'credit']
        widgets = {
            'compte': forms.Select(attrs={'class': 'form-select'}),
            'libelle': forms.TextInput(attrs={'class': 'form-control'}),
            'debit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'credit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class BudgetPrevisionnelForm(forms.ModelForm):
    """Formulaire de budget prévisionnel"""

    class Meta:
        model = BudgetPrevisionnel
        fields = [
            'exercice', 'libelle', 'type_budget',
            'montant_previsionnel', 'notes'
        ]
        widgets = {
            'exercice': forms.Select(attrs={'class': 'form-select'}),
            'libelle': forms.TextInput(attrs={'class': 'form-control'}),
            'type_budget': forms.Select(attrs={'class': 'form-select'}),
            'montant_previsionnel': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ExerciceComptableForm(forms.ModelForm):
    """Formulaire d'exercice comptable"""

    class Meta:
        model = ExerciceComptable
        fields = ['libelle', 'date_debut', 'date_fin']
        widgets = {
            'libelle': forms.TextInput(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

class RapportFinancierForm(forms.Form):
    """Formulaire de génération de rapport financier"""

    TYPE_RAPPORT = [
        ('bilan', 'Bilan comptable'),
        ('resultat', 'Compte de résultat'),
        ('tresorerie', 'État de trésorerie'),
        ('grand_livre', 'Grand livre'),
        ('balance', 'Balance générale'),
    ]

    type_rapport = forms.ChoiceField(
        choices=TYPE_RAPPORT,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    date_debut = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    date_fin = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    format_export = forms.ChoiceField(
        choices=[('pdf', 'PDF'), ('excel', 'Excel'), ('csv', 'CSV')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class ValidationPaiementForm(forms.Form):
    """Formulaire de validation de paiement"""

    ACTION_CHOICES = [
        ('valider', 'Valider le paiement'),
        ('rejeter', 'Rejeter le paiement'),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect
    )

    motif = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Motif de rejet (obligatoire en cas de rejet)'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        motif = cleaned_data.get('motif')

        if action == 'rejeter' and not motif:
            raise forms.ValidationError("Un motif est obligatoire pour rejeter un paiement")

        return cleaned_data

class ApprobationDepenseForm(forms.Form):
    """Formulaire d'approbation de dépense"""

    ACTION_CHOICES = [
        ('approuver', 'Approuver la dépense'),
        ('rejeter', 'Rejeter la dépense'),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Notes ou motif de rejet'
        })
    )
