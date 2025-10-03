# apps/enrollment/views.py
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.generic import CreateView, UpdateView, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.db.models import Q, Count
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from datetime import timedelta

from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
import json

from .forms import (
    PeriodeCandidatureForm, DocumentRequisForm, CandidatureForm,
    DocumentCandidatureForm, CandidatureFilterForm, InscriptionForm,
    TransfertForm, AbandonForm, CandidatureEvaluationForm
)

from .models import (
    PeriodeCandidature, DocumentRequis, Candidature, DocumentCandidature,
    Inscription, HistoriqueInscription, Transfert, Abandon
)
from .serializers import (
    PeriodeCandidatureSerializer, DocumentRequisSerializer,
    CandidatureListSerializer, CandidatureDetailSerializer, CandidatureCreateUpdateSerializer,
    DocumentCandidatureSerializer, InscriptionSerializer, HistoriqueInscriptionSerializer,
    TransfertSerializer, AbandonSerializer, CandidatureStatsSerializer, InscriptionStatsSerializer
)
from .permissions import (
    EnrollmentPermission, CandidaturePermission, DocumentCandidaturePermission,
    InscriptionPermission
)

from .utils import (
    envoyer_email_candidature_soumise,
    envoyer_email_candidature_evaluee,
    creer_compte_utilisateur_depuis_candidature
)

# Configuration du logger
logger = logging.getLogger(__name__)
User = get_user_model()

# Dashboard
@login_required
def enrollment_dashboard(request):
    """Dashboard principal des inscriptions"""
    stats = {
        'candidatures_total': Candidature.objects.count(),
        'candidatures_soumises': Candidature.objects.filter(statut='SOUMISE').count(),
        'candidatures_approuvees': Candidature.objects.filter(statut='APPROUVEE').count(),
        'inscriptions_actives': Inscription.objects.filter(statut='ACTIVE').count(),
        'transferts_en_attente': Transfert.objects.filter(statut='PENDING').count(),
    }

    # Candidatures récentes
    candidatures_recentes = Candidature.objects.filter(
        statut='SOUMISE'
    ).order_by('-date_soumission')[:5]

    # Inscriptions récentes
    inscriptions_recentes = Inscription.objects.order_by('-date_inscription')[:5]

    context = {
        'stats': stats,
        'candidatures_recentes': candidatures_recentes,
        'inscriptions_recentes': inscriptions_recentes,
    }
    return render(request, 'enrollment/dashboard.html', context)


# Périodes de candidature
class PeriodeCandidatureListView(LoginRequiredMixin, ListView):
    model = PeriodeCandidature
    template_name = 'enrollment/periode/list.html'
    context_object_name = 'periodes'
    paginate_by = 20

    def get_queryset(self):
        return PeriodeCandidature.objects.select_related(
            'etablissement', 'annee_academique'
        ).prefetch_related('filieres')

class PeriodeCandidatureCreateView(LoginRequiredMixin, CreateView):
    model = PeriodeCandidature
    form_class = PeriodeCandidatureForm
    template_name = 'enrollment/periode/create.html'
    success_url = reverse_lazy('enrollment:periode_list')

    def form_valid(self, form):
        messages.success(self.request, 'Période de candidature créée avec succès.')
        return super().form_valid(form)

# Candidatures
class CandidatureCreateView(CreateView):
    """
    View pour créer une nouvelle candidature
    Gère à la fois les soumissions classiques et AJAX
    """
    model = Candidature
    form_class = CandidatureForm
    template_name = 'public/candidature/candidature.html'

    def post(self, request, *args, **kwargs):
        """Gestion AJAX et formulaire classique"""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return self.handle_ajax_request(request)
        return super().post(request, *args, **kwargs)

    def handle_ajax_request(self, request):
        """Traitement des requêtes AJAX"""
        try:
            logger.info("Début traitement candidature AJAX")

            # Extraire les données du FormData
            data = self.extract_form_data(request)

            # Validation des champs obligatoires
            validation_errors = self.validate_required_fields(data)
            if validation_errors:
                logger.warning(f"Champs manquants: {validation_errors}")
                return JsonResponse({
                    'success': False,
                    'error': 'Champs manquants',
                    'message': f'Les champs suivants sont obligatoires: {", ".join(validation_errors)}',
                    'missing_fields': validation_errors
                }, status=400)

            # Vérifier l'unicité de l'email
            if self.check_email_exists(data['email']):
                logger.warning(f"Email déjà utilisé: {data['email']}")
                return JsonResponse({
                    'success': False,
                    'error': 'Email déjà utilisé',
                    'message': 'Cette adresse email est déjà utilisée pour une autre candidature.'
                }, status=400)

            # Créer la candidature avec transaction atomique
            with transaction.atomic():
                candidature = self.create_candidature(data)
                documents_uploaded = self.process_uploaded_documents(request, candidature)

                logger.info(f"Candidature créée: {candidature.numero_candidature}")

            return JsonResponse({
                'success': True,
                'message': 'Candidature créée avec succès',
                'candidature_id': str(candidature.id),
                'numero_candidature': candidature.numero_candidature,
                'documents_uploaded': documents_uploaded,
                'redirect_url': f'/public/candidature/success/?numero={candidature.numero_candidature}'
            })

        except ValidationError as e:
            logger.error(f"Erreur de validation: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Erreur de validation',
                'message': str(e)
            }, status=400)

        except Exception as e:
            logger.error(f"Erreur création candidature: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Erreur serveur',
                'message': f'Une erreur est survenue: {str(e)}'
            }, status=500)

    def extract_form_data(self, request):
        """Extraire les données du FormData"""
        return {
            # Formation
            'etablissement': request.POST.get('etablissement'),
            'departement': request.POST.get('departement'),
            'filiere': request.POST.get('filiere'),
            'niveau': request.POST.get('niveau'),
            'annee_academique': request.POST.get('annee_academique'),

            # Informations personnelles
            'prenom': request.POST.get('prenom'),
            'nom': request.POST.get('nom'),
            'date_naissance': request.POST.get('date_naissance'),
            'lieu_naissance': request.POST.get('lieu_naissance'),
            'genre': request.POST.get('genre'),
            'telephone': request.POST.get('telephone'),
            'email': request.POST.get('email'),
            'adresse': request.POST.get('adresse'),

            # Informations parentales (optionnelles)
            'nom_pere': request.POST.get('nom_pere', ''),
            'telephone_pere': request.POST.get('telephone_pere', ''),
            'nom_mere': request.POST.get('nom_mere', ''),
            'telephone_mere': request.POST.get('telephone_mere', ''),
            'nom_tuteur': request.POST.get('nom_tuteur', ''),
            'telephone_tuteur': request.POST.get('telephone_tuteur', ''),

            # Informations académiques (optionnelles)
            'ecole_precedente': request.POST.get('ecole_precedente', ''),
            'dernier_diplome': request.POST.get('dernier_diplome', ''),
            'annee_obtention': request.POST.get('annee_obtention', ''),
        }

    def validate_required_fields(self, data):
        """Validation des champs obligatoires"""
        required_fields = [
            'etablissement', 'filiere', 'niveau', 'annee_academique',
            'prenom', 'nom', 'date_naissance', 'lieu_naissance',
            'genre', 'telephone', 'email', 'adresse'
        ]

        missing_fields = []
        for field in required_fields:
            if not data.get(field):
                missing_fields.append(field)

        return missing_fields

    def check_email_exists(self, email):
        """Vérifier si l'email est déjà utilisé"""
        return Candidature.objects.filter(email=email).exists()

    def create_candidature(self, data):
        """Créer la candidature"""
        candidature = Candidature.objects.create(
            # Formation
            etablissement_id=data['etablissement'],
            filiere_id=data['filiere'],
            niveau_id=data['niveau'],
            annee_academique_id=data['annee_academique'],

            # Informations personnelles
            prenom=data['prenom'],
            nom=data['nom'],
            date_naissance=data['date_naissance'],
            lieu_naissance=data['lieu_naissance'],
            genre=data['genre'],
            telephone=data['telephone'],
            email=data['email'],
            adresse=data['adresse'],

            # Informations parentales
            nom_pere=data['nom_pere'] or None,
            telephone_pere=data['telephone_pere'] or None,
            nom_mere=data['nom_mere'] or None,
            telephone_mere=data['telephone_mere'] or None,
            nom_tuteur=data['nom_tuteur'] or None,
            telephone_tuteur=data['telephone_tuteur'] or None,

            # Informations académiques
            ecole_precedente=data['ecole_precedente'] or None,
            dernier_diplome=data['dernier_diplome'] or None,
            annee_obtention=int(data['annee_obtention']) if data['annee_obtention'] else None,

            # Statut initial
            statut='BROUILLON'
        )

        return candidature

    def process_uploaded_documents(self, request, candidature):
        """Traiter les documents uploadés"""
        documents_uploaded = []

        for key, file in request.FILES.items():
            if key.startswith('document_'):
                document_type = key.replace('document_', '')

                document = DocumentCandidature.objects.create(
                    candidature=candidature,
                    type_document=document_type,
                    nom=file.name,
                    fichier=file,
                    est_valide=False
                )

                documents_uploaded.append({
                    'type': document_type,
                    'nom': file.name,
                    'id': str(document.id)
                })

                logger.info(f"Document uploadé: {file.name} pour candidature {candidature.numero_candidature}")

        return documents_uploaded

    def form_valid(self, form):
        """Pour les soumissions non-AJAX"""
        messages.success(self.request, 'Candidature créée avec succès.')
        return super().form_valid(form)

    def get_success_url(self):
        """Redirection après création réussie (non-AJAX)"""
        return reverse_lazy('enrollment:candidature_success') + f'?numero={self.object.numero_candidature}'

