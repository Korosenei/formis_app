# apps/enrollment/views.py
import logging
from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.generic import TemplateView, CreateView, UpdateView, DetailView, ListView
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
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from datetime import timedelta
from django.conf import settings

from django.contrib.auth import get_user_model
import secrets
import string

from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

from .forms import (
    PeriodeCandidatureForm, DocumentRequisForm, CandidatureForm,
    DocumentCandidatureForm, CandidatureFilterForm, InscriptionForm,
    TransfertForm, AbandonForm, CandidatureEvaluationForm
)
from .models import (
    PeriodeCandidature, DocumentRequis, Candidature, DocumentCandidature,
    Inscription, HistoriqueInscription, Transfert, Abandon
)

from .managers import EmailCandidatureManager

from .signals import *

from apps.academic.models import Filiere, Niveau, Classe
from apps.accounts.models import ProfilUtilisateur, ProfilApprenant
from apps.enrollment.models import DocumentCandidature
from apps.payments.models import PlanPaiement, InscriptionPaiement, Paiement

from apps.payments.services.ligdicash import ligdicash_service

logger = logging.getLogger(__name__)
User = get_user_model()


# ========== GESTION DES PÉRIODES DE CANDIDATURE ==========
class PeriodeCandidatureListView(LoginRequiredMixin, ListView):
    model = PeriodeCandidature
    template_name = 'enrollment/periode/list.html'
    context_object_name = 'periodes'
    paginate_by = 20

    def get_queryset(self):
        queryset = PeriodeCandidature.objects.select_related(
            'etablissement', 'annee_academique'
        ).prefetch_related('filieres')

        if not self.request.user.role == 'SUPERADMIN':
            queryset = queryset.filter(etablissement=self.request.user.etablissement)

        return queryset.order_by('-date_debut')

class PeriodeCandidatureCreateView(LoginRequiredMixin, CreateView):
    model = PeriodeCandidature
    form_class = PeriodeCandidatureForm
    template_name = 'enrollment/periode/create.html'
    success_url = reverse_lazy('enrollment:periode_list')

    def form_valid(self, form):
        messages.success(self.request, 'Période de candidature créée avec succès.')
        return super().form_valid(form)


