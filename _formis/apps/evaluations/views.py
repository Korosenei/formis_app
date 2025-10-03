from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404, HttpResponseRedirect
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from django.urls import reverse, reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.core.exceptions import PermissionDenied
import json
import mimetypes
import os
import csv
from io import TextIOWrapper

from .models import Evaluation, Composition, FichierComposition, Note, MoyenneModule
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
from apps.academic.models import Classe


# ============ VUES ENSEIGNANT ============

@login_required
@role_required(['ENSEIGNANT'])
def evaluations_enseignant(request):
    """Liste des évaluations créées par l'enseignant avec recherche et pagination"""
    form = EvaluationSearchForm(request.GET, user=request.user)
    evaluations = Evaluation.objects.filter(enseignant=request.user).select_related(
        'matiere_module__matiere', 'matiere_module__module'
    )

    # Filtrage
    if form.is_valid():
        if form.cleaned_data['titre']:
            evaluations = evaluations.filter(titre__icontains=form.cleaned_data['titre'])
        if form.cleaned_data['type_evaluation']:
            evaluations = evaluations.filter(type_evaluation=form.cleaned_data['type_evaluation'])
        if form.cleaned_data['statut']:
            evaluations = evaluations.filter(statut=form.cleaned_data['statut'])
        if form.cleaned_data['matiere']:
            evaluations = evaluations.filter(matiere_module=form.cleaned_data['matiere'])
        if form.cleaned_data['classe']:
            evaluations = evaluations.filter(classes=form.cleaned_data['classe'])
        if form.cleaned_data['date_debut']:
            evaluations = evaluations.filter(date_debut__date__gte=form.cleaned_data['date_debut'])
        if form.cleaned_data['date_fin']:
            evaluations = evaluations.filter(date_fin__date__lte=form.cleaned_data['date_fin'])

    # Annotations pour les statistiques
    evaluations = evaluations.annotate(
        nb_compositions=Count('compositions'),
        nb_corrigees=Count('compositions', filter=Q(compositions__statut='CORRIGEE')),
        nb_en_cours=Count('compositions', filter=Q(compositions__statut='EN_COURS')),
        nb_soumises=Count('compositions', filter=Q(compositions__statut__in=['SOUMISE', 'EN_RETARD']))
    ).order_by('-date_creation')

    # Statistiques générales
    stats_generales = {
        'total': evaluations.count(),
        'brouillons': evaluations.filter(statut='BROUILLON').count(),
        'programmees': evaluations.filter(statut='PROGRAMMEE').count(),
        'en_cours': evaluations.filter(statut='EN_COURS').count(),
        'terminees': evaluations.filter(statut='TERMINEE').count(),
    }

    # Pagination
    paginator = Paginator(evaluations, 12)
    page = request.GET.get('page')
    evaluations = paginator.get_page(page)

    return render(request, 'evaluations/enseignant/list.html', {
        'evaluations': evaluations,
        'form': form,
        'stats_generales': stats_generales
    })

@login_required
@role_required(['ENSEIGNANT'])
def creer_evaluation(request):
    """Créer une nouvelle évaluation"""
    if request.method == 'POST':
        form = EvaluationForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    evaluation = form.save(commit=False)
                    evaluation.enseignant = request.user
                    evaluation.save()
                    form.save_m2m()  # Pour les classes (ManyToMany)

                    messages.success(
                        request,
                        f'Évaluation "{evaluation.titre}" créée avec succès.'
                    )

                    # Rediriger selon le choix de l'utilisateur
                    if 'save_and_continue' in request.POST:
                        return redirect('evaluations:edit', pk=evaluation.pk)
                    elif 'save_and_new' in request.POST:
                        return redirect('evaluations:create')
                    else:
                        return redirect('evaluations:detail_enseignant', pk=evaluation.pk)
            except Exception as e:
                messages.error(request, f'Erreur lors de la création: {str(e)}')
    else:
        form = EvaluationForm(user=request.user)

    return render(request, 'evaluations/enseignant/create.html', {
        'form': form
    })

