# apps/enrollment/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import (
    PeriodeCandidature, DocumentRequis, Candidature, DocumentCandidature,
    Inscription, Transfert, Abandon
)

User = get_user_model()


class DateInput(forms.DateInput):
    """Widget personnalisé pour les dates"""
    input_type = 'date'

class PeriodeCandidatureForm(forms.ModelForm):
    """Formulaire pour les périodes de candidature"""

    class Meta:
        model = PeriodeCandidature
        fields = [
            'nom', 'description', 'etablissement', 'annee_academique',
            'date_debut', 'date_fin', 'filieres', 'est_active'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Candidatures Licence 2024-2025'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Description de la période de candidature...'
            }),
            'etablissement': forms.Select(attrs={'class': 'form-select'}),
            'annee_academique': forms.Select(attrs={'class': 'form-select'}),
            'date_debut': DateInput(attrs={'class': 'form-control'}),
            'date_fin': DateInput(attrs={'class': 'form-control'}),
            'filieres': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
            'est_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        labels = {
            'nom': 'Nom de la période',
            'description': 'Description',
            'etablissement': 'Établissement',
            'annee_academique': 'Année académique',
            'date_debut': 'Date de début',
            'date_fin': 'Date de fin',
            'filieres': 'Filières concernées',
            'est_active': 'Période active'
        }
        help_texts = {
            'filieres': 'Sélectionnez les filières pour lesquelles cette période est valide',
            'est_active': 'Décochez pour désactiver temporairement cette période'
        }

    def __init__(self, *args, **kwargs):
        self.etablissement = kwargs.pop('etablissement', None)
        super().__init__(*args, **kwargs)

        # Filtrer les filières selon l'établissement si spécifié
        if self.etablissement:
            self.fields['filieres'].queryset = self.fields['filieres'].queryset.filter(
                etablissement=self.etablissement
            )

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        etablissement = cleaned_data.get('etablissement')
        annee_academique = cleaned_data.get('annee_academique')

        if date_debut and date_fin:
            if date_debut >= date_fin:
                raise ValidationError({
                    'date_fin': 'La date de fin doit être postérieure à la date de début.'
                })

            # Vérifier la cohérence avec l'année académique
            if annee_academique:
                annee_debut = int(annee_academique.nom.split('-')[0])
                if date_debut.year != annee_debut and date_debut.year != annee_debut + 1:
                    raise ValidationError({
                        'date_debut': 'La date de début doit correspondre à l\'année académique sélectionnée.'
                    })

        # Vérifier l'unicité pour éviter les chevauchements
        if etablissement and date_debut and date_fin:
            existing = PeriodeCandidature.objects.filter(
                etablissement=etablissement,
                est_active=True
            ).filter(
                Q(date_debut__lte=date_fin) & Q(date_fin__gte=date_debut)
            )

            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(
                    'Une période de candidature active existe déjà pour ces dates dans cet établissement.'
                )

        return cleaned_data

class DocumentRequisForm(forms.ModelForm):
    """Formulaire pour les documents requis"""

    class Meta:
        model = DocumentRequis
        fields = [
            'nom', 'description', 'filiere', 'niveau', 'type_document',
            'est_obligatoire', 'taille_maximale', 'formats_autorises',
            'ordre_affichage'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Certificat de scolarité'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description détaillée du document requis...'
            }),
            'filiere': forms.Select(attrs={'class': 'form-select'}),
            'niveau': forms.Select(attrs={'class': 'form-select'}),
            'type_document': forms.Select(attrs={'class': 'form-select'}),
            'est_obligatoire': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'taille_maximale': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1024',
                'min': '1024',
                'max': '52428800'  # 50MB
            }),
            'formats_autorises': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'pdf,jpg,jpeg,png'
            }),
            'ordre_affichage': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '1'
            })
        }
        labels = {
            'taille_maximale': 'Taille maximale (octets)',
            'formats_autorises': 'Formats autorisés',
            'ordre_affichage': 'Ordre d\'affichage'
        }
        help_texts = {
            'taille_maximale': 'Taille maximale du fichier en octets (5MB = 5242880)',
            'formats_autorises': 'Formats séparés par des virgules (ex: pdf,jpg,png)',
            'niveau': 'Laissez vide pour appliquer à tous les niveaux de la filière'
        }

    def clean_formats_autorises(self):
        formats = self.cleaned_data['formats_autorises']
        if not formats:
            return formats

        formats_list = [f.strip().lower() for f in formats.split(',')]
        valid_formats = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'txt']

        invalid_formats = [f for f in formats_list if f not in valid_formats]
        if invalid_formats:
            raise ValidationError(
                f"Formats non autorisés: {', '.join(invalid_formats)}. "
                f"Formats valides: {', '.join(valid_formats)}"
            )

        return ','.join(formats_list)

    def clean_taille_maximale(self):
        taille = self.cleaned_data['taille_maximale']

        # Minimum 1KB, Maximum 50MB
        if taille < 1024:
            raise ValidationError('La taille minimale est de 1KB (1024 octets)')

        if taille > 52428800:  # 50MB
            raise ValidationError('La taille maximale est de 50MB (52428800 octets)')

        return taille