# ========== GESTION DES CANDIDATURES ==========
class CandidatureCreateView(CreateView):
    """View pour créer une nouvelle candidature"""
    model = Candidature
    form_class = CandidatureForm
    template_name = 'enrollment/candidature/candidature.html'

    def post(self, request, *args, **kwargs):
        """Gestion AJAX et formulaire classique"""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.handle_ajax_request(request)
        return super().post(request, *args, **kwargs)

    def handle_ajax_request(self, request):
        """Traitement des requêtes AJAX"""
        try:
            logger.info("Début traitement candidature AJAX")

            data = self.extract_form_data(request)
            validation_errors = self.validate_required_fields(data)

            if validation_errors:
                return JsonResponse({
                    'success': False,
                    'error': 'Champs manquants',
                    'message': f'Les champs suivants sont obligatoires: {", ".join(validation_errors)}',
                    'missing_fields': validation_errors
                }, status=400)

            if self.check_email_exists(data['email'], data):
                return JsonResponse({
                    'success': False,
                    'error': 'Email déjà utilisé',
                    'message': 'Vous avez déjà une candidature en cours pour cette formation.'
                }, status=400)

            with transaction.atomic():
                candidature = self.create_candidature(data)
                documents_uploaded = self.process_uploaded_documents(request, candidature)

                try:
                    email_sent = EmailCandidatureManager.send_candidature_submitted(candidature)

                    if email_sent:
                        logger.info(f"Email de confirmation envoyé à {candidature.email}")
                    else:
                        logger.error(f"Échec envoi email à {candidature.email}")
                except Exception as e:
                    logger.error(f"Erreur envoi email: {str(e)}", exc_info=True)
                    # Ne pas bloquer la création de candidature si l'email échoue

                logger.info(f"Candidature créée et soumise: {candidature.numero_candidature}")

            return JsonResponse({
                'success': True,
                'message': 'Candidature soumise avec succès',
                'candidature_id': str(candidature.id),
                'numero_candidature': candidature.numero_candidature,
                'documents_uploaded': documents_uploaded,
                'redirect_url': reverse('enrollment:candidature_success') + f'?numero={candidature.numero_candidature}'
            })

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
            'etablissement': request.POST.get('etablissement'),
            'departement': request.POST.get('departement'),
            'filiere': request.POST.get('filiere'),
            'niveau': request.POST.get('niveau'),
            'annee_academique': request.POST.get('annee_academique'),
            'prenom': request.POST.get('prenom'),
            'nom': request.POST.get('nom'),
            'date_naissance': request.POST.get('date_naissance'),
            'lieu_naissance': request.POST.get('lieu_naissance'),
            'genre': request.POST.get('genre'),
            'telephone': request.POST.get('telephone'),
            'email': request.POST.get('email'),
            'adresse': request.POST.get('adresse'),
            'nom_pere': request.POST.get('nom_pere', ''),
            'telephone_pere': request.POST.get('telephone_pere', ''),
            'nom_mere': request.POST.get('nom_mere', ''),
            'telephone_mere': request.POST.get('telephone_mere', ''),
            'nom_tuteur': request.POST.get('nom_tuteur', ''),
            'telephone_tuteur': request.POST.get('telephone_tuteur', ''),
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
        return [field for field in required_fields if not data.get(field)]

    def check_email_exists(self, email, data):
        """Vérifier si l'email est déjà utilisé pour la même formation"""
        return Candidature.objects.filter(
            email=email,
            etablissement_id=data['etablissement'],
            filiere_id=data['filiere'],
            niveau_id=data['niveau'],
            annee_academique_id=data['annee_academique'],
            statut__in=['BROUILLON', 'SOUMISE', 'EN_COURS_EXAMEN', 'APPROUVEE']
        ).exists()

    def create_candidature(self, data):
        """Créer et soumettre automatiquement la candidature"""
        candidature = Candidature.objects.create(
            etablissement_id=data['etablissement'],
            filiere_id=data['filiere'],
            niveau_id=data['niveau'],
            annee_academique_id=data['annee_academique'],
            prenom=data['prenom'],
            nom=data['nom'],
            date_naissance=data['date_naissance'],
            lieu_naissance=data['lieu_naissance'],
            genre=data['genre'],
            telephone=data['telephone'],
            email=data['email'],
            adresse=data['adresse'],
            nom_pere=data['nom_pere'] or None,
            telephone_pere=data['telephone_pere'] or None,
            nom_mere=data['nom_mere'] or None,
            telephone_mere=data['telephone_mere'] or None,
            nom_tuteur=data['nom_tuteur'] or None,
            telephone_tuteur=data['telephone_tuteur'] or None,
            ecole_precedente=data['ecole_precedente'] or None,
            dernier_diplome=data['dernier_diplome'] or None,
            annee_obtention=int(data['annee_obtention']) if data['annee_obtention'] else None,
            statut='SOUMISE',
            date_soumission=timezone.now()
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

        return documents_uploaded

class CandidatureSoumettreView(DetailView):
    """View pour soumettre une candidature"""
    model = Candidature

    def post(self, request, *args, **kwargs):
        candidature = self.get_object()

        try:
            with transaction.atomic():
                if candidature.statut != 'BROUILLON':
                    return JsonResponse({
                        'success': False,
                        'message': 'Cette candidature ne peut plus être modifiée'
                    }, status=400)

                peut_soumettre, message = candidature.peut_etre_soumise()
                if not peut_soumettre:
                    return JsonResponse({
                        'success': False,
                        'message': message
                    }, status=400)

                # Vérifier l'unicité
                candidatures_existantes = Candidature.objects.filter(
                    email=candidature.email,
                    etablissement=candidature.etablissement,
                    filiere=candidature.filiere,
                    niveau=candidature.niveau,
                    annee_academique=candidature.annee_academique,
                    statut__in=['SOUMISE', 'EN_COURS_EXAMEN', 'APPROUVEE']
                ).exclude(id=candidature.id)

                if candidatures_existantes.exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'Vous avez déjà une candidature en cours pour cette formation'
                    }, status=400)

                # Soumettre
                candidature.statut = 'SOUMISE'
                candidature.date_soumission = timezone.now()
                candidature.save()

                # Envoyer email de confirmation
                EmailCandidatureManager.send_candidature_submitted(candidature)

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
    """View pour évaluer une candidature"""
    model = Candidature

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
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
                if candidature.statut not in ['SOUMISE', 'EN_COURS_EXAMEN']:
                    return JsonResponse({
                        'success': False,
                        'message': 'Cette candidature ne peut pas être évaluée'
                    }, status=400)

                candidature.statut = decision
                candidature.date_decision = timezone.now()
                candidature.examine_par = request.user

                if decision == 'REJETEE':
                    candidature.motif_rejet = motif_rejet
                else:
                    candidature.notes_approbation = notes_approbation

                candidature.save()

                # Envoyer email de notification
                EmailCandidatureManager.send_candidature_evaluated(candidature)

                # Si approuvée, créer un compte utilisateur
                # if decision == 'APPROUVEE':
                #     self.create_user_account(candidature)

                return JsonResponse({
                    'success': True,
                    'message': f'Candidature {decision.lower()} avec succès',
                    'decision': decision,
                    'date_decision': candidature.date_decision.strftime('%d/%m/%Y à %H:%M')
                })

        except Exception as e:
            logger.error(f"Erreur évaluation candidature: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Une erreur est survenue: {str(e)}'
            }, status=500)

    # def create_user_account(self, candidature):
    #     """Créer un compte utilisateur depuis une candidature approuvée"""
    #     try:
    #         if User.objects.filter(email=candidature.email).exists():
    #             logger.info(f"Compte existe déjà pour {candidature.email}")
    #             return
    #
    #         password = get_random_string(12)
    #
    #         user = User.objects.create_user(
    #             email=candidature.email,
    #             username=candidature.email,
    #             prenom=candidature.prenom,
    #             nom=candidature.nom,
    #             role='APPRENANT',
    #             etablissement=candidature.etablissement,
    #             departement=candidature.filiere.departement if hasattr(candidature.filiere, 'departement') else None,
    #             date_naissance=candidature.date_naissance,
    #             lieu_naissance=candidature.lieu_naissance,
    #             genre=candidature.genre,
    #             telephone=candidature.telephone,
    #             adresse=candidature.adresse,
    #             est_actif=True
    #         )
    #
    #         user.set_password(password)
    #         user.save()
    #
    #         # Envoyer les informations de connexion
    #         EmailCandidatureManager.send_account_created(user, password, candidature.etablissement)
    #
    #         logger.info(f"Compte créé pour {user.email}")
    #
    #     except Exception as e:
    #         logger.error(f"Erreur création compte: {str(e)}", exc_info=True)

