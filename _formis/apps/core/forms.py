from django import forms
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from apps.establishments.models import Etablissement
from apps.academic.models import Filiere, Niveau
from apps.enrollment.models import Candidature


class CandidatureForm(forms.ModelForm):
    """Formulaire de candidature"""

    class Meta:
        model = Candidature
        fields = [
            'etablissement', 'filiere', 'niveau',
            'prenom', 'nom', 'date_naissance', 'lieu_naissance',
            'genre', 'telephone', 'email', 'adresse',
            'nom_pere', 'telephone_pere', 'nom_mere', 'telephone_mere',
            'nom_tuteur', 'telephone_tuteur',
            'ecole_precedente', 'dernier_diplome', 'annee_obtention'
        ]
        widgets = {
            'date_naissance': forms.DateInput(attrs={'type': 'date'}),
            'adresse': forms.Textarea(attrs={'rows': 3}),
            'etablissement': forms.Select(attrs={'id': 'id_etablissement'}),
            'filiere': forms.Select(attrs={'id': 'id_filiere'}),
            'niveau': forms.Select(attrs={'id': 'id_niveau'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrer les établissements publics
        self.fields['etablissement'].queryset = Etablissement.objects.filter(
            actif=True,
            public=True
        )

        # Les champs filière et niveau seront remplis via AJAX
        self.fields['filiere'].queryset = Filiere.objects.none()
        self.fields['niveau'].queryset = Niveau.objects.none()

        # Si des données sont présentes (modification)
        if 'etablissement' in self.data:
            try:
                etablissement_id = int(self.data.get('etablissement'))
                self.fields['filiere'].queryset = Filiere.objects.filter(
                    etablissement_id=etablissement_id,
                )
            except (ValueError, TypeError):
                pass

        if 'filiere' in self.data:
            try:
                filiere_id = int(self.data.get('filiere'))
                self.fields['niveau'].queryset = Niveau.objects.filter(
                    filiere_id=filiere_id
                )
            except (ValueError, TypeError):
                pass


class ContactForm(forms.Form):
    """Formulaire de contact"""
    nom = forms.CharField(max_length=100, label="Nom complet")
    email = forms.EmailField(label="Email")
    sujet = forms.CharField(max_length=200, label="Sujet")
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}), label="Message")

    def envoyer_email(self):
        """Envoie l'email de contact"""
        nom = self.cleaned_data['nom']
        email = self.cleaned_data['email']
        sujet = self.cleaned_data['sujet']
        message = self.cleaned_data['message']

        send_mail(
            subject=f"Contact FORMIS: {sujet}",
            message=f"De: {nom} ({email})\n\n{message}",
            from_email=email,
            recipient_list=['contact@formis.bf'],
            fail_silently=False,
        )

