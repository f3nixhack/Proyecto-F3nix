import os
import sys
import json
import logging
import threading
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QCoreApplication

from core.ai_engine import AIEngine
from core.voice_speaker import VoiceSpeaker
from core.voice_listener import VoiceListener
from core.multi_agent_council import MultiAgentCouncil
from core.task_manager import TaskManager
from core.system_audio_listener import SystemAudioListener
import keyboard
from ui.floating_avatar import FloatingAvatar
from ui.f3nix_studio import F3nixStudio
from ui.selection_copilot import SelectionCopilotWidget
from ui.model_downloader_dialog import ModelDownloaderDialog
from ui.command_deck import CommandDeckDialog
from ui.quick_guide_dialog import QuickGuideDialog
from ui.environment_doctor_dialog import EnvironmentDoctorDialog
from ui.quick_launcher_bar import QuickLauncherBar
from core.environment_doctor import EnvironmentDoctor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ThrusterMain")

def load_config(config_path="config.json"):
    defaults = {
        "ollama_url": "http://localhost:11434",
        "model": "thruster_ai",
        "fallback_model": "llama3.1",
        "ptt_key": "f12",
        "voice_tts": "es-MX-JorgeNeural",
        "stt_language": "es-ES",
        "avatar_image": "thruster_avatar.jpg",
        "show_subtitles": True
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception as e:
            logger.error(f"No se pudo cargar {config_path}: {e}")
    return defaults

def save_config(config, config_path="config.json"):
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Configuración guardada en {config_path}")
    except Exception as e:
        logger.error(f"No se pudo guardar {config_path}: {e}")

class ThrusterApp:
    def __init__(self, config):
        self.config = config

        # 0. Diagnóstico y Auto-Reparación de Entorno (Doctor F3NIX)
        self._ensure_environment_health()

        # 1. Inicializar Motores de IA y Memoria
        self.ai = AIEngine(
            base_url=config.get("ollama_url", "http://localhost:11434"),
            default_model=config.get("model", "thruster_ai")
        )
        self.memory = self.ai.memory

        # Voz preferida persistente: lee de la Bóveda de Memoria o de config.json (Default: Mexicano)
        saved_voice = getattr(self.ai, "memory", None) and self.ai.memory.data.get("preferred_voice")
        if not saved_voice:
            saved_voice = config.get("voice_tts", "es-MX-JorgeNeural")
        self.config["voice_tts"] = saved_voice

        self.speaker = VoiceSpeaker(
            voice=saved_voice,
            rate=config.get("voice_rate", "+18%")
        )

        # 2. Inicializar Interfaz HUD
        self.hud = FloatingAvatar(avatar_path=config.get("avatar_image", "thruster_avatar.jpg"))
        self.hud.show_subtitles = config.get("show_subtitles", True)
        self.hud.current_voice = saved_voice
        self._cancel_requested = False

        # Restaurar posición guardada del avatar en pantalla
        self.hud.restore_position(config.get("avatar_x"), config.get("avatar_y"))

        # Sincronizar modelos disponibles con el HUD
        installed_models = self.ai.list_installed_models()
        self.hud.available_models = installed_models
        self.hud.active_model = self.ai.current_model

        # 3. Inicializar Mesa Redonda Multi-IA y Workspace F3NIX Studio
        self.council = MultiAgentCouncil(
            base_url=config.get("ollama_url", "http://localhost:11434"),
            vault=self.memory
        )
        self.studio = F3nixStudio(memory_vault=self.memory, rag=self.ai.rag, council=self.council, speaker=self.speaker)
        self.studio.sync_models_and_voices(
            installed_models,
            self.ai.current_model,
            self.speaker.current_voice
        )

        # 4. Inicializar Escuchador de Teclado Push-to-Talk (F12) con señales Qt
        self.listener = VoiceListener(
            ptt_key=config.get("ptt_key", "f12"),
            language=config.get("stt_language", "es-ES"),
            parent=self.hud
        )
        self.listener.start_listening_signal.connect(self.on_start_listening)
        self.listener.stop_listening_signal.connect(self.on_stop_listening)
        self.listener.transcription_ready.connect(self.on_transcription_ready)
        self.listener.error_occurred.connect(self.on_listener_error)

        # Conectar señales del HUD
        self.hud.clear_history_requested.connect(self.ai.clear_history)
        self.hud.quit_requested.connect(self.shutdown)
        self.hud.text_submitted.connect(self.on_transcription_ready)
        self.hud.model_change_requested.connect(self.on_model_changed)
        self.hud.analyze_clipboard_requested.connect(self.analyze_clipboard_now)
        self.hud.open_model_store_requested.connect(self.open_model_store)
        self.hud.open_command_deck_requested.connect(self.open_command_deck)
        self.hud.open_quick_guide_requested.connect(self.open_quick_guide)
        self.hud.voice_change_requested.connect(self.on_voice_changed)
        self.hud.file_dropped.connect(self.on_file_dropped)
        self.hud.toggle_studio_requested.connect(self.toggle_studio)
        self.hud.open_doctor_requested.connect(self.open_environment_doctor)
        self.hud.position_changed.connect(self.on_avatar_position_changed)
        self.hud.interrupt_requested.connect(self.interrupt_ai)

        # Conectar señales del Studio
        self.studio.chat_submitted.connect(self.on_transcription_ready)
        self.studio.model_changed.connect(self.on_model_changed)
        self.studio.voice_changed.connect(self.on_voice_changed)
        self.studio.file_loaded.connect(self.on_studio_file_loaded)
        self.studio.folder_indexed.connect(self.on_project_folder_indexed)
        self.studio.debate_concluded.connect(self.on_debate_concluded)
        self.studio.open_model_store_requested.connect(self.open_model_store)
        self.studio.open_doctor_requested.connect(self.open_environment_doctor)
        self.studio.window_closed.connect(self.on_studio_closed)

        # Conectar callbacks de IA (temporizadores y telemetría de actividad)
        self.ai.on_timer_finished_callback = self.on_timer_finished
        self.ai.on_activity_callback = self.studio.log_activity

        # 5. Inicializar Barra de Invocación Rápida Global (Alt + F)
        self.launcher = QuickLauncherBar(ai_engine=self.ai, speaker=self.speaker)
        self.launcher.open_studio_requested.connect(self.toggle_studio)
        self.hud.toggle_quick_launcher_requested.connect(self.launcher.toggle_launcher)
        self.hud.toggle_turbo_requested.connect(self.on_toggle_turbo)
        self.studio.turbo_mode_changed.connect(self.on_turbo_mode_changed)
        self._is_ai_busy = False

        # 6. Inicializar Gestor de Tareas To-Do y sincronizar con el HUD
        self.task_manager = TaskManager()
        self.ai.task_manager = self.task_manager
        self.hud.update_tasks(self.task_manager.get_all_tasks())
        self.hud.task_added.connect(self.on_task_added)
        self.hud.task_toggled.connect(self.on_task_toggled)
        self.hud.task_deleted.connect(self.on_task_deleted)
        self.hud.clear_completed_tasks_requested.connect(self.on_clear_completed_tasks)
        self.hud.trigger_screen_analysis_requested.connect(self.on_trigger_screen_analysis)
        self.hud.trigger_system_audio_summary_requested.connect(self.on_trigger_audio_summary)
        self.hud.trigger_selection_copilot_requested.connect(self.on_trigger_selection_copilot)

        # 7. Inicializar Copiloto Flotante de Selección y Resumen de Audio
        self.copilot = SelectionCopilotWidget(ai_engine=self.ai)
        self.audio_listener = SystemAudioListener(ai_engine=self.ai)

        # Registrar atajos globales de teclado en Windows
        try:
            keyboard.add_hotkey("alt+f", lambda: self.hud.toggle_quick_launcher_requested.emit())
            keyboard.add_hotkey("ctrl+alt+s", lambda: self.hud.trigger_screen_analysis_requested.emit())
            keyboard.add_hotkey("ctrl+alt+c", lambda: self.hud.trigger_selection_copilot_requested.emit())
            keyboard.add_hotkey("esc", self.on_global_esc_pressed)
            logger.info("Atajos globales Alt+F, Ctrl+Alt+S, Ctrl+Alt+C y Esc (Kill-Switch) registrados.")
        except Exception as e:
            logger.warning(f"No se pudieron registrar algunos atajos globales: {e}")

        # 8. Inicializar Bandeja del Sistema (System Tray) e Historial de Portapapeles (Clipboard Ring)
        self._setup_system_tray()
        try:
            QApplication.clipboard().dataChanged.connect(self.on_clipboard_data_changed)
        except Exception as e:
            logger.warning(f"No se pudo conectar el monitor de portapapeles: {e}")

    def _setup_system_tray(self):
        """Configura el icono interactivo en el área de notificaciones de Windows."""
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            avatar_path = self.config.get("avatar_image", "thruster_avatar.jpg")
            if os.path.exists(avatar_path):
                tray_icon = QIcon(avatar_path)
            else:
                tray_icon = self.hud.windowIcon()

            self.tray = QSystemTrayIcon(tray_icon, parent=self.hud)
            self.tray.setToolTip("Proyecto F3NIX - Asistente de Escritorio IA")

            tray_menu = QMenu()
            tray_menu.setStyleSheet(
                "QMenu { background-color: #1A1E29; color: #FFFFFF; border: 1px solid #2E384D; padding: 4px; border-radius: 6px; }"
                "QMenu::item { padding: 6px 20px; border-radius: 4px; }"
                "QMenu::item:selected { background-color: #00E5FF; color: #000000; font-weight: bold; }"
            )

            title_act = tray_menu.addAction("⚡ F3NIX Asistente de Escritorio")
            title_act.setEnabled(False)
            tray_menu.addSeparator()

            toggle_hud_act = tray_menu.addAction("👁️ Mostrar / Ocultar HUD")
            toggle_hud_act.triggered.connect(self.toggle_hud_visibility)

            mini_mode_act = tray_menu.addAction("🔮 Modo Mini-Orbe Zen")
            mini_mode_act.triggered.connect(self.hud.toggle_mini_mode)

            turbo_act = tray_menu.addAction("⚡ Alternar Modo Turbo")
            turbo_act.triggered.connect(self.on_toggle_turbo)

            studio_act = tray_menu.addAction("⛶ F3NIX Studio")
            studio_act.triggered.connect(self.toggle_studio)

            tray_menu.addSeparator()
            quit_act = tray_menu.addAction("Cerrar F3NIX")
            quit_act.triggered.connect(self.shutdown)

            self.tray.setContextMenu(tray_menu)
            self.tray.activated.connect(self.on_tray_activated)
            self.tray.show()
            logger.info("Icono de bandeja del sistema (System Tray) iniciado con éxito.")
        except Exception as e:
            logger.warning(f"No se pudo inicializar la bandeja del sistema: {e}")

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.studio.isVisible():
                self.studio.raise_()
                self.studio.activateWindow()
            else:
                self.toggle_hud_visibility()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_studio()

    def toggle_hud_visibility(self):
        if self.hud.isVisible():
            self.hud.hide()
        else:
            if self.studio.isVisible():
                self.studio.hide()
            self.hud.show()
            self.hud.raise_()
            self.hud.activateWindow()

    def on_clipboard_data_changed(self):
        """Vigila pasivamente el portapapeles y guarda las copias en ClipboardRing."""
        try:
            from core.f3nix_tools import F3nixTools
            text = QApplication.clipboard().text()
            if text and len(text.strip()) > 1:
                F3nixTools.clipboard_ring.add(text)
        except Exception:
            pass

    def on_avatar_position_changed(self, x: int, y: int):
        """Persiste la posición del avatar en pantalla para futuros arranques."""
        self.config["avatar_x"] = x
        self.config["avatar_y"] = y
        save_config(self.config)

    def on_global_esc_pressed(self):
        """Atajo global Esc: interrumpe a F3NIX si está hablando o procesando."""
        if self._is_ai_busy or self.speaker.is_speaking or self.hud.current_state in ["speaking", "thinking", "alarm"]:
            self.interrupt_ai()

    def interrupt_ai(self):
        """Kill-Switch: corta inmediatamente la voz, cancela la inferencia en curso y devuelve el HUD a idle."""
        if not self._is_ai_busy and not self.speaker.is_speaking and self.hud.current_state not in ["speaking", "thinking"]:
            return
        logger.info("Kill-Switch: Interrupción solicitada por el usuario.")
        self._cancel_requested = True
        self.speaker.stop()
        self._is_ai_busy = False
        self.hud.state_changed.emit("idle")
        self.hud.subtitle_received.emit("F3nix", "⏹️ Respuesta cancelada.")
        try:
            from core.f3nix_tools import F3nixTools
            F3nixTools.play_sound_chime("cancel")
        except Exception:
            pass

    def on_task_added(self, text: str):
        """Agrega una tarea desde el HUD o por voz y actualiza la vista."""
        self.task_manager.add_task(text)
        self.hud.update_tasks(self.task_manager.get_all_tasks())

    def on_task_toggled(self, task_id: str):
        """Alterna el estado completado de una tarea."""
        self.task_manager.toggle_task(task_id)
        self.hud.update_tasks(self.task_manager.get_all_tasks())

    def on_task_deleted(self, task_id: str):
        """Elimina una tarea."""
        self.task_manager.delete_task(task_id)
        self.hud.update_tasks(self.task_manager.get_all_tasks())

    def on_clear_completed_tasks(self):
        """Limpia las tareas completadas."""
        self.task_manager.clear_completed()
        self.hud.update_tasks(self.task_manager.get_all_tasks())

    def on_trigger_screen_analysis(self):
        """Dispara captura y análisis multimodal con Moondream ('Mira esto')."""
        if self._is_ai_busy:
            return
        self._is_ai_busy = True
        self.hud.state_changed.emit("thinking")
        self.hud.brain_badge_changed.emit("Visión 👁️")
        self.hud.subtitle_received.emit("F3nix", "👁️ Capturando y analizando tu pantalla con Moondream...")
        threading.Thread(
            target=self._process_screen_analysis_turn,
            daemon=True
        ).start()

    def _process_screen_analysis_turn(self):
        try:
            from core.f3nix_tools import F3nixTools
            screen_data = F3nixTools.capture_screen()
            if not screen_data.get("success"):
                self.hud.subtitle_received.emit("F3nix", f"Error capturando pantalla: {screen_data.get('error')}")
                self.hud.state_changed.emit("idle")
                return

            base64_img = screen_data.get("base64")
            prompt = "Analiza lo que ves en mi pantalla. Explica qué ventana o contenido principal está visible y destaca cualquier error, código o información relevante."
            self._process_streaming_turn(prompt, image_base64=base64_img)
        except Exception as e:
            logger.error(f"Error en análisis de pantalla: {e}")
            self.hud.subtitle_received.emit("F3nix", f"Error: {e}")
            self.hud.state_changed.emit("idle")
        finally:
            self._is_ai_busy = False

    def on_trigger_selection_copilot(self):
        """Captura la selección activa en Windows y despliega el mini copiloto flotante (Ctrl+Alt+C)."""
        import time
        try:
            # Simular Ctrl+C para capturar la selección del usuario
            keyboard.send("ctrl+c")
            time.sleep(0.08)
            clip_text = QApplication.clipboard().text().strip()
            if clip_text:
                self.copilot.show_at_cursor(clip_text)
            else:
                self.hud.subtitle_received.emit("F3NIX Copiloto", "Selecciona primero un texto y presiona Ctrl+Alt+C.")
        except Exception as e:
            logger.error(f"Error activando Copiloto de Selección: {e}")

    def on_trigger_audio_summary(self):
        """Inicia o detiene la captura y resumen de audio del sistema (Videos / Reuniones)."""
        if self.audio_listener.is_recording:
            self.audio_listener.stop()
            self.hud.subtitle_received.emit("F3nix", "Procesando audio capturado...")
            return

        self.hud.state_changed.emit("listening")
        self.hud.subtitle_received.emit("F3nix", "🎧 Escuchando audio del sistema (20s)... Toca 🎧 para detener antes.")

        def on_status(msg):
            self.hud.subtitle_received.emit("F3nix", msg)

        def on_summary_ready(summary):
            self.hud.subtitle_received.emit("F3nix", summary)
            self.studio.append_chat_message("F3nix [Resumen de Audio]", summary)
            # Hablar la conclusión o el resumen
            self.speaker.speak(
                summary,
                on_start=lambda: self.hud.state_changed.emit("speaking"),
                on_finish=lambda: self.hud.state_changed.emit("idle")
            )

        def on_finish():
            self.hud.state_changed.emit("idle")

        self.audio_listener.start_listen_and_summarize(
            duration=20,
            on_status=on_status,
            on_summary_ready=on_summary_ready,
            on_finish=on_finish
        )

    def on_turbo_mode_changed(self, enabled: bool):
        """Sincroniza el Modo Turbo entre AIEngine, Council, Launcher y HUD."""
        self.ai.set_turbo_mode(enabled)
        self.council.set_turbo_mode(enabled)
        self.hud.turbo_mode = enabled
        if hasattr(self, "launcher") and hasattr(self.launcher, "btn_turbo"):
            self.launcher.btn_turbo.blockSignals(True)
            self.launcher.btn_turbo.setChecked(enabled)
            self.launcher.btn_turbo.blockSignals(False)

    def on_toggle_turbo(self):
        """Alterna el Modo Turbo desde el HUD y actualiza Studio y Launcher."""
        new_state = not self.ai.turbo_mode
        self.on_turbo_mode_changed(new_state)
        if hasattr(self, "studio") and hasattr(self.studio, "btn_turbo_toggle"):
            self.studio.btn_turbo_toggle.blockSignals(True)
            self.studio.btn_turbo_toggle.setChecked(new_state)
            self.studio.btn_turbo_toggle.blockSignals(False)

    def _get_user_name(self) -> str:
        """Obtiene de forma segura el nombre del usuario configurado."""
        if hasattr(self, "memory") and self.memory and hasattr(self.memory, "get_user_name"):
            return self.memory.get_user_name()
        return "Usuario"

    def _get_salutation(self) -> str:
        """Obtiene de forma segura el título o saludo del usuario."""
        if hasattr(self, "memory") and self.memory and hasattr(self.memory, "get_salutation"):
            return self.memory.get_salutation()
        return "Comandante"

    def on_debate_concluded(self, topic: str, synthesis: str):
        """Notificación auditiva y visual cuando la Mesa Redonda concluye un debate estratégico."""
        try:
            short_topic = topic[:45] + ("..." if len(topic) > 45 else "")
            self.hud.subtitle_received.emit("Mesa Redonda", f"Debate completado: {short_topic}")
            salutation = self._get_salutation()
            self.speaker.speak(
                f"{salutation}, la Mesa Redonda ha concluido su deliberación sobre {short_topic}. El plan maestro está listo en tu Studio.",
                on_start=lambda: self.hud.state_changed.emit("speaking"),
                on_finish=lambda: self.hud.state_changed.emit("idle")
            )
            # Notificación nativa de Windows (Toast de Sistema)
            if hasattr(self, "tray") and self.tray.isVisible():
                self.tray.showMessage(
                    "🏛️ Mesa Redonda F3NIX",
                    f"Debate completado: {short_topic}\nEl Director ha emitido el Plan Maestro.",
                    QSystemTrayIcon.MessageIcon.Information,
                    6000
                )
        except Exception as e:
            logger.error(f"Error en on_debate_concluded: {e}")

    def on_project_folder_indexed(self, folder_path: str, files_count: int, chunks_count: int):
        """Notificación auditiva y visual cuando se indexa un proyecto con RAG."""
        folder_name = os.path.basename(folder_path)
        msg = f"Proyecto '{folder_name}' indexado ({files_count} archivos, {chunks_count} fragmentos)."
        self.hud.subtitle_received.emit("F3nix RAG", msg)
        self.speaker.speak(
            f"He indexado {files_count} archivos de tu proyecto {folder_name}. Ahora conozco todo tu código.",
            on_start=lambda: self.hud.state_changed.emit("speaking"),
            on_finish=lambda: self.hud.state_changed.emit("idle")
        )

    def toggle_studio(self):
        """Abre o minimiza el Workspace F3NIX Studio con ocultamiento automático del Avatar flotante."""
        if self.studio.isVisible():
            self.studio.hide()
            self.hud.show()
            self.hud.raise_()
        else:
            self.hud.hide()
            self.studio.show()
            self.studio.raise_()
            self.studio.activateWindow()

    def on_studio_closed(self):
        """Restaura automáticamente el avatar flotante cuando F3NIX Studio se cierra o se minimiza."""
        if not self.hud.isVisible():
            self.hud.show()
            self.hud.raise_()

    def on_studio_file_loaded(self, filename: str, content: str):
        """Maneja la carga o remoción de archivos desde el visor del Studio."""
        if filename and content:
            self.ai.load_document(filename, content)
            self.hud.subtitle_received.emit("F3nix", f"Documento '{filename}' cargado.")
        else:
            self.ai.active_document = None
            self.ai.active_document_name = None

    def on_voice_changed(self, voice_id: str):
        """Actualiza el timbre de voz, lo persiste en configuración y memoria permanente, y confirma oralmente."""
        self.speaker.set_voice(voice_id)
        self.hud.current_voice = voice_id
        self.config["voice_tts"] = voice_id
        save_config(self.config)

        # Guardar en la Bóveda de Memoria permanente
        if hasattr(self.ai, "memory") and self.ai.memory:
            self.ai.memory.data["preferred_voice"] = voice_id
            self.ai.memory._save()

        self.studio.sync_models_and_voices(
            self.ai.list_installed_models(),
            self.ai.current_model,
            voice_id
        )
        voice_names = {
            "es-MX-JorgeNeural": "Jorge de México",
            "es-ES-AlvaroNeural": "Álvaro de España",
            "es-ES-ElviraNeural": "Elvira de España",
            "es-MX-DaliaNeural": "Dalia de México"
        }
        friendly_name = voice_names.get(voice_id, voice_id)
        self.speaker.speak(
            f"Voz configurada a {friendly_name}. Guardada en tu memoria permanente.",
            on_start=lambda: self.hud.state_changed.emit("speaking"),
            on_finish=lambda: self.hud.state_changed.emit("idle")
        )

    def on_file_dropped(self, file_path: str):
        """Lee y almacena el documento arrastrado al avatar."""
        try:
            filename = os.path.basename(file_path)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            self.ai.load_document(filename, content)
            self.studio.set_active_document(filename, content)
            msg = f"Documento '{filename}' cargado ({len(content)} caracteres)."
            self.hud.subtitle_received.emit("F3nix", msg)
            self.speaker.speak(
                f"He cargado el archivo {filename}. Pregúntame lo que necesites sobre él.",
                on_start=lambda: self.hud.state_changed.emit("speaking"),
                on_finish=lambda: self.hud.state_changed.emit("idle")
            )
        except Exception as e:
            logger.error(f"Error cargando archivo arrastrado: {e}")
            self.hud.subtitle_received.emit("Error", f"No se pudo leer el archivo: {e}")

    def on_timer_finished(self, label: str):
        """Notificación visual y por voz cuando expira un temporizador o pomodoro."""
        try:
            logger.info(f"Temporizador concluido: {label}")
            self.hud.state_changed.emit("alarm")
            user_name = self._get_user_name()
            alert_text = f"¡Atención {user_name}! Tu {label} ha concluido."
            self.hud.subtitle_received.emit("⏰ ALARMA", alert_text)
            self.speaker.speak(
                alert_text,
                on_start=lambda: self.hud.state_changed.emit("alarm"),
                on_finish=lambda: self.hud.state_changed.emit("idle")
            )
        except Exception as e:
            logger.error(f"Error en on_timer_finished: {e}")

    def open_command_deck(self):
        """Abre el panel de control y casos de uso rápidos."""
        if hasattr(self, "_command_deck_dialog") and self._command_deck_dialog and self._command_deck_dialog.isVisible():
            self._command_deck_dialog.raise_()
            self._command_deck_dialog.activateWindow()
            return
        self._command_deck_dialog = CommandDeckDialog(parent=self.hud)
        self._command_deck_dialog.action_triggered.connect(self.on_transcription_ready)
        self._command_deck_dialog.exec()

    def open_quick_guide(self):
        """Abre la guía visual interactiva de comandos y superpoderes de forma segura y fluida."""
        if hasattr(self, "_quick_guide_dialog") and self._quick_guide_dialog and self._quick_guide_dialog.isVisible():
            self._quick_guide_dialog.raise_()
            self._quick_guide_dialog.activateWindow()
            return
        self._quick_guide_dialog = QuickGuideDialog(parent=self.hud)
        self._quick_guide_dialog.show()
        self._quick_guide_dialog.raise_()
        self._quick_guide_dialog.activateWindow()

    def open_model_store(self):
        """Abre la tienda/centro de descargas gráfico de modelos."""
        if hasattr(self, "_model_store_dialog") and self._model_store_dialog and self._model_store_dialog.isVisible():
            self._model_store_dialog.raise_()
            self._model_store_dialog.activateWindow()
            return
        installed = self.ai.list_installed_models()
        self._model_store_dialog = ModelDownloaderDialog(installed_models=installed, parent=self.hud)
        self._model_store_dialog.model_installed.connect(self.on_new_model_downloaded)
        self._model_store_dialog.exec()

    def _ensure_environment_health(self):
        """Diagnostica rutas, repara posibles discos desconectados y arranca Ollama si está apagado."""
        heal_res = EnvironmentDoctor.check_and_heal_ollama_path()
        if heal_res.get("healed"):
            logger.info("Doctor F3NIX: Se repararon rutas de modelos automáticamente.")
            for reason in heal_res.get("reasons", []):
                logger.info(f"Doctor F3NIX: {reason}")

        if not EnvironmentDoctor.is_ollama_running():
            logger.info("Doctor F3NIX: Ollama está apagado. Intentando iniciar servicio en segundo plano...")
            ok, msg = EnvironmentDoctor.auto_start_ollama(wait_seconds=6)
            if ok:
                logger.info("Doctor F3NIX: Motor Ollama iniciado con éxito.")
            else:
                logger.warning(f"Doctor F3NIX: {msg}")

    def open_environment_doctor(self):
        """Abre la ventana interactiva del Doctor F3NIX para salud y diagnóstico del sistema."""
        if hasattr(self, "_doctor_dialog") and self._doctor_dialog and self._doctor_dialog.isVisible():
            self._doctor_dialog.raise_()
            self._doctor_dialog.activateWindow()
            return
        self._doctor_dialog = EnvironmentDoctorDialog(parent=self.hud)
        self._doctor_dialog.open_model_store_requested.connect(self.open_model_store)
        self._doctor_dialog.exec()

    def on_new_model_downloaded(self, model_name: str):
        """Notifica cuando se completa la descarga de un modelo."""
        installed = self.ai.list_installed_models()
        self.hud.available_models = installed
        self.studio.sync_models_and_voices(installed, self.ai.current_model, self.speaker.current_voice)
        self.speaker.speak(
            f"El nuevo cerebro {model_name} ha sido instalado exitosamente. Ya puedes seleccionarlo.",
            on_start=lambda: self.hud.state_changed.emit("speaking"),
            on_finish=lambda: self.hud.state_changed.emit("idle")
        )

    def on_model_changed(self, model_name: str):
        """Cambia el cerebro de IA, lo persiste en configuración y memoria, y confirma por voz."""
        self.ai.set_model(model_name)
        self.hud.active_model = model_name
        self.config["model"] = model_name
        save_config(self.config)

        # Guardar en la Bóveda de Memoria permanente
        if hasattr(self.ai, "memory") and self.ai.memory:
            self.ai.memory.data["preferred_model"] = model_name
            self.ai.memory._save()

        self.studio.sync_models_and_voices(
            self.ai.list_installed_models(),
            model_name,
            self.speaker.current_voice
        )
        confirm_msg = f"Cerebro cambiado a {model_name}. Preferencia guardada."
        self.speaker.speak(
            confirm_msg,
            on_start=lambda: self.hud.state_changed.emit("speaking"),
            on_finish=lambda: self.hud.state_changed.emit("idle")
        )

    def analyze_clipboard_now(self):
        """Acción rápida para analizar el portapapeles actual."""
        clip_text = QApplication.clipboard().text()
        if not clip_text or not clip_text.strip():
            self.hud.subtitle_received.emit("Aviso", "El portapapeles está vacío. Copia algo con Ctrl+C primero.")
            return
        prompt = "Analiza y resume de forma concisa lo que tengo copiado en el portapapeles."
        self.on_transcription_ready(prompt)

    def on_start_listening(self):
        """Se activa al presionar F12."""
        logger.info("PTT activado (escuchando...)")
        self.speaker.stop()
        self.hud.state_changed.emit("listening")
        try:
            from core.f3nix_tools import F3nixTools
            F3nixTools.play_sound_chime("start")
        except Exception:
            pass

    def on_stop_listening(self):
        """Se activa al soltar F12."""
        logger.info("PTT liberado (procesando...)")
        self.hud.state_changed.emit("thinking")
        try:
            from core.f3nix_tools import F3nixTools
            F3nixTools.play_sound_chime("stop")
        except Exception:
            pass

    def on_listener_error(self, error_msg: str):
        """Se activa si hubo silencio o fallo en reconocimiento."""
        self.hud.subtitle_received.emit("Aviso", error_msg)
        self.hud.state_changed.emit("idle")

    def on_transcription_ready(self, user_text: str):
        """Se activa cuando el usuario habla o escribe un mensaje."""
        clean_text = user_text.strip()
        if not clean_text:
            return

        logger.info(f"Usuario: {clean_text}")
        self.hud.subtitle_received.emit("Tú", clean_text)
        self.studio.append_chat_message("Tú", clean_text)

        # Si ya hay una consulta en proceso, notificar y no saturar CPU con hilos paralelos
        if self._is_ai_busy:
            self.hud.subtitle_received.emit("F3nix", "Un momento, sigo procesando tu consulta anterior...")
            return

        self._is_ai_busy = True
        self.hud.state_changed.emit("thinking")

        # 1. Chequeo de comando de voz para Tareas To-Do
        voice_task = TaskManager.parse_voice_task(clean_text)
        if voice_task:
            self.task_manager.add_task(voice_task)
            self.hud.update_tasks(self.task_manager.get_all_tasks())
            user_name = self._get_user_name()
            msg = f"Anotado en tus tareas: «{voice_task}», {user_name}."
            self.hud.subtitle_received.emit("F3nix", msg)
            self.studio.append_chat_message("F3nix", msg)
            self._is_ai_busy = False
            self.speaker.speak(
                msg,
                on_start=lambda: self.hud.state_changed.emit("speaking"),
                on_finish=lambda: self.hud.state_changed.emit("idle")
            )
            return

        # 2. Chequeo de comando de voz para Resumen de Audio del Sistema (Videos / Reuniones)
        audio_sum_triggers = [
            "resume el video", "resumir el video", "resume la reunión", "resumir la reunión",
            "resume la reunion", "resumir la reunion", "resume el audio", "resumir el audio",
            "resume lo que suena", "resumir lo que suena", "resume lo que se escucha",
            "resumen del video", "resumen de la reunión", "resumen de la reunion"
        ]
        if any(ast in clean_text.lower() for ast in audio_sum_triggers):
            self._is_ai_busy = False
            self.on_trigger_audio_summary()
            return

        # 3. Si el usuario pide ayuda o comandos
        help_triggers = [
            "qué puedes hacer", "que puedes hacer", "ayuda", "cómo te uso", "como te uso",
            "comandos", "qué sabes hacer", "que sabes hacer", "tutorial", "en qué me puedes ayudar",
            "en que me puedes ayudar", "en qué me pods ayudar", "en que me pods ayudar",
            "en qué me podés ayudar", "en que me podes ayudar", "superpoderes", "super poderes"
        ]
        if any(ht in clean_text.lower() for ht in help_triggers):
            msg = "He abierto en tu pantalla la guía rápida de superpoderes y comandos."
            self.hud.subtitle_received.emit("F3nix", msg)
            self.studio.append_chat_message("F3nix", msg)
            self._is_ai_busy = False
            self.speaker.speak(
                msg,
                on_start=lambda: self.hud.state_changed.emit("speaking"),
                on_finish=lambda: self.hud.state_changed.emit("idle")
            )
            self.open_quick_guide()
            return

        # Capturar el portapapeles en el hilo principal de Qt de forma segura
        clip_content = QApplication.clipboard().text()

        # Consultar a la IA en un hilo separado
        threading.Thread(
            target=self._process_ai_turn,
            args=(clean_text, clip_content),
            daemon=True
        ).start()

    def _process_ai_turn(self, user_text: str, clip_content: str = ""):
        try:
            is_dictation = any(user_text.lower().startswith(p) for p in ["escribe: ", "dicta: ", "redacta: ", "escribe ", "dicta "])

            if is_dictation:
                reply = self.ai.chat(user_text, clipboard_text=clip_content)
                self.hud.subtitle_received.emit("F3nix", reply)
                self.studio.append_chat_message("F3nix", reply)
                from core.f3nix_tools import F3nixTools
                F3nixTools.type_into_active_window(reply)
                user_name = self._get_user_name()
                self.speaker.speak(
                    f"Texto escrito en tu cursor, {user_name}.",
                    on_start=lambda: self.hud.state_changed.emit("speaking"),
                    on_finish=lambda: self.hud.state_changed.emit("idle")
                )
                return

            self._process_streaming_turn(user_text, clip_content=clip_content)

        except Exception as e:
            logger.error(f"Error en _process_ai_turn: {e}", exc_info=True)
            self.hud.subtitle_received.emit("F3nix", f"Error: {str(e)}")
            self.hud.state_changed.emit("idle")
        finally:
            self._is_ai_busy = False

    def _process_streaming_turn(self, user_text: str, clip_content: str = "", image_base64: Optional[str] = None):
        """Procesa una consulta en streaming: tokens en vivo en UI y audio frase a frase."""
        import queue
        sentence_queue = queue.Queue()

        def sentence_generator():
            while True:
                item = sentence_queue.get()
                if item is None:
                    break
                yield item

        # Iniciar reproductor de audio frase a frase en streaming
        self.speaker.speak_stream(
            sentence_generator(),
            on_start=lambda: self.hud.state_changed.emit("speaking"),
            on_finish=lambda: self.hud.state_changed.emit("idle")
        )

        full_reply = ""
        self._cancel_requested = False
        try:
            for chunk in self.ai.chat_stream(
                user_text,
                clipboard_text=clip_content,
                image_base64=image_base64
            ):
                if getattr(self, "_cancel_requested", False):
                    logger.info("Inferencia en streaming abortada por Kill-Switch.")
                    break
                c_type = chunk.get("type")
                if c_type == "meta":
                    brain = chunk.get("brain", "")
                    if brain:
                        self.hud.brain_badge_changed.emit(brain)
                elif c_type == "thought_token":
                    t_text = chunk.get("thought_text", "")
                    snippet = "..." + t_text[-80:] if len(t_text) > 80 else t_text
                    self.hud.subtitle_received.emit("🧠 Razonando...", snippet.replace("\n", " "))
                elif c_type == "thought":
                    # Razonamiento interno concluido; pasa a la respuesta limpia sintetizada
                    pass
                elif c_type == "token":
                    full_reply = chunk.get("full_text", "")
                    self.hud.subtitle_received.emit("F3nix", full_reply)
                elif c_type == "sentence":
                    sentence_text = chunk.get("content", "")
                    if sentence_text:
                        sentence_queue.put(sentence_text)
                elif c_type == "plan_steps":
                    steps = chunk.get("steps", [])
                    self.hud.update_tasks(self.task_manager.get_all_tasks())
                    self.hud.subtitle_received.emit("F3nix Planificador", f"🎯 {len(steps)} tareas cargadas en tu lista.")
                elif c_type == "auto_memory":
                    fact = chunk.get("fact", "")
                    self.hud.subtitle_received.emit("💾 Auto-Memoria", f"Guardado: {fact}")
                elif c_type == "error":
                    err_msg = chunk.get("content", "")
                    self.hud.subtitle_received.emit("F3nix", err_msg)
                    sentence_queue.put(err_msg)
        finally:
            sentence_queue.put(None)  # Notificar fin al reproductor

        if full_reply:
            self.studio.append_chat_message("F3nix", full_reply)

    def start(self):
        """Arranca el HUD y el escuchador PTT con auto-arranque silencioso de Ollama y saludo de bienvenida."""
        self.hud.show()
        self.listener.start()

        if not EnvironmentDoctor.is_ollama_running():
            self.hud.subtitle_received.emit("F3NIX", "Iniciando servicio de IA local en segundo plano...")
            ok, msg = EnvironmentDoctor.auto_start_ollama(wait_seconds=6)
            if not ok:
                self.hud.subtitle_received.emit("Doctor F3NIX", "Ollama no pudo iniciarse automáticamente. Abriendo diagnóstico...")
                self.open_environment_doctor()
            else:
                installed_models = self.ai.list_installed_models()
                self.hud.available_models = installed_models
                self.hud.active_model = self.ai.current_model
                self.studio.sync_models_and_voices(installed_models, self.ai.current_model, self.speaker.current_voice)

        if not self.hud.available_models:
            welcome_msg = "Bienvenido a F3nix. Selecciona un cerebro de IA para comenzar."
            self.hud.subtitle_received.emit("F3nix", welcome_msg)
            # Abrir automáticamente el centro de descargas para nuevos usuarios
            self.open_model_store()
        else:
            welcome_msg = "Proyecto F3nix en línea. Mantén presionada la tecla F12 para hablar."
            self.hud.subtitle_received.emit("F3nix", welcome_msg)
            self.speaker.speak(
                welcome_msg,
                on_start=lambda: self.hud.state_changed.emit("speaking"),
                on_finish=lambda: self.hud.state_changed.emit("idle")
            )

    def shutdown(self):
        """Cierra de forma limpia todos los subprocesos."""
        logger.info("Cerrando Proyecto F3nix...")
        if hasattr(self, "tray"):
            try:
                self.tray.hide()
            except Exception:
                pass
        self.listener.stop()
        self.speaker.stop()
        try:
            self.studio.close()
        except Exception:
            pass
        QApplication.quit()

def _global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Excepción no controlada:", exc_info=(exc_type, exc_value, exc_traceback))

def main():
    sys.excepthook = _global_exception_handler
    config = load_config()
    app = QApplication(sys.argv)
    app.setApplicationName("Proyecto F3nix")
    app.setQuitOnLastWindowClosed(False)

    thruster = ThrusterApp(config)
    thruster.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
