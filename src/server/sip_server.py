"""
Serveur SIP/Proxy pour le routage des appels VoIP
Implémente un serveur registrar et proxy SIP selon RFC 3261
"""

import socket
import threading
import json
import logging
import hashlib
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.sip_messages import (
    SIPMessage, SIPRequestBuilder, SIPResponseBuilder,
    create_sdp, parse_sdp, generate_call_id
)
from shared.rtp import RTPSession


# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SIPServer')


@dataclass
class RegisteredUser:
    """Utilisateur enregistré auprès du serveur"""
    user_id: str
    username: str
    display_name: str
    contact_uri: str
    host: str
    port: int
    expires: datetime
    call_id: str = ""

    def is_expired(self) -> bool:
        return datetime.now() > self.expires


@dataclass
class ActiveCall:
    """Appel en cours"""
    call_id: str
    caller: tuple
    callee: str
    callee_contact: tuple = field(default_factory=tuple)
    caller_sdp: dict = field(default_factory=dict)
    callee_sdp: dict = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    status: str = "initiating"


class SIPRegistrar:
    """
    Gère l'enregistrement des utilisateurs SIP
    """

    def __init__(self):
        self.users: Dict[str, RegisteredUser] = {}
        self.lock = threading.Lock()

    def register(self, user_id: str, username: str, display_name: str,
                 contact_uri: str, host: str, port: int, expires: int,
                 call_id: str) -> bool:
        """Enregistre un utilisateur"""
        with self.lock:
            self.users[user_id] = RegisteredUser(
                user_id=user_id,
                username=username,
                display_name=display_name,
                contact_uri=contact_uri,
                host=host,
                port=port,
                expires=datetime.now() + timedelta(seconds=expires),
                call_id=call_id
            )
            logger.info(f"Utilisateur enregistré: {user_id} ({display_name})")
            return True

    def unregister(self, user_id: str) -> bool:
        """Désenregistre un utilisateur"""
        with self.lock:
            if user_id in self.users:
                del self.users[user_id]
                logger.info(f"Utilisateur désenregistré: {user_id}")
                return True
            return False

    def get_user(self, user_id: str) -> Optional[RegisteredUser]:
        """Récupère les informations d'un utilisateur"""
        with self.lock:
            user = self.users.get(user_id)
            if user and not user.is_expired():
                return user
            elif user:
                # Nettoyage des utilisateurs expirés
                del self.users[user_id]
            return None

    def get_all_users(self) -> Dict[str, str]:
        """Retourne la liste des utilisateurs enregistrés"""
        with self.lock:
            return {
                uid: user.display_name
                for uid, user in self.users.items()
                if not user.is_expired()
            }

    def cleanup_expired(self):
        """Nettoie les utilisateurs expirés"""
        with self.lock:
            expired = [
                uid for uid, user in self.users.items()
                if user.is_expired()
            ]
            for uid in expired:
                del self.users[uid]
            if expired:
                logger.info(f"Nettoyage de {len(expired)} utilisateurs expirés")


