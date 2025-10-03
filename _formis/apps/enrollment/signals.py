import logging
from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Candidature, Inscription, DocumentCandidature, Transfert, Abandon, HistoriqueInscription
from .utils import (
    envoyer_email_candidature_soumise,
    envoyer_email_candidature_evaluee,
    creer_compte_utilisateur_depuis_candidature,
    generer_numero_candidature, synchroniser_utilisateur_etudiant
)

# Configuration du logger
logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(pre_save, sender=Candidature)
def candidature_pre_save(sender, instance, **kwargs):
    """
    Signal avant sauvegarde d'une candidature
    Gère la génération du numéro et les validations
    """
    try:
        # Générer le numéro de candidature si nouveau et si les infos sont disponibles
        if (not instance.numero_candidature and
                instance.etablissement and
                instance.filiere and
                instance.annee_academique):
            instance.numero_candidature = generer_numero_candidature(
                instance.etablissement,
                instance.filiere,
                instance.annee_academique
            )
            logger.info(f"Numéro de candidature généré: {instance.numero_candidature}")

        # Si c'est une mise à jour, vérifier les transitions de statut
        if instance.pk:
            try:
                old_instance = Candidature.objects.get(pk=instance.pk)

                # Transition de BROUILLON à SOUMISE
                if (old_instance.statut == 'BROUILLON' and
                        instance.statut == 'SOUMISE'):

                    # Vérifier si la candidature peut être soumise
                    peut_soumettre, message = instance.peut_etre_soumise()
                    if not peut_soumettre:
                        raise ValueError(f"Impossible de soumettre la candidature: {message}")

                    # Définir la date de soumission si pas déjà définie
                    if not instance.date_soumission:
                        instance.date_soumission = timezone.now()

                    logger.info(f"Transition BROUILLON -> SOUMISE pour {instance.numero_candidature}")

                # Transition vers APPROUVEE ou REJETEE
                elif (old_instance.statut in ['SOUMISE', 'EN_COURS_EXAMEN'] and
                      instance.statut in ['APPROUVEE', 'REJETEE']):

                    # Définir la date de décision si pas déjà définie
                    if not instance.date_decision:
                        instance.date_decision = timezone.now()

                    logger.info(f"Transition vers {instance.statut} pour {instance.numero_candidature}")

            except Candidature.DoesNotExist:
                # Candidature créée pour la première fois
                pass

    except Exception as e:
        logger.error(f"Erreur dans candidature_pre_save: {e}", exc_info=True)
        raise

@receiver(post_save, sender=Candidature)
def candidature_post_save(sender, instance, created, **kwargs):
    """
    Signal après sauvegarde d'une candidature
    Gère les emails et la création d'utilisateur
    """

    # Éviter la récursion en utilisant un attribut temporaire
    if hasattr(instance, '_signal_processing'):
        return

    try:
        # Si nouvelle candidature créée
        if created:
            logger.info(f"Nouvelle candidature créée: {instance.numero_candidature} pour {instance.nom_complet()}")
            return

        # Traitement des transitions de statut
        # On utilise transaction.on_commit pour s'assurer que la DB est cohérente
        if instance.statut == 'SOUMISE' and instance.date_soumission:
            # Vérifier si c'est un changement récent (dans les dernières 2 minutes)
            time_diff = timezone.now() - instance.date_soumission
            if time_diff.total_seconds() < 120:  # 2 minutes
                transaction.on_commit(
                    lambda: traiter_candidature_soumise.apply_async(
                        args=[instance.pk], countdown=2
                    )
                )
                logger.info(f"Traitement candidature soumise programmé: {instance.numero_candidature}")

        elif instance.statut in ['APPROUVEE', 'REJETEE'] and instance.date_decision:
            # Vérifier si c'est un changement récent
            time_diff = timezone.now() - instance.date_decision
            if time_diff.total_seconds() < 120:  # 2 minutes
                transaction.on_commit(
                    lambda: traiter_candidature_evaluee.apply_async(
                        args=[instance.pk], countdown=2
                    )
                )
                logger.info(f"Traitement candidature évaluée programmé: {instance.numero_candidature}")

    except Exception as e:
        logger.error(f"Erreur dans candidature_post_save: {e}", exc_info=True)

