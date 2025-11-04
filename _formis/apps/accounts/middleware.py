# apps/accounts/middleware.py

from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from apps.enrollment.models import Inscription
import logging

logger = logging.getLogger(__name__)


class InscriptionRequiredMiddleware:
    """
    Middleware qui vérifie si un apprenant a une inscription active.
    Si non, affiche le modal d'inscription.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # URLs exemptées de la vérification
        self.exempt_urls = [
            '/accounts/login/',
            '/accounts/logout/',
            '/accounts/forgot-password/',
            '/accounts/reset-password/',
            '/static/',
            '/media/',
            '/payments/',  # Toutes les URLs de paiement
            '/api/',
        ]

    def __call__(self, request):
        # Vérifier si l'utilisateur est authentifié
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Vérifier si c'est un apprenant
        if request.user.role != 'APPRENANT':
            return self.get_response(request)

        # Vérifier si l'URL est exemptée
        if any(request.path.startswith(url) for url in self.exempt_urls):
            return self.get_response(request)

        # Vérifier si l'apprenant a une inscription active
        try:
            inscription = Inscription.objects.filter(
                apprenant=request.user,
                statut='ACTIVE'
            ).exists()

            if not inscription:
                # Pas d'inscription active
                logger.info(f"⚠️ Apprenant sans inscription: {request.user.email}")

                # Si c'est une requête AJAX, retourner un JSON
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'inscription_requise': True,
                        'message': 'Inscription requise'
                    }, status=403)

                # Sinon, rediriger vers le dashboard étudiant
                # Le template du dashboard affichera le modal
                if not request.path.startswith('/dashboard/student/'):
                    return redirect('dashboard:student')

        except Exception as e:
            logger.error(f"Erreur middleware inscription: {str(e)}")

        response = self.get_response(request)
        return response