class CandidatureSuccessView(DetailView):
    """View pour afficher la page de succès"""
    template_name = 'enrollment/candidature/success.html'

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

@login_required
@require_http_methods(["GET"])
def candidature_details_ajax(request, pk):
    """Récupérer les détails d'une candidature en AJAX"""
    try:
        candidature = get_object_or_404(
            Candidature.objects.select_related(
                'etablissement', 'filiere', 'niveau', 'annee_academique', 'examine_par'
            ),
            pk=pk
        )

        # Vérifier les permissions
        if request.user.role == 'CHEF_DEPARTEMENT':
            if candidature.filiere.departement != request.user.departement:
                return JsonResponse({
                    'success': False,
                    'message': 'Accès non autorisé'
                }, status=403)

        data = {
            'success': True,
            'candidature': {
                'id': str(candidature.id),
                'numero_candidature': candidature.numero_candidature,
                'prenom': candidature.prenom,
                'nom': candidature.nom,
                'date_naissance': candidature.date_naissance.strftime('%d/%m/%Y'),
                'lieu_naissance': candidature.lieu_naissance,
                'genre': candidature.genre,
                'telephone': candidature.telephone,
                'email': candidature.email,
                'adresse': candidature.adresse,
                'filiere': candidature.filiere.nom,
                'niveau': candidature.niveau.nom,
                'annee_academique': candidature.annee_academique.nom,
                'ecole_precedente': candidature.ecole_precedente or '',
                'dernier_diplome': candidature.dernier_diplome or '',
                'annee_obtention': candidature.annee_obtention or '',
                'statut': candidature.statut,
                'statut_display': candidature.get_statut_display(),
                'date_soumission': candidature.date_soumission.strftime('%d/%m/%Y %H:%M') if candidature.date_soumission else None,
                'date_decision': candidature.date_decision.strftime('%d/%m/%Y %H:%M') if candidature.date_decision else None,
                'examine_par': candidature.examine_par.get_full_name() if candidature.examine_par else None,
            }
        }

        return JsonResponse(data)

    except Exception as e:
        logger.error(f"Erreur récupération détails candidature: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Erreur lors du chargement des détails'
        }, status=500)

@login_required
@require_http_methods(["GET"])
def candidature_documents_ajax(request, pk):
    """Récupérer les documents d'une candidature en AJAX"""
    try:
        candidature = get_object_or_404(Candidature, pk=pk)

        # Vérifier les permissions
        if request.user.role == 'CHEF_DEPARTEMENT':
            if candidature.filiere.departement != request.user.departement:
                return JsonResponse({
                    'success': False,
                    'message': 'Accès non autorisé'
                }, status=403)

        documents = candidature.documents.all()

        documents_data = []
        for doc in documents:
            documents_data.append({
                'id': str(doc.id),
                'nom': doc.nom,
                'type_document': doc.type_document,
                'type_display': doc.get_type_document_display(),
                'fichier': doc.fichier.url if doc.fichier else '',
                'type': doc.format_fichier,
                'taille': doc.taille_fichier,
                'est_valide': doc.est_valide,
                'date_creation': doc.created_at.strftime('%d/%m/%Y %H:%M'),
            })

        return JsonResponse({
            'success': True,
            'documents': documents_data,
            'total': len(documents_data)
        })

    except Exception as e:
        logger.error(f"Erreur récupération documents: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Erreur lors du chargement des documents'
        }, status=500)

@login_required
@require_http_methods(["POST"])
def candidature_start_exam(request, pk):
    """Démarrer l'examen d'une candidature"""
    try:
        candidature = get_object_or_404(Candidature, pk=pk)

        # Vérifier les permissions
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            return JsonResponse({
                'success': False,
                'message': 'Accès non autorisé'
            }, status=403)

        if request.user.role == 'CHEF_DEPARTEMENT':
            if candidature.filiere.departement != request.user.departement:
                return JsonResponse({
                    'success': False,
                    'message': 'Accès non autorisé'
                }, status=403)

        # Vérifier le statut
        if candidature.statut != 'SOUMISE':
            return JsonResponse({
                'success': False,
                'message': 'Cette candidature ne peut pas être examinée'
            }, status=400)

        # Démarrer l'examen
        with transaction.atomic():
            candidature.statut = 'EN_COURS_EXAMEN'
            candidature.date_examen = timezone.now()
            candidature.examine_par = request.user
            candidature.save()

            logger.info(f"Examen démarré pour candidature {candidature.numero_candidature} par {request.user.username}")

        return JsonResponse({
            'success': True,
            'message': 'Examen démarré avec succès'
        })

    except Exception as e:
        logger.error(f"Erreur démarrage examen: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Erreur lors du démarrage de l\'examen'
        }, status=500)

