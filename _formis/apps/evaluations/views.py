# apps/evaluations/views.py
from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Sum, Avg, Max, Min
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
import json
import csv
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import mimetypes

from .models import Evaluation, Composition, FichierComposition, Note
from .forms import (
    EvaluationForm, CompositionUploadForm, CorrectionForm,
    NoteForm, EvaluationSearchForm, PublierCorrectionForm,
    BulkNoteForm, ImportNotesForm, StatistiquesForm
)
from .utils import MoyenneCalculator, EvaluationUtils
from apps.core.decorators import (
    role_required, enseignant_owns_evaluation, apprenant_in_evaluation_classes,
    check_evaluation_availability, composition_can_be_modified,
    active_academic_year_required, require_evaluation_file_access
)

from apps.establishments.models import AnneeAcademique
from apps.courses.models import Matiere
from apps.academic.models import Classe
from apps.accounts.models import Utilisateur


# ============ VUES ENSEIGNANT ============
@login_required
def evaluations_enseignant(request):
    """Liste des évaluations de l'enseignant"""
    if request.user.role != 'ENSEIGNANT':
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    evaluations = Evaluation.objects.filter(
        enseignant=request.user
    ).select_related('matiere').prefetch_related('classes').order_by('-date_debut')

    # Filtres
    statut = request.GET.get('statut')
    if statut:
        evaluations = evaluations.filter(statut=statut)

    matiere_id = request.GET.get('matiere')
    if matiere_id:
        evaluations = evaluations.filter(matiere_id=matiere_id)

    # Statistiques
    stats = {
        'total': evaluations.count(),
        'brouillon': evaluations.filter(statut='BROUILLON').count(),
        'programmees': evaluations.filter(statut='PROGRAMMEE').count(),
        'en_cours': evaluations.filter(statut='EN_COURS').count(),
        'terminees': evaluations.filter(statut='TERMINEE').count(),
    }

    # Mes matières
    matieres = Matiere.objects.filter(
        enseignant_responsable=request.user,
        actif=True
    )

    context = {
        'evaluations': evaluations,
        'stats': stats,
        'matieres': matieres,
        'statuts': Evaluation.STATUT,
    }

    return render(request, 'evaluations/enseignant/list.html', context)

@login_required
def creer_evaluation(request):
    """Créer une nouvelle évaluation"""
    if request.user.role != 'ENSEIGNANT':
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    if request.method == 'POST':
        try:
            matiere = get_object_or_404(Matiere, id=request.POST.get('matiere'))

            # Vérifier le coefficient disponible
            coefficient = Decimal(request.POST.get('coefficient', '1.0'))
            total_utilise = Evaluation.objects.filter(
                matiere=matiere,
                enseignant=request.user,
                statut__in=['PROGRAMMEE', 'EN_COURS', 'TERMINEE']
            ).aggregate(total=models.Sum('coefficient'))['total'] or Decimal('0')

            coef_restant = Decimal(str(matiere.coefficient)) - total_utilise

            if coefficient > coef_restant:
                messages.error(
                    request,
                    f"Coefficient insuffisant. Disponible: {coef_restant}, Demandé: {coefficient}"
                )
                return redirect('evaluations:evaluation_create')

            # Créer l'évaluation
            evaluation = Evaluation.objects.create(
                enseignant=request.user,
                matiere=matiere,
                titre=request.POST.get('titre'),
                description=request.POST.get('description'),
                type_evaluation=request.POST.get('type_evaluation'),
                coefficient=coefficient,
                note_maximale=request.POST.get('note_maximale', 20),
                date_debut=request.POST.get('date_debut'),
                date_fin=request.POST.get('date_fin'),
                duree_minutes=request.POST.get('duree_minutes'),
                correction_visible_immediatement=request.POST.get('correction_visible_immediatement') == 'on',
                autorise_retard=request.POST.get('autorise_retard') == 'on',
                penalite_retard=request.POST.get('penalite_retard', 0),
                statut=request.POST.get('statut', 'BROUILLON')
            )

            # Gérer le fichier d'évaluation
            if 'fichier_evaluation' in request.FILES:
                evaluation.fichier_evaluation = request.FILES['fichier_evaluation']
                evaluation.save()

            # Ajouter les classes
            classes_ids = request.POST.getlist('classes')
            evaluation.classes.set(classes_ids)

            messages.success(request, "Évaluation créée avec succès")
            return redirect('evaluations:evaluation_detail_enseignant', pk=evaluation.pk)

        except Exception as e:
            messages.error(request, f"Erreur lors de la création: {str(e)}")
            return redirect('evaluations:evaluation_create')

    # GET
    matieres = Matiere.objects.filter(
        enseignant_responsable=request.user,
        actif=True
    )

    # Calculer le coefficient restant pour chaque matière
    for matiere in matieres:
        total_utilise = Evaluation.objects.filter(
            matiere=matiere,
            enseignant=request.user,
            statut__in=['PROGRAMMEE', 'EN_COURS', 'TERMINEE']
        ).aggregate(total=models.Sum('coefficient'))['total'] or Decimal('0')

        matiere.coefficient_restant = float(Decimal(str(matiere.coefficient)) - total_utilise)

    classes = Classe.objects.filter(
        niveau__filiere__etablissement=request.user.etablissement,
        est_active=True
    )

    context = {
        'matieres': matieres,
        'classes': classes,
        'types_evaluation': Evaluation.TYPE_EVALUATION,
    }

    return render(request, 'evaluations/evaluation/form.html', context)