@login_required
@role_required(['ENSEIGNANT'])
@enseignant_owns_evaluation
def detail_evaluation_enseignant(request, pk):
    """Détail d'une évaluation pour l'enseignant avec statistiques"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    # Mettre à jour le statut automatiquement
    EvaluationUtils.mettre_a_jour_statut_evaluation(evaluation)

    # Récupérer les compositions avec données associées
    compositions = evaluation.compositions.select_related(
        'apprenant__classe'
    ).prefetch_related(
        'fichiers_composition', 'note'
    ).order_by('apprenant__last_name', 'apprenant__first_name')

    # Statistiques détaillées
    stats = EvaluationUtils.obtenir_statistiques_evaluation(evaluation)
    temps_restant = EvaluationUtils.obtenir_temps_restant(evaluation)

    # Statistiques par classe
    stats_par_classe = {}
    for classe in evaluation.classes.all():
        compositions_classe = compositions.filter(apprenant__classe=classe)
        if compositions_classe.exists():
            notes_classe = [
                comp.note_obtenue for comp in compositions_classe
                if comp.note_obtenue is not None
            ]
            stats_par_classe[classe.nom] = {
                'total_apprenants': compositions_classe.count(),
                'compositions_soumises': compositions_classe.filter(
                    statut__in=['SOUMISE', 'EN_RETARD', 'CORRIGEE']
                ).count(),
                'compositions_corrigees': compositions_classe.filter(
                    statut='CORRIGEE'
                ).count(),
                'moyenne_classe': sum(notes_classe) / len(notes_classe) if notes_classe else None,
                'nb_notes': len(notes_classe)
            }

    # Formulaires pour actions rapides
    bulk_note_form = None
    if evaluation.statut == 'TERMINEE':
        compositions_non_corrigees = compositions.filter(
            statut__in=['SOUMISE', 'EN_RETARD']
        )
        if compositions_non_corrigees.exists():
            bulk_note_form = BulkNoteForm(
                compositions=compositions_non_corrigees,
                evaluation=evaluation
            )

    return render(request, 'evaluations/enseignant/detail.html', {
        'evaluation': evaluation,
        'compositions': compositions,
        'stats': stats,
        'stats_par_classe': stats_par_classe,
        'temps_restant': temps_restant,
        'bulk_note_form': bulk_note_form
    })

@login_required
@role_required(['ENSEIGNANT'])
@enseignant_owns_evaluation
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
                    return redirect('evaluations:detail_enseignant', pk=pk)
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
@enseignant_owns_evaluation
def corriger_composition(request, pk):
    """Corriger une composition individuelle"""
    composition = get_object_or_404(
        Composition,
        pk=pk,
        evaluation__enseignant=request.user,
        statut__in=['SOUMISE', 'EN_RETARD']
    )

    if request.method == 'POST':
        correction_form = CorrectionForm(request.POST, request.FILES, instance=composition)
        note_form = NoteForm(request.POST, evaluation=composition.evaluation)

        if correction_form.is_valid() and note_form.is_valid():
            try:
                with transaction.atomic():
                    # Sauvegarder la correction
                    composition = correction_form.save(commit=False)
                    composition.statut = 'CORRIGEE'
                    composition.corrigee_par = request.user
                    composition.date_correction = timezone.now()
                    composition.save()

                    # Sauvegarder ou mettre à jour la note
                    note, created = Note.objects.update_or_create(
                        apprenant=composition.apprenant,
                        evaluation=composition.evaluation,
                        defaults={
                            'matiere_module': composition.evaluation.matiere_module,
                            'composition': composition,
                            'valeur': note_form.cleaned_data['valeur'],
                            'note_sur': note_form.cleaned_data['note_sur'],
                            'commentaire': note_form.cleaned_data['commentaire'],
                            'attribuee_par': request.user
                        }
                    )

                    # Mettre à jour la note dans la composition
                    composition.note_obtenue = note.valeur
                    composition.save()

                    # Mettre à jour les moyennes
                    try:
                        annee_academique = AnneeAcademique.objects.get(active=True)
                        MoyenneCalculator.mettre_a_jour_moyennes_module(
                            composition.apprenant,
                            composition.evaluation.matiere_module.module,
                            annee_academique
                        )
                    except AnneeAcademique.DoesNotExist:
                        pass

                    action = 'créée' if created else 'mise à jour'
                    messages.success(
                        request,
                        f'Composition corrigée et note {action} avec succès.'
                    )

                    # Redirection selon le choix
                    if 'save_and_next' in request.POST:
                        # Trouver la composition suivante à corriger
                        prochaine_composition = Composition.objects.filter(
                            evaluation=composition.evaluation,
                            statut__in=['SOUMISE', 'EN_RETARD'],
                            id__gt=composition.id
                        ).first()

                        if prochaine_composition:
                            return redirect('evaluations:corriger_composition', pk=prochaine_composition.pk)

                    return redirect('evaluations:detail_enseignant', pk=composition.evaluation.pk)

            except Exception as e:
                messages.error(request, f'Erreur lors de la correction: {str(e)}')
    else:
        correction_form = CorrectionForm(instance=composition)

        # Pré-remplir la note si elle existe
        try:
            note_existante = Note.objects.get(
                apprenant=composition.apprenant,
                evaluation=composition.evaluation
            )
            note_form = NoteForm(instance=note_existante, evaluation=composition.evaluation)
        except Note.DoesNotExist:
            note_form = NoteForm(evaluation=composition.evaluation)

    # Informations contextuelles
    context = {
        'composition': composition,
        'correction_form': correction_form,
        'note_form': note_form,
        'evaluation': composition.evaluation,
        'apprenant': composition.apprenant,
        'fichiers_composition': composition.fichiers_composition.all()
    }

    # Ajouter les compositions suivantes pour navigation
    prochaines_compositions = Composition.objects.filter(
        evaluation=composition.evaluation,
        statut__in=['SOUMISE', 'EN_RETARD'],
        id__gt=composition.id
    )[:3]  # Les 3 suivantes
    context['prochaines_compositions'] = prochaines_compositions

    return render(request, 'evaluations/enseignant/corriger.html', context)

@login_required
@role_required(['ENSEIGNANT'])
@enseignant_owns_evaluation
@require_POST
def correction_en_masse(request, pk):
    """Correction en masse des compositions"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    compositions = evaluation.compositions.filter(
        statut__in=['SOUMISE', 'EN_RETARD']
    )

    form = BulkNoteForm(
        request.POST,
        compositions=compositions,
        evaluation=evaluation
    )

    if form.is_valid():
        try:
            with transaction.atomic():
                notes_creees = 0
                notes_modifiees = 0

                for composition in compositions:
                    note_value = form.cleaned_data.get(f'note_{composition.id}')
                    commentaire = form.cleaned_data.get(f'commentaire_{composition.id}')

                    if note_value is not None:
                        # Créer ou mettre à jour la note
                        note, created = Note.objects.update_or_create(
                            apprenant=composition.apprenant,
                            evaluation=evaluation,
                            defaults={
                                'matiere_module': evaluation.matiere_module,
                                'composition': composition,
                                'valeur': note_value,
                                'note_sur': evaluation.note_maximale,
                                'commentaire': commentaire or '',
                                'attribuee_par': request.user
                            }
                        )

                        # Mettre à jour la composition
                        composition.note_obtenue = note_value
                        composition.statut = 'CORRIGEE'
                        composition.corrigee_par = request.user
                        composition.date_correction = timezone.now()
                        composition.save()

                        if created:
                            notes_creees += 1
                        else:
                            notes_modifiees += 1

                # Mettre à jour les moyennes pour tous les apprenants concernés
                try:
                    annee_academique = AnneeAcademique.objects.get(active=True)
                    apprenants = {comp.apprenant for comp in compositions}

                    for apprenant in apprenants:
                        MoyenneCalculator.mettre_a_jour_moyennes_module(
                            apprenant,
                            evaluation.matiere_module.module,
                            annee_academique
                        )
                except AnneeAcademique.DoesNotExist:
                    pass

                messages.success(
                    request,
                    f'Correction en masse terminée: {notes_creees} notes créées, '
                    f'{notes_modifiees} notes modifiées.'
                )

        except Exception as e:
            messages.error(request, f'Erreur lors de la correction en masse: {str(e)}')
    else:
        messages.error(request, 'Erreurs dans le formulaire de correction.')

    return redirect('evaluations:detail_enseignant', pk=pk)

