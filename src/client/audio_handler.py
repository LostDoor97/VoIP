"""
Gestion de l'audio pour le client VoIP
Capture et playback audio avec support des codecs
"""

import numpy as np
import threading
import queue
from typing import Optional, Callable
from dataclasses import dataclass

try:
    import sounddevice as sd
    import soundfile as sf
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Warning: sounddevice/soundfile non disponibles, utilisation du mode simulé")

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.codecs import G711Codec, AudioCodecManager


@dataclass
class AudioConfig:
    """Configuration audio"""
    sample_rate: int = 8000
    channels: int = 1
    frame_size: int = 160  # 20ms à 8kHz
    codec: str = 'PCMU'
    echo_cancellation: bool = True
    noise_suppression: bool = True


class AudioHandler:
    """
    Gère la capture et le playback audio
    """

    def __init__(self, config: AudioConfig = None):
        self.config = config or AudioConfig()
        self.codec_manager = AudioCodecManager(self.config.codec)

        self.audio_queue = queue.Queue()
        self.record_queue = queue.Queue()

        self.is_recording = False
        self.is_playing = False

        self.audio_stream: Optional[sd.Stream] = None
        self.playback_stream: Optional[sd.Stream] = None

        # Callbacks
        self.on_audio_data: Optional[Callable[[bytes], None]] = None
        self.on_speech_detected: Optional[Callable[[], None]] = None
        self.on_silence_detected: Optional[Callable[[], None]] = None

        # Détection de voix (VAD simplifié)
        self.vad_threshold = 500  # Seuil de détection de voix
        self.speech_timeout = 0.5  # Secondes avant détection de silence

        # Statistiques
        self.frames_captured = 0
        self.frames_played = 0

    def start_capture(self, callback: Callable[[bytes], None] = None):
        """Démarre la capture audio"""
        if not AUDIO_AVAILABLE:
            print("[Audio] Mode simulé - capture désactivée")
            return

        if callback:
            self.on_audio_data = callback

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"[Audio] Status: {status}")

            pcm_data = indata.tobytes()

            # Détection de voix simplifiée
            rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
            if rms > self.vad_threshold:
                if self.on_speech_detected:
                    self.on_speech_detected()
            else:
                if self.on_silence_detected:
                    self.on_silence_detected()

            # Encoder avec le codec
            encoded = self.codec_manager.encode(pcm_data)

            # Envoyer via callback
            if self.on_audio_data:
                self.on_audio_data(encoded)

            self.frames_captured += 1

        try:
            self.audio_stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype='int16',
                blocksize=self.config.frame_size,
                callback=audio_callback
            )
            self.audio_stream.start()
            self.is_recording = True
            print(f"[Audio] Capture démarrée ({self.config.sample_rate}Hz, {self.config.codec})")
        except Exception as e:
            print(f"[Audio] Erreur de capture: {e}")
            self.is_recording = False

    def stop_capture(self):
        """Arrête la capture audio"""
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
        self.is_recording = False
        print("[Audio] Capture arrêtée")

    def start_playback(self):
        """Démarre le playback audio"""
        if not AUDIO_AVAILABLE:
            print("[Audio] Mode simulé - playback désactivé")
            return

        def playback_callback(outdata, frames, time_info, status):
            if status:
                print(f"[Audio] Playback status: {status}")

            try:
                encoded_data = self.audio_queue.get(timeout=0.02)
                pcm_data = self.codec_manager.decode(encoded_data)
                
                outdata_np = np.frombuffer(pcm_data, dtype=np.int16).reshape(-1, 1)
                
                frames_to_copy = min(len(outdata), len(outdata_np))
                outdata[:frames_to_copy, :] = outdata_np[:frames_to_copy, :]
                
                if frames_to_copy < len(outdata):
                    outdata[frames_to_copy:, :].fill(0)
                
                self.frames_played += 1
            except queue.Empty:
                outdata.fill(0)

        try:
            self.playback_stream = sd.OutputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype='int16',
                blocksize=self.config.frame_size,
                callback=playback_callback
            )
            self.playback_stream.start()
            self.is_playing = True
            print("[Audio] Playback démarré")
        except Exception as e:
            print(f"[Audio] Erreur de playback: {e}")
            self.is_playing = False

    def stop_playback(self):
        """Arrête le playback audio"""
        if self.playback_stream:
            self.playback_stream.stop()
            self.playback_stream.close()
            self.playback_stream = None
        self.is_playing = False
        # Vider la queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        print("[Audio] Playback arrêté")

    def queue_audio_frame(self, encoded_data: bytes):
        """Ajoute un frame audio à la queue de playback"""
        self.audio_queue.put(encoded_data)

    def receive_rtp_packet(self, payload: bytes):
        """Reçoit un payload RTP et l'envoie au playback"""
        self.queue_audio_frame(payload)

    def get_stats(self) -> dict:
        """Retourne les statistiques audio"""
        return {
            'frames_captured': self.frames_captured,
            'frames_played': self.frames_played,
            'codec': self.config.codec,
            'sample_rate': self.config.sample_rate,
            'is_recording': self.is_recording,
            'is_playing': self.is_playing,
            'queue_size': self.audio_queue.qsize()
        }

    def test_audio_devices(self) -> dict:
        """Teste et liste les périphériques audio disponibles"""
        if not AUDIO_AVAILABLE:
            return {'error': 'sounddevice non disponible'}

        devices = sd.query_devices()
        hostapis = sd.query_hostapis()

        result = {
            'input_devices': [],
            'output_devices': [],
            'default_input': None,
            'default_output': None
        }

        for i, device in enumerate(devices):
            device_info = {
                'id': i,
                'name': device['name'],
                'channels': device.get('max_input_channels', 0) or device.get('max_output_channels', 0)
            }

            if device['max_input_channels'] > 0:
                result['input_devices'].append(device_info)
            if device['max_output_channels'] > 0:
                result['output_devices'].append(device_info)

        # Périphériques par défaut
        for api in hostapis:
            if api['default_input_device'] >= 0:
                result['default_input'] = devices[api['default_input_device']]['name']
            if api['default_output_device'] >= 0:
                result['default_output'] = devices[api['default_output_device']]['name']

        return result


