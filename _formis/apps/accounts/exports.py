"""
accounts/exports.py
Gestion des exportations CSV et PDF
"""
import csv
from io import BytesIO
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Q, Count
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime

from .models import Utilisateur, ProfilApprenant
from apps.academic.models import Departement, Classe


# ============================================================================
# UTILITAIRES GÉNÉRAUX
# ============================================================================

def get_csv_response(filename):
    """Crée une réponse HTTP pour CSV avec encodage UTF-8 BOM"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff'.encode('utf8'))  # BOM pour Excel
    return response


def get_pdf_response(filename):
    """Crée une réponse HTTP pour PDF"""
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def create_pdf_document(buffer, title, landscape_mode=False):
    """Crée un document PDF avec configuration de base"""
    pagesize = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm
    )
    return doc


def get_pdf_styles():
    """Retourne les styles pour le PDF"""
    styles = getSampleStyleSheet()

    # Style pour le titre principal
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=20,
        alignment=1  # Centre
    ))

    # Style pour les sous-titres
    styles.add(ParagraphStyle(
        name='CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=12,
        spaceBefore=12
    ))

    # Style pour le texte normal
    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#4b5563')
    ))

    return styles


def create_table_style():
    """Crée le style de base pour les tableaux PDF"""
    return TableStyle([
        # En-tête
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),

        # Corps du tableau
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1f2937')),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),

        # Lignes alternées
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),

        # Bordures
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#2563eb')),
    ])


def add_pdf_header(elements, title, etablissement, styles):
    """Ajoute l'en-tête du PDF"""
    # Titre principal
    elements.append(Paragraph(title, styles['CustomTitle']))

    # Informations établissement
    info_text = f"""
    <b>Établissement :</b> {etablissement.nom}<br/>
    <b>Date d'export :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}<br/>
    """
    elements.append(Paragraph(info_text, styles['CustomBody']))
    elements.append(Spacer(1, 20))


# ============================================================================
# EXPORT UTILISATEURS
# ============================================================================

