# apps/payments/services/ligdicash.py

import requests
import json
import logging
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from datetime import datetime

logger = logging.getLogger(__name__)


class LigdiCashService:
    """Service pour intégrer les paiements LigdiCash"""

    def __init__(self):
        self.api_key = getattr(settings, 'LIGDICASH_API_KEY', '')
        self.auth_token = getattr(settings, 'LIGDICASH_AUTH_TOKEN', '')
        self.platform = getattr(settings, 'LIGDICASH_PLATFORM', 'live')  # live ou test

        # URLs de l'API selon la plateforme
        if self.platform == 'live':
            self.base_url = 'https://client.ligdicash.com/directpayment/api'
        else:
            self.base_url = 'https://app.ligdicash.com/pay/redirect'

        # Headers par défaut
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.auth_token}',
            'Ligdicash-Api-Key': self.api_key,
        }

        if not self.api_key or not self.auth_token:
            logger.error("Configuration LigdiCash manquante")

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

        Args:
            paiement_id: ID unique du paiement dans notre système
            montant: Montant à payer
            description: Description du paiement
            email_client: Email du client
            nom_client: Nom complet du client
            url_retour_succes: URL de retour en cas de succès
            url_retour_echec: URL de retour en cas d'échec
            url_callback: URL de callback pour notification (optionnel)

        Returns:
            Tuple (success, response_data)
        """
        try:
            # Données de la requête
            payload = {
                'commande': paiement_id,
                'montant': str(montant),
                'description': description,
                'custom': json.dumps({
                    'paiement_id': paiement_id,
                    'timestamp': timezone.now().isoformat()
                }),
                'devise': 'XOF',  # Franc CFA
                'client': {
                    'nom': nom_client,
                    'email': email_client
                },
                'urls': {
                    'success': url_retour_succes,
                    'error': url_retour_echec,
                    'cancel': url_retour_echec,
                }
            }

            # Ajouter le callback si fourni
            if url_callback:
                payload['urls']['callback'] = url_callback

            logger.info(f"Création paiement LigdiCash: {paiement_id} - {montant} XOF")

            # Appel à l'API LigdiCash
            response = requests.post(
                f"{self.base_url}/redirect",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            response_data = response.json()

            if response.status_code == 200 and response_data.get('success'):
                # Succès: récupérer l'URL de redirection
                payment_url = response_data.get('url') or response_data.get('redirect_url')
                transaction_id = response_data.get('token') or response_data.get('transaction_id')

                logger.info(f"Paiement LigdiCash créé avec succès: {transaction_id}")

                return True, {
                    'payment_url': payment_url,
                    'transaction_id': transaction_id,
                    'status': 'created',
                    'raw_response': response_data
                }
            else:
                # Échec
                error_message = response_data.get('message', 'Erreur inconnue')
                logger.error(f"Erreur création paiement LigdiCash: {error_message}")

                return False, {
                    'error': error_message,
                    'error_code': response_data.get('error_code'),
                    'raw_response': response_data
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur réseau LigdiCash: {str(e)}")
            return False, {
                'error': f'Erreur de connexion: {str(e)}',
                'error_code': 'network_error'
            }
        except json.JSONDecodeError as e:
            logger.error(f"Erreur décodage JSON LigdiCash: {str(e)}")
            return False, {
                'error': 'Réponse invalide du serveur de paiement',
                'error_code': 'json_decode_error'
            }
        except Exception as e:
            logger.error(f"Erreur inattendue LigdiCash: {str(e)}")
            return False, {
                'error': f'Erreur inattendue: {str(e)}',
                'error_code': 'unexpected_error'
            }

    def verifier_statut_paiement(self, transaction_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Vérifie le statut d'un paiement

        Args:
            transaction_id: ID de transaction LigdiCash

        Returns:
            Tuple (success, payment_data)
        """
        try:
            logger.info(f"Vérification statut paiement: {transaction_id}")

            response = requests.get(
                f"{self.base_url}/status",
                headers=self.headers,
                params={'token': transaction_id},
                timeout=30
            )

            response_data = response.json()

            if response.status_code == 200:
                status = response_data.get('status', '').lower()

                # Mapper les statuts LigdiCash vers nos statuts
                status_mapping = {
                    'success': 'CONFIRME',
                    'completed': 'CONFIRME',
                    'paid': 'CONFIRME',
                    'failed': 'ECHEC',
                    'cancelled': 'ANNULE',
                    'pending': 'EN_COURS',
                    'processing': 'EN_COURS'
                }

                notre_statut = status_mapping.get(status, 'EN_ATTENTE')

                return True, {
                    'status': notre_statut,
                    'ligdicash_status': status,
                    'amount': response_data.get('montant'),
                    'fees': response_data.get('frais', 0),
                    'transaction_date': response_data.get('date_transaction'),
                    'raw_response': response_data
                }
            else:
                error_message = response_data.get('message', 'Erreur lors de la vérification')
                logger.error(f"Erreur vérification statut: {error_message}")

                return False, {
                    'error': error_message,
                    'raw_response': response_data
                }

        except Exception as e:
            logger.error(f"Erreur vérification statut LigdiCash: {str(e)}")
            return False, {
                'error': f'Erreur lors de la vérification: {str(e)}'
            }

    def traiter_callback(self, callback_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Traite les données reçues via le callback LigdiCash

        Args:
            callback_data: Données reçues du callback

        Returns:
            Tuple (success, processed_data)
        """
        try:
            logger.info(f"Traitement callback LigdiCash: {callback_data}")

            # Extraire les informations importantes
            transaction_id = callback_data.get('token') or callback_data.get('transaction_id')
            status = callback_data.get('status', '').lower()
            montant = callback_data.get('montant') or callback_data.get('amount')
            frais = callback_data.get('frais') or callback_data.get('fees', 0)

            # Données custom (notre paiement_id)
            custom_data = callback_data.get('custom')
            if isinstance(custom_data, str):
                try:
                    custom_data = json.loads(custom_data)
                except json.JSONDecodeError:
                    custom_data = {}

            paiement_id = custom_data.get('paiement_id') if custom_data else None

            # Mapper le statut
            status_mapping = {
                'success': 'CONFIRME',
                'completed': 'CONFIRME',
                'paid': 'CONFIRME',
                'failed': 'ECHEC',
                'cancelled': 'ANNULE',
                'pending': 'EN_COURS'
            }

            notre_statut = status_mapping.get(status, 'EN_ATTENTE')

            # Valider la signature si disponible
            signature_valide = self._valider_signature(callback_data)

            return True, {
                'paiement_id': paiement_id,
                'transaction_id': transaction_id,
                'status': notre_statut,
                'ligdicash_status': status,
                'amount': montant,
                'fees': frais,
                'signature_valid': signature_valide,
                'raw_data': callback_data
            }

        except Exception as e:
            logger.error(f"Erreur traitement callback: {str(e)}")
            return False, {
                'error': f'Erreur traitement callback: {str(e)}'
            }

    def _valider_signature(self, data: Dict[str, Any]) -> bool:
        """
        Valide la signature du callback (si implémentée par LigdiCash)

        Args:
            data: Données du callback

        Returns:
            True si la signature est valide, False sinon
        """
        # À implémenter selon la documentation LigdiCash
        # pour valider l'authenticité du callback

        signature = data.get('signature')
        if not signature:
            logger.warning("Aucune signature trouvée dans le callback")
            return False

        # Logique de validation de signature
        # (dépend de l'implémentation LigdiCash)

        return True  # Par défaut, considérer comme valide

    def rembourser_paiement(
            self,
            transaction_id: str,
            montant_remboursement: Decimal,
            motif: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Initie un remboursement

        Args:
            transaction_id: ID de la transaction à rembourser
            montant_remboursement: Montant à rembourser
            motif: Motif du remboursement

        Returns:
            Tuple (success, response_data)
        """
        try:
            payload = {
                'transaction_id': transaction_id,
                'montant': str(montant_remboursement),
                'motif': motif
            }

            response = requests.post(
                f"{self.base_url}/refund",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            response_data = response.json()

            if response.status_code == 200 and response_data.get('success'):
                logger.info(f"Remboursement LigdiCash initié: {transaction_id}")
                return True, response_data
            else:
                error_message = response_data.get('message', 'Erreur remboursement')
                logger.error(f"Erreur remboursement LigdiCash: {error_message}")
                return False, {'error': error_message}

        except Exception as e:
            logger.error(f"Erreur remboursement LigdiCash: {str(e)}")
            return False, {'error': str(e)}

    def obtenir_balance(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Obtient la balance du compte marchand

        Returns:
            Tuple (success, balance_data)
        """
        try:
            response = requests.get(
                f"{self.base_url}/balance",
                headers=self.headers,
                timeout=30
            )

            response_data = response.json()

            if response.status_code == 200:
                return True, {
                    'balance': response_data.get('balance', 0),
                    'currency': response_data.get('currency', 'XOF'),
                    'last_updated': response_data.get('last_updated')
                }
            else:
                return False, {'error': 'Erreur lors de la récupération de la balance'}

        except Exception as e:
            logger.error(f"Erreur récupération balance: {str(e)}")
            return False, {'error': str(e)}

    def tester_connexion(self) -> bool:
        """
        Teste la connexion à l'API LigdiCash

        Returns:
            True si la connexion est OK, False sinon
        """
        try:
            response = requests.get(
                f"{self.base_url}/ping",
                headers=self.headers,
                timeout=10
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Test connexion LigdiCash échoué: {str(e)}")
            return False


# Instance globale du service
ligdicash_service = LigdiCashService()


# Fonctions utilitaires
def creer_urls_retour(request, paiement_id: str) -> Dict[str, str]:
    """
    Crée les URLs de retour pour LigdiCash

    Args:
        request: Objet HttpRequest
        paiement_id: ID du paiement

    Returns:
        Dict avec les URLs de retour
    """
    base_url = f"{request.scheme}://{request.get_host()}"

    return {
        'success': f"{base_url}{reverse('payments:callback_success', kwargs={'paiement_id': paiement_id})}",
        'error': f"{base_url}{reverse('payments:callback_error', kwargs={'paiement_id': paiement_id})}",
        'callback': f"{base_url}{reverse('payments:webhook_ligdicash')}"
    }


def formater_montant_ligdicash(montant: Decimal) -> str:
    """
    Formate un montant pour LigdiCash (XOF, 2 décimales)

    Args:
        montant: Montant à formater

    Returns:
        Montant formaté en string
    """
    return f"{montant:.2f}"


def valider_montant_minimum(montant: Decimal) -> bool:
    """
    Valide que le montant respecte le minimum LigdiCash

    Args:
        montant: Montant à valider

    Returns:
        True si valide, False sinon
    """
    MONTANT_MINIMUM = Decimal('100')  # 100 XOF minimum
    return montant >= MONTANT_MINIMUM