class CandidatureForm(forms.ModelForm):
    """Formulaire principal pour les candidatures"""

    class Meta:
        model = Candidature
        fields = [
            # Formation
            'etablissement', 'filiere', 'niveau', 'annee_academique',
            # Informations personnelles
            'prenom', 'nom', 'date_naissance', 'lieu_naissance', 'genre',
            'telephone', 'email', 'adresse',
            # Informations familiales
            'nom_pere', 'telephone_pere', 'nom_mere', 'telephone_mere',
            'nom_tuteur', 'telephone_tuteur',
            # Informations académiques
            'ecole_precedente', 'dernier_diplome', 'annee_obtention'
        ]
        widgets = {
            # Formation
            'etablissement': forms.Select(attrs={'class': 'form-select'}),
            'filiere': forms.Select(attrs={'class': 'form-select'}),
            'niveau': forms.Select(attrs={'class': 'form-select'}),
            'annee_academique': forms.Select(attrs={'class': 'form-select'}),

            # Informations personnelles
            'prenom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénom(s)'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de famille'
            }),
            'date_naissance': DateInput(attrs={'class': 'form-control'}),
            'lieu_naissance': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ville, Pays'
            }),
            'genre': forms.Select(attrs={'class': 'form-select'}),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+226 XX XX XX XX',
                'pattern': r'^(\+226|00226)?[0-9\s]{8,}$'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemple.com'
            }),
            'adresse': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Adresse complète'
            }),

            # Informations familiales
            'nom_pere': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom complet du père'
            }),
            'telephone_pere': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+226 XX XX XX XX'
            }),
            'nom_mere': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom complet de la mère'
            }),
            'telephone_mere': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+226 XX XX XX XX'
            }),
            'nom_tuteur': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom complet du tuteur'
            }),
            'telephone_tuteur': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+226 XX XX XX XX'
            }),

            # Informations académiques
            'ecole_precedente': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de l\'établissement précédent'
            }),
            'dernier_diplome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Baccalauréat série C'
            }),
            'annee_obtention': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1950',
                'max': str(timezone.now().year)
            })
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Rendre certains champs obligatoires
        required_fields = [
            'etablissement', 'filiere', 'niveau', 'annee_academique',
            'prenom', 'nom', 'date_naissance', 'lieu_naissance', 'genre',
            'telephone', 'email', 'adresse'
        ]

        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
                self.fields[field_name].widget.attrs['required'] = True

        # Filtrer les filières selon l'établissement
        if 'etablissement' in self.data:
            try:
                etablissement_id = int(self.data.get('etablissement'))
                self.fields['filiere'].queryset = self.fields['filiere'].queryset.filter(
                    etablissement_id=etablissement_id
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.etablissement_id:
            self.fields['filiere'].queryset = self.fields['filiere'].queryset.filter(
                etablissement_id=self.instance.etablissement_id
        )

    def clean_date_naissance(self):
        date_naissance = self.cleaned_data.get('date_naissance')
        if not date_naissance:
            return date_naissance

        today = timezone.now().date()
        age = today.year - date_naissance.year - (
                (today.month, today.day) < (date_naissance.month, date_naissance.day)
        )

        if age < 15:
            raise ValidationError("L'âge minimum requis est de 15 ans.")

        if age > 100:
            raise ValidationError("Veuillez vérifier la date de naissance.")

        # Pas de date future
        if date_naissance > today:
            raise ValidationError("La date de naissance ne peut pas être dans le futur.")

        return date_naissance

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            return email

        # Pour les nouvelles candidatures, vérifier s'il n'y a pas déjà une candidature active
        if not self.instance.pk:
            candidatures_actives = Candidature.objects.filter(
                email=email,
                statut__in=['SOUMISE', 'EN_COURS_EXAMEN', 'APPROUVEE']
            )

            if candidatures_actives.exists():
                candidature_active = candidatures_actives.first()
                raise ValidationError(
                    f"Vous avez déjà une candidature active ({candidature_active.numero_candidature}) "
                    f"pour {candidature_active.filiere.nom} à {candidature_active.etablissement.nom}."
                )

        # Vérifier l'unicité pour les brouillons (permet plusieurs brouillons du même email)
        queryset = Candidature.objects.filter(
            email=email,
            statut='BROUILLON'
        )
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        # Limiter le nombre de brouillons par email (optionnel)
        if queryset.count() >= 3:  # Maximum 3 brouillons par email
            raise ValidationError(
                "Vous avez trop de candidatures en cours. "
                "Veuillez terminer ou supprimer certaines avant d'en créer de nouvelles."
            )

        return email

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone')
        if not telephone:
            return telephone

        # Nettoyer le numéro
        telephone_clean = ''.join(c for c in telephone if c.isdigit() or c == '+')

        # Validation pour numéros burkinabés
        import re
        pattern = r'^(\+226|00226|226)?[0-9]{8}$'
        if not re.match(pattern, telephone_clean.replace(' ', '')):
            raise ValidationError(
                "Format de téléphone invalide. Utilisez le format: +226 XX XX XX XX ou XX XX XX XX"
            )

        return telephone

    def clean_annee_obtention(self):
        annee = self.cleaned_data.get('annee_obtention')
        if annee:
            current_year = timezone.now().year
            if annee < 1950 or annee > current_year:
                raise ValidationError(f"L'année doit être entre 1950 et {current_year}.")
        return annee

    def clean(self):
        cleaned_data = super().clean()

        # Vérifications supplémentaires pour éviter les doublons
        etablissement = cleaned_data.get('etablissement')
        filiere = cleaned_data.get('filiere')
        niveau = cleaned_data.get('niveau')
        annee_academique = cleaned_data.get('annee_academique')
        email = cleaned_data.get('email')

        if all([etablissement, filiere, niveau, annee_academique, email]):
            # Vérifier s'il n'y a pas déjà une candidature active pour cette combinaison
            candidatures_existantes = Candidature.objects.filter(
                email=email,
                etablissement=etablissement,
                filiere=filiere,
                niveau=niveau,
                annee_academique=annee_academique,
                statut__in=['SOUMISE', 'EN_COURS_EXAMEN', 'APPROUVEE']
            )

            if self.instance.pk:
                candidatures_existantes = candidatures_existantes.exclude(pk=self.instance.pk)

            if candidatures_existantes.exists():
                raise ValidationError(
                    "Une candidature active existe déjà pour cette formation avec cette adresse email."
                )

        return cleaned_data

class DocumentCandidatureForm(forms.ModelForm):
    """Formulaire pour les documents de candidature"""

    class Meta:
        model = DocumentCandidature
        fields = ['type_document', 'nom', 'description', 'fichier']
        widgets = {
            'type_document': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du document'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description optionnelle...'
            }),
            'fichier': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
            })
        }

    def __init__(self, *args, **kwargs):
        self.candidature = kwargs.pop('candidature', None)
        super().__init__(*args, **kwargs)

        if self.candidature:
            # Filtrer les types de documents selon la filière et le niveau
            docs_requis = DocumentRequis.objects.filter(
                filiere=self.candidature.filiere
            ).filter(
                Q(niveau=self.candidature.niveau) | Q(niveau__isnull=True)
            )

            # Créer les choix disponibles
            choices = [('', '---------')]
            for doc in docs_requis:
                # Vérifier si ce type de document n'est pas déjà fourni
                if not self.candidature.documents.filter(
                        type_document=doc.type_document
                ).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
                    choices.append((doc.type_document, doc.nom))

            self.fields['type_document'].choices = choices

    def clean_fichier(self):
        fichier = self.cleaned_data.get('fichier')
        if not fichier:
            return fichier

        # Vérifier la taille et le format selon les exigences
        if self.candidature:
            type_doc = self.cleaned_data.get('type_document')
            if type_doc:
                try:
                    doc_requis = DocumentRequis.objects.get(
                        filiere=self.candidature.filiere,
                        type_document=type_doc
                    )

                    # Vérifier la taille
                    if fichier.size > doc_requis.taille_maximale:
                        raise ValidationError(
                            f"Le fichier est trop volumineux. Taille maximale: "
                            f"{doc_requis.taille_maximale / (1024 * 1024):.1f}MB"
                        )

                    # Vérifier le format
                    extension = fichier.name.split('.')[-1].lower()
                    formats_autorises = doc_requis.formats_autorises.split(',')
                    if extension not in formats_autorises:
                        raise ValidationError(
                            f"Format de fichier non autorisé. Formats acceptés: "
                            f"{', '.join(formats_autorises)}"
                        )

                except DocumentRequis.DoesNotExist:
                    # Validation générale si pas de document requis spécifique
                    if fichier.size > 10 * 1024 * 1024:  # 10MB
                        raise ValidationError("Le fichier est trop volumineux (max 10MB)")

                    extension = fichier.name.split('.')[-1].lower()
                    if extension not in ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']:
                        raise ValidationError("Format de fichier non autorisé")

        return fichier

