from rest_framework import generics, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg, Sum
from django.shortcuts import get_object_or_404

from ..models import (
    Localite, TypeEtablissement, Etablissement, AnneeAcademique,
    BaremeNotation, NiveauNote, ParametresEtablissement, Salle,
    JourFerie, Campus
)
from .serializers import (
    LocaliteSerializer, TypeEtablissementSerializer, EtablissementListSerializer,
    EtablissementDetailSerializer, EtablissementCreateUpdateSerializer,
    AnneeAcademiqueSerializer, BaremeNotationSerializer, SalleSerializer,
    CampusSerializer, JourFerieSerializer, ParametresEtablissementSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# API Views pour Localités
class LocaliteListCreateAPIView(generics.ListCreateAPIView):
    queryset = Localite.objects.all().order_by('nom')
    serializer_class = LocaliteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'region']
    ordering_fields = ['nom', 'region', 'created_at']


class LocaliteRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Localite.objects.all()
    serializer_class = LocaliteSerializer
    permission_classes = [IsAuthenticated]


# API Views pour Types d'Établissement
class TypeEtablissementListCreateAPIView(generics.ListCreateAPIView):
    queryset = TypeEtablissement.objects.all().order_by('nom')
    serializer_class = TypeEtablissementSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nom', 'description']
    filterset_fields = ['actif', 'structure_academique_defaut']


class TypeEtablissementRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TypeEtablissement.objects.all()
    serializer_class = TypeEtablissementSerializer
    permission_classes = [IsAuthenticated]


# API Views pour Établissements
class EtablissementListAPIView(generics.ListAPIView):
    serializer_class = EtablissementListSerializer
    permission_classes = [AllowAny]  # API publique
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['nom', 'sigle', 'code', 'description']
    filterset_fields = ['type_etablissement', 'localite', 'actif', 'public']
    ordering_fields = ['nom', 'created_at', 'capacite_totale', 'etudiants_actuels']
    ordering = ['nom']

    def get_queryset(self):
        queryset = Etablissement.objects.select_related('type_etablissement', 'localite')

        # Filtres additionnels
        capacite_min = self.request.query_params.get('capacite_min')
        capacite_max = self.request.query_params.get('capacite_max')
        taux_occupation_min = self.request.query_params.get('taux_occupation_min')

        if capacite_min:
            queryset = queryset.filter(capacite_totale__gte=capacite_min)
        if capacite_max:
            queryset = queryset.filter(capacite_totale__lte=capacite_max)

        # Pour l'API publique, ne montrer que les établissements actifs et publics
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(actif=True, public=True)

        return queryset


class EtablissementCreateAPIView(generics.CreateAPIView):
    queryset = Etablissement.objects.all()
    serializer_class = EtablissementCreateUpdateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        etablissement = serializer.save()
        # Créer automatiquement les paramètres par défaut
        ParametresEtablissement.objects.get_or_create(etablissement=etablissement)


class EtablissementRetrieveAPIView(generics.RetrieveAPIView):
    queryset = Etablissement.objects.all()
    serializer_class = EtablissementDetailSerializer
    permission_classes = [AllowAny]  # API publique

    def get_queryset(self):
        queryset = Etablissement.objects.select_related(
            'type_etablissement', 'localite'
        ).prefetch_related(
            'campuses', 'salle_set', 'anneeacademique_set',
            'baremenotation_set', 'jourferie_set'
        )

        # Pour l'API publique, ne montrer que les établissements actifs et publics
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(actif=True, public=True)

        return queryset


class EtablissementUpdateAPIView(generics.UpdateAPIView):
    queryset = Etablissement.objects.all()
    serializer_class = EtablissementCreateUpdateSerializer
    permission_classes = [IsAuthenticated]


class EtablissementDestroyAPIView(generics.DestroyAPIView):
    queryset = Etablissement.objects.all()
    permission_classes = [IsAuthenticated]


# API Views pour Salles
class SalleListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = SalleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nom', 'code', 'description']
    filterset_fields = ['etablissement', 'type_salle', 'etat', 'est_active']

    def get_queryset(self):
        queryset = Salle.objects.select_related('etablissement')

        # Filtres additionnels
        capacite_min = self.request.query_params.get('capacite_min')
        equipements = self.request.query_params.getlist('equipements')

        if capacite_min:
            queryset = queryset.filter(capacite__gte=capacite_min)

        # Filtrage par équipements
        equipements_mapping = {
            'projecteur': 'projecteur',
            'ordinateur': 'ordinateur',
            'climatisation': 'climatisation',
            'wifi': 'wifi',
            'tableau_blanc': 'tableau_blanc',
            'systeme_audio': 'systeme_audio'
        }

        for equipement in equipements:
            if equipement in equipements_mapping:
                queryset = queryset.filter(**{equipements_mapping[equipement]: True})

        return queryset


class SalleRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Salle.objects.select_related('etablissement')
    serializer_class = SalleSerializer
    permission_classes = [IsAuthenticated]


# API Views pour Campus
class CampusListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = CampusSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nom', 'code', 'adresse']
    filterset_fields = ['etablissement', 'est_campus_principal', 'est_actif']

    def get_queryset(self):
        return Campus.objects.select_related('etablissement', 'localite', 'responsable_campus')


class CampusRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Campus.objects.select_related('etablissement', 'localite', 'responsable_campus')
    serializer_class = CampusSerializer
    permission_classes = [IsAuthenticated]


# API Views pour Années Académiques
class AnneeAcademiqueListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = AnneeAcademiqueSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['etablissement', 'est_courante', 'est_active']

    def get_queryset(self):
        return AnneeAcademique.objects.select_related('etablissement').order_by('-date_debut')


# API Views pour Barèmes de Notation
class BaremeNotationListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = BaremeNotationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['etablissement', 'est_defaut']

    def get_queryset(self):
        return BaremeNotation.objects.select_related('etablissement').prefetch_related('niveaux_notes')


# API Views pour Jours Fériés
class JourFerieListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = JourFerieSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['etablissement', 'type_jour_ferie', 'est_recurrent']

    def get_queryset(self):
        return JourFerie.objects.select_related('etablissement').order_by('-date_debut')


