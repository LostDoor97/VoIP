"""
Tests pour les codecs audio et le traitement RTP
"""

import sys
import os
import math
import array

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from shared.codecs import G711Codec, AudioCodecManager
from shared.rtp import RTPPacket, RTPSession


def generate_test_signal(frequency: float = 440, duration_ms: int = 20, sample_rate: int = 8000) -> bytes:
    """Génère un signal sinusoïdal de test"""
    samples = []
    num_samples = int(sample_rate * duration_ms / 1000)

    for i in range(num_samples):
        value = int(10000 * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(value)

    return array.array('h', samples).tobytes()


def test_g711_ulaw_roundtrip():
    """Teste l'encodage/décodage μ-law avec préservation du signal"""
    print("Test: G.711 μ-law Roundtrip")
    print("-" * 40)

    # Générer un signal test
    pcm_data = generate_test_signal(440, 20)

    # Encoder
    encoded = G711Codec.encode_pcmu(pcm_data)

    # Décoder
    decoded = G711Codec.decode_pcmu(encoded)

    # Comparer les signaux (avec tolérance pour la perte de compression)
    original_samples = array.array('h', pcm_data)
    decoded_samples = array.array('h', decoded)

    max_error = 0
    total_error = 0

    for orig, dec in zip(original_samples, decoded_samples):
        error = abs(orig - dec)
        max_error = max(max_error, error)
        total_error += error

    avg_error = total_error / len(original_samples)

    print(f"  Échantillons: {len(original_samples)}")
    print(f"  Taille PCM: {len(pcm_data)} bytes")
    print(f"  Taille encodée: {len(encoded)} bytes")
    print(f"  Ratio de compression: {len(pcm_data) / len(encoded):.2f}:1")
    print(f"  Erreur maximale: {max_error}")
    print(f"  Erreur moyenne: {avg_error:.2f}")

    # Le G.711 est lossy: on valide des seuils téléphonie réalistes
    if max_error <= 300 and avg_error <= 100:
        print("  ✓ Test PASSED\n")
        return True
    else:
        print("  ✗ Test FAILED\n")
        return False


def test_g711_alaw_roundtrip():
    """Teste l'encodage/décodage A-law"""
    print("Test: G.711 A-law Roundtrip")
    print("-" * 40)

    pcm_data = generate_test_signal(440, 20)
    encoded = G711Codec.encode_pcma(pcm_data)
    decoded = G711Codec.decode_pcma(encoded)

    original_samples = array.array('h', pcm_data)
    decoded_samples = array.array('h', decoded)

    max_error = 0
    for orig, dec in zip(original_samples, decoded_samples):
        max_error = max(max_error, abs(orig - dec))

    print(f"  Taille encodée: {len(encoded)} bytes")
    print(f"  Erreur maximale: {max_error}")

    if max_error <= 300:
        print("  ✓ Test PASSED\n")
        return True
    else:
        print("  ✗ Test FAILED\n")
        return False


def test_codec_manager_negotiation():
    """Teste la négociation de codecs"""
    print("Test: Négociation de codecs")
    print("-" * 40)

    manager = AudioCodecManager('PCMU')

    # Test 1: Codecs communs
    local = ['PCMU', 'PCMA', 'opus']
    remote = ['PCMU', 'PCMA']

    selected = manager.negotiate_codecs(local, remote)
    print(f"  Local: {local}")
    print(f"  Remote: {remote}")
    print(f"  Sélectionné: {selected}")

    if selected == 'PCMU':
        print("  ✓ Priorité correcte (PCMU préféré)\n")
        test1 = True
    else:
        print("  ✗ Mauvaise sélection\n")
        test1 = False

    # Test 2: Fallback
    local = ['opus']
    remote = ['PCMU', 'PCMA']

    selected = manager.negotiate_codecs(local, remote)
    print(f"  Local: {local}")
    print(f"  Remote: {remote}")
    print(f"  Sélectionné: {selected}")

    if selected == 'PCMU':  # Fallback par défaut
        print("  ✓ Fallback correct\n")
        test2 = True
    else:
        print("  ✗ Fallback incorrect\n")
        test2 = False

    return test1 and test2


def test_rtp_packet_creation():
    """Teste la création de paquets RTP"""
    print("Test: Création de paquets RTP")
    print("-" * 40)

    # Créer un paquet
    payload = generate_test_signal(440, 20)

    packet = RTPPacket(
        version=2,
        payload_type=0,  # PCMU
        sequence_number=100,
        timestamp=1000,
        ssrc=0xABCDEF00,
        payload=payload[:160]  # 20ms de audio en μ-law
    )

    # Sérialiser
    data = packet.to_bytes()

    print(f"  Taille du paquet: {len(data)} bytes")
    print(f"  Header RTP: 12 bytes")
    print(f"  Payload: {len(data) - 12} bytes")

    # Parser
    parsed = RTPPacket.from_bytes(data)

    checks = [
        (parsed.version == 2, "Version"),
        (parsed.payload_type == 0, "Payload Type"),
        (parsed.sequence_number == 100, "Sequence Number"),
        (parsed.timestamp == 1000, "Timestamp"),
        (parsed.ssrc == 0xABCDEF00, "SSRC"),
        (len(parsed.payload) == 160, "Payload Length")
    ]

    all_passed = True
    for check, name in checks:
        status = "✓" if check else "✗"
        print(f"  {status} {name}")
        if not check:
            all_passed = False

    if all_passed:
        print("  ✓ Test PASSED\n")
    else:
        print("  ✗ Test FAILED\n")

    return all_passed


def test_rtp_sequence():
    """Teste la séquence des paquets RTP"""
    print("Test: Séquence RTP (simulé)")
    print("-" * 40)

    # Simuler l'envoi de plusieurs paquets
    packets_sent = 10
    prev_seq = -1
    prev_ts = -1
    sequence_ok = True
    timestamp_ok = True

    for i in range(packets_sent):
        packet = RTPPacket(
            version=2,
            payload_type=0,
            sequence_number=i,
            timestamp=1000 + i * 160,  # 160 samples par frame
            ssrc=0x12345678,
            payload=bytes([127] * 160)  # Silence
        )

        # Vérifier la séquence
        if prev_seq >= 0 and packet.sequence_number != prev_seq + 1:
            sequence_ok = False

        # Vérifier le timestamp
        if prev_ts >= 0 and packet.timestamp != prev_ts + 160:
            timestamp_ok = False

        prev_seq = packet.sequence_number
        prev_ts = packet.timestamp

    print(f"  Paquets simulés: {packets_sent}")
    print(f"  {'✓' if sequence_ok else '✗'} Séquence incrémentale")
    print(f"  {'✓' if timestamp_ok else '✗'} Timestamps incrémentaux (160 samples)")

    if sequence_ok and timestamp_ok:
        print("  ✓ Test PASSED\n")
        return True
    else:
        print("  ✗ Test FAILED\n")
        return False


def run_audio_tests():
    """Exécute tous les tests audio"""
    print("\n" + "=" * 60)
    print("  TESTS AUDIO ET CODECS")
    print("=" * 60 + "\n")

    results = [
        test_g711_ulaw_roundtrip(),
        test_g711_alaw_roundtrip(),
        test_codec_manager_negotiation(),
        test_rtp_packet_creation(),
        test_rtp_sequence()
    ]

    passed = sum(results)
    total = len(results)

    print("=" * 60)
    print(f"  RÉSULTATS: {passed}/{total} tests passés")
    print("=" * 60 + "\n")

    return passed == total


if __name__ == '__main__':
    success = run_audio_tests()
    sys.exit(0 if success else 1)
