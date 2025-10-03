from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from establishments.models import Localite, TypeEtablissement, Etablissement


class EstablishmentViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.localite = Localite.objects.create(nom="Ouagadougou")
        self.type_etab = TypeEtablissement.objects.create(nom="Université", code="UNIV")
        self.etablissement = Etablissement.objects.create(
            nom="Test Université",
            code="TEST",
            type_etablissement=self.type_etab,
            localite=self.localite,
            adresse="Test Address"
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('establishments:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_dashboard_with_login(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('establishments:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')

    def test_etablissement_list(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('establishments:etablissement_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.etablissement.nom)

    def test_etablissement_detail(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('establishments:etablissement_detail', kwargs={'pk': self.etablissement.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.etablissement.nom)

    def test_api_etablissements_publics(self):
        # Cette API est publique, pas besoin de login
        response = self.client.get(reverse('establishments:api_etablissements_publics'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('results', data)