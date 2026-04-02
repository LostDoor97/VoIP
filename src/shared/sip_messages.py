"""
Module de gestion des messages SIP (Session Initiation Protocol)
Implémente RFC 3261 pour l'établissement, la modification et la terminaison de sessions
"""

import uuid
import socket
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime


@dataclass
class SIPMessage:
    """Classe de base pour les messages SIP"""
    method: str = ""
    uri: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""

    def to_bytes(self) -> bytes:
        """Sérialise le message SIP en bytes"""
        lines: List[str] = []

        # Ligne de démarrage
        if self.method:
            # Message request
            first_line = f"{self.method} {self.uri} SIP/2.0"
        else:
            # Message response
            status = self.headers.get('Status', '200 OK').strip()
            if status and status.split()[0].isdigit() and len(status.split()) == 1:
                # Ajouter une raison minimale si absente
                status = f"{status} OK"
            first_line = f"SIP/2.0 {status}"

        lines.append(first_line)

        body_bytes = self.body.encode('utf-8') if self.body else b''
        # Garder Content-Length cohérent (la majorité du code attend ce header)
        self.headers['Content-Length'] = str(len(body_bytes))

        # Headers
        for header, value in self.headers.items():
            lines.append(f"{header}: {value}")

        # Fin des headers
        lines.append("")

        # Corps (SDP)
        if self.body:
            lines.append(self.body)

        return "\r\n".join(lines).encode('utf-8')

    @classmethod
    def from_bytes(cls, data: bytes) -> 'SIPMessage':
        """Désérialise un message SIP depuis des bytes"""
        text = data.decode('utf-8', errors='ignore')
        lines = text.split('\r\n')

        msg = cls()

        # Ligne de démarrage
        first_line = lines[0].split(' ')
        if first_line[0] == 'SIP/2.0':
            # Réponse
            msg.headers['Status'] = first_line[1] if len(first_line) > 1 else '200'
        else:
            # Requête
            msg.method = first_line[0]
            msg.uri = first_line[1] if len(first_line) > 1 else ''

        # Headers
        body_started = False
        for line in lines[1:]:
            if not line:
                body_started = True
                continue
            if body_started:
                msg.body += line + '\r\n'
            elif ':' in line:
                key, value = line.split(':', 1)
                msg.headers[key.strip()] = value.strip()

        msg.body = msg.body.strip()
        return msg


def generate_via_branch() -> str:
    """Génère un identifiant unique pour le header Via"""
    return f"z9hG4bK-{uuid.uuid4().hex[:16]}"


def generate_call_id() -> str:
    """Génère un Call-ID unique"""
    hostname = socket.gethostname()
    return f"{uuid.uuid4().hex[:20]}@{hostname}"


def generate_cseq() -> int:
    """Génère un numéro CSeq"""
    return random.randint(1, 10000)


class SIPRequestBuilder:
    """Constructeur de messages SIP Request"""

    def __init__(self, method: str, uri: str, from_tag: str = None):
        self.method = method
        self.uri = uri
        self.from_tag = from_tag or uuid.uuid4().hex[:10]
        self.to_tag = ""
        self.call_id = generate_call_id()
        self.cseq = generate_cseq()
        self.via_branch = generate_via_branch()
        self.headers: Dict[str, str] = {}
        self.body = ""
        self.contact = ""

    def add_header(self, name: str, value: str) -> 'SIPRequestBuilder':
        self.headers[name] = value
        return self

    def set_contact(self, host: str, port: int) -> 'SIPRequestBuilder':
        self.contact = f"sip:{self.from_tag}@{host}:{port}"
        return self

    def set_sdp_body(self, sdp: str) -> 'SIPRequestBuilder':
        self.body = sdp
        return self

    def build(self) -> SIPMessage:
        """Construit le message SIP"""
        msg = SIPMessage(method=self.method, uri=self.uri)

        # Headers obligatoires
        msg.headers['Via'] = f"SIP/2.0/UDP {socket.gethostbyname(socket.gethostname())};branch={self.via_branch}"
        msg.headers['From'] = f"<sip:{self.from_tag}@example.com>;tag={self.from_tag}"
        msg.headers['To'] = f"<sip:{self.to_tag}@example.com>{f';tag={self.to_tag}' if self.to_tag else ''}"
        msg.headers['Call-ID'] = self.call_id
        msg.headers['CSeq'] = f"{self.cseq} {self.method}"
        msg.headers['Max-Forwards'] = "70"
        msg.headers['User-Agent'] = "VoIP-Project/1.0"

        if self.contact:
            msg.headers['Contact'] = f"<{self.contact}>"

        # Headers personnalisés
        msg.headers.update(self.headers)

        # Corps SDP
        if self.body:
            msg.headers['Content-Type'] = "application/sdp"
            msg.headers['Content-Length'] = str(len(self.body))
            msg.body = self.body
        else:
            msg.headers['Content-Length'] = "0"

        return msg