class CandidatureFilterForm(forms.Form):
    """Formulaire de filtrage des candidatures"""

    STATUT_CHOICES = [('', 'Tous les statuts')] + Candidature.STATUTS_CANDIDATURE

    statut = forms.ChoiceField(
        choices=STATUT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    etablissement = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Tous les établissements",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    filiere = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Toutes les filières",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    niveau = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Tous les niveaux",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    date_debut = forms.DateField(
        required=False,
        widget=DateInput(attrs={'class': 'form-control'}),
        label="À partir du"
    )

    date_fin = forms.DateField(
        required=False,
        widget=DateInput(attrs={'class': 'form-control'}),
        label="Jusqu'au"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from apps.establishments.models import Etablissement
        from apps.academic.models import Filiere, Niveau

        self.fields['etablissement'].queryset = Etablissement.objects.all()
        self.fields['filiere'].queryset = Filiere.objects.all()
        self.fields['niveau'].queryset = Niveau.objects.all()


class InscriptionForm(forms.ModelForm):
    """Formulaire pour les inscriptions"""

    class Meta:
        model = Inscription
        fields = [
            'candidature', 'apprenant', 'classe_assignee',
            'date_debut', 'date_fin_prevue', 'frais_scolarite', 'notes'
        ]
        widgets = {
            'candidature': forms.Select(attrs={'class': 'form-select'}),
            'apprenant': forms.Select(attrs={'class': 'form-select'}),
            'classe_assignee': forms.Select(attrs={'class': 'form-select'}),
            'date_debut': DateInput(attrs={'class': 'form-control'}),
            'date_fin_prevue': DateInput(attrs={'class': 'form-control'}),
            'frais_scolarite': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Notes sur l\'inscription...'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrer les candidatures approuvées sans inscription
        self.fields['candidature'].queryset = Candidature.objects.filter(
            statut='APPROUVEE'
        ).exclude(inscription__isnull=False)

        # Filtrer les utilisateurs avec le rôle APPRENANT
        self.fields['apprenant'].queryset = User.objects.filter(role='APPRENANT')

    def clean(self):
        cleaned_data = super().clean()
        candidature = cleaned_data.get('candidature')
        classe_assignee = cleaned_data.get('classe_assignee')
        date_debut = cleaned_data.get('date_debut')
        date_fin_prevue = cleaned_data.get('date_fin_prevue')

        if candidature and classe_assignee:
            # Vérifier la cohérence filière/niveau
            if (candidature.filiere != classe_assignee.filiere or
                    candidature.niveau != classe_assignee.niveau):
                raise ValidationError({
                    'classe_assignee': 'La classe doit correspondre à la filière et au niveau de la candidature.'
                })

        if date_debut and date_fin_prevue:
            if date_debut >= date_fin_prevue:
                raise ValidationError({
                    'date_fin_prevue': 'La date de fin doit être postérieure à la date de début.'
                })

        return cleaned_data


class TransfertForm(forms.ModelForm):
    """Formulaire pour les transferts"""

    class Meta:
        model = Transfert
        fields = [
            'inscription', 'classe_origine', 'classe_destination',
            'date_transfert', 'date_effet', 'motif'
        ]
        widgets = {
            'inscription': forms.Select(attrs={'class': 'form-select'}),
            'classe_origine': forms.Select(attrs={'class': 'form-select'}),
            'classe_destination': forms.Select(attrs={'class': 'form-select'}),
            'date_transfert': DateInput(attrs={'class': 'form-control'}),
            'date_effet': DateInput(attrs={'class': 'form-control'}),
            'motif': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Motif détaillé du transfert...',
                'required': True
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrer les inscriptions actives
        self.fields['inscription'].queryset = Inscription.objects.filter(
            statut='ACTIVE'
        ).select_related('apprenant', 'classe_assignee')

    def clean(self):
        cleaned_data = super().clean()
        inscription = cleaned_data.get('inscription')
        classe_origine = cleaned_data.get('classe_origine')
        classe_destination = cleaned_data.get('classe_destination')
        date_transfert = cleaned_data.get('date_transfert')
        date_effet = cleaned_data.get('date_effet')

        if inscription and classe_origine:
            if inscription.classe_assignee != classe_origine:
                raise ValidationError({
                    'classe_origine': 'La classe d\'origine doit être la classe actuelle de l\'étudiant.'
                })

        if classe_origine and classe_destination:
            if classe_origine == classe_destination:
                raise ValidationError({
                    'classe_destination': 'La classe de destination doit être différente de la classe d\'origine.'
                })

        if date_transfert and date_effet:
            if date_effet < date_transfert:
                raise ValidationError({
                    'date_effet': 'La date d\'effet ne peut pas être antérieure à la date de transfert.'
                })

        return cleaned_data


class AbandonForm(forms.ModelForm):
    """Formulaire pour les abandons"""

    class Meta:
        model = Abandon
        fields = [
            'inscription', 'date_abandon', 'date_effet', 'type_abandon',
            'motif', 'eligible_remboursement', 'montant_remboursable'
        ]
        widgets = {
            'inscription': forms.Select(attrs={'class': 'form-select'}),
            'date_abandon': DateInput(attrs={'class': 'form-control'}),
            'date_effet': DateInput(attrs={'class': 'form-control'}),
            'type_abandon': forms.Select(attrs={'class': 'form-select'}),
            'motif': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Décrivez en détail les raisons de l\'abandon...',
                'required': True
            }),
            'eligible_remboursement': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'montant_remboursable': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrer les inscriptions actives ou suspendues
        self.fields['inscription'].queryset = Inscription.objects.filter(
            statut__in=['ACTIVE', 'SUSPENDED']
        ).select_related('apprenant')

    def clean(self):
        cleaned_data = super().clean()
        inscription = cleaned_data.get('inscription')
        date_abandon = cleaned_data.get('date_abandon')
        date_effet = cleaned_data.get('date_effet')
        eligible_remboursement = cleaned_data.get('eligible_remboursement')
        montant_remboursable = cleaned_data.get('montant_remboursable')

        if date_abandon and date_effet:
            if date_effet < date_abandon:
                raise ValidationError({
                    'date_effet': 'La date d\'effet ne peut pas être antérieure à la date d\'abandon.'
                })

        if eligible_remboursement:
            if not montant_remboursable or montant_remboursable <= 0:
                raise ValidationError({
                    'montant_remboursable': 'Veuillez spécifier un montant remboursable valide.'
                })

        if montant_remboursable and inscription:
            if montant_remboursable > inscription.total_paye:
                raise ValidationError({
                    'montant_remboursable': 'Le montant remboursable ne peut pas dépasser le montant payé.'
                })

        return cleaned_data


class CandidatureEvaluationForm(forms.Form):
    """Formulaire pour l'évaluation des candidatures"""

    DECISION_CHOICES = [
        ('APPROUVEE', 'Approuver la candidature'),
        ('REJETEE', 'Rejeter la candidature'),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Décision"
    )

    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Commentaires sur la décision...'
        }),
        required=False,
        label="Notes et commentaires"
    )

    def clean(self):
        cleaned_data = super().clean()
        decision = cleaned_data.get('decision')
        notes = cleaned_data.get('notes')

        if decision == 'REJETEE' and not notes:
            raise ValidationError({
                'notes': 'Les notes sont obligatoires en cas de rejet de candidature.'
            })

        return cleaned_data