def traiter_candidature_soumise_sync(candidature_id):
    """Traitement synchrone d'une candidature soumise"""
    try:
        candidature = Candidature.objects.select_related(
            'etablissement', 'filiere', 'niveau', 'annee_academique'
        ).get(pk=candidature_id)

        logger.info(f"Traitement candidature soumise: {candidature.numero_candidature}")

        # Supprimer/Annuler les autres candidatures en brouillon du même email
        with transaction.atomic():
            autres_brouillons = Candidature.objects.filter(
                email=candidature.email,
                statut='BROUILLON'
            ).exclude(pk=candidature.pk)

            if autres_brouillons.exists():
                count = autres_brouillons.update(statut='ANNULEE')
                logger.info(f"{count} brouillons annulés pour {candidature.email}")

        # Envoyer l'email de confirmation
        try:
            if envoyer_email_candidature_soumise(candidature):
                logger.info(f"Email de confirmation envoyé à {candidature.email}")
                return True
            else:
                logger.error(f"Échec envoi email de confirmation à {candidature.email}")
                return False
        except Exception as e:
            logger.error(f"Erreur envoi email candidature soumise: {e}", exc_info=True)
            return False

    except Candidature.DoesNotExist:
        logger.error(f"Candidature {candidature_id} non trouvée")
        return False
    except Exception as e:
        logger.error(f"Erreur traitement candidature soumise {candidature_id}: {e}", exc_info=True)
        return False

def traiter_candidature_evaluee_sync(candidature_id):
    """Traitement synchrone d'une candidature évaluée"""
    try:
        candidature = Candidature.objects.select_related(
            'etablissement', 'filiere', 'niveau', 'annee_academique', 'examine_par'
        ).get(pk=candidature_id)

        logger.info(f"Traitement candidature évaluée: {candidature.numero_candidature} - {candidature.statut}")

        # Envoyer l'email de notification
        email_sent = False
        try:
            if envoyer_email_candidature_evaluee(candidature):
                logger.info(f"Email de notification envoyé à {candidature.email}")
                email_sent = True
            else:
                logger.error(f"Échec envoi email de notification à {candidature.email}")
        except Exception as e:
            logger.error(f"Erreur envoi email candidature évaluée: {e}", exc_info=True)

        # Si approuvée, créer un compte utilisateur
        user_created = False
        if candidature.statut == 'APPROUVEE':
            try:
                utilisateur = creer_compte_utilisateur_depuis_candidature(candidature)
                if utilisateur:
                    logger.info(f"Compte utilisateur créé: {utilisateur.username} pour {candidature.numero_candidature}")
                    user_created = True
                else:
                    logger.error(f"Échec création compte utilisateur pour {candidature.email}")
            except Exception as e:
                logger.error(f"Erreur création compte utilisateur: {e}", exc_info=True)

        return {
            'email_sent': email_sent,
            'user_created': user_created if candidature.statut == 'APPROUVEE' else None
        }

    except Candidature.DoesNotExist:
        logger.error(f"Candidature {candidature_id} non trouvée")
        return False
    except Exception as e:
        logger.error(f"Erreur traitement candidature évaluée {candidature_id}: {e}", exc_info=True)
        return False

# Version avec tâches asynchrones (si Celery est disponible)
try:
    from celery import shared_task


    @shared_task(bind=True, max_retries=3)
    def traiter_candidature_soumise(self, candidature_id):
        """Tâche asynchrone pour traiter une candidature soumise"""
        try:
            return traiter_candidature_soumise_sync(candidature_id)
        except Exception as e:
            logger.error(f"Erreur tâche candidature soumise: {e}")
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=60, exc=e)
            return False


    @shared_task(bind=True, max_retries=3)
    def traiter_candidature_evaluee(self, candidature_id):
        """Tâche asynchrone pour traiter une candidature évaluée"""
        try:
            return traiter_candidature_evaluee_sync(candidature_id)
        except Exception as e:
            logger.error(f"Erreur tâche candidature évaluée: {e}")
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=60, exc=e)
            return False

except ImportError:
    # Si Celery n'est pas disponible, utiliser les versions synchrones
    logger.info("Celery non disponible, utilisation du traitement synchrone")


    def traiter_candidature_soumise(candidature_id):
        return traiter_candidature_soumise_sync(candidature_id)


    def traiter_candidature_evaluee(candidature_id):
        return traiter_candidature_evaluee_sync(candidature_id)

@receiver(post_save, sender=DocumentCandidature)
def document_candidature_post_save(sender, instance, created, **kwargs):
    """Signal après sauvegarde d'un document de candidature"""
    try:
        if created:
            logger.info(f"Document ajouté à candidature {instance.candidature.numero_candidature}: {instance.nom}")
        else:
            logger.info(f"Document modifié pour candidature {instance.candidature.numero_candidature}: {instance.nom}")

            # Si le document a été validé
            if instance.est_valide and instance.valide_par and instance.date_validation:
                time_diff = (timezone.now() - instance.date_validation).total_seconds()
                if time_diff < 60:  # Validé dans la dernière minute
                    logger.info(
                        f"Document validé: {instance.nom} pour candidature {instance.candidature.numero_candidature} par {instance.valide_par.username}")

    except Exception as e:
        logger.error(f"Erreur dans signal post_save document candidature: {str(e)}", exc_info=True)