# API Views pour Statistiques
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def statistiques_api_view(request):
    """API pour les statistiques générales"""
    # Statistiques globales
    stats = {
        'totaux': {
            'etablissements': Etablissement.objects.filter(actif=True).count(),
            'salles': Salle.objects.filter(est_active=True).count(),
            'campus': Campus.objects.filter(est_actif=True).count(),
            'localites': Localite.objects.count(),
            'types_etablissement': TypeEtablissement.objects.filter(actif=True).count(),
        },
        'capacites': {
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
    }

    # Statistiques par type d'établissement
    stats['par_type'] = []
    types = TypeEtablissement.objects.annotate(
        nombre_etablissements=Count('etablissement', filter=Q(etablissement__actif=True)),
        capacite_totale=Sum('etablissement__capacite_totale', filter=Q(etablissement__actif=True)),
        etudiants_totaux=Sum('etablissement__etudiants_actuels', filter=Q(etablissement__actif=True))
    ).filter(nombre_etablissements__gt=0)

    for type_etab in types:
        stats['par_type'].append({
            'nom': type_etab.nom,
            'code': type_etab.code,
            'nombre_etablissements': type_etab.nombre_etablissements,
            'capacite_totale': type_etab.capacite_totale or 0,
            'etudiants_totaux': type_etab.etudiants_totaux or 0,
        })

    # Statistiques des salles par type
    stats['salles_par_type'] = {}
    for type_salle in Salle.TYPES_SALLE:
        count = Salle.objects.filter(type_salle=type_salle[0], est_active=True).count()
        if count > 0:
            stats['salles_par_type'][type_salle[1]] = count

    return Response({
        'success': True,
        'data': stats
    })


@api_view(['GET'])
@permission_classes([AllowAny])  # API publique
def etablissements_par_localite_api(request):
    """API pour obtenir les établissements par localité"""
    localites = Localite.objects.annotate(
        nombre_etablissements=Count('etablissement', filter=Q(etablissement__actif=True, etablissement__public=True))
    ).filter(nombre_etablissements__gt=0)

    data = []
    for localite in localites:
        etablissements = localite.etablissement_set.filter(actif=True, public=True).values(
            'id', 'nom', 'sigle', 'type_etablissement__nom'
        )

        data.append({
            'localite': {
                'id': localite.id,
                'nom': localite.nom,
                'region': localite.region,
                'pays': localite.pays,
            },
            'nombre_etablissements': localite.nombre_etablissements,
            'etablissements': list(etablissements)
        })

    return Response({
        'success': True,
        'count': len(data),
        'data': data
    })


@require_http_methods(["GET"])
def api_etablissements_publics(request):
    """API publique pour lister les établissements"""
    etablissements = Etablissement.objects.filter(actif=True, public=True).select_related(
        'type_etablissement', 'localite'
    )

    data = []
    for etab in etablissements:
        data.append({
            'id': etab.id,
            'nom': etab.nom,
            'sigle': etab.sigle,
            'code': etab.code,
            'type': etab.type_etablissement.nom,
            'localite': etab.localite.nom,
            'adresse': etab.adresse,
            'telephone': etab.telephone,
            'email': etab.email,
            'site_web': etab.site_web,
            'capacite_totale': etab.capacite_totale,
            'logo': etab.logo.url if etab.logo else None,
            'description': etab.description,
        })

    return JsonResponse({
        'success': True,
        'count': len(data),
        'results': data
    })


@require_http_methods(["GET"])
def api_etablissement_detail(request, etablissement_id):
    """API pour les détails d'un établissement"""
    try:
        etab = Etablissement.objects.select_related('type_etablissement', 'localite').get(
            id=etablissement_id, actif=True, public=True
        )
    except Etablissement.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Établissement non trouvé'}, status=404)

    # Récupérer les informations liées
    campus = etab.campuses.filter(est_actif=True)
    salles = etab.salle_set.filter(est_active=True)

    data = {
        'id': etab.id,
        'nom': etab.nom,
        'sigle': etab.sigle,
        'code': etab.code,
        'type': {
            'nom': etab.type_etablissement.nom,
            'code': etab.type_etablissement.code,
            'structure_academique': etab.type_etablissement.structure_academique_defaut,
        },
        'localite': {
            'nom': etab.localite.nom,
            'region': etab.localite.region,
            'pays': etab.localite.pays,
        },
        'contact': {
            'adresse': etab.adresse,
            'telephone': etab.telephone,
            'email': etab.email,
            'site_web': etab.site_web,
        },
        'informations': {
            'nom_directeur': etab.nom_directeur,
            'date_creation': etab.date_creation.isoformat() if etab.date_creation else None,
            'description': etab.description,
            'mission': etab.mission,
            'vision': etab.vision,
        },
        'statistiques': {
            'capacite_totale': etab.capacite_totale,
            'etudiants_actuels': etab.etudiants_actuels,
            'taux_occupation': etab.taux_occupation(),
        },
        'images': {
            'logo': etab.logo.url if etab.logo else None,
            'couverture': etab.image_couverture.url if etab.image_couverture else None,
        },
        'campus': [
            {
                'nom': c.nom,
                'adresse': c.adresse,
                'services': c.get_liste_services(),
            } for c in campus
        ],
        'salles': {
            'total': salles.count(),
            'par_type': {
                type_salle[1]: salles.filter(type_salle=type_salle[0]).count()
                for type_salle in Salle.TYPES_SALLE
            }
        }
    }

    return JsonResponse({
        'success': True,
        'data': data
    })


# Vues utilitaires
@login_required
def mise_a_jour_etudiants_view(request):
    """Vue pour mettre à jour le nombre d'étudiants de tous les établissements"""
    if request.method == 'POST':
        etablissements = Etablissement.objects.filter(actif=True)
        count = 0

        for etablissement in etablissements:
            etablissement.mise_a_jour_nombre_etudiants()
            count += 1

        messages.success(request, f'Nombre d\'étudiants mis à jour pour {count} établissements.')
        return redirect('establishments:dashboard')

    return render(request, 'establishments/mise_a_jour_etudiants.html')


@login_required
def rapport_etablissement_pdf(request, etablissement_id):
    """Génère un rapport PDF pour un établissement"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO

    etablissement = get_object_or_404(Etablissement, pk=etablissement_id)

    # Créer le PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Titre
    title = Paragraph(f"Rapport - {etablissement.nom}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 20))

    # Informations générales
    info_data = [
        ['Nom', etablissement.nom],
        ['Sigle', etablissement.sigle or 'N/A'],
        ['Code', etablissement.code],
        ['Type', etablissement.type_etablissement.nom],
        ['Localité', etablissement.localite.nom],
        ['Capacité totale', str(etablissement.capacite_totale)],
        ['Étudiants actuels', str(etablissement.etudiants_actuels)],
        ['Taux d\'occupation', f"{etablissement.taux_occupation():.1f}%"],
    ]

    info_table = Table(info_data)
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(info_table)
    story.append(Spacer(1, 20))

    # Statistiques des salles
    salles = etablissement.salle_set.filter(est_active=True)
    if salles.exists():
        story.append(Paragraph("Statistiques des Salles", styles['Heading2']))

        salles_data = [['Type de salle', 'Nombre', 'Capacité totale']]
        for type_salle in Salle.TYPES_SALLE:
            salles_type = salles.filter(type_salle=type_salle[0])
            if salles_type.exists():
                capacite_totale = sum(s.capacite for s in salles_type)
                salles_data.append([type_salle[1], str(salles_type.count()), str(capacite_totale)])

        if len(salles_data) > 1:
            salles_table = Table(salles_data)
            salles_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(salles_table)

    # Construire le PDF
    doc.build(story)

    # Retourner la réponse
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_{etablissement.code}.pdf"'

    return response
