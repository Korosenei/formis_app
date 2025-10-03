from rest_framework import serializers
from ..models import (
    Localite, TypeEtablissement, Etablissement, AnneeAcademique,
    BaremeNotation, NiveauNote, ParametresEtablissement, Salle,
    JourFerie, Campus
)


class LocaliteSerializer(serializers.ModelSerializer):
    nombre_etablissements = serializers.SerializerMethodField()

    class Meta:
        model = Localite
        fields = [
            'id', 'nom', 'region', 'pays', 'code_postal',
            'created_at', 'updated_at', 'nombre_etablissements'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_nombre_etablissements(self, obj):
        return obj.etablissement_set.filter(actif=True).count()


class TypeEtablissementSerializer(serializers.ModelSerializer):
    nombre_etablissements = serializers.SerializerMethodField()

    class Meta:
        model = TypeEtablissement
        fields = [
            'id', 'nom', 'description', 'code', 'structure_academique_defaut',
            'icone', 'actif', 'created_at', 'updated_at', 'nombre_etablissements'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_nombre_etablissements(self, obj):
        return obj.etablissement_set.filter(actif=True).count()


class NiveauNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = NiveauNote
        fields = [
            'id', 'nom', 'note_minimale', 'note_maximale',
            'couleur', 'description', 'points_gpa'
        ]


class BaremeNotationSerializer(serializers.ModelSerializer):
    niveaux_notes = NiveauNoteSerializer(many=True, read_only=True)
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)

    class Meta:
        model = BaremeNotation
        fields = [
            'id', 'etablissement', 'etablissement_nom', 'nom',
            'note_minimale', 'note_maximale', 'note_passage',
            'est_defaut', 'description', 'niveaux_notes'
        ]


class ParametresEtablissementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametresEtablissement
        fields = [
            'id', 'etablissement', 'structure_academique', 'bareme_notation_defaut',
            'frais_dossier_requis', 'montant_frais_dossier',
            'date_limite_inscription_anticipée', 'date_limite_inscription_normale',
            'date_limite_inscription_tardive', 'paiement_echelonne_autorise',
            'nombre_maximum_tranches', 'frais_echelonnement', 'taux_penalite_retard',
            'taux_presence_minimum', 'points_bonus_autorises', 'points_bonus_maximum',
            'notifications_sms', 'notifications_email', 'jours_avant_reset_mot_de_passe',
            'tentatives_connexion_max', 'examens_rattrapage_autorises',
            'frais_examen_rattrapage', 'couleur_primaire', 'couleur_secondaire'
        ]


class SalleSerializer(serializers.ModelSerializer):
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    type_salle_display = serializers.CharField(source='get_type_salle_display', read_only=True)
    etat_display = serializers.CharField(source='get_etat_display', read_only=True)
    surface = serializers.ReadOnlyField()
    liste_equipements = serializers.ReadOnlyField(source='get_liste_equipements')

    class Meta:
        model = Salle
        fields = [
            'id', 'etablissement', 'etablissement_nom', 'nom', 'code',
            'type_salle', 'type_salle_display', 'capacite', 'etage', 'batiment',
            'longueur', 'largeur', 'surface', 'projecteur', 'ordinateur',
            'climatisation', 'wifi', 'tableau_blanc', 'systeme_audio',
            'accessible_pmr', 'etat', 'etat_display', 'description', 'notes',
            'est_active', 'liste_equipements', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CampusSerializer(serializers.ModelSerializer):
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    localite_nom = serializers.CharField(source='localite.nom', read_only=True)
    responsable_nom = serializers.CharField(source='responsable_campus.get_full_name', read_only=True)
    liste_services = serializers.ReadOnlyField(source='get_liste_services')

    class Meta:
        model = Campus
        fields = [
            'id', 'etablissement', 'etablissement_nom', 'nom', 'code',
            'adresse', 'localite', 'localite_nom', 'latitude', 'longitude',
            'description', 'superficie_totale', 'bibliotheque', 'cafeteria',
            'parking', 'internat', 'installations_sportives', 'infirmerie',
            'telephone', 'email', 'responsable_campus', 'responsable_nom',
            'est_campus_principal', 'est_actif', 'liste_services',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AnneeAcademiqueSerializer(serializers.ModelSerializer):
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)

    class Meta:
        model = AnneeAcademique
        fields = [
            'id', 'etablissement', 'etablissement_nom', 'nom',
            'date_debut', 'date_fin', 'debut_inscriptions', 'fin_inscriptions',
            'debut_cours', 'fin_cours', 'debut_examens_premier_semestre',
            'fin_examens_premier_semestre', 'debut_examens_second_semestre',
            'fin_examens_second_semestre', 'debut_vacances_hiver',
            'fin_vacances_hiver', 'debut_vacances_ete', 'fin_vacances_ete',
            'est_courante', 'est_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class JourFerieSerializer(serializers.ModelSerializer):
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    type_jour_ferie_display = serializers.CharField(source='get_type_jour_ferie_display', read_only=True)
    duree_jours = serializers.ReadOnlyField()

    class Meta:
        model = JourFerie
        fields = [
            'id', 'etablissement', 'etablissement_nom', 'nom',
            'date_debut', 'date_fin', 'duree_jours', 'type_jour_ferie',
            'type_jour_ferie_display', 'description', 'est_recurrent',
            'modele_recurrence', 'affecte_cours', 'affecte_examens',
            'affecte_inscriptions', 'couleur', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EtablissementListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des établissements (vue simplifiée)"""
    type_etablissement_nom = serializers.CharField(source='type_etablissement.nom', read_only=True)
    localite_nom = serializers.CharField(source='localite.nom', read_only=True)
    taux_occupation = serializers.ReadOnlyField()

    class Meta:
        model = Etablissement
        fields = [
            'id', 'nom', 'sigle', 'code', 'type_etablissement_nom',
            'localite_nom', 'adresse', 'telephone', 'email',
            'capacite_totale', 'etudiants_actuels', 'taux_occupation',
            'actif', 'public', 'created_at'
        ]


class EtablissementDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un établissement"""
    type_etablissement = TypeEtablissementSerializer(read_only=True)
    localite = LocaliteSerializer(read_only=True)
    parametres = ParametresEtablissementSerializer(read_only=True)
    campuses = CampusSerializer(many=True, read_only=True)
    salles = SalleSerializer(many=True, read_only=True, source='salle_set')
    annees_academiques = AnneeAcademiqueSerializer(many=True, read_only=True, source='anneeacademique_set')
    baremes_notation = BaremeNotationSerializer(many=True, read_only=True, source='baremenotation_set')
    jours_feries = JourFerieSerializer(many=True, read_only=True, source='jourferie_set')
    taux_occupation = serializers.ReadOnlyField()

    # Statistiques
    total_salles = serializers.SerializerMethodField()
    total_campus = serializers.SerializerMethodField()
    salles_par_type = serializers.SerializerMethodField()

    class Meta:
        model = Etablissement
        fields = [
            'id', 'nom', 'sigle', 'code', 'type_etablissement', 'localite',
            'adresse', 'telephone', 'email', 'site_web', 'nom_directeur',
            'numero_enregistrement', 'date_creation', 'logo', 'image_couverture',
            'description', 'mission', 'vision', 'capacite_totale', 'etudiants_actuels',
            'taux_occupation', 'actif', 'public', 'parametres', 'campuses',
            'salles', 'annees_academiques', 'baremes_notation', 'jours_feries',
            'total_salles', 'total_campus', 'salles_par_type',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_salles(self, obj):
        return obj.salle_set.filter(est_active=True).count()

    def get_total_campus(self, obj):
        return obj.campuses.filter(est_actif=True).count()

    def get_salles_par_type(self, obj):
        salles = obj.salle_set.filter(est_active=True)
        stats = {}
        for type_salle in Salle.TYPES_SALLE:
            stats[type_salle[1]] = salles.filter(type_salle=type_salle[0]).count()
        return stats


class EtablissementCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour création/modification d'établissement"""

    class Meta:
        model = Etablissement
        fields = [
            'nom', 'sigle', 'code', 'type_etablissement', 'localite',
            'adresse', 'telephone', 'email', 'site_web', 'nom_directeur',
            'numero_enregistrement', 'date_creation', 'logo', 'image_couverture',
            'description', 'mission', 'vision', 'capacite_totale', 'actif', 'public'
        ]

    def validate_code(self, value):
        """Validation du code unique"""
        if self.instance:
            # Modification : exclure l'instance actuelle
            if Etablissement.objects.filter(code=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("Ce code existe déjà.")
        else:
            # Création : vérifier l'unicité
            if Etablissement.objects.filter(code=value).exists():
                raise serializers.ValidationError("Ce code existe déjà.")
        return value.upper()

