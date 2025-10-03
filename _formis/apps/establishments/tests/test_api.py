from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from establishments.models import Localite, TypeEtablissement, Etablissement


class EstablishmentAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.localite = Localite.objects.create(nom="Ouagadougou")
        self.type_etab = TypeEtablissement.objects.create(nom="Université", code="UNIV")

    def test_create_etablissement_authenticated(self):
        self.client.force_authenticate(user=self.user)
        data = {
            'nom': 'Nouvelle Université',
            'code': 'NU',
            'type_etablissement': self.type_etab.pk,
            'localite': self.localite.pk,
            'adresse': 'Nouvelle adresse',
            'actif': True,
            'public': True
        }
        response = self.client.post('/api/establishments/etablissements/create/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_etablissement_unauthenticated(self):
        data = {
            'nom': 'Nouvelle Université',
            'code': 'NU',
            'type_etablissement': self.type_etab.pk,
            'localite': self.localite.pk,
            'adresse': 'Nouvelle adresse'
        }
        response = self.client.post('/api/establishments/etablissements/create/', data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_etablissements_public(self):
        # Créer un établissement public
        Etablissement.objects.create(
            nom="Université Publique",
            code="UP",
            type_etablissement=self.type_etab,
            localite=self.localite,
            adresse="Adresse publique",
            actif=True,
            public=True
        )

        response = self.client.get('/api/establishments/etablissements/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)


if __name__ == '__main__':
    print("Structure complète de l'application Establishments créée avec succès!")
    print("\nComposants inclus:")
    print("✓ Modèles complets avec relations")
    print("✓ Configuration Admin avec inlines et filtres")
    print("✓ Formulaires avec validation")
    print("✓ Vues Class-Based et Function-Based")
    print("✓ URLs organisées")
    print("✓ API REST complète avec serializers")
    print("✓ Templates Bootstrap responsifs")
    print("✓ Utilitaires et commandes de management")
    print("✓ Signaux Django")
    print("✓ Tags de templates personnalisés")
    print("✓ Tests unitaires")
    print("✓ Structure de fichiers complète")

    print("\nPour utiliser cette application:")
    print("1. Ajouter 'establishments' à INSTALLED_APPS")
    print("2. Ajouter 'rest_framework' à INSTALLED_APPS pour l'API")
    print("3. Inclure les URLs dans le projet principal")
    print("4. Faire les migrations: python manage.py makemigrations establishments")
    print("5. Appliquer les migrations: python manage.py migrate")
    print("6. Créer un superuser: python manage.py createsuperuser")
    print("7. Collecter les fichiers statiques si nécessaire")