class BulkUploadForm(forms.Form):
    """Formulaire pour l'upload en masse de candidatures"""

    fichier_excel = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        }),
        label="Fichier Excel",
        help_text="Fichier Excel (.xlsx ou .xls) contenant les données des candidatures"
    )

    etablissement = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Établissement",
        help_text="Établissement pour toutes les candidatures du fichier"
    )

    annee_academique = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Année académique",
        help_text="Année académique pour toutes les candidatures du fichier"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from apps.establishments.models import Etablissement, AnneeAcademique

        self.fields['etablissement'].queryset = Etablissement.objects.all()
        self.fields['annee_academique'].queryset = AnneeAcademique.objects.all()

    def clean_fichier_excel(self):
        fichier = self.cleaned_data['fichier_excel']

        if not fichier.name.lower().endswith(('.xlsx', '.xls')):
            raise ValidationError("Seuls les fichiers Excel (.xlsx, .xls) sont acceptés.")

        # Vérifier la taille (max 10MB)
        if fichier.size > 10 * 1024 * 1024:
            raise ValidationError("Le fichier est trop volumineux (maximum 10MB).")

        return fichier


class InscriptionFilterForm(forms.Form):
    """Formulaire de filtrage des inscriptions"""

    STATUT_CHOICES = [('', 'Tous les statuts')] + Inscription.STATUTS_INSCRIPTION
    PAIEMENT_CHOICES = [('', 'Tous les statuts')] + Inscription.STATUTS_PAIEMENT

    statut = forms.ChoiceField(
        choices=STATUT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    statut_paiement = forms.ChoiceField(
        choices=PAIEMENT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Statut de paiement"
    )

    etablissement = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Tous les établissements",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    filiere = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Toutes les filières",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    classe = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Toutes les classes",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    annee_inscription = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Année d'inscription"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from apps.establishments.models import Etablissement
        from apps.academic.models import Filiere, Classe

        self.fields['etablissement'].queryset = Etablissement.objects.all()
        self.fields['filiere'].queryset = Filiere.objects.all()
        self.fields['classe'].queryset = Classe.objects.all()

        # Générer les choix d'années
        current_year = timezone.now().year
        year_choices = [('', 'Toutes les années')]
        for year in range(current_year - 10, current_year + 2):
            year_choices.append((str(year), str(year)))
        self.fields['annee_inscription'].choices = year_choices


class DocumentValidationForm(forms.Form):
    """Formulaire pour la validation des documents"""

    est_valide = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Document valide"
    )

    notes_validation = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Notes sur la validation du document...'
        }),
        required=False,
        label="Notes de validation"
    )

    def clean(self):
        cleaned_data = super().clean()
        est_valide = cleaned_data.get('est_valide')
        notes_validation = cleaned_data.get('notes_validation')

        if not est_valide and not notes_validation:
            raise ValidationError({
                'notes_validation': 'Veuillez préciser les raisons si le document n\'est pas valide.'
            })

        return cleaned_data


