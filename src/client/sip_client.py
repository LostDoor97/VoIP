"""
Client SIP pour l'application VoIP
Gère l'enregistrement, les appels et la communication audio
"""

import socket
import threading
import json
import logging
import time
import random
from typing import Optional, Dict, Callable
from dataclasses import dataclass
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.sip_messages import (
    SIPMessage, SIPRequestBuilder, SIPResponseBuilder,
    create_sdp, parse_sdp, generate_call_id, generate_via_branch
)
from shared.rtp import RTPSession
from shared.codecs import AudioCodecManager
from shared.stun import get_stun_mapped_address
from client.audio_handler import create_audio_handler, AudioHandler, SimulatedAudioHandler, AudioConfig


# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SIPClient')


@dataclass
class CallState:
    """État d'un appel en cours"""
    call_id: str
    remote_user: str
    status: str  # initiating, ringing, active, on_hold, terminated
    local_sdp: dict = None
    remote_sdp: dict = None
    start_time: datetime = None
    end_time: datetime = None


class SIPClient:
    """
    Client SIP complet pour les communications VoIP
    """

    def __init__(self, config: dict = None):
        self.config = config or self._load_default_config()

        # Informations utilisateur
        self.user_id = self.config.get('client', {}).get('user_id', '1001')
        self.username = self.config.get('client', {}).get('username', 'user1001')
        self.display_name = self.config.get('client', {}).get('display_name', 'User')
        self.server_host = self.config.get('client', {}).get('server_host', 'localhost')
        self.server_port = self.config.get('client', {}).get('server_port', 5060)

        # Configuration réseau (STUN)
        network_config = self.config.get('network', {})
        self.stun_enabled = network_config.get('stun_enabled', False)
        self.stun_server = network_config.get('stun_server', 'stun.l.google.com')
        self.stun_port = int(network_config.get('stun_port', 19302))
        self.stun_timeout = float(network_config.get('stun_timeout', 1.5))

        # Configuration audio
        audio_config = self.config.get('audio', {})
        self.audio_config = AudioConfig(
            sample_rate=audio_config.get('sample_rate', 8000),
            channels=audio_config.get('channels', 1),
            frame_size=audio_config.get('frame_size', 160),
            codec=audio_config.get('codec', 'PCMU')
        )

        # Socket SIP
        self.sip_socket: Optional[socket.socket] = None
        self.sip_port = self.config.get('client', {}).get('local_sip_port', 0)
        self.running = False

        # Session RTP
        self.rtp_session: Optional[RTPSession] = None
        self.rtp_port = self.config.get('client', {}).get('local_rtp_port', 0)

        # État des appels
        self.current_call: Optional[CallState] = None
        self.call_history: list = []

        # Contacts
        self.contacts = self.config.get('contacts', [])
        self.registered_users: Dict[str, str] = {}

        # Codec manager
        self.codec_manager = AudioCodecManager(self.audio_config.codec)

        # Handler audio
        use_simulation = self.config.get('client', {}).get('use_simulation', False)
        self.audio_handler = create_audio_handler(use_simulation, self.audio_config)

        # Callbacks
        self.on_call_started: Optional[Callable[[str], None]] = None
        self.on_call_ended: Optional[Callable[[str], None]] = None
        self.on_incoming_call: Optional[Callable[[str], None]] = None
        self.on_registration_success: Optional[Callable[[], None]] = None
        self.on_registration_failed: Optional[Callable[[str], None]] = None
        self.on_call_state_changed: Optional[Callable[[str], None]] = None

        # Threads
        self.sip_recv_thread: Optional[threading.Thread] = None
        self.registration_thread: Optional[threading.Thread] = None

    def _load_default_config(self) -> dict:
        """Charge la configuration par défaut"""
        try:
            with open('config/client_config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                'client': {
                    'user_id': '1001',
                    'username': 'user1001',
                    'display_name': 'User',
                    'server_host': 'localhost',
                    'server_port': 5060,
                    'local_rtp_port': 8000
                },
                'audio': {
                    'sample_rate': 8000,
                    'channels': 1,
                    'frame_size': 160,
                    'codec': 'PCMU'
                },
                'network': {
                    'stun_enabled': False,
                    'stun_server': 'stun.l.google.com',
                    'stun_port': 19302,
                    'stun_timeout': 1.5
                },
                'contacts': []
            }

    def _get_advertised_rtp_endpoint(self) -> tuple[str, int]:
        """Retourne l'IP/port RTP à annoncer dans le SDP (local ou public via STUN)."""
        self._ensure_rtp_session()

        advertised_ip = self._get_local_ip()
        advertised_port = self.rtp_port

        if self.stun_enabled and self.rtp_session and self.rtp_session.socket:
            try:
                mapped = get_stun_mapped_address(
                    udp_socket=self.rtp_session.socket,
                    stun_host=self.stun_server,
                    stun_port=self.stun_port,
                    timeout=self.stun_timeout,
                )
                if mapped:
                    advertised_ip, advertised_port = mapped
                    logger.info(f"STUN mapping RTP: {advertised_ip}:{advertised_port}")
                else:
                    logger.warning("STUN actif mais mapping introuvable, fallback IP locale")
            except Exception as e:
                logger.warning(f"Échec STUN ({self.stun_server}:{self.stun_port}): {e}")

        return advertised_ip, advertised_port

    def start(self):
        """Démarre le client SIP"""
        # Créer le socket SIP
        self.sip_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sip_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sip_socket.bind(('0.0.0.0', self.sip_port))
        self.sip_port = self.sip_socket.getsockname()[1]
        self.sip_socket.settimeout(0.1)

        self.running = True

        # Démarrer le thread de réception SIP
        self.sip_recv_thread = threading.Thread(target=self._sip_recv_loop, daemon=True)
        self.sip_recv_thread.start()

        # Démarrer le thread de ré-enregistrement périodique
        self.registration_thread = threading.Thread(target=self._registration_loop, daemon=True)
        self.registration_thread.start()

        # S'enregistrer auprès du serveur
        self.register()

        logger.info(f"Client SIP démarré - Utilisateur: {self.user_id} ({self.display_name})")
        print(f"\n{'='*50}")
        print(f"  CLIENT SIP VoIP")
        print(f"  Utilisateur: {self.user_id} - {self.display_name}")
        print(f"  Serveur: {self.server_host}:{self.server_port}")
        print(f"{'='*50}\n")

    def stop(self):
        """Arrête le client SIP"""
        self.running = False

        # Se désenregistrer
        self.unregister()

        # Terminer l'appel en cours
        if self.current_call:
            self.hangup()

        # Arrêter l'audio
        self.audio_handler.stop_capture()
        self.audio_handler.stop_playback()

        # Arrêter RTP
        if self.rtp_session:
            self.rtp_session.stop()

        # Fermer le socket SIP
        if self.sip_socket:
            self.sip_socket.close()

        logger.info("Client SIP arrêté")

    def _get_local_ip(self) -> str:
        """Récupère l'adresse IP locale"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((self.server_host, self.server_port))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'

    def _sip_recv_loop(self):
        """Boucle de réception des messages SIP"""
        while self.running:
            try:
                data, addr = self.sip_socket.recvfrom(4096)
                message = SIPMessage.from_bytes(data)
                self._handle_message(message, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Erreur de réception SIP: {e}")

    def _handle_message(self, message: SIPMessage, addr: tuple):
        """Traite un message SIP reçu"""
        # Vérifier si c'est une réponse ou une requête
        if 'Status' in message.headers:
            # C'est une réponse
            self._handle_response(message)
        else:
            # C'est une requête
            self._handle_request(message, addr)

    def _handle_response(self, message: SIPMessage):
        """Gère une réponse SIP"""
        status = int(message.headers.get('Status', '200').split()[0])
        method = message.headers.get('CSeq', '').split()[-1] if 'CSeq' in message.headers else ''
        call_id = message.headers.get('Call-ID', '')

        logger.debug(f"Réponse reçue: {status} {method}")

        if method == 'REGISTER':
            if status == 200:
                logger.info("Enregistrement réussi")
                if self.on_registration_success:
                    self.on_registration_success()
            else:
                logger.error(f"Échec enregistrement: {status}")
                if self.on_registration_failed:
                    self.on_registration_failed(f"Erreur {status}")

        elif method == 'INVITE':
            if status == 100:
                logger.info("Serveur traite l'INVITE (Trying)")
                self._update_call_state(call_id, 'initiating')
            elif status == 180:
                logger.info("Le distant sonne (Ringing)")
                self._update_call_state(call_id, 'ringing')
            elif status == 200:
                logger.info("Appel accepté (OK)")
                self._handle_invite_ok(message)
            elif status >= 400:
                logger.error(f"Échec de l'appel: {status}")
                self._handle_call_failure(call_id, status)

        elif method == 'BYE':
            if status == 200:
                logger.info("Appel terminé (BYE OK)")
                self._handle_call_ended()

    def _handle_request(self, message: SIPMessage, addr: tuple):
        """Gère une requête SIP entrante"""
        method = message.method

        if method == 'INVITE':
            self._handle_incoming_invite(message, addr)
        elif method == 'BYE':
            self._handle_incoming_bye(message, addr)
        elif method == 'ACK':
            logger.info("ACK reçu")
        elif method == 'CANCEL':
            self._handle_incoming_cancel(message, addr)

    def _handle_incoming_invite(self, message: SIPMessage, addr: tuple):
        """Gère un INVITE entrant (appel reçu)"""
        call_id = message.headers.get('Call-ID', '')
        from_header = message.headers.get('From', '')

        # Extraire l'identifiant de l'appelant
        caller_id = from_header.split(';tag=')[-1] if ';tag=' in from_header else 'unknown'

        logger.info(f"Appel entrant de {caller_id}")

        # Créer l'état d'appel
        self.current_call = CallState(
            call_id=call_id,
            remote_user=caller_id,
            status='ringing',
            remote_sdp=parse_sdp(message.body) if message.body else None
        )

        # Envoyer 100 Trying
        trying = SIPResponseBuilder(message, 100).build()
        self.sip_socket.sendto(trying.to_bytes(), addr)

        # Envoyer 180 Ringing
        ringing = SIPResponseBuilder(message, 180).build()
        self.sip_socket.sendto(ringing.to_bytes(), addr)

        # Notification callback
        if self.on_incoming_call:
            self.on_incoming_call(caller_id)

    def _handle_incoming_bye(self, message: SIPMessage, addr: tuple):
        """Gère un BYE entrant (l'autre partie raccroche)"""
        logger.info("BYE reçu - l'appelant a raccroché")

        # Envoyer 200 OK
        response = SIPResponseBuilder(message, 200).build()
        self.sip_socket.sendto(response.to_bytes(), addr)

        self._handle_call_ended()

    def _handle_incoming_cancel(self, message: SIPMessage, addr: tuple):
        """Gère un CANCEL entrant"""
        logger.info("CANCEL reçu - appel annulé")

        response = SIPResponseBuilder(message, 200).build()
        self.sip_socket.sendto(response.to_bytes(), addr)

        self._handle_call_ended()

    def _handle_invite_ok(self, message: SIPMessage):
        """Gère une réponse 200 OK à un INVITE"""
        call_id = message.headers.get('Call-ID', '')

        # Parser le SDP distant
        if message.body:
            remote_sdp = parse_sdp(message.body)
            if self.current_call:
                self.current_call.remote_sdp = remote_sdp

        # Envoyer ACK
        ack_builder = SIPRequestBuilder('ACK', message.uri)
        ack_builder.to_tag = message.headers.get('To', '').split(';tag=')[-1] if ';tag=' in message.headers.get('To', '') else ''
        ack_builder.call_id = call_id
        ack_builder.headers['Via'] = f"SIP/2.0/UDP {self._get_local_ip()};branch={generate_via_branch()}"
        ack = ack_builder.build()
        self.sip_socket.sendto(ack.to_bytes(), (self.server_host, self.server_port))

        # Démarrer la session RTP
        if self.current_call and self.current_call.remote_sdp:
            self._start_rtp_session(self.current_call.remote_sdp)

        # Mettre à jour l'état
        self._update_call_state(call_id, 'active')

        # Démarrer l'audio
        self.audio_handler.start_playback()
        self.audio_handler.start_capture(callback=self._send_audio)

        if self.on_call_started:
            self.on_call_started(self.current_call.remote_user)

    def _handle_call_failure(self, call_id: str, status: int):
        """Gère l'échec d'un appel"""
        self._update_call_state(call_id, 'terminated')
        self.current_call = None

    def _handle_call_ended(self):
        """Gère la fin d'un appel"""
        if self.current_call:
            self.current_call.end_time = datetime.now()
            self.current_call.status = 'terminated'

            # Ajouter à l'historique
            self.call_history.append({
                'type': 'incoming' if self.current_call.start_time else 'outgoing',
                'remote_user': self.current_call.remote_user,
                'start_time': self.current_call.start_time,
                'end_time': self.current_call.end_time,
                'duration': (self.current_call.end_time - self.current_call.start_time) if self.current_call.start_time else None
            })

            # Arrêter l'audio et RTP
            self.audio_handler.stop_capture()
            self.audio_handler.stop_playback()
            if self.rtp_session:
                self.rtp_session.stop()
                self.rtp_session = None

            remote_user = self.current_call.remote_user
            self.current_call = None

            if self.on_call_ended:
                self.on_call_ended(remote_user)

            logger.info(f"Appel terminé avec {remote_user}")

    def _update_call_state(self, call_id: str, status: str):
        """Met à jour l'état d'un appel"""
        if self.current_call and self.current_call.call_id == call_id:
            self.current_call.status = status
            if self.on_call_state_changed:
                self.on_call_state_changed(status)

    def register(self):
        """Envoie une requête REGISTER au serveur"""
        local_ip = self._get_local_ip()

        builder = SIPRequestBuilder('REGISTER', f'sip:{self.server_host}')
        builder.from_tag = self.user_id
        builder.set_contact(local_ip, self.sip_port)
        builder.add_header('Expires', '3600')
        builder.add_header('Via', f"SIP/2.0/UDP {local_ip};branch={generate_via_branch()}")

        request = builder.build()
        self.sip_socket.sendto(request.to_bytes(), (self.server_host, self.server_port))

        logger.info(f"REGISTER envoyé pour {self.user_id}")

    def unregister(self):
        """Se désenregistre du serveur"""
        local_ip = self._get_local_ip()

        builder = SIPRequestBuilder('REGISTER', f'sip:{self.server_host}')
        builder.from_tag = self.user_id
        builder.set_contact(local_ip, self.sip_port)
        builder.add_header('Expires', '0')
        builder.add_header('Via', f"SIP/2.0/UDP {local_ip};branch={generate_via_branch()}")

        request = builder.build()
        self.sip_socket.sendto(request.to_bytes(), (self.server_host, self.server_port))

        logger.info("REGISTER (expire=0) envoyé")

    def _registration_loop(self):
        """Ré-enregistrement périodique"""
        while self.running:
            time.sleep(300)  # Toutes les 5 minutes
            if self.running:
                self.register()

    def call(self, callee_id: str):
        """
        Initie un appel vers un utilisateur

        Args:
            callee_id: Identifiant de l'utilisateur à appeler
        """
        if self.current_call:
            logger.warning("Un appel est déjà en cours")
            return

        local_ip = self._get_local_ip()
        advertised_ip, advertised_port = self._get_advertised_rtp_endpoint()
        
        # Créer le SDP d'offre
        sdp = create_sdp(offer=True, ip=advertised_ip, port=advertised_port)

        # Créer l'INVITE
        builder = SIPRequestBuilder('INVITE', f'sip:{callee_id}@{self.server_host}')
        builder.from_tag = self.user_id
        builder.set_contact(local_ip, self.sip_port)
        builder.set_sdp_body(sdp)
        builder.add_header('Via', f"SIP/2.0/UDP {local_ip};branch={generate_via_branch()}")
        builder.add_header('Content-Type', 'application/sdp')

        request = builder.build()

        # Créer l'état d'appel
        self.current_call = CallState(
            call_id=builder.call_id,
            remote_user=callee_id,
            status='initiating',
            local_sdp=parse_sdp(sdp),
            start_time=datetime.now()
        )

        # Envoyer l'INVITE
        self.sip_socket.sendto(request.to_bytes(), (self.server_host, self.server_port))

        logger.info(f"INVITE envoyé à {callee_id}")

        if self.on_call_state_changed:
            self.on_call_state_changed('initiating')

    def accept_call(self):
        """Accepte un appel entrant"""
        if not self.current_call:
            return

        if self.current_call.status not in ('ringing', 'initiating'):
            logger.warning(f"accept_call ignoré: état actuel={self.current_call.status}")
            return

        local_ip = self._get_local_ip()
        advertised_ip, advertised_port = self._get_advertised_rtp_endpoint()
        
        # Créer le SDP de réponse
        sdp = create_sdp(offer=False, ip=advertised_ip, port=advertised_port)

        # Envoyer 200 OK
        # Note: Dans une implémentation complète, il faudrait reconstruire la réponse correctement
        builder = SIPRequestBuilder('INVITE', f'sip:{self.current_call.remote_user}@{self.server_host}')
        builder.to_tag = self.user_id
        builder.call_id = self.current_call.call_id
        builder.set_sdp_body(sdp)

        # Envoyer directement un 200 OK
        ok_response = self._create_200_ok(sdp)
        self.sip_socket.sendto(ok_response.to_bytes(), (self.server_host, self.server_port))

        # Démarrer RTP et audio
        self._start_rtp_session(self.current_call.remote_sdp)
        self.audio_handler.start_playback()
        self.audio_handler.start_capture(callback=self._send_audio)

        self.current_call.status = 'active'

        if self.on_call_started:
            self.on_call_started(self.current_call.remote_user)

    def _create_200_ok(self, sdp: str) -> SIPMessage:
        """Crée une réponse 200 OK pour un INVITE"""
        response = SIPMessage()
        response.headers['Status'] = '200 OK'
        response.headers['Via'] = f"SIP/2.0/UDP {self._get_local_ip()};branch={generate_via_branch()}"
        response.headers['From'] = f"<sip:{self.current_call.remote_user}@example.com>;tag={self.current_call.remote_user}"
        response.headers['To'] = f"<sip:{self.user_id}@example.com>;tag={self.user_id}"
        response.headers['Call-ID'] = self.current_call.call_id
        response.headers['CSeq'] = '1 INVITE'
        response.headers['Contact'] = f"<sip:{self.user_id}@{self._get_local_ip()}:{self.sip_port}>"
        response.headers['Content-Type'] = 'application/sdp'
        response.headers['Content-Length'] = str(len(sdp))
        response.body = sdp
        return response

    def reject_call(self):
        """Rejette un appel entrant"""
        if not self.current_call:
            return

        # Envoyer 486 Busy Here ou 603 Decline
        response = SIPMessage()
        response.headers['Status'] = '603 Decline'
        response.headers['Via'] = f"SIP/2.0/UDP {self._get_local_ip()};branch={generate_via_branch()}"
        response.headers['From'] = f"<sip:{self.current_call.remote_user}@example.com>;tag={self.current_call.remote_user}"
        response.headers['To'] = f"<sip:{self.user_id}@example.com>;tag={self.user_id}"
        response.headers['Call-ID'] = self.current_call.call_id
        response.headers['CSeq'] = '1 INVITE'
        response.headers['Content-Length'] = '0'

        self.sip_socket.sendto(response.to_bytes(), (self.server_host, self.server_port))

        self.current_call = None

    def hangup(self):
        """Termine un appel en cours"""
        if not self.current_call:
            return

        call_status = self.current_call.status
        method = 'CANCEL' if call_status in ('initiating', 'ringing') else 'BYE'

        builder = SIPRequestBuilder(method, f'sip:{self.current_call.remote_user}@{self.server_host}')
        builder.call_id = self.current_call.call_id
        builder.from_tag = self.user_id
        builder.add_header('Via', f"SIP/2.0/UDP {self._get_local_ip()};branch={generate_via_branch()}")

        request = builder.build()
        self.sip_socket.sendto(request.to_bytes(), (self.server_host, self.server_port))

        logger.info(f"{method} envoyé à {self.current_call.remote_user}")

        # Arrêter audio immédiatement
        self.audio_handler.stop_capture()
        self.audio_handler.stop_playback()

        if self.rtp_session:
            self.rtp_session.stop()
            self.rtp_session = None

        self.current_call = None

    def _ensure_rtp_session(self):
        if not self.rtp_session:
            self.rtp_session = RTPSession(
                local_port=self.rtp_port,
                payload_type=0
            )
            self.rtp_session.on_packet_received = self._receive_audio
            self.rtp_session.start()
            self.rtp_port = self.rtp_session.local_port

    def _start_rtp_session(self, remote_sdp: dict):
        """Démarre la session RTP"""
        if not remote_sdp or 'ip' not in remote_sdp or 'port' not in remote_sdp:
            logger.warning("SDP invalide pour RTP")
            return

        # Négocier le codec
        remote_codecs = remote_sdp.get('codecs', ['PCMU'])
        local_codecs = self.codec_manager.get_supported_codecs()
        selected_codec = self.codec_manager.negotiate_codecs(local_codecs, remote_codecs)

        logger.info(f"Codec négocié: {selected_codec}")

        self._ensure_rtp_session()

        self.rtp_session.payload_type = self.codec_manager.preferred_codec == 'PCMU' and 0 or 8
        self.rtp_session.set_remote_addr((remote_sdp['ip'], remote_sdp['port']))

    def _send_audio(self, encoded_data: bytes):
        """Envoie des données audio via RTP"""
        if self.rtp_session:
            self.rtp_session.send_audio_frame(encoded_data)

    def _receive_audio(self, payload: bytes):
        """Reçoit des données audio de RTP"""
        self.audio_handler.receive_rtp_packet(payload)

    def send_dtmf(self, digit: str):
        """Envoie un ton DTMF"""
        # Implémentation simplifiée - DTMF via RTP (RFC 2833)
        if self.rtp_session and self.rtp_session.remote_addr:
            # DTMF event packet (simplifié)
            dtmf_event = bytes([
                ord(digit),  # Event ID
                0,           # Volume
                0, 0         # Duration
            ])
            self.rtp_session.send_audio_frame(dtmf_event, marker=True)

    def get_call_duration(self) -> str:
        """Retourne la durée de l'appel en cours"""
        if not self.current_call or not self.current_call.start_time:
            return "00:00"

        elapsed = datetime.now() - self.current_call.start_time
        minutes = int(elapsed.total_seconds() // 60)
        seconds = int(elapsed.total_seconds() % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def get_stats(self) -> dict:
        """Retourne les statistiques du client"""
        stats = {
            'user_id': self.user_id,
            'display_name': self.display_name,
            'server': f"{self.server_host}:{self.server_port}",
            'current_call': self.current_call.remote_user if self.current_call else None,
            'call_state': self.current_call.status if self.current_call else None,
            'call_history_count': len(self.call_history)
        }

        if self.rtp_session:
            stats['rtp'] = self.rtp_session.get_stats()

        stats['audio'] = self.audio_handler.get_stats()

        return stats


def main():
    """Point d'entrée principal pour tester le client"""
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Charger la configuration
    try:
        with open('config/client_config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {}

    client = SIPClient(config)

    def on_call_started(remote_user):
        print(f"\n[Appel] Connecté avec {remote_user}")
        print("  Parlez maintenant... (Ctrl+C pour raccrocher)")

    def on_call_ended(remote_user):
        print(f"\n[Appel] Terminé avec {remote_user}")

    def on_incoming_call(caller_id):
        print(f"\n[Appel] Appel entrant de {caller_id}")
        print("  Tapez 'accept' pour répondre ou 'reject' pour refuser")

    client.on_call_started = on_call_started
    client.on_call_ended = on_call_ended
    client.on_incoming_call = on_incoming_call

    try:
        client.start()

        # Boucle interactive simple
        print("\nCommandes disponibles:")
        print("  call <numero> - Appeler un utilisateur")
        print("  hangup        - Raccrocher")
        print("  stats         - Afficher les statistiques")
        print("  quit          - Quitter")

        while True:
            try:
                cmd = input("\n> ").strip()

                if cmd.startswith('call '):
                    callee = cmd.split(' ')[1]
                    client.call(callee)
                elif cmd == 'hangup':
                    client.hangup()
                elif cmd == 'stats':
                    print(json.dumps(client.get_stats(), indent=2, default=str))
                elif cmd == 'quit':
                    break
                else:
                    print("Commande inconnue")

            except KeyboardInterrupt:
                if client.current_call:
                    client.hangup()
                continue

    except KeyboardInterrupt:
        print("\nArrêt...")
    finally:
        client.stop()


if __name__ == '__main__':
    main()