class SimulatedAudioHandler:
    """
    Handler audio simulé pour les environnements sans périphériques audio
    """

    def __init__(self, config: AudioConfig = None):
        self.config = config or AudioConfig()
        self.codec_manager = AudioCodecManager(self.config.codec)
        self.is_recording = False
        self.is_playing = False
        self.on_audio_data: Optional[Callable[[bytes], None]] = None
        self.audio_queue = queue.Queue()
        self.frames_captured = 0
        self.frames_played = 0

    def start_capture(self, callback: Callable[[bytes], None] = None):
        """Simule la capture audio"""
        if callback:
            self.on_audio_data = callback
        self.is_recording = True
        print("[Audio Simulé] Capture démarrée (mode simulé)")

        # Générer du silence encodé périodiquement
        def simulate_capture():
            silence = bytes([127] * 160)  # Silence en μ-law
            while self.is_recording:
                if self.on_audio_data:
                    self.on_audio_data(silence)
                self.frames_captured += 1
                threading.Event().wait(0.02)  # 20ms

        thread = threading.Thread(target=simulate_capture, daemon=True)
        thread.start()

    def stop_capture(self):
        self.is_recording = False
        print("[Audio Simulé] Capture arrêtée")

    def start_playback(self):
        self.is_playing = True
        print("[Audio Simulé] Playback démarré (mode simulé)")

    def stop_playback(self):
        self.is_playing = False
        print("[Audio Simulé] Playback arrêté")

    def queue_audio_frame(self, encoded_data: bytes):
        self.audio_queue.put(encoded_data)

    def receive_rtp_packet(self, payload: bytes):
        self.queue_audio_frame(payload)

    def get_stats(self) -> dict:
        return {
            'frames_captured': self.frames_captured,
            'frames_played': self.frames_played,
            'codec': self.config.codec,
            'sample_rate': self.config.sample_rate,
            'is_recording': self.is_recording,
            'is_playing': self.is_playing,
            'queue_size': self.audio_queue.qsize()
        }

    def test_audio_devices(self) -> dict:
        return {'error': 'Mode simulé - pas de périphériques'}


def create_audio_handler(use_simulation: bool = False, config: AudioConfig = None):
    """Factory pour créer un handler audio"""
    if use_simulation or not AUDIO_AVAILABLE:
        return SimulatedAudioHandler(config)
    return AudioHandler(config)