@receiver(pre_delete, sender=Candidature)
def candidature_pre_delete(sender, instance, **kwargs):
    """Signal avant suppression d'une candidature"""
    try:
        logger.info(f"Suppression candidature: {instance.numero_candidature} - {instance.nom_complet()}")

        # Supprimer les fichiers associés
        for document in instance.documents.all():
            if document.fichier:
                try:
                    document.fichier.delete(save=False)
                    logger.info(f"Fichier supprimé: {document.nom}")
                except Exception as e:
                    logger.error(f"Erreur suppression fichier {document.nom}: {str(e)}")

    except Exception as e:
        logger.error(f"Erreur dans signal pre_delete candidature: {str(e)}", exc_info=True)

@receiver(pre_delete, sender=DocumentCandidature)
def document_candidature_pre_delete(sender, instance, **kwargs):
    """Signal avant suppression d'un document de candidature"""
    try:
        logger.info(f"Suppression document: {instance.nom} de candidature {instance.candidature.numero_candidature}")

        # Supprimer le fichier physique
        if instance.fichier:
            try:
                instance.fichier.delete(save=False)
                logger.info(f"Fichier physique supprimé: {instance.fichier.name}")
            except Exception as e:
                logger.error(f"Erreur suppression fichier physique {instance.fichier.name}: {str(e)}")

    except Exception as e:
        logger.error(f"Erreur dans signal pre_delete document candidature: {str(e)}", exc_info=True)

# Signaux pour audit et logging
@receiver(post_save, sender=User)
def user_created_from_candidature(sender, instance, created, **kwargs):
    """Signal pour traquer la création d'utilisateurs depuis les candidatures"""
    try:
        if created and instance.role == 'APPRENANT':
            # Chercher une candidature approuvée avec le même email
            candidature = Candidature.objects.filter(
                email=instance.email,
                statut='APPROUVEE'
            ).first()

            if candidature:
                logger.info(f"Utilisateur {instance.username} créé depuis candidature {candidature.numero_candidature}")
            else:
                logger.info(f"Nouvel utilisateur apprenant créé: {instance.username} (pas de candidature associée)")

    except Exception as e:
        logger.error(f"Erreur dans signal user_created_from_candidature: {str(e)}", exc_info=True)



@receiver(post_save, sender=Inscription)
def inscription_post_save(sender, instance, created, **kwargs):
    """Signal après sauvegarde d'une inscription"""

    if created:
        print(f"Nouvelle inscription créée: {instance.numero_inscription}")

        # Synchroniser les données de l'utilisateur étudiant
        if synchroniser_utilisateur_etudiant(instance):
            print(f"Données utilisateur synchronisées pour {instance.numero_inscription}")

        # Créer une entrée dans l'historique si elle n'existe pas
        if not HistoriqueInscription.objects.filter(
                inscription=instance,
                type_action='CREATION'
        ).exists():
            HistoriqueInscription.objects.create(
                inscription=instance,
                type_action='CREATION',
                nouvelle_valeur='ACTIVE',
                effectue_par=instance.cree_par
            )

@receiver(pre_save, sender=Inscription)
def inscription_pre_save(sender, instance, **kwargs):
    """Signal avant sauvegarde d'une inscription"""

    # Générer le numéro d'inscription si nouveau
    if not instance.numero_inscription and instance.pk is None:
        from .utils import generer_numero_inscription
        instance.numero_inscription = generer_numero_inscription(
            instance.candidature.etablissement,
            instance.date_debut.year
        )

    # Calculer le solde automatiquement
    if instance.frais_scolarite and instance.total_paye is not None:
        instance.solde = instance.frais_scolarite - instance.total_paye

        # Mettre à jour le statut de paiement
        if instance.solde <= 0:
            instance.statut_paiement = 'COMPLETE'
        elif instance.total_paye > 0:
            instance.statut_paiement = 'PARTIAL'
        else:
            instance.statut_paiement = 'PENDING'

    # Détecter les changements de statut pour l'historique
    if instance.pk:
        try:
            old_instance = Inscription.objects.get(pk=instance.pk)

            # Si changement de statut, créer une entrée dans l'historique
            if old_instance.statut != instance.statut:
                # Cette création sera faite après la sauvegarde via un signal post_save
                instance._status_changed = True
                instance._old_status = old_instance.statut

        except Inscription.DoesNotExist:
            pass


@receiver(post_delete, sender=DocumentCandidature)
def document_candidature_post_delete(sender, instance, **kwargs):
    """Signal après suppression d'un document de candidature"""

    print(f"Document supprimé de la candidature {instance.candidature.numero_candidature}: {instance.nom}")

    # Supprimer le fichier physique
    if instance.fichier and instance.fichier.storage.exists(instance.fichier.name):
        instance.fichier.delete(save=False)


