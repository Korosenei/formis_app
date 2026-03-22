# apps/payments/services/ligdicash.py

import requests
import json
import logging
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from django.conf import settings
from django.utils import timezone
import hashlib
from django.urls import reverse

logger = logging.getLogger(__name__)


class LigdiCashService:
    """Service pour gérer les paiements LigdiCash"""

    def __init__(self):
        self.api_key = getattr(settings, 'LIGDICASH_API_KEY', '')
        self.auth_token = getattr(settings, 'LIGDICASH_AUTH_TOKEN', '')
        self.base_url = getattr(settings, 'LIGDICASH_BASE_URL',
                                'https://client.ligdicash.com/pay/v01/redirect/checkout-invoice/create')
        self.store_name = getattr(settings, 'LIGDICASH_STORE_NAME', 'FORMIS')
        self.store_website = getattr(settings, 'LIGDICASH_STORE_WEBSITE', '')

        # URL pour vérifier le statut d'un paiement
        self.verify_url = getattr(settings, 'LIGDICASH_VERIFY_URL',
                                  'https://client.ligdicash.com/pay/v01/verify')

    def creer_paiement_redirection(self, paiement_id, montant, description,
                                   email_client, nom_client, url_retour_succes,
                                   url_retour_echec, url_callback):
        """
        Créer un paiement avec redirection LigdiCash
        """
        logger.info("=" * 60)
        logger.info("LIGDICASH API CALL")
        logger.info("=" * 60)

        logger.info("[PARAMS] Parametres d'entree:")
        logger.info(f"  - paiement_id: {paiement_id}")
        logger.info(f"  - montant: {montant}")
        logger.info(f"  - email_client: {email_client}")
        logger.info(f"  - nom_client: {nom_client}")

        logger.info("[URLS] URLs de callback:")
        logger.info(f"  - url_retour_succes: {url_retour_succes}")
        logger.info(f"  - url_retour_echec: {url_retour_echec}")
        logger.info(f"  - url_callback: {url_callback}")

        try:
            # Séparer prénom et nom
            parts = nom_client.split(' ', 1)
            prenom = parts[0] if parts else nom_client
            nom = parts[1] if len(parts) > 1 else nom_client

            # Convertir le montant en string (sans décimales pour XOF)
            montant_str = str(int(float(montant)))

            # Structure du payload
            payload = {
                "invoice": {
                    "items": [{
                        "name": description,
                        "description": description,
                        "quantity": 1,
                        "unit_price": montant_str,
                        "total_price": montant_str
                    }],
                    "total_amount": montant_str,
                    "devise": "XOF",
                    "description": description,
                    "customer": nom_client,
                    "customer_email": email_client,
                    "external_id": str(paiement_id)
                },
                "store": {
                    "name": self.store_name,
                    "website_url": self.store_website or url_retour_succes.split('/payments')[0]
                },
                "actions": {
                    "cancel_url": url_retour_echec,
                    "return_url": url_retour_succes,
                    "callback_url": url_callback
                }
            }

            logger.info("[PAYLOAD] Payload construit")
            logger.info("-" * 60)
            logger.info(json.dumps(payload, indent=2, ensure_ascii=False))
            logger.info("-" * 60)

            # Headers
            headers = {
                'Content-Type': 'application/json',
                'Apikey': self.api_key,
                'Authorization': f'Bearer {self.auth_token}'
            }

            # Appel API
            logger.info(f"[API] POST vers: {self.base_url}")
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=30
            )

            logger.info(f"[API] Reponse recue - Status: {response.status_code}")

            # Parser la réponse
            try:
                result = response.json()
                logger.info("[RESPONSE] JSON parse OK")
            except json.JSONDecodeError:
                logger.error("[RESPONSE] JSON parse FAILED")
                logger.error(f"[RESPONSE] Raw: {response.text[:500]}")
                return False, {
                    'error': 'Réponse invalide de LigdiCash',
                    'error_code': 'invalid_response',
                    'description': 'La réponse n\'est pas du JSON valide'
                }

            logger.info("-" * 60)
            logger.info(json.dumps(result, indent=2, ensure_ascii=False))
            logger.info("-" * 60)

            response_code = result.get('response_code')
            logger.info(f"[RESPONSE] response_code: {response_code}")

            # Vérifier le succès
            if response_code == '00':
                token = result.get('token')
                payment_url = result.get('response_text')

                logger.info(f"[SUCCESS] Token: {token}")
                logger.info(f"[SUCCESS] Payment URL: {payment_url}")

                return True, {
                    'transaction_id': token,
                    'payment_url': payment_url,
                    'raw_response': result
                }
            else:
                logger.error("=" * 60)
                logger.error("ERROR")
                logger.error("=" * 60)
                logger.error(f"[ERROR] Code: {response_code}")
                logger.error(f"[ERROR] Message: {result.get('response_text', 'Erreur inconnue')}")

                return False, {
                    'error': result.get('response_text', 'Erreur inconnue'),
                    'error_code': f'ligdicash_{response_code}',
                    'description': result.get('description', ''),
                    'wiki': result.get('wiki', ''),
                    'raw_response': result
                }

        except requests.exceptions.Timeout:
            logger.error("[ERROR] Timeout lors de l'appel API")
            return False, {
                'error': 'Délai d\'attente dépassé',
                'error_code': 'timeout'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"[ERROR] Erreur réseau: {str(e)}")
            return False, {
                'error': f'Erreur réseau: {str(e)}',
                'error_code': 'network_error'
            }
        except Exception as e:
            logger.error(f"[ERROR] Erreur inattendue: {str(e)}", exc_info=True)
            return False, {
                'error': f'Erreur inattendue: {str(e)}',
                'error_code': 'unexpected_error'
            }

    def verifier_statut_paiement(self, transaction_id):
        """
        Vérifier le statut d'un paiement auprès de LigdiCash

        Returns:
            tuple: (success: bool, data: dict)
        """
        logger.info("=" * 60)
        logger.info("VÉRIFICATION STATUT PAIEMENT LIGDICASH")
        logger.info("=" * 60)
        logger.info(f"Transaction ID: {transaction_id}")

        try:
            # Construire l'URL de vérification
            verify_url = f"{self.verify_url}/{transaction_id}"

            headers = {
                'Content-Type': 'application/json',
                'Apikey': self.api_key,
                'Authorization': f'Bearer {self.auth_token}'
            }

            logger.info(f"[API] GET vers: {verify_url}")

            response = requests.get(
                verify_url,
                headers=headers,
                timeout=30
            )

            logger.info(f"[API] Status: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"[ERROR] Status code: {response.status_code}")
                return False, {
                    'error': 'Erreur lors de la vérification',
                    'status_code': response.status_code
                }

            result = response.json()
            logger.info("[RESPONSE]")
            logger.info(json.dumps(result, indent=2, ensure_ascii=False))

            # Mapper le statut LigdiCash vers notre statut
            status = result.get('status', '').lower()
            response_code = result.get('response_code', '')

            # Déterminer si le paiement est confirmé
            is_confirmed = (
                    status in ['completed', 'success', 'successful'] or
                    response_code == '00'
            )

            return True, {
                'status': 'CONFIRME' if is_confirmed else 'EN_COURS',
                'ligdicash_status': status,
                'response_code': response_code,
                'fees': result.get('fees', 0),
                'raw_response': result
            }

        except requests.exceptions.Timeout:
            logger.error("[ERROR] Timeout")
            return False, {'error': 'Timeout'}
        except requests.exceptions.RequestException as e:
            logger.error(f"[ERROR] Erreur réseau: {str(e)}")
            return False, {'error': str(e)}
        except Exception as e:
            logger.error(f"[ERROR] Erreur: {str(e)}", exc_info=True)
            return False, {'error': str(e)}


# Instance unique
ligdicash_service = LigdiCashService()


# ============================================
# FONCTIONS HELPER
# ============================================
def creer_urls_retour(request, paiement_id, use_public_urls=False):
    """
    Créer les URLs de retour pour LigdiCash

    Args:
        request: La requête Django
        paiement_id: ID du paiement
        use_public_urls: True pour utiliser les URLs publiques (sans auth)
    """
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("🔗 GÉNÉRATION DES URLs DE CALLBACK")
    logger.info(f"   Type: {'PUBLIC' if use_public_urls else 'AUTHENTIFIED'}")
    logger.info("=" * 60)

    # Récupérer SITE_URL depuis settings
    site_url = getattr(settings, 'SITE_URL', None)

    if site_url:
        base_url = site_url.rstrip('/')
        logger.info(f"✅ Utilisation de SITE_URL: {base_url}")
    else:
        if request.is_secure():
            scheme = 'https'
        else:
            scheme = 'http'
        host = request.get_host()
        base_url = f"{scheme}://{host}"
        logger.warning(f"⚠️ SITE_URL non configuré, utilisation de: {base_url}")

    # Choisir les URLs selon le type
    if use_public_urls:
        # URLs publiques (sans authentification)
        success_path = reverse('payments:callback_success_public', kwargs={'paiement_id': paiement_id})
        error_path = reverse('payments:callback_error_public', kwargs={'paiement_id': paiement_id})
    else:
        # URLs avec authentification
        success_path = reverse('payments:callback_success', kwargs={'paiement_id': paiement_id})
        error_path = reverse('payments:callback_error', kwargs={'paiement_id': paiement_id})

    callback_path = reverse('payments:webhook_ligdicash')

    urls = {
        'success': f"{base_url}{success_path}",
        'error': f"{base_url}{error_path}",
        'callback': f"{base_url}{callback_path}"
    }

    # Log
    logger.info("📍 URLs générées:")
    logger.info(f"  ✅ Success:  {urls['success']}")
    logger.info(f"  ❌ Error:    {urls['error']}")
    logger.info(f"  🔔 Callback: {urls['callback']}")
    logger.info("-" * 60)

    return urls

# def creer_urls_retour(request, paiement_id):
#     """
#     Créer les URLs de retour pour LigdiCash
#     """
#     logger = logging.getLogger(__name__)
#
#     logger.info("=" * 60)
#     logger.info("🔗 GÉNÉRATION DES URLs DE CALLBACK")
#     logger.info("=" * 60)
#
#     # Récupérer SITE_URL depuis settings
#     site_url = getattr(settings, 'SITE_URL', None)
#
#     if site_url:
#         base_url = site_url.rstrip('/')
#         logger.info(f"✅ Utilisation de SITE_URL: {base_url}")
#     else:
#         if request.is_secure():
#             scheme = 'https'
#         else:
#             scheme = 'http'
#         host = request.get_host()
#         base_url = f"{scheme}://{host}"
#         logger.warning(f"⚠️ SITE_URL non configuré, utilisation de: {base_url}")
#
#     # Construire l'URL de succès SANS paramètres supplémentaires
#     # LigdiCash ajoutera ses propres paramètres
#     success_path = reverse('payments:callback_success', kwargs={'paiement_id': paiement_id})
#     error_path = reverse('payments:callback_error', kwargs={'paiement_id': paiement_id})
#     callback_path = reverse('payments:webhook_ligdicash')
#
#     urls = {
#         'success': f"{base_url}{success_path}",
#         'error': f"{base_url}{error_path}",
#         'callback': f"{base_url}{callback_path}"
#     }
#
#     # Log
#     logger.info("📍 URLs générées:")
#     logger.info(f"  ✅ Success:  {urls['success']}")
#     logger.info(f"  ❌ Error:    {urls['error']}")
#     logger.info(f"  🔔 Callback: {urls['callback']}")
#     logger.info("-" * 60)
#
#     return urls

def formater_montant_ligdicash(montant: Decimal) -> str:
    """
    Formate un montant pour LigdiCash (entier, sans décimales)
    """
    return str(int(montant))


def valider_montant_minimum(montant: Decimal) -> bool:
    """
    Valide que le montant respecte le minimum LigdiCash
    """
    MONTANT_MINIMUM = Decimal('100')  # 100 XOF minimum
    return montant >= MONTANT_MINIMUM