# def create_user_from_candidature(candidature):
#     """
#     Créer un compte utilisateur APPRENANT depuis une candidature approuvée.
#     L'inscription et le paiement seront effectués lors de la première connexion.
#     """
#     try:
#         # Vérifier si l'utilisateur existe déjà
#         if User.objects.filter(email=candidature.email).exists():
#             logger.info(f"Compte existe déjà pour {candidature.email}")
#             return None
#
#         # Générer un mot de passe aléatoire sécurisé
#         password = get_random_string(12)
#
#         with transaction.atomic():
#             # Récupérer la photo d'identité depuis les documents de candidature
#             photo_profil = None
#             try:
#                 doc_photo = DocumentCandidature.objects.filter(
#                     candidature=candidature,
#                     type_document='PHOTO_IDENTITE'
#                 ).first()
#
#                 if doc_photo and doc_photo.fichier:
#                     photo_profil = doc_photo.fichier
#                     logger.info(f"Photo d'identité trouvée pour {candidature.email}")
#             except Exception as e:
#                 logger.error(f"Erreur récupération photo d'identité: {str(e)}")
#
#             # 1. Créer l'utilisateur de base avec rôle APPRENANT
#             user = User.objects.create_user(
#                 email=candidature.email,
#                 username=candidature.email,  # Sera remplacé par le matricule automatiquement
#                 prenom=candidature.prenom,
#                 nom=candidature.nom,
#                 role='APPRENANT',
#                 etablissement=candidature.etablissement,
#                 departement=candidature.filiere.departement,
#                 date_naissance=candidature.date_naissance,
#                 lieu_naissance=candidature.lieu_naissance,
#                 genre=candidature.genre,
#                 telephone=candidature.telephone,
#                 adresse=candidature.adresse,
#                 photo_profil=photo_profil,
#                 est_actif=True
#             )
#
#             user.set_password(password)
#             user.save()
#
#             logger.info(f"✅ Utilisateur créé: {user.email} - Matricule: {user.matricule}")
#
#             # 2. Créer le ProfilUtilisateur
#             profil_utilisateur, created = ProfilUtilisateur.objects.get_or_create(
#                 utilisateur=user,
#                 defaults={
#                     'recevoir_notifications': True,
#                     'recevoir_notifications_email': True,
#                     'langue': 'fr',
#                     'fuseau_horaire': 'Africa/Ouagadougou',
#                 }
#             )
#
#             logger.info(f"✅ ProfilUtilisateur créé pour {user.email}")
#
#             # 3. Créer le ProfilApprenant avec les informations de base
#             # IMPORTANT: Pas de classe assignée ni d'inscription à ce stade
#             profil_apprenant = ProfilApprenant.objects.create(
#                 utilisateur=user,
#                 # Informations académiques de base
#                 niveau_actuel=candidature.niveau,
#                 annee_academique=candidature.annee_academique,
#                 classe_actuelle=None,  # Sera assigné lors de l'inscription
#                 statut_paiement='EN_ATTENTE',
#
#                 # Informations parentales depuis la candidature
#                 nom_pere=candidature.nom_pere or '',
#                 telephone_pere=candidature.telephone_pere or '',
#                 nom_mere=candidature.nom_mere or '',
#                 telephone_mere=candidature.telephone_mere or '',
#                 nom_tuteur=candidature.nom_tuteur or '',
#                 telephone_tuteur=candidature.telephone_tuteur or '',
#             )
#
#             logger.info(f"✅ ProfilApprenant créé pour {user.email}")
#
#             # 4. Envoyer les informations de connexion par email
#             try:
#                 EmailCandidatureManager.send_account_created(
#                     user,
#                     password,
#                     candidature.etablissement
#                 )
#                 logger.info(f"✅ Email de création de compte envoyé à {user.email}")
#             except Exception as e:
#                 logger.error(f"❌ Erreur envoi email: {str(e)}")
#
#             logger.info(
#                 f"✅ Compte APPRENANT créé avec succès:\n"
#                 f"   - Email: {user.email}\n"
#                 f"   - Matricule: {user.matricule}\n"
#                 f"   - Rôle: {user.role}\n"
#                 f"   - Niveau: {candidature.niveau.nom}\n"
#                 f"   - Filière: {candidature.filiere.nom}\n"
#                 f"   ⚠️ L'apprenant devra s'inscrire et payer lors de sa première connexion"
#             )
#
#             return user
#
#     except Exception as e:
#         logger.error(f"❌ Erreur création compte depuis candidature: {str(e)}", exc_info=True)
#         return None

