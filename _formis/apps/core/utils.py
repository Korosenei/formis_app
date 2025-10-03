import random
import string
import os
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
import uuid
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile


def generate_random_string(length=8, include_digits=True, include_uppercase=True):
    """Génère une chaîne aléatoire"""
    chars = string.ascii_lowercase
    if include_digits:
        chars += string.digits
    if include_uppercase:
        chars += string.ascii_uppercase

    return ''.join(random.choice(chars) for _ in range(length))


def generate_password(length=12):
    """Génère un mot de passe sécurisé"""
    characters = string.ascii_letters + string.digits + "!@#$%&*"
    password = ''.join(random.choice(characters) for _ in range(length))
    return password


def send_account_creation_email(user, password, establishment):
    """Envoie un email de création de compte"""
    context = {
        'user': user,
        'password': password,
        'establishment': establishment,
        'login_url': f"{settings.FRONTEND_URL}/login"
    }

    subject = f"Création de votre compte - {establishment.name}"
    html_message = render_to_string('email/account_created.html', context)

    send_mail(
        subject=subject,
        message='',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False
    )


def send_application_approval_email(application):
    """Envoie un email d'approbation de candidature"""
    context = {
        'application': application,
        'login_url': f"{settings.FRONTEND_URL}/login"
    }

    subject = f"Candidature approuvée - {application.establishment.name}"
    html_message = render_to_string('email/application_approved.html', context)

    send_mail(
        subject=subject,
        message='',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[application.email],
        html_message=html_message,
        fail_silently=False
    )


def compress_image(uploaded_file, max_size=(800, 600), quality=85):
    """Compresse une image uploadée"""
    image = Image.open(uploaded_file)

    # Convertir en RGB si nécessaire
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    # Redimensionner si nécessaire
    image.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Sauvegarder avec compression
    output = BytesIO()
    image.save(output, format='JPEG', quality=quality)
    output.seek(0)

    # Créer un nouveau fichier
    return InMemoryUploadedFile(
        output, 'ImageField',
        f"{uploaded_file.name.split('.')[0]}.jpg",
        'image/jpeg',
        output.getbuffer().nbytes,
        None
    )


def get_file_extension(filename):
    """Retourne l'extension d'un fichier"""
    return os.path.splitext(filename)[1].lower().replace('.', '')


def validate_file_type(file, allowed_types):
    """Valide le type d'un fichier"""
    extension = get_file_extension(file.name)
    return extension in allowed_types


def format_file_size(size_bytes):
    """Formate la taille d'un fichier en format lisible"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def calculate_age(birth_date):
    """Calcule l'âge à partir de la date de naissance"""
    today = timezone.now().date()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def generate_matricule(role, establishment_code, year=None):
    """Génère un matricule selon le rôle et l'établissement"""
    if year is None:
        year = timezone.now().year

    role_prefixes = {
        'SUPERADMIN': 'SA',
        'ADMIN': 'AD',
        'DEPARTMENT_HEAD': 'DH',
        'TEACHER': 'TC',
        'STUDENT': 'ST'
    }

    prefix = role_prefixes.get(role, 'US')
    random_suffix = random.randint(1000, 9999)

    return f"{prefix}{year}{establishment_code}{random_suffix}"


def slugify_filename(filename):
    """Crée un slug sûr à partir d'un nom de fichier"""
    name, extension = os.path.splitext(filename)
    # Remplacer les caractères spéciaux
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    # Ajouter un timestamp pour éviter les doublons
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe_name}_{timestamp}{extension}"


def get_academic_year_from_date(date):
    """Détermine l'année académique à partir d'une date"""
    if date.month >= 9:  # Septembre à décembre
        return f"{date.year}-{date.year + 1}"
    else:  # Janvier à août
        return f"{date.year - 1}-{date.year}"


def calculate_gpa(grades, credits):
    """Calcule la moyenne pondérée (GPA)"""
    if not grades or not credits or len(grades) != len(credits):
        return 0

    total_points = sum(grade * credit for grade, credit in zip(grades, credits))
    total_credits = sum(credits)

    return total_points / total_credits if total_credits > 0 else 0


def get_semester_from_date(date, academic_structure='SEMESTER'):
    """Détermine le semestre/trimestre à partir d'une date"""
    month = date.month

    if academic_structure == 'SEMESTER':
        if 9 <= month <= 12 or month == 1:
            return 1  # Premier semestre
        else:
            return 2  # Deuxième semestre

    elif academic_structure == 'TRIMESTER':
        if 9 <= month <= 12:
            return 1  # Premier trimestre
        elif 1 <= month <= 4:
            return 2  # Deuxième trimestre
        else:
            return 3  # Troisième trimestre

    return 1


def format_phone_number(phone):
    """Formate un numéro de téléphone"""
    # Supprimer tous les caractères non numériques
    digits = ''.join(filter(str.isdigit, phone))

    # Format pour le Burkina Faso
    if len(digits) == 8:
        return f"{digits[:2]} {digits[2:4]} {digits[4:6]} {digits[6:8]}"
    elif len(digits) == 11 and digits.startswith('226'):
        return f"+226 {digits[3:5]} {digits[5:7]} {digits[7:9]} {digits[9:11]}"

    return phone


def validate_email_domain(email, allowed_domains=None):
    """Valide le domaine d'un email"""
    if not allowed_domains:
        return True

    domain = email.split('@')[-1].lower()
    return domain in [d.lower() for d in allowed_domains]

