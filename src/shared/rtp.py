"""
Module de gestion du protocole RTP (Real-time Transport Protocol)
Implémente RFC 3550 pour le transport des flux audio en temps réel
"""

import struct
import time
import random
from dataclasses import dataclass
from typing import Optional, Callable
import threading
import socket


@dataclass
class RTPPacket:
    """
    Structure d'un paquet RTP selon RFC 3550

    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |V=2|P|X|  CC   |M|     PT      |       sequence number         |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                           timestamp                           |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |           synchronization source (SSRC) identifier            |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |            contributing source (CSRC) identifiers             |
   |                             ....                              |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                         payload data                          |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """

    version: int = 2
    padding: int = 0
    extension: int = 0
    csrc_count: int = 0
    marker: int = 0
    payload_type: int = 0  # 0=PCMU, 8=PCMA, 123=Opus
    sequence_number: int = 0
    timestamp: int = 0
    ssrc: int = 0
    payload: bytes = b''

    def to_bytes(self) -> bytes:
        """Sérialise le paquet RTP en bytes"""
        # Header RTP (12 bytes minimum)
        first_byte = (
            (self.version << 6) |
            (self.padding << 5) |
            (self.extension << 4) |
            self.csrc_count
        )
        second_byte = (
            (self.marker << 7) |
            self.payload_type
        )

        header = struct.pack(
            '!BBHII',
            first_byte,
            second_byte,
            self.sequence_number,
            self.timestamp & 0xFFFFFFFF,
            self.ssrc
        )

        return header + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> 'RTPPacket':
        """Désérialise un paquet RTP depuis des bytes"""
        if len(data) < 12:
            raise ValueError("Paquet RTP trop court")

        first_byte, second_byte, seq, ts, ssrc = struct.unpack('!BBHII', data[:12])

        packet = cls(
            version=(first_byte >> 6) & 0x03,
            padding=(first_byte >> 5) & 0x01,
            extension=(first_byte >> 4) & 0x01,
            csrc_count=first_byte & 0x0F,
            marker=(second_byte >> 7) & 0x01,
            payload_type=second_byte & 0x7F,
            sequence_number=seq,
            timestamp=ts,
            ssrc=ssrc,
            payload=data[12:]
        )

        return packet


class RTPSession:
    """
    Gère une session RTP pour l'envoi et la réception de paquets audio
    """

    # Payload types selon RFC 3551
    PAYLOAD_PCMU = 0       # G.711 μ-law
    PAYLOAD_PCMA = 8       # G.711 A-law
    PAYLOAD_OPUS = 123     # Opus (dynamic)

    def __init__(self, local_port: int = 0, payload_type: int = 0):
        self.local_port = local_port
        self.remote_addr: Optional[tuple] = None
        self.payload_type = payload_type
        self.ssrc = random.randint(1, 0xFFFFFFFF)
        self.sequence_number = random.randint(0, 65535)
        self.timestamp = random.randint(0, 0xFFFFFFFF)
        self.sample_rate = 8000  # 8 kHz pour G.711

        self.socket: Optional[socket.socket] = None
        self.running = False
        self.recv_thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_packet_received: Optional[Callable[[bytes], None]] = None
        self.on_session_started: Optional[Callable[[], None]] = None
        self.on_session_stopped: Optional[Callable[[], None]] = None

        # Statistiques
        self.packets_sent = 0
        self.packets_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0

    def start(self, remote_addr: tuple = None):
        """Démarre la session RTP"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('0.0.0.0', self.local_port))
        self.socket.settimeout(0.1)

        # Récupérer le port effectivement utilisé
        self.local_port = self.socket.getsockname()[1]

        if remote_addr:
            self.remote_addr = remote_addr

        self.running = True
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()

        if self.on_session_started:
            self.on_session_started()

        print(f"[RTP] Session démarrée - SSRC: {self.ssrc}, Port local: {self.local_port}")

    def stop(self):
        """Arrête la session RTP"""
        self.running = False
        if self.recv_thread:
            self.recv_thread.join(timeout=1.0)
        if self.socket:
            self.socket.close()
            self.socket = None

        if self.on_session_stopped:
            self.on_session_stopped()

        print(f"[RTP] Session arrêtée - Paquets envoyés: {self.packets_sent}, reçus: {self.packets_received}")

    def set_remote_addr(self, addr: tuple):
        """Définit l'adresse distante pour l'envoi"""
        self.remote_addr = addr

    def send_audio_frame(self, audio_data: bytes, marker: bool = False) -> bool:
        """
        Envoie un frame audio encapsulé dans un paquet RTP

        Args:
            audio_data: Données audio encodées
            marker: True si c'est le premier paquet d'un talkspurt

        Returns:
            True si l'envoi a réussi
        """
        if not self.socket or not self.remote_addr:
            return False

        # Incrémenter le timestamp (160 samples pour 20ms à 8kHz)
        self.timestamp = (self.timestamp + 160) & 0xFFFFFFFF

        packet = RTPPacket(
            version=2,
            payload_type=self.payload_type,
            sequence_number=self.sequence_number & 0xFFFF,
            timestamp=self.timestamp,
            ssrc=self.ssrc,
            marker=1 if marker else 0,
            payload=audio_data
        )

        try:
            self.socket.sendto(packet.to_bytes(), self.remote_addr)
            self.sequence_number += 1
            self.packets_sent += 1
            self.bytes_sent += len(audio_data)
            return True
        except socket.error as e:
            print(f"[RTP] Erreur d'envoi: {e}")
            return False

    def _recv_loop(self):
        """Boucle de réception des paquets RTP"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(2048)
                packet = RTPPacket.from_bytes(data)

                self.packets_received += 1
                self.bytes_received += len(packet.payload)

                if self.on_packet_received:
                    self.on_packet_received(packet.payload)

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[RTP] Erreur de réception: {e}")

    def get_stats(self) -> dict:
        """Retourne les statistiques de la session"""
        return {
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'ssrc': self.ssrc,
            'local_port': self.local_port,
            'remote_addr': self.remote_addr
        }


class RTCPHandler:
    """
    Gère le protocole RTCP (RTP Control Protocol) pour le contrôle qualité
    """

    def __init__(self, rtp_port: int):
        self.rtcp_port = rtp_port + 1  # RTCP utilise le port RTP + 1
        self.socket: Optional[socket.socket] = None
        self.ssrc = random.randint(1, 0xFFFFFFFF)

    def send_report(self, remote_addr: tuple, stats: dict):
        """Envoie un rapport de réception RTCP"""
        # Rapport de type Sender Report (SR) ou Receiver Report (RR)
        packet_type = 200  # SR
        length = 6  # 6 mots de 32 bits

        # NTP timestamp (simplifié)
        ntp_ts = int(time.time() * 2**32)

        header = struct.pack('!BBHII',
            (2 << 6) | 0,  # Version 2, pas de padding, 0 SSRC
            packet_type,
            length,
            self.ssrc,
            (ntp_ts >> 32) & 0xFFFFFFFF  # NTP timestamp MSW
        )

        # Envoi simplifié - implémentation complète serait plus élaborée
        pass