class CandidatureSoumettreView(DetailView):
    """
    View pour soumettre une candidature (passer de BROUILLON à SOUMISE)
    """
    model = Candidature

    def post(self, request, *args, **kwargs):
        candidature = self.get_object()

        try:
            with transaction.atomic():
                # Vérifier que la candidature peut être soumise
                if candidature.statut != 'BROUILLON':
                    logger.warning(f"Tentative de soumission candidature non-brouillon: {candidature.numero_candidature}")
                    return JsonResponse({
                        'success': False,
                        'message': 'Cette candidature ne peut plus être modifiée'
                    }, status=400)

                # Vérifier les documents requis
                peut_soumettre, message = candidature.peut_etre_soumise()
                if not peut_soumettre:
                    logger.warning(f"Candidature non soumettable: {candidature.numero_candidature} - {message}")
                    return JsonResponse({
                        'success': False,
                        'message': message
                    }, status=400)

                # Vérifier l'unicité pour éviter les doublons
                candidatures_existantes = Candidature.objects.filter(
                    email=candidature.email,
                    etablissement=candidature.etablissement,
                    filiere=candidature.filiere,
                    niveau=candidature.niveau,
                    annee_academique=candidature.annee_academique,
                    statut__in=['SOUMISE', 'EN_COURS_EXAMEN', 'APPROUVEE']
                ).exclude(id=candidature.id)

                if candidatures_existantes.exists():
                    logger.warning(f"Candidature en doublon détectée pour {candidature.email}")
                    return JsonResponse({
                        'success': False,
                        'message': 'Vous avez déjà une candidature en cours pour cette formation'
                    }, status=400)

                # Supprimer les autres brouillons du même candidat pour la même formation
                autres_brouillons = Candidature.objects.filter(
                    email=candidature.email,
                    etablissement=candidature.etablissement,
                    filiere=candidature.filiere,
                    niveau=candidature.niveau,
                    annee_academique=candidature.annee_academique,
                    statut='BROUILLON'
                ).exclude(id=candidature.id)

                brouillons_supprimes = autres_brouillons.count()
                if brouillons_supprimes > 0:
                    autres_brouillons.delete()
                    logger.info(f"{brouillons_supprimes} brouillons supprimés pour {candidature.email}")

                # Soumettre la candidature
                candidature.statut = 'SOUMISE'
                candidature.date_soumission = timezone.now()
                candidature.save()

                logger.info(f"Candidature soumise: {candidature.numero_candidature}")

                # Envoyer l'email de confirmation
                try:
                    if envoyer_email_candidature_soumise(candidature):
                        logger.info(f"Email de confirmation envoyé à {candidature.email}")
                    else:
                        logger.error(f"Échec envoi email de confirmation à {candidature.email}")
                except Exception as e:
                    logger.error(f"Erreur envoi email confirmation: {str(e)}")

                return JsonResponse({
                    'success': True,
                    'message': 'Candidature soumise avec succès',
                    'numero_candidature': candidature.numero_candidature,
                    'date_soumission': candidature.date_soumission.strftime('%d/%m/%Y à %H:%M')
                })

        except Exception as e:
            logger.error(f"Erreur soumission candidature: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Une erreur est survenue: {str(e)}'
            }, status=500)

class CandidatureEvaluerView(LoginRequiredMixin, DetailView):
    """
    View pour évaluer une candidature (APPROUVEE ou REJETEE)
    Accessible uniquement aux admins et chefs de département
    """
    model = Candidature

    def dispatch(self, request, *args, **kwargs):
        # Vérifier les permissions
        if not request.user.role in ['ADMIN', 'CHEF_DEPARTMENT']:
            logger.warning(f"Tentative d'accès non autorisé par {request.user.username}")
            return JsonResponse({
                'success': False,
                'message': 'Vous n\'avez pas les permissions nécessaires'
            }, status=403)

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        candidature = self.get_object()
        decision = request.POST.get('decision')
        motif_rejet = request.POST.get('motif_rejet', '')
        notes_approbation = request.POST.get('notes_approbation', '')

        if decision not in ['APPROUVEE', 'REJETEE']:
            return JsonResponse({
                'success': False,
                'message': 'Décision invalide'
            }, status=400)

        try:
            with transaction.atomic():
                # Vérifier que la candidature peut être évaluée
                if candidature.statut not in ['SOUMISE', 'EN_COURS_EXAMEN']:
                    logger.warning(f"Tentative d'évaluation candidature invalide: {candidature.numero_candidature}")
                    return JsonResponse({
                        'success': False,
                        'message': 'Cette candidature ne peut pas être évaluée'
                    }, status=400)

                # Mettre à jour la candidature
                candidature.statut = decision
                candidature.date_decision = timezone.now()
                candidature.examine_par = request.user

                if decision == 'REJETEE':
                    candidature.motif_rejet = motif_rejet
                else:
                    candidature.notes_approbation = notes_approbation

                candidature.save()

                logger.info(f"Candidature évaluée: {candidature.numero_candidature} - {decision} par {request.user.username}")

                # Envoyer l'email de notification
                try:
                    if envoyer_email_candidature_evaluee(candidature):
                        logger.info(f"Email de notification envoyé à {candidature.email}")
                    else:
                        logger.error(f"Échec envoi email de notification à {candidature.email}")
                except Exception as e:
                    logger.error(f"Erreur envoi email notification: {str(e)}")

                # Si approuvée, créer un compte utilisateur
                if decision == 'APPROUVEE':
                    try:
                        # Vérifier si l'utilisateur n'existe pas déjà
                        if not User.objects.filter(email=candidature.email).exists():
                            utilisateur = creer_compte_utilisateur_depuis_candidature(candidature)
                            if utilisateur:
                                logger.info(f"Compte utilisateur créé: {utilisateur.username} pour candidature {candidature.numero_candidature}")
                            else:
                                logger.error(f"Échec création compte utilisateur pour {candidature.email}")
                        else:
                            logger.info(f"Compte utilisateur existe déjà pour {candidature.email}")
                    except Exception as e:
                        logger.error(f"Erreur création compte utilisateur: {str(e)}")

                return JsonResponse({
                    'success': True,
                    'message': f'Candidature {decision.lower()} avec succès',
                    'decision': decision,
                    'date_decision': candidature.date_decision.strftime('%d/%m/%Y à %H:%M'),
                    'examine_par': candidature.examine_par.get_full_name() if candidature.examine_par else ''
                })

        except Exception as e:
            logger.error(f"Erreur évaluation candidature: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Une erreur est survenue: {str(e)}'
            }, status=500)

class CandidatureUpdateView(LoginRequiredMixin, UpdateView):
    model = Candidature
    form_class = CandidatureForm
    template_name = 'enrollment/candidature/edit.html'

    def get_queryset(self):
        # Seules les candidatures en brouillon peuvent être modifiées
        return Candidature.objects.filter(statut='BROUILLON')

    def form_valid(self, form):
        messages.success(self.request, 'Candidature mise à jour avec succès.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('enrollment:candidature_detail', kwargs={'pk': self.object.pk})

class CandidatureDetailView(DetailView):
    """
    View pour afficher les détails d'une candidature
    """
    model = Candidature
    template_name = 'enrollment/candidature/detail.html'
    context_object_name = 'candidature'

    def get_queryset(self):
        return Candidature.objects.select_related(
            'etablissement', 'filiere', 'niveau', 'annee_academique', 'examine_par'
        ).prefetch_related('documents')

class CandidatureListView(LoginRequiredMixin, ListView):
    """
    View pour lister les candidatures (pour les administrateurs)
    """
    model = Candidature
    template_name = 'enrollment/candidature/list.html'
    context_object_name = 'candidatures'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        # Vérifier les permissions
        if not request.user.role in ['ADMIN', 'CHEF_DEPARTMENT']:
            return redirect('home')

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Candidature.objects.select_related(
            'etablissement', 'filiere', 'niveau', 'annee_academique', 'examine_par'
        ).order_by('-created_at')

        # Filtrage par statut
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        # Filtrage par établissement (pour les chefs de département)
        if self.request.user.role == 'CHEF_DEPARTMENT':
            queryset = queryset.filter(etablissement=self.request.user.etablissement)

        # Recherche
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero_candidature__icontains=search) |
                Q(nom__icontains=search) |
                Q(prenom__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuts'] = Candidature.STATUTS_CANDIDATURE
        context['statut_filtre'] = self.request.GET.get('statut', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context

class CandidatureSuccessView(DetailView):
    """
    View pour afficher la page de succès après soumission
    """
    template_name = 'public/candidature/success.html'

    def get(self, request, *args, **kwargs):
        numero = request.GET.get('numero')
        if not numero:
            return redirect('enrollment:candidature_create')

        try:
            candidature = Candidature.objects.select_related(
                'etablissement', 'filiere', 'niveau'
            ).get(numero_candidature=numero)

            context = {
                'candidature': candidature,
                'formation': f"{candidature.filiere.nom} - {candidature.niveau.nom}",
                'etablissement': candidature.etablissement.nom,
            }

            return render(request, self.template_name, context)

        except Candidature.DoesNotExist:
            messages.error(request, 'Candidature non trouvée')
            return redirect('enrollment:candidature_create')

# Views API pour le JavaScript
def get_candidature_status(request, numero_candidature):
    """
    API pour récupérer le statut d'une candidature
    """
    try:
        candidature = Candidature.objects.select_related(
            'etablissement', 'filiere', 'niveau'
        ).get(numero_candidature=numero_candidature)

        return JsonResponse({
            'success': True,
            'data': {
                'numero_candidature': candidature.numero_candidature,
                'statut': candidature.statut,
                'statut_display': candidature.get_statut_display(),
                'date_soumission': candidature.date_soumission.isoformat() if candidature.date_soumission else None,
                'date_decision': candidature.date_decision.isoformat() if candidature.date_decision else None,
                'nom_complet': candidature.nom_complet(),
                'formation': f"{candidature.filiere.nom} - {candidature.niveau.nom}",
                'etablissement': candidature.etablissement.nom,
            }
        })

    except Candidature.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Candidature non trouvée'
        }, status=404)

