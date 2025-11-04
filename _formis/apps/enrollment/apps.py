from django.apps import AppConfig


class EnrollmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.enrollment'
    verbose_name = 'Inscriptions et Candidatures'

    def ready(self):
        import apps.enrollment.signals