@login_required
@require_http_methods(["POST"])
def candidature_approve(request, pk):
    """
    Approuver une candidature
    Envoie UNIQUEMENT le lien d'inscription avec paiement
    PAS de création de compte à ce stade
    """
    try:
        candidature = get_object_or_404(Candidature, pk=pk)

        # Vérifier les permissions
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            return JsonResponse({
                'success': False,
                'message': 'Accès non autorisé'
            }, status=403)

        if request.user.role == 'CHEF_DEPARTEMENT':
            if candidature.filiere.departement != request.user.departement:
                return JsonResponse({
                    'success': False,
                    'message': 'Accès non autorisé'
                }, status=403)

        # Vérifier le statut
        if candidature.statut not in ['SOUMISE', 'EN_COURS_EXAMEN']:
            return JsonResponse({
                'success': False,
                'message': 'Cette candidature ne peut pas être approuvée'
            }, status=400)

        # Récupérer les notes
        import json
        data = json.loads(request.body)
        notes = data.get('notes', '')

        # Approuver dans une transaction atomique
        with transaction.atomic():
            candidature.statut = 'APPROUVEE'
            candidature.date_decision = timezone.now()
            candidature.examine_par = request.user
            candidature.notes_approbation = notes
            candidature.save()

            logger.info(f"[OK] Candidature approuvée: {candidature.numero_candidature}")

            # ========================================
            # IMPORTANT: Envoyer UNIQUEMENT l'email avec lien
            # PAS de création de compte
            # ========================================
            try:
                email_sent = EmailCandidatureManager.send_candidature_evaluated(candidature)

                if email_sent:
                    logger.info(
                        f"[OK] Email lien inscription envoyé à {candidature.email}\n"
                        f"     Token: {candidature.token_inscription}\n"
                        f"     Expire: {candidature.token_inscription_expire}\n"
                        f"     Le compte sera créé APRÈS le paiement"
                    )
                else:
                    logger.error(f"[ERROR] Échec envoi email à {candidature.email}")

            except Exception as e:
                logger.error(f"[ERROR] Envoi email: {str(e)}", exc_info=True)

        return JsonResponse({
            'success': True,
            'message': (
                'Candidature approuvée avec succès. '
                'Un email avec le lien d\'inscription a été envoyé au candidat. '
                'Le compte utilisateur sera créé automatiquement APRÈS le paiement.'
            ),
            'decision': 'APPROUVEE',
            'date_decision': candidature.date_decision.strftime('%d/%m/%Y à %H:%M'),
            'email_sent': email_sent,
            'token_inscription': candidature.token_inscription,
            'url_inscription': f"{settings.SITE_URL}/enrollment/inscription/nouvelle/{candidature.token_inscription}/"
        })

    except Exception as e:
        logger.error(f"[ERROR] Approbation candidature: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Une erreur est survenue: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
def candidature_reject(request, pk):
    """Rejeter une candidature"""
    try:
        candidature = get_object_or_404(Candidature, pk=pk)

        # Vérifier les permissions
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            return JsonResponse({
                'success': False,
                'message': 'Accès non autorisé'
            }, status=403)

        if request.user.role == 'CHEF_DEPARTEMENT':
            if candidature.filiere.departement != request.user.departement:
                return JsonResponse({
                    'success': False,
                    'message': 'Accès non autorisé'
                }, status=403)

        # Vérifier le statut
        if candidature.statut not in ['SOUMISE', 'EN_COURS_EXAMEN']:
            return JsonResponse({
                'success': False,
                'message': 'Cette candidature ne peut pas être rejetée'
            }, status=400)

        # Récupérer le motif
        import json
        data = json.loads(request.body)
        motif = data.get('motif', '')

        if not motif:
            return JsonResponse({
                'success': False,
                'message': 'Le motif de rejet est obligatoire'
            }, status=400)

        # Rejeter
        with transaction.atomic():
            candidature.statut = 'REJETEE'
            candidature.date_decision = timezone.now()
            candidature.examine_par = request.user
            candidature.motif_rejet = motif
            candidature.save()

            # Envoyer email de notification
            EmailCandidatureManager.send_candidature_evaluated(candidature)

            logger.info(f"Candidature {candidature.numero_candidature} rejetée par {request.user.username}")

        return JsonResponse({
            'success': True,
            'message': 'Candidature rejetée avec succès'
        })

    except Exception as e:
        logger.error(f"Erreur rejet candidature: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Erreur lors du rejet'
        }, status=500)

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
class InscriptionAvecPaiementView(TemplateView):
    """
    View publique pour inscription avec paiement
    N'affiche QUE les plans de paiement
    PAS de création de compte à ce stade
    """
    template_name = 'enrollment/inscription/inscription_publique.html'

    def get(self, request, token):
        try:
            candidature = get_object_or_404(
                Candidature.objects.select_related(
                    'etablissement', 'filiere', 'niveau', 'annee_academique'
                ),
                token_inscription=token,
                statut='APPROUVEE'
            )

            # Vérifier validité du token
            if not candidature.token_est_valide():
                messages.error(request, "Ce lien d'inscription a expiré. Contactez l'établissement.")
                return redirect('enrollment:candidature_create')

            # ============================================
            # VÉRIFIER SI DÉJÀ INSCRIT (avec apprenant)
            # ============================================
            if hasattr(candidature, 'inscription'):
                inscription_existante = candidature.inscription

                # Si inscription ACTIVE avec apprenant → déjà inscrit
                if inscription_existante.apprenant and inscription_existante.statut == 'ACTIVE':
                    logger.info(f"[INFO] Candidat déjà inscrit: {inscription_existante.apprenant.email}")
                    messages.info(request, "Vous êtes déjà inscrit. Connectez-vous avec vos identifiants.")
                    return redirect('accounts:login')

                # Si inscription PENDING sans apprenant → Nettoyer
                if not inscription_existante.apprenant:
                    logger.warning(
                        f"[WARN] Inscription PENDING orpheline détectée: {inscription_existante.numero_inscription}")

                    # Vérifier s'il y a des paiements en cours
                    paiements_en_cours = Paiement.objects.filter(
                        inscription_paiement__inscription=inscription_existante,
                        statut__in=['EN_ATTENTE', 'EN_COURS']
                    )

                    # Si paiements anciens (> 1 heure), nettoyer
                    from datetime import timedelta
                    paiements_recents = paiements_en_cours.filter(
                        created_at__gte=timezone.now() - timedelta(hours=1)
                    )

                    if not paiements_recents.exists():
                        logger.info("[CLEAN] Nettoyage inscription PENDING orpheline...")

                        # Annuler les vieux paiements
                        paiements_en_cours.update(
                            statut='ANNULE',
                            notes_admin='Paiement expiré automatiquement'
                        )

                        # Supprimer l'InscriptionPaiement
                        InscriptionPaiement.objects.filter(inscription=inscription_existante).delete()

                        # Supprimer l'inscription
                        inscription_existante.delete()

                        logger.info("[OK] Nettoyage terminé - Nouvelle tentative possible")

            # ============================================
            # AFFICHER LA PAGE D'INSCRIPTION
            # ============================================

            # Récupérer le plan de paiement
            plan = PlanPaiement.objects.get(
                filiere=candidature.filiere,
                niveau=candidature.niveau,
                annee_academique=candidature.annee_academique,
                est_actif=True
            )

            tranches = plan.tranches.order_by('numero')
            montant_unique = plan.get_montant_avec_remise()
            montant_echelonne = plan.get_montant_avec_frais()
            premiere_tranche = tranches.filter(est_premiere_tranche=True).first() or tranches.first()

            context = {
                'candidature': candidature,
                'plan': plan,
                'tranches': tranches,
                'montant_unique': montant_unique,
                'montant_echelonne': montant_echelonne,
                'premiere_tranche': premiere_tranche,
                'token': token,
            }

            return render(request, self.template_name, context)

        except PlanPaiement.DoesNotExist:
            logger.error(f"[ERROR] Plan de paiement non trouvé pour candidature {candidature.id}")
            messages.error(request, "Aucun plan de paiement configuré. Contactez l'établissement.")
            return redirect('enrollment:candidature_create')

        except Candidature.DoesNotExist:
            logger.error(f"[ERROR] Candidature non trouvée pour token: {token}")
            messages.error(request, "Lien d'inscription invalide.")
            return redirect('enrollment:candidature_create')

        except Exception as e:
            logger.error(f"[ERROR] Erreur get(): {str(e)}", exc_info=True)
            messages.error(request, f"Une erreur est survenue: {str(e)}")
            return redirect('enrollment:candidature_create')

    def post(self, request, token):
        """
        Traitement de l'inscription
        Crée UNIQUEMENT l'inscription et le paiement
        PAS de création de compte
        """
        try:
            candidature = get_object_or_404(
                Candidature,
                token_inscription=token,
                statut='APPROUVEE'
            )

            if not candidature.token_est_valide():
                return JsonResponse({
                    'success': False,
                    'message': "Le lien d'inscription a expiré"
                }, status=400)

            type_paiement = request.POST.get('type_paiement')
            if type_paiement not in ['UNIQUE', 'ECHELONNE']:
                return JsonResponse({
                    'success': False,
                    'message': "Type de paiement invalide"
                }, status=400)

            with transaction.atomic():
                # ============================================
                # VÉRIFIER/NETTOYER INSCRIPTION EXISTANTE
                # ============================================
                if hasattr(candidature, 'inscription'):
                    inscription_existante = candidature.inscription

                    # Si déjà inscrit avec apprenant
                    if inscription_existante.apprenant:
                        logger.warning(f"[WARN] Tentative de réinscription: {inscription_existante.apprenant.email}")
                        return JsonResponse({
                            'success': False,
                            'message': "Vous êtes déjà inscrit. Connectez-vous avec vos identifiants."
                        }, status=400)

                    # Si PENDING sans apprenant, nettoyer
                    logger.info(f"[CLEAN] Suppression inscription PENDING: {inscription_existante.numero_inscription}")
                    InscriptionPaiement.objects.filter(inscription=inscription_existante).delete()
                    inscription_existante.delete()

                # ============================================
                # ÉTAPE 1: CRÉER L'INSCRIPTION SANS APPRENANT
                # ============================================
                plan = PlanPaiement.objects.get(
                    filiere=candidature.filiere,
                    niveau=candidature.niveau,
                    annee_academique=candidature.annee_academique,
                    est_actif=True
                )

                inscription = Inscription.objects.create(
                    candidature=candidature,
                    apprenant=None,  # ⚠️ NULL pour l'instant
                    frais_scolarite=plan.montant_total,
                    date_debut=timezone.now().date(),
                    date_fin_prevue=candidature.annee_academique.date_fin,
                    statut='PENDING',  # En attente du paiement
                    cree_par=None
                )

                logger.info(f"[OK] Inscription créée (sans apprenant): {inscription.numero_inscription}")

                # ============================================
                # ÉTAPE 2: CRÉER LE PAIEMENT
                # ============================================
                montant_du = (plan.get_montant_avec_remise()
                              if type_paiement == 'UNIQUE'
                              else plan.get_montant_avec_frais())

                inscription_paiement = InscriptionPaiement.objects.create(
                    inscription=inscription,
                    plan=plan,
                    type_paiement=type_paiement,
                    montant_total_du=montant_du,
                    statut='EN_ATTENTE'
                )

                # Déterminer le montant à payer
                if type_paiement == 'UNIQUE':
                    montant_a_payer = montant_du
                    tranche = None
                    description = f"Paiement unique - Inscription {candidature.filiere.nom}"
                else:
                    tranche = plan.tranches.filter(
                        est_premiere_tranche=True
                    ).first() or plan.tranches.order_by('numero').first()

                    montant_a_payer = tranche.get_montant_avec_penalite()
                    description = f"Première tranche - Inscription {candidature.filiere.nom}"

                paiement = Paiement.objects.create(
                    inscription_paiement=inscription_paiement,
                    tranche=tranche,
                    montant=montant_a_payer,
                    methode_paiement='LIGDICASH',
                    statut='EN_ATTENTE',
                    description=description
                )

                logger.info(f"[OK] Paiement créé: {paiement.id} - Montant: {montant_a_payer}")

                # ============================================
                # Redirection vers le paiement LigdiCash
                # ============================================
                return JsonResponse({
                    'success': True,
                    'message': 'Redirection vers le paiement...',
                    'redirect_url': reverse('payments:payer_ligdicash_public', kwargs={
                        'paiement_id': paiement.id,
                        'token': token
                    })
                })

        except Exception as e:
            logger.error(f"[ERROR] Création inscription: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Erreur: {str(e)}'
            }, status=500)

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


