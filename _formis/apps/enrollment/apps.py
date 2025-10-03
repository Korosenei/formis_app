from django.apps import AppConfig


class EnrollmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.enrollment'

    def ready(self):
        # Importer les signaux
        import apps.enrollment.signals  # noqa