def candidature_statistics(request):
    """
    API pour les statistiques des candidatures (pour le dashboard)
    """
    if not request.user.is_authenticated or request.user.role not in ['ADMIN', 'CHEF_DEPARTMENT']:
        return JsonResponse({'success': False, 'message': 'Non autorisé'}, status=403)

    # Filtrage par établissement pour les chefs de département
    queryset = Candidature.objects.all()
    if request.user.role == 'CHEF_DEPARTMENT':
        queryset = queryset.filter(etablissement=request.user.etablissement)

    stats = {
        'total': queryset.count(),
        'brouillons': queryset.filter(statut='BROUILLON').count(),
        'soumises': queryset.filter(statut='SOUMISE').count(),
        'en_cours': queryset.filter(statut='EN_COURS_EXAMEN').count(),
        'approuvees': queryset.filter(statut='APPROUVEE').count(),
        'rejetees': queryset.filter(statut='REJETEE').count(),
        'annulees': queryset.filter(statut='ANNULEE').count(),
    }

    return JsonResponse({
        'success': True,
        'data': stats
    })


@login_required
def candidature_evaluate(request, pk):
    """Évaluer une candidature (approuver/rejeter)"""
    candidature = get_object_or_404(Candidature, pk=pk, statut='SOUMISE')

    if request.method == 'POST':
        form = CandidatureEvaluationForm(request.POST)
        if form.is_valid():
            decision = form.cleaned_data['decision']
            notes = form.cleaned_data['notes']

            candidature.statut = decision
            candidature.examine_par = request.user
            candidature.date_decision = timezone.now()

            if decision == 'APPROUVEE':
                candidature.notes_approbation = notes
            else:
                candidature.motif_rejet = notes

            candidature.save()

            message = "Candidature approuvée" if decision == 'APPROUVEE' else "Candidature rejetée"
            messages.success(request, f"{message} avec succès.")

            return redirect('enrollment:candidature_detail', pk=pk)
    else:
        form = CandidatureEvaluationForm()

    return render(request, 'enrollment/candidature/evaluate.html', {
        'candidature': candidature,
        'form': form
    })

@login_required
def candidature_submit(request, pk):
    """Soumettre une candidature"""
    candidature = get_object_or_404(Candidature, pk=pk, statut='BROUILLON')

    peut_soumettre, message = candidature.peut_etre_soumise()
    if not peut_soumettre:
        messages.error(request, f"Impossible de soumettre la candidature : {message}")
        return redirect('enrollment:candidature_detail', pk=pk)

    candidature.soumettre()
    messages.success(request, 'Candidature soumise avec succès.')

    return redirect('enrollment:candidature_detail', pk=pk)


# Documents de candidature
@login_required
def candidature_documents(request, pk):
    """Gérer les documents d'une candidature"""
    candidature = get_object_or_404(Candidature, pk=pk)

    if request.method == 'POST':
        form = DocumentCandidatureForm(request.POST, request.FILES, candidature=candidature)
        if form.is_valid():
            document = form.save(commit=False)
            document.candidature = candidature
            document.save()
            messages.success(request, 'Document ajouté avec succès.')
            return redirect('enrollment:candidature_documents', pk=pk)
    else:
        form = DocumentCandidatureForm(candidature=candidature)

    documents = candidature.documents.all()

    return render(request, 'enrollment/candidature/documents.html', {
        'candidature': candidature,
        'documents': documents,
        'form': form
    })

@login_required
def document_delete(request, candidature_pk, document_pk):
    """Supprimer un document de candidature"""
    candidature = get_object_or_404(Candidature, pk=candidature_pk)
    document = get_object_or_404(DocumentCandidature, pk=document_pk, candidature=candidature)

    if request.method == 'POST':
        document.delete()
        messages.success(request, 'Document supprimé avec succès.')

    return redirect('enrollment:candidature_documents', pk=candidature_pk)


# Inscriptions
class InscriptionListView(LoginRequiredMixin, ListView):
    model = Inscription
    template_name = 'enrollment/inscription/list.html'
    context_object_name = 'inscriptions'
    paginate_by = 25

    def get_queryset(self):
        queryset = Inscription.objects.select_related(
            'candidature', 'apprenant', 'classe_assignee', 'cree_par'
        ).order_by('-date_inscription')

        # Filtrage par statut
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        # Recherche
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero_inscription__icontains=search) |
                Q(apprenant__nom__icontains=search) |
                Q(apprenant__prenom__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuts'] = Inscription.STATUTS_INSCRIPTION
        context['current_statut'] = self.request.GET.get('statut', '')
        context['search'] = self.request.GET.get('search', '')
        return context

class InscriptionDetailView(LoginRequiredMixin, DetailView):
    model = Inscription
    template_name = 'enrollment/inscription/detail.html'
    context_object_name = 'inscription'

    def get_object(self):
        return get_object_or_404(
            Inscription.objects.select_related(
                'candidature', 'apprenant', 'classe_assignee', 'cree_par'
            ).prefetch_related('historique'),
            pk=self.kwargs['pk']
        )

class InscriptionCreateView(LoginRequiredMixin, CreateView):
    model = Inscription
    form_class = InscriptionForm
    template_name = 'enrollment/inscription/create.html'

    def form_valid(self, form):
        form.instance.cree_par = self.request.user
        messages.success(self.request, 'Inscription créée avec succès.')

        # Créer une entrée dans l'historique
        response = super().form_valid(form)

        HistoriqueInscription.objects.create(
            inscription=self.object,
            type_action='CREATION',
            nouvelle_valeur='ACTIVE',
            effectue_par=self.request.user
        )

        return response

    def get_success_url(self):
        return reverse_lazy('enrollment:inscription_detail', kwargs={'pk': self.object.pk})

# Transferts
class TransfertListView(LoginRequiredMixin, ListView):
    model = Transfert
    template_name = 'enrollment/transfert/list.html'
    context_object_name = 'transferts'
    paginate_by = 20

    def get_queryset(self):
        return Transfert.objects.select_related(
            'inscription__apprenant', 'classe_origine', 'classe_destination',
            'demande_par', 'approuve_par'
        ).order_by('-date_transfert')

class TransfertCreateView(LoginRequiredMixin, CreateView):
    model = Transfert
    form_class = TransfertForm
    template_name = 'enrollment/transfert/create.html'
    success_url = reverse_lazy('enrollment:transfert_list')

    def form_valid(self, form):
        form.instance.demande_par = self.request.user
        messages.success(self.request, 'Demande de transfert créée avec succès.')
        return super().form_valid(form)

@login_required
def transfert_approve(request, pk):
    """Approuver un transfert"""
    transfert = get_object_or_404(Transfert, pk=pk, statut='PENDING')

    if request.method == 'POST':
        notes = request.POST.get('notes', '')

        # Approuver le transfert
        transfert.statut = 'APPROVED'
        transfert.approuve_par = request.user
        transfert.date_approbation = timezone.now()
        transfert.notes_approbation = notes
        transfert.save()

        # Mettre à jour la classe de l'inscription
        transfert.inscription.classe_assignee = transfert.classe_destination
        transfert.inscription.save()

        # Créer une entrée dans l'historique
        HistoriqueInscription.objects.create(
            inscription=transfert.inscription,
            type_action='TRANSFERT',
            ancienne_valeur=transfert.classe_origine.nom,
            nouvelle_valeur=transfert.classe_destination.nom,
            motif=transfert.motif,
            effectue_par=request.user
        )

        messages.success(request, 'Transfert approuvé avec succès.')
        return redirect('enrollment:transfert_list')

    return render(request, 'enrollment/transfert/approve.html', {'transfert': transfert})

# Abandons
class AbandonCreateView(LoginRequiredMixin, CreateView):
    model = Abandon
    form_class = AbandonForm
    template_name = 'enrollment/abandon/create.html'
    success_url = reverse_lazy('enrollment:inscription_list')

    def form_valid(self, form):
        form.instance.traite_par = self.request.user

        # Mettre à jour le statut de l'inscription
        inscription = form.instance.inscription
        inscription.statut = 'WITHDRAWN'
        inscription.date_fin_reelle = form.instance.date_effet
        inscription.save()

        # Créer une entrée dans l'historique
        HistoriqueInscription.objects.create(
            inscription=inscription,
            type_action='ABANDON',
            nouvelle_valeur='WITHDRAWN',
            motif=form.instance.motif,
            effectue_par=self.request.user
        )

        messages.success(self.request, 'Abandon enregistré avec succès.')
        return super().form_valid(form)


@login_required
def api_stats(request):
    """API pour les statistiques du dashboard"""
    stats = {
        'candidatures_par_statut': list(
            Candidature.objects.values('statut').annotate(count=Count('id'))
        ),
        'inscriptions_par_mois': list(
            Inscription.objects.extra(
                select={'mois': 'EXTRACT(month FROM date_inscription)'}
            ).values('mois').annotate(count=Count('id')).order_by('mois')
        ),
    }
    return JsonResponse(stats)

@require_http_methods(["GET"])
def api_documents_requis_by_filiereId_publics(request, filiere_id):
    """
    API publique pour récupérer les documents requis par filière

    Args:
        request: HttpRequest
        filiere_id: UUID de la filière

    Returns:
        JsonResponse avec la liste des documents requis
    """
    try:
        # Vérifier que l'ID de filière est valide
        from apps.academic.models import Filiere
        filiere = get_object_or_404(Filiere, id=filiere_id)

        # Récupérer les documents requis pour cette filière
        documents_requis = DocumentRequis.objects.filter(
            filiere_id=filiere_id
        ).select_related('filiere', 'niveau').order_by('ordre_affichage', 'nom')

        # Construire la réponse
        documents_data = []
        for doc in documents_requis:
            documents_data.append({
                'id': doc.id,
                'nom': doc.nom,
                'description': doc.description,
                'type_document': doc.type_document,
                'type_document_display': doc.get_type_document_display(),
                'est_obligatoire': doc.est_obligatoire,
                'taille_maximale': doc.taille_maximale,
                'formats_autorises': doc.formats_autorises.split(',') if doc.formats_autorises else [],
                'ordre_affichage': doc.ordre_affichage,
                'niveau': {
                    'id': doc.niveau.id if doc.niveau else None,
                    'nom': doc.niveau.nom if doc.niveau else None,
                    'code': doc.niveau.code if doc.niveau else None,
                } if doc.niveau else None,
                'filiere': {
                    'id': doc.filiere.id,
                    'nom': doc.filiere.nom,
                    'code': doc.filiere.code,
                }
            })

        return JsonResponse({
            'success': True,
            'data': {
                'filiere': {
                    'id': filiere.id,
                    'nom': filiere.nom,
                    'code': filiere.code,
                },
                'documents_requis': documents_data,
                'total': len(documents_data)
            }
        })

    except ValidationError as e:
        logger.warning(f"ID filière invalide: {filiere_id} - {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'ID de filière invalide',
            'message': 'L\'identifiant de la filière fourni n\'est pas valide.'
        }, status=400)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des documents pour la filière {filiere_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur serveur',
            'message': 'Une erreur est survenue lors de la récupération des documents requis.'
        }, status=500)

