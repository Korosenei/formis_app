from decimal import Decimal
from django.db.models import Sum, Avg, Q
from django.utils import timezone
from .models import Note, MoyenneModule, Evaluation
from apps.courses.models import MatiereModule, Module
from apps.establishments.models import AnneeAcademique


class MoyenneCalculator:
    """
    Classe utilitaire pour calculer les moyennes des apprenants
    """

    @staticmethod
    def calculer_moyenne_matiere(apprenant, matiere_module, annee_academique=None):
        """
        Calcule la moyenne d'un apprenant dans une matière spécifique

        Args:
            apprenant: Instance de l'utilisateur apprenant
            matiere_module: Instance de MatiereModule
            annee_academique: Instance d'AnneeAcademique (optionnel)

        Returns:
            dict: {
                'moyenne': Decimal ou None,
                'notes': QuerySet des notes,
                'total_coefficient': Decimal,
                'nb_evaluations': int
            }
        """
        # Filtrer les notes
        notes_query = Note.objects.filter(
            apprenant=apprenant,
            matiere_module=matiere_module,
            evaluation__statut='TERMINEE'
        )

        # Filtrer par année académique si spécifiée
        if annee_academique:
            notes_query = notes_query.filter(
                evaluation__date_debut__range=(
                    annee_academique.date_debut,
                    annee_academique.date_fin
                )
            )

        notes = notes_query.order_by('-date_attribution')

        if not notes.exists():
            return {
                'moyenne': None,
                'notes': notes,
                'total_coefficient': Decimal('0'),
                'nb_evaluations': 0
            }

        # Calcul de la moyenne pondérée
        somme_notes_ponderees = Decimal('0')
        somme_coefficients = Decimal('0')

        for note in notes:
            note_sur_20 = note.note_sur_20
            coefficient = note.coefficient_pondere

            somme_notes_ponderees += note_sur_20 * coefficient
            somme_coefficients += coefficient

        moyenne = None
        if somme_coefficients > 0:
            moyenne = round(somme_notes_ponderees / somme_coefficients, 2)

        return {
            'moyenne': moyenne,
            'notes': notes,
            'total_coefficient': somme_coefficients,
            'nb_evaluations': notes.count()
        }

    @staticmethod
    def calculer_moyenne_module(apprenant, module, annee_academique):
        """
        Calcule la moyenne d'un apprenant dans un module

        Args:
            apprenant: Instance de l'utilisateur apprenant
            module: Instance de Module
            annee_academique: Instance d'AnneeAcademique

        Returns:
            dict: {
                'moyenne_generale': Decimal ou None,
                'moyennes_matieres': dict,
                'total_credits': Decimal,
                'validee': bool
            }
        """
        # Récupérer toutes les matières du module
        matieres_module = module.matieres_modules.all()

        if not matieres_module.exists():
            return {
                'moyenne_generale': None,
                'moyennes_matieres': {},
                'total_credits': Decimal('0'),
                'validee': False
            }

        moyennes_matieres = {}
        somme_moyennes_ponderees = Decimal('0')
        somme_coefficients_matieres = Decimal('0')

        # Calculer la moyenne pour chaque matière
        for matiere_module in matieres_module:
            resultat_matiere = MoyenneCalculator.calculer_moyenne_matiere(
                apprenant, matiere_module, annee_academique
            )

            moyennes_matieres[matiere_module.id] = {
                'matiere_module': matiere_module,
                'moyenne': resultat_matiere['moyenne'],
                'coefficient': matiere_module.coefficient,
                'notes': resultat_matiere['notes'],
                'nb_evaluations': resultat_matiere['nb_evaluations']
            }

            # Si l'apprenant a une moyenne dans cette matière
            if resultat_matiere['moyenne'] is not None:
                coefficient_matiere = matiere_module.coefficient
                somme_moyennes_ponderees += resultat_matiere['moyenne'] * coefficient_matiere
                somme_coefficients_matieres += coefficient_matiere

        # Calcul de la moyenne générale du module
        moyenne_generale = None
        if somme_coefficients_matieres > 0:
            moyenne_generale = round(somme_moyennes_ponderees / somme_coefficients_matieres, 2)

        # Calcul des crédits
        total_credits = Decimal('0')
        validee = False
        if moyenne_generale and moyenne_generale >= 10:
            total_credits = module.credits_ects or Decimal('0')
            validee = True

        return {
            'moyenne_generale': moyenne_generale,
            'moyennes_matieres': moyennes_matieres,
            'total_credits': total_credits,
            'validee': validee
        }

    @staticmethod
    def calculer_moyenne_generale_apprenant(apprenant, annee_academique):
        """
        Calcule la moyenne générale d'un apprenant pour une année académique

        Args:
            apprenant: Instance de l'utilisateur apprenant
            annee_academique: Instance d'AnneeAcademique

        Returns:
            dict: {
                'moyenne_generale': Decimal ou None,
                'moyennes_modules': dict,
                'total_credits_obtenus': Decimal,
                'total_credits_possibles': Decimal,
                'modules_valides': int,
                'modules_total': int
            }
        """
        # Récupérer les modules de la classe de l'apprenant
        try:
            classe_apprenant = apprenant.classe
            modules = classe_apprenant.modules.all()
        except:
            return {
                'moyenne_generale': None,
                'moyennes_modules': {},
                'total_credits_obtenus': Decimal('0'),
                'total_credits_possibles': Decimal('0'),
                'modules_valides': 0,
                'modules_total': 0
            }

        if not modules.exists():
            return {
                'moyenne_generale': None,
                'moyennes_modules': {},
                'total_credits_obtenus': Decimal('0'),
                'total_credits_possibles': Decimal('0'),
                'modules_valides': 0,
                'modules_total': 0
            }

        moyennes_modules = {}
        somme_moyennes_ponderees = Decimal('0')
        somme_credits = Decimal('0')
        total_credits_obtenus = Decimal('0')
        total_credits_possibles = Decimal('0')
        modules_valides = 0

        # Calculer la moyenne pour chaque module
        for module in modules:
            resultat_module = MoyenneCalculator.calculer_moyenne_module(
                apprenant, module, annee_academique
            )

            credits_module = module.credits_ects or Decimal('0')
            total_credits_possibles += credits_module

            moyennes_modules[module.id] = {
                'module': module,
                'moyenne': resultat_module['moyenne_generale'],
                'credits': credits_module,
                'credits_obtenus': resultat_module['total_credits'],
                'validee': resultat_module['validee'],
                'moyennes_matieres': resultat_module['moyennes_matieres']
            }

            # Si le module a une moyenne
            if resultat_module['moyenne_generale'] is not None:
                somme_moyennes_ponderees += resultat_module['moyenne_generale'] * credits_module
                somme_credits += credits_module

                if resultat_module['validee']:
                    total_credits_obtenus += credits_module
                    modules_valides += 1

        # Calcul de la moyenne générale
        moyenne_generale = None
        if somme_credits > 0:
            moyenne_generale = round(somme_moyennes_ponderees / somme_credits, 2)

        return {
            'moyenne_generale': moyenne_generale,
            'moyennes_modules': moyennes_modules,
            'total_credits_obtenus': total_credits_obtenus,
            'total_credits_possibles': total_credits_possibles,
            'modules_valides': modules_valides,
            'modules_total': modules.count()
        }

    @staticmethod
    def mettre_a_jour_moyennes_module(apprenant, module, annee_academique):
        """
        Met à jour ou crée l'objet MoyenneModule pour un apprenant

        Args:
            apprenant: Instance de l'utilisateur apprenant
            module: Instance de Module
            annee_academique: Instance d'AnneeAcademique

        Returns:
            MoyenneModule: Instance mise à jour
        """
        # Calculer les nouvelles moyennes
        resultats = MoyenneCalculator.calculer_moyenne_module(
            apprenant, module, annee_academique
        )

        # Récupérer ou créer l'objet MoyenneModule
        moyenne_module, created = MoyenneModule.objects.get_or_create(
            apprenant=apprenant,
            module=module,
            annee_academique=annee_academique
        )

        # Mettre à jour les valeurs
        moyenne_module.moyenne_generale = resultats['moyenne_generale']
        moyenne_module.total_credits = resultats['total_credits']
        moyenne_module.validee = resultats['validee']

        # Mettre à jour la date de validation si le module est validé
        if resultats['validee'] and not moyenne_module.date_validation:
            moyenne_module.date_validation = timezone.now()
        elif not resultats['validee']:
            moyenne_module.date_validation = None

        moyenne_module.save()
        return moyenne_module

    @staticmethod
    def mettre_a_jour_toutes_moyennes_apprenant(apprenant, annee_academique):
        """
        Met à jour toutes les moyennes d'un apprenant pour une année académique

        Args:
            apprenant: Instance de l'utilisateur apprenant
            annee_academique: Instance d'AnneeAcademique

        Returns:
            dict: Résultats de la mise à jour
        """
        try:
            classe_apprenant = apprenant.classe
            modules = classe_apprenant.modules.all()
        except:
            return {'success': False, 'error': 'Apprenant sans classe assignée'}

        moyennes_mises_a_jour = []

        for module in modules:
            moyenne_module = MoyenneCalculator.mettre_a_jour_moyennes_module(
                apprenant, module, annee_academique
            )
            moyennes_mises_a_jour.append(moyenne_module)

        return {
            'success': True,
            'moyennes_mises_a_jour': moyennes_mises_a_jour,
            'nb_modules': len(moyennes_mises_a_jour)
        }

    @staticmethod
    def obtenir_classement_classe(classe, annee_academique, module=None):
        """
        Obtient le classement des apprenants d'une classe

        Args:
            classe: Instance de Classe
            annee_academique: Instance d'AnneeAcademique
            module: Instance de Module (optionnel, pour classement par module)

        Returns:
            list: Liste des apprenants avec leurs moyennes, triée par moyenne décroissante
        """
        apprenants = classe.apprenants.filter(is_active=True)
        classement = []

        for apprenant in apprenants:
            if module:
                # Classement pour un module spécifique
                resultats = MoyenneCalculator.calculer_moyenne_module(
                    apprenant, module, annee_academique
                )
                moyenne = resultats['moyenne_generale']
            else:
                # Classement général
                resultats = MoyenneCalculator.calculer_moyenne_generale_apprenant(
                    apprenant, annee_academique
                )
                moyenne = resultats['moyenne_generale']

            classement.append({
                'apprenant': apprenant,
                'moyenne': moyenne or Decimal('0'),
                'resultats': resultats
            })

        # Trier par moyenne décroissante
        classement.sort(key=lambda x: x['moyenne'], reverse=True)

        # Ajouter les rangs
        for i, item in enumerate(classement, 1):
            item['rang'] = i

        return classement

    @staticmethod
    def obtenir_statistiques_evaluation(evaluation):
        """
        Obtient les statistiques d'une évaluation

        Args:
            evaluation: Instance d'Evaluation

        Returns:
            dict: Statistiques de l'évaluation
        """
        notes = Note.objects.filter(evaluation=evaluation)

        if not notes.exists():
            return {
                'nb_notes': 0,
                'moyenne': None,
                'note_min': None,
                'note_max': None,
                'nb_reussites': 0,
                'taux_reussite': 0,
                'repartition': {}
            }

        # Convertir toutes les notes sur 20
        notes_sur_20 = [note.note_sur_20 for note in notes]

        # Calculs statistiques
        nb_notes = len(notes_sur_20)
        moyenne = sum(notes_sur_20) / nb_notes
        note_min = min(notes_sur_20)
        note_max = max(notes_sur_20)
        nb_reussites = sum(1 for note in notes_sur_20 if note >= 10)
        taux_reussite = (nb_reussites / nb_notes) * 100

        # Répartition par tranches
        repartition = {
            '0-5': sum(1 for note in notes_sur_20 if 0 <= note < 5),
            '5-10': sum(1 for note in notes_sur_20 if 5 <= note < 10),
            '10-15': sum(1 for note in notes_sur_20 if 10 <= note < 15),
            '15-20': sum(1 for note in notes_sur_20 if 15 <= note <= 20),
        }

        return {
            'nb_notes': nb_notes,
            'moyenne': round(moyenne, 2),
            'note_min': round(note_min, 2),
            'note_max': round(note_max, 2),
            'nb_reussites': nb_reussites,
            'taux_reussite': round(taux_reussite, 2),
            'repartition': repartition
        }


