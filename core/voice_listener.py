import io
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

    def __init__(
        self,
        ptt_key: str = "f12",
        language: str = "es-ES",
        on_start_listening: Optional[Callable[[], None]] = None,
        on_stop_listening: Optional[Callable[[], None]] = None,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.ptt_key = ptt_key.lower()
        self.language = language
        self.on_start_listening = on_start_listening
        self.on_stop_listening = on_stop_listening
        self.on_transcription = on_transcription
        self.on_error = on_error

        self.recognizer = sr.Recognizer()
        self.is_recording = False
        self._running = False
        self._audio_frames = []
        self._thread: Optional[threading.Thread] = None

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

    def start(self):
        """Inicia el monitoreo de la tecla de Push-to-Talk en un hilo en segundo plano."""
        if self._running:
            return
        if not self._pa:
            self._init_pyaudio()
        self._running = True
        self._thread = threading.Thread(target=self._key_listener_loop, daemon=True)
        self._thread.start()
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

    def _transcribe_worker(self, frames):
        """Convierte los frames de audio grabados a texto."""
        if not frames or len(frames) < 8:  # Menos de ~0.4 seg
            # Notificar para que el HUD regrese a 'idle' sin quedarse congelado en 'thinking'
            self.error_occurred.emit("")
            if self.on_error:
                self.on_error("")
            return

        raw_audio_bytes = b"".join(frames)
        audio_data = sr.AudioData(raw_audio_bytes, self.sample_rate, 2)

        try:
            text = self.recognizer.recognize_google(audio_data, language=self.language)
            logger.info(f"Texto reconocido: {text}")
            if text.strip():
                self.transcription_ready.emit(text.strip())
                if self.on_transcription:
                    self.on_transcription(text.strip())
        except sr.UnknownValueError:
            logger.warning("No se detectó voz comprensible.")
            self.error_occurred.emit("No logré entender lo que dijiste.")
            if self.on_error:
                self.on_error("No logré entender lo que dijiste.")
        except sr.RequestError as e:
            logger.error(f"Error del servicio de reconocimiento: {e}")
            self.error_occurred.emit("Error de conexión con el servicio de voz.")
            if self.on_error:
                self.on_error("Error de conexión con el servicio de voz.")
        except Exception as e:
            logger.error(f"Error procesando transcripción: {e}")
