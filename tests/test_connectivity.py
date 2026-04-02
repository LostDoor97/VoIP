"""
Scripts de test de connectivité pour le projet VoIP
Teste la communication client-serveur et les appels
"""

import socket
import sys
import os
import time
import threading

# Ajouter le parent directory au path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from shared.sip_messages import SIPMessage, SIPRequestBuilder, generate_via_branch


class TestResult:
    """Classe pour stocker les résultats de test"""
    def __init__(self, name: str):
        self.name = name
        self.success = False
        self.message = ""
        self.details = ""

    def __str__(self):
        status = "✓ PASS" if self.success else "✗ FAIL"
        return f"{status} - {self.name}\n  {self.message}\n  {self.details}"


def test_sip_server_reachable(host: str = 'localhost', port: int = 5060) -> TestResult:
    """Teste si le serveur SIP est accessible"""
    result = TestResult("Serveur SIP accessible")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)

        # Envoyer un message OPTIONS (keepalive)
        builder = SIPRequestBuilder('OPTIONS', f'sip:{host}')
        builder.add_header('Via', f"SIP/2.0/UDP localhost;branch={generate_via_branch()}")
        request = builder.build()

        sock.sendto(request.to_bytes(), (host, port))

        # Attendre une réponse
        data, addr = sock.recvfrom(4096)
        response = SIPMessage.from_bytes(data)

        if '200' in response.headers.get('Status', ''):
            result.success = True
            result.message = f"Serveur répond sur {host}:{port}"
            result.details = f"Réponse: {response.headers.get('Status', '')}"
        else:
            result.success = False
            result.message = f"Réponse inattendue: {response.headers.get('Status', '')}"

        sock.close()

    except socket.timeout:
        result.success = False
        result.message = "Timeout - Le serveur ne répond pas"
    except ConnectionRefusedError:
        result.success = False
        result.message = "Connexion refusée - Le serveur n'est pas démarré"
    except Exception as e:
        result.success = False
        result.message = f"Erreur: {e}"

    return result


def test_sip_register(host: str = 'localhost', port: int = 5060, user_id: str = '1001') -> TestResult:
    """Teste l'enregistrement d'un utilisateur"""
    result = TestResult("Enregistrement SIP (REGISTER)")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        sock.bind(('0.0.0.0', 0))  # Port aléatoire

        # Envoyer REGISTER
        builder = SIPRequestBuilder('REGISTER', f'sip:{host}')
        builder.from_tag = user_id
        builder.set_contact('localhost', sock.getsockname()[1])
        builder.add_header('Expires', '60')
        builder.add_header('Via', f"SIP/2.0/UDP localhost;branch={generate_via_branch()}")
        request = builder.build()

        sock.sendto(request.to_bytes(), (host, port))

        # Attendre la réponse
        data, addr = sock.recvfrom(4096)
        response = SIPMessage.from_bytes(data)

        status = response.headers.get('Status', '')

        if '200' in status:
            result.success = True
            result.message = f"Utilisateur {user_id} enregistré avec succès"
        elif '401' in status or '407' in status:
            result.success = True  # Authentification requise - comportement normal
            result.message = "Authentification requise (comportement attendu)"
        else:
            result.success = False
            result.message = f"Statut: {status}"

        # Envoyer unregister
        builder2 = SIPRequestBuilder('REGISTER', f'sip:{host}')
        builder2.from_tag = user_id
        builder2.set_contact('localhost', sock.getsockname()[1])
        builder2.add_header('Expires', '0')
        builder2.add_header('Via', f"SIP/2.0/UDP localhost;branch={generate_via_branch()}")
        sock.sendto(builder2.build().to_bytes(), (host, port))

        sock.close()

    except socket.timeout:
        result.success = False
        result.message = "Timeout - Pas de réponse du serveur"
    except Exception as e:
        result.success = False
        result.message = f"Erreur: {e}"

    return result


