from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.admin.widgets import AdminDateWidget
from django.utils import timezone
from datetime import date, datetime
import re

from .models import (
    Localite, TypeEtablissement, Etablissement, AnneeAcademique,
    BaremeNotation, NiveauNote, ParametresEtablissement, Salle,
    JourFerie, Campus
)



class BaseModelForm(forms.ModelForm):
    """Formulaire de base avec styles Bootstrap"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'form-control'
                if 'rows' not in field.widget.attrs:
                    field.widget.attrs['rows'] = 3
            elif isinstance(field.widget,
                            (forms.TextInput, forms.EmailInput, forms.URLInput, forms.NumberInput, forms.DateInput)):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = 'form-control'


class LocaliteForm(BaseModelForm):
    class Meta:
        model = Localite
        fields = ['nom', 'region', 'pays', 'code_postal']
        widgets = {
            'nom': forms.TextInput(attrs={
                'placeholder': 'Nom de la localité',
                'autocomplete': 'off'
            }),
            'region': forms.TextInput(attrs={
                'placeholder': 'Région',
                'list': 'regions-list'
            }),
            'pays': forms.TextInput(attrs={
                'value': 'Burkina Faso',
                'readonly': True
            }),
            'code_postal': forms.TextInput(attrs={
                'placeholder': 'Code postal (optionnel)',
                'pattern': '[0-9]{5}',
                'title': 'Code postal à 5 chiffres'
            }),
        }
        help_texts = {
            'nom': 'Nom de la ville, commune ou localité',
            'region': 'Région administrative',
            'code_postal': 'Code postal à 5 chiffres (optionnel)'
        }

    def clean_nom(self):
        nom = self.cleaned_data['nom'].strip()
        if len(nom) < 2:
            raise ValidationError("Le nom doit contenir au moins 2 caractères")
        # Capitaliser la première lettre de chaque mot
        return ' '.join(word.capitalize() for word in nom.split())

    def clean_code_postal(self):
        code_postal = self.cleaned_data.get('code_postal')
        if code_postal:
            code_postal = code_postal.strip()
            if not re.match(r'^\d{5}$', code_postal):
                raise ValidationError("Le code postal doit contenir exactement 5 chiffres")
        return code_postal or None


class TypeEtablissementForm(BaseModelForm):
    class Meta:
        model = TypeEtablissement
        fields = [
            'nom', 'description', 'code', 'structure_academique_defaut',
            'icone', 'actif'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Nom du type d\'établissement'}),
            'description': forms.Textarea(attrs={'placeholder': 'Description du type d\'établissement'}),
            'code': forms.TextInput(attrs={
                'placeholder': 'Code unique (ex: UNIV)',
                'style': 'text-transform: uppercase;'
            }),
            'icone': forms.TextInput(attrs={
                'placeholder': 'Classe FontAwesome (ex: fas fa-university)',
                'data-bs-toggle': 'tooltip',
                'title': 'Icône FontAwesome pour l\'affichage'
            }),
        }
        help_texts = {
            'code': 'Code unique en majuscules pour identifier le type',
            'icone': 'Classe CSS FontAwesome pour l\'icône d\'affichage',
            'structure_academique_defaut': 'Structure par défaut pour ce type d\'établissement'
        }

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if len(code) < 2:
            raise ValidationError("Le code doit contenir au moins 2 caractères")
        if not re.match(r'^[A-Z0-9_]+$', code):
            raise ValidationError("Le code ne peut contenir que des lettres majuscules, chiffres et underscores")

        # Vérifier l'unicité
        queryset = TypeEtablissement.objects.filter(code=code)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise ValidationError("Ce code existe déjà")

        return code

    def clean_icone(self):
        icone = self.cleaned_data.get('icone', '').strip()
        if icone and not icone.startswith(('fas ', 'far ', 'fab ', 'fal ')):
            raise ValidationError("L'icône doit commencer par 'fas', 'far', 'fab' ou 'fal'")
        return icone or 'fas fa-building'


class EtablissementForm(BaseModelForm):
    class Meta:
        model = Etablissement
        fields = [
            'nom', 'sigle', 'code', 'type_etablissement', 'localite',
            'adresse', 'telephone', 'email', 'site_web', 'nom_directeur',
            'numero_enregistrement', 'date_creation', 'logo', 'image_couverture',
            'description', 'mission', 'vision', 'capacite_totale',
            'actif', 'public'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Nom complet de l\'établissement'}),
            'sigle': forms.TextInput(attrs={'placeholder': 'Sigle ou acronyme'}),
            'code': forms.TextInput(attrs={
                'placeholder': 'Code unique',
                'style': 'text-transform: uppercase;'
            }),
            'adresse': forms.Textarea(attrs={
                'placeholder': 'Adresse complète de l\'établissement',
                'rows': 3
            }),
            'telephone': forms.TextInput(attrs={
                'placeholder': '+226 XX XX XX XX',
                'pattern': r'^\+?[0-9\s\-\(\)]+$',
                'title': 'Numéro de téléphone valide'
            }),
            'email': forms.EmailInput(attrs={'placeholder': 'contact@etablissement.bf'}),
            'site_web': forms.URLInput(attrs={'placeholder': 'https://www.etablissement.bf'}),
            'nom_directeur': forms.TextInput(attrs={'placeholder': 'Nom et prénoms du directeur'}),
            'numero_enregistrement': forms.TextInput(attrs={
                'placeholder': 'Numéro d\'enregistrement officiel'
            }),
            'date_creation': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={
                'placeholder': 'Description générale de l\'établissement',
                'rows': 4
            }),
            'mission': forms.Textarea(attrs={
                'placeholder': 'Mission de l\'établissement',
                'rows': 3
            }),
            'vision': forms.Textarea(attrs={
                'placeholder': 'Vision de l\'établissement',
                'rows': 3
            }),
            'capacite_totale': forms.NumberInput(attrs={
                'min': '0',
                'step': '1',
                'placeholder': 'Nombre total de places'
            }),
        }
        help_texts = {
            'code': 'Code unique d\'identification de l\'établissement',
            'telephone': 'Numéro de téléphone principal',
            'logo': 'Logo de l\'établissement (formats: JPG, PNG, max 2MB)',
            'image_couverture': 'Image de couverture (formats: JPG, PNG, max 5MB)',
            'capacite_totale': 'Nombre total d\'étudiants que peut accueillir l\'établissement',
            'public': 'Cochez si l\'établissement doit être visible au public'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les types d'établissement actifs
        self.fields['type_etablissement'].queryset = TypeEtablissement.objects.filter(actif=True)
        # Ordonner les localités par nom
        self.fields['localite'].queryset = Localite.objects.order_by('nom')

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if len(code) < 2:
            raise ValidationError("Le code doit contenir au moins 2 caractères")

        # Vérifier l'unicité
        queryset = Etablissement.objects.filter(code=code)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise ValidationError("Ce code existe déjà")

        return code

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone', '').strip()
        if telephone:
            # Nettoyer le numéro
            cleaned_phone = re.sub(r'[^\d\+]', '', telephone)
            if not re.match(r'^\+?[0-9]{8,15}$', cleaned_phone):
                raise ValidationError("Format de téléphone invalide")
        return telephone or None

    def clean_capacite_totale(self):
        capacite = self.cleaned_data['capacite_totale']
        if capacite < 0:
            raise ValidationError("La capacité ne peut pas être négative")
        if capacite > 1000000:
            raise ValidationError("La capacité semble trop élevée")
        return capacite

    def clean_date_creation(self):
        date_creation = self.cleaned_data.get('date_creation')
        if date_creation and date_creation > date.today():
            raise ValidationError("La date de création ne peut pas être dans le futur")
        return date_creation

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo:
            if logo.size > 2 * 1024 * 1024:  # 2MB
                raise ValidationError("Le logo ne doit pas dépasser 2MB")
            if not logo.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                raise ValidationError("Le logo doit être au format PNG ou JPEG")
        return logo

    def clean_image_couverture(self):
        image = self.cleaned_data.get('image_couverture')
        if image:
            if image.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError("L'image de couverture ne doit pas dépasser 5MB")
            if not image.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                raise ValidationError("L'image doit être au format PNG ou JPEG")
        return image


class AnneeAcademiqueForm(BaseModelForm):
    class Meta:
        model = AnneeAcademique
        fields = [
            'etablissement', 'nom', 'date_debut', 'date_fin',
            'debut_inscriptions', 'fin_inscriptions',
            'debut_cours', 'fin_cours',
            'debut_examens_premier_semestre', 'fin_examens_premier_semestre',
            'debut_examens_second_semestre', 'fin_examens_second_semestre',
            'debut_vacances_hiver', 'fin_vacances_hiver',
            'debut_vacances_ete', 'fin_vacances_ete',
            'est_courante', 'est_active'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': '2024-2025'}),
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
            'debut_inscriptions': forms.DateInput(attrs={'type': 'date'}),
            'fin_inscriptions': forms.DateInput(attrs={'type': 'date'}),
            'debut_cours': forms.DateInput(attrs={'type': 'date'}),
            'fin_cours': forms.DateInput(attrs={'type': 'date'}),
            'debut_examens_premier_semestre': forms.DateInput(attrs={'type': 'date'}),
            'fin_examens_premier_semestre': forms.DateInput(attrs={'type': 'date'}),
            'debut_examens_second_semestre': forms.DateInput(attrs={'type': 'date'}),
            'fin_examens_second_semestre': forms.DateInput(attrs={'type': 'date'}),
            'debut_vacances_hiver': forms.DateInput(attrs={'type': 'date'}),
            'fin_vacances_hiver': forms.DateInput(attrs={'type': 'date'}),
            'debut_vacances_ete': forms.DateInput(attrs={'type': 'date'}),
            'fin_vacances_ete': forms.DateInput(attrs={'type': 'date'}),
        }
        help_texts = {
            'nom': 'Format recommandé: YYYY-YYYY (ex: 2024-2025)',
            'est_courante': 'Une seule année peut être courante par établissement',
            'est_active': 'Décochez pour archiver l\'année académique'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['etablissement'].queryset = Etablissement.objects.filter(actif=True)

    def clean_nom(self):
        nom = self.cleaned_data['nom'].strip()
        if not re.match(r'^\d{4}-\d{4}$', nom):
            if not re.match(r'^\d{4}/\d{4}$', nom):
                raise ValidationError("Format attendu: YYYY-YYYY ou YYYY/YYYY")
        return nom

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        etablissement = cleaned_data.get('etablissement')

        # Vérifier que la date de début est antérieure à la date de fin
        if date_debut and date_fin:
            if date_debut >= date_fin:
                raise ValidationError("La date de début doit être antérieure à la date de fin")

            # Vérifier que l'année académique dure au moins 6 mois
            if (date_fin - date_debut).days < 180:
                raise ValidationError("L'année académique doit durer au moins 6 mois")

        # Vérifier les dates d'inscription
        debut_inscriptions = cleaned_data.get('debut_inscriptions')
        fin_inscriptions = cleaned_data.get('fin_inscriptions')
        if debut_inscriptions and fin_inscriptions:
            if debut_inscriptions >= fin_inscriptions:
                raise ValidationError("La date de début des inscriptions doit être antérieure à la date de fin")

        # Vérifier les dates de cours
        debut_cours = cleaned_data.get('debut_cours')
        fin_cours = cleaned_data.get('fin_cours')
        if debut_cours and fin_cours:
            if debut_cours >= fin_cours:
                raise ValidationError("La date de début des cours doit être antérieure à la date de fin")

        # Vérifier l'unicité du nom par établissement
        if etablissement and cleaned_data.get('nom'):
            queryset = AnneeAcademique.objects.filter(
                etablissement=etablissement,
                nom=cleaned_data['nom']
            )
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise ValidationError("Une année académique avec ce nom existe déjà pour cet établissement")

        return cleaned_data


class BaremeNotationForm(BaseModelForm):
    class Meta:
        model = BaremeNotation
        fields = [
            'etablissement', 'nom', 'note_minimale', 'note_maximale',
            'note_passage', 'est_defaut', 'description'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Nom du barème (ex: Standard 0-20)'}),
            'note_minimale': forms.NumberInput(attrs={
                'min': '0', 'max': '100', 'step': '0.01',
                'placeholder': '0'
            }),
            'note_maximale': forms.NumberInput(attrs={
                'min': '0', 'max': '100', 'step': '0.01',
                'placeholder': '20'
            }),
            'note_passage': forms.NumberInput(attrs={
                'min': '0', 'max': '100', 'step': '0.01',
                'placeholder': '10'
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Description du système de notation',
                'rows': 3
            }),
        }
        help_texts = {
            'est_defaut': 'Un seul barème peut être défini par défaut par établissement',
            'note_passage': 'Note minimale pour valider'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['etablissement'].queryset = Etablissement.objects.filter(actif=True)

    def clean(self):
        cleaned_data = super().clean()
        note_min = cleaned_data.get('note_minimale')
        note_max = cleaned_data.get('note_maximale')
        note_passage = cleaned_data.get('note_passage')

        if note_min is not None and note_max is not None:
            if note_min >= note_max:
                raise ValidationError("La note minimale doit être inférieure à la note maximale")

        if note_passage is not None and note_min is not None and note_max is not None:
            if not (note_min <= note_passage <= note_max):
                raise ValidationError("La note de passage doit être comprise entre la note minimale et maximale")

        return cleaned_data


class NiveauNoteForm(BaseModelForm):
    class Meta:
        model = NiveauNote
        fields = [
            'bareme_notation', 'nom', 'note_minimale', 'note_maximale',
            'couleur', 'description', 'points_gpa'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Ex: Excellent, Bien, Passable'}),
            'note_minimale': forms.NumberInput(attrs={'step': '0.01'}),
            'note_maximale': forms.NumberInput(attrs={'step': '0.01'}),
            'couleur': forms.TextInput(attrs={'type': 'color'}),
            'description': forms.TextInput(attrs={'placeholder': 'Description du niveau'}),
            'points_gpa': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '4'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        note_min = cleaned_data.get('note_minimale')
        note_max = cleaned_data.get('note_maximale')

        if note_min is not None and note_max is not None:
            if note_min >= note_max:
                raise ValidationError("La note minimale doit être inférieure à la note maximale")

        return cleaned_data


class SalleForm(BaseModelForm):
    class Meta:
        model = Salle
        fields = [
            'etablissement', 'nom', 'code', 'type_salle', 'capacite',
            'etage', 'batiment', 'longueur', 'largeur',
            'projecteur', 'ordinateur', 'climatisation', 'wifi',
            'tableau_blanc', 'systeme_audio', 'accessible_pmr',
            'etat', 'description', 'notes', 'est_active'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Nom de la salle'}),
            'code': forms.TextInput(attrs={'placeholder': 'Code unique de la salle'}),
            'capacite': forms.NumberInput(attrs={'min': '1', 'placeholder': 'Nombre de places'}),
            'etage': forms.TextInput(attrs={'placeholder': 'Ex: RDC, 1er, 2ème'}),
            'batiment': forms.TextInput(attrs={'placeholder': 'Nom ou numéro du bâtiment'}),
            'longueur': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'Longueur en mètres'}),
            'largeur': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'Largeur en mètres'}),
            'description': forms.Textarea(attrs={
                'placeholder': 'Description de la salle',
                'rows': 3
            }),
            'notes': forms.Textarea(attrs={
                'placeholder': 'Notes et observations',
                'rows': 3
            }),
        }
        help_texts = {
            'code': 'Code unique d\'identification de la salle',
            'accessible_pmr': 'Accessible aux Personnes à Mobilité Réduite',
            'longueur': 'Longueur de la salle en mètres',
            'largeur': 'Largeur de la salle en mètres'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['etablissement'].queryset = Etablissement.objects.filter(actif=True)

    def clean_capacite(self):
        capacite = self.cleaned_data['capacite']
        if capacite <= 0:
            raise ValidationError("La capacité doit être supérieure à 0")
        if capacite > 10000:
            raise ValidationError("La capacité semble trop élevée")
        return capacite

    def clean(self):
        cleaned_data = super().clean()
        etablissement = cleaned_data.get('etablissement')
        code = cleaned_data.get('code')

        # Vérifier l'unicité du code par établissement
        if etablissement and code:
            queryset = Salle.objects.filter(etablissement=etablissement, code=code)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise ValidationError("Une salle avec ce code existe déjà dans cet établissement")

        return cleaned_data


class JourFerieForm(BaseModelForm):
    class Meta:
        model = JourFerie
        fields = [
            'etablissement', 'nom', 'date_debut', 'date_fin',
            'type_jour_ferie', 'description', 'est_recurrent',
            'modele_recurrence', 'affecte_cours', 'affecte_examens',
            'affecte_inscriptions', 'couleur'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Nom du jour férié ou des vacances'}),
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={
                'placeholder': 'Description ou notes',
                'rows': 3
            }),
            'couleur': forms.TextInput(attrs={'type': 'color', 'value': '#dc3545'}),
        }
        help_texts = {
            'date_fin': 'Même date que le début pour un jour unique',
            'est_recurrent': 'Répétition automatique chaque année',
            'couleur': 'Couleur d\'affichage dans le calendrier'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['etablissement'].queryset = Etablissement.objects.filter(actif=True)
        # Le modèle de récurrence n'est requis que si récurrent
        self.fields['modele_recurrence'].required = False

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        est_recurrent = cleaned_data.get('est_recurrent')
        modele_recurrence = cleaned_data.get('modele_recurrence')

        if date_debut and date_fin and date_debut > date_fin:
            raise ValidationError("La date de début doit être antérieure ou égale à la date de fin")

        if est_recurrent and not modele_recurrence:
            raise ValidationError("Le modèle de récurrence est requis pour les événements récurrents")

        return cleaned_data


class CampusForm(BaseModelForm):
    class Meta:
        model = Campus
        fields = [
            'etablissement', 'nom', 'code', 'adresse', 'localite',
            'latitude', 'longitude', 'description', 'superficie_totale',
            'bibliotheque', 'cafeteria', 'parking', 'internat',
            'installations_sportives', 'infirmerie', 'telephone',
            'email', 'responsable_campus', 'est_campus_principal', 'est_actif'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Nom du campus'}),
            'code': forms.TextInput(attrs={'placeholder': 'Code unique du campus'}),
            'adresse': forms.Textarea(attrs={
                'placeholder': 'Adresse complète du campus',
                'rows': 3
            }),
            'latitude': forms.NumberInput(attrs={
                'step': '0.000001',
                'placeholder': 'Latitude GPS'
            }),
            'longitude': forms.NumberInput(attrs={
                'step': '0.000001',
                'placeholder': 'Longitude GPS'
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Description du campus',
                'rows': 4
            }),
            'superficie_totale': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': 'Superficie en m²'
            }),
            'telephone': forms.TextInput(attrs={'placeholder': '+226 XX XX XX XX'}),
            'email': forms.EmailInput(attrs={'placeholder': 'contact@campus.bf'}),
        }
        help_texts = {
            'code': 'Code unique d\'identification du campus',
            'latitude': 'Coordonnée GPS latitude (optionnel)',
            'longitude': 'Coordonnée GPS longitude (optionnel)',
            'est_campus_principal': 'Un seul campus principal par établissement'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['etablissement'].queryset = Etablissement.objects.filter(actif=True)
        self.fields['localite'].queryset = Localite.objects.order_by('nom')
        # Filtrer les responsables potentiels
        from apps.accounts.models import Utilisateur
        self.fields['responsable_campus'].queryset = Utilisateur.objects.filter(
            role__in=['ADMIN', 'CHEF_DEPARTEMENT'],
            is_active=True
        ).order_by('first_name', 'last_name')

    def clean(self):
        cleaned_data = super().clean()
        etablissement = cleaned_data.get('etablissement')
        code = cleaned_data.get('code')

        # Vérifier l'unicité du code par établissement
        if etablissement and code:
            queryset = Campus.objects.filter(etablissement=etablissement, code=code)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise ValidationError("Un campus avec ce code existe déjà dans cet établissement")

        return cleaned_data


class ParametresEtablissementForm(BaseModelForm):
    class Meta:
        model = ParametresEtablissement
        fields = [
            'etablissement', 'structure_academique', 'bareme_notation_defaut',
            'frais_dossier_requis', 'montant_frais_dossier',
            'date_limite_inscription_anticipée', 'date_limite_inscription_normale',
            'date_limite_inscription_tardive', 'paiement_echelonne_autorise',
            'nombre_maximum_tranches', 'frais_echelonnement',
            'taux_penalite_retard', 'taux_presence_minimum',
            'points_bonus_autorises', 'points_bonus_maximum',
            'notifications_sms', 'notifications_email',
            'jours_avant_reset_mot_de_passe', 'tentatives_connexion_max',
            'examens_rattrapage_autorises', 'frais_examen_rattrapage',
            'couleur_primaire', 'couleur_secondaire'
        ]
        widgets = {
            'montant_frais_dossier': forms.NumberInput(attrs={'step': '0.01'}),
            'date_limite_inscription_anticipée': forms.DateInput(attrs={'type': 'date'}),
            'date_limite_inscription_normale': forms.DateInput(attrs={'type': 'date'}),
            'date_limite_inscription_tardive': forms.DateInput(attrs={'type': 'date'}),
            'nombre_maximum_tranches': forms.NumberInput(attrs={'min': '1'}),
            'frais_echelonnement': forms.NumberInput(attrs={'step': '0.01'}),
            'taux_penalite_retard': forms.NumberInput(attrs={'step': '0.01'}),
            'taux_presence_minimum': forms.NumberInput(attrs={'step': '0.01'}),
            'points_bonus_maximum': forms.NumberInput(attrs={'step': '0.01'}),
            'jours_avant_reset_mot_de_passe': forms.NumberInput(attrs={'min': '1'}),
            'tentatives_connexion_max': forms.NumberInput(attrs={'min': '1'}),
            'frais_examen_rattrapage': forms.NumberInput(attrs={'step': '0.01'}),
            'couleur_primaire': forms.TextInput(attrs={'type': 'color', 'value': '#007bff'}),
            'couleur_secondaire': forms.TextInput(attrs={'type': 'color', 'value': '#6c757d'}),
        }
        help_texts = {
            'taux_presence_minimum': 'Pourcentage minimal de présence requis',
            'couleur_primaire': 'Couleur principale de l\'interface',
            'couleur_secondaire': 'Couleur secondaire de l\'interface'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les barèmes de notation du même établissement
        if self.instance.pk and self.instance.etablissement:
            self.fields['bareme_notation_defaut'].queryset = BaremeNotation.objects.filter(
                etablissement=self.instance.etablissement
            )
        else:
            self.fields['bareme_notation_defaut'].queryset = BaremeNotation.objects.none()

    def clean_taux_presence_minimum(self):
        taux = self.cleaned_data['taux_presence_minimum']
        if not (0 <= taux <= 100):
            raise ValidationError("Le taux de présence doit être entre 0 et 100%")
        return taux

    def clean_taux_penalite_retard(self):
        taux = self.cleaned_data['taux_penalite_retard']
        if taux < 0:
            raise ValidationError("Le taux de pénalité ne peut pas être négatif")
        if taux > 100:
            raise ValidationError("Le taux de pénalité ne peut pas dépasser 100%")
        return taux


# ============================================================================
# FORMULAIRES DE RECHERCHE
# ============================================================================

class EtablissementSearchForm(forms.Form):
    """Formulaire de recherche des établissements"""
    nom = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom de l\'établissement'
        }),
        label="Nom"
    )

    type_etablissement = forms.ModelChoiceField(
        queryset=TypeEtablissement.objects.filter(actif=True).order_by('nom'),
        required=False,
        empty_label="Tous les types",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Type d'établissement"
    )

    localite = forms.ModelChoiceField(
        queryset=Localite.objects.order_by('nom'),
        required=False,
        empty_label="Toutes les localités",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Localité"
    )

    actif = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Établissements actifs uniquement"
    )

    capacite_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Capacité minimale'
        }),
        label="Capacité minimale"
    )

    capacite_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Capacité maximale'
        }),
        label="Capacité maximale"
    )


class SalleSearchForm(forms.Form):
    """Formulaire de recherche des salles"""
    TYPES_SALLE = [('', 'Tous les types')] + list(Salle.TYPES_SALLE)
    ETATS_SALLE = [('', 'Tous les états')] + list(Salle._meta.get_field('etat').choices)

    nom = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom de la salle'
        }),
        label="Nom"
    )

    etablissement = forms.ModelChoiceField(
        queryset=Etablissement.objects.filter(actif=True).order_by('nom'),
        required=False,
        empty_label="Tous les établissements",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Établissement"
    )

    type_salle = forms.ChoiceField(
        choices=TYPES_SALLE,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Type de salle"
    )

    capacite_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Capacité minimum'
        }),
        label="Capacité minimum"
    )

    batiment = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bâtiment'
        }),
        label="Bâtiment"
    )

    etat = forms.ChoiceField(
        choices=ETATS_SALLE,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="État"
    )

    equipements = forms.MultipleChoiceField(
        choices=[
            ('projecteur', 'Projecteur'),
            ('ordinateur', 'Ordinateur'),
            ('climatisation', 'Climatisation'),
            ('wifi', 'WiFi'),
            ('tableau_blanc', 'Tableau blanc'),
            ('systeme_audio', 'Système audio'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Équipements"
    )


class CampusSearchForm(forms.Form):
    """Formulaire de recherche des campus"""
    nom = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom du campus'
        }),
        label="Nom"
    )

    etablissement = forms.ModelChoiceField(
        queryset=Etablissement.objects.filter(actif=True).order_by('nom'),
        required=False,
        empty_label="Tous les établissements",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Établissement"
    )

    localite = forms.ModelChoiceField(
        queryset=Localite.objects.order_by('nom'),
        required=False,
        empty_label="Toutes les localités",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Localité"
    )

    est_actif = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Campus actifs uniquement"
    )


class StatistiquesForm(forms.Form):
    """Formulaire pour filtrer les statistiques"""
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Date de début"
    )

    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Date de fin"
    )

    etablissement = forms.ModelChoiceField(
        queryset=Etablissement.objects.filter(actif=True).order_by('nom'),
        required=False,
        empty_label="Tous les établissements",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Établissement"
    )

    type_etablissement = forms.ModelChoiceField(
        queryset=TypeEtablissement.objects.filter(actif=True).order_by('nom'),
        required=False,
        empty_label="Tous les types",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Type d'établissement"
    )


class RechercheGlobaleForm(forms.Form):
    """Formulaire de recherche globale"""
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher dans les établissements, salles, campus...',
            'autocomplete': 'off'
        }),
        label="Recherche"
    )

    type_recherche = forms.MultipleChoiceField(
        choices=[
            ('etablissements', 'Établissements'),
            ('salles', 'Salles'),
            ('campus', 'Campus'),
            ('localites', 'Localités'),
        ],
        required=False,
        initial=['etablissements', 'salles', 'campus'],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Rechercher dans"
    )


# ============================================================================
# FORMSETS POUR LES MODÈLES LIÉS
# ============================================================================

# FormSet pour les niveaux de notes d'un barème
NiveauNoteFormSet = inlineformset_factory(
    BaremeNotation,
    NiveauNote,
    form=NiveauNoteForm,
    extra=3,
    can_delete=True,
    fields=['nom', 'note_minimale', 'note_maximale', 'couleur', 'description', 'points_gpa']
)

# FormSet pour les salles d'un établissement
SalleFormSet = inlineformset_factory(
    Etablissement,
    Salle,
    form=SalleForm,
    extra=1,
    can_delete=True,
    fields=['nom', 'code', 'type_salle', 'capacite', 'batiment', 'etage', 'est_active']
)

# FormSet pour les campus d'un établissement
CampusFormSet = inlineformset_factory(
    Etablissement,
    Campus,
    form=CampusForm,
    extra=1,
    can_delete=True,
    fields=['nom', 'code', 'adresse', 'localite', 'est_campus_principal', 'est_actif']
)


# ============================================================================
# FORMULAIRES SPÉCIALISÉS
# ============================================================================

class ImportEtablissementsForm(forms.Form):
    """Formulaire pour importer des établissements depuis un fichier CSV"""
    fichier_csv = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        }),
        label="Fichier CSV",
        help_text="Fichier CSV avec les colonnes: nom, code, type_code, localite, adresse, etc."
    )

    mode_import = forms.ChoiceField(
        choices=[
            ('create_only', 'Créer uniquement (ignorer les doublons)'),
            ('create_update', 'Créer et mettre à jour'),
            ('update_only', 'Mettre à jour uniquement'),
        ],
        initial='create_update',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Mode d'importation"
    )

    dry_run = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Mode simulation (aucune donnée ne sera sauvegardée)",
        help_text="Activez pour tester l'import sans modifier la base de données"
    )

    def clean_fichier_csv(self):
        fichier = self.cleaned_data['fichier_csv']
        if not fichier.name.endswith('.csv'):
            raise ValidationError("Le fichier doit être au format CSV")
        if fichier.size > 5 * 1024 * 1024:  # 5MB
            raise ValidationError("Le fichier ne doit pas dépasser 5MB")
        return fichier


class ExportEtablissementsForm(forms.Form):
    """Formulaire pour configurer l'export des établissements"""
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('pdf', 'PDF'),
    ]

    format_export = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        initial='csv',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Format d'export"
    )

    etablissements = forms.ModelMultipleChoiceField(
        queryset=Etablissement.objects.filter(actif=True).order_by('nom'),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label="Établissements à exporter (tous si aucun sélectionné)"
    )

    inclure_salles = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Inclure les salles"
    )

    inclure_campus = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Inclure les campus"
    )

    inclure_inactifs = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Inclure les établissements inactifs"
    )