@login_required
def detail_evaluation_enseignant(request, pk):
    """Détail d'une évaluation pour l'enseignant"""
    evaluation = get_object_or_404(
        Evaluation.objects.prefetch_related('classes', 'compositions__apprenant'),
        pk=pk,
        enseignant=request.user
    )

    # Statistiques de soumission
    compositions = evaluation.compositions.all()
    total_apprenants = sum(classe.apprenants.count() for classe in evaluation.classes.all())

    stats = {
        'total_apprenants': total_apprenants,
        'soumises': compositions.filter(statut__in=['SOUMISE', 'EN_RETARD']).count(),
        'corrigees': compositions.filter(statut='CORRIGEE').count(),
        'en_cours': compositions.filter(statut='EN_COURS').count(),
        'taux_soumission': evaluation.taux_soumission,
        'taux_correction': evaluation.taux_correction,
    }

    # Statistiques de notes (si corrigées)
    notes_stats = None
    if compositions.filter(statut='CORRIGEE').exists():
        notes = Note.objects.filter(evaluation=evaluation)
        notes_stats = {
            'moyenne': notes.aggregate(Avg('valeur'))['valeur__avg'] or 0,
            'max': notes.aggregate(models.Max('valeur'))['valeur__max'] or 0,
            'min': notes.aggregate(models.Min('valeur'))['valeur__min'] or 0,
        }

    context = {
        'evaluation': evaluation,
        'compositions': compositions,
        'stats': stats,
        'notes_stats': notes_stats,
    }

    return render(request, 'evaluations/evaluation/detail.html', context)

@login_required
def corriger_composition(request, pk):
    """Corriger une composition"""
    composition = get_object_or_404(
        Composition.objects.select_related('evaluation', 'apprenant'),
        pk=pk,
        evaluation__enseignant=request.user
    )

    if request.method == 'POST':
        try:
            note_obtenue = Decimal(request.POST.get('note_obtenue'))

            # Vérifier que la note ne dépasse pas la note maximale
            if note_obtenue > composition.evaluation.note_maximale:
                messages.error(request, f"La note ne peut pas dépasser {composition.evaluation.note_maximale}")
                return redirect('evaluations:corriger_composition', pk=pk)

            # Mettre à jour la composition
            composition.note_obtenue = note_obtenue
            composition.commentaire_correction = request.POST.get('commentaire_correction')
            composition.statut = 'CORRIGEE'
            composition.corrigee_par = request.user
            composition.date_correction = timezone.now()

            # Gérer le fichier de correction personnalisé
            if 'fichier_correction' in request.FILES:
                composition.fichier_correction_personnalise = request.FILES['fichier_correction']

            composition.save()

            # Créer ou mettre à jour la note
            note, created = Note.objects.update_or_create(
                apprenant=composition.apprenant,
                evaluation=composition.evaluation,
                defaults={
                    'matiere': composition.evaluation.matiere,
                    'composition': composition,
                    'valeur': composition.note_avec_penalite or note_obtenue,
                    'note_sur': composition.evaluation.note_maximale,
                    'attribuee_par': request.user,
                    'commentaire': composition.commentaire_correction,
                }
            )

            messages.success(request, "Composition corrigée avec succès")
            return redirect('evaluations:detail_enseignant', pk=composition.evaluation.pk)

        except Exception as e:
            messages.error(request, f"Erreur lors de la correction: {str(e)}")

    context = {
        'composition': composition,
        'fichiers': composition.fichiers_composition.all(),
    }

    return render(request, 'evaluations/composition/corriger.html', context)