class EvaluationUtils:
    """
    Classe utilitaire pour les opérations sur les évaluations
    """

    @staticmethod
    def verifier_disponibilite_evaluation(evaluation, apprenant):
        """
        Vérifie si une évaluation est disponible pour un apprenant

        Args:
            evaluation: Instance d'Evaluation
            apprenant: Instance de l'utilisateur apprenant

        Returns:
            dict: {
                'disponible': bool,
                'raison': str,
                'peut_composer': bool
            }
        """
        now = timezone.now()

        # Vérifier que l'apprenant est dans une des classes concernées
        if not evaluation.classes.filter(apprenants=apprenant).exists():
            return {
                'disponible': False,
                'raison': 'Vous n\'êtes pas dans les classes concernées par cette évaluation.',
                'peut_composer': False
            }

        # Vérifier le statut de l'évaluation
        if evaluation.statut not in ['PROGRAMMEE', 'EN_COURS']:
            return {
                'disponible': False,
                'raison': f'Évaluation {evaluation.get_statut_display().lower()}.',
                'peut_composer': False
            }

        # Vérifier les dates
        if now < evaluation.date_debut:
            return {
                'disponible': False,
                'raison': f'L\'évaluation commence le {evaluation.date_debut.strftime("%d/%m/%Y à %H:%M")}.',
                'peut_composer': False
            }

        # Vérifier si l'évaluation est terminée
        if now > evaluation.date_fin:
            if evaluation.autorise_retard:
                return {
                    'disponible': True,
                    'raison': 'Évaluation terminée mais soumission en retard autorisée.',
                    'peut_composer': True
                }
            else:
                return {
                    'disponible': False,
                    'raison': 'Évaluation terminée.',
                    'peut_composer': False
                }

        # Évaluation disponible
        return {
            'disponible': True,
            'raison': 'Évaluation disponible.',
            'peut_composer': True
        }

    @staticmethod
    def obtenir_temps_restant(evaluation):
        """
        Calcule le temps restant pour une évaluation

        Args:
            evaluation: Instance d'Evaluation

        Returns:
            dict: {
                'temps_restant_secondes': int,
                'temps_restant_str': str,
                'evaluation_terminee': bool
            }
        """
        now = timezone.now()

        if now >= evaluation.date_fin:
            return {
                'temps_restant_secondes': 0,
                'temps_restant_str': 'Terminée',
                'evaluation_terminee': True
            }

        temps_restant = evaluation.date_fin - now
        temps_restant_secondes = int(temps_restant.total_seconds())

        # Formatage du temps restant
        heures = temps_restant_secondes // 3600
        minutes = (temps_restant_secondes % 3600) // 60
        secondes = temps_restant_secondes % 60

        if heures > 0:
            temps_str = f"{heures}h {minutes}min {secondes}s"
        elif minutes > 0:
            temps_str = f"{minutes}min {secondes}s"
        else:
            temps_str = f"{secondes}s"

        return {
            'temps_restant_secondes': temps_restant_secondes,
            'temps_restant_str': temps_str,
            'evaluation_terminee': False
        }

    @staticmethod
    def mettre_a_jour_statut_evaluation(evaluation):
        """
        Met à jour automatiquement le statut d'une évaluation

        Args:
            evaluation: Instance d'Evaluation

        Returns:
            bool: True si le statut a été modifié
        """
        now = timezone.now()
        ancien_statut = evaluation.statut

        # Logique de mise à jour du statut
        if evaluation.statut == 'PROGRAMMEE' and now >= evaluation.date_debut:
            evaluation.statut = 'EN_COURS'
        elif evaluation.statut == 'EN_COURS' and now > evaluation.date_fin:
            evaluation.statut = 'TERMINEE'

        if evaluation.statut != ancien_statut:
            evaluation.save()
            return True

        return False
