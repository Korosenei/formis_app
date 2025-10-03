
class FormisException(Exception):
    """Exception de base pour l'application FORMIS"""
    pass


class InsufficientPermissionsException(FormisException):
    """Exception pour les permissions insuffisantes"""
    pass


class ApplicationNotSubmittableException(FormisException):
    """Exception quand une candidature ne peut pas être soumise"""
    pass


class EnrollmentException(FormisException):
    """Exception pour les problèmes d'inscription"""
    pass


class PaymentException(FormisException):
    """Exception pour les problèmes de paiement"""
    pass


class GradingException(FormisException):
    """Exception pour les problèmes de notation"""
    pass


class ScheduleConflictException(FormisException):
    """Exception pour les conflits d'emploi du temps"""
    pass
