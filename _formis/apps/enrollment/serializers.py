from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    PeriodeCandidature, DocumentRequis, Candidature, DocumentCandidature,
    Inscription, HistoriqueInscription, Transfert, Abandon
)

User = get_user_model()


class PeriodeCandidatureSerializer(serializers.ModelSerializer):
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    annee_academique_nom = serializers.CharField(source='annee_academique.nom', read_only=True)
    filieres_noms = serializers.StringRelatedField(source='filieres', many=True, read_only=True)
    est_ouverte = serializers.BooleanField(read_only=True)

    class Meta:
        model = PeriodeCandidature
        fields = [
            'id', 'nom', 'description', 'etablissement', 'etablissement_nom',
            'annee_academique', 'annee_academique_nom', 'date_debut', 'date_fin',
            'filieres', 'filieres_noms', 'est_active', 'est_ouverte',
            'created_at', 'updated_at'
        ]


class DocumentRequisSerializer(serializers.ModelSerializer):
    filiere_nom = serializers.CharField(source='filiere.nom', read_only=True)
    niveau_nom = serializers.CharField(source='niveau.nom', read_only=True)
    type_document_display = serializers.CharField(source='get_type_document_display', read_only=True)

    class Meta:
        model = DocumentRequis
        fields = [
            'id', 'filiere', 'filiere_nom', 'niveau', 'niveau_nom',
            'nom', 'description', 'type_document', 'type_document_display',
            'est_obligatoire', 'taille_maximale', 'formats_autorises',
            'ordre_affichage', 'created_at', 'updated_at'
        ]


class DocumentCandidatureSerializer(serializers.ModelSerializer):
    type_document_display = serializers.CharField(source='get_type_document_display', read_only=True)
    valide_par_nom = serializers.CharField(source='valide_par.get_full_name', read_only=True)
    fichier_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentCandidature
        fields = [
            'id', 'candidature', 'type_document', 'type_document_display',
            'nom', 'description', 'fichier', 'fichier_url', 'taille_fichier',
            'format_fichier', 'est_valide', 'valide_par', 'valide_par_nom',
            'date_validation', 'notes_validation', 'created_at', 'updated_at'
        ]

    def get_fichier_url(self, obj):
        if obj.fichier:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fichier.url)
            return obj.fichier.url
        return None


class CandidatureListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des candidatures (données minimales)"""
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    filiere_nom = serializers.CharField(source='filiere.nom', read_only=True)
    niveau_nom = serializers.CharField(source='niveau.nom', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    nom_complet = serializers.CharField(read_only=True)

    class Meta:
        model = Candidature
        fields = [
            'id', 'numero_candidature', 'nom_complet', 'email', 'telephone',
            'etablissement', 'etablissement_nom', 'filiere', 'filiere_nom',
            'niveau', 'niveau_nom', 'statut', 'statut_display',
            'date_soumission', 'created_at'
        ]


class CandidatureDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour une candidature"""
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    filiere_nom = serializers.CharField(source='filiere.nom', read_only=True)
    niveau_nom = serializers.CharField(source='niveau.nom', read_only=True)
    annee_academique_nom = serializers.CharField(source='annee_academique.nom', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    genre_display = serializers.CharField(source='get_genre_display', read_only=True)
    examine_par_nom = serializers.CharField(source='examine_par.get_full_name', read_only=True)
    documents = DocumentCandidatureSerializer(many=True, read_only=True)
    nom_complet = serializers.CharField(read_only=True)

    class Meta:
        model = Candidature
        fields = [
            'id', 'numero_candidature', 'etablissement', 'etablissement_nom',
            'filiere', 'filiere_nom', 'niveau', 'niveau_nom',
            'annee_academique', 'annee_academique_nom', 'prenom', 'nom', 'nom_complet',
            'date_naissance', 'lieu_naissance', 'genre', 'genre_display',
            'telephone', 'email', 'adresse', 'nom_pere', 'telephone_pere',
            'nom_mere', 'telephone_mere', 'nom_tuteur', 'telephone_tuteur',
            'ecole_precedente', 'dernier_diplome', 'annee_obtention',
            'statut', 'statut_display', 'date_soumission', 'date_examen',
            'date_decision', 'examine_par', 'examine_par_nom',
            'motif_rejet', 'notes_approbation', 'frais_dossier_requis',
            'montant_frais_dossier', 'frais_dossier_payes', 'date_paiement_frais',
            'documents', 'created_at', 'updated_at'
        ]

    def validate(self, data):
        """Validation personnalisée"""
        if 'date_naissance' in data:
            from django.utils import timezone
            today = timezone.now().date()
            age = today.year - data['date_naissance'].year
            if age < 15 or age > 100:
                raise serializers.ValidationError({
                    'date_naissance': 'Âge invalide (entre 15 et 100 ans)'
                })
        return data


class CandidatureCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier une candidature"""

    class Meta:
        model = Candidature
        fields = [
            'etablissement', 'filiere', 'niveau', 'annee_academique',
            'prenom', 'nom', 'date_naissance', 'lieu_naissance', 'genre',
            'telephone', 'email', 'adresse', 'nom_pere', 'telephone_pere',
            'nom_mere', 'telephone_mere', 'nom_tuteur', 'telephone_tuteur',
            'ecole_precedente', 'dernier_diplome', 'annee_obtention'
        ]

    def validate_email(self, value):
        # Vérifier l'unicité de l'email
        queryset = Candidature.objects.filter(email=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError("Cette adresse email est déjà utilisée.")
        return value


class InscriptionSerializer(serializers.ModelSerializer):
    candidature_numero = serializers.CharField(source='candidature.numero_candidature', read_only=True)
    apprenant_nom_complet = serializers.CharField(source='apprenant.get_full_name', read_only=True)
    classe_assignee_nom = serializers.CharField(source='classe_assignee.nom', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    statut_paiement_display = serializers.CharField(source='get_statut_paiement_display', read_only=True)
    cree_par_nom = serializers.CharField(source='cree_par.get_full_name', read_only=True)

    class Meta:
        model = Inscription
        fields = [
            'id', 'numero_inscription', 'candidature', 'candidature_numero',
            'apprenant', 'apprenant_nom_complet', 'classe_assignee', 'classe_assignee_nom',
            'date_inscription', 'date_debut', 'date_fin_prevue', 'date_fin_reelle',
            'statut', 'statut_display', 'statut_paiement', 'statut_paiement_display',
            'frais_scolarite', 'total_paye', 'solde', 'notes',
            'cree_par', 'cree_par_nom', 'created_at', 'updated_at'
        ]


class HistoriqueInscriptionSerializer(serializers.ModelSerializer):
    type_action_display = serializers.CharField(source='get_type_action_display', read_only=True)
    effectue_par_nom = serializers.CharField(source='effectue_par.get_full_name', read_only=True)

    class Meta:
        model = HistoriqueInscription
        fields = [
            'id', 'inscription', 'type_action', 'type_action_display',
            'ancienne_valeur', 'nouvelle_valeur', 'motif',
            'effectue_par', 'effectue_par_nom', 'created_at'
        ]


class TransfertSerializer(serializers.ModelSerializer):
    inscription_apprenant = serializers.CharField(source='inscription.apprenant.get_full_name', read_only=True)
    classe_origine_nom = serializers.CharField(source='classe_origine.nom', read_only=True)
    classe_destination_nom = serializers.CharField(source='classe_destination.nom', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    demande_par_nom = serializers.CharField(source='demande_par.get_full_name', read_only=True)
    approuve_par_nom = serializers.CharField(source='approuve_par.get_full_name', read_only=True)

    class Meta:
        model = Transfert
        fields = [
            'id', 'inscription', 'inscription_apprenant', 'classe_origine',
            'classe_origine_nom', 'classe_destination', 'classe_destination_nom',
            'date_transfert', 'date_effet', 'motif', 'statut', 'statut_display',
            'demande_par', 'demande_par_nom', 'approuve_par', 'approuve_par_nom',
            'date_approbation', 'notes_approbation', 'created_at', 'updated_at'
        ]

    def validate(self, data):
        inscription = data.get('inscription')
        classe_origine = data.get('classe_origine')
        classe_destination = data.get('classe_destination')

        if inscription and classe_origine:
            if inscription.classe_assignee != classe_origine:
                raise serializers.ValidationError({
                    'classe_origine': 'La classe d\'origine doit être la classe actuelle de l\'étudiant.'
                })

        if classe_origine and classe_destination:
            if classe_origine == classe_destination:
                raise serializers.ValidationError({
                    'classe_destination': 'La classe de destination doit être différente de la classe d\'origine.'
                })

        return data


class AbandonSerializer(serializers.ModelSerializer):
    inscription_apprenant = serializers.CharField(source='inscription.apprenant.get_full_name', read_only=True)
    type_abandon_display = serializers.CharField(source='get_type_abandon_display', read_only=True)
    traite_par_nom = serializers.CharField(source='traite_par.get_full_name', read_only=True)

    class Meta:
        model = Abandon
        fields = [
            'id', 'inscription', 'inscription_apprenant', 'date_abandon',
            'date_effet', 'type_abandon', 'type_abandon_display', 'motif',
            'eligible_remboursement', 'montant_remboursable', 'remboursement_traite',
            'date_remboursement', 'documents_retournes', 'materiel_retourne',
            'traite_par', 'traite_par_nom', 'created_at', 'updated_at'
        ]

    def validate(self, data):
        date_abandon = data.get('date_abandon')
        date_effet = data.get('date_effet')
        eligible_remboursement = data.get('eligible_remboursement')
        montant_remboursable = data.get('montant_remboursable')
        inscription = data.get('inscription')

        if date_abandon and date_effet:
            if date_effet < date_abandon:
                raise serializers.ValidationError({
                    'date_effet': 'La date d\'effet ne peut pas être antérieure à la date d\'abandon.'
                })

        if eligible_remboursement and not montant_remboursable:
            raise serializers.ValidationError({
                'montant_remboursable': 'Veuillez spécifier le montant remboursable si éligible.'
            })

        if montant_remboursable and inscription:
            if montant_remboursable > inscription.total_paye:
                raise serializers.ValidationError({
                    'montant_remboursable': 'Le montant remboursable ne peut pas dépasser le montant payé.'
                })

        return data


class CandidatureStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des candidatures"""
    total_candidatures = serializers.IntegerField()
    candidatures_brouillon = serializers.IntegerField()
    candidatures_soumises = serializers.IntegerField()
    candidatures_approuvees = serializers.IntegerField()
    candidatures_rejetees = serializers.IntegerField()
    candidatures_par_mois = serializers.ListField(child=serializers.DictField())


class InscriptionStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des inscriptions"""
    total_inscriptions = serializers.IntegerField()
    inscriptions_actives = serializers.IntegerField()
    inscriptions_suspendues = serializers.IntegerField()
    inscriptions_par_filiere = serializers.ListField(child=serializers.DictField())
    revenus_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    solde_restant = serializers.DecimalField(max_digits=12, decimal_places=2)

