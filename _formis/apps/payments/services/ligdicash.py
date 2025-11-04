# apps/payments/services/ligdicash.py

import requests
import json
import logging
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from django.conf import settings
from django.utils import timezone
import hashlib

logger = logging.getLogger(__name__)


class LigdiCashService:
    """Service pour intégrer les paiements LigdiCash"""

    def __init__(self):
        self.api_key = getattr(settings, 'LIGDICASH_API_KEY', '')
        self.auth_token = getattr(settings, 'LIGDICASH_AUTH_TOKEN', '')
        self.platform = getattr(settings, 'LIGDICASH_PLATFORM', 'test')

        # URLs de l'API
        if self.platform == 'live':
            self.base_url = 'https://client.ligdicash.com'
        else:
            self.base_url = 'https://app.ligdicash.com'

        # Headers par défaut
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        if self.auth_token:
            self.headers['Authorization'] = f'Bearer {self.auth_token}'
        if self.api_key:
            self.headers['Apikey'] = self.api_key

        if not self.api_key or not self.auth_token:
            logger.warning("[WARN] Configuration LigdiCash incomplete")

    def creer_paiement_redirection(
            self,
            paiement_id: str,
            montant: Decimal,
            description: str,
            email_client: str,
            nom_client: str,
            url_retour_succes: str,
            url_retour_echec: str,
            url_callback: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Crée un paiement avec redirection vers LigdiCash
        """
        try:
            # Endpoint correct
            url = f"{self.base_url}/pay/v01/redirect/checkout-invoice/create"

            # ============================================
            # PAYLOAD CORRIGÉ selon la documentation LigdiCash
            # ============================================
            payload = {
                'commande': {
                    'invoice': {
                        'items': [
                            {
                                'name': description[:100],  # Limiter la longueur
                                'description': description[:200],
                                'quantity': 1,
                                'unit_price': str(int(montant)),
                                'total_price': str(int(montant))
                            }
                        ],
                        'total_amount': str(int(montant)),
                        'devise': 'XOF',
                        'description': description[:200],
                        'customer': nom_client[:100],
                        'customer_firstname': nom_client.split()[0][:50] if ' ' in nom_client else nom_client[:50],
                        'customer_lastname': nom_client.split()[-1][:50] if ' ' in nom_client else nom_client[:50],
                        'customer_email': email_client
                    }
                },
                'store': {
                    'name': getattr(settings, 'SITE_NAME', 'FORMIS')[:100],
                    'website_url': getattr(settings, 'SITE_URL', 'http://localhost:8000')
                },
                'actions': {
                    'cancel_url': url_retour_echec,
                    'return_url': url_retour_succes,
                    'callback_url': url_callback if url_callback else url_retour_succes
                },
                'custom_data': {
                    'paiement_id': str(paiement_id),
                    'timestamp': timezone.now().isoformat()
                }
            }

            logger.info(f"[API] Creation paiement LigdiCash: {paiement_id} - {montant} XOF")
            logger.debug(f"URL: {url}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

            # Appel à l'API
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )

            logger.info(f"[API] Status Code: {response.status_code}")

            # Parser la réponse
            try:
                response_data = response.json()
                logger.debug(f"Response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
            except json.JSONDecodeError as e:
                logger.error(f"[ERROR] Decode JSON: {e}")
                logger.error(f"Response content: {response.text}")

                if response.status_code == 404:
                    return False, {
                        'error': 'Endpoint LigdiCash incorrect',
                        'error_code': 'invalid_endpoint',
                        'suggestion': 'Verifiez LIGDICASH_API_KEY et LIGDICASH_AUTH_TOKEN'
                    }

                return False, {
                    'error': 'Reponse invalide du serveur',
                    'error_code': 'json_decode_error',
                    'status_code': response.status_code
                }

            # ============================================
            # VÉRIFIER LE CODE DE RÉPONSE LIGDICASH
            # ============================================
            response_code = response_data.get('response_code', '')
            response_text = response_data.get('response_text', '')

            # Code 00 = Succès
            if response_code == '00':
                payment_url = (
                        response_data.get('response_url') or
                        response_data.get('url') or
                        response_data.get('redirect_url') or
                        response_data.get('payment_url')
                )

                transaction_id = (
                        response_data.get('token') or
                        response_data.get('transaction_id') or
                        str(paiement_id)
                )

                if not payment_url:
                    logger.error("[ERROR] URL de paiement manquante")
                    logger.error(f"Response data: {response_data}")
                    return False, {
                        'error': 'URL de paiement non fournie',
                        'response_code': response_code,
                        'response_text': response_text,
                        'raw_response': response_data
                    }

                logger.info(f"[OK] Paiement LigdiCash cree: {transaction_id}")

                return True, {
                    'payment_url': payment_url,
                    'transaction_id': transaction_id,
                    'status': 'created',
                    'raw_response': response_data
                }

            # Erreur de LigdiCash
            else:
                error_message = response_text or 'Erreur inconnue'

                # Messages d'erreur détaillés
                error_details = {
                    '01': 'Erreur dans la requete',
                    '02': 'Authentification invalide',
                    '03': 'Montant invalide',
                    '04': 'Devise invalide',
                    '05': 'Merchant non trouve',
                    '08': 'Donnees manquantes (Empty command actions)',
                }

                detailed_error = error_details.get(response_code, error_message)

                logger.error(f"[ERROR] LigdiCash: {response_code} - {detailed_error}")
                logger.error(f"Response: {json.dumps(response_data, indent=2)}")

                return False, {
                    'error': detailed_error,
                    'error_code': f'ligdicash_{response_code}',
                    'response_code': response_code,
                    'response_text': response_text,
                    'raw_response': response_data,
                    'wiki': response_data.get('wiki', '')
                }

        except requests.exceptions.Timeout:
            logger.error("[ERROR] Timeout connexion LigdiCash")
            return False, {
                'error': 'Delai d\'attente depasse',
                'error_code': 'timeout_error'
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[ERROR] Connexion LigdiCash: {str(e)}")
            return False, {
                'error': 'Impossible de se connecter au serveur',
                'error_code': 'connection_error'
            }
        except Exception as e:
            logger.error(f"[ERROR] Inattendu: {str(e)}", exc_info=True)
            return False, {
                'error': f'Erreur inattendue: {str(e)}',
                'error_code': 'unexpected_error'
            }

    def verifier_statut_paiement(self, transaction_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Vérifie le statut d'un paiement"""
        try:
            logger.info(f"[API] Verification statut: {transaction_id}")

            url = f"{self.base_url}/pay/v01/redirect/checkout-invoice/confirm/"

            response = requests.post(
                url,
                headers=self.headers,
                json={'token': transaction_id},
                timeout=30
            )

            try:
                response_data = response.json()
            except json.JSONDecodeError:
                logger.error(f"[ERROR] Decode JSON: {response.text}")
                return False, {'error': 'Reponse invalide'}

            if response.status_code == 200:
                status = str(response_data.get('status', '')).lower()
                response_code = response_data.get('response_code', '')

                # Mapper les statuts
                if response_code == '00' or status == 'completed':
                    notre_statut = 'CONFIRME'
                elif status in ['failed', 'error']:
                    notre_statut = 'ECHEC'
                elif status in ['cancelled', 'canceled']:
                    notre_statut = 'ANNULE'
                else:
                    notre_statut = 'EN_ATTENTE'

                logger.info(f"[OK] Statut: {status} -> {notre_statut}")

                return True, {
                    'status': notre_statut,
                    'ligdicash_status': status,
                    'response_code': response_code,
                    'amount': response_data.get('montant') or response_data.get('amount'),
                    'raw_response': response_data
                }
            else:
                error_message = response_data.get('message', 'Erreur verification')
                logger.error(f"[ERROR] Verification: {error_message}")

                return False, {
                    'error': error_message,
                    'raw_response': response_data
                }

        except Exception as e:
            logger.error(f"[ERROR] Verification: {str(e)}")
            return False, {'error': f'Erreur: {str(e)}'}


# Instance globale
ligdicash_service = LigdiCashService()


# ============================================
# FONCTION HELPER POUR DEBUG
# ============================================

def test_ligdicash_connection():
    """Teste la connexion et configuration LigdiCash"""
    print("\n" + "=" * 60)
    print("TEST CONFIGURATION LIGDICASH")
    print("=" * 60)

    print(f"\n1. Configuration:")
    print(f"   - API Key: {'✓ OK' if ligdicash_service.api_key else '✗ Manquante'}")
    print(f"   - Auth Token: {'✓ OK' if ligdicash_service.auth_token else '✗ Manquant'}")
    print(f"   - Platform: {ligdicash_service.platform}")
    print(f"   - Base URL: {ligdicash_service.base_url}")

    if not ligdicash_service.api_key or not ligdicash_service.auth_token:
        print("\n❌ Configuration incomplete!")
        print("\nPour corriger:")
        print("1. Allez sur https://ligdicash.com")
        print("2. Connectez-vous a votre compte")
        print("3. Allez dans Parametres > API")
        print("4. Copiez votre API Key et Auth Token")
        print("5. Ajoutez-les dans settings.py:")
        print("   LIGDICASH_API_KEY = 'votre_api_key'")
        print("   LIGDICASH_AUTH_TOKEN = 'votre_auth_token'")
        return False

    print("\n2. Test de creation de paiement:")

    success, response = ligdicash_service.creer_paiement_redirection(
        paiement_id='TEST-123',
        montant=Decimal('100'),
        description='Test de paiement',
        email_client='test@example.com',
        nom_client='Test User',
        url_retour_succes='http://localhost:8000/success',
        url_retour_echec='http://localhost:8000/error',
        url_callback='http://localhost:8000/callback'
    )

    if success:
        print("   ✓ Paiement cree avec succes!")
        print(f"   - URL: {response.get('payment_url')}")
        print(f"   - Token: {response.get('transaction_id')}")
        return True
    else:
        print("   ✗ Echec de creation")
        print(f"   - Erreur: {response.get('error')}")
        print(f"   - Code: {response.get('error_code')}")
        if response.get('response_code'):
            print(f"   - Response code: {response.get('response_code')}")
            print(f"   - Response text: {response.get('response_text')}")
        if response.get('wiki'):
            print(f"   - Doc: {response.get('wiki')}")
        return False

    print("=" * 60 + "\n")

# Fonctions utilitaires
def creer_urls_retour(request, paiement_id: str) -> Dict[str, str]:
    """
    Crée les URLs de retour pour LigdiCash
    """
    base_url = f"{request.scheme}://{request.get_host()}"

    return {
        'success': f"{base_url}/payments/callback/success/{paiement_id}/",
        'error': f"{base_url}/payments/callback/error/{paiement_id}/",
        'callback': f"{base_url}/payments/webhook/ligdicash/"
    }

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

