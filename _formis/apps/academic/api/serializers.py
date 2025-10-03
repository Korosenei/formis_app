
from rest_framework import serializers
from ..models import (
    Departement, Filiere, Niveau, Classe, 
    PeriodeAcademique, Programme
)


class DepartementListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des départements"""
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    chef_nom = serializers.CharField(source='chef.get_full_name', read_only=True)
    nombre_filieres = serializers.IntegerField(read_only=True)

    class Meta:
        model = Departement
        fields = [
            'id', 'nom', 'code', 'etablissement', 'etablissement_nom',
            'chef', 'chef_nom', 'telephone', 'email', 'bureau',
            'est_actif', 'nombre_filieres', 'created_at', 'updated_at'
        ]


class DepartementDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un département"""
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    chef_nom = serializers.CharField(source='chef.get_full_name', read_only=True)
    filieres = serializers.StringRelatedField(many=True, source='filiere_set', read_only=True)

    class Meta:
        model = Departement
        fields = [
            'id', 'nom', 'code', 'description', 'etablissement', 
            'etablissement_nom', 'chef', 'chef_nom', 'telephone',
            'email', 'bureau', 'est_actif', 'filieres',
            'created_at', 'updated_at'
        ]


class DepartementCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier un département"""
    
    class Meta:
        model = Departement
        fields = [
            'etablissement', 'nom', 'code', 'description',
            'chef', 'telephone', 'email', 'bureau', 'est_actif'
        ]

    def validate_code(self):
        code = self.validated_data['code']
        etablissement = self.validated_data['etablissement']
        
        queryset = Departement.objects.filter(
            etablissement=etablissement,
            code=code
        )
        
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError(
                f"Un département avec ce code existe déjà dans {etablissement}"
            )
        
        return code


class FiliereListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des filières"""
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    departement_nom = serializers.CharField(source='departement.nom', read_only=True)
    nombre_niveaux = serializers.IntegerField(read_only=True)

    class Meta:
        model = Filiere
        fields = [
            'id', 'nom', 'code', 'etablissement', 'etablissement_nom',
            'departement', 'departement_nom', 'type_filiere', 'duree_annees',
            'nom_diplome', 'frais_scolarite', 'capacite_maximale',
            'nombre_niveaux', 'est_active', 'created_at'
        ]


class FiliereDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour une filière"""
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    departement_nom = serializers.CharField(source='departement.nom', read_only=True)
    niveaux = serializers.StringRelatedField(many=True, read_only=True)
    programme = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Filiere
        fields = [
            'id', 'nom', 'code', 'description', 'etablissement',
            'etablissement_nom', 'departement', 'departement_nom',
            'duree_annees', 'nom_diplome', 'type_filiere', 'prerequis',
            'frais_scolarite', 'capacite_maximale', 'niveaux', 'programme',
            'est_active', 'created_at', 'updated_at'
        ]


class FiliereCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier une filière"""
    
    class Meta:
        model = Filiere
        fields = [
            'etablissement', 'departement', 'nom', 'code', 'description',
            'duree_annees', 'nom_diplome', 'type_filiere', 'prerequis',
            'frais_scolarite', 'capacite_maximale', 'est_active'
        ]

    def validate(self, attrs):
        # Vérifier que le département appartient à l'établissement
        departement = attrs.get('departement')
        etablissement = attrs.get('etablissement')
        
        if departement and etablissement:
            if departement.etablissement != etablissement:
                raise serializers.ValidationError(
                    "Le département sélectionné n'appartient pas à cet établissement."
                )
        
        return attrs

    def validate_code(self):
        code = self.validated_data['code']
        etablissement = self.validated_data['etablissement']
        
        queryset = Filiere.objects.filter(
            etablissement=etablissement,
            code=code
        )
        
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError(
                f"Une filière avec ce code existe déjà dans {etablissement}"
            )
        
        return code


class NiveauListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des niveaux"""
    filiere_nom = serializers.CharField(source='filiere.nom', read_only=True)
    etablissement_nom = serializers.CharField(source='filiere.etablissement.nom', read_only=True)
    nombre_classes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Niveau
        fields = [
            'id', 'nom', 'code', 'ordre', 'filiere', 'filiere_nom',
            'etablissement_nom', 'frais_scolarite', 'nombre_classes',
            'est_actif', 'created_at'
        ]


class NiveauDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un niveau"""
    filiere_nom = serializers.CharField(source='filiere.nom', read_only=True)
    classes = serializers.StringRelatedField(many=True, source='classe_set', read_only=True)

    class Meta:
        model = Niveau
        fields = [
            'id', 'nom', 'code', 'ordre', 'description', 'filiere',
            'filiere_nom', 'frais_scolarite', 'classes',
            'est_actif', 'created_at', 'updated_at'
        ]


class NiveauCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier un niveau"""
    
    class Meta:
        model = Niveau
        fields = [
            'filiere', 'nom', 'code', 'ordre', 'description',
            'frais_scolarite', 'est_actif'
        ]

    def validate_ordre(self):
        ordre = self.validated_data['ordre']
        filiere = self.validated_data['filiere']
        
        queryset = Niveau.objects.filter(filiere=filiere, ordre=ordre)
        
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError(
                f"Un niveau avec cet ordre existe déjà dans la filière {filiere}"
            )
        
        return ordre


class ClasseListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des classes"""
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    niveau_nom = serializers.CharField(source='niveau.nom', read_only=True)
    filiere_nom = serializers.CharField(source='niveau.filiere.nom', read_only=True)
    annee_nom = serializers.CharField(source='annee_academique.nom', read_only=True)
    professeur_nom = serializers.CharField(source='professeur_principal.get_full_name', read_only=True)
    places_disponibles = serializers.IntegerField(read_only=True)

    class Meta:
        model = Classe
        fields = [
            'id', 'nom', 'code', 'etablissement', 'etablissement_nom',
            'niveau', 'niveau_nom', 'filiere_nom', 'annee_academique',
            'annee_nom', 'professeur_principal', 'professeur_nom',
            'capacite_maximale', 'effectif_actuel', 'places_disponibles',
            'est_active', 'created_at'
        ]


class ClasseDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour une classe"""
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    niveau_nom = serializers.CharField(source='niveau.nom', read_only=True)
    filiere_nom = serializers.CharField(source='niveau.filiere.nom', read_only=True)
    annee_nom = serializers.CharField(source='annee_academique.nom', read_only=True)
    professeur_nom = serializers.CharField(source='professeur_principal.get_full_name', read_only=True)
    salle_nom = serializers.CharField(source='salle_principale.nom', read_only=True)
    places_disponibles = serializers.SerializerMethodField()
    est_pleine = serializers.SerializerMethodField()

    class Meta:
        model = Classe
        fields = [
            'id', 'nom', 'code', 'etablissement', 'etablissement_nom',
            'niveau', 'niveau_nom', 'filiere_nom', 'annee_academique',
            'annee_nom', 'professeur_principal', 'professeur_nom',
            'salle_principale', 'salle_nom', 'capacite_maximale',
            'effectif_actuel', 'places_disponibles', 'est_pleine',
            'est_active', 'created_at', 'updated_at'
        ]

    def get_places_disponibles(self, obj):
        return obj.get_places_disponibles()

    def get_est_pleine(self, obj):
        return obj.est_pleine()


class ClasseCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier une classe"""
    
    class Meta:
        model = Classe
        fields = [
            'etablissement', 'niveau', 'annee_academique', 'nom', 'code',
            'professeur_principal', 'salle_principale', 'capacite_maximale',
            'effectif_actuel', 'est_active'
        ]

    def validate_effectif_actuel(self):
        effectif = self.validated_data['effectif_actuel']
        capacite = self.validated_data.get('capacite_maximale')
        
        if capacite and effectif > capacite:
            raise serializers.ValidationError(
                "L'effectif actuel ne peut pas dépasser la capacité maximale"
            )
        
        return effectif


class PeriodeAcademiqueListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des périodes académiques"""
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    annee_nom = serializers.CharField(source='annee_academique.nom', read_only=True)

    class Meta:
        model = PeriodeAcademique
        fields = [
            'id', 'nom', 'code', 'etablissement', 'etablissement_nom',
            'annee_academique', 'annee_nom', 'type_periode', 'ordre',
            'date_debut', 'date_fin', 'est_courante', 'est_active'
        ]


class PeriodeAcademiqueDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour une période académique"""
    etablissement_nom = serializers.CharField(source='etablissement.nom', read_only=True)
    annee_nom = serializers.CharField(source='annee_academique.nom', read_only=True)

    class Meta:
        model = PeriodeAcademique
        fields = [
            'id', 'nom', 'code', 'etablissement', 'etablissement_nom',
            'annee_academique', 'annee_nom', 'type_periode', 'ordre',
            'date_debut', 'date_fin', 'date_limite_inscription',
            'date_debut_examens', 'date_fin_examens', 'date_publication_resultats',
            'est_courante', 'est_active', 'created_at', 'updated_at'
        ]


class PeriodeAcademiqueCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier une période académique"""
    
    class Meta:
        model = PeriodeAcademique
        fields = [
            'etablissement', 'annee_academique', 'nom', 'code',
            'type_periode', 'ordre', 'date_debut', 'date_fin',
            'date_limite_inscription', 'date_debut_examens',
            'date_fin_examens', 'date_publication_resultats',
            'est_courante', 'est_active'
        ]

    def validate(self, attrs):
        date_debut = attrs.get('date_debut')
        date_fin = attrs.get('date_fin')
        
        if date_debut and date_fin:
            if date_debut >= date_fin:
                raise serializers.ValidationError(
                    "La date de début doit être antérieure à la date de fin"
                )
        
        return attrs


class ProgrammeListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des programmes"""
    filiere_nom = serializers.CharField(source='filiere.nom', read_only=True)
    etablissement_nom = serializers.CharField(source='filiere.etablissement.nom', read_only=True)
    approuve_par_nom = serializers.CharField(source='approuve_par.get_full_name', read_only=True)

    class Meta:
        model = Programme
        fields = [
            'id', 'nom', 'filiere', 'filiere_nom', 'etablissement_nom',
            'credits_totaux', 'date_derniere_revision', 'approuve_par',
            'approuve_par_nom', 'date_approbation', 'est_actif', 'created_at'
        ]


class ProgrammeDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un programme"""
    filiere_nom = serializers.CharField(source='filiere.nom', read_only=True)
    etablissement_nom = serializers.CharField(source='filiere.etablissement.nom', read_only=True)
    approuve_par_nom = serializers.CharField(source='approuve_par.get_full_name', read_only=True)

    class Meta:
        model = Programme
        fields = [
            'id', 'nom', 'description', 'filiere', 'filiere_nom',
            'etablissement_nom', 'objectifs', 'competences', 'debouches',
            'credits_totaux', 'date_derniere_revision', 'approuve_par',
            'approuve_par_nom', 'date_approbation', 'est_actif',
            'created_at', 'updated_at'
        ]


class ProgrammeCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier un programme"""
    
    class Meta:
        model = Programme
        fields = [
            'filiere', 'nom', 'description', 'objectifs', 'competences',
            'debouches', 'credits_totaux', 'date_derniere_revision',
            'approuve_par', 'date_approbation', 'est_actif'
        ]


# Serializers simplifiés pour les sélections
class DepartementSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departement
        fields = ['id', 'nom', 'code']


class FiliereSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Filiere
        fields = ['id', 'nom', 'code', 'type_filiere']


class NiveauSimpleSerializer(serializers.ModelSerializer):
    filiere_nom = serializers.CharField(source='filiere.nom', read_only=True)
    
    class Meta:
        model = Niveau
        fields = ['id', 'nom', 'code', 'ordre', 'filiere_nom']


class ClasseSimpleSerializer(serializers.ModelSerializer):
    niveau_nom = serializers.CharField(source='niveau.nom', read_only=True)
    filiere_nom = serializers.CharField(source='niveau.filiere.nom', read_only=True)
    
    class Meta:
        model = Classe
        fields = ['id', 'nom', 'code', 'niveau_nom', 'filiere_nom']
        
