from rest_framework import serializers
from django.contrib.auth import authenticate
from ..models import Utilisateur, ProfilUtilisateur, ProfilApprenant, ProfilEnseignant


class UtilisateurSerializer(serializers.ModelSerializer):
    """Serializer pour le modèle Utilisateur"""

    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = Utilisateur
        fields = (
            'id', 'username', 'email', 'prenom', 'nom', 'matricule',
            'role', 'date_naissance', 'lieu_naissance', 'genre',
            'telephone', 'adresse', 'etablissement', 'departement',
            'est_actif', 'date_creation', 'photo_profil',
            'password', 'confirm_password'
        )
        read_only_fields = ('id', 'matricule', 'username', 'date_creation')

    def validate(self, attrs):
        if 'password' in attrs and 'confirm_password' in attrs:
            if attrs['password'] != attrs['confirm_password']:
                raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')
        user = Utilisateur.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class UtilisateurProfileSerializer(serializers.ModelSerializer):
    """Serializer pour le profil public d'un utilisateur"""

    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = Utilisateur
        fields = (
            'id', 'matricule', 'prenom', 'nom', 'full_name',
            'role', 'email', 'telephone', 'etablissement',
            'departement', 'photo_profil'
        )
        read_only_fields = ('id', 'matricule', 'role')


class ProfilUtilisateurSerializer(serializers.ModelSerializer):
    """Serializer pour le profil étendu de l'utilisateur"""

    class Meta:
        model = ProfilUtilisateur
        fields = '__all__'
        read_only_fields = ('utilisateur',)


class ProfilApprenantSerializer(serializers.ModelSerializer):
    """Serializer pour le profil apprenant"""

    class Meta:
        model = ProfilApprenant
        fields = '__all__'
        read_only_fields = ('utilisateur',)


class ProfilEnseignantSerializer(serializers.ModelSerializer):
    """Serializer pour le profil enseignant"""

    class Meta:
        model = ProfilEnseignant
        fields = '__all__'
        read_only_fields = ('utilisateur',)


class LoginSerializer(serializers.Serializer):
    """Serializer pour l'authentification"""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError("Identifiants incorrects.")
            if not user.est_actif:
                raise serializers.ValidationError("Compte désactivé.")
            attrs['user'] = user
        else:
            raise serializers.ValidationError("Le nom d'utilisateur et le mot de passe sont requis.")

        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer pour le changement de mot de passe"""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Ancien mot de passe incorrect.")
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Les nouveaux mots de passe ne correspondent pas.")
        return attrs