@login_required
def users_export_csv(request):
    """Exporte les utilisateurs en CSV"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    # Récupérer les utilisateurs
    if request.user.role == 'ADMIN':
        users = Utilisateur.objects.filter(etablissement=request.user.etablissement)
    else:
        users = Utilisateur.objects.filter(departement=request.user.departement)

    # Appliquer les filtres
    users = apply_user_filters(request, users)
    users = users.select_related('departement').order_by('-date_creation')

    # Créer le CSV
    response = get_csv_response(f'utilisateurs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    writer = csv.writer(response)

    writer.writerow([
        'Matricule', 'Prénom', 'Nom', 'Email', 'Téléphone',
        'Rôle', 'Département', 'Statut', 'Date création'
    ])

    for user in users:
        writer.writerow([
            user.matricule,
            user.prenom,
            user.nom,
            user.email,
            user.telephone or '',
            user.get_role_display(),
            user.departement.nom if user.departement else '',
            'Actif' if user.est_actif else 'Inactif',
            user.date_creation.strftime('%d/%m/%Y %H:%M')
        ])

    messages.success(request, f"{users.count()} utilisateur(s) exporté(s) avec succès")
    return response


@login_required
def users_export_pdf(request):
    """Exporte les utilisateurs en PDF"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    # Récupérer les utilisateurs
    if request.user.role == 'ADMIN':
        users = Utilisateur.objects.filter(etablissement=request.user.etablissement)
    else:
        users = Utilisateur.objects.filter(departement=request.user.departement)

    users = apply_user_filters(request, users)
    users = users.select_related('departement').order_by('-date_creation')

    # Créer le PDF
    buffer = BytesIO()
    doc = create_pdf_document(buffer, "Liste des Utilisateurs", landscape_mode=True)
    elements = []
    styles = get_pdf_styles()

    # En-tête
    add_pdf_header(elements, "Liste des Utilisateurs", request.user.etablissement, styles)

    # Statistiques rapides
    stats_text = f"""
    <b>Total :</b> {users.count()} utilisateur(s)<br/>
    <b>Actifs :</b> {users.filter(est_actif=True).count()}<br/>
    <b>Inactifs :</b> {users.filter(est_actif=False).count()}
    """
    elements.append(Paragraph(stats_text, styles['CustomBody']))
    elements.append(Spacer(1, 15))

    # Tableau
    data = [['Matricule', 'Nom complet', 'Email', 'Rôle', 'Département', 'Statut', 'Date']]

    for user in users[:100]:  # Limite à 100 pour la performance
        data.append([
            user.matricule,
            user.get_full_name()[:25],
            user.email[:30],
            user.get_role_display()[:15],
            (user.departement.code if user.departement else '-')[:15],
            'Actif' if user.est_actif else 'Inactif',
            user.date_creation.strftime('%d/%m/%y')
        ])

    table = Table(data, colWidths=[3 * cm, 4.5 * cm, 5 * cm, 3 * cm, 3.5 * cm, 2 * cm, 2 * cm])
    table.setStyle(create_table_style())
    elements.append(table)

    # Note si plus de 100 utilisateurs
    if users.count() > 100:
        elements.append(Spacer(1, 10))
        note = Paragraph(
            f"<i>Note: Seuls les 100 premiers utilisateurs sont affichés sur {users.count()} au total.</i>",
            styles['CustomBody']
        )
        elements.append(note)

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = get_pdf_response(f'utilisateurs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
    response.write(pdf)

    messages.success(request, f"Export PDF généré avec succès ({users.count()} utilisateurs)")
    return response


def apply_user_filters(request, queryset):
    """Applique les filtres de recherche utilisateurs"""
    role = request.GET.get('role')
    if role:
        queryset = queryset.filter(role=role)

    departement = request.GET.get('departement')
    if departement:
        queryset = queryset.filter(departement_id=departement)

    search = request.GET.get('search')
    if search:
        queryset = queryset.filter(
            Q(prenom__icontains=search) |
            Q(nom__icontains=search) |
            Q(matricule__icontains=search) |
            Q(email__icontains=search)
        )

    return queryset


# ============================================================================
# EXPORT COMPTABLES
# ============================================================================

@login_required
def comptables_export_csv(request):
    """Exporte les comptables en CSV"""
    if request.user.role != 'ADMIN':
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    response = get_csv_response(f'comptables_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    writer = csv.writer(response)

    writer.writerow([
        'Matricule', 'Nom', 'Prénom', 'Email', 'Téléphone',
        'Date embauche', 'Spécialisation', 'Statut'
    ])

    comptables = Utilisateur.objects.filter(
        etablissement=request.user.etablissement,
        role='COMPTABLE'
    ).select_related('profil_comptable')

    for comptable in comptables:
        profil = getattr(comptable, 'profil_comptable', None)
        writer.writerow([
            comptable.matricule,
            comptable.nom,
            comptable.prenom,
            comptable.email,
            comptable.telephone or '',
            profil.date_embauche.strftime('%d/%m/%Y') if profil and profil.date_embauche else '',
            profil.specialisation if profil else '',
            'Actif' if comptable.est_actif else 'Inactif'
        ])

    messages.success(request, f"{comptables.count()} comptable(s) exporté(s) avec succès")
    return response


@login_required
def comptables_export_pdf(request):
    """Exporte les comptables en PDF"""
    if request.user.role != 'ADMIN':
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    comptables = Utilisateur.objects.filter(
        etablissement=request.user.etablissement,
        role='COMPTABLE'
    ).select_related('profil_comptable')

    buffer = BytesIO()
    doc = create_pdf_document(buffer, "Liste des Comptables", landscape_mode=True)
    elements = []
    styles = get_pdf_styles()

    add_pdf_header(elements, "Liste des Comptables", request.user.etablissement, styles)

    # Tableau
    data = [['Matricule', 'Nom complet', 'Email', 'Téléphone', 'Spécialisation', 'Date embauche', 'Statut']]

    for comptable in comptables:
        profil = getattr(comptable, 'profil_comptable', None)
        data.append([
            comptable.matricule,
            comptable.get_full_name()[:30],
            comptable.email[:30],
            comptable.telephone or '-',
            (profil.specialisation[:20] if profil else '-'),
            profil.date_embauche.strftime('%d/%m/%Y') if profil and profil.date_embauche else '-',
            'Actif' if comptable.est_actif else 'Inactif'
        ])

    table = Table(data, colWidths=[2.5 * cm, 4 * cm, 5 * cm, 3 * cm, 4 * cm, 2.5 * cm, 2 * cm])
    table.setStyle(create_table_style())
    elements.append(table)

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = get_pdf_response(f'comptables_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
    response.write(pdf)

    messages.success(request, f"{comptables.count()} comptable(s) exporté(s) en PDF")
    return response


# ============================================================================
# EXPORT CHEFS DE DÉPARTEMENT
# ============================================================================

@login_required
def department_heads_export_csv(request):
    """Exporte les chefs de département en CSV"""
    if request.user.role != 'ADMIN':
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    response = get_csv_response(f'chefs_departement_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    writer = csv.writer(response)

    writer.writerow([
        'Département', 'Code Département', 'Chef', 'Matricule Chef',
        'Email', 'Téléphone', 'Nombre Enseignants', 'Nombre Filières',
        'Statut', 'Date Nomination'
    ])

    departements = Departement.objects.filter(
        etablissement=request.user.etablissement,
        est_actif=True
    ).select_related('chef').prefetch_related('utilisateurs', 'filieres').order_by('nom')

    for dept in departements:
        if dept.chef:
            writer.writerow([
                dept.nom,
                dept.code,
                dept.chef.get_full_name(),
                dept.chef.matricule,
                dept.chef.email,
                dept.chef.telephone or '',
                dept.utilisateurs.count(),
                dept.filieres.count(),
                'Assigné',
                dept.chef.date_creation.strftime('%d/%m/%Y') if dept.chef.date_creation else ''
            ])
        else:
            writer.writerow([
                dept.nom,
                dept.code,
                'Non assigné',
                '-',
                '-',
                '-',
                dept.utilisateurs.count(),
                dept.filieres.count(),
                'Vacant',
                '-'
            ])

    messages.success(request, f"{departements.count()} département(s) exporté(s) avec succès")
    return response


@login_required
def department_heads_export_pdf(request):
    """Exporte les chefs de département en PDF"""
    if request.user.role != 'ADMIN':
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    departements = Departement.objects.filter(
        etablissement=request.user.etablissement,
        est_actif=True
    ).select_related('chef').prefetch_related('utilisateurs', 'filieres').order_by('nom')

    buffer = BytesIO()
    doc = create_pdf_document(buffer, "Chefs de Département", landscape_mode=True)
    elements = []
    styles = get_pdf_styles()

    add_pdf_header(elements, "Liste des Chefs de Département", request.user.etablissement, styles)

    # Statistiques
    avec_chef = departements.filter(chef__isnull=False).count()
    sans_chef = departements.filter(chef__isnull=True).count()

    stats_text = f"""
    <b>Total départements :</b> {departements.count()}<br/>
    <b>Avec chef :</b> {avec_chef}<br/>
    <b>Sans chef :</b> {sans_chef}
    """
    elements.append(Paragraph(stats_text, styles['CustomBody']))
    elements.append(Spacer(1, 15))

    # Tableau
    data = [['Département', 'Code', 'Chef', 'Email', 'Téléphone', 'Ens.', 'Fil.', 'Statut']]

    for dept in departements:
        if dept.chef:
            data.append([
                dept.nom[:25],
                dept.code,
                dept.chef.get_full_name()[:25],
                dept.chef.email[:25],
                dept.chef.telephone or '-',
                str(dept.utilisateurs.count()),
                str(dept.filieres.count()),
                'Assigné'
            ])
        else:
            data.append([
                dept.nom[:25],
                dept.code,
                'Non assigné',
                '-',
                '-',
                str(dept.utilisateurs.count()),
                str(dept.filieres.count()),
                'Vacant'
            ])

    table = Table(data, colWidths=[4.5 * cm, 2 * cm, 4 * cm, 4.5 * cm, 3 * cm, 1.5 * cm, 1.5 * cm, 2 * cm])
    table.setStyle(create_table_style())
    elements.append(table)

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = get_pdf_response(f'chefs_departement_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
    response.write(pdf)

    messages.success(request, f"{departements.count()} département(s) exporté(s) en PDF")
    return response


# ============================================================================
# EXPORT ENSEIGNANTS
# ============================================================================

@login_required
def teachers_export_csv(request):
    """Exporte les enseignants en CSV"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    response = get_csv_response(f'enseignants_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    writer = csv.writer(response)

    writer.writerow([
        'Matricule', 'Nom', 'Prénom', 'Email', 'Téléphone',
        'Département', 'Spécialisation', 'Statut', 'Actif'
    ])

    if request.user.role == 'ADMIN':
        teachers = Utilisateur.objects.filter(
            etablissement=request.user.etablissement,
            role='ENSEIGNANT'
        )
    else:
        teachers = Utilisateur.objects.filter(
            departement=request.user.departement,
            role='ENSEIGNANT'
        )

    teachers = teachers.select_related('departement', 'profil_enseignant')

    for teacher in teachers:
        profil = getattr(teacher, 'profil_enseignant', None)
        writer.writerow([
            teacher.matricule,
            teacher.nom,
            teacher.prenom,
            teacher.email,
            teacher.telephone or '',
            teacher.departement.nom if teacher.departement else '',
            profil.specialisation if profil else '',
            'Permanent' if profil and profil.est_permanent else 'Vacataire',
            'Oui' if teacher.est_actif else 'Non'
        ])

    messages.success(request, f"{teachers.count()} enseignant(s) exporté(s) avec succès")
    return response


@login_required
def teachers_export_pdf(request):
    """Exporte les enseignants en PDF"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    if request.user.role == 'ADMIN':
        teachers = Utilisateur.objects.filter(
            etablissement=request.user.etablissement,
            role='ENSEIGNANT'
        )
    else:
        teachers = Utilisateur.objects.filter(
            departement=request.user.departement,
            role='ENSEIGNANT'
        )

    teachers = teachers.select_related('departement', 'profil_enseignant')

    buffer = BytesIO()
    doc = create_pdf_document(buffer, "Liste des Enseignants", landscape_mode=True)
    elements = []
    styles = get_pdf_styles()

    add_pdf_header(elements, "Liste des Enseignants", request.user.etablissement, styles)

    # Tableau
    data = [['Matricule', 'Nom complet', 'Email', 'Département', 'Spécialisation', 'Type', 'Statut']]

    for teacher in teachers[:150]:
        profil = getattr(teacher, 'profil_enseignant', None)
        data.append([
            teacher.matricule,
            teacher.get_full_name()[:30],
            teacher.email[:30],
            (teacher.departement.code if teacher.departement else '-')[:15],
            (profil.specialisation[:20] if profil else '-'),
            'Permanent' if profil and profil.est_permanent else 'Vacataire',
            'Actif' if teacher.est_actif else 'Inactif'
        ])

    table = Table(data, colWidths=[2.5 * cm, 4 * cm, 5 * cm, 3 * cm, 4 * cm, 2.5 * cm, 2 * cm])
    table.setStyle(create_table_style())
    elements.append(table)

    if teachers.count() > 150:
        elements.append(Spacer(1, 10))
        note = Paragraph(
            f"<i>Note: Seuls les 150 premiers enseignants sont affichés sur {teachers.count()} au total.</i>",
            styles['CustomBody']
        )
        elements.append(note)

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = get_pdf_response(f'enseignants_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
    response.write(pdf)

    messages.success(request, f"{teachers.count()} enseignant(s) exporté(s) en PDF")
    return response


# ============================================================================
# EXPORT ÉTUDIANTS
# ============================================================================

@login_required
def students_export_csv(request):
    """Exporte les étudiants en CSV"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    response = get_csv_response(f'etudiants_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    writer = csv.writer(response)

    writer.writerow([
        'Matricule', 'Nom', 'Prénom', 'Email', 'Téléphone',
        'Département', 'Classe', 'Statut Paiement', 'Actif'
    ])

    if request.user.role == 'ADMIN':
        students = Utilisateur.objects.filter(
            etablissement=request.user.etablissement,
            role='APPRENANT'
        )
    else:
        students = Utilisateur.objects.filter(
            departement=request.user.departement,
            role='APPRENANT'
        )

    students = students.select_related('departement', 'profil_apprenant__classe_actuelle')

    for student in students:
        profil = getattr(student, 'profil_apprenant', None)
        writer.writerow([
            student.matricule,
            student.nom,
            student.prenom,
            student.email,
            student.telephone or '',
            student.departement.nom if student.departement else '',
            profil.classe_actuelle.nom if profil and profil.classe_actuelle else '',
            profil.get_statut_paiement_display() if profil else '',
            'Oui' if student.est_actif else 'Non'
        ])

    messages.success(request, f"{students.count()} étudiant(s) exporté(s) avec succès")
    return response


@login_required
def students_export_pdf(request):
    """Exporte les étudiants en PDF"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    if request.user.role == 'ADMIN':
        students = Utilisateur.objects.filter(
            etablissement=request.user.etablissement,
            role='APPRENANT'
        )
    else:
        students = Utilisateur.objects.filter(
            departement=request.user.departement,
            role='APPRENANT'
        )

    students = students.select_related('departement', 'profil_apprenant__classe_actuelle')

    buffer = BytesIO()
    doc = create_pdf_document(buffer, "Liste des Étudiants", landscape_mode=True)
    elements = []
    styles = get_pdf_styles()

    add_pdf_header(elements, "Liste des Étudiants", request.user.etablissement, styles)

    # Tableau
    data = [['Matricule', 'Nom complet', 'Email', 'Département', 'Classe', 'Paiement', 'Statut']]

    for student in students[:150]:
        profil = getattr(student, 'profil_apprenant', None)
        data.append([
            student.matricule,
            student.get_full_name()[:30],
            student.email[:30],
            (student.departement.code if student.departement else '-')[:15],
            (profil.classe_actuelle.nom[:15] if profil and profil.classe_actuelle else '-'),
            (profil.get_statut_paiement_display()[:10] if profil else '-'),
            'Actif' if student.est_actif else 'Inactif'
        ])

    table = Table(data, colWidths=[2.5 * cm, 4 * cm, 5 * cm, 3 * cm, 3 * cm, 2.5 * cm, 2 * cm])
    table.setStyle(create_table_style())
    elements.append(table)

    if students.count() > 150:
        elements.append(Spacer(1, 10))
        note = Paragraph(
            f"<i>Note: Seuls les 150 premiers étudiants sont affichés sur {students.count()} au total.</i>",
            styles['CustomBody']
        )
        elements.append(note)

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = get_pdf_response(f'etudiants_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
    response.write(pdf)

    messages.success(request, f"{students.count()} étudiant(s) exporté(s) en PDF")
    return response