class SIPProxy:
    """
    Proxy SIP pour le routage des messages entre utilisateurs
    """

    def __init__(self, registrar: SIPRegistrar):
        self.registrar = registrar
        self.active_calls: Dict[str, ActiveCall] = {}
        self.auth_users = self._load_auth_users()

    def _load_auth_users(self) -> Dict[str, dict]:
        """Charge les utilisateurs authentifiés depuis la configuration"""
        try:
            with open('config/server_config.json', 'r') as f:
                config = json.load(f)
                return config.get('users', {})
        except FileNotFoundError:
            logger.warning("Fichier de configuration non trouvé")
            return {}

    def authenticate(self, user_id: str, password: str) -> bool:
        """Authentifie un utilisateur"""
        user = self.auth_users.get(user_id)
        if user and user.get('password') == password:
            return True
        return False

    def handle_invite(self, request: SIPMessage, sender_host: str, sender_port: int) -> Tuple[int, SIPMessage]:
        """
        Gère une requête INVITE pour initier un appel

        Returns:
            Tuple (status_code, response_message)
        """
        # Extraire le callee de l'URI
        callee_id = request.uri.split(':')[-1].split('@')[0]

        # Vérifier si le callee est enregistré
        callee = self.registrar.get_user(callee_id)

        if not callee:
            # Utilisateur non trouvé
            response_builder = SIPResponseBuilder(request, 404)
            return 404, response_builder.build()

        # Créer un nouvel appel
        call_id = request.headers.get('Call-ID', '')
        call = ActiveCall(
            call_id=call_id,
            caller=request.headers.get('From', '').split(';tag=')[-1] if ';tag=' in request.headers.get('From', '') else 'unknown',
            callee=callee_id,
            caller_sdp=parse_sdp(request.body) if request.body else {},
            status="ringing"
        )
        self.active_calls[call_id] = call

        logger.info(f"Nouvel appel: {call.caller} -> {callee_id}")

        # Forward INVITE au callee
        return 100, SIPResponseBuilder(request, 100).build()

    def handle_bye(self, request: SIPMessage) -> Tuple[int, SIPMessage]:
        """Gère une requête BYE pour terminer un appel"""
        call_id = request.headers.get('Call-ID', '')

        if call_id in self.active_calls:
            call = self.active_calls[call_id]
            call.status = "terminated"
            del self.active_calls[call_id]
            logger.info(f"Appel terminé: {call_id}")

        return 200, SIPResponseBuilder(request, 200).build()

    def handle_ack(self, request: SIPMessage) -> None:
        """Gère un ACK pour confirmer l'établissement d'appel"""
        call_id = request.headers.get('Call-ID', '')
        if call_id in self.active_calls:
            self.active_calls[call_id].status = "active"
            logger.info(f"Appel établi: {call_id}")

    def get_call_info(self, call_id: str) -> Optional[ActiveCall]:
        """Récupère les informations d'un appel"""
        return self.active_calls.get(call_id)


