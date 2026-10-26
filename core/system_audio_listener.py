import io
import time
import wave
import logging
import threading
from typing import Optional, Callable
import pyaudio
import speech_recognition as sr

logger = logging.getLogger(__name__)

class SystemAudioListener:
    """
    Escucha y captura audio del sistema (videos, YouTube, reuniones)
    usando Mezcla Estéreo o micrófono primario, lo transcribe y genera un resumen en viñetas con IA.
    """
    def __init__(self, ai_engine=None):
        self.ai = ai_engine
        self.is_recording = False
        self._stop_requested = False
        self._thread: Optional[threading.Thread] = None

        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = 1024
        self.audio_format = pyaudio.paInt16

    def find_best_input_device(self) -> Optional[int]:
        """Detecta 'Mezcla estéreo' si está habilitada; de lo contrario usa el micrófono por defecto."""
        p = pyaudio.PyAudio()
        best_idx = None
        try:
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                name = dev.get("name", "").lower()
                inputs = dev.get("maxInputChannels", 0)
                if inputs > 0:
                    if "mezcla" in name or "stereo" in name or "loopback" in name:
                        best_idx = i
                        break
        except Exception as e:
            logger.debug(f"Error enumerando dispositivos de audio: {e}")
        finally:
            p.terminate()
        return best_idx

    def start_listen_and_summarize(
        self,
        duration: int = 20,
        on_status: Optional[Callable[[str], None]] = None,
        on_summary_ready: Optional[Callable[[str], None]] = None,
        on_finish: Optional[Callable[[], None]] = None
    ):
        """Inicia la grabación de audio en segundo plano durante 'duration' segundos."""
        if self.is_recording:
            return

        self._stop_requested = False
        self.is_recording = True

        self._thread = threading.Thread(
            target=self._worker,
            args=(duration, on_status, on_summary_ready, on_finish),
            daemon=True
        )
        self._thread.start()

    def stop(self):
        """Detiene la grabación antes de tiempo."""
        self._stop_requested = True

    def _worker(
        self,
        duration: int,
        on_status: Optional[Callable[[str], None]],
        on_summary_ready: Optional[Callable[[str], None]],
        on_finish: Optional[Callable[[], None]]
    ):
        p = pyaudio.PyAudio()
        dev_idx = self.find_best_input_device()
        frames = []

        try:
            if on_status:
                on_status(f"🎧 Escuchando audio ({duration}s)...")

            stream_kwargs = {
                "format": self.audio_format,
                "channels": self.channels,
                "rate": self.sample_rate,
                "input": True,
                "frames_per_buffer": self.chunk_size
            }
            if dev_idx is not None:
                stream_kwargs["input_device_index"] = dev_idx

            stream = p.open(**stream_kwargs)

            total_chunks = int((self.sample_rate / self.chunk_size) * duration)
            for i in range(total_chunks):
                if self._stop_requested:
                    break
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)

            stream.stop_stream()
            stream.close()
        except Exception as e:
            logger.error(f"Error grabando audio del sistema: {e}")
            if on_status:
                on_status(f"Error grabando audio: {e}")
            if on_finish:
                on_finish()
            self.is_recording = False
            p.terminate()
            return
        finally:
            p.terminate()

        self.is_recording = False

        if not frames:
            if on_status:
                on_status("No se capturó audio.")
            if on_finish:
                on_finish()
            return

        if on_status:
            on_status("Transcribiendo contenido...")

        # Convertir a formato WAV en memoria
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(b"".join(frames))

        wav_buffer.seek(0)

        # Transcripción con speech_recognition
        recognizer = sr.Recognizer()
        transcribed_text = ""
        try:
            with sr.AudioFile(wav_buffer) as source:
                audio_data = recognizer.record(source)
                transcribed_text = recognizer.recognize_google(audio_data, language="es-ES")
        except sr.UnknownValueError:
            msg = "No se detectaron voces o palabras claras en el audio."
            if on_status:
                on_status(msg)
            if on_summary_ready:
                on_summary_ready(msg)
            if on_finish:
                on_finish()
            return
        except Exception as stt_err:
            logger.error(f"Fallo en transcripción: {stt_err}")
            msg = "No se pudo procesar la transcripción del audio."
            if on_status:
                on_status(msg)
            if on_finish:
                on_finish()
            return

        if on_status:
            on_status("Generando resumen con F3NIX...")

        # Resumen estructurado con IA
        summary_prompt = (
            "Eres F3NIX. Analiza la siguiente transcripción de un video o reunión y genera un resumen conciso en español "
            "estructurado exactamente en 3 viñetas con los puntos clave:\n\n"
            f"«{transcribed_text}»\n\n"
            "Formato requerido:\n"
            "• [Punto 1]\n"
            "• [Punto 2]\n"
            "• [Punto 3]\n"
            "Conclusión: [1 frase]"
        )

        try:
            if self.ai:
                summary = self.ai.chat(summary_prompt)
            else:
                summary = f"Transcripción: {transcribed_text}"

            if on_summary_ready:
                on_summary_ready(summary)
        except Exception as ai_err:
            logger.error(f"Error generando resumen con IA: {ai_err}")
            if on_summary_ready:
                on_summary_ready(f"Transcripción detectada:\n{transcribed_text}")
        finally:
            if on_finish:
                on_finish()
