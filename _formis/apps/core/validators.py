from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re


def validate_phone_number(value):
    """Valide un numéro de téléphone"""
    # Pattern pour les numéros du Burkina Faso
    pattern = r'^(\+226\s?)?[0-9]{2}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}'
    if not re.match(pattern, value):
        raise ValidationError(
            _('Numéro de téléphone invalide. Format attendu: XX XX XX XX ou +226 XX XX XX XX')
        )


def validate_matricule(value):
    """Valide un matricule"""
    pattern = r'^[A-Z]{2}[0-9]{4}[A-Z0-9]{4,8}'
    if not re.match(pattern, value):
        raise ValidationError(
            _('Format de matricule invalide.')
        )


def validate_file_size(file):
    """Valide la taille d'un fichier"""
    max_size = 10 * 1024 * 1024  # 10MB
    if file.size > max_size:
        raise ValidationError(
            _('Le fichier est trop volumineux. Taille maximale autorisée: 10MB')
        )


def validate_academic_year(value):
    """Valide le format d'une année académique"""
    pattern = r'^[0-9]{4}-[0-9]{4}'
    if not re.match(pattern, value):
        raise ValidationError(
            _('Format d\'année académique invalide. Format attendu: YYYY-YYYY')
        )

    years = value.split('-')
    if int(years[1]) - int(years[0]) != 1:
        raise ValidationError(
            _('L\'année académique doit couvrir deux années consécutives.')
        )


def validate_grade(value, min_grade=0, max_grade=20):
    """Valide une note"""
    if value < min_grade or value > max_grade:
        raise ValidationError(
            _('La note doit être comprise entre %(min)s et %(max)s.') % {
                'min': min_grade,
                'max': max_grade
            }
        )