class SIPResponseBuilder:
    """Constructeur de messages SIP Response"""

    def __init__(self, request: SIPMessage, status_code: int):
        self.request = request
        self.status_code = status_code
        self.status_text = self._get_status_text(status_code)
        self.headers: Dict[str, str] = {}
        self.body = ""

    def _get_status_text(self, code: int) -> str:
        texts = {
            100: "Trying",
            180: "Ringing",
            183: "Session Progress",
            200: "OK",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            407: "Proxy Authentication Required",
            408: "Request Timeout",
            480: "Temporarily Unavailable",
            486: "Busy Here",
            500: "Internal Server Error",
            503: "Service Unavailable"
        }
        return texts.get(code, "Unknown")

    def add_header(self, name: str, value: str) -> 'SIPResponseBuilder':
        self.headers[name] = value
        return self

    def set_to_tag(self, tag: str) -> 'SIPResponseBuilder':
        self.headers['To'] = self.request.headers.get('To', '')
        if ';tag=' not in self.headers['To']:
            self.headers['To'] += f";tag={tag}"
        return self

    def set_sdp_body(self, sdp: str) -> 'SIPResponseBuilder':
        self.body = sdp
        return self

    def build(self) -> SIPMessage:
        """Construit la réponse SIP"""
        msg = SIPMessage()
        msg.headers['Status'] = f"{self.status_code} {self.status_text}"

        # Reprendre les headers de la requête
        msg.headers['Via'] = self.request.headers.get('Via', '')
        msg.headers['From'] = self.request.headers.get('From', '')
        msg.headers['To'] = self.request.headers.get('To', '')
        msg.headers['Call-ID'] = self.request.headers.get('Call-ID', '')
        msg.headers['CSeq'] = self.request.headers.get('CSeq', '')

        # Headers standards
        msg.headers['Server'] = "VoIP-Project/1.0"

        # Headers personnalisés
        msg.headers.update(self.headers)

        # Corps SDP
        if self.body:
            msg.headers['Content-Type'] = "application/sdp"
            msg.headers['Content-Length'] = str(len(self.body))
            msg.body = self.body
        else:
            msg.headers['Content-Length'] = "0"

        return msg


def create_sdp(offer: bool, ip: str, port: int, codecs: List[str] = None) -> str:
    """
    Crée un corps SDP (Session Description Protocol)

    Args:
        offer: True si c'est une offre, False si c'est une réponse
        ip: Adresse IP locale
        port: Port RTP
        codecs: Liste des codecs supportés
    """
    if codecs is None:
        codecs = ['PCMU', 'PCMA']

    codec_payload_types = {
        'PCMU': 0,
        'PCMA': 8,
        'opus': 123
    }

    session_id = random.randint(1000, 9999)

    sdp_lines = [
        "v=0",
        f"o=- {session_id} {session_id} IN IP4 {ip}",
        "s=-",
        "c=IN IP4 " + ip,
        "t=0 0",
        "m=audio " + str(port) + " RTP/AVP " + " ".join(str(codec_payload_types.get(c, 123)) for c in codecs),
        "a=rtpmap:0 PCMU/8000",
        "a=rtpmap:8 PCMA/8000",
        "a=rtpmap:123 opus/48000/2",
        "a=sendrecv" if offer else "a=recvonly"
    ]

    return "\r\n".join(sdp_lines)


def parse_sdp(sdp_body: str) -> Dict:
    """Parse un corps SDP et extrait les informations"""
    result = {
        'ip': '',
        'port': 0,
        'codecs': []
    }

    for raw_line in sdp_body.split('\r\n'):
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith('c=IN IP4 '):
            parts = line.split()
            if len(parts) >= 3:
                result['ip'] = parts[2]
        elif line.startswith('m=audio '):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                result['port'] = int(parts[1])
        elif line.startswith('a=rtpmap:'):
            # Format: a=rtpmap:<pt> <encoding>/<clock>[/<channels>]
            parts = line.split()
            if len(parts) >= 2:
                encoding = parts[1].split('/')[0].strip()
                if encoding and encoding not in result['codecs']:
                    result['codecs'].append(encoding)

    return result