# ========== API PUBLIQUE ==========
@require_http_methods(["GET"])
def api_documents_requis_by_filiereId(request, filiere_id):
    """API pour récupérer les documents requis d'une filière"""
    try:
        filiere = get_object_or_404(Filiere, id=filiere_id)

        documents_requis = DocumentRequis.objects.filter(
            filiere_id=filiere_id
        ).select_related('filiere', 'niveau').order_by('ordre_affichage', 'nom')

        documents_data = []
        for doc in documents_requis:
            documents_data.append({
                'id': str(doc.id),
                'nom': doc.nom,
                'description': doc.description,
                'type_document': doc.type_document,
                'type_document_display': doc.get_type_document_display(),
                'est_obligatoire': doc.est_obligatoire,
                'taille_maximale': doc.taille_maximale,
                'formats_autorises': doc.formats_autorises.split(',') if doc.formats_autorises else [],
                'ordre_affichage': doc.ordre_affichage,
            })

        return JsonResponse({
            'success': True,
            'data': {
                'filiere': {
                    'id': str(filiere.id),
                    'nom': filiere.nom,
                    'code': filiere.code,
                },
                'documents_requis': documents_data,
                'total': len(documents_data)
            }
        })

    except Exception as e:
        logger.error(f"Erreur API documents: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur serveur',
            'message': 'Une erreur est survenue.'
        }, status=500)