class NotificationForm(forms.Form):
    """Formulaire pour envoyer des notifications"""
    destinataires = forms.MultipleChoiceField(
        choices=[
            ('tous', 'Tous les utilisateurs'),
            ('admins', 'Administrateurs uniquement'),
            ('personnalise', 'Sélection personnalisée'),
        ],
        widget=forms.CheckboxSelectMultiple(),
        label="Destinataires"
    )

    etablissements = forms.ModelMultipleChoiceField(
        queryset=Etablissement.objects.filter(actif=True).order_by('nom'),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label="Filtrer par établissements"
    )

    sujet = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sujet de la notification'
        }),
        label="Sujet"
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Contenu de la notification'
        }),
        label="Message"
    )

    type_notification = forms.ChoiceField(
        choices=[
            ('info', 'Information'),
            ('warning', 'Avertissement'),
            ('success', 'Succès'),
            ('error', 'Erreur'),
        ],
        initial='info',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Type de notification"
    )

    envoyer_email = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Envoyer aussi par email"
    )

    envoyer_sms = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Envoyer aussi par SMS"
    )


# ============================================================================
# FORMULAIRES DE CONFIGURATION
# ============================================================================

class ConfigurationSystemeForm(forms.Form):
    """Formulaire de configuration générale du système"""
    nom_systeme = forms.CharField(
        initial="Gestion des Établissements",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Nom du système"
    )

    logo_systeme = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        label="Logo du système"
    )

    couleur_theme = forms.CharField(
        initial="#007bff",
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-control'}),
        label="Couleur du thème"
    )

    timezone = forms.ChoiceField(
        choices=[
            ('Africa/Ouagadougou', 'Ouagadougou (GMT+0)'),
            ('UTC', 'UTC (GMT+0)'),
            ('Europe/Paris', 'Paris (GMT+1)'),
        ],
        initial='Africa/Ouagadougou',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Fuseau horaire"
    )

    langue_defaut = forms.ChoiceField(
        choices=[
            ('fr', 'Français'),
            ('en', 'English'),
        ],
        initial='fr',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Langue par défaut"
    )

    maintenance_mode = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Mode maintenance"
    )

    debug_mode = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Mode debug"
    )


# ============================================================================
# WIDGETS PERSONNALISÉS
# ============================================================================

class ColorPickerWidget(forms.TextInput):
    """Widget personnalisé pour sélectionner une couleur"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('attrs', {})
        kwargs['attrs']['type'] = 'color'
        kwargs['attrs']['class'] = 'form-control form-control-color'
        super().__init__(*args, **kwargs)


class DateRangeWidget(forms.MultiWidget):
    """Widget pour sélectionner une plage de dates"""

    def __init__(self, attrs=None):
        widgets = [
            forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return [value.start, value.end]
        return [None, None]


class TagsWidget(forms.TextInput):
    """Widget pour saisir des tags séparés par des virgules"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('attrs', {})
        kwargs['attrs']['class'] = 'form-control'
        kwargs['attrs']['placeholder'] = 'Tapez et appuyez sur Entrée pour ajouter un tag'
        kwargs['attrs']['data-role'] = 'tagsinput'
        super().__init__(*args, **kwargs)