@require_http_methods(["GET"])
def api_documents_requis_by_niveauId_publics(request, niveau_id):
    """
    API publique pour récupérer les documents requis par niveau

    Args:
        request: HttpRequest
        niveau_id: UUID du niveau

    Returns:
        JsonResponse avec la liste des documents requis
    """
    try:
        # Vérifier que l'ID de niveau est valide
        from apps.academic.models import Niveau
        niveau = get_object_or_404(Niveau, id=niveau_id)

        # Récupérer les documents requis pour ce niveau
        # Inclure aussi les documents sans niveau spécifique (niveau__isnull=True)
        documents_requis = DocumentRequis.objects.filter(
            Q(niveau_id=niveau_id) | Q(niveau__isnull=True)
        ).select_related('filiere', 'niveau').order_by('filiere__nom', 'ordre_affichage', 'nom')

        # Grouper les documents par filière
        documents_by_filiere = {}
        for doc in documents_requis:
            filiere_id = str(doc.filiere.id)
            if filiere_id not in documents_by_filiere:
                documents_by_filiere[filiere_id] = {
                    'filiere': {
                        'id': doc.filiere.id,
                        'nom': doc.filiere.nom,
                        'code': doc.filiere.code,
                    },
                    'documents': []
                }

            documents_by_filiere[filiere_id]['documents'].append({
                'id': doc.id,
                'nom': doc.nom,
                'description': doc.description,
                'type_document': doc.type_document,
                'type_document_display': doc.get_type_document_display(),
                'est_obligatoire': doc.est_obligatoire,
                'taille_maximale': doc.taille_maximale,
                'formats_autorises': doc.formats_autorises.split(',') if doc.formats_autorises else [],
                'ordre_affichage': doc.ordre_affichage,
                'specifique_niveau': doc.niveau is not None,
            })

        return JsonResponse({
            'success': True,
            'data': {
                'niveau': {
                    'id': niveau.id,
                    'nom': niveau.nom,
                    'code': niveau.code,
                },
                'documents_par_filiere': list(documents_by_filiere.values()),
                'total_filieres': len(documents_by_filiere),
                'total_documents': documents_requis.count()
            }
        })

    except ValidationError as e:
        logger.warning(f"ID niveau invalide: {niveau_id} - {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'ID de niveau invalide',
            'message': 'L\'identifiant du niveau fourni n\'est pas valide.'
        }, status=400)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des documents pour le niveau {niveau_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur serveur',
            'message': 'Une erreur est survenue lors de la récupération des documents requis.'
        }, status=500)

# Méthode save personnalisée pour DocumentRequis (optionnelle)
def save_document_requis_with_validation(self, *args, **kwargs):
    """
    Méthode save personnalisée pour DocumentRequis avec validations supplémentaires
    À ajouter dans la classe DocumentRequis si nécessaire
    """
    # Validation de la taille maximale
    if self.taille_maximale <= 0:
        raise ValidationError("La taille maximale doit être supérieure à 0")

    # Validation des formats autorisés
    if self.formats_autorises:
        formats = [f.strip().lower() for f in self.formats_autorises.split(',')]
        formats_valides = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'gif', 'txt']
        formats_invalides = [f for f in formats if f not in formats_valides]
        if formats_invalides:
            raise ValidationError(f"Formats non autorisés: {', '.join(formats_invalides)}")

        # Nettoyer et reformater
        self.formats_autorises = ','.join(formats)

    # Validation de l'ordre d'affichage
    if self.ordre_affichage < 0:
        self.ordre_affichage = 0

    # Si aucun ordre spécifié, mettre à la fin
    if not self.ordre_affichage and self.filiere:
        max_ordre = DocumentRequis.objects.filter(
            filiere=self.filiere,
            niveau=self.niveau
        ).aggregate(
            max_ordre=models.Max('ordre_affichage')
        )['max_ordre'] or 0
        self.ordre_affichage = max_ordre + 10

    super(DocumentRequis, self).save(*args, **kwargs)

class EnrollmentPagination(PageNumberPagination):
    """Pagination personnalisée pour l'API enrollment"""
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'pagination': {
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'page_size': self.page_size,
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
            },
            'results': data
        })

class BaseEnrollmentViewSet(viewsets.ModelViewSet):
    """ViewSet de base avec fonctionnalités communes"""
    pagination_class = EnrollmentPagination
    permission_classes = [IsAuthenticated, EnrollmentPermission]

    def get_user_etablissement(self):
        """Récupère l'établissement de l'utilisateur connecté"""
        return getattr(self.request.user, 'etablissement', None)

    def get_user_role(self):
        """Récupère le rôle de l'utilisateur connecté"""
        return getattr(self.request.user, 'role', None)

    def filter_by_etablissement(self, queryset):
        """Filtre le queryset par établissement selon les permissions"""
        if self.request.user.is_superuser:
            return queryset

        user_role = self.get_user_role()
        if user_role == 'ADMIN':
            return queryset

        user_etablissement = self.get_user_etablissement()
        if user_etablissement:
            return queryset.filter(etablissement=user_etablissement)

        return queryset.none()

    def log_action(self, action, instance, extra_data=None):
        """Log une action utilisateur"""
        data = {
            'user': str(self.request.user),
            'action': action,
            'instance': str(instance),
            'ip': self.request.META.get('REMOTE_ADDR'),
        }
        if extra_data:
            data.update(extra_data)

        logger.info(f"API Action: {data}")

class PeriodeCandidatureViewSet(BaseEnrollmentViewSet):
    """ViewSet pour les périodes de candidature"""

    serializer_class = PeriodeCandidatureSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['etablissement', 'annee_academique', 'est_active']
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'date_debut', 'date_fin', 'created_at']
    ordering = ['-date_debut']

    def get_queryset(self):
        queryset = PeriodeCandidature.objects.select_related(
            'etablissement', 'annee_academique'
        ).prefetch_related('filieres')
        return self.filter_by_etablissement(queryset)

    def perform_create(self, serializer):
        instance = serializer.save()
        self.log_action('CREATE_PERIODE', instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self.log_action('UPDATE_PERIODE', instance)

    def perform_destroy(self, instance):
        self.log_action('DELETE_PERIODE', instance)
        super().perform_destroy(instance)

    @action(detail=False, methods=['get'])
    def ouvertes(self, request):
        """Récupérer les périodes de candidature ouvertes"""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            est_active=True,
            date_debut__lte=today,
            date_fin__gte=today
        )

        # Pagination optionnelle
        if request.query_params.get('no_pagination') != 'true':
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Activer/désactiver une période de candidature"""
        periode = self.get_object()
        periode.est_active = not periode.est_active
        periode.save()

        self.log_action('TOGGLE_PERIODE', periode, {
            'new_status': periode.est_active
        })

        serializer = self.get_serializer(periode)
        return Response({
            'success': True,
            'message': f"Période {'activée' if periode.est_active else 'désactivée'}",
            'data': serializer.data
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques des périodes de candidature"""
        queryset = self.get_queryset()

        stats = {
            'total': queryset.count(),
            'actives': queryset.filter(est_active=True).count(),
            'ouvertes': queryset.filter(
                est_active=True,
                date_debut__lte=timezone.now().date(),
                date_fin__gte=timezone.now().date()
            ).count(),
            'futures': queryset.filter(
                date_debut__gt=timezone.now().date()
            ).count(),
            'passees': queryset.filter(
                date_fin__lt=timezone.now().date()
            ).count(),
        }

        return Response(stats)