@require_http_methods(["GET"])
def api_documents_requis_by_niveauId_publics(request, niveau_id):

    try:
        # Vérifier que l'ID de niveau est valide
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

# Export
@login_required
def export_candidatures(request):
    """Exporter les candidatures"""
    # Implémentation de l'export Excel/CSV
    pass

@login_required
def export_inscriptions(request):
    """Exporter les inscriptions"""
    # Implémentation de l'export Excel/CSV
    pass




##############################
### APPRENANT INSCRIPTION ####
##############################
# def payer_ligdicash_public(request, paiement_id, token):
#     """
#     Paiement LigdiCash pour inscription publique (sans compte)
#     """
#     try:
#         # Vérifier le token
#         candidature = get_object_or_404(
#             Candidature,
#             token_inscription=token,
#             statut='APPROUVEE'
#         )
#
#         if not candidature.token_est_valide():
#             messages.error(request, "Le lien d'inscription a expiré.")
#             return redirect('enrollment:candidature_create')
#
#         # Récupérer le paiement
#         paiement = get_object_or_404(
#             Paiement.objects.select_related(
#                 'inscription_paiement__inscription__candidature'
#             ),
#             id=paiement_id,
#             inscription_paiement__inscription__candidature=candidature
#         )
#
#         if paiement.statut != 'EN_ATTENTE':
#             messages.error(request, "Ce paiement ne peut plus être traité.")
#             return redirect('enrollment:candidature_create')
#
#         # Créer les URLs de retour publiques
#         urls = {
#             'success': request.build_absolute_uri(
#                 reverse('payments:callback_success_public', kwargs={
#                     'paiement_id': paiement.id,
#                     'token': token
#                 })
#             ),
#             'error': request.build_absolute_uri(
#                 reverse('payments:callback_error_public', kwargs={
#                     'paiement_id': paiement.id,
#                     'token': token
#                 })
#             ),
#             'callback': request.build_absolute_uri(
#                 reverse('payments:webhook_ligdicash')
#             )
#         }
#
#         # Appeler LigdiCash
#         success, response = ligdicash_service.creer_paiement_redirection(
#             paiement_id=str(paiement.id),
#             montant=paiement.montant,
#             description=paiement.description,
#             email_client=candidature.email,
#             nom_client=f"{candidature.prenom} {candidature.nom}",
#             url_retour_succes=urls['success'],
#             url_retour_echec=urls['error'],
#             url_callback=urls['callback']
#         )
#
#         if success:
#             paiement.statut = 'EN_COURS'
#             paiement.reference_externe = response.get('transaction_id')
#             paiement.donnees_transaction = response.get('raw_response', {})
#             paiement.save()
#
#             payment_url = response.get('payment_url')
#             if payment_url:
#                 return redirect(payment_url)
#             else:
#                 messages.error(request, "URL de paiement non reçue.")
#                 return redirect('enrollment:candidature_create')
#         else:
#             error_msg = response.get('error', 'Erreur inconnue')
#             messages.error(request, f"Impossible d'initier le paiement: {error_msg}")
#             paiement.echec(f"Échec création LigdiCash: {error_msg}")
#             return redirect('enrollment:candidature_create')
#
#     except Exception as e:
#         logger.error(f"Erreur paiement public: {str(e)}", exc_info=True)
#         messages.error(request, "Une erreur est survenue.")
#         return redirect('enrollment:candidature_create')
#
# def callback_success_public(request, paiement_id, token):
#     """
#     Callback de succès pour paiement public
#     Crée le compte utilisateur après confirmation du paiement
#     """
#     try:
#         candidature = get_object_or_404(
#             Candidature.objects.select_related(
#                 'etablissement', 'filiere', 'niveau', 'annee_academique'
#             ),
#             token_inscription=token,
#             statut='APPROUVEE'
#         )
#
#         paiement = get_object_or_404(
#             Paiement.objects.select_related(
#                 'inscription_paiement__inscription__candidature'
#             ),
#             id=paiement_id,
#             inscription_paiement__inscription__candidature=candidature
#         )
#
#         inscription = paiement.inscription_paiement.inscription
#
#         # Vérifier le statut auprès de LigdiCash
#         if paiement.reference_externe and paiement.statut != 'CONFIRME':
#             success, status_data = ligdicash_service.verifier_statut_paiement(
#                 paiement.reference_externe
#             )
#
#             if success and status_data.get('status') == 'CONFIRME':
#                 with transaction.atomic():
#                     # Confirmer le paiement
#                     frais = status_data.get('fees', 0)
#                     paiement.confirmer(
#                         reference_externe=paiement.reference_externe,
#                         frais=frais
#                     )
#
#                     # Créer le compte utilisateur
#                     user = creer_utilisateur_depuis_candidature(candidature)
#
#                     if user:
#                         # Lier l'inscription à l'utilisateur
#                         inscription.apprenant = user
#                         inscription.statut = 'ACTIVE'
#                         inscription.save()
#
#                         # Invalider le token
#                         candidature.token_inscription = None
#                         candidature.token_inscription_expire = None
#                         candidature.save()
#
#                         logger.info(f"Compte créé et inscription activée: {user.email}")
#
#                         return render(request, 'enrollment/inscription/success_public.html', {
#                             'candidature': candidature,
#                             'user': user,
#                             'inscription': inscription,
#                             'paiement': paiement
#                         })
#
#         if paiement.statut == 'CONFIRME':
#             messages.info(request, "Votre paiement a été confirmé. Connectez-vous avec vos identifiants.")
#             return redirect('accounts:login')
#
#         messages.info(request, "Votre paiement est en cours de traitement.")
#         return render(request, 'enrollment/inscription/attente_confirmation.html', {
#             'candidature': candidature,
#             'paiement': paiement
#         })
#
#     except Exception as e:
#         logger.error(f"Erreur callback success public: {str(e)}", exc_info=True)
#         messages.error(request, "Une erreur est survenue.")
#         return redirect('enrollment:candidature_create')
#
# def creer_utilisateur_depuis_candidature(candidature):
#     """
#     Crée un utilisateur APPRENANT depuis une candidature avec mot de passe aléatoire
#     """
#     try:
#
#         User = get_user_model()
#
#         # Vérifier si existe déjà
#         if User.objects.filter(email=candidature.email).exists():
#             logger.warning(f"Utilisateur existe déjà: {candidature.email}")
#             return User.objects.get(email=candidature.email)
#
#         # Générer mot de passe sécurisé
#         alphabet = string.ascii_letters + string.digits + "!@#$%"
#         password = ''.join(secrets.choice(alphabet) for _ in range(12))
#
#         with transaction.atomic():
#             # Créer l'utilisateur
#             user = User.objects.create_user(
#                 email=candidature.email,
#                 username=candidature.email,
#                 prenom=candidature.prenom,
#                 nom=candidature.nom,
#                 role='APPRENANT',
#                 etablissement=candidature.etablissement,
#                 departement=candidature.filiere.departement,
#                 date_naissance=candidature.date_naissance,
#                 lieu_naissance=candidature.lieu_naissance,
#                 genre=candidature.genre,
#                 telephone=candidature.telephone,
#                 adresse=candidature.adresse,
#                 est_actif=True
#             )
#
#             user.set_password(password)
#             user.save()
#
#             # Créer les profils
#             ProfilUtilisateur.objects.get_or_create(
#                 utilisateur=user,
#                 defaults={
#                     'recevoir_notifications': True,
#                     'recevoir_notifications_email': True,
#                     'langue': 'fr',
#                 }
#             )
#
#             ProfilApprenant.objects.create(
#                 utilisateur=user,
#                 niveau_actuel=candidature.niveau,
#                 annee_academique=candidature.annee_academique,
#                 statut_paiement='PARTIEL',
#                 nom_pere=candidature.nom_pere,
#                 telephone_pere=candidature.telephone_pere,
#                 nom_mere=candidature.nom_mere,
#                 telephone_mere=candidature.telephone_mere,
#                 nom_tuteur=candidature.nom_tuteur,
#                 telephone_tuteur=candidature.telephone_tuteur,
#             )
#
#             # Envoyer les identifiants par email
#             EmailCandidatureManager.send_account_created(
#                 user,
#                 password,
#                 candidature.etablissement
#             )
#
#             logger.info(f"✅ Compte créé après paiement: {user.email} - Matricule: {user.matricule}")
#
#             return user
#
#     except Exception as e:
#         logger.error(f"❌ Erreur création utilisateur: {str(e)}", exc_info=True)
#         return None
