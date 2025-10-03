# apps/academic/api/views.py

from rest_framework import generics, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

from ..models import (
    Departement, Filiere, Niveau, Classe, 
    PeriodeAcademique, Programme
)
from .serializers import (
    DepartementListSerializer, DepartementDetailSerializer, DepartementCreateUpdateSerializer,
    FiliereListSerializer, FiliereDetailSerializer, FiliereCreateUpdateSerializer,
    NiveauListSerializer, NiveauDetailSerializer, NiveauCreateUpdateSerializer,
    ClasseListSerializer, ClasseDetailSerializer, ClasseCreateUpdateSerializer,
    PeriodeAcademiqueListSerializer, PeriodeAcademiqueDetailSerializer, 
    PeriodeAcademiqueCreateUpdateSerializer,
    ProgrammeListSerializer, ProgrammeDetailSerializer, ProgrammeCreateUpdateSerializer,
    DepartementSimpleSerializer, FiliereSimpleSerializer, 
    NiveauSimpleSerializer, ClasseSimpleSerializer
)


# ==== DEPARTEMENT API VIEWS ====

class DepartementListCreateAPIView(generics.ListCreateAPIView):
    """Liste et création des départements"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['etablissement', 'est_actif']
    search_fields = ['nom', 'code', 'description']
    ordering_fields = ['nom', 'code', 'created_at']
    ordering = ['etablissement__nom', 'nom']

    def get_queryset(self):
        return Departement.objects.select_related(
            'etablissement', 'chef'
        ).annotate(
            nombre_filieres=Count('filiere')
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DepartementCreateUpdateSerializer
        return DepartementListSerializer


class DepartementRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Détail, modification et suppression d'un département"""
    permission_classes = [IsAuthenticated]
    queryset = Departement.objects.select_related(
        'etablissement', 'chef'
    ).prefetch_related('filiere_set')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DepartementCreateUpdateSerializer
        return DepartementDetailSerializer


# ==== FILIERE API VIEWS ====

class FiliereListCreateAPIView(generics.ListCreateAPIView):
    """Liste et création des filières"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['etablissement', 'departement', 'type_filiere', 'est_active']
    search_fields = ['nom', 'code', 'description', 'nom_diplome']
    ordering_fields = ['nom', 'code', 'duree_annees', 'created_at']
    ordering = ['etablissement__nom', 'nom']

    def get_queryset(self):
        return Filiere.objects.select_related(
            'etablissement', 'departement'
        ).annotate(
            nombre_niveaux=Count('niveaux')
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return FiliereCreateUpdateSerializer
        return FiliereListSerializer


class FiliereRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Détail, modification et suppression d'une filière"""
    permission_classes = [IsAuthenticated]
    queryset = Filiere.objects.select_related(
        'etablissement', 'departement'
    ).prefetch_related('niveaux', 'programme')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return FiliereCreateUpdateSerializer
        return FiliereDetailSerializer


# ==== NIVEAU API VIEWS ====

class NiveauListCreateAPIView(generics.ListCreateAPIView):
    """Liste et création des niveaux"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['filiere', 'filiere__etablissement', 'est_actif']
    search_fields = ['nom', 'code', 'description']
    ordering_fields = ['nom', 'ordre', 'created_at']
    ordering = ['filiere__nom', 'ordre']

    def get_queryset(self):
        return Niveau.objects.select_related(
            'filiere', 'filiere__etablissement'
        ).annotate(
            nombre_classes=Count('classe_set')
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return NiveauCreateUpdateSerializer
        return NiveauListSerializer


class NiveauRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Détail, modification et suppression d'un niveau"""
    permission_classes = [IsAuthenticated]
    queryset = Niveau.objects.select_related(
        'filiere', 'filiere__etablissement'
    ).prefetch_related('classe_set')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return NiveauCreateUpdateSerializer
        return NiveauDetailSerializer


# ==== CLASSE API VIEWS ====

class ClasseListCreateAPIView(generics.ListCreateAPIView):
    """Liste et création des classes"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'etablissement', 'niveau', 'niveau__filiere', 
        'annee_academique', 'est_active'
    ]
    search_fields = ['nom', 'code']
    ordering_fields = ['nom', 'effectif_actuel', 'capacite_maximale', 'created_at']
    ordering = ['niveau__filiere__nom', 'niveau__ordre', 'nom']

    def get_queryset(self):
        from django.db.models import F
        return Classe.objects.select_related(
            'etablissement', 'niveau', 'niveau__filiere',
            'annee_academique', 'professeur_principal'
        ).annotate(
            places_disponibles=F('capacite_maximale') - F('effectif_actuel')
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ClasseCreateUpdateSerializer
        return ClasseListSerializer


class ClasseRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Détail, modification et suppression d'une classe"""
    permission_classes = [IsAuthenticated]
    queryset = Classe.objects.select_related(
        'etablissement', 'niveau', 'niveau__filiere',
        'annee_academique', 'professeur_principal', 'salle_principale'
    )

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ClasseCreateUpdateSerializer
        return ClasseDetailSerializer


# ==== PERIODE ACADEMIQUE API VIEWS ====

class PeriodeAcademiqueListCreateAPIView(generics.ListCreateAPIView):
    """Liste et création des périodes académiques"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'etablissement', 'annee_academique', 'type_periode', 
        'est_courante', 'est_active'
    ]
    search_fields = ['nom', 'code']
    ordering_fields = ['nom', 'ordre', 'date_debut', 'created_at']
    ordering = ['annee_academique__nom', 'ordre']

    def get_queryset(self):
        return PeriodeAcademique.objects.select_related(
            'etablissement', 'annee_academique'
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PeriodeAcademiqueCreateUpdateSerializer
        return PeriodeAcademiqueListSerializer


class PeriodeAcademiqueRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Détail, modification et suppression d'une période académique"""
    permission_classes = [IsAuthenticated]
    queryset = PeriodeAcademique.objects.select_related(
        'etablissement', 'annee_academique'
    )

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PeriodeAcademiqueCreateUpdateSerializer
        return PeriodeAcademiqueDetailSerializer


