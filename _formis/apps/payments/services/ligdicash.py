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

    def creer_paiement_redirection(self, paiement_id, montant, description,
                                   email_client, nom_client, url_retour_succes,
                                   url_retour_echec, url_callback):
        """
        Créer un paiement avec redirection LigdiCash

        CORRECTION: Structure du payload selon la doc LigdiCash
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

            # CORRECTION CRITIQUE: Structure selon la doc officielle LigdiCash
            # Les URLs doivent être dans "actions" avec les BONS noms de clés
            payload = {
                "commande": {
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
                        "customer_firstname": prenom,
                        "customer_lastname": nom,
                        "customer_email": email_client,
                        "external_id": str(paiement_id)
                    }
                },
                "store": {
                    "name": self.store_name,
                    "website_url": self.store_website or url_retour_succes.split('/payments')[0]
                },
                # CORRECTION: Clés exactes selon la doc LigdiCash
                "actions": {
                    "cancel_url": url_retour_echec,  # URL en cas d'annulation
                    "return_url": url_retour_succes,  # URL de retour après paiement
                    "callback_url": url_callback  # URL de notification serveur
                },
                "custom_data": {
                    "paiement_id": str(paiement_id),
                    "timestamp": str(timezone.now().isoformat())
                }
            }

            logger.info("[PAYLOAD] Payload construit")
            logger.info("-" * 60)
            logger.info(json.dumps(payload, indent=2, ensure_ascii=False))
            logger.info("-" * 60)

            # VÉRIFICATION: S'assurer que la section actions existe
            if "actions" not in payload or not payload["actions"]:
                logger.error("[ERROR] Section 'actions' manquante dans le payload!")
                return False, {
                    'error': 'Configuration invalide',
                    'error_code': 'payload_error',
                    'description': 'Section actions manquante'
                }

            # Vérifier chaque URL
            logger.info("[ACTIONS] Verification section actions:")
            logger.info(f"  - cancel_url: {payload['actions'].get('cancel_url')}")
            logger.info(f"  - return_url: {payload['actions'].get('return_url')}")
            logger.info(f"  - callback_url: {payload['actions'].get('callback_url')}")

            # S'assurer qu'aucune URL n'est None ou vide
            for key in ['cancel_url', 'return_url', 'callback_url']:
                if not payload['actions'].get(key):
                    logger.error(f"[ERROR] {key} est vide ou None!")
                    return False, {
                        'error': f'{key} manquant',
                        'error_code': 'missing_url',
                        'description': f'L\'URL {key} est requise'
                    }

            logger.info("[ACTIONS] OK - Toutes les URLs sont presentes")

            # Headers
            headers = {
                'Authorization': f'Bearer {self.auth_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }

            # Appel API
            logger.info(f"[API] POST vers: {self.base_url}")
            logger.info(f"[API] Envoi...")

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
            logger.info(f"[RESPONSE] response_text: {result.get('response_text')}")
            logger.info(f"[RESPONSE] description: {result.get('description')}")

            # Vérifier le succès
            if response_code == '00':
                # Succès
                payment_url = result.get('response_text')  # L'URL de paiement
                token = result.get('token')

                logger.info(f"[SUCCESS] Token: {token}")
                logger.info(f"[SUCCESS] Payment URL: {payment_url}")

                return True, {
                    'transaction_id': token,
                    'payment_url': payment_url,
                    'raw_response': result
                }
            else:
                # Échec
                logger.error("=" * 60)
                logger.error("ERROR")
                logger.error("=" * 60)
                logger.error(f"[ERROR] Code: {response_code}")
                logger.error(f"[ERROR] Message: {result.get('response_text', 'Erreur inconnue')}")
                logger.error(f"[ERROR] Description: {result.get('description', '')}")
                logger.error(f"[ERROR] Wiki: {result.get('wiki', '')}")

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
        """Vérifier le statut d'un paiement"""
        # À implémenter selon votre besoin
        pass


# Instance unique
ligdicash_service = LigdiCashService()


# ============================================
# FONCTION HELPER POUR DEBUG
# ============================================


# Fonctions utilitaires
def creer_urls_retour(request, paiement_id):
    """
    Créer les URLs de retour pour LigdiCash
    FORCE HTTPS pour ngrok et domaines publics
    """
    host = request.get_host()

    # FORCER HTTPS si domaine public
    if 'ngrok' in host or 'herokuapp' in host or not ('localhost' in host or '127.0.0.1' in host):
        scheme = 'https'
    else:
        scheme = request.scheme

    base_url = f"{scheme}://{host}"

    # Construire les URLs (sans token pour les paiements authentifiés)
    success_url = f"{base_url}{reverse('payments:callback_success', kwargs={'paiement_id': paiement_id})}"
    error_url = f"{base_url}{reverse('payments:callback_error', kwargs={'paiement_id': paiement_id})}"
    callback_url = f"{base_url}{reverse('payments:webhook_ligdicash')}"

    return {
        'success': success_url,
        'error': error_url,
        'callback': callback_url
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