@login_required
def correction_en_masse(request, pk):
    """Correction en masse des compositions"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    if request.method == 'POST':
        try:
            compositions_data = request.POST.getlist('compositions')
            for comp_data in compositions_data:
                comp_id, note = comp_data.split(':')
                composition = Composition.objects.get(id=comp_id, evaluation=evaluation)

                composition.note_obtenue = Decimal(note)
                composition.statut = 'CORRIGEE'
                composition.corrigee_par = request.user
                composition.date_correction = timezone.now()
                composition.save()

                # Créer la note
                Note.objects.update_or_create(
                    apprenant=composition.apprenant,
                    evaluation=evaluation,
                    defaults={
                        'matiere': evaluation.matiere,
                        'composition': composition,
                        'valeur': composition.note_avec_penalite or composition.note_obtenue,
                        'note_sur': evaluation.note_maximale,
                        'attribuee_par': request.user,
                    }
                )

            messages.success(request, "Corrections enregistrées avec succès")
            return redirect('evaluations:detail_enseignant', pk=pk)

        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")

    compositions = evaluation.compositions.filter(statut__in=['SOUMISE', 'EN_RETARD']).select_related('apprenant')

    context = {
        'evaluation': evaluation,
        'compositions': compositions,
    }

    return render(request, 'evaluations/composition/correction_masse.html', context)


@login_required
@role_required(['ENSEIGNANT'])
def modifier_evaluation(request, pk):
    """Modifier une évaluation existante"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    # Vérifier que l'évaluation peut être modifiée
    if evaluation.statut in ['EN_COURS', 'TERMINEE']:
        messages.error(
            request,
            'Impossible de modifier une évaluation en cours ou terminée.'
        )
        return redirect('evaluations:detail_enseignant', pk=pk)

    if request.method == 'POST':
        form = EvaluationForm(
            request.POST,
            request.FILES,
            instance=evaluation,
            user=request.user
        )
        if form.is_valid():
            try:
                with transaction.atomic():
                    evaluation = form.save()
                    messages.success(
                        request,
                        f'Évaluation "{evaluation.titre}" modifiée avec succès.'
                    )
                    return redirect('evaluations:evaluation_detail_enseignant', pk=pk)
            except Exception as e:
                messages.error(request, f'Erreur lors de la modification: {str(e)}')
    else:
        form = EvaluationForm(instance=evaluation, user=request.user)

    return render(request, 'evaluations/enseignant/edit.html', {
        'form': form,
        'evaluation': evaluation
    })

@login_required
@role_required(['ENSEIGNANT'])
def publier_correction(request, pk):
    """Publier la correction d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    if request.method == 'POST':
        form = PublierCorrectionForm(request.POST, request.FILES, instance=evaluation)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Correction publiée avec succès.')
                return redirect('evaluations:evaluation_detail_enseignant', pk=pk)
            except Exception as e:
                messages.error(request, f'Erreur lors de la publication: {str(e)}')
    else:
        form = PublierCorrectionForm(instance=evaluation)

    return render(request, 'evaluations/enseignant/publier_correction.html', {
        'form': form,
        'evaluation': evaluation
    })

@login_required
@role_required(['ENSEIGNANT'])
@enseignant_owns_evaluation
def supprimer_evaluation(request, pk):
    """Supprimer une évaluation (si possible)"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    # Vérifier que l'évaluation peut être supprimée
    if evaluation.statut in ['EN_COURS', 'TERMINEE']:
        messages.error(
            request,
            'Impossible de supprimer une évaluation en cours ou terminée.'
        )
        return redirect('evaluations:detail_enseignant', pk=pk)

    if evaluation.compositions.exists():
        messages.error(
            request,
            'Impossible de supprimer une évaluation qui a des compositions.'
        )
        return redirect('evaluations:detail_enseignant', pk=pk)

    if request.method == 'POST':
        titre = evaluation.titre
        try:
            with transaction.atomic():
                evaluation.delete()
                messages.success(request, f'Évaluation "{titre}" supprimée avec succès.')
                return redirect('evaluations:list_enseignant')
        except Exception as e:
            messages.error(request, f'Erreur lors de la suppression: {str(e)}')
            return redirect('evaluations:detail_enseignant', pk=pk)

    return render(request, 'evaluations/enseignant/confirm_delete.html', {
        'evaluation': evaluation
    })

