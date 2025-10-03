from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from establishments.models import (
    Localite, TypeEtablissement, Etablissement, AnneeAcademique,
    BaremeNotation, NiveauNote, Salle, Campus
)


class LocaliteModelTest(TestCase):
    def test_create_localite(self):
        localite = Localite.objects.create(
            nom="Ouagadougou",
            region="Centre",
            pays="Burkina Faso"
        )
        self.assertEqual(str(localite), "Ouagadougou")

    def test_localite_unique_nom(self):
        Localite.objects.create(nom="Bobo-Dioulasso")
        # Devrait permettre une autre localité avec le même nom mais région différente
        Localite.objects.create(nom="Bobo-Dioulasso", region="Hauts-Bassins")


class TypeEtablissementModelTest(TestCase):
    def test_create_type_etablissement(self):
        type_etab = TypeEtablissement.objects.create(
            nom="Université",
            code="UNIV",
            description="Établissement universitaire"
        )
        self.assertEqual(str(type_etab), "Université")
        self.assertTrue(type_etab.actif)

    def test_code_unique(self):
        TypeEtablissement.objects.create(nom="Université", code="UNIV")
        with self.assertRaises(IntegrityError):
            TypeEtablissement.objects.create(nom="Autre", code="UNIV")


class EtablissementModelTest(TestCase):
    def setUp(self):
        self.localite = Localite.objects.create(nom="Ouagadougou")
        self.type_etab = TypeEtablissement.objects.create(nom="Université", code="UNIV")

    def test_create_etablissement(self):
        etablissement = Etablissement.objects.create(
            nom="Université Joseph Ki-Zerbo",
            code="UJKZ",
            type_etablissement=self.type_etab,
            localite=self.localite,
            adresse="Avenue Charles de Gaulle",
            capacite_totale=15000
        )
        self.assertEqual(str(etablissement), "Université Joseph Ki-Zerbo")
        self.assertEqual(etablissement.taux_occupation(), 0)

    def test_taux_occupation(self):
        etablissement = Etablissement.objects.create(
            nom="Test Université",
            code="TEST",
            type_etablissement=self.type_etab,
            localite=self.localite,
            adresse="Test Address",
            capacite_totale=1000,
            etudiants_actuels=750
        )
        self.assertEqual(etablissement.taux_occupation(), 75.0)

    def test_taux_occupation_zero_capacity(self):
        etablissement = Etablissement.objects.create(
            nom="Test Université",
            code="TEST",
            type_etablissement=self.type_etab,
            localite=self.localite,
            adresse="Test Address",
            capacite_totale=0,
            etudiants_actuels=100
        )
        self.assertEqual(etablissement.taux_occupation(), 0)