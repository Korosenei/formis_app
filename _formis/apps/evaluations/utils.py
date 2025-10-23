from decimal import Decimal
from django.db.models import Q, Avg, Sum, Count, Max, Min
from django.utils import timezone
from .models import Evaluation, Composition, Note
from apps.courses.models import Matiere, Module
from apps.establishments.models import AnneeAcademique


class MoyenneCalculator:
    """Classe utilitaire pour calculer les moyennes"""

    @staticmethod
    def calculer_moyenne_matiere(apprenant, matiere):
        """Calcule la moyenne d'un apprenant dans une matière"""
        notes = Note.objects.filter(apprenant=apprenant, matiere=matiere)

        if not notes.exists():
            return 0

        total_coef = Decimal('0')
        somme_ponderee = Decimal('0')

        for note in notes:
            coef = Decimal(str(note.evaluation.coefficient))
            total_coef += coef
            somme_ponderee += Decimal(str(note.note_sur_20)) * coef

        if total_coef > 0:
            return float(somme_ponderee / total_coef)
        return 0

    @staticmethod
    def calculer_moyenne_generale(apprenant):
        """Calcule la moyenne générale d'un apprenant"""

        matieres = Matiere.objects.filter(
            notes__apprenant=apprenant
        ).distinct()

        if not matieres.exists():
            return 0

        total_coef = Decimal('0')
        somme_ponderee = Decimal('0')

        for matiere in matieres:
            moyenne_matiere = MoyenneCalculator.calculer_moyenne_matiere(
                apprenant, matiere
            )
            coef_matiere = Decimal(str(matiere.coefficient))
            total_coef += coef_matiere
            somme_ponderee += Decimal(str(moyenne_matiere)) * coef_matiere

        if total_coef > 0:
            return float(somme_ponderee / total_coef)
        return 0


class EvaluationUtils:
    """Classe utilitaire pour les évaluations"""

    @staticmethod
    def obtenir_statistiques_detaillees(evaluation):
        """Retourne des statistiques détaillées pour une évaluation"""
        compositions = evaluation.compositions.all()
        notes = Note.objects.filter(evaluation=evaluation)

        total_apprenants = sum(
            classe.etudiants.count()
            for classe in evaluation.classes.all()
        )

        stats = {
            'total_apprenants': total_apprenants,
            'compositions_total': compositions.count(),
            'compositions_soumises': compositions.filter(
                statut__in=['SOUMISE', 'EN_RETARD']
            ).count(),
            'compositions_corrigees': compositions.filter(
                statut='CORRIGEE'
            ).count(),
            'compositions_en_cours': compositions.filter(
                statut='EN_COURS'
            ).count(),
            'taux_soumission': evaluation.taux_soumission,
            'taux_correction': evaluation.taux_correction,
        }

        # Statistiques de notes
        if notes.exists():
            stats['notes'] = {
                'moyenne': float(notes.aggregate(Avg('valeur'))['valeur__avg'] or 0),
                'mediane': EvaluationUtils._calculer_mediane(notes),
                'max': float(notes.aggregate(Max('valeur'))['valeur__max'] or 0),
                'min': float(notes.aggregate(Min('valeur'))['valeur__min'] or 0),
                'ecart_type': EvaluationUtils._calculer_ecart_type(notes),
            }

            # Distribution
            stats['distribution'] = {
                'excellent': notes.filter(valeur__gte=16).count(),
                'bien': notes.filter(valeur__gte=14, valeur__lt=16).count(),
                'assez_bien': notes.filter(valeur__gte=12, valeur__lt=14).count(),
                'passable': notes.filter(valeur__gte=10, valeur__lt=12).count(),
                'insuffisant': notes.filter(valeur__lt=10).count(),
            }

        return stats

    @staticmethod
    def _calculer_mediane(notes):
        """Calcule la médiane d'un queryset de notes"""
        valeurs = list(notes.values_list('valeur', flat=True).order_by('valeur'))
        n = len(valeurs)

        if n == 0:
            return 0

        if n % 2 == 0:
            return float((valeurs[n // 2 - 1] + valeurs[n // 2]) / 2)
        return float(valeurs[n // 2])

    @staticmethod
    def _calculer_ecart_type(notes):
        """Calcule l'écart-type d'un queryset de notes"""
        import math

        valeurs = list(notes.values_list('valeur', flat=True))
        n = len(valeurs)

        if n < 2:
            return 0

        moyenne = sum(float(v) for v in valeurs) / n
        variance = sum((float(v) - moyenne) ** 2 for v in valeurs) / n

        return math.sqrt(variance)

    @staticmethod
    def generer_analyses_statistiques(evaluation):
        """Génère des analyses statistiques avancées"""
        stats = EvaluationUtils.obtenir_statistiques_detaillees(evaluation)

        analyses = {
            'performance_globale': 'Bonne' if stats.get('notes', {}).get('moyenne', 0) >= 12 else 'Moyenne',
            'homogeneite': 'Homogène' if stats.get('notes', {}).get('ecart_type', 0) < 3 else 'Hétérogène',
            'taux_reussite': 0,
        }

        if 'distribution' in stats:
            total_notes = sum(stats['distribution'].values())
            if total_notes > 0:
                reussis = (
                        stats['distribution']['excellent'] +
                        stats['distribution']['bien'] +
                        stats['distribution']['assez_bien'] +
                        stats['distribution']['passable']
                )
                analyses['taux_reussite'] = (reussis / total_notes) * 100

        return analyses


class NotificationHelper:
    """Classe utilitaire pour les notifications"""

    @staticmethod
    def notifier_nouvelle_evaluation(evaluation):
        """Notifie les apprenants d'une nouvelle évaluation"""
        # À implémenter selon votre système de notifications
        pass

    @staticmethod
    def notifier_correction_publiee(evaluation):
        """Notifie les apprenants qu'une correction est publiée"""
        # À implémenter selon votre système de notifications
        pass

    @staticmethod
    def rappel_evaluation_proche(evaluation):
        """Rappelle aux apprenants une évaluation proche"""
        # À implémenter selon votre système de notifications
        pass