@receiver(post_save, sender=Transfert)
def transfert_post_save(sender, instance, created, **kwargs):
    """Signal après sauvegarde d'un transfert"""

    if created:
        print(f"Nouveau transfert créé: {instance.inscription.numero_inscription}")

        # Notifier les responsables
        # TODO: Implémenter notification aux chefs de département

    # Si transfert approuvé
    if not created and instance.statut == 'APPROVED':
        print(f"Transfert approuvé pour {instance.inscription.numero_inscription}")

        # Créer une entrée dans l'historique si elle n'existe pas
        if not HistoriqueInscription.objects.filter(
                inscription=instance.inscription,
                type_action='TRANSFERT',
                ancienne_valeur=instance.classe_origine.nom,
                nouvelle_valeur=instance.classe_destination.nom
        ).exists():
            HistoriqueInscription.objects.create(
                inscription=instance.inscription,
                type_action='TRANSFERT',
                ancienne_valeur=instance.classe_origine.nom,
                nouvelle_valeur=instance.classe_destination.nom,
                motif=instance.motif,
                effectue_par=instance.approuve_par
            )


@receiver(post_save, sender=Abandon)
def abandon_post_save(sender, instance, created, **kwargs):
    """Signal après sauvegarde d'un abandon"""

    if created:
        print(f"Nouvel abandon créé pour {instance.inscription.numero_inscription}")

        # Mettre à jour le statut de l'inscription
        inscription = instance.inscription
        if inscription.statut != 'WITHDRAWN':
            inscription.statut = 'WITHDRAWN'
            inscription.date_fin_reelle = instance.date_effet
            inscription.save()

        # Créer une entrée dans l'historique
        HistoriqueInscription.objects.create(
            inscription=inscription,
            type_action='ABANDON',
            nouvelle_valeur='WITHDRAWN',
            motif=instance.motif,
            effectue_par=instance.traite_par
        )


# Signal personnalisé pour détecter les changements de statut d'inscription
@receiver(post_save, sender=Inscription)
def inscription_status_changed(sender, instance, created, **kwargs):
    """Détecte et enregistre les changements de statut d'inscription"""

    if not created and hasattr(instance, '_status_changed'):
        # Créer une entrée dans l'historique pour le changement de statut
        type_action_map = {
            'ACTIVE': 'REACTIVATION',
            'SUSPENDED': 'SUSPENSION',
            'TRANSFERRED': 'TRANSFERT',
            'WITHDRAWN': 'ABANDON',
            'GRADUATED': 'DIPLOME',
            'EXPELLED': 'EXCLUSION',
        }

        type_action = type_action_map.get(instance.statut, 'CHANGEMENT_STATUT')

        HistoriqueInscription.objects.create(
            inscription=instance,
            type_action=type_action,
            ancienne_valeur=instance._old_status,
            nouvelle_valeur=instance.statut,
            effectue_par=getattr(instance, '_changed_by', None)
        )

        # Nettoyer les attributs temporaires
        delattr(instance, '_status_changed')
        delattr(instance, '_old_status')
        if hasattr(instance, '_changed_by'):
            delattr(instance, '_changed_by')


# Signaux pour les tâches de maintenance
from django.db.models.signals import post_migrate


@receiver(post_migrate)
def create_default_document_types(sender, **kwargs):
    """Crée les types de documents par défaut après migration"""

    if sender.name == 'enrollment':
        from .models import DocumentRequis

        # Types de documents par défaut (exemple)
        types_defaut = [
            {
                'type_document': 'PIECE_IDENTITE',
                'nom': 'Pièce d\'identité',
                'description': 'Carte d\'identité nationale ou passeport',
                'est_obligatoire': True,
                'formats_autorises': 'pdf,jpg,jpeg,png',
                'ordre_affichage': 1
            },
            {
                'type_document': 'ACTE_NAISSANCE',
                'nom': 'Acte de naissance',
                'description': 'Acte de naissance original ou copie certifiée',
                'est_obligatoire': True,
                'formats_autorises': 'pdf,jpg,jpeg,png',
                'ordre_affichage': 2
            },
            {
                'type_document': 'PHOTO_IDENTITE',
                'nom': 'Photo d\'identité',
                'description': 'Photo d\'identité récente',
                'est_obligatoire': True,
                'formats_autorises': 'jpg,jpeg,png',
                'ordre_affichage': 3
            }
        ]

        print("Signal post_migrate reçu pour enrollment - Types de documents par défaut")
        # Note: L'implémentation complète nécessiterait de vérifier les filières existantes