class SIPServer:
    """
    Serveur SIP principal combinant Registrar et Proxy
    """

    def __init__(self, host: str = '0.0.0.0', port: int = 5060):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False

        self.registrar = SIPRegistrar()
        self.proxy = SIPProxy(self.registrar)

        # Charger la configuration
        self.config = self._load_config()
        self._configure_from_config()

    def _load_config(self) -> dict:
        """Charge la configuration depuis le fichier"""
        try:
            with open('config/server_config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                'server': {'host': '0.0.0.0', 'sip_port': 5060},
                'users': {}
            }

    def _configure_from_config(self):
        """Configure le serveur depuis le fichier de config"""
        server_config = self.config.get('server', {})
        self.host = server_config.get('host', '0.0.0.0')
        self.port = server_config.get('sip_port', 5060)

    def start(self):
        """Démarre le serveur SIP"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))

        self.running = True

        logger.info(f"Serveur SIP démarré sur {self.host}:{self.port}")
        print(f"\n{'='*50}")
        print(f"  SERVEUR SIP VoIP")
        print(f"  Écoute sur: {self.host}:{self.port}")
        print(f"  Utilisateurs configurés: {len(self.config.get('users', {}))}")
        print(f"{'='*50}\n")

        # Thread de nettoyage des utilisateurs expirés
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

        # Boucle principale de réception
        self._recv_loop()

    def stop(self):
        """Arrête le serveur SIP"""
        self.running = False
        if self.socket:
            self.socket.close()
        logger.info("Serveur SIP arrêté")

    def _recv_loop(self):
        """Boucle principale de réception des messages SIP"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                message = SIPMessage.from_bytes(data)

                # Traiter le message dans un thread séparé
                thread = threading.Thread(
                    target=self._handle_message,
                    args=(message, addr),
                    daemon=True
                )
                thread.start()

            except socket.error as e:
                if self.running:
                    logger.error(f"Erreur de réception: {e}")
            except Exception as e:
                logger.error(f"Erreur inattendue: {e}")

    def _handle_message(self, message: SIPMessage, addr: tuple):
        """Traite un message SIP reçu"""
        logger.debug(f"Reçu de {addr}: {message.method or message.headers.get('Status', 'Unknown Response')}")

        try:
            if not message.method:
                self._handle_response(message, addr)
            elif message.method == 'REGISTER':
                self._handle_register(message, addr)
            elif message.method == 'INVITE':
                self._handle_invite(message, addr)
            elif message.method == 'ACK':
                self._handle_ack(message, addr)
            elif message.method == 'BYE':
                self._handle_bye(message, addr)
            elif message.method == 'CANCEL':
                self._handle_cancel(message, addr)
            elif message.method == 'OPTIONS':
                self._handle_options(message, addr)
            else:
                logger.warning(f"Méthode non supportée: {message.method}")

        except Exception as e:
            logger.error(f"Erreur de traitement: {e}")
            # Envoyer une erreur 500
            if message.method:
                response = SIPResponseBuilder(message, 500).build()
                self.socket.sendto(response.to_bytes(), addr)

    def _handle_register(self, message: SIPMessage, addr: tuple):
        """Gère l'enregistrement d'un utilisateur"""
        # Extraire les informations du message REGISTER
        from_header = message.headers.get('From', '')
        contact_header = message.headers.get('Contact', '')
        expires_header = message.headers.get('Expires', '3600')

        # Extraire l'identifiant utilisateur
        user_id = from_header.split(';tag=')[-1] if ';tag=' in from_header else 'unknown'

        # Vérifier l'expiration (Expires: 0 = désenregistrement)
        expires = int(expires_header)

        if expires == 0:
            # Désenregistrement
            self.registrar.unregister(user_id)
            response = SIPResponseBuilder(message, 200).build()
        else:
            # Enregistrement
            self.registrar.register(
                user_id=user_id,
                username=user_id,
                display_name=user_id,
                contact_uri=contact_header.strip('<>'),
                host=addr[0],
                port=addr[1],
                expires=expires,
                call_id=message.headers.get('Call-ID', '')
            )
            response = SIPResponseBuilder(message, 200).build()

        self.socket.sendto(response.to_bytes(), addr)

    def _handle_invite(self, message: SIPMessage, addr: tuple):
        """Gère une requête INVITE"""
        callee_id = message.uri.split(':')[-1].split('@')[0]
        callee = self.registrar.get_user(callee_id)

        if not callee:
            # Utilisateur non trouvé - 404
            response = SIPResponseBuilder(message, 404).build()
            self.socket.sendto(response.to_bytes(), addr)
            return

        # Envoyer 100 Trying
        trying = SIPResponseBuilder(message, 100).build()
        self.socket.sendto(trying.to_bytes(), addr)

        # Forward l'INVITE au callee
        callee_addr = (callee.host, callee.port)

        # Créer un nouvel INVITE pour le callee
        forward_request = SIPMessage(method='INVITE', uri=message.uri)
        forward_request.headers = message.headers.copy()
        forward_request.headers['Via'] = f"SIP/2.0/UDP {self.host}:{self.port};branch={generate_call_id()}"
        forward_request.body = message.body

        self.socket.sendto(forward_request.to_bytes(), callee_addr)
        logger.info(f"INVITE forwardé à {callee_id} ({callee_addr})")

        # Stocker l'appel en cours
        call_id = message.headers.get('Call-ID', '')
        self.proxy.active_calls[call_id] = ActiveCall(
            call_id=call_id,
            caller=addr,
            callee=callee_id,
            callee_contact=callee_addr,
            status="ringing"
        )

    def _handle_ack(self, message: SIPMessage, addr: tuple):
        """Gère un ACK"""
        call_id = message.headers.get('Call-ID', '')
        logger.info(f"ACK reçu pour l'appel {call_id}")

        if call_id in self.proxy.active_calls:
            self.proxy.active_calls[call_id].status = "active"

        # Forward ACK au callee si nécessaire
        call = self.proxy.active_calls.get(call_id)
        if call and hasattr(call, 'callee_contact'):
            message.headers['Via'] = f"SIP/2.0/UDP {self.host}:{self.port};branch={generate_call_id()}"
            self.socket.sendto(message.to_bytes(), call.callee_contact)

    def _handle_bye(self, message: SIPMessage, addr: tuple):
        """Gère une requête BYE"""
        call_id = message.headers.get('Call-ID', '')
        logger.info(f"BYE reçu pour l'appel {call_id}")

        # Envoyer 200 OK
        response = SIPResponseBuilder(message, 200).build()
        self.socket.sendto(response.to_bytes(), addr)

        # Forward BYE à l'autre partie si nécessaire
        call = self.proxy.active_calls.get(call_id)
        if call and call.callee_contact:
            forward_bye = SIPMessage(method='BYE', uri=message.uri)
            forward_bye.headers = message.headers.copy()
            forward_bye.headers['Via'] = f"SIP/2.0/UDP {self.host}:{self.port};branch={generate_call_id()}"

            # Si le BYE vient du callee, forward au caller, sinon au callee
            target_addr = call.caller if addr == call.callee_contact else call.callee_contact
            self.socket.sendto(forward_bye.to_bytes(), target_addr)

        # Supprimer l'appel
        if call_id in self.proxy.active_calls:
            del self.proxy.active_calls[call_id]

    def _handle_cancel(self, message: SIPMessage, addr: tuple):
        """Gère une requête CANCEL"""
        call_id = message.headers.get('Call-ID', '')
        logger.info(f"CANCEL reçu pour l'appel {call_id}")

        if call_id in self.proxy.active_calls:
            call = self.proxy.active_calls[call_id]
            if call.status == "ringing":
                call.status = "cancelled"
                del self.proxy.active_calls[call_id]

        # Envoyer 200 OK
        response = SIPResponseBuilder(message, 200).build()
        self.socket.sendto(response.to_bytes(), addr)

    def _handle_options(self, message: SIPMessage, addr: tuple):
        """Gère une requête OPTIONS (keepalive/capabilities)"""
        response = SIPResponseBuilder(message, 200).build()
        response.headers['Allow'] = 'INVITE, ACK, BYE, CANCEL, REGISTER, OPTIONS'
        self.socket.sendto(response.to_bytes(), addr)

    def _handle_response(self, message: SIPMessage, addr: tuple):
        """Forward une réponse SIP (100, 180, 200 OK, etc.) à l'autre partie de l'appel"""
        call_id = message.headers.get('Call-ID', '')
        if call_id in self.proxy.active_calls:
            call = self.proxy.active_calls[call_id]
            # Déterminer la destination
            if addr == call.callee_contact:
                self.socket.sendto(message.to_bytes(), call.caller)
            elif addr == call.caller and call.callee_contact:
                self.socket.sendto(message.to_bytes(), call.callee_contact)

    def _cleanup_loop(self):
        """Nettoie périodiquement les utilisateurs expirés"""
        while self.running:
            time.sleep(60)  # Toutes les minutes
            self.registrar.cleanup_expired()

    def send_response(self, request: SIPMessage, status_code: int, addr: tuple, sdp_body: str = None):
        """Envoie une réponse SIP"""
        response_builder = SIPResponseBuilder(request, status_code)
        if sdp_body:
            response_builder.set_sdp_body(sdp_body)
        response = response_builder.build()
        self.socket.sendto(response.to_bytes(), addr)


def main():
    """Point d'entrée principal"""
    import sys
    import os

    # Ajouter le parent directory au path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    server = SIPServer()

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nArrêt du serveur...")
        server.stop()
    except Exception as e:
        logger.error(f"Erreur: {e}")
        server.stop()


if __name__ == '__main__':
    main()
