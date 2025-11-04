# from django.contrib import admin
# from django.utils import timezone
# from django.http import HttpResponse, JsonResponse
# from django.db.models import Q
# from django.contrib import messages
# from django.urls import path
# from django.shortcuts import get_object_or_404
# from django.template.response import TemplateResponse
# from django.utils.html import format_html
# from .models import (
#     PeriodeCandidature, DocumentRequis, Candidature, DocumentCandidature,
#     Inscription, HistoriqueInscription, Transfert, Abandon
# )
#
# import logging
#
# logger = logging.getLogger(__name__)
#
#
# @admin.register(PeriodeCandidature)
# class PeriodeCandidatureAdmin(admin.ModelAdmin):
#     list_display = ['nom', 'etablissement', 'annee_academique', 'date_debut', 'date_fin', 'est_active',
#                     'est_ouverte_display']
#     list_filter = ['etablissement', 'annee_academique', 'est_active', 'date_debut']
#     search_fields = ['nom', 'description']
#     filter_horizontal = ['filieres']
#     date_hierarchy = 'date_debut'
#
#     fieldsets = (
#         ('Informations générales', {
#             'fields': ('nom', 'description', 'etablissement', 'annee_academique')
#         }),
#         ('Période', {
#             'fields': ('date_debut', 'date_fin', 'est_active')
#         }),
#         ('Filières concernées', {
#             'fields': ('filieres',)
#         }),
#     )
#
#     def est_ouverte_display(self, obj):
#         return "🟢 Ouverte" if obj.est_ouverte() else "🔴 Fermée"
#
#     est_ouverte_display.short_description = "Statut"
#
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related(
#             'etablissement', 'annee_academique'
#         ).prefetch_related('filieres')
#
#
# @admin.register(DocumentRequis)
# class DocumentRequisAdmin(admin.ModelAdmin):
#     list_display = ['nom', 'filiere', 'niveau', 'type_document', 'est_obligatoire', 'ordre_affichage']
#     list_filter = ['filiere', 'niveau', 'type_document', 'est_obligatoire']
#     search_fields = ['nom', 'description']
#     list_editable = ['est_obligatoire', 'ordre_affichage']
#     ordering = ['filiere', 'ordre_affichage', 'nom']
#
#     fieldsets = (
#         ('Informations générales', {
#             'fields': ('nom', 'description', 'filiere', 'niveau')
#         }),
#         ('Type et paramètres', {
#             'fields': ('type_document', 'est_obligatoire', 'ordre_affichage')
#         }),
#         ('Contraintes fichier', {
#             'fields': ('taille_maximale', 'formats_autorises')
#         }),
#     )
#
#
# class DocumentCandidatureInline(admin.TabularInline):
#     model = DocumentCandidature
#     extra = 0
#     fields = ['type_document', 'nom', 'fichier', 'est_valide', 'notes_validation']
#     readonly_fields = ['taille_fichier', 'format_fichier']
#
#
# @admin.register(Candidature)
# class CandidatureAdmin(admin.ModelAdmin):
#     list_display = [
#         'numero_candidature', 'nom_complet', 'filiere', 'niveau',
#         'etablissement', 'statut_display', 'date_soumission', 'date_decision', 'examine_par'
#     ]
#     list_filter = [
#         'statut', 'etablissement', 'filiere', 'niveau', 'annee_academique',
#         'date_soumission', 'date_decision', 'created_at'
#     ]
#     search_fields = ['numero_candidature', 'nom', 'prenom', 'email', 'telephone']
#     readonly_fields = ['numero_candidature', 'date_soumission', 'created_at', 'updated_at']
#     list_per_page = 25
#
#     fieldsets = (
#         ('Informations de candidature', {
#             'fields': ('numero_candidature', 'etablissement', 'filiere', 'niveau', 'annee_academique')
#         }),
#         ('Informations personnelles', {
#             'fields': (
#                 ('prenom', 'nom'), 'date_naissance', 'lieu_naissance', 'genre',
#                 'telephone', 'email', 'adresse'
#             )
#         }),
#         ('Informations familiales', {
#             'fields': (
#                 ('nom_pere', 'telephone_pere'),
#                 ('nom_mere', 'telephone_mere'),
#                 ('nom_tuteur', 'telephone_tuteur')
#             ),
#             'classes': ['collapse']
#         }),
#         ('Informations académiques', {
#             'fields': ('ecole_precedente', 'dernier_diplome', 'annee_obtention'),
#             'classes': ['collapse']
#         }),
#         ('Statut et traitement', {
#             'fields': (
#                 'statut', 'date_soumission', 'date_examen', 'date_decision',
#                 'examine_par', 'motif_rejet', 'notes_approbation'
#             )
#         }),
#         ('Frais', {
#             'fields': (
#                 'frais_dossier_requis', 'montant_frais_dossier',
#                 'frais_dossier_payes', 'date_paiement_frais'
#             ),
#             'classes': ['collapse']
#         }),
#         ('Métadonnées', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ['collapse']
#         }),
#     )
#
#     inlines = [DocumentCandidatureInline]
#
#     actions = [
#         'approuver_candidatures', 'rejeter_candidatures',
#         'export_candidatures', 'annuler_candidatures', 'evaluer_candidatures'
#     ]
#
#     def statut_display(self, obj):
#         """Affichage coloré du statut"""
#         colors = {
#             'BROUILLON': 'gray',
#             'SOUMISE': 'blue',
#             'EN_COURS_EXAMEN': 'orange',
#             'APPROUVEE': 'green',
#             'REJETEE': 'red',
#             'ANNULEE': 'gray',
#             'EXPIREE': 'gray',
#         }
#         color = colors.get(obj.statut, 'black')
#         return format_html(
#             '<span style="color: {}; font-weight: bold;">{}</span>',
#             color,
#             obj.get_statut_display()
#         )
#
#     statut_display.short_description = "Statut"
#     statut_display.admin_order_field = 'statut'
#
#     def get_urls(self):
#         """Ajouter des URLs personnalisées"""
#         urls = super().get_urls()
#         custom_urls = [
#             path('evaluer/<uuid:candidature_id>/',
#                  self.admin_site.admin_view(self.evaluer_candidature_view),
#                  name='enrollment_candidature_evaluer'),
#         ]
#         return custom_urls + urls
#
#     def evaluer_candidature_view(self, request, candidature_id):
#         """Vue personnalisée pour évaluer une candidature"""
#         candidature = get_object_or_404(Candidature, pk=candidature_id)
#
#         if request.method == 'POST':
#             decision = request.POST.get('decision')
#             motif_rejet = request.POST.get('motif_rejet', '').strip()
#             notes_approbation = request.POST.get('notes_approbation', '').strip()
#
#             if decision not in ['APPROUVEE', 'REJETEE']:
#                 messages.error(request, 'Décision invalide.')
#                 return self.evaluer_candidature_view(request, candidature_id)
#
#             # Validation
#             if decision == 'REJETEE' and not motif_rejet:
#                 messages.error(request, 'Le motif de rejet est obligatoire.')
#                 return self.evaluer_candidature_view(request, candidature_id)
#
#             try:
#                 # Mettre à jour la candidature
#                 candidature.statut = decision
#                 candidature.date_decision = timezone.now()
#                 candidature.examine_par = request.user
#
#                 if decision == 'REJETEE':
#                     candidature.motif_rejet = motif_rejet
#                     candidature.notes_approbation = ''
#                 else:
#                     candidature.notes_approbation = notes_approbation
#                     candidature.motif_rejet = ''
#
#                 candidature.save()
#
#                 # Envoyer l'email de notification
#                 try:
#                     if envoyer_email_candidature_evaluee(candidature):
#                         messages.success(request, f"Email de notification envoyé à {candidature.email}")
#                     else:
#                         messages.warning(request, "Candidature évaluée mais échec envoi email")
#                 except Exception as e:
#                     messages.warning(request, f"Candidature évaluée mais erreur email: {str(e)}")
#
#                 # Si approuvée, créer un compte utilisateur
#                 if decision == 'APPROUVEE':
#                     try:
#                         utilisateur = creer_compte_utilisateur_depuis_candidature(candidature)
#                         if utilisateur:
#                             messages.success(request, f"Compte utilisateur créé: {utilisateur.username}")
#                         else:
#                             messages.warning(request, "Candidature approuvée mais échec création compte utilisateur")
#                     except Exception as e:
#                         messages.warning(request, f"Candidature approuvée mais erreur création compte: {str(e)}")
#
#                 messages.success(request, f"Candidature {decision.lower()} avec succès.")
#                 logger.info(
#                     f"Candidature {candidature.numero_candidature} évaluée: {decision} par {request.user.username}")
#
#             except Exception as e:
#                 messages.error(request, f"Erreur lors de l'évaluation: {str(e)}")
#                 logger.error(f"Erreur évaluation candidature {candidature.numero_candidature}: {e}")
#
#         context = {
#             'candidature': candidature,
#             'title': f'Évaluer la candidature {candidature.numero_candidature}',
#             'opts': self.model._meta,
#             'has_change_permission': True,
#         }
#
#         return TemplateResponse(request, 'admin/enrollment/candidature/evaluer.html', context)
#
#     def approuver_candidatures(self, request, queryset):
#         """Action pour approuver plusieurs candidatures"""
#         candidatures_traitees = 0
#         erreurs = []
#
#         for candidature in queryset.filter(statut__in=['SOUMISE', 'EN_COURS_EXAMEN']):
#             try:
#                 candidature.statut = 'APPROUVEE'
#                 candidature.date_decision = timezone.now()
#                 candidature.examine_par = request.user
#                 candidature.save()
#
#                 # Envoyer email et créer compte
#                 try:
#                     envoyer_email_candidature_evaluee(candidature)
#                     utilisateur = creer_compte_utilisateur_depuis_candidature(candidature)
#                     if utilisateur:
#                         logger.info(f"Compte créé pour {candidature.numero_candidature}: {utilisateur.username}")
#                 except Exception as e:
#                     logger.error(f"Erreur post-approbation pour {candidature.numero_candidature}: {e}")
#
#                 candidatures_traitees += 1
#
#             except Exception as e:
#                 erreurs.append(f"{candidature.numero_candidature}: {str(e)}")
#
#         message = f"{candidatures_traitees} candidature(s) approuvée(s)."
#         if erreurs:
#             message += f" Erreurs: {'; '.join(erreurs)}"
#
#         self.message_user(request, message, level=messages.SUCCESS if not erreurs else messages.WARNING)
#
#     approuver_candidatures.short_description = "Approuver les candidatures sélectionnées"
#
#     def rejeter_candidatures(self, request, queryset):
#         """Action pour rejeter plusieurs candidatures"""
#         candidatures_traitees = 0
#
#         for candidature in queryset.filter(statut__in=['SOUMISE', 'EN_COURS_EXAMEN']):
#             candidature.statut = 'REJETEE'
#             candidature.date_decision = timezone.now()
#             candidature.examine_par = request.user
#             candidature.motif_rejet = "Rejet groupé depuis l'administration"
#             candidature.save()
#
#             # Envoyer email
#             try:
#                 envoyer_email_candidature_evaluee(candidature)
#             except Exception as e:
#                 logger.error(f"Erreur envoi email rejet pour {candidature.numero_candidature}: {e}")
#
#             candidatures_traitees += 1
#
#         self.message_user(request, f"{candidatures_traitees} candidature(s) rejetée(s).", level=messages.SUCCESS)
#
#     rejeter_candidatures.short_description = "Rejeter les candidatures sélectionnées"
#
#     def annuler_candidatures(self, request, queryset):
#         """Annuler les candidatures sélectionnées"""
#         updated = queryset.filter(statut='BROUILLON').update(statut='ANNULEE')
#         self.message_user(request, f"{updated} candidature(s) annulée(s).", level=messages.SUCCESS)
#
#     annuler_candidatures.short_description = "Annuler les candidatures sélectionnées (brouillons uniquement)"
#
#     def evaluer_candidatures(self, request, queryset):
#         """Rediriger vers la page d'évaluation pour une candidature"""
#         candidatures = queryset.filter(statut__in=['SOUMISE', 'EN_COURS_EXAMEN'])
#
#         if candidatures.count() == 1:
#             candidature = candidatures.first()
#             from django.shortcuts import redirect
#             return redirect('admin:enrollment_candidature_evaluer', candidature_id=candidature.pk)
#         elif candidatures.count() > 1:
#             self.message_user(request, "Sélectionnez une seule candidature pour l'évaluation détaillée.",
#                               level=messages.WARNING)
#         else:
#             self.message_user(request, "Aucune candidature évaluable sélectionnée.", level=messages.WARNING)
#
#     evaluer_candidatures.short_description = "Évaluer la candidature sélectionnée"
#
#     def export_candidatures(self, request, queryset):
#         """Exporter les candidatures en CSV"""
#         import csv
#         from django.http import HttpResponse
#
#         response = HttpResponse(content_type='text/csv')
#         response['Content-Disposition'] = 'attachment; filename="candidatures.csv"'
#
#         writer = csv.writer(response)
#         writer.writerow([
#             'Numéro', 'Nom', 'Prénom', 'Email', 'Téléphone', 'Filière', 'Niveau',
#             'Établissement', 'Statut', 'Date soumission', 'Date décision', 'Examiné par'
#         ])
#
#         for candidature in queryset.select_related('filiere', 'niveau', 'etablissement', 'examine_par'):
#             writer.writerow([
#                 candidature.numero_candidature,
#                 candidature.nom,
#                 candidature.prenom,
#                 candidature.email,
#                 candidature.telephone,
#                 candidature.filiere.nom,
#                 candidature.niveau.nom,
#                 candidature.etablissement.nom,
#                 candidature.get_statut_display(),
#                 candidature.date_soumission.strftime('%d/%m/%Y %H:%M') if candidature.date_soumission else '',
#                 candidature.date_decision.strftime('%d/%m/%Y %H:%M') if candidature.date_decision else '',
#                 candidature.examine_par.get_full_name() if candidature.examine_par else ''
#             ])
#
#         return response
#
#     export_candidatures.short_description = "Exporter les candidatures sélectionnées"
#
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related(
#             'etablissement', 'filiere', 'niveau', 'annee_academique', 'examine_par'
#         )
#
#     def has_change_permission(self, request, obj=None):
#         """Permettre l'évaluation pour les superutilisateurs et admins"""
#         if request.user.is_superuser:
#             return True
#         if hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'CHEF_DEPARTMENT']:
#             return True
#         return False
#
#
# @admin.register(DocumentCandidature)
# class DocumentCandidatureAdmin(admin.ModelAdmin):
#     list_display = ['candidature', 'type_document', 'nom', 'est_valide', 'valide_par', 'date_validation']
#     list_filter = ['type_document', 'est_valide', 'date_validation', 'candidature__statut']
#     search_fields = ['candidature__numero_candidature', 'candidature__nom', 'candidature__prenom', 'nom']
#     readonly_fields = ['taille_fichier', 'format_fichier']
#
#     fieldsets = (
#         ('Document', {
#             'fields': ('candidature', 'type_document', 'nom', 'description', 'fichier')
#         }),
#         ('Informations fichier', {
#             'fields': ('taille_fichier', 'format_fichier'),
#             'classes': ['collapse']
#         }),
#         ('Validation', {
#             'fields': ('est_valide', 'valide_par', 'date_validation', 'notes_validation')
#         }),
#     )
#
#     actions = ['valider_documents']
#
#     def valider_documents(self, request, queryset):
#         updated = queryset.update(
#             est_valide=True,
#             valide_par=request.user,
#             date_validation=timezone.now()
#         )
#         self.message_user(request, f"{updated} document(s) validé(s).", level=messages.SUCCESS)
#
#     valider_documents.short_description = "Valider les documents sélectionnés"
#
#
# # Garder les autres classes admin existantes...
# class HistoriqueInscriptionInline(admin.TabularInline):
#     model = HistoriqueInscription
#     extra = 0
#     fields = ['type_action', 'ancienne_valeur', 'nouvelle_valeur', 'motif', 'effectue_par', 'created_at']
#     readonly_fields = ['created_at']
#
#
# @admin.register(Inscription)
# class InscriptionAdmin(admin.ModelAdmin):
#     list_display = [
#         'numero_inscription', 'apprenant', 'candidature', 'classe_assignee',
#         'statut', 'statut_paiement', 'date_inscription'
#     ]
#     list_filter = [
#         'statut', 'statut_paiement', 'classe_assignee__niveau__filiere',
#         'classe_assignee__niveau', 'date_inscription'
#     ]
#     search_fields = [
#         'numero_inscription', 'apprenant__nom', 'apprenant__prenom',
#         'candidature__numero_candidature'
#     ]
#     readonly_fields = ['numero_inscription', 'solde', 'date_inscription']
#
#     fieldsets = (
#         ('Informations générales', {
#             'fields': ('numero_inscription', 'candidature', 'apprenant', 'classe_assignee')
#         }),
#         ('Dates', {
#             'fields': ('date_inscription', 'date_debut', 'date_fin_prevue', 'date_fin_reelle')
#         }),
#         ('Statuts', {
#             'fields': ('statut', 'statut_paiement')
#         }),
#         ('Finances', {
#             'fields': ('frais_scolarite', 'total_paye', 'solde')
#         }),
#         ('Informations complémentaires', {
#             'fields': ('notes', 'cree_par'),
#             'classes': ['collapse']
#         }),
#     )
#
#     inlines = [HistoriqueInscriptionInline]
#
#     actions = ['suspendre_inscriptions', 'reactiver_inscriptions']
#
#     def suspendre_inscriptions(self, request, queryset):
#         updated = queryset.filter(statut='ACTIVE').update(statut='SUSPENDED')
#         self.message_user(request, f"{updated} inscription(s) suspendue(s).", level=messages.SUCCESS)
#
#     suspendre_inscriptions.short_description = "Suspendre les inscriptions sélectionnées"
#
#     def reactiver_inscriptions(self, request, queryset):
#         updated = queryset.filter(statut='SUSPENDED').update(statut='ACTIVE')
#         self.message_user(request, f"{updated} inscription(s) réactivée(s).", level=messages.SUCCESS)
#
#     reactiver_inscriptions.short_description = "Réactiver les inscriptions sélectionnées"
#
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related(
#             'candidature', 'apprenant', 'classe_assignee', 'cree_par'
#         )
#
#
# @admin.register(Transfert)
# class TransfertAdmin(admin.ModelAdmin):
#     list_display = [
#         'inscription', 'classe_origine', 'classe_destination',
#         'date_transfert', 'statut', 'demande_par'
#     ]
#     list_filter = ['statut', 'date_transfert', 'classe_origine__niveau__filiere']
#     search_fields = [
#         'inscription__apprenant__nom', 'inscription__apprenant__prenom',
#         'inscription__numero_inscription'
#     ]
#
#     fieldsets = (
#         ('Transfert', {
#             'fields': ('inscription', 'classe_origine', 'classe_destination')
#         }),
#         ('Dates', {
#             'fields': ('date_transfert', 'date_effet')
#         }),
#         ('Demande', {
#             'fields': ('motif', 'statut', 'demande_par')
#         }),
#         ('Validation', {
#             'fields': ('approuve_par', 'date_approbation', 'notes_approbation')
#         }),
#     )
#
#     actions = ['approuver_transferts']
#
#     def approuver_transferts(self, request, queryset):
#         for transfert in queryset.filter(statut='PENDING'):
#             transfert.statut = 'APPROVED'
#             transfert.approuve_par = request.user
#             transfert.date_approbation = timezone.now()
#             transfert.save()
#
#             # Mettre à jour la classe de l'inscription
#             transfert.inscription.classe_assignee = transfert.classe_destination
#             transfert.inscription.save()
#
#             # Créer une entrée dans l'historique
#             HistoriqueInscription.objects.create(
#                 inscription=transfert.inscription,
#                 type_action='TRANSFERT',
#                 ancienne_valeur=transfert.classe_origine.nom,
#                 nouvelle_valeur=transfert.classe_destination.nom,
#                 motif=transfert.motif,
#                 effectue_par=request.user
#             )
#
#         self.message_user(request, "Transferts approuvés avec succès.", level=messages.SUCCESS)
#
#     approuver_transferts.short_description = "Approuver les transferts sélectionnés"
#
#
# @admin.register(Abandon)
# class AbandonAdmin(admin.ModelAdmin):
#     list_display = [
#         'inscription', 'date_abandon', 'type_abandon',
#         'eligible_remboursement', 'remboursement_traite'
#     ]
#     list_filter = ['type_abandon', 'eligible_remboursement', 'remboursement_traite', 'date_abandon']
#     search_fields = [
#         'inscription__apprenant__nom', 'inscription__apprenant__prenom',
#         'inscription__numero_inscription'
#     ]
#
#     fieldsets = (
#         ('Abandon', {
#             'fields': ('inscription', 'date_abandon', 'date_effet', 'type_abandon', 'motif')
#         }),
#         ('Remboursement', {
#             'fields': (
#                 'eligible_remboursement', 'montant_remboursable',
#                 'remboursement_traite', 'date_remboursement'
#             )
#         }),
#         ('Restitutions', {
#             'fields': ('documents_retournes', 'materiel_retourne')
#         }),
#         ('Traitement', {
#             'fields': ('traite_par',)
#         }),
#     )