@login_required
@role_required(['ENSEIGNANT'])
#@enseignant_owns_evaluation
def statistiques_evaluation(request, pk):
    """Statistiques détaillées d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    # Statistiques avancées
    stats = EvaluationUtils.obtenir_statistiques_detaillees(evaluation)

    # Graphiques et analyses
    analyses = EvaluationUtils.generer_analyses_statistiques(evaluation)

    return render(request, 'evaluations/enseignant/statistiques.html', {
        'evaluation': evaluation,
        'stats': stats,
        'analyses': analyses
    })


# ============ VUES APPRENANT ============
@login_required
def evaluations_apprenant(request):
    """Liste des évaluations pour l'apprenant"""
    if request.user.role != 'APPRENANT':
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    # Récupérer la classe de l'apprenant
    classe = None
    if hasattr(request.user, 'profil_apprenant') and request.user.profil_apprenant.classe_actuelle:
        classe = request.user.profil_apprenant.classe_actuelle

    if not classe:
        messages.warning(request, "Vous n'êtes pas inscrit dans une classe")
        return render(request, 'evaluations/apprenant/list.html', {'evaluations': []})

    # Évaluations de la classe
    evaluations = Evaluation.objects.filter(
        classes=classe,
        statut__in=['PROGRAMMEE', 'EN_COURS', 'TERMINEE']
    ).select_related('matiere', 'enseignant').order_by('-date_debut')

    # Ajouter les informations de composition pour chaque évaluation
    for evaluation in evaluations:
        try:
            evaluation.ma_composition = Composition.objects.get(
                evaluation=evaluation,
                apprenant=request.user
            )
        except Composition.DoesNotExist:
            evaluation.ma_composition = None

    # Filtrer par statut
    filtre_statut = request.GET.get('statut')
    if filtre_statut == 'a_faire':
        evaluations = [e for e in evaluations if not e.ma_composition or e.ma_composition.statut == 'EN_COURS']
    elif filtre_statut == 'soumises':
        evaluations = [e for e in evaluations if
                       e.ma_composition and e.ma_composition.statut in ['SOUMISE', 'EN_RETARD']]
    elif filtre_statut == 'corrigees':
        evaluations = [e for e in evaluations if e.ma_composition and e.ma_composition.statut == 'CORRIGEE']

    context = {
        'evaluations': evaluations,
    }

    return render(request, 'evaluations/apprenant/list.html', context)

@login_required
def detail_evaluation_apprenant(request, pk):
    """Détail d'une évaluation pour l'apprenant"""
    if request.user.role != 'APPRENANT':
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    evaluation = get_object_or_404(Evaluation, pk=pk)

    # Vérifier que l'apprenant est dans une des classes concernées
    classe = None
    if hasattr(request.user, 'profil_apprenant') and request.user.profil_apprenant.classe_actuelle:
        classe = request.user.profil_apprenant.classe_actuelle

    if classe not in evaluation.classes.all():
        messages.error(request, "Vous n'avez pas accès à cette évaluation")
        return redirect('evaluations:list_apprenant')

    # Récupérer ou créer la composition
    composition, created = Composition.objects.get_or_create(
        evaluation=evaluation,
        apprenant=request.user
    )

    # Récupérer la note si elle existe
    try:
        note = Note.objects.get(evaluation=evaluation, apprenant=request.user)
    except Note.DoesNotExist:
        note = None

    context = {
        'evaluation': evaluation,
        'composition': composition,
        'note': note,
        'fichiers': composition.fichiers_composition.all() if composition else [],
    }

    return render(request, 'evaluations/apprenant/detail.html', context)