class DocumentRequisViewSet(BaseEnrollmentViewSet):
    """ViewSet pour les documents requis"""

    serializer_class = DocumentRequisSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['filiere', 'niveau', 'type_document', 'est_obligatoire']
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'ordre_affichage', 'created_at']
    ordering = ['filiere', 'ordre_affichage', 'nom']

    def get_queryset(self):
        return DocumentRequis.objects.select_related('filiere', 'niveau')

    @action(detail=False, methods=['get'])
    def by_filiere(self, request):
        """Récupérer les documents requis pour une filière spécifique"""
        filiere_id = request.query_params.get('filiere_id')
        niveau_id = request.query_params.get('niveau_id')

        if not filiere_id:
            return Response(
                {'error': 'Le paramètre filiere_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            filiere_id = int(filiere_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'filiere_id doit être un entier valide'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(filiere_id=filiere_id)

        if niveau_id:
            try:
                niveau_id = int(niveau_id)
                queryset = queryset.filter(Q(niveau_id=niveau_id) | Q(niveau__isnull=True))
            except (ValueError, TypeError):
                return Response(
                    {'error': 'niveau_id doit être un entier valide'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            queryset = queryset.filter(niveau__isnull=True)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'filiere_id': filiere_id,
            'niveau_id': niveau_id,
            'count': queryset.count(),
            'documents': serializer.data
        })

    @action(detail=False, methods=['get'])
    def types_disponibles(self, request):
        """Récupérer tous les types de documents disponibles"""
        types = [
            {'value': code, 'label': label}
            for code, label in DocumentRequis.TYPES_DOCUMENT
        ]
        return Response({'types_documents': types})

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Création en masse de documents requis"""
        documents_data = request.data.get('documents', [])

        if not documents_data:
            return Response(
                {'error': 'Aucun document fourni'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_documents = []
        errors = []

        with transaction.atomic():
            for i, doc_data in enumerate(documents_data):
                try:
                    serializer = self.get_serializer(data=doc_data)
                    if serializer.is_valid():
                        instance = serializer.save()
                        created_documents.append(serializer.data)
                        self.log_action('BULK_CREATE_DOCUMENT', instance)
                    else:
                        errors.append({
                            'index': i,
                            'errors': serializer.errors
                        })
                except Exception as e:
                    errors.append({
                        'index': i,
                        'errors': {'general': str(e)}
                    })

        return Response({
            'success': len(errors) == 0,
            'created_count': len(created_documents),
            'created_documents': created_documents,
            'errors': errors
        })

class CandidatureViewSet(BaseEnrollmentViewSet):
    """ViewSet pour les candidatures"""

    permission_classes = [IsAuthenticated, CandidaturePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'statut', 'etablissement', 'filiere', 'niveau', 'annee_academique',
        'genre', 'frais_dossier_payes'
    ]
    search_fields = ['numero_candidature', 'nom', 'prenom', 'email', 'telephone']
    ordering_fields = ['numero_candidature', 'nom', 'prenom', 'date_soumission', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Candidature.objects.select_related(
            'etablissement', 'filiere', 'niveau', 'annee_academique', 'examine_par'
        ).prefetch_related('documents')

        user = self.request.user
        if user.is_superuser:
            return queryset

        user_role = self.get_user_role()
        if user_role == 'APPRENANT':
            return queryset.filter(email=user.email)
        elif user_role in ['CHEF_DEPARTMENT', 'ENSEIGNANT']:
            user_etablissement = self.get_user_etablissement()
            if user_etablissement:
                return queryset.filter(etablissement=user_etablissement)
        elif user_role == 'ADMIN':
            return queryset

        return queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return CandidatureListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return CandidatureCreateUpdateSerializer
        return CandidatureDetailSerializer

    def perform_create(self, serializer):
        candidature = serializer.save()
        self.log_action('CREATE_CANDIDATURE', candidature)

    def perform_update(self, serializer):
        candidature = serializer.save()
        self.log_action('UPDATE_CANDIDATURE', candidature)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Soumettre une candidature"""
        candidature = self.get_object()

        # Vérifications préliminaires
        if candidature.statut != 'BROUILLON':
            return Response(
                {'error': 'Seules les candidatures en brouillon peuvent être soumises'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Vérifier si l'utilisateur peut soumettre cette candidature
        user_role = self.get_user_role()
        if user_role == 'APPRENANT' and candidature.email != request.user.email:
            raise PermissionDenied("Vous ne pouvez soumettre que vos propres candidatures")

        # Vérifier les conditions de soumission
        peut_soumettre, message = candidature.peut_etre_soumise()
        if not peut_soumettre:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                candidature.soumettre()
                self.log_action('SUBMIT_CANDIDATURE', candidature)

            serializer = CandidatureDetailSerializer(candidature, context={'request': request})
            return Response({
                'success': True,
                'message': 'Candidature soumise avec succès',
                'data': serializer.data
            })
        except Exception as e:
            logger.error(f"Erreur soumission candidature {candidature.pk}: {e}")
            return Response(
                {'error': f'Erreur lors de la soumission: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def evaluate(self, request, pk=None):
        """Évaluer une candidature (approuver/rejeter)"""
        candidature = self.get_object()

        # Vérifier les permissions d'évaluation
        user_role = self.get_user_role()
        if user_role not in ['ADMIN', 'CHEF_DEPARTMENT']:
            raise PermissionDenied("Permissions insuffisantes pour évaluer les candidatures")

        if candidature.statut not in ['SOUMISE', 'EN_COURS_EXAMEN']:
            return Response(
                {'error': 'Seules les candidatures soumises peuvent être évaluées'},
                status=status.HTTP_400_BAD_REQUEST
            )

        decision = request.data.get('decision')
        notes = request.data.get('notes', '').strip()

        if decision not in ['APPROUVEE', 'REJETEE']:
            return Response(
                {'error': 'Décision invalide. Valeurs acceptées: APPROUVEE, REJETEE'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if decision == 'REJETEE' and not notes:
            return Response(
                {'error': 'Les notes sont obligatoires en cas de rejet'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                candidature.statut = decision
                candidature.examine_par = request.user
                candidature.date_decision = timezone.now()
                candidature.date_examen = timezone.now()

                if decision == 'APPROUVEE':
                    candidature.notes_approbation = notes
                else:
                    candidature.motif_rejet = notes

                candidature.save()

                self.log_action('EVALUATE_CANDIDATURE', candidature, {
                    'decision': decision,
                    'notes': notes[:100]  # Limiter les logs
                })

            serializer = CandidatureDetailSerializer(candidature, context={'request': request})
            return Response({
                'success': True,
                'message': f'Candidature {decision.lower()} avec succès',
                'data': serializer.data
            })

        except Exception as e:
            logger.error(f"Erreur évaluation candidature {candidature.pk}: {e}")
            return Response(
                {'error': f'Erreur lors de l\'évaluation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def bulk_evaluate(self, request):
        """Évaluation en masse des candidatures"""
        user_role = self.get_user_role()
        if user_role not in ['ADMIN', 'CHEF_DEPARTMENT']:
            raise PermissionDenied("Permissions insuffisantes pour l'évaluation en masse")

        candidature_ids = request.data.get('candidature_ids', [])
        decision = request.data.get('decision')
        notes = request.data.get('notes', '').strip()

        if not candidature_ids:
            return Response(
                {'error': 'Aucune candidature sélectionnée'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if decision not in ['APPROUVEE', 'REJETEE']:
            return Response(
                {'error': 'Décision invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if decision == 'REJETEE' and not notes:
            return Response(
                {'error': 'Les notes sont obligatoires pour le rejet en masse'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                candidatures = self.get_queryset().filter(
                    id__in=candidature_ids,
                    statut__in=['SOUMISE', 'EN_COURS_EXAMEN']
                )

                updated_count = 0
                for candidature in candidatures:
                    candidature.statut = decision
                    candidature.examine_par = request.user
                    candidature.date_decision = timezone.now()
                    candidature.date_examen = timezone.now()

                    if decision == 'APPROUVEE':
                        candidature.notes_approbation = notes
                    else:
                        candidature.motif_rejet = notes

                    candidature.save()
                    updated_count += 1

                self.log_action('BULK_EVALUATE', f"{updated_count} candidatures", {
                    'decision': decision,
                    'count': updated_count
                })

            return Response({
                'success': True,
                'message': f'{updated_count} candidature(s) {decision.lower()}(s) avec succès',
                'updated_count': updated_count
            })

        except Exception as e:
            logger.error(f"Erreur évaluation en masse: {e}")
            return Response(
                {'error': f'Erreur lors de l\'évaluation en masse: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques détaillées des candidatures"""
        queryset = self.get_queryset()

        # Filtres optionnels
        etablissement_id = request.query_params.get('etablissement_id')
        filiere_id = request.query_params.get('filiere_id')
        annee_id = request.query_params.get('annee_academique_id')
        periode_jours = int(request.query_params.get('periode', 30))

        if etablissement_id:
            try:
                queryset = queryset.filter(etablissement_id=int(etablissement_id))
            except (ValueError, TypeError):
                pass

        if filiere_id:
            try:
                queryset = queryset.filter(filiere_id=int(filiere_id))
            except (ValueError, TypeError):
                pass

        if annee_id:
            try:
                queryset = queryset.filter(annee_academique_id=int(annee_id))
            except (ValueError, TypeError):
                pass

        # Statistiques générales
        total_candidatures = queryset.count()

        stats_by_status = {}
        for statut_code, statut_label in Candidature.STATUTS_CANDIDATURE:
            stats_by_status[statut_code] = queryset.filter(statut=statut_code).count()

        # Candidatures récentes
        date_limite = timezone.now().date() - timedelta(days=periode_jours)
        nouvelles_candidatures = queryset.filter(created_at__date__gte=date_limite).count()

        # Évolution mensuelle (12 derniers mois)
        candidatures_par_mois = []
        for i in range(12):
            mois_debut = timezone.now().date() - timedelta(days=30 * (11 - i))
            mois_fin = mois_debut + timedelta(days=30)

            count = queryset.filter(
                created_at__date__gte=mois_debut,
                created_at__date__lt=mois_fin
            ).count()

            candidatures_par_mois.append({
                'mois': mois_debut.strftime('%Y-%m'),
                'label': mois_debut.strftime('%b %Y'),
                'count': count
            })

        # Top filières
        top_filieres = list(
            queryset.values('filiere__nom')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # Répartition par genre
        repartition_genre = list(
            queryset.values('genre')
            .annotate(count=Count('id'))
        )

        # Temps moyen de traitement
        candidatures_traitees = queryset.filter(
            statut__in=['APPROUVEE', 'REJETEE'],
            date_soumission__isnull=False,
            date_decision__isnull=False
        )

        temps_traitement_moyen = 0
        if candidatures_traitees.exists():
            durees = []
            for candidature in candidatures_traitees[:100]:  # Limiter pour performance
                if candidature.date_soumission and candidature.date_decision:
                    duree = (candidature.date_decision.date() - candidature.date_soumission.date()).days
                    durees.append(max(duree, 0))

            if durees:
                temps_traitement_moyen = sum(durees) / len(durees)

        # Taux de conversion
        taux_soumission = 0
        taux_approbation = 0

        if total_candidatures > 0:
            candidatures_soumises = stats_by_status.get('SOUMISE', 0) + stats_by_status.get('APPROUVEE',
                                                                                            0) + stats_by_status.get(
                'REJETEE', 0)
            taux_soumission = round((candidatures_soumises / total_candidatures) * 100, 2)

            if candidatures_soumises > 0:
                taux_approbation = round((stats_by_status.get('APPROUVEE', 0) / candidatures_soumises) * 100, 2)

        stats_data = {
            'resume': {
                'total_candidatures': total_candidatures,
                'nouvelles_periode': nouvelles_candidatures,
                'taux_soumission': taux_soumission,
                'taux_approbation': taux_approbation,
                'temps_traitement_moyen': round(temps_traitement_moyen, 1),
            },
            'par_statut': stats_by_status,
            'evolution_mensuelle': candidatures_par_mois,
            'top_filieres': top_filieres,
            'repartition_genre': repartition_genre,
            'periode_analyse': periode_jours
        }

        serializer = CandidatureStatsSerializer(stats_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def export_data(self, request):
        """Export des candidatures selon les filtres"""
        format_export = request.query_params.get('format', 'excel')

        if format_export not in ['excel', 'csv', 'pdf']:
            return Response(
                {'error': 'Format non supporté. Formats disponibles: excel, csv, pdf'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            queryset = self.filter_queryset(self.get_queryset())

            from ..utils import EnrollmentExporter

            if format_export == 'excel':
                filepath = EnrollmentExporter.export_to_excel(queryset, 'candidatures')
            elif format_export == 'csv':
                filepath = EnrollmentExporter.export_to_csv(queryset, 'candidatures')
            else:  # pdf
                from ..utils import export_candidatures_pdf
                filepath = export_candidatures_pdf(queryset)

            filename = filepath.split('/')[-1]

            self.log_action('EXPORT_CANDIDATURES', f"Format: {format_export}", {
                'format': format_export,
                'count': queryset.count(),
                'filename': filename
            })

            return Response({
                'success': True,
                'download_url': f'/media/exports/{filename}',
                'filename': filename,
                'format': format_export,
                'count': queryset.count()
            })

        except Exception as e:
            logger.error(f"Erreur export candidatures: {e}")
            return Response(
                {'error': f'Erreur lors de l\'export: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def documents_status(self, request, pk=None):
        """Statut des documents requis pour une candidature"""
        candidature = self.get_object()

        # Documents requis
        docs_requis = DocumentRequis.objects.filter(
            filiere=candidature.filiere
        ).filter(
            Q(niveau=candidature.niveau) | Q(niveau__isnull=True)
        ).order_by('ordre_affichage', 'nom')

        # Documents fournis
        docs_fournis = {
            doc.type_document: doc
            for doc in candidature.documents.all()
        }

        # Statut par document
        documents_status = []
        manquants_obligatoires = 0

        for doc_requis in docs_requis:
            doc_fourni = docs_fournis.get(doc_requis.type_document)
            is_missing = doc_requis.est_obligatoire and not doc_fourni

            if is_missing:
                manquants_obligatoires += 1

            documents_status.append({
                'type_document': doc_requis.type_document,
                'nom_requis': doc_requis.nom,
                'description': doc_requis.description,
                'obligatoire': doc_requis.est_obligatoire,
                'fourni': bool(doc_fourni),
                'valide': doc_fourni.est_valide if doc_fourni else False,
                'nom_fichier': doc_fourni.nom if doc_fourni else None,
                'date_upload': doc_fourni.created_at if doc_fourni else None,
                'manquant': is_missing,
                'doc_fourni_id': doc_fourni.id if doc_fourni else None,
            })

        completion_stats = {
            'total_requis': docs_requis.count(),
            'total_fournis': len(docs_fournis),
            'obligatoires_manquants': manquants_obligatoires,
            'peut_soumettre': manquants_obligatoires == 0,
            'taux_completion': round((len(docs_fournis) / max(docs_requis.count(), 1)) * 100, 2)
        }

        return Response({
            'candidature_id': candidature.id,
            'statut_candidature': candidature.statut,
            'completion': completion_stats,
            'documents': documents_status
        })

class DocumentCandidatureViewSet(BaseEnrollmentViewSet):
    """ViewSet pour les documents de candidature"""

    serializer_class = DocumentCandidatureSerializer
    permission_classes = [IsAuthenticated, DocumentCandidaturePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['candidature', 'type_document', 'est_valide']
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'created_at']
    ordering = ['candidature', 'type_document']

    def get_queryset(self):
        queryset = DocumentCandidature.objects.select_related(
            'candidature', 'valide_par'
        )

        user = self.request.user
        if user.is_superuser:
            return queryset

        user_role = self.get_user_role()
        if user_role == 'APPRENANT':
            return queryset.filter(candidature__email=user.email)
        elif user_role in ['CHEF_DEPARTMENT', 'ENSEIGNANT']:
            user_etablissement = self.get_user_etablissement()
            if user_etablissement:
                return queryset.filter(candidature__etablissement=user_etablissement)
        elif user_role == 'ADMIN':
            return queryset

        return queryset.none()

    @action(detail=True, methods=['post'])
    def manage_payment(self, request, pk=None):
        """Gestion complète des paiements d'une inscription"""
        inscription = self.get_object()

        user_role = self.get_user_role()
        if user_role not in ['ADMIN', 'CHEF_DEPARTMENT']:
            raise PermissionDenied("Permissions insuffisantes pour gérer les paiements")

        action_type = request.data.get('action', 'ADD')  # ADD, SET, REFUND
        montant = request.data.get('montant')
        reference = request.data.get('reference', '')
        notes = request.data.get('notes', '')
        date_paiement = request.data.get('date_paiement')

        if not montant:
            return Response(
                {'error': 'Le montant est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            montant = float(montant)
            if montant < 0:
                return Response(
                    {'error': 'Le montant ne peut pas être négatif'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Montant invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validation de la date
        if date_paiement:
            try:
                from datetime import datetime
                date_paiement = datetime.strptime(date_paiement, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Format de date invalide (YYYY-MM-DD)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            date_paiement = timezone.now().date()

        try:
            with transaction.atomic():
                ancien_total = inscription.total_paye
                ancien_solde = inscription.solde

                if action_type == 'SET':
                    # Définir le montant total payé
                    nouveau_total = montant
                elif action_type == 'ADD':
                    # Ajouter un paiement
                    nouveau_total = ancien_total + montant
                elif action_type == 'REFUND':
                    # Remboursement (soustraire)
                    nouveau_total = max(ancien_total - montant, 0)
                else:
                    return Response(
                        {'error': 'Action invalide. Actions: ADD, SET, REFUND'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Vérification cohérence
                if nouveau_total > inscription.frais_scolarite and action_type != 'REFUND':
                    return Response(
                        {'error': 'Le montant payé ne peut pas dépasser les frais de scolarité'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                inscription.total_paye = nouveau_total
                inscription.save()  # Le solde sera recalculé automatiquement

                # Description pour l'historique
                action_descriptions = {
                    'ADD': f'Paiement ajouté: {montant}',
                    'SET': f'Montant payé défini à: {montant}',
                    'REFUND': f'Remboursement: {montant}'
                }

                description = action_descriptions[action_type]
                if reference:
                    description += f' (Réf: {reference})'
                if notes:
                    description += f' - {notes}'

                # Créer l'historique
                HistoriqueInscription.objects.create(
                    inscription=inscription,
                    type_action='PAIEMENT',
                    ancienne_valeur=f'{ancien_total} (solde: {ancien_solde})',
                    nouvelle_valeur=f'{nouveau_total} (solde: {inscription.solde})',
                    motif=description,
                    effectue_par=request.user
                )

                self.log_action('MANAGE_PAYMENT', inscription, {
                    'action_type': action_type,
                    'montant': montant,
                    'ancien_total': ancien_total,
                    'nouveau_total': nouveau_total,
                    'reference': reference
                })  # Ajout de la parenthèse fermante manquante

                return Response({
                    'success': True,
                    'message': 'Paiement traité avec succès',
                    'ancien_total': ancien_total,
                    'nouveau_total': nouveau_total,
                    'solde': inscription.solde
                })

        except Exception as e:
            logger.error(f"Erreur gestion paiement {inscription.pk}: {e}")
            return Response(
                {'error': f'Erreur lors du traitement du paiement: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def validate_document(self, request, pk=None):
        """Valider un document"""
        document = self.get_object()

        user_role = self.get_user_role()
        if user_role not in ['ADMIN', 'CHEF_DEPARTMENT']:
            raise PermissionDenied("Permissions insuffisantes pour valider les documents")

        notes = request.data.get('notes', '').strip()
        est_valide = request.data.get('est_valide', True)

        try:
            with transaction.atomic():
                document.est_valide = est_valide
                document.valide_par = request.user
                document.date_validation = timezone.now()
                document.notes_validation = notes
                document.save()

                action = 'VALIDATE_DOCUMENT' if est_valide else 'INVALIDATE_DOCUMENT'
                self.log_action(action, document, {
                    'candidature': str(document.candidature.numero_candidature),
                    'type': document.type_document,
                    'notes': notes[:100]
                })

            serializer = self.get_serializer(document)
            message = 'Document validé' if est_valide else 'Document invalidé'

            return Response({
                'success': True,
                'message': message,
                'data': serializer.data
            })

        except Exception as e:
            logger.error(f"Erreur validation document {document.pk}: {e}")
            return Response(
                {'error': f'Erreur lors de la validation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def bulk_validate(self, request):
        """Validation en masse des documents"""
        user_role = self.get_user_role()
        if user_role not in ['ADMIN', 'CHEF_DEPARTMENT']:
            raise PermissionDenied("Permissions insuffisantes pour la validation en masse")

        document_ids = request.data.get('document_ids', [])
        est_valide = request.data.get('est_valide', True)
        notes = request.data.get('notes', '').strip()

        if not document_ids:
            return Response(
                {'error': 'Aucun document sélectionné'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                documents = self.get_queryset().filter(id__in=document_ids)
                updated_count = 0

                for document in documents:
                    document.est_valide = est_valide
                    document.valide_par = request.user
                    document.date_validation = timezone.now()
                    document.notes_validation = notes
                    document.save()
                    updated_count += 1

                action = 'BULK_VALIDATE_DOCUMENTS' if est_valide else 'BULK_INVALIDATE_DOCUMENTS'
                self.log_action(action, f"{updated_count} documents", {
                    'count': updated_count,
                    'est_valide': est_valide
                })

            message = f'{updated_count} document(s) {"validé(s)" if est_valide else "invalidé(s)"}'
            return Response({
                'success': True,
                'message': message,
                'updated_count': updated_count
            })

        except Exception as e:
            logger.error(f"Erreur validation en masse: {e}")
            return Response(
                {'error': f'Erreur lors de la validation en masse: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def validation_stats(self, request):
        """Statistiques de validation des documents"""
        queryset = self.get_queryset()

        total_documents = queryset.count()
        documents_valides = queryset.filter(est_valide=True).count()
        documents_en_attente = queryset.filter(est_valide=False).count()

        # Répartition par type
        stats_by_type = list(
            queryset.values('type_document')
            .annotate(
                total=Count('id'),
                valides=Count('id', filter=Q(est_valide=True))
            )
            .order_by('-total')
        )

        # Documents récents (7 derniers jours)
        date_limite = timezone.now() - timedelta(days=7)
        nouveaux_documents = queryset.filter(created_at__gte=date_limite).count()

        return Response({
            'resume': {
                'total_documents': total_documents,
                'documents_valides': documents_valides,
                'documents_en_attente': documents_en_attente,
                'nouveaux_7j': nouveaux_documents,
                'taux_validation': round((documents_valides / max(total_documents, 1)) * 100, 2)
            },
            'par_type': stats_by_type
        })

class InscriptionViewSet(BaseEnrollmentViewSet):
    """ViewSet pour les inscriptions"""

    serializer_class = InscriptionSerializer
    permission_classes = [IsAuthenticated, InscriptionPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'statut', 'statut_paiement', 'classe_assignee', 'apprenant',
        'candidature__etablissement', 'candidature__filiere'
    ]
    search_fields = [
        'numero_inscription', 'apprenant__nom', 'apprenant__prenom',
        'candidature__numero_candidature'
    ]
    ordering_fields = ['numero_inscription', 'date_inscription', 'created_at']
    ordering = ['-date_inscription']

    def get_queryset(self):
        queryset = Inscription.objects.select_related(
            'candidature', 'apprenant', 'classe_assignee', 'cree_par'
        )

        user = self.request.user
        if user.is_superuser:
            return queryset

        user_role = self.get_user_role()
        if user_role == 'APPRENANT':
            return queryset.filter(apprenant=user)
        elif user_role in ['CHEF_DEPARTMENT', 'ENSEIGNANT']:
            user_etablissement = self.get_user_etablissement()
            if user_etablissement:
                return queryset.filter(candidature__etablissement=user_etablissement)
        elif user_role == 'ADMIN':
            return queryset

        return queryset.none()

    def perform_create(self, serializer):
        with transaction.atomic():
            inscription = serializer.save(cree_par=self.request.user)

            # Créer l'historique
            HistoriqueInscription.objects.create(
                inscription=inscription,
                type_action='CREATION',
                nouvelle_valeur='ACTIVE',
                effectue_par=self.request.user
            )

            self.log_action('CREATE_INSCRIPTION', inscription)

    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """Changer le statut d'une inscription"""
        inscription = self.get_object()

        user_role = self.get_user_role()
        if user_role not in ['ADMIN', 'CHEF_DEPARTMENT']:
            raise PermissionDenied("Permissions insuffisantes pour modifier le statut")

        nouveau_statut = request.data.get('nouveau_statut')
        motif = request.data.get('motif', '').strip()

        if nouveau_statut not in dict(Inscription.STATUTS_INSCRIPTION):
            return Response(
                {'error': 'Statut invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if nouveau_statut == inscription.statut:
            return Response(
                {'error': 'Le statut est déjà identique'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Vérifications spécifiques selon le changement
        if nouveau_statut == 'SUSPENDED' and inscription.statut != 'ACTIVE':
            return Response(
                {'error': 'Seules les inscriptions actives peuvent être suspendues'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if nouveau_statut == 'ACTIVE' and inscription.statut != 'SUSPENDED':
            return Response(
                {'error': 'Seules les inscriptions suspendues peuvent être réactivées'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                ancien_statut = inscription.statut
                inscription.statut = nouveau_statut
                inscription.save()

                # Type d'action selon le changement
                type_action_map = {
                    ('ACTIVE', 'SUSPENDED'): 'SUSPENSION',
                    ('SUSPENDED', 'ACTIVE'): 'REACTIVATION',
                    ('ACTIVE', 'WITHDRAWN'): 'ABANDON',
                    ('ACTIVE', 'GRADUATED'): 'DIPLOME',
                    ('ACTIVE', 'EXPELLED'): 'EXCLUSION',
                }

                type_action = type_action_map.get(
                    (ancien_statut, nouveau_statut),
                    'CHANGEMENT_STATUT'
                )

                # Créer l'historique
                HistoriqueInscription.objects.create(
                    inscription=inscription,
                    type_action=type_action,
                    ancienne_valeur=ancien_statut,
                    nouvelle_valeur=nouveau_statut,
                    motif=motif,
                    effectue_par=request.user
                )

                self.log_action('CHANGE_INSCRIPTION_STATUS', inscription, {
                    'ancien_statut': ancien_statut,
                    'nouveau_statut': nouveau_statut,
                    'motif': motif[:100]
                })

            serializer = self.get_serializer(inscription)
            return Response({
                'success': True,
                'message': f'Statut changé de {ancien_statut} à {nouveau_statut}',
                'data': serializer.data
            })

        except Exception as e:
            logger.error(f"Erreur changement statut inscription {inscription.pk}: {e}")
            return Response(
                {'error': f'Erreur lors du changement de statut: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def update_payment(self, request, pk=None):
        """Mettre à jour les paiements d'une inscription"""
        inscription = self.get_object()

        user_role = self.get_user_role()
        if user_role not in ['ADMIN', 'CHEF_DEPARTMENT']:
            raise PermissionDenied("Permissions insuffisantes pour modifier les paiements")

        montant_paiement = request.data.get('montant_paiement')
        type_operation = request.data.get('type_operation', 'ADD')  # ADD ou SET
        notes = request.data.get('notes', '')

        if not montant_paiement:
            return Response(
                {'error': 'Le montant du paiement est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            montant_paiement = float(montant_paiement)
            if montant_paiement < 0:
                return Response(
                    {'error': 'Le montant ne peut pas être négatif'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            with transaction.atomic():
                ancien_total = inscription.total_paye

                if type_operation == 'SET':
                    nouveau_total = montant_paiement
                else:  # ADD
                    nouveau_total = ancien_total + montant_paiement

                if nouveau_total > inscription.frais_scolarite:
                    return Response(
                        {'error': 'Le montant total ne peut pas dépasser les frais de scolarité'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                inscription.total_paye = nouveau_total
                inscription.save()  # Le solde sera recalculé automatiquement

                # Créer l'historique
                HistoriqueInscription.objects.create(
                    inscription=inscription,
                    type_action='PAIEMENT',
                    ancienne_valeur=str(ancien_total),
                    nouvelle_valeur=str(nouveau_total),
                    motif=f"Paiement: {montant_paiement}. {notes}",
                    effectue_par=request.user
                )

                self.log_action('UPDATE_PAYMENT', inscription, {
                    'ancien_total': ancien_total,
                    'nouveau_total': nouveau_total,
                    'montant_operation': montant_paiement,
                    'type_operation': type_operation
                })

            serializer = self.get_serializer(inscription)
            return Response({
                'success': True,
                'message': f'Paiement mis à jour. Nouveau solde: {inscription.solde}',
                'data': serializer.data
            })

        except (ValueError, TypeError):
            return Response(
                {'error': 'Montant de paiement invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Erreur mise à jour paiement inscription {inscription.pk}: {e}")
            return Response(
                {'error': f'Erreur lors de la mise à jour du paiement: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def financial_summary(self, request):
        """Résumé financier des inscriptions"""
        queryset = self.get_queryset()

        # Filtres optionnels
        etablissement_id = request.query_params.get('etablissement_id')
        filiere_id = request.query_params.get('filiere_id')

        if etablissement_id:
            try:
                queryset = queryset.filter(candidature__etablissement_id=int(etablissement_id))
            except (ValueError, TypeError):
                pass

        if filiere_id:
            try:
                queryset = queryset.filter(candidature__filiere_id=int(filiere_id))
            except (ValueError, TypeError):
                pass

        # Agrégations financières
        financial_data = queryset.aggregate(
            total_inscriptions=Count('id'),
            total_frais_scolarite=Sum('frais_scolarite'),
            total_paye=Sum('total_paye'),
            total_solde=Sum('solde')
        )

        # Répartition par statut de paiement
        payment_status_breakdown = list(
            queryset.values('statut_paiement')
            .annotate(
                count=Count('id'),
                frais_total=Sum('frais_scolarite'),
                montant_paye=Sum('total_paye'),
                solde_total=Sum('solde')
            )
        )

        # Top filières par revenus
        top_filieres_revenus = list(
            queryset.values('candidature__filiere__nom')
            .annotate(
                revenus=Sum('total_paye'),
                count=Count('id'),
                solde_restant=Sum('solde')
            )
            .order_by('-revenus')[:10]
        )

        # Évolution des paiements (12 derniers mois)
        paiements_evolution = []
        for i in range(12):
            mois_debut = timezone.now().date() - timedelta(days=30 * (11 - i))
            mois_fin = mois_debut + timedelta(days=30)

            revenus_mois = queryset.filter(
                date_inscription__gte=mois_debut,
                date_inscription__lt=mois_fin
            ).aggregate(total=Sum('total_paye'))['total'] or 0

            paiements_evolution.append({
                'mois': mois_debut.strftime('%Y-%m'),
                'label': mois_debut.strftime('%b %Y'),
                'revenus': float(revenus_mois)
            })

        # Calculs de ratios
        frais_total = financial_data['total_frais_scolarite'] or 0
        paye_total = financial_data['total_paye'] or 0

        taux_recouvrement = 0
        if frais_total > 0:
            taux_recouvrement = round((paye_total / frais_total) * 100, 2)

        return Response({
            'resume': {
                'total_inscriptions': financial_data['total_inscriptions'],
                'total_frais_scolarite': float(frais_total),
                'total_paye': float(paye_total),
                'total_solde': float(financial_data['total_solde'] or 0),
                'taux_recouvrement': taux_recouvrement
            },
            'par_statut_paiement': payment_status_breakdown,
            'top_filieres_revenus': top_filieres_revenus,
            'evolution_mensuelle': paiements_evolution
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques complètes des inscriptions"""
        queryset = self.get_queryset()

        total_inscriptions = queryset.count()

        # Répartition par statut
        stats_by_status = {}
        for statut_code, statut_label in Inscription.STATUTS_INSCRIPTION:
            stats_by_status[statut_code] = queryset.filter(statut=statut_code).count()

        # Nouvelles inscriptions (30 derniers jours)
        date_limite = timezone.now().date() - timedelta(days=30)
        nouvelles_inscriptions = queryset.filter(date_inscription__gte=date_limite).count()

        # Évolution mensuelle
        evolution_mensuelle = []
        for i in range(12):
            mois_debut = timezone.now().date() - timedelta(days=30 * (11 - i))
            mois_fin = mois_debut + timedelta(days=30)

            count = queryset.filter(
                date_inscription__gte=mois_debut,
                date_inscription__lt=mois_fin
            ).count()

            evolution_mensuelle.append({
                'mois': mois_debut.strftime('%Y-%m'),
                'label': mois_debut.strftime('%b %Y'),
                'count': count
            })

        # Répartition par filière
        repartition_filiere = list(
            queryset.values('candidature__filiere__nom')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        stats_data = {
            'total_inscriptions': total_inscriptions,
            'nouvelles_30j': nouvelles_inscriptions,
            'inscriptions_actives': stats_by_status.get('ACTIVE', 0),
            'inscriptions_suspendues': stats_by_status.get('SUSPENDED', 0),
            'par_statut': stats_by_status,
            'evolution_mensuelle': evolution_mensuelle,
            'repartition_filiere': repartition_filiere,
        }

        serializer = InscriptionStatsSerializer(stats_data)
        return Response(serializer.data)

class TransfertViewSet(BaseEnrollmentViewSet):
    """ViewSet pour les transferts"""

    serializer_class = TransfertSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'classe_origine', 'classe_destination', 'demande_par']
    search_fields = [
        'inscription__apprenant__nom', 'inscription__apprenant__prenom',
        'inscription__numero_inscription'
    ]
    ordering_fields = ['date_transfert', 'created_at']
    ordering = ['-date_transfert']

    def get_queryset(self):
        queryset = Transfert.objects.select_related(
            'inscription__apprenant', 'classe_origine', 'classe_destination',
            'demande_par', 'approuve_par'
        )

        user = self.request.user
        if user.is_superuser:
            return queryset

        user_role = self.get_user_role()
        if user_role == 'APPRENANT':
            return queryset.filter(inscription__apprenant=user)
        elif user_role in ['CHEF_DEPARTMENT', 'ENSEIGNANT']:
            user_etablissement = self.get_user_etablissement()
            if user_etablissement:
                return queryset.filter(inscription__candidature__etablissement=user_etablissement)
        elif user_role == 'ADMIN':
            return queryset

        return queryset.none()

    def perform_create(self, serializer):
        transfert = serializer.save(demande_par=self.request.user)
        self.log_action('CREATE_TRANSFERT', transfert)

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Traiter un transfert (approuver ou rejeter)"""
        transfert = self.get_object()

        user_role = self.get_user_role()
        if user_role not in ['ADMIN', 'CHEF_DEPARTMENT']:
            raise PermissionDenied("Permissions insuffisantes pour traiter les transferts")

        if transfert.statut != 'PENDING':
            return Response(
                {'error': 'Seuls les transferts en attente peuvent être traités'},
                status=status.HTTP_400_BAD_REQUEST
            )

        decision = request.data.get('decision')  # 'APPROVED' ou 'REJECTED'
        notes = request.data.get('notes', '').strip()

        if decision not in ['APPROVED', 'REJECTED']:
            return Response(
                {'error': 'Décision invalide. Valeurs: APPROVED, REJECTED'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if decision == 'REJECTED' and not notes:
            return Response(
                {'error': 'Les notes sont obligatoires pour rejeter un transfert'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                transfert.statut = decision
                transfert.approuve_par = request.user
                transfert.date_approbation = timezone.now()
                transfert.notes_approbation = notes
                transfert.save()

                if decision == 'APPROVED':
                    # Mettre à jour la classe de l'inscription
                    transfert.inscription.classe_assignee = transfert.classe_destination
                    transfert.inscription.save()

                    # Créer l'historique
                    HistoriqueInscription.objects.create(
                        inscription=transfert.inscription,
                        type_action='TRANSFERT',
                        ancienne_valeur=transfert.classe_origine.nom,
                        nouvelle_valeur=transfert.classe_destination.nom,
                        motif=transfert.motif,
                        effectue_par=request.user
                    )

                self.log_action('PROCESS_TRANSFERT', transfert, {
                    'decision': decision,
                    'inscription': str(transfert.inscription.numero_inscription)
                })

            message = 'Transfert approuvé' if decision == 'APPROVED' else 'Transfert rejeté'
            serializer = self.get_serializer(transfert)

            return Response({
                'success': True,
                'message': message,
                'data': serializer.data
            })

        except Exception as e:
            logger.error(f"Erreur traitement transfert {transfert.pk}: {e}")
            return Response(
                {'error': f'Erreur lors du traitement: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def pending_count(self, request):
        """Nombre de transferts en attente"""
        count = self.get_queryset().filter(statut='PENDING').count()
        return Response({'pending_count': count})

class AbandonViewSet(BaseEnrollmentViewSet):
    """ViewSet pour les abandons"""

    serializer_class = AbandonSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'type_abandon', 'eligible_remboursement', 'remboursement_traite',
        'documents_retournes', 'materiel_retourne'
    ]
    search_fields = [
        'inscription__apprenant__nom', 'inscription__apprenant__prenom',
        'inscription__numero_inscription'
    ]
    ordering_fields = ['date_abandon', 'created_at']
    ordering = ['-date_abandon']

    def get_queryset(self):
        queryset = Abandon.objects.select_related(
            'inscription__apprenant', 'traite_par'
        )

        user = self.request.user
        if user.is_superuser:
            return queryset

        user_role = self.get_user_role()
        if user_role == 'APPRENANT':
            return queryset.filter(inscription__apprenant=user)
        elif user_role in ['CHEF_DEPARTMENT', 'ENSEIGNANT']:
            user_etablissement = self.get_user_etablissement()
            if user_etablissement:
                return queryset.filter(inscription__candidature__etablissement=user_etablissement)
        elif user_role == 'ADMIN':
            return queryset

        return queryset.none()

    def perform_create(self, serializer):
        with transaction.atomic():
            abandon = serializer.save(traite_par=self.request.user)

            # Mettre à jour l'inscription
            inscription = abandon.inscription
            inscription.statut = 'WITHDRAWN'
            inscription.date_fin_reelle = abandon.date_effet
            inscription.save()

            # Créer l'historique
            HistoriqueInscription.objects.create(
                inscription=inscription,
                type_action='ABANDON',
                nouvelle_valeur='WITHDRAWN',
                motif=abandon.motif,
                effectue_par=self.request.user
            )

            self.log_action('CREATE_ABANDON', abandon)

    @action(detail=True, methods=['post'])
    def process_refund(self, request, pk=None):
        """Traiter le remboursement d'un abandon"""
        abandon = self.get_object()

        user_role = self.get_user_role()
        if user_role not in ['ADMIN', 'CHEF_DEPARTMENT']:
            raise PermissionDenied("Permissions insuffisantes pour traiter les remboursements")

        if not abandon.eligible_remboursement:
            return Response(
                {'error': 'Cet abandon n\'est pas éligible au remboursement'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if abandon.remboursement_traite:
            return Response(
                {'error': 'Le remboursement a déjà été traité'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            abandon.remboursement_traite = True
            abandon.date_remboursement = timezone.now().date()
            abandon.save()

            self.log_action('PROCESS_REFUND', abandon, {
                'montant': str(abandon.montant_remboursable),
                'inscription': str(abandon.inscription.numero_inscription)
            })

            serializer = self.get_serializer(abandon)
            return Response({
                'success': True,
                'message': 'Remboursement traité avec succès',
                'data': serializer.data
            })

        except Exception as e:
            logger.error(f"Erreur traitement remboursement abandon {abandon.pk}: {e}")
            return Response(
                {'error': f'Erreur lors du traitement: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def refund_pending(self, request):
        """Abandons en attente de remboursement"""
        queryset = self.get_queryset().filter(
            eligible_remboursement=True,
            remboursement_traite=False
        )

        total_montant = queryset.aggregate(
            total=Sum('montant_remboursable')
        )['total'] or 0

        return Response({
            'count': queryset.count(),
            'total_montant_remboursable': float(total_montant)
        })