@login_required
@role_required(['ENSEIGNANT'])
@enseignant_owns_evaluation
def publier_correction(request, pk):
    """Publier la correction d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk, enseignant=request.user)

    if request.method == 'POST':
        form = PublierCorrectionForm(request.POST, request.FILES, instance=evaluation)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Correction publiée avec succès.')
                return redirect('evaluations:detail_enseignant', pk=pk)
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
@enseignant_owns_evaluation
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
@role_required(['APPRENANT'])
def evaluations_apprenant(request):
    """Liste des évaluations disponibles pour l'apprenant"""
    try:
        classe_apprenant = request.user.classe
        evaluations_base = Evaluation.objects.filter(
            classes=classe_apprenant,
            statut__in=['PROGRAMMEE', 'EN_COURS', 'TERMINEE']
        ).select_related(
            'matiere_module__matiere', 'matiere_module__module', 'enseignant'
        ).order_by('date_debut')
    except AttributeError:
        evaluations_base = Evaluation.objects.none()
        messages.warning(request, 'Vous n\'êtes assigné à aucune classe.')

    # Filtrage optionnel
    form = EvaluationSearchForm(request.GET, user=request.user)
    if form.is_valid():
        if form.cleaned_data['titre']:
            evaluations_base = evaluations_base.filter(
                titre__icontains=form.cleaned_data['titre']
            )
        if form.cleaned_data['type_evaluation']:
            evaluations_base = evaluations_base.filter(
                type_evaluation=form.cleaned_data['type_evaluation']
            )
        if form.cleaned_data['matiere']:
            evaluations_base = evaluations_base.filter(
                matiere_module=form.cleaned_data['matiere']
            )

    # Ajouter des informations contextuelles
    evaluations_avec_info = []
    for evaluation in evaluations_base:
        disponibilite = EvaluationUtils.verifier_disponibilite_evaluation(
            evaluation, request.user
        )
        temps_restant = EvaluationUtils.obtenir_temps_restant(evaluation)

        # Récupérer la composition de l'apprenant
        try:
            composition = Composition.objects.get(
                evaluation=evaluation,
                apprenant=request.user
            )
        except Composition.DoesNotExist:
            composition = None

        # Note obtenue
        note = None
        if composition and composition.statut == 'CORRIGEE':
            try:
                note = Note.objects.get(
                    apprenant=request.user,
                    evaluation=evaluation
                )
            except Note.DoesNotExist:
                pass

        evaluations_avec_info.append({
            'evaluation': evaluation,
            'disponibilite': disponibilite,
            'temps_restant': temps_restant,
            'composition': composition,
            'note': note,
        })

    # Statistiques personnelles
    stats_personnelles = {
        'total_evaluations': len(evaluations_avec_info),
        'compositions_soumises': sum(1 for e in evaluations_avec_info if
                                     e['composition'] and e['composition'].statut in ['SOUMISE', 'EN_RETARD',
                                                                                      'CORRIGEE']),
        'compositions_corrigees': sum(
            1 for e in evaluations_avec_info if e['composition'] and e['composition'].statut == 'CORRIGEE'),
        'en_cours': sum(1 for e in evaluations_avec_info if e['composition'] and e['composition'].statut == 'EN_COURS'),
    }

    return render(request, 'evaluations/apprenant/list.html', {
        'evaluations_avec_info': evaluations_avec_info,
        'form': form,
        'stats_personnelles': stats_personnelles
    })