def test_sip_invite(host: str = 'localhost', port: int = 5060, caller: str = '1001', callee: str = '1002') -> TestResult:
    """Teste l'initiation d'un appel (INVITE)"""
    result = TestResult("Initiation d'appel (INVITE)")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        sock.bind(('0.0.0.0', 0))

        # Créer un SDP simple
        sdp = "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio 8000 RTP/AVP 0 8\r\na=rtpmap:0 PCMU/8000\r\na=rtpmap:8 PCMA/8000\r\n"

        # Envoyer INVITE
        builder = SIPRequestBuilder('INVITE', f'sip:{callee}@{host}')
        builder.from_tag = caller
        builder.set_contact('localhost', sock.getsockname()[1])
        builder.set_sdp_body(sdp)
        builder.add_header('Via', f"SIP/2.0/UDP localhost;branch={generate_via_branch()}")
        request = builder.build()

        sock.sendto(request.to_bytes(), (host, port))

        # Attendre la réponse (100 Trying ou 404 Not Found)
        data, addr = sock.recvfrom(4096)
        response = SIPMessage.from_bytes(data)

        status = response.headers.get('Status', '')
        status_code = int(status.split()[0]) if status.split()[0].isdigit() else 0

        # 100, 180, 200, 404, 480 sont des réponses valides
        if status_code in [100, 180, 200, 404, 480]:
            result.success = True
            result.message = f"Réponse valide reçue: {status}"
            if status_code == 404:
                result.details = "Utilisateur callee non enregistré (normal en test isolé)"
            elif status_code == 480:
                result.details = "Utilisateur temporairement indisponible"
        else:
            result.success = False
            result.message = f"Statut inattendu: {status}"

        sock.close()

    except socket.timeout:
        result.success = False
        result.message = "Timeout - Pas de réponse"
    except Exception as e:
        result.success = False
        result.message = f"Erreur: {e}"

    return result


def test_rtp_port_available(start_port: int = 10000) -> TestResult:
    """Teste la disponibilité des ports RTP"""
    result = TestResult("Ports RTP disponibles")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', start_port))
        sock.close()

        result.success = True
        result.message = f"Port {start_port} disponible pour RTP"

    except OSError as e:
        result.success = False
        result.message = f"Port {start_port} non disponible: {e}"
    except Exception as e:
        result.success = False
        result.message = f"Erreur: {e}"

    return result


def test_codec_g711() -> TestResult:
    """Teste l'encodage/décodage G.711"""
    result = TestResult("Codec G.711 (PCMU/PCMA)")

    try:
        from shared.codecs import G711Codec

        # Générer un signal test (sinusoïde simple)
        import math
        samples = []
        for i in range(160):  # 20ms à 8kHz
            value = int(10000 * math.sin(2 * math.pi * 440 * i / 8000))
            samples.append(value)

        # Convertir en bytes
        import array
        pcm_data = array.array('h', samples).tobytes()

        # Encoder en μ-law
        encoded = G711Codec.encode_pcmu(pcm_data)

        # Décoder
        decoded = G711Codec.decode_pcmu(encoded)

        # Vérifier que la taille correspond
        if len(encoded) == 160 and len(decoded) == 320:  # 160 bytes encoded, 320 bytes decoded (16-bit)
            result.success = True
            result.message = "Encodage/Décodage G.711 fonctionnel"
            result.details = f"Taille: {len(pcm_data)} -> {len(encoded)} -> {len(decoded)} bytes"
        else:
            result.success = False
            result.message = f"Tailles inattendues: {len(pcm_data)} -> {len(encoded)} -> {len(decoded)}"

    except ImportError as e:
        result.success = False
        result.message = f"Module non disponible: {e}"
    except Exception as e:
        result.success = False
        result.message = f"Erreur: {e}"

    return result