# ==== PROGRAMME API VIEWS ====

class ProgrammeListCreateAPIView(generics.ListCreateAPIView):
    """Liste et création des programmes"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['filiere', 'filiere__etablissement', 'est_actif']
    search_fields = ['nom', 'description', 'objectifs', 'competences']
    ordering_fields = ['nom', 'date_derniere_revision', 'created_at']
    ordering = ['filiere__nom']

    def get_queryset(self):
        return Programme.objects.select_related(
            'filiere', 'filiere__etablissement', 'approuve_par'
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProgrammeCreateUpdateSerializer
        return ProgrammeListSerializer


class ProgrammeRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Détail, modification et suppression d'un programme"""
    permission_classes = [IsAuthenticated]
    queryset = Programme.objects.select_related(
        'filiere', 'filiere__etablissement', 'approuve_par'
    )

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProgrammeCreateUpdateSerializer
        return ProgrammeDetailSerializer


# ==== API UTILITAIRES ====

@api_view(['GET'])
def departements_by_etablissement(request, etablissement_id):
    """Retourne les départements d'un établissement"""
    departements = Departement.objects.filter(
        etablissement_id=etablissement_id,
        est_actif=True
    ).order_by('nom')
    
    serializer = DepartementSimpleSerializer(departements, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def filieres_by_etablissement(request, etablissement_id):
    """Retourne les filières d'un établissement"""
    departement_id = request.GET.get('departement')
    
    queryset = Filiere.objects.filter(
        etablissement_id=etablissement_id,
        est_active=True
    )
    
    if departement_id:
        queryset = queryset.filter(departement_id=departement_id)
    
    queryset = queryset.order_by('nom')
    
    serializer = FiliereSimpleSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def niveaux_by_filiere(request, filiere_id):
    """Retourne les niveaux d'une filière"""
    niveaux = Niveau.objects.filter(
        filiere_id=filiere_id,
        est_actif=True
    ).order_by('ordre')
    
    serializer = NiveauSimpleSerializer(niveaux, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def classes_by_niveau(request, niveau_id):
    """Retourne les classes d'un niveau"""
    annee_id = request.GET.get('annee')
    
    queryset = Classe.objects.filter(
        niveau_id=niveau_id,
        est_active=True
    ).select_related('niveau', 'niveau__filiere')
    
    if annee_id:
        queryset = queryset.filter(annee_academique_id=annee_id)
    
    queryset = queryset.order_by('nom')
    
    serializer = ClasseSimpleSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def academic_statistics(request):
    """Statistiques académiques générales"""
    etablissement_id = request.GET.get('etablissement')
    
    # Base queryset selon l'établissement
    if etablissement_id:
        departements = Departement.objects.filter(
            etablissement_id=etablissement_id
        )
        filieres = Filiere.objects.filter(
            etablissement_id=etablissement_id
        )
        classes = Classe.objects.filter(
            etablissement_id=etablissement_id
        )
    else:
        departements = Departement.objects.all()
        filieres = Filiere.objects.all()
        classes = Classe.objects.all()
    
    # Calcul des statistiques
    stats = {
        'departements': {
            'total': departements.count(),
            'actifs': departements.filter(est_actif=True).count(),
        },
        'filieres': {
            'total': filieres.count(),
            'actives': filieres.filter(est_active=True).count(),
            'par_type': list(
                filieres.filter(est_active=True)
                .values('type_filiere')
                .annotate(count=Count('id'))
                .order_by('type_filiere')
            )
        },
        'niveaux': {
            'total': Niveau.objects.filter(
                filiere__in=filieres
            ).count(),
            'actifs': Niveau.objects.filter(
                filiere__in=filieres,
                est_actif=True
            ).count(),
        },
        'classes': {
            'total': classes.count(),
            'actives': classes.filter(est_active=True).count(),
            'effectif_total': classes.filter(
                est_active=True
            ).aggregate(
                total=Count('effectif_actuel')
            )['total'] or 0,
            'capacite_totale': classes.filter(
                est_active=True
            ).aggregate(
                total=Count('capacite_maximale')
            )['total'] or 0,
        },
        'programmes': {
            'total': Programme.objects.filter(
                filiere__in=filieres
            ).count(),
            'actifs': Programme.objects.filter(
                filiere__in=filieres,
                est_actif=True
            ).count(),
        }
    }
    
    return Response(stats)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_update_status(request):
    """Mise à jour en lot du statut (actif/inactif)"""
    model_name = request.data.get('model')
    ids = request.data.get('ids', [])
    status = request.data.get('status', True)
    
    if not model_name or not ids:
        return Response(
            {'error': 'Paramètres manquants'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    model_map = {
        'departement': Departement,
        'filiere': Filiere,
        'niveau': Niveau,
        'classe': Classe,
        'periode': PeriodeAcademique,
        'programme': Programme,
    }
    
    if model_name not in model_map:
        return Response(
            {'error': 'Modèle non valide'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    model = model_map[model_name]
    
    # Déterminer le champ de statut
    if model_name in ['filiere', 'classe', 'periode']:
        status_field = 'est_active'
    else:
        status_field = 'est_actif'
    
    # Mise à jour en lot
    updated_count = model.objects.filter(
        id__in=ids
    ).update(**{status_field: status})
    
    return Response({
        'message': f'{updated_count} enregistrement(s) mis à jour',
        'updated_count': updated_count
    })