import os
import re
import asyncio
import tempfile
import threading
import logging
from typing import Optional, Callable
import edge_tts

# Ocultar mensaje de bienvenida de pygame en consola
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame

logger = logging.getLogger(__name__)

AVAILABLE_VOICES = {
    "es-ES-AlvaroNeural": "Álvaro (España - Masculino)",
    "es-MX-JorgeNeural": "Jorge (México - Masculino)",
    "es-ES-ElviraNeural": "Elvira (España - Femenino)",
    "es-MX-DaliaNeural": "Dalia (México - Femenino)"
}

class VoiceSpeaker:
    """
    Motor de síntesis de voz (TTS) ultranatural en español usando edge-tts
    y reproducción oculta de bajo impacto mediante pygame.mixer.
    """
    def __init__(self, voice: str = "es-MX-JorgeNeural", rate: str = "+18%"):
        self.voice = voice
        self.rate = rate
        self.is_speaking = False
        self._stop_requested = False
        self._lock = threading.Lock()
        self._init_mixer()

    @property
    def current_voice(self) -> str:
        """Devuelve el identificador de voz activo."""
        return self.voice

    @current_voice.setter
    def current_voice(self, val: str):
        self.voice = val

    def set_voice(self, voice_name: str):
        """Cambia el identificador de voz para síntesis."""
        self.voice = voice_name
        logger.info(f"Voz cambiada a: {voice_name}")

    def set_rate(self, rate: str):
        """Cambia la velocidad de síntesis de voz (ej. '+18%')."""
        self.rate = rate
        logger.info(f"Velocidad de voz ajustada a: {rate}")

    def _init_mixer(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception as e:
            logger.error(f"Error inicializando pygame.mixer: {e}")

    @staticmethod
    def clean_text_for_speech(text: str) -> str:
        """
        Limpia bloques de código, URLs, markdown y caracteres especiales
        para que la lectura hablada sea natural y fluida.
        """
        # Eliminar bloques de pensamiento <think>...</think>
        text = re.sub(r'<think>[\s\S]*?</think>', ' ', text, flags=re.IGNORECASE)
        # Eliminar bloques de código ```...```
        text = re.sub(r'```[\s\S]*?```', ' [Código omitido en audio] ', text)
        # Eliminar código en línea `...`
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Eliminar enlaces markdown [texto](url)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Eliminar encabezados y negritas/cursivas
        text = re.sub(r'[#*_~>]+', '', text)
        # Limpiar múltiples saltos de línea y espacios redundantes
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def _generate_audio_file(self, clean_text: str, output_path: str, voice: Optional[str] = None):
        """Genera el archivo MP3 mediante edge-tts de forma asíncrona a velocidad acelerada."""
        active_voice = voice or self.voice
        communicate = edge_tts.Communicate(clean_text, active_voice, rate=self.rate)
        await communicate.save(output_path)

    def speak(self, text: str, voice: Optional[str] = None, on_start: Optional[Callable[[], None]] = None, on_finish: Optional[Callable[[], None]] = None):
        """
        Sintetiza y reproduce el texto en un hilo de ejecución independiente con soporte para voz personalizada.
        """
        thread = threading.Thread(target=self._speak_worker, args=(text, voice, on_start, on_finish), daemon=True)
        thread.start()

    def speak_wait(self, text: str, voice: Optional[str] = None, check_cancelled: Optional[Callable[[], bool]] = None):
        """
        Sintetiza y reproduce el texto, esperando de forma síncrona en el hilo actual a que termine o se cancele.
        Ideal para narrar debates turno a turno secuencialmente.
        """
        import time
        done_event = threading.Event()
        self.speak(text, voice=voice, on_finish=done_event.set)
        while not done_event.is_set():
            if check_cancelled and check_cancelled():
                self.stop()
                break
            time.sleep(0.05)

    def _speak_worker(self, text: str, voice: Optional[str] = None, on_start: Optional[Callable[[], None]] = None, on_finish: Optional[Callable[[], None]] = None):
        with self._lock:
            clean = self.clean_text_for_speech(text)
            if not clean:
                if on_finish:
                    on_finish()
                return

            self._stop_requested = False
            self.is_speaking = True

            if on_start:
                try:
                    on_start()
                except Exception as e:
                    logger.error(f"Error en callback on_start: {e}")

            temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            temp_path = temp_audio_file.name
            temp_audio_file.close()

            try:
                # Generar archivo de audio con edge-tts usando la voz asignada
                asyncio.run(self._generate_audio_file(clean, temp_path, voice=voice))

                if self._stop_requested:
                    return

                # Reproducir usando pygame
                pygame.mixer.music.load(temp_path)
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy() and not self._stop_requested:
                    pygame.time.Clock().tick(20)

                if self._stop_requested:
                    pygame.mixer.music.stop()

            except Exception as e:
                logger.error(f"Error durante síntesis o reproducción de audio: {e}")
            finally:
                self.is_speaking = False
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

                if on_finish:
                    try:
                        on_finish()
                    except Exception as e:
                        logger.error(f"Error en callback on_finish: {e}")

    def speak_stream(
        self,
        sentence_generator,
        on_start: Optional[Callable[[], None]] = None,
        on_finish: Optional[Callable[[], None]] = None
    ):
        """
        Reproduce oraciones generadas en streaming (frase a frase).
        Sintetiza la siguiente oración en segundo plano mientras reproduce la actual
        para una experiencia instantánea y sin silencios.
        """
        thread = threading.Thread(
            target=self._speak_stream_worker,
            args=(sentence_generator, on_start, on_finish),
            daemon=True
        )
        thread.start()

    def _speak_stream_worker(
        self,
        sentence_generator,
        on_start: Optional[Callable[[], None]],
        on_finish: Optional[Callable[[], None]]
    ):
        import queue
        with self._lock:
            self._stop_requested = False
            self.is_speaking = True
            audio_queue = queue.Queue(maxsize=4)
            started_callback_fired = False

            # Hilo productor: sintetiza oraciones a archivos temporales
            def _producer():
                try:
                    for sentence in sentence_generator:
                        if self._stop_requested:
                            break
                        clean = self.clean_text_for_speech(sentence)
                        if not clean or len(clean.strip()) < 2:
                            continue

                        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                        temp_path = temp_audio.name
                        temp_audio.close()

                        try:
                            asyncio.run(self._generate_audio_file(clean, temp_path))
                            audio_queue.put(temp_path)
                        except Exception as ex:
                            logger.error(f"Error generando audio en stream: {ex}")
                            if os.path.exists(temp_path):
                                try:
                                    os.remove(temp_path)
                                except Exception:
                                    pass
                finally:
                    audio_queue.put(None)  # Centinela de fin

            prod_thread = threading.Thread(target=_producer, daemon=True)
            prod_thread.start()

            # Consumidor: reproduce en orden conforme van estando listos
            try:
                while not self._stop_requested:
                    item = audio_queue.get()
                    if item is None:
                        break  # Fin del stream

                    if self._stop_requested:
                        if os.path.exists(item):
                            try:
                                os.remove(item)
                            except Exception:
                                pass
                        break

                    if not started_callback_fired and on_start:
                        try:
                            on_start()
                            started_callback_fired = True
                        except Exception as e:
                            logger.error(f"Error en callback on_start: {e}")

                    try:
                        pygame.mixer.music.load(item)
                        pygame.mixer.music.play()

                        while pygame.mixer.music.get_busy() and not self._stop_requested:
                            pygame.time.Clock().tick(25)

                        if self._stop_requested:
                            pygame.mixer.music.stop()
                    except Exception as play_err:
                        logger.error(f"Error reproduciendo chunk de audio en stream: {play_err}")
                    finally:
                        try:
                            pygame.mixer.music.unload()
                        except Exception:
                            pass
                        if os.path.exists(item):
                            try:
                                os.remove(item)
                            except Exception:
                                pass

            finally:
                self.is_speaking = False
                # Limpiar cualquier archivo residual en la cola
                while not audio_queue.empty():
                    try:
                        residual = audio_queue.get_nowait()
                        if residual and os.path.exists(residual):
                            os.remove(residual)
                    except Exception:
                        pass

                if on_finish:
                    try:
                        on_finish()
                    except Exception as e:
                        logger.error(f"Error en callback on_finish: {e}")

    def stop(self):
        """Detiene la reproducción de voz actual inmediatamente."""
        self._stop_requested = True
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        self.is_speaking = False

