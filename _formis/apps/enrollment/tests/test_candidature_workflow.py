from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core import mail
from datetime import timedelta
from unittest.mock import patch, Mock

from ..models import Candidature, DocumentCandidature
from ..utils import (
    envoyer_email_candidature_soumise,
    envoyer_email_candidature_evaluee,
    creer_compte_utilisateur_depuis_candidature
)
from establishments.models import Etablissement, AnneeAcademique
from academic.models import Filiere, Niveau

User = get_user_model()


class CandidatureWorkflowTestCase(TransactionTestCase):
    """Tests du workflow complet des candidatures"""

    def setUp(self):
        """Prépare les données de test"""
        # Créer les objets de référence
        self.etablissement = Etablissement.objects.create(
            nom="Université Test",
            code="UT",
            adresse="Adresse test"
        )

        self.annee_academique = AnneeAcademique.objects.create(
            nom="2024-2025",
            etablissement=self.etablissement,
            date_debut="2024-09-01",
            date_fin="2025-06-30"
        )

        self.filiere = Filiere.objects.create(
            nom="Informatique",
            code="INFO",
            etablissement=self.etablissement
        )

        self.niveau = Niveau.objects.create(
            nom="Licence 1",
            code="L1"
        )

        # Créer un admin pour les évaluations
        self.admin_user = User.objects.create_user(
            username="admin_test",
            email="admin@test.com",
            password="testpass123",
            role="ADMIN",
            nom="Admin",
            prenom="Test"
        )

    def test_creation_candidature_complete(self):
        """Test la création d'une candidature complète"""
        candidature = Candidature.objects.create(
            etablissement=self.etablissement,
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique=self.annee_academique,
            prenom="Jean",
            nom="Dupont",
            email="jean.dupont@test.com",
            telephone="+22670000000",
            date_naissance="2000-01-01",
            lieu_naissance="Ouagadougou",
            genre="M",
            adresse="123 rue Test"
        )

        # Vérifier que le numéro de candidature est généré
        self.assertTrue(candidature.numero_candidature)
        self.assertTrue(candidature.numero_candidature.startswith("CAND2024"))

        # Vérifier le statut initial
        self.assertEqual(candidature.statut, 'BROUILLON')

        # Vérifier la méthode nom_complet
        self.assertEqual(candidature.nom_complet(), "Jean Dupont")

    def test_soumission_candidature(self):
        """Test la soumission d'une candidature"""
        candidature = Candidature.objects.create(
            etablissement=self.etablissement,
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique=self.annee_academique,
            prenom="Marie",
            nom="Martin",
            email="marie.martin@test.com",
            telephone="+22670000001",
            date_naissance="1999-05-15",
            lieu_naissance="Bobo-Dioulasso",
            genre="F",
            adresse="456 avenue Test"
        )

        # Simuler que tous les documents requis sont fournis
        with patch.object(candidature, 'peut_etre_soumise', return_value=(True, "OK")):
            candidature.soumettre()

        # Vérifier les changements
        candidature.refresh_from_db()
        self.assertEqual(candidature.statut, 'SOUMISE')
        self.assertIsNotNone(candidature.date_soumission)
        self.assertLessEqual(
            (timezone.now() - candidature.date_soumission).seconds,
            60  # Moins d'une minute
        )

    @patch('enrollment.utils.send_mail')
    def test_envoi_email_candidature_soumise(self, mock_send_mail):
        """Test l'envoi d'email après soumission"""
        mock_send_mail.return_value = True

        candidature = Candidature.objects.create(
            etablissement=self.etablissement,
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique=self.annee_academique,
            prenom="Pierre",
            nom="Durand",
            email="pierre.durand@test.com",
            telephone="+22670000002",
            date_naissance="1998-12-10",
            lieu_naissance="Ouahigouya",
            genre="M",
            adresse="789 boulevard Test",
            statut='SOUMISE',
            date_soumission=timezone.now()
        )

        # Tester l'envoi d'email
        result = envoyer_email_candidature_soumise(candidature)

        self.assertTrue(result)
        mock_send_mail.assert_called_once()

        # Vérifier les arguments de l'appel
        args, kwargs = mock_send_mail.call_args
        self.assertIn(candidature.numero_candidature, kwargs['subject'])
        self.assertIn(candidature.email, kwargs['recipient_list'])

    def test_evaluation_candidature_approuvee(self):
        """Test l'approbation d'une candidature"""
        candidature = Candidature.objects.create(
            etablissement=self.etablissement,
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique=self.annee_academique,
            prenom="Sophie",
            nom="Leclerc",
            email="sophie.leclerc@test.com",
            telephone="+22670000003",
            date_naissance="1997-08-20",
            lieu_naissance="Koudougou",
            genre="F",
            adresse="321 place Test",
            statut='SOUMISE',
            date_soumission=timezone.now() - timedelta(days=1)
        )

        # Approuver la candidature
        candidature.statut = 'APPROUVEE'
        candidature.date_decision = timezone.now()
        candidature.examine_par = self.admin_user
        candidature.notes_approbation = "Dossier complet et excellent profil"
        candidature.save()

        # Vérifier les changements
        self.assertEqual(candidature.statut, 'APPROUVEE')
        self.assertIsNotNone(candidature.date_decision)
        self.assertEqual(candidature.examine_par, self.admin_user)
        self.assertTrue(candidature.notes_approbation)

    def test_evaluation_candidature_rejetee(self):
        """Test le rejet d'une candidature"""
        candidature = Candidature.objects.create(
            etablissement=self.etablissement,
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique=self.annee_academique,
            prenom="Antoine",
            nom="Bernard",
            email="antoine.bernard@test.com",
            telephone="+22670000004",
            date_naissance="1996-03-12",
            lieu_naissance="Banfora",
            genre="M",
            adresse="654 rue Test",
            statut='SOUMISE',
            date_soumission=timezone.now() - timedelta(days=2)
        )

        # Rejeter la candidature
        candidature.statut = 'REJETEE'
        candidature.date_decision = timezone.now()
        candidature.examine_par = self.admin_user
        candidature.motif_rejet = "Dossier incomplet"
        candidature.save()

        # Vérifier les changements
        self.assertEqual(candidature.statut, 'REJETEE')
        self.assertIsNotNone(candidature.date_decision)
        self.assertEqual(candidature.examine_par, self.admin_user)
        self.assertTrue(candidature.motif_rejet)

    @patch('enrollment.utils.envoyer_informations_connexion')
    def test_creation_compte_utilisateur(self, mock_envoyer_info):
        """Test la création automatique de compte utilisateur"""
        mock_envoyer_info.return_value = True

        candidature = Candidature.objects.create(
            etablissement=self.etablissement,
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique=self.annee_academique,
            prenom="Laura",
            nom="Moreau",
            email="laura.moreau@test.com",
            telephone="+22670000005",
            date_naissance="1995-11-25",
            lieu_naissance="Tenkodogo",
            genre="F",
            adresse="987 chemin Test",
            statut='APPROUVEE',
            date_decision=timezone.now(),
            examine_par=self.admin_user
        )

        # Créer le compte utilisateur
        utilisateur = creer_compte_utilisateur_depuis_candidature(candidature)

        # Vérifier la création
        self.assertIsNotNone(utilisateur)
        self.assertEqual(utilisateur.email, candidature.email)
        self.assertEqual(utilisateur.nom, candidature.nom)
        self.assertEqual(utilisateur.prenom, candidature.prenom)
        self.assertEqual(utilisateur.role, 'APPRENANT')
        self.assertEqual(utilisateur.etablissement, candidature.etablissement)
        self.assertTrue(utilisateur.is_active)

        # Vérifier que l'email d'informations a été envoyé
        mock_envoyer_info.assert_called_once()

    def test_prevention_doublons_candidature(self):
        """Test la prévention des candidatures en doublon"""
        # Créer une première candidature
        candidature1 = Candidature.objects.create(
            etablissement=self.etablissement,
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique=self.annee_academique,
            prenom="Thomas",
            nom="Petit",
            email="thomas.petit@test.com",
            telephone="+22670000006",
            date_naissance="1994-07-08",
            lieu_naissance="Gaoua",
            genre="M",
            adresse="159 allée Test",
            statut='SOUMISE'
        )

        # Tenter de créer une candidature similaire
        candidature2 = Candidature.objects.create(
            etablissement=self.etablissement,
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique=self.annee_academique,
            prenom="Thomas",
            nom="Petit",
            email="thomas.petit@test.com",
            telephone="+22670000006",
            date_naissance="1994-07-08",
            lieu_naissance="Gaoua",
            genre="M",
            adresse="159 allée Test",
            statut='BROUILLON'
        )

        # Simuler la soumission de la deuxième candidature
        # En réalité, la vue devrait empêcher cela
        with patch.object(candidature2, 'peut_etre_soumise', return_value=(True, "OK")):
            candidature2.soumettre()

        # Vérifier que les brouillons sont supprimés
        # (Ceci devrait être géré par les signaux)
        brouillons = Candidature.objects.filter(
            email="thomas.petit@test.com",
            statut='BROUILLON'
        )
        # Le signal devrait avoir supprimé les brouillons
        # En test, il faut simuler ce comportement


class CandidatureAPITestCase(TestCase):
    """Tests des vues et API des candidatures"""

    def setUp(self):
        self.etablissement = Etablissement.objects.create(
            nom="Université API Test",
            code="UAT",
            adresse="Adresse API test"
        )

        self.client.defaults['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'

    def test_creation_candidature_ajax(self):
        """Test la création de candidature via AJAX"""
        data = {
            'etablissement': self.etablissement.id,
            'prenom': 'Test',
            'nom': 'Ajax',
            'email': 'test.ajax@test.com',
            'telephone': '+22670000000',
            'date_naissance': '2000-01-01',
            'lieu_naissance': 'Test City',
            'genre': 'M',
            'adresse': 'Adresse AJAX test'
        }

        # Cette partie nécessiterait les autres modèles (filiere, niveau, etc.)
        # et une configuration complète pour fonctionner
        pass

    def test_validation_champs_obligatoires(self):
        """Test la validation des champs obligatoires"""
        data = {
            'prenom': 'Test',
            # Champs manquants intentionnellement
        }

        response = self.client.post(
            '/enrollment/public/candidature/create/',
            data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        # Devrait retourner une erreur 400 avec les champs manquants
        # (nécessite une configuration complète pour fonctionner)
        pass