@login_required
@role_required(['APPRENANT'])
@apprenant_in_evaluation_classes
def detail_evaluation_apprenant(request, pk):
    """Détail d'une évaluation pour l'apprenant"""
    evaluation = get_object_or_404(Evaluation, pk=pk)

    # Vérifier la disponibilité
    disponibilite = EvaluationUtils.verifier_disponibilite_evaluation(
        evaluation, request.user
    )
    temps_restant = EvaluationUtils.obtenir_temps_restant(evaluation)

    # Récupérer ou créer la composition
    composition, created = Composition.objects.get_or_create(
        evaluation=evaluation,
        apprenant=request.user
    )

    # Récupérer les fichiers de composition
    fichiers_composition = composition.fichiers_composition.all().order_by('-date_creation')

    # Note et correction
    note = None
    if composition.statut == 'CORRIGEE':
        try:
            note = Note.objects.get(
                apprenant=request.user,
                evaluation=evaluation
            )
        except Note.DoesNotExist:
            pass

    context = {
        'evaluation': evaluation,
        'composition': composition,
        'fichiers_composition': fichiers_composition,
        'disponibilite': disponibilite,
        'temps_restant': temps_restant,
        'note': note,
    }

    return render(request, 'evaluations/apprenant/detail.html', context)


@login_required
@role_required(['APPRENANT'])
@apprenant_in_evaluation_classes
@composition_can_be_modified
@require_POST
def upload_composition(request, pk):
    """Upload des fichiers de composition via AJAX"""
    evaluation = get_object_or_404(Evaluation, pk=pk)

    # Vérifier la disponibilité
    disponibilite = EvaluationUtils.verifier_disponibilite_evaluation(
        evaluation, request.user
    )
    if not disponibilite['peut_composer']:
        return JsonResponse({
            'success': False,
            'error': disponibilite['raison']
        })

    # Récupérer la composition
    composition, created = Composition.objects.get_or_create(
        evaluation=evaluation,
        apprenant=request.user
    )

    # Vérifier si la composition peut encore être modifiée
    if not composition.peut_soumettre:
        return JsonResponse({
            'success': False,
            'error': 'Vous ne pouvez plus modifier cette composition.'
        })

    form = CompositionUploadForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            fichiers_uploades = []

            with transaction.atomic():
                for fichier in request.FILES.getlist('fichiers'):
                    # Créer l'objet FichierComposition
                    fichier_composition = FichierComposition(
                        nom_original=fichier.name,
                        fichier=fichier,
                        uploade_par=request.user,
                        type_mime=fichier.content_type or 'application/octet-stream'
                    )
                    fichier_composition.save()

                    # Associer à la composition
                    composition.fichiers_composition.add(fichier_composition)

                    fichiers_uploades.append({
                        'id': fichier_composition.id,
                        'nom': fichier_composition.nom_original,
                        'taille': fichier_composition.taille
                    })

            return JsonResponse({
                'success': True,
                'message': f'{len(fichiers_uploades)} fichier(s) uploadé(s) avec succès.',
                'fichiers': fichiers_uploades
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Erreur lors de l\'upload: {str(e)}'
            })
    else:
        errors = []
        for field, field_errors in form.errors.items():
            errors.extend(field_errors)
        return JsonResponse({
            'success': False,
            'error': ' '.join(errors)
        })


