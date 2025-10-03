import os
import uuid
from decimal import Decimal
from django.db.models import Q
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import logging
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.db import transaction
from django.core.exceptions import ValidationError

# Configuration du logger
logger = logging.getLogger(__name__)
User = get_user_model()

def generer_numero_inscription(etablissement, annee):
    """Génère un numéro d'inscription unique"""
    from .models import Inscription

    code_etablissement = etablissement.code
    count = Inscription.objects.filter(
        candidature__etablissement=etablissement,
        date_debut__year=annee
    ).count() + 1

    return f"INS{annee}{code_etablissement}{count:05d}"

def upload_candidature_document(instance, filename):
    """Génère le chemin d'upload pour les documents de candidature"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('candidature', 'documents', str(instance.candidature.id), filename)

def valider_document_candidature(document):
    """Valide un document de candidature"""
    errors = []

    # Vérifier la taille
    if document.fichier.size > document.candidature.filiere.taille_max_document:
        errors.append(
            f"Le fichier est trop volumineux. Taille maximale: {document.candidature.filiere.taille_max_document / (1024 * 1024):.1f}MB")

    # Vérifier le format
    extension = document.fichier.name.split('.')[-1].lower()
    formats_autorises = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
    if extension not in formats_autorises:
        errors.append(f"Format de fichier non autorisé. Formats acceptés: {', '.join(formats_autorises)}")

    return errors


def generer_numero_candidature(etablissement, filiere, annee_academique):
    """Génère un numéro de candidature unique"""
    from .models import Candidature

    try:
        annee = annee_academique.nom.split('-')[0] if annee_academique else str(timezone.now().year)
        code_etablissement = etablissement.code
        code_filiere = filiere.code

        # Compter les candidatures existantes pour cette combinaison
        count = Candidature.objects.filter(
            etablissement=etablissement,
            filiere=filiere,
            annee_academique=annee_academique
        ).count() + 1

        return f"CAND{annee}{code_etablissement}{code_filiere}{count:04d}"

    except Exception as e:
        logger.error(f"Erreur génération numéro candidature: {e}")
        # Fallback avec UUID partiel
        import uuid
        return f"CAND-TEMP-{uuid.uuid4().hex[:8].upper()}"

def envoyer_email_candidature_soumise(candidature):
    """Envoie un email de confirmation de soumission de candidature"""
    try:
        subject = f"Candidature soumise avec succès - {candidature.numero_candidature}"

        context = {
            'candidature': candidature,
            'etablissement': candidature.etablissement,
            'formation': f"{candidature.filiere.nom} - {candidature.niveau.nom}",
            'nom_complet': candidature.nom_complet(),
            'site_name': getattr(settings, 'SITE_NAME', 'Plateforme d\'inscription'),
            'date_soumission': candidature.date_soumission,
        }

        # Template HTML pour un email professionnel
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Candidature soumise</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f8f9fa; }}
                .footer {{ padding: 15px; text-align: center; font-size: 12px; color: #666; }}
                .success-icon {{ font-size: 48px; color: #28a745; text-align: center; margin: 20px 0; }}
                .info-box {{ background: white; padding: 15px; border-left: 4px solid #007bff; margin: 15px 0; }}
                .button {{ display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Candidature Soumise</h1>
                    <p>{context['site_name']}</p>
                </div>

                <div class="content">
                    <div class="success-icon">✅</div>

                    <h2>Bonjour {candidature.nom_complet()},</h2>

                    <p>Votre candidature a été soumise avec succès. Voici un récapitulatif :</p>

                    <div class="info-box">
                        <strong>Numéro de candidature :</strong> {candidature.numero_candidature}<br>
                        <strong>Formation :</strong> {context['formation']}<br>
                        <strong>Établissement :</strong> {candidature.etablissement.nom}<br>
                        <strong>Date de soumission :</strong> {candidature.date_soumission.strftime('%d/%m/%Y à %H:%M')}<br>
                    </div>

                    <h3>Prochaines étapes :</h3>
                    <ul>
                        <li>Votre dossier sera examiné par nos équipes</li>
                        <li>Vous recevrez une notification par email dès qu'une décision sera prise</li>
                        <li>En cas d'approbation, vous recevrez vos identifiants de connexion</li>
                    </ul>

                    <p><strong>Important :</strong> Conservez ce numéro de candidature : <strong>{candidature.numero_candidature}</strong></p>
                </div>

                <div class="footer">
                    <p>Cet email a été envoyé automatiquement, merci de ne pas répondre.</p>
                    <p>{context['site_name']} - Service des inscriptions</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Créer et envoyer l'email
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
            to=[candidature.email],
        )
        email.content_subtype = 'html'

        result = email.send()

        if result:
            logger.info(f"Email de confirmation envoyé avec succès à {candidature.email}")
            return True
        else:
            logger.error(f"Échec envoi email à {candidature.email}")
            return False

    except Exception as e:
        logger.error(f"Erreur envoi email candidature soumise: {e}", exc_info=True)
        return False

def envoyer_email_candidature_evaluee(candidature):
    """Envoie un email de notification d'évaluation de candidature"""
    try:
        if candidature.statut == 'APPROUVEE':
            subject = f"Candidature approuvée - {candidature.numero_candidature}"
            status_color = "#28a745"
            status_icon = "✅"
            status_message = "Félicitations ! Votre candidature a été approuvée."
        else:
            subject = f"Candidature non retenue - {candidature.numero_candidature}"
            status_color = "#dc3545"
            status_icon = "❌"
            status_message = "Nous sommes désolés, votre candidature n'a pas pu être retenue."

        context = {
            'candidature': candidature,
            'etablissement': candidature.etablissement,
            'formation': f"{candidature.filiere.nom} - {candidature.niveau.nom}",
            'site_name': getattr(settings, 'SITE_NAME', 'Plateforme d\'inscription'),
        }

        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Résultat de votre candidature</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {status_color}; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f8f9fa; }}
                .footer {{ padding: 15px; text-align: center; font-size: 12px; color: #666; }}
                .status-icon {{ font-size: 48px; text-align: center; margin: 20px 0; }}
                .info-box {{ background: white; padding: 15px; border-left: 4px solid {status_color}; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Résultat de votre candidature</h1>
                    <p>{context['site_name']}</p>
                </div>

                <div class="content">
                    <div class="status-icon">{status_icon}</div>

                    <h2>Bonjour {candidature.nom_complet()},</h2>

                    <p>{status_message}</p>

                    <div class="info-box">
                        <strong>Numéro de candidature :</strong> {candidature.numero_candidature}<br>
                        <strong>Formation :</strong> {context['formation']}<br>
                        <strong>Établissement :</strong> {candidature.etablissement.nom}<br>
                        <strong>Date d'évaluation :</strong> {candidature.date_decision.strftime('%d/%m/%Y à %H:%M')}<br>
                    </div>
        """

        if candidature.statut == 'APPROUVEE':
            html_message += """
                    <h3>Prochaines étapes :</h3>
                    <ul>
                        <li>Vous recevrez vos identifiants de connexion dans un email séparé</li>
                        <li>Connectez-vous à votre espace étudiant pour finaliser votre inscription</li>
                        <li>Consultez les informations sur la rentrée et les modalités pratiques</li>
                    </ul>
            """
            if candidature.notes_approbation:
                html_message += f"""
                    <div class="info-box">
                        <strong>Message de l'équipe :</strong><br>
                        {candidature.notes_approbation}
                    </div>
                """
        else:
            if candidature.motif_rejet:
                html_message += f"""
                    <div class="info-box">
                        <strong>Motif :</strong><br>
                        {candidature.motif_rejet}
                    </div>
                """
            html_message += """
                    <p>Nous vous encourageons à postuler de nouveau lors des prochaines sessions de candidature.</p>
            """

        html_message += """
                </div>

                <div class="footer">
                    <p>Cet email a été envoyé automatiquement, merci de ne pas répondre.</p>
                    <p>{} - Service des inscriptions</p>
                </div>
            </div>
        </body>
        </html>
        """.format(context['site_name'])

        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
            to=[candidature.email],
        )
        email.content_subtype = 'html'

        result = email.send()

        if result:
            logger.info(f"Email d'évaluation envoyé avec succès à {candidature.email}")
            return True
        else:
            logger.error(f"Échec envoi email d'évaluation à {candidature.email}")
            return False

    except Exception as e:
        logger.error(f"Erreur envoi email candidature évaluée: {e}", exc_info=True)
        return False

def creer_compte_utilisateur_depuis_candidature(candidature):
    """Crée un compte utilisateur depuis une candidature approuvée"""
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        # Vérifier si l'utilisateur existe déjà
        if User.objects.filter(email=candidature.email).exists():
            logger.warning(f"Utilisateur existe déjà pour {candidature.email}")
            return User.objects.get(email=candidature.email)

        # Générer un nom d'utilisateur unique
        username_base = f"{candidature.prenom.lower()}.{candidature.nom.lower()}"
        username_base = username_base.replace(' ', '').replace('-', '')
        username = username_base
        counter = 1

        while User.objects.filter(username=username).exists():
            username = f"{username_base}{counter}"
            counter += 1

        # Générer un mot de passe temporaire sécurisé
        mot_de_passe_temp = get_random_string(12)

        # Préparer les données de l'utilisateur
        user_data = {
            'username': username,
            'email': candidature.email,
            'password': mot_de_passe_temp,
            'first_name': candidature.prenom,
            'last_name': candidature.nom,
            'is_active': True,
        }

        # Ajouter les champs personnalisés si votre modèle User les a
        try:
            user_data.update({
                'nom': candidature.nom,
                'prenom': candidature.prenom,
                'telephone': candidature.telephone,
                'date_naissance': candidature.date_naissance,
                'lieu_naissance': candidature.lieu_naissance,
                'genre': candidature.genre,
                'adresse': candidature.adresse,
                'role': 'APPRENANT',
                'etablissement': candidature.etablissement,
            })
        except Exception as e:
            logger.warning(f"Champs personnalisés non disponibles: {e}")

        # Créer l'utilisateur
        utilisateur = User.objects.create_user(**user_data)

        logger.info(f"Compte utilisateur créé: {utilisateur.username} pour candidature {candidature.numero_candidature}")

        # Envoyer les informations de connexion
        if envoyer_informations_connexion(utilisateur, mot_de_passe_temp):
            logger.info(f"Informations de connexion envoyées à {utilisateur.email}")
        else:
            logger.error(f"Échec envoi informations de connexion à {utilisateur.email}")

        return utilisateur

    except Exception as e:
        logger.error(f"Erreur création utilisateur pour candidature {candidature.numero_candidature}: {e}", exc_info=True)
        return None


def envoyer_informations_connexion(utilisateur, mot_de_passe):
    """Envoie les informations de connexion à un nouvel utilisateur"""
    try:
        subject = "Vos identifiants de connexion - Espace étudiant"

        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        site_name = getattr(settings, 'SITE_NAME', 'Plateforme d\'inscription')

        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Identifiants de connexion</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f8f9fa; }}
                .footer {{ padding: 15px; text-align: center; font-size: 12px; color: #666; }}
                .credentials {{ background: white; padding: 20px; border: 2px solid #28a745; border-radius: 8px; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
                .warning {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Bienvenue !</h1>
                    <p>Votre compte étudiant est prêt</p>
                </div>
                
                <div class="content">
                    <h2>Bonjour {utilisateur.get_full_name() or utilisateur.username},</h2>
                    
                    <p>Félicitations ! Votre candidature a été approuvée et votre compte étudiant a été créé.</p>
                    
                    <div class="credentials">
                        <h3>🔐 Vos identifiants de connexion :</h3>
                        <p><strong>Nom d'utilisateur :</strong> {utilisateur.username}</p>
                        <p><strong>Mot de passe temporaire :</strong> {mot_de_passe}</p>
                        <p><strong>Adresse email :</strong> {utilisateur.email}</p>
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ Important :</strong>
                        <ul>
                            <li>Changez votre mot de passe dès votre première connexion</li>
                            <li>Conservez vos identifiants en lieu sûr</li>
                            <li>Ne partagez jamais vos informations de connexion</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="{site_url}/login/" class="button">Se connecter maintenant</a>
                    </div>
                    
                    <h3>Prochaines étapes :</h3>
                    <ol>
                        <li>Connectez-vous à votre espace étudiant</li>
                        <li>Complétez votre profil si nécessaire</li>
                        <li>Consultez les informations sur votre formation</li>
                        <li>Suivez les instructions pour finaliser votre inscription</li>
                    </ol>
                </div>
                
                <div class="footer">
                    <p>Si vous rencontrez des difficultés, contactez le service technique.</p>
                    <p>{site_name} - Service des inscriptions</p>
                </div>
            </div>
        </body>
        </html>
        """

        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
            to=[utilisateur.email],
        )
        email.content_subtype = 'html'

        result = email.send()

        if result:
            logger.info(f"Informations de connexion envoyées avec succès à {utilisateur.email}")
            return True
        else:
            logger.error(f"Échec envoi informations de connexion à {utilisateur.email}")
            return False

    except Exception as e:
        logger.error(f"Erreur envoi informations connexion: {e}", exc_info=True)
        return False

def valider_documents_candidature(candidature):
    """Valide que tous les documents requis sont fournis pour une candidature"""
    try:
        from .models import DocumentRequis

        logger.info(f"Validation documents pour candidature {candidature.numero_candidature}")

        # Récupérer les documents requis pour cette filière/niveau
        documents_requis = DocumentRequis.objects.filter(
            filiere=candidature.filiere,
            est_obligatoire=True
        ).filter(
            models.Q(niveau=candidature.niveau) | models.Q(niveau__isnull=True)
        )

        documents_manquants = []

        for doc_requis in documents_requis:
            if not candidature.documents.filter(type_document=doc_requis.type_document).exists():
                documents_manquants.append(doc_requis.nom)
                logger.warning(f"Document manquant: {doc_requis.nom} pour candidature {candidature.numero_candidature}")

        if documents_manquants:
            logger.info(f"Documents manquants pour candidature {candidature.numero_candidature}: {documents_manquants}")
            return False, f"Documents requis manquants: {', '.join(documents_manquants)}"

        logger.info(f"Tous les documents requis sont fournis pour candidature {candidature.numero_candidature}")
        return True, "Tous les documents requis sont fournis"

    except Exception as e:
        logger.error(f"Erreur validation documents candidature {candidature.numero_candidature}: {str(e)}")
        return False, f"Erreur lors de la validation des documents: {str(e)}"

def nettoyer_candidatures_expirees():
    """Nettoie les candidatures expirées (brouillons anciens)"""
    from .models import Candidature
    from datetime import timedelta

    try:
        # Marquer comme expirées les candidatures brouillons de plus de 30 jours
        date_limite = timezone.now() - timedelta(days=30)

        candidatures_expirees = Candidature.objects.filter(
            statut='BROUILLON',
            created_at__lt=date_limite
        )

        count = candidatures_expirees.count()
        if count > 0:
            candidatures_expirees.update(statut='EXPIREE')
            logger.info(f"{count} candidatures marquées comme expirées")

        return count

    except Exception as e:
        logger.error(f"Erreur nettoyage candidatures expirées: {str(e)}")
        return 0

def statistiques_candidatures(etablissement=None):
    """Génère des statistiques sur les candidatures"""
    from .models import Candidature

    try:
        queryset = Candidature.objects.all()
        if etablissement:
            queryset = queryset.filter(etablissement=etablissement)

        stats = {
            'total': queryset.count(),
            'par_statut': {},
            'par_filiere': {},
            'par_mois': {},
        }

        # Statistiques par statut
        for statut_code, statut_label in Candidature.STATUTS_CANDIDATURE:
            count = queryset.filter(statut=statut_code).count()
            stats['par_statut'][statut_code] = {
                'label': statut_label,
                'count': count,
                'pourcentage': round((count / stats['total'] * 100) if stats['total'] > 0 else 0, 1)
            }

        logger.info(f"Statistiques générées: {stats['total']} candidatures analysées")
        return stats

    except Exception as e:
        logger.error(f"Erreur génération statistiques candidatures: {str(e)}")
        return {
            'total': 0,
            'par_statut': {},
            'par_filiere': {},
            'par_mois': {},
        }

def export_candidatures_excel(queryset, filename=None):
    """Exporte les candidatures en format Excel"""
    if not filename:
        filename = f"candidatures_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    # Préparer les données
    data = []
    for candidature in queryset:
        data.append({
            'Numéro': candidature.numero_candidature,
            'Nom': candidature.nom,
            'Prénom': candidature.prenom,
            'Email': candidature.email,
            'Téléphone': candidature.telephone,
            'Date de naissance': candidature.date_naissance,
            'Lieu de naissance': candidature.lieu_naissance,
            'Genre': candidature.get_genre_display(),
            'Établissement': candidature.etablissement.nom,
            'Filière': candidature.filiere.nom,
            'Niveau': candidature.niveau.nom,
            'Année académique': candidature.annee_academique.nom,
            'Statut': candidature.get_statut_display(),
            'Date de soumission': candidature.date_soumission,
            'Date de création': candidature.created_at,
        })

    # Créer le DataFrame
    df = pd.DataFrame(data)

    # Sauvegarder en Excel
    filepath = os.path.join(settings.MEDIA_ROOT, 'exports', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Candidatures', index=False)

    return filepath

def export_candidatures_pdf(queryset, filename=None):
    """Exporte les candidatures en format PDF"""
    if not filename:
        filename = f"candidatures_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    filepath = os.path.join(settings.MEDIA_ROOT, 'exports', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    doc = SimpleDocTemplate(filepath, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Titre
    title = Paragraph("Liste des Candidatures", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    # Informations générales
    info_text = f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}<br/>Nombre de candidatures: {queryset.count()}"
    info = Paragraph(info_text, styles['Normal'])
    story.append(info)
    story.append(Spacer(1, 12))

    # Tableau des candidatures
    data = [['Numéro', 'Nom Complet', 'Email', 'Filière', 'Statut', 'Date Soumission']]

    for candidature in queryset:
        data.append([
            candidature.numero_candidature,
            candidature.nom_complet(),
            candidature.email,
            candidature.filiere.nom,
            candidature.get_statut_display(),
            candidature.date_soumission.strftime('%d/%m/%Y') if candidature.date_soumission else 'N/A'
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(table)
    doc.build(story)

    return filepath

def calculer_frais_inscription(candidature):
    """Calcule les frais d'inscription pour une candidature"""
    # Frais de base selon la filière et le niveau
    frais_base = candidature.filiere.frais_scolarite or Decimal('0.00')

    # Ajustements selon le niveau
    if candidature.niveau:
        frais_base += candidature.niveau.frais_additionnels or Decimal('0.00')

    # Frais supplémentaires selon l'établissement
    frais_etablissement = candidature.etablissement.frais_inscription or Decimal('0.00')

    return frais_base + frais_etablissement

def verifier_documents_candidature_complets(candidature):
    """Vérifie si tous les documents requis sont fournis"""
    from .models import DocumentRequis

    # Documents requis pour cette filière et ce niveau
    documents_requis = DocumentRequis.objects.filter(
        filiere=candidature.filiere,
        est_obligatoire=True
    ).filter(
        Q(niveau=candidature.niveau) | Q(niveau__isnull=True)
    )

    documents_manquants = []
    for doc_requis in documents_requis:
        if not candidature.documents.filter(type_document=doc_requis.type_document).exists():
            documents_manquants.append(doc_requis.nom)

    return len(documents_manquants) == 0, documents_manquants

def importer_candidatures_excel(fichier_excel, etablissement, annee_academique):
    """Importe des candidatures depuis un fichier Excel"""
    from .models import Candidature
    from apps.academic.models import Filiere, Niveau

    resultats = {
        'succes': 0,
        'erreurs': 0,
        'details': []
    }

    try:
        df = pd.read_excel(fichier_excel)

        colonnes_requises = ['nom', 'prenom', 'email', 'telephone', 'date_naissance', 'filiere', 'niveau']
        colonnes_manquantes = [col for col in colonnes_requises if col not in df.columns]

        if colonnes_manquantes:
            resultats['erreurs'] += 1
            resultats['details'].append(f"Colonnes manquantes: {', '.join(colonnes_manquantes)}")
            return resultats

        for index, row in df.iterrows():
            try:
                # Vérifier si la filière existe
                try:
                    filiere = Filiere.objects.get(nom=row['filiere'], etablissement=etablissement)
                except Filiere.DoesNotExist:
                    resultats['erreurs'] += 1
                    resultats['details'].append(f"Ligne {index + 2}: Filière '{row['filiere']}' non trouvée")
                    continue

                # Vérifier si le niveau existe
                try:
                    niveau = Niveau.objects.get(nom=row['niveau'])
                except Niveau.DoesNotExist:
                    resultats['erreurs'] += 1
                    resultats['details'].append(f"Ligne {index + 2}: Niveau '{row['niveau']}' non trouvé")
                    continue

                # Vérifier si l'email existe déjà
                if Candidature.objects.filter(email=row['email']).exists():
                    resultats['erreurs'] += 1
                    resultats['details'].append(f"Ligne {index + 2}: Email '{row['email']}' déjà utilisé")
                    continue

                # Créer la candidature
                candidature = Candidature.objects.create(
                    etablissement=etablissement,
                    filiere=filiere,
                    niveau=niveau,
                    annee_academique=annee_academique,
                    nom=row['nom'],
                    prenom=row['prenom'],
                    email=row['email'],
                    telephone=row['telephone'],
                    date_naissance=pd.to_datetime(row['date_naissance']).date(),
                    lieu_naissance=row.get('lieu_naissance', ''),
                    genre=row.get('genre', 'M'),
                    adresse=row.get('adresse', ''),
                )

                resultats['succes'] += 1
                resultats['details'].append(f"Ligne {index + 2}: Candidature créée - {candidature.numero_candidature}")

            except Exception as e:
                resultats['erreurs'] += 1
                resultats['details'].append(f"Ligne {index + 2}: Erreur - {str(e)}")

    except Exception as e:
        resultats['erreurs'] += 1
        resultats['details'].append(f"Erreur de lecture du fichier: {str(e)}")

    return resultats

def generer_rapport_mensuel_inscriptions(mois, annee):
    """Génère un rapport mensuel des inscriptions"""
    from .models import Inscription, Candidature

    debut_mois = timezone.datetime(annee, mois, 1)
    if mois == 12:
        fin_mois = timezone.datetime(annee + 1, 1, 1)
    else:
        fin_mois = timezone.datetime(annee, mois + 1, 1)

    # Statistiques du mois
    inscriptions_mois = Inscription.objects.filter(
        date_inscription__gte=debut_mois,
        date_inscription__lt=fin_mois
    )

    candidatures_mois = Candidature.objects.filter(
        created_at__gte=debut_mois,
        created_at__lt=fin_mois
    )

    rapport = {
        'periode': f"{debut_mois.strftime('%B %Y')}",
        'inscriptions_total': inscriptions_mois.count(),
        'candidatures_total': candidatures_mois.count(),
        'candidatures_par_statut': {
            statut[0]: candidatures_mois.filter(statut=statut[0]).count()
            for statut in Candidature.STATUTS_CANDIDATURE
        },
        'inscriptions_par_statut': {
            statut[0]: inscriptions_mois.filter(statut=statut[0]).count()
            for statut in Inscription.STATUTS_INSCRIPTION
        },
        'revenus_mois': inscriptions_mois.aggregate(
            total=models.Sum('total_paye')
        )['total'] or Decimal('0.00'),
    }

    return rapport

def nettoyer_fichiers_temporaires():
    """Nettoie les fichiers d'export temporaires"""
    export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
    if os.path.exists(export_dir):
        for filename in os.listdir(export_dir):
            filepath = os.path.join(export_dir, filename)
            # Supprimer les fichiers de plus de 24h
            if os.path.isfile(filepath):
                file_time = os.path.getctime(filepath)
                if timezone.now().timestamp() - file_time > 86400:  # 24 heures
                    try:
                        os.remove(filepath)
                    except Exception as e:
                        print(f"Erreur suppression fichier {filepath}: {e}")

def synchroniser_utilisateur_etudiant(inscription):
    """Synchronise les données de l'inscription avec le compte utilisateur étudiant"""
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        # Mettre à jour les informations de l'utilisateur
        etudiant = inscription.etudiant
        candidature = inscription.candidature

        # Mise à jour des champs de base
        etudiant.nom = candidature.nom
        etudiant.prenom = candidature.prenom
        etudiant.email = candidature.email
        etudiant.telephone = candidature.telephone
        etudiant.date_naissance = candidature.date_naissance
        etudiant.lieu_naissance = candidature.lieu_naissance
        etudiant.genre = candidature.genre
        etudiant.adresse = candidature.adresse

        # Informations parentales
        etudiant.nom_pere = candidature.nom_pere
        etudiant.telephone_pere = candidature.telephone_pere
        etudiant.nom_mere = candidature.nom_mere
        etudiant.telephone_mere = candidature.telephone_mere
        etudiant.nom_tuteur = candidature.nom_tuteur
        etudiant.telephone_tuteur = candidature.telephone_tuteur

        etudiant.save()
        return True

    except Exception as e:
        print(f"Erreur synchronisation étudiant {inscription.numero_inscription}: {e}")
        return False

def calculer_taux_reussite_candidatures(etablissement=None, filiere=None, annee_academique=None):
    """Calcule le taux de réussite des candidatures"""
    from .models import Candidature

    queryset = Candidature.objects.all()

    if etablissement:
        queryset = queryset.filter(etablissement=etablissement)
    if filiere:
        queryset = queryset.filter(filiere=filiere)
    if annee_academique:
        queryset = queryset.filter(annee_academique=annee_academique)

    total = queryset.count()
    if total == 0:
        return 0

    approuvees = queryset.filter(statut='APPROUVEE').count()
    return round((approuvees / total) * 100, 2)

def generer_statistiques_enrollment(etablissement=None):
    """Génère des statistiques complètes sur les inscriptions"""
    from .models import Candidature, Inscription, Transfert, Abandon
    from django.db.models import Count, Sum, Avg

    # Base queryset
    candidatures_qs = Candidature.objects.all()
    inscriptions_qs = Inscription.objects.all()

    if etablissement:
        candidatures_qs = candidatures_qs.filter(etablissement=etablissement)
        inscriptions_qs = inscriptions_qs.filter(candidature__etablissement=etablissement)

    stats = {
        'candidatures': {
            'total': candidatures_qs.count(),
            'par_statut': dict(
                candidatures_qs.values('statut').annotate(count=Count('id')).values_list('statut', 'count')),
            'par_filiere': list(
                candidatures_qs.values('filiere__nom').annotate(count=Count('id')).order_by('-count')[:10]),
            'par_mois': list(candidatures_qs.extra(
                select={'mois': 'EXTRACT(month FROM created_at)'}
            ).values('mois').annotate(count=Count('id')).order_by('mois')),
        },
        'inscriptions': {
            'total': inscriptions_qs.count(),
            'actives': inscriptions_qs.filter(statut='ACTIVE').count(),
            'par_statut': dict(
                inscriptions_qs.values('statut').annotate(count=Count('id')).values_list('statut', 'count')),
            'revenus_total': inscriptions_qs.aggregate(total=Sum('total_paye'))['total'] or 0,
            'solde_restant': inscriptions_qs.aggregate(solde=Sum('solde'))['solde'] or 0,
        },
        'transferts': {
            'total': Transfert.objects.count(),
            'en_attente': Transfert.objects.filter(statut='PENDING').count(),
            'approuves': Transfert.objects.filter(statut='APPROVED').count(),
        },
        'abandons': {
            'total': Abandon.objects.count(),
            'par_type': dict(
                Abandon.objects.values('type_abandon').annotate(count=Count('id')).values_list('type_abandon',
                                                                                               'count')),
            'remboursements_dus': Abandon.objects.filter(eligible_remboursement=True,
                                                         remboursement_traite=False).count(),
        }
    }

    return stats


class EnrollmentExporter:
    """Classe utilitaire pour l'export de données"""

    @staticmethod
    def export_to_excel(queryset, model_name, fields=None):
        """Export générique vers Excel"""
        filename = f"{model_name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(settings.MEDIA_ROOT, 'exports', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        if not fields:
            # Champs par défaut selon le modèle
            if model_name == 'candidatures':
                fields = ['numero_candidature', 'nom', 'prenom', 'email', 'filiere__nom', 'statut']
            elif model_name == 'inscriptions':
                fields = ['numero_inscription', 'etudiant__nom', 'etudiant__prenom', 'classe_assignee__nom', 'statut']
            else:
                fields = ['id', 'created_at']

        data = list(queryset.values(*fields))
        df = pd.DataFrame(data)

        # Renommer les colonnes
        column_mapping = {
            'numero_candidature': 'Numéro Candidature',
            'numero_inscription': 'Numéro Inscription',
            'nom': 'Nom',
            'prenom': 'Prénom',
            'email': 'Email',
            'filiere__nom': 'Filière',
            'classe_assignee__nom': 'Classe',
            'etudiant__nom': 'Nom Étudiant',
            'etudiant__prenom': 'Prénom Étudiant',
            'statut': 'Statut',
            'created_at': 'Date Création',
        }

        df = df.rename(columns=column_mapping)

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=model_name.title(), index=False)

        return filepath

    @staticmethod
    def export_to_csv(queryset, model_name, fields=None):
        """Export générique vers CSV"""
        filename = f"{model_name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(settings.MEDIA_ROOT, 'exports', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        if not fields:
            if model_name == 'candidatures':
                fields = ['numero_candidature', 'nom', 'prenom', 'email', 'filiere__nom', 'statut']
            elif model_name == 'inscriptions':
                fields = ['numero_inscription', 'etudiant__nom', 'etudiant__prenom', 'classe_assignee__nom', 'statut']
            else:
                fields = ['id', 'created_at']

        data = list(queryset.values(*fields))
        df = pd.DataFrame(data)

        df.to_csv(filepath, index=False, encoding='utf-8')
        return filepath

def valider_import_candidatures(fichier):
    """Valide un fichier d'import de candidatures"""
    erreurs = []

    try:
        # Vérifier l'extension
        if not fichier.name.endswith(('.xlsx', '.xls')):
            erreurs.append("Le fichier doit être au format Excel (.xlsx ou .xls)")
            return erreurs

        # Lire le fichier
        df = pd.read_excel(fichier)

        # Vérifier les colonnes obligatoires
        colonnes_obligatoires = ['nom', 'prenom', 'email', 'telephone', 'date_naissance', 'filiere', 'niveau']
        colonnes_manquantes = [col for col in colonnes_obligatoires if col not in df.columns]

        if colonnes_manquantes:
            erreurs.append(f"Colonnes manquantes: {', '.join(colonnes_manquantes)}")

        # Vérifier que le fichier n'est pas vide
        if df.empty:
            erreurs.append("Le fichier est vide")

        # Vérifier le nombre maximum de lignes
        if len(df) > 1000:
            erreurs.append("Le fichier ne peut pas contenir plus de 1000 lignes")

    except Exception as e:
        erreurs.append(f"Erreur de lecture du fichier: {str(e)}")

    return erreurs

