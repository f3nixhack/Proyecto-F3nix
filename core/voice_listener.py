import io
import re
import time
import wave
import threading
import logging
from typing import Callable, Optional
import keyboard
import pyaudio
import speech_recognition as sr
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

class VoiceListener(QObject):
    """
    Controlador Push-to-Talk (Mantener presionado F12 para hablar).
    Graba el audio exclusivamente mientras la tecla está presionada y lo
    transcribe a texto al soltarla usando reconocimiento de voz.
    Emite señales Qt nativas para garantizar la ejecución en el hilo principal de la GUI.
    """
    start_listening_signal = pyqtSignal()
    stop_listening_signal = pyqtSignal()
    transcription_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    hands_free_changed = pyqtSignal(bool)

    def __init__(
        self,
        ptt_key: str = "f12",
        language: str = "es-ES",
        on_start_listening: Optional[Callable[[], None]] = None,
        on_stop_listening: Optional[Callable[[], None]] = None,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        groq_api_key: Optional[str] = None,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.ptt_key = ptt_key.lower()
        self.language = language
        self.on_start_listening = on_start_listening
        self.on_stop_listening = on_stop_listening
        self.on_transcription = on_transcription
        self.on_error = on_error
        self.groq_api_key = groq_api_key
        self.groq_whisper_enabled = bool(groq_api_key)

        self.recognizer = sr.Recognizer()
        self.is_recording = False
        self._running = False
        self._audio_frames = []
        self._thread: Optional[threading.Thread] = None
        self._hf_thread: Optional[threading.Thread] = None

        # Parámetros de Modo Manos Libres y VAD
        self.hands_free: bool = False
        self.barge_in_callback: Optional[Callable[[], None]] = None
        self.is_speaking_checker: Optional[Callable[[], bool]] = None
        self.rms_threshold: int = 750
        self.silence_limit_seconds: float = 0.38  # Ultra-rápido: 380ms para respuesta inmediata estilo llamada

        # Filtro Anti-Eco Acústico de ChoferPro (evita que los parlantes activen el mic)
        self.last_assistant_speech: str = ""
        self.last_speech_end_time: float = 0.0
        self.echo_cancellation_enabled: bool = True

        # Parámetros de audio
        self.chunk_size = 1024
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.sample_rate = 16000
        self._pa: Optional[pyaudio.PyAudio] = None
        self._init_pyaudio()

    def _init_pyaudio(self):
        """Inicializa una instancia persistente de PyAudio para eliminar latencia de arranque."""
        try:
            self._pa = pyaudio.PyAudio()
        except Exception as e:
            logger.error(f"Error inicializando PyAudio: {e}")
            self._pa = None

    def set_hands_free(self, enabled: bool):
        """Activa o desactiva la escucha continua manos libres con detección de voz (VAD)."""
        self.hands_free = enabled
        logger.info(f"Modo Manos Libres {'ACTIVADO' if enabled else 'DESACTIVADO'}")
        self.hands_free_changed.emit(enabled)

    def set_last_assistant_speech(self, text: str):
        """Registra el último texto sintetizado por el asistente para filtrado de eco acústico."""
        self.last_assistant_speech = text or ""

    def mark_speech_ended(self):
        """Marca el timestamp de fin de reproducción para el período de gracia anti-eco."""
        self.last_speech_end_time = time.time()

    @staticmethod
    def _normalize_for_echo(s: str) -> str:
        """Normaliza texto para comparación acústica idéntica al algoritmo de ChoferPro."""
        text = (s or "").lower()
        replacements = [
            ('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'),
            ('ü', 'u'), ('ñ', 'n')
        ]
        for orig, rep in replacements:
            text = text.replace(orig, rep)
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()

    def is_echo(self, text: str) -> bool:
        """
        Determina si el texto capturado proviene del eco de los altavoces de la PC.
        Utiliza solapamiento de palabras (overlap ratio >= 35%) y subcadenas normalizadas.
        """
        if not self.echo_cancellation_enabled or not text or not self.last_assistant_speech:
            return False

        norm_input = self._normalize_for_echo(text)
        norm_last = self._normalize_for_echo(self.last_assistant_speech)

        if not norm_input or not norm_last:
            return False

        # Si el input completo está contenido en la última frase del asistente (longitud mínima 7 chars)
        if len(norm_input) >= 7 and norm_input in norm_last:
            return True

        # Comparación por conjunto de palabras con umbral de 35% de solapamiento
        input_words = set(norm_input.split())
        last_words = set(norm_last.split())
        if not input_words:
            return False

        overlap = input_words.intersection(last_words)
        overlap_ratio = len(overlap) / float(len(input_words))

        # Si recién terminó de hablar (<0.7s) somos más estrictos con el solapamiento
        time_since_speech = time.time() - self.last_speech_end_time
        if time_since_speech < 0.7 and (overlap_ratio >= 0.25 or len(overlap) >= 2):
            return True

        return overlap_ratio >= 0.35

    def start(self):
        """Inicia el monitoreo de la tecla PTT y el hilo de manos libres en segundo plano."""
        if self._running:
            return
        if not self._pa:
            self._init_pyaudio()
        self._running = True
        self._thread = threading.Thread(target=self._key_listener_loop, daemon=True)
        self._thread.start()
        self._hf_thread = threading.Thread(target=self._hands_free_loop, daemon=True)
        self._hf_thread.start()
        logger.info(f"Escuchador Push-to-Talk iniciado en tecla: {self.ptt_key.upper()}")

    def stop(self):
        """Detiene el escuchador y libera recursos de audio."""
        self._running = False
        self.is_recording = False
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    @staticmethod
    def _calc_rms(data: bytes) -> int:
        try:
            import audioop
            return audioop.rms(data, 2)
        except Exception:
            import struct, math
            count = len(data) // 2
            if count == 0:
                return 0
            shorts = struct.unpack(f"<{count}h", data)
            sum_sq = sum(s * s for s in shorts)
            return int(math.sqrt(sum_sq / count))

    def _hands_free_loop(self):
        """Ciclo continuo de detección de voz humana (VAD) y soporte para interrupción al hablar (barge-in)."""
        stream = None
        while self._running:
            if not self.hands_free:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                    stream = None
                time.sleep(0.2)
                continue

            if not self._pa:
                self._init_pyaudio()
                if not self._pa:
                    time.sleep(1.0)
                    continue

            if stream is None:
                try:
                    stream = self._pa.open(
                        format=self.audio_format,
                        channels=self.channels,
                        rate=self.sample_rate,
                        input=True,
                        frames_per_buffer=self.chunk_size
                    )
                except Exception as ex:
                    logger.error(f"Error abriendo stream para manos libres: {ex}")
                    time.sleep(1.0)
                    continue

            is_speaking_now = False
            speaking_frames = []
            last_sound_time = time.time()

            try:
                while self._running and self.hands_free:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    rms = self._calc_rms(data)

                    # Si el asistente está hablando por los altavoces de la PC:
                    # Ignorar entrada de micrófono para evitar que el sonido de los altavoces corte la reproducción
                    if self.is_speaking_checker and self.is_speaking_checker():
                        is_speaking_now = False
                        speaking_frames = []
                        time.sleep(0.04)
                        continue

                    # Período de gracia post-habla: drenar el eco y reverberación residual del ambiente (0.65s)
                    if time.time() - self.last_speech_end_time < 0.65:
                        is_speaking_now = False
                        speaking_frames = []
                        continue

                    # Detección de voz activa
                    if rms > self.rms_threshold:
                        if not is_speaking_now:
                            is_speaking_now = True
                            self.is_recording = True
                            speaking_frames = [data]
                            self.start_listening_signal.emit()
                            if self.on_start_listening:
                                try:
                                    self.on_start_listening()
                                except Exception:
                                    pass
                        else:
                            speaking_frames.append(data)
                        last_sound_time = time.time()
                    else:
                        if is_speaking_now:
                            speaking_frames.append(data)
                            # Silencio sostenido -> fin de frase
                            if time.time() - last_sound_time > self.silence_limit_seconds:
                                is_speaking_now = False
                                self.is_recording = False
                                self.stop_listening_signal.emit()
                                if self.on_stop_listening:
                                    try:
                                        self.on_stop_listening()
                                    except Exception:
                                        pass
                                frames_to_process = list(speaking_frames)
                                speaking_frames = []
                                threading.Thread(target=self._transcribe_worker, args=(frames_to_process,), daemon=True).start()
                                time.sleep(0.35)

            except Exception as stream_err:
                logger.error(f"Excepción en captura de manos libres: {stream_err}")
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                    stream = None
                time.sleep(0.5)

        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass

    def _key_listener_loop(self):
        """Ciclo continuo que vigila el estado de la tecla PTT."""
        was_pressed = False

        while self._running:
            try:
                is_pressed = keyboard.is_pressed(self.ptt_key)
            except Exception:
                # Posible fallo de permisos o tecla en foco especial
                time.sleep(0.05)
                continue

            if is_pressed and not was_pressed:
                # La tecla acaba de ser presionada
                was_pressed = True
                self._start_recording()

            elif not is_pressed and was_pressed:
                # La tecla acaba de ser soltada
                was_pressed = False
                self._stop_recording_and_process()

            time.sleep(0.02)

    def _start_recording(self):
        """Comienza a capturar audio del micrófono."""
        if self.is_recording:
            return

        self.is_recording = True
        self._audio_frames = []

        self.start_listening_signal.emit()
        if self.on_start_listening:
            try:
                self.on_start_listening()
            except Exception as e:
                logger.error(f"Error en callback on_start_listening: {e}")

        # Iniciar hilo de captura de buffers de audio
        threading.Thread(target=self._record_audio_worker, daemon=True).start()

    def _record_audio_worker(self):
        """Lee buffers del micrófono mientras is_recording sea True reutilizando la instancia de PyAudio."""
        if not self._pa:
            self._init_pyaudio()

        stream = None
        try:
            stream = self._pa.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )

            while self.is_recording:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                self._audio_frames.append(data)

        except Exception as e:
            logger.error(f"Error capturando audio del micrófono: {e}")
            self.error_occurred.emit("No se pudo acceder al micrófono.")
            if self.on_error:
                self.on_error("No se pudo acceder al micrófono.")
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass

    def _stop_recording_and_process(self):
        """Detiene la grabación y envía el audio a transcribir."""
        if not self.is_recording:
            return

        self.is_recording = False

        self.stop_listening_signal.emit()
        if self.on_stop_listening:
            try:
                self.on_stop_listening()
            except Exception as e:
                logger.error(f"Error en callback on_stop_listening: {e}")

        # Transcribir en un hilo para no bloquear la UI
        threading.Thread(target=self._transcribe_worker, args=(list(self._audio_frames),), daemon=True).start()

    def _transcribe_groq_whisper(self, raw_audio_bytes: bytes) -> Optional[str]:
        """Transcribe audio en ultra-alta velocidad (< 400ms) usando Groq Whisper-Large-v3-Turbo."""
        if not self.groq_api_key or not self.groq_whisper_enabled:
            return None
        try:
            import requests
            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(raw_audio_bytes)
            wav_io.seek(0)

            files = {"file": ("audio.wav", wav_io, "audio/wav")}
            data = {"model": "whisper-large-v3-turbo", "language": "es"}
            r = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.groq_api_key}"},
                files=files,
                data=data,
                timeout=3.5
            )
            if r.status_code == 200:
                result = r.json().get("text", "").strip()
                if result:
                    logger.info(f"Groq Whisper reconocido en alta velocidad: '{result}'")
                    return result
        except Exception as e:
            logger.warning(f"Groq Whisper falló o agotó tiempo, pasando a Google STT fallback: {e}")
        return None

    def _transcribe_worker(self, frames):
        """Convierte los frames de audio grabados a texto (Groq Whisper con fallback Google)."""
        if not frames or len(frames) < 8:  # Menos de ~0.4 seg
            # Notificar para que el HUD regrese a 'idle' sin quedarse congelado en 'thinking'
            self.error_occurred.emit("")
            if self.on_error:
                self.on_error("")
            return

        raw_audio_bytes = b"".join(frames)

        # 1. Intentar reconocimiento de voz ultra-rápido por Groq Whisper (< 400ms)
        text = self._transcribe_groq_whisper(raw_audio_bytes)

        # 2. Si no hay Groq o falló conexión, usar fallback estándar de Google
        if not text:
            audio_data = sr.AudioData(raw_audio_bytes, self.sample_rate, 2)
            try:
                text = self.recognizer.recognize_google(audio_data, language=self.language)
            except sr.UnknownValueError:
                logger.warning("No se detectó voz comprensible.")
                self.error_occurred.emit("No logré entender lo que dijiste.")
                if self.on_error:
                    self.on_error("No logré entender lo que dijiste.")
                return
            except sr.RequestError as e:
                logger.error(f"Error del servicio de reconocimiento: {e}")
                self.error_occurred.emit("Error de conexión con el servicio de voz.")
                if self.on_error:
                    self.on_error("Error de conexión con el servicio de voz.")
                return
            except Exception as e:
                logger.error(f"Error procesando transcripción: {e}")
                return

        logger.info(f"Texto reconocido final: {text}")
        stripped = (text or "").strip()
        if stripped:
            if self.is_echo(stripped):
                logger.info(f"[Anti-Echo] Descartada transcripción por eco acústico del parlante: '{stripped}'")
                self.error_occurred.emit("")
                if self.on_error:
                    self.on_error("")
                return
            self.transcription_ready.emit(stripped)
            if self.on_transcription:
                self.on_transcription(stripped)