class StatisticsFilterForm(forms.Form):
    """Formulaire de filtrage pour les statistiques"""

    PERIODE_CHOICES = [
        ('7', 'Derniers 7 jours'),
        ('30', 'Derniers 30 jours'),
        ('90', 'Derniers 3 mois'),
        ('365', 'Dernière année'),
        ('custom', 'Période personnalisée'),
    ]

    periode = forms.ChoiceField(
        choices=PERIODE_CHOICES,
        initial='30',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Période"
    )

    date_debut = forms.DateField(
        required=False,
        widget=DateInput(attrs={'class': 'form-control'}),
        label="Date de début"
    )

    date_fin = forms.DateField(
        required=False,
        widget=DateInput(attrs={'class': 'form-control'}),
        label="Date de fin"
    )

    etablissement = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Tous les établissements",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    filiere = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Toutes les filières",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from apps.establishments.models import Etablissement
        from apps.academic.models import Filiere

        self.fields['etablissement'].queryset = Etablissement.objects.all()
        self.fields['filiere'].queryset = Filiere.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        periode = cleaned_data.get('periode')
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if periode == 'custom':
            if not date_debut or not date_fin:
                raise ValidationError("Veuillez spécifier les dates de début et de fin pour une période personnalisée.")

            if date_debut >= date_fin:
                raise ValidationError({
                    'date_fin': 'La date de fin doit être postérieure à la date de début.'
                })

        return cleaned_data