@login_required
def upload_composition(request, pk):
    """Uploader un fichier de composition"""
    if request.user.role != 'APPRENANT':
        return JsonResponse({'success': False, 'error': 'Non autorisé'})

    evaluation = get_object_or_404(Evaluation, pk=pk)

    # Récupérer la composition
    composition, created = Composition.objects.get_or_create(
        evaluation=evaluation,
        apprenant=request.user
    )

    if not composition.peut_soumettre:
        return JsonResponse({'success': False, 'error': 'Vous ne pouvez plus soumettre'})

    if request.method == 'POST' and request.FILES.get('fichier'):
        try:
            fichier = request.FILES['fichier']

            # Créer le fichier de composition
            fichier_comp = FichierComposition.objects.create(
                nom_original=fichier.name,
                fichier=fichier,
                taille=fichier.size,
                type_mime=fichier.content_type,
                uploade_par=request.user
            )

            # Lier à la composition
            composition.fichiers_composition.add(fichier_comp)

            return JsonResponse({
                'success': True,
                'fichier': {
                    'id': fichier_comp.id,
                    'nom': fichier_comp.nom_original,
                    'taille': fichier_comp.taille,
                }
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Aucun fichier'})

@login_required
def soumettre_composition(request, pk):
    """Soumettre la composition"""
    if request.user.role != 'APPRENANT':
        return JsonResponse({'success': False, 'error': 'Non autorisé'})

    evaluation = get_object_or_404(Evaluation, pk=pk)

    try:
        composition = Composition.objects.get(
            evaluation=evaluation,
            apprenant=request.user
        )

        if not composition.peut_soumettre:
            return JsonResponse({'success': False, 'error': 'Vous ne pouvez plus soumettre'})

        if not composition.fichiers_composition.exists():
            return JsonResponse({'success': False, 'error': 'Vous devez uploader au moins un fichier'})

        composition.soumettre()

        return JsonResponse({
            'success': True,
            'message': 'Composition soumise avec succès',
            'statut': composition.get_statut_display()
        })

    except Composition.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Composition introuvable'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def mes_notes(request):
    """Voir toutes mes notes"""
    if request.user.role != 'APPRENANT':
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    notes = Note.objects.filter(
        apprenant=request.user
    ).select_related('evaluation__matiere', 'evaluation').order_by('-date_attribution')

    # Calculer les moyennes par matière
    moyennes_matieres = {}
    for note in notes:
        matiere_id = note.matiere.id
        if matiere_id not in moyennes_matieres:
            moyennes_matieres[matiere_id] = {
                'matiere': note.matiere,
                'notes': [],
                'total_coefficient': Decimal('0'),
                'somme_ponderee': Decimal('0'),
            }

        moyennes_matieres[matiere_id]['notes'].append(note)
        moyennes_matieres[matiere_id]['total_coefficient'] += note.coefficient_pondere
        moyennes_matieres[matiere_id]['somme_ponderee'] += note.note_sur_20 * note.coefficient_pondere

    # Calculer les moyennes
    for data in moyennes_matieres.values():
        if data['total_coefficient'] > 0:
            data['moyenne'] = data['somme_ponderee'] / data['total_coefficient']
        else:
            data['moyenne'] = 0

    # Moyenne générale
    moyenne_generale = 0
    if moyennes_matieres:
        total_coef = sum(d['total_coefficient'] for d in moyennes_matieres.values())
        if total_coef > 0:
            somme_ponderee_generale = sum(d['somme_ponderee'] for d in moyennes_matieres.values())
            moyenne_generale = somme_ponderee_generale / total_coef

    context = {
        'notes': notes,
        'moyennes_matieres': moyennes_matieres.values(),
        'moyenne_generale': round(float(moyenne_generale), 2),
    }

    return render(request, 'evaluations/apprenant/mes_notes.html', context)


@login_required
@role_required(['APPRENANT'])
@require_POST
def supprimer_fichier_composition(request, pk):
    """Supprimer un fichier de composition via AJAX"""
    fichier_composition = get_object_or_404(
        FichierComposition,
        pk=pk,
        uploade_par=request.user
    )

    # Vérifier que la composition peut encore être modifiée
    compositions = fichier_composition.compositions.filter(apprenant=request.user)
    for composition in compositions:
        if not composition.peut_soumettre:
            return JsonResponse({
                'success': False,
                'error': 'Vous ne pouvez plus modifier cette composition.'
            })

    try:
        nom_fichier = fichier_composition.nom_original
        with transaction.atomic():
            fichier_composition.delete()

        return JsonResponse({
            'success': True,
            'message': f'Fichier "{nom_fichier}" supprimé avec succès.'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de la suppression: {str(e)}'
        })


# ============ GESTION DES NOTES ============
@login_required
def creer_note(request, composition_id):
    """Créer une note pour une composition"""
    composition = get_object_or_404(
        Composition,
        pk=composition_id,
        evaluation__enseignant=request.user
    )

    if request.method == 'POST':
        try:
            valeur = Decimal(request.POST.get('valeur'))

            note, created = Note.objects.update_or_create(
                apprenant=composition.apprenant,
                evaluation=composition.evaluation,
                defaults={
                    'matiere': composition.evaluation.matiere,
                    'composition': composition,
                    'valeur': valeur,
                    'note_sur': composition.evaluation.note_maximale,
                    'attribuee_par': request.user,
                    'commentaire': request.POST.get('commentaire', ''),
                }
            )

            # Mettre à jour la composition
            composition.note_obtenue = valeur
            composition.statut = 'CORRIGEE'
            composition.corrigee_par = request.user
            composition.date_correction = timezone.now()
            composition.save()

            messages.success(request, 'Note enregistrée avec succès')
            return redirect('evaluations:detail_enseignant', pk=composition.evaluation.pk)

        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')

    return render(request, 'evaluations/note/form.html', {
        'composition': composition
    })

@login_required
def modifier_note(request, pk):
    """Modifier une note existante"""
    note = get_object_or_404(Note, pk=pk, attribuee_par=request.user)

    if request.method == 'POST':
        try:
            note.valeur = Decimal(request.POST.get('valeur'))
            note.commentaire = request.POST.get('commentaire', '')
            note.save()

            # Mettre à jour la composition
            if note.composition:
                note.composition.note_obtenue = note.valeur
                note.composition.save()

            messages.success(request, 'Note modifiée avec succès')
            return redirect('evaluations:detail_enseignant', pk=note.evaluation.pk)

        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')

    return render(request, 'evaluations/note/edit.html', {'note': note})

@login_required
@require_POST
def supprimer_note(request, pk):
    """Supprimer une note"""
    note = get_object_or_404(Note, pk=pk, attribuee_par=request.user)
    evaluation_id = note.evaluation.pk

    try:
        note.delete()
        messages.success(request, 'Note supprimée')
    except Exception as e:
        messages.error(request, f'Erreur: {str(e)}')

    return redirect('evaluations:detail_enseignant', pk=evaluation_id)


# ============ IMPORT/EXPORT NOTES ============
@login_required
def importer_notes(request, pk):
    """Importer des notes depuis un fichier CSV"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    if request.method == 'POST' and request.FILES.get('fichier_csv'):
        try:
            fichier = request.FILES['fichier_csv']
            decoded_file = fichier.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)

            notes_creees = 0
            erreurs = []

            with transaction.atomic():
                for row in reader:
                    try:
                        matricule = row.get('matricule')
                        valeur = Decimal(row.get('note'))
                        commentaire = row.get('commentaire', '')

                        apprenant = get_object_or_404(
                            Utilisateur,
                            matricule=matricule,
                            role='APPRENANT'
                        )

                        composition = Composition.objects.get(
                            evaluation=evaluation,
                            apprenant=apprenant
                        )

                        note, created = Note.objects.update_or_create(
                            apprenant=apprenant,
                            evaluation=evaluation,
                            defaults={
                                'matiere': evaluation.matiere,
                                'composition': composition,
                                'valeur': valeur,
                                'note_sur': evaluation.note_maximale,
                                'attribuee_par': request.user,
                                'commentaire': commentaire,
                            }
                        )

                        composition.note_obtenue = valeur
                        composition.statut = 'CORRIGEE'
                        composition.corrigee_par = request.user
                        composition.date_correction = timezone.now()
                        composition.save()

                        notes_creees += 1

                    except Exception as e:
                        erreurs.append(f"Ligne {reader.line_num}: {str(e)}")

            if erreurs:
                for err in erreurs[:5]:
                    messages.warning(request, err)

            messages.success(request, f'{notes_creees} notes importées')
            return redirect('evaluations:detail_enseignant', pk=pk)

        except Exception as e:
            messages.error(request, f'Erreur lors de l\'importation: {str(e)}')

    return render(request, 'evaluations/note/import.html', {
        'evaluation': evaluation
    })

@login_required
def exporter_notes(request, pk):
    """Exporter les notes en CSV"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="notes_{evaluation.titre}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Matricule', 'Nom', 'Prénom', 'Note', 'Commentaire', 'Date'])

    notes = Note.objects.filter(evaluation=evaluation).select_related('apprenant')
    for note in notes:
        writer.writerow([
            note.apprenant.matricule,
            note.apprenant.nom,
            note.apprenant.prenom,
            note.valeur,
            note.commentaire,
            note.date_attribution.strftime('%d/%m/%Y')
        ])

    return response


# ============ RAPPORTS ET STATISTIQUES ============
@login_required
def rapport_evaluation(request, pk):
    """Rapport détaillé d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    compositions = evaluation.compositions.select_related('apprenant')
    notes = Note.objects.filter(evaluation=evaluation)

    stats = {
        'total_apprenants': sum(c.etudiants.count() for c in evaluation.classes.all()),
        'compositions_soumises': compositions.filter(statut__in=['SOUMISE', 'EN_RETARD']).count(),
        'compositions_corrigees': compositions.filter(statut='CORRIGEE').count(),
        'moyenne': notes.aggregate(Avg('valeur'))['valeur__avg'] or 0,
        'note_max': notes.aggregate(Max('valeur'))['valeur__max'] or 0,
        'note_min': notes.aggregate(Min('valeur'))['valeur__min'] or 0,
    }

    # Distribution des notes
    distribution = {
        'excellent': notes.filter(valeur__gte=16).count(),
        'bien': notes.filter(valeur__gte=14, valeur__lt=16).count(),
        'assez_bien': notes.filter(valeur__gte=12, valeur__lt=14).count(),
        'passable': notes.filter(valeur__gte=10, valeur__lt=12).count(),
        'insuffisant': notes.filter(valeur__lt=10).count(),
    }

    return render(request, 'evaluations/rapport.html', {
        'evaluation': evaluation,
        'stats': stats,
        'distribution': distribution,
        'compositions': compositions,
    })

@login_required
def statistiques_enseignant(request):
    """Statistiques globales pour un enseignant"""
    enseignant = request.user

    evaluations = Evaluation.objects.filter(enseignant=enseignant)

    stats = {
        'total_evaluations': evaluations.count(),
        'en_cours': evaluations.filter(statut='EN_COURS').count(),
        'terminees': evaluations.filter(statut='TERMINEE').count(),
        'total_corrections': Composition.objects.filter(
            evaluation__enseignant=enseignant,
            statut='CORRIGEE'
        ).count(),
    }

    # Statistiques par matière
    stats_matieres = []
    matieres = Matiere.objects.filter(enseignant_responsable=enseignant)
    for matiere in matieres:
        evals = evaluations.filter(matiere=matiere)
        notes = Note.objects.filter(evaluation__in=evals)

        stats_matieres.append({
            'matiere': matiere,
            'nb_evaluations': evals.count(),
            'moyenne': notes.aggregate(Avg('valeur'))['valeur__avg'] or 0,
        })

    return render(request, 'evaluations/enseignant/statistiques_globales.html', {
        'stats': stats,
        'stats_matieres': stats_matieres,
    })

@login_required
def bulletin_apprenant(request, apprenant_id):
    """Bulletin de notes d'un apprenant"""
    apprenant = get_object_or_404(Utilisateur, pk=apprenant_id, role='APPRENANT')

    # Vérifier les permissions
    if request.user.role == 'APPRENANT' and request.user.pk != apprenant_id:
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    notes = Note.objects.filter(apprenant=apprenant).select_related(
        'matiere', 'evaluation'
    ).order_by('matiere', '-date_attribution')

    # Calculer les moyennes par matière
    moyennes_matieres = {}
    for note in notes:
        matiere_id = note.matiere.id
        if matiere_id not in moyennes_matieres:
            moyennes_matieres[matiere_id] = {
                'matiere': note.matiere,
                'notes': [],
                'total_coef': Decimal('0'),
                'somme_ponderee': Decimal('0'),
            }

        moyennes_matieres[matiere_id]['notes'].append(note)
        moyennes_matieres[matiere_id]['total_coef'] += note.coefficient_pondere
        moyennes_matieres[matiere_id]['somme_ponderee'] += note.note_sur_20 * note.coefficient_pondere

    # Calculer les moyennes
    for data in moyennes_matieres.values():
        if data['total_coef'] > 0:
            data['moyenne'] = data['somme_ponderee'] / data['total_coef']
        else:
            data['moyenne'] = 0

    # Moyenne générale
    total_coef = sum(d['total_coef'] for d in moyennes_matieres.values())
    somme_ponderee = sum(d['somme_ponderee'] for d in moyennes_matieres.values())
    moyenne_generale = somme_ponderee / total_coef if total_coef > 0 else 0

    return render(request, 'evaluations/bulletin.html', {
        'apprenant': apprenant,
        'moyennes_matieres': moyennes_matieres.values(),
        'moyenne_generale': round(float(moyenne_generale), 2),
    })


# ============ ACTIONS EN MASSE ============
@login_required
@require_POST
def actions_masse_evaluations(request):
    """Actions en masse sur plusieurs évaluations"""
    action = request.POST.get('action')
    eval_ids = request.POST.getlist('evaluations')

    evaluations = Evaluation.objects.filter(
        id__in=eval_ids,
        enseignant=request.user
    )

    if action == 'changer_statut':
        nouveau_statut = request.POST.get('nouveau_statut')
        evaluations.update(statut=nouveau_statut)
        messages.success(request, f'{evaluations.count()} évaluations mises à jour')

    elif action == 'supprimer':
        count = evaluations.filter(
            statut='BROUILLON',
            compositions__isnull=True
        ).count()
        evaluations.filter(
            statut='BROUILLON',
            compositions__isnull=True
        ).delete()
        messages.success(request, f'{count} évaluations supprimées')

    return redirect('evaluations:list_enseignant')


# ============ UTILITAIRES ============
def format_time(seconds):
    """Formate un temps en secondes"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# ============ VUES API AJAX ============
@login_required
def api_temps_restant(request, pk):
    """Retourne le temps restant pour une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk)

    now = timezone.now()
    if now < evaluation.date_debut:
        status = 'not_started'
        time_left = (evaluation.date_debut - now).total_seconds()
    elif now > evaluation.date_fin:
        status = 'finished'
        time_left = 0
    else:
        status = 'in_progress'
        time_left = (evaluation.date_fin - now).total_seconds()

    return JsonResponse({
        'status': status,
        'time_left': int(time_left),
        'formatted_time': format_time(time_left)
    })

@login_required
def api_statistiques_evaluation(request, pk):
    """Retourne les statistiques détaillées d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    compositions = evaluation.compositions.all()
    notes = Note.objects.filter(evaluation=evaluation)

    stats = {
        'total_compositions': compositions.count(),
        'soumises': compositions.filter(statut__in=['SOUMISE', 'EN_RETARD']).count(),
        'corrigees': compositions.filter(statut='CORRIGEE').count(),
        'moyenne': float(notes.aggregate(Avg('valeur'))['valeur__avg'] or 0),
        'note_max': float(notes.aggregate(Max('valeur'))['valeur__max'] or 0),
        'note_min': float(notes.aggregate(Min('valeur'))['valeur__min'] or 0),
    }

    return JsonResponse(stats)


@login_required
@require_POST
def api_mettre_a_jour_statut(request, pk):
    """Met à jour le statut d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    data = json.loads(request.body)
    nouveau_statut = data.get('statut')

    if nouveau_statut in dict(Evaluation.STATUT).keys():
        evaluation.statut = nouveau_statut
        evaluation.save()
        return JsonResponse({'success': True, 'message': 'Statut mis à jour'})

    return JsonResponse({'success': False, 'error': 'Statut invalide'}, status=400)



@login_required
def telecharger_fichier_evaluation(request, pk):
    """Télécharger le fichier d'évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk)

    # Vérifier les droits d'accès
    if request.user.role == 'ENSEIGNANT' and evaluation.enseignant != request.user:
        messages.error(request, "Accès non autorisé")
        return redirect('evaluations:list_enseignant')

    if request.user.role == 'APPRENANT':
        classe = request.user.profil_apprenant.classe_actuelle if hasattr(request.user, 'profil_apprenant') else None
        if classe not in evaluation.classes.all():
            messages.error(request, "Accès non autorisé")
            return redirect('evaluations:list_apprenant')

    if not evaluation.fichier_evaluation:
        messages.error(request, "Aucun fichier disponible")
        return redirect(
            'evaluations:detail_enseignant' if request.user.role == 'ENSEIGNANT' else 'evaluations:detail_apprenant',
            pk=pk)

    return FileResponse(evaluation.fichier_evaluation.open('rb'), as_attachment=True)

@login_required
def voir_fichier(request, type_fichier, pk):
    """Visualiser un fichier dans le navigateur"""
    if type_fichier == 'evaluation':
        obj = get_object_or_404(Evaluation, pk=pk)
        fichier = obj.fichier_evaluation
    elif type_fichier == 'correction':
        obj = get_object_or_404(Evaluation, pk=pk)
        fichier = obj.fichier_correction
    elif type_fichier == 'composition':
        obj = get_object_or_404(FichierComposition, pk=pk)
        fichier = obj.fichier
    else:
        return HttpResponse("Type de fichier invalide", status=400)

    if not fichier:
        return HttpResponse("Fichier non trouvé", status=404)

    # Déterminer le type MIME
    content_type, _ = mimetypes.guess_type(fichier.name)

    response = FileResponse(fichier.open('rb'), content_type=content_type)
    response['Content-Disposition'] = 'inline'

    return response

@login_required
def supprimer_fichier_composition(request, pk):
    """Supprimer un fichier de composition"""
    if request.user.role != 'APPRENANT':
        return JsonResponse({'success': False, 'error': 'Non autorisé'})

    fichier = get_object_or_404(FichierComposition, pk=pk, uploade_par=request.user)

    try:
        # Vérifier que la composition n'est pas encore soumise
        composition = fichier.compositions.first()
        if composition and composition.statut in ['SOUMISE', 'EN_RETARD', 'CORRIGEE']:
            return JsonResponse({'success': False, 'error': 'Impossible de supprimer après soumission'})

        fichier.delete()
        return JsonResponse({'success': True, 'message': 'Fichier supprimé'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def telecharger_fichier_correction(request, pk):
    """Télécharger le fichier de correction"""
    evaluation = get_object_or_404(Evaluation, pk=pk)

    # Vérifier les droits d'accès
    if request.user.role == 'ENSEIGNANT' and evaluation.enseignant != request.user:
        messages.error(request, "Accès non autorisé")
        return redirect('evaluations:list_enseignant')

    if request.user.role == 'APPRENANT':
        classe = request.user.profil_apprenant.classe_actuelle if hasattr(request.user, 'profil_apprenant') else None
        if classe not in evaluation.classes.all():
            messages.error(request, "Accès non autorisé")
            return redirect('evaluations:list_apprenant')

        # Vérifier que la correction est visible
        if not evaluation.correction_visible:
            messages.error(request, "La correction n'est pas encore disponible")
            return redirect('evaluations:detail_apprenant', pk=pk)

    if not evaluation.fichier_correction:
        messages.error(request, "Aucun fichier de correction disponible")
        return redirect(
            'evaluations:detail_enseignant' if request.user.role == 'ENSEIGNANT' else 'evaluations:detail_apprenant',
            pk=pk)

    return FileResponse(evaluation.fichier_correction.open('rb'), as_attachment=True)

@login_required
def telecharger_fichier_composition(request, pk):
    """Télécharger un fichier de composition"""
    fichier = get_object_or_404(FichierComposition, pk=pk)

    # Vérifier les droits
    composition = fichier.compositions.first()
    if not composition:
        messages.error(request, "Composition introuvable")
        return redirect('evaluations:list_apprenant')

    if request.user.role == 'APPRENANT':
        if composition.apprenant != request.user:
            messages.error(request, "Accès non autorisé")
            return redirect('evaluations:list_apprenant')
    elif request.user.role == 'ENSEIGNANT':
        if composition.evaluation.enseignant != request.user:
            messages.error(request, "Accès non autorisé")
            return redirect('evaluations:list_enseignant')

    return FileResponse(fichier.fichier.open('rb'), as_attachment=True)


