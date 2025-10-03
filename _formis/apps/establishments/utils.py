from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from .models import Etablissement, Salle, Campus, JourFerie
import calendar
from datetime import datetime, timedelta


class EstablishmentStats:
    """Classe utilitaire pour les statistiques des établissements"""

    @staticmethod
    def get_global_stats():
        """Statistiques globales"""
        return {
            'total_etablissements': Etablissement.objects.filter(actif=True).count(),
            'total_salles': Salle.objects.filter(est_active=True).count(),
            'total_campus': Campus.objects.filter(est_actif=True).count(),
            'capacite_totale': Etablissement.objects.filter(actif=True).aggregate(
                total=Sum('capacite_totale')
            )['total'] or 0,
            'etudiants_totaux': Etablissement.objects.filter(actif=True).aggregate(
                total=Sum('etudiants_actuels')
            )['total'] or 0,
            'taux_occupation_moyen': Etablissement.objects.filter(actif=True).aggregate(
                avg=Avg('etudiants_actuels')
            )['avg'] or 0,
        }

    @staticmethod
    def get_etablissements_by_occupation():
        """Établissements groupés par taux d'occupation"""
        etablissements = Etablissement.objects.filter(actif=True)
        stats = {
            'faible': 0,  # < 50%
            'moyen': 0,  # 50-75%
            'eleve': 0,  # 75-90%
            'plein': 0,  # > 90%
        }

        for etab in etablissements:
            taux = etab.taux_occupation()
            if taux < 50:
                stats['faible'] += 1
            elif taux < 75:
                stats['moyen'] += 1
            elif taux < 90:
                stats['eleve'] += 1
            else:
                stats['plein'] += 1

        return stats

    @staticmethod
    def get_salles_by_type():
        """Répartition des salles par type"""
        stats = {}
        for type_salle in Salle.TYPES_SALLE:
            count = Salle.objects.filter(
                type_salle=type_salle[0],
                est_active=True
            ).count()
            if count > 0:
                stats[type_salle[1]] = count
        return stats


class CalendarUtils:
    """Utilitaires pour le calendrier"""

    @staticmethod
    def get_events_for_month(etablissement_id=None, year=None, month=None):
        """Récupère les événements pour un mois donné"""
        if not year:
            year = timezone.now().year
        if not month:
            month = timezone.now().month

        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, calendar.monthrange(year, month)[1]).date()

        queryset = JourFerie.objects.filter(
            date_debut__lte=end_date,
            date_fin__gte=start_date
        )

        if etablissement_id:
            queryset = queryset.filter(etablissement_id=etablissement_id)

        events = []
        for jour in queryset:
            events.append({
                'title': jour.nom,
                'start': jour.date_debut.isoformat(),
                'end': jour.date_fin.isoformat() if jour.date_fin != jour.date_debut else None,
                'color': jour.couleur,
                'description': jour.description or '',
                'type': jour.get_type_jour_ferie_display(),
                'etablissement': jour.etablissement.nom,
            })

        return events


class SearchUtils:
    """Utilitaires pour la recherche"""

    @staticmethod
    def search_etablissements(query):
        """Recherche dans les établissements"""
        return Etablissement.objects.filter(
            Q(nom__icontains=query) |
            Q(sigle__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query) |
            Q(adresse__icontains=query)
        ).select_related('type_etablissement', 'localite')

    @staticmethod
    def search_salles(query):
        """Recherche dans les salles"""
        return Salle.objects.filter(
            Q(nom__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query) |
            Q(batiment__icontains=query)
        ).select_related('etablissement')

    @staticmethod
    def search_campus(query):
        """Recherche dans les campus"""
        return Campus.objects.filter(
            Q(nom__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query) |
            Q(adresse__icontains=query)
        ).select_related('etablissement')