@login_required
@role_required(['APPRENANT'])
@apprenant_in_evaluation_classes
@composition_can_be_modified
@require_POST
def soumettre_composition(request, pk):
    """Soumettre la composition via AJAX"""
    evaluation = get_object_or_404(Evaluation, pk=pk)

    try:
        composition = Composition.objects.get(
            evaluation=evaluation,
            apprenant=request.user
        )
    except Composition.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Aucune composition trouvée'
        })

    # Vérifier si la composition peut être soumise
    if not composition.peut_soumettre:
        return JsonResponse({
            'success': False,
            'error': 'Vous ne pouvez plus soumettre cette composition.'
        })

    # Vérifier qu'il y a au moins un fichier
    if not composition.fichiers_composition.exists():
        return JsonResponse({
            'success': False,
            'error': 'Vous devez uploader au moins un fichier avant de soumettre.'
        })

    try:
        with transaction.atomic():
            # Soumettre la composition
            composition.soumettre()

            return JsonResponse({
                'success': True,
                'message': 'Composition soumise avec succès.',
                'statut': composition.get_statut_display(),
                'date_soumission': composition.date_soumission.isoformat() if composition.date_soumission else None
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de la soumission: {str(e)}'
        })


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


@login_required
@role_required(['APPRENANT'])
def mes_notes(request):
    """Notes de l'apprenant connecté"""
    notes = Note.objects.filter(
        apprenant=request.user
    ).select_related(
        'evaluation', 'evaluation__matiere_module__matiere',
        'evaluation__matiere_module__module'
    ).order_by('-evaluation__date_fin')

    # Calcul des moyennes par module
    modules_notes = {}
    for note in notes:
        module = note.evaluation.matiere_module.module
        if module not in modules_notes:
            modules_notes[module] = []
        modules_notes[module].append(note)

    # Statistiques personnelles
    stats = {
        'total_notes': notes.count(),
        'moyenne_generale': notes.aggregate(Avg('valeur'))['valeur__avg'],
        'meilleure_note': notes.aggregate(Max('valeur'))['valeur__max'],
        'pire_note': notes.aggregate(Min('valeur'))['valeur__min'],
    }

    return render(request, 'evaluations/apprenant/mes_notes.html', {
        'notes': notes,
        'modules_notes': modules_notes,
        'stats': stats
    })