def test_rtp_packet() -> TestResult:
    """Teste la création et parsing de paquets RTP"""
    result = TestResult("Paquets RTP")

    try:
        from shared.rtp import RTPPacket

        # Créer un paquet RTP
        packet = RTPPacket(
            version=2,
            payload_type=0,  # PCMU
            sequence_number=12345,
            timestamp=67890,
            ssrc=0x12345678,
            payload=b'\x80\x81\x82\x83'  # Données μ-law test
        )

        # Sérialiser
        data = packet.to_bytes()

        # Désérialiser
        parsed = RTPPacket.from_bytes(data)

        # Vérifier
        if (parsed.version == 2 and
            parsed.payload_type == 0 and
            parsed.sequence_number == 12345 and
            parsed.timestamp == 67890 and
            parsed.ssrc == 0x12345678 and
            parsed.payload == b'\x80\x81\x82\x83'):

            result.success = True
            result.message = "Création et parsing RTP fonctionnels"
            result.details = f"Header: 12 bytes + {len(parsed.payload)} bytes payload"
        else:
            result.success = False
            result.message = "Données corrompues après sérialisation"

    except Exception as e:
        result.success = False
        result.message = f"Erreur: {e}"

    return result


def test_sdp_create_parse() -> TestResult:
    """Teste la création et parsing SDP"""
    result = TestResult("SDP (Session Description Protocol)")

    try:
        from shared.sip_messages import create_sdp, parse_sdp

        # Créer un SDP
        sdp = create_sdp(
            offer=True,
            ip='192.168.1.100',
            port=8000,
            codecs=['PCMU', 'PCMA']
        )

        # Parser le SDP
        parsed = parse_sdp(sdp)

        # Vérifier
        if (parsed.get('ip') == '192.168.1.100' and
            parsed.get('port') == 8000 and
            'PCMU' in parsed.get('codecs', []) and
            'PCMA' in parsed.get('codecs', [])):

            result.success = True
            result.message = "Création et parsing SDP fonctionnels"
            result.details = f"IP: {parsed['ip']}, Port: {parsed['port']}, Codecs: {parsed['codecs']}"
        else:
            result.success = False
            result.message = f"Données SDP incorrectes: {parsed}"

    except Exception as e:
        result.success = False
        result.message = f"Erreur: {e}"

    return result


def run_all_tests(server_host: str = 'localhost', server_port: int = 5060):
    """Exécute tous les tests"""
    print("\n" + "=" * 60)
    print("  TESTS DE CONNECTIVITÉ VoIP")
    print("=" * 60 + "\n")

    results = []

    # Tests sans serveur
    print("Tests unitaires (sans serveur):")
    print("-" * 40)

    results.append(test_codec_g711())
    results.append(test_rtp_packet())
    results.append(test_sdp_create_parse())
    results.append(test_rtp_port_available())

    for result in results:
        print(result)
        print()

    # Tests avec serveur
    print("\nTests d'intégration (avec serveur):")
    print("-" * 40)

    integration_results = [
        test_sip_server_reachable(server_host, server_port),
        test_sip_register(server_host, server_port),
        test_sip_invite(server_host, server_port)
    ]

    for result in integration_results:
        print(result)
        print()

    results.extend(integration_results)

    # Résumé
    print("\n" + "=" * 60)
    print("  RÉSUMÉ DES TESTS")
    print("=" * 60)

    passed = sum(1 for r in results if r.success)
    total = len(results)

    print(f"\n  Tests réussis: {passed}/{total}")
    print(f"  Taux de succès: {passed/total*100:.1f}%\n")

    if passed == total:
        print("  ✓ Tous les tests sont passés avec succès!")
    else:
        print(f"  ✗ {total - passed} test(s) échoué(s)")

    print()

    return passed == total


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Tests de connectivité VoIP')
    parser.add_argument('--host', default='localhost', help='Hôte du serveur SIP')
    parser.add_argument('--port', type=int, default=5060, help='Port du serveur SIP')

    args = parser.parse_args()

    success = run_all_tests(args.host, args.port)
    sys.exit(0 if success else 1)