class QuickSearchForm(forms.Form):
    """Formulaire de recherche rapide"""

    TYPE_CHOICES = [
        ('candidature', 'Candidature'),
        ('inscription', 'Inscription'),
        ('apprenant', 'Étudiant'),
    ]

    query = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher par nom, numéro, email...',
            'autocomplete': 'off'
        }),
        label="Recherche",
        max_length=200
    )

    type_search = forms.ChoiceField(
        choices=TYPE_CHOICES,
        initial='candidature',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Type"
    )

    def clean_query(self):
        query = self.cleaned_data['query'].strip()
        if len(query) < 2:
            raise ValidationError("La recherche doit contenir au moins 2 caractères.")
        return query


class PasswordChangeForm(forms.Form):
    """Formulaire de changement de mot de passe pour les étudiants"""

    ancien_mot_de_passe = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ancien mot de passe'
        }),
        label="Ancien mot de passe"
    )

    nouveau_mot_de_passe = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nouveau mot de passe'
        }),
        label="Nouveau mot de passe",
        min_length=8,
        help_text="Le mot de passe doit contenir au moins 8 caractères."
    )

    confirmer_mot_de_passe = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmer le nouveau mot de passe'
        }),
        label="Confirmer le mot de passe"
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_ancien_mot_de_passe(self):
        ancien_mot_de_passe = self.cleaned_data['ancien_mot_de_passe']

        if self.user and not self.user.check_password(ancien_mot_de_passe):
            raise ValidationError("L'ancien mot de passe est incorrect.")

        return ancien_mot_de_passe

    def clean(self):
        cleaned_data = super().clean()
        nouveau_mot_de_passe = cleaned_data.get('nouveau_mot_de_passe')
        confirmer_mot_de_passe = cleaned_data.get('confirmer_mot_de_passe')

        if nouveau_mot_de_passe and confirmer_mot_de_passe:
            if nouveau_mot_de_passe != confirmer_mot_de_passe:
                raise ValidationError({
                    'confirmer_mot_de_passe': 'Les mots de passe ne correspondent pas.'
                })

        return cleaned_data


class ContactForm(forms.Form):
    """Formulaire de contact pour support"""

    SUJET_CHOICES = [
        ('candidature', 'Question sur candidature'),
        ('inscription', 'Question sur inscription'),
        ('documents', 'Problème avec documents'),
        ('technique', 'Problème technique'),
        ('autre', 'Autre'),
    ]

    nom = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre nom complet'
        }),
        max_length=100
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'votre.email@exemple.com'
        })
    )

    sujet = forms.ChoiceField(
        choices=SUJET_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Décrivez votre question ou problème...'
        }),
        min_length=10,
        max_length=1000
    )

    def clean_message(self):
        message = self.cleaned_data['message'].strip()

        if len(message) < 10:
            raise ValidationError("Le message doit contenir au moins 10 caractères.")

        return message