@login_required
@role_required(['ENSEIGNANT', 'ADMINISTRATEUR'])
def moyennes_module(request, module_id):
    """Moyennes des apprenants dans un module"""
    module = get_object_or_404(Module, pk=module_id)

    # Vérifier les permissions
    if request.user.role == 'ENSEIGNANT':
        if not module.enseignants.filter(id=request.user.id).exists():
            raise PermissionDenied

    # Récupérer les moyennes
    moyennes = MoyenneModule.objects.filter(
        module=module
    ).select_related('apprenant').order_by('-valeur')

    # Statistiques du module
    stats_module = moyennes.aggregate(
        moyenne_generale=Avg('valeur'),
        meilleure_note=Max('valeur'),
        pire_note=Min('valeur'),
        nb_apprenants=Count('apprenant')
    )

    return render(request, 'evaluations/moyennes_module.html', {
        'module': module,
        'moyennes': moyennes,
        'stats_module': stats_module
    })

# ============ VUES COMMUNES ============

@login_required
@require_evaluation_file_access('evaluation')
def telecharger_fichier_evaluation(request, pk):
    """Télécharger le fichier d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk)

    if not evaluation.fichier_evaluation:
        raise Http404("Fichier non trouvé")

    try:
        response = HttpResponse(
            evaluation.fichier_evaluation.read(),
            content_type='application/octet-stream'
        )
        filename = os.path.basename(evaluation.fichier_evaluation.name)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception:
        raise Http404("Erreur lors du téléchargement")


@login_required
@require_evaluation_file_access('correction')
def telecharger_fichier_correction(request, pk):
    """Télécharger le fichier de correction"""
    evaluation = get_object_or_404(Evaluation, pk=pk)

    if not evaluation.fichier_correction:
        raise Http404("Fichier de correction non trouvé")

    try:
        response = HttpResponse(
            evaluation.fichier_correction.read(),
            content_type='application/octet-stream'
        )
        filename = os.path.basename(evaluation.fichier_correction.name)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception:
        raise Http404("Erreur lors du téléchargement")


@login_required
@require_evaluation_file_access('composition')
def telecharger_fichier_composition(request, pk):
    """Télécharger un fichier de composition"""
    fichier_composition = get_object_or_404(FichierComposition, pk=pk)

    if not fichier_composition.fichier:
        raise Http404("Fichier non trouvé")

    try:
        response = HttpResponse(
            fichier_composition.fichier.read(),
            content_type='application/octet-stream'
        )
        filename = fichier_composition.nom_original
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception:
        raise Http404("Erreur lors du téléchargement")


@login_required
def voir_fichier(request, type_fichier, pk):
    """Visualiser un fichier dans le navigateur"""
    fichier = None

    if type_fichier == 'evaluation':
        evaluation = get_object_or_404(Evaluation, pk=pk)
        fichier = evaluation.fichier_evaluation
    elif type_fichier == 'correction':
        evaluation = get_object_or_404(Evaluation, pk=pk)
        fichier = evaluation.fichier_correction
    elif type_fichier == 'composition':
        fichier_composition = get_object_or_404(FichierComposition, pk=pk)
