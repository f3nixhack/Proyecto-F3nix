import os
import sys
import time
import re
import hashlib
import logging
import requests
from datetime import datetime
from typing import Optional, List, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QThread, QEvent, QPoint, QMarginsF
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QKeySequence, QShortcut, QTextCursor,
    QTextDocument, QPdfWriter, QPageSize, QPageLayout
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextBrowser, QTextEdit, QLineEdit, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QComboBox, QSplitter, QFrame, QMessageBox, QProgressDialog,
    QInputDialog, QMenu
)

logger = logging.getLogger(__name__)

from core.memory_vault import MemoryVault
from core.f3nix_rag import LocalRAG
from core.multi_agent_council import MultiAgentCouncil, ROLES_CONFIG, DEBATE_MODES
from core.voice_speaker import VoiceSpeaker, AVAILABLE_VOICES
from ui.council_guide_dialog import CouncilGuideDialog
from ui.constitution_dialog import ConstitutionDialog
from ui.life_case_dialog import LifeCaseDialog

class CouncilWorker(QThread):
    """
    Hilo de trabajo en segundo plano para el debate secuencial de la Mesa Redonda Multi-IA.
    Transmite tokens en tiempo real para evitar congelamientos o incertidumbre durante la inferencia,
    soporta 10 modos dialécticos, rondas, intervenciones en vivo de Fenix y narración en voz alta
    secuencial y opcional con voces diferenciadas por rol.
    """
    turn_started = pyqtSignal(str, str, int, str)        # role, model, round_num, phase_title
    token_received = pyqtSignal(str, str, str)           # role, model, chunk
    turn_finished = pyqtSignal(str, str, str, int, str)   # role, model, reply, round_num, phase_title
    debate_completed = pyqtSignal(dict)                  # full results dict
    debate_error = pyqtSignal(str)                       # error msg

    def __init__(
        self,
        council: MultiAgentCouncil,
        topic: str,
        models_per_role: Dict[str, str],
        rounds: int = 2,
        mode: str = "clasico",
        file_data: Optional[Dict[str, Any]] = None,
        speaker: Optional[VoiceSpeaker] = None,
        enable_tts: bool = False,
        role_voices: Optional[Dict[str, str]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.council = council
        self.topic = topic
        self.models_per_role = models_per_role
        self.rounds = rounds
        self.mode = mode
        self.file_data = file_data
        self.speaker = speaker
        self.enable_tts = enable_tts
        self.role_voices = role_voices or {}
        self._is_cancelled = False
        self._pending_interventions: List[str] = []

    def set_tts_enabled(self, enabled: bool):
        """Activa o desactiva la narración hablada en vivo del debate."""
        self.enable_tts = enabled
        if not enabled and self.speaker:
            self.speaker.stop()

    def add_intervention(self, text: str):
        if text and text.strip():
            self._pending_interventions.append(text.strip())

    def get_intervention(self) -> Optional[str]:
        if self._pending_interventions:
            return self._pending_interventions.pop(0)
        return None

    def run(self):
        try:
            def on_start(role, model, round_num=1, phase_title=""):
                if not self._is_cancelled:
                    self.turn_started.emit(role, model, round_num, phase_title)

            def on_token(role, model, chunk):
                if not self._is_cancelled:
                    self.token_received.emit(role, model, chunk)

            def on_finish(role, model, reply, round_num=1, phase_title=""):
                if not self._is_cancelled:
                    self.turn_finished.emit(role, model, reply, round_num, phase_title)
                    # Narración en voz alta secuencial por turno con voz asignada
                    if self.enable_tts and self.speaker and reply.strip():
                        voice = self.role_voices.get(role, self.speaker.current_voice)
                        role_title = ROLES_CONFIG.get(role, {}).get("title", role.capitalize())
                        role_name = re.sub(r'[^\w\s]', '', role_title).strip()
                        spoken_text = f"{role_name}. {reply}" if role_name else reply
                        self.speaker.speak_wait(
                            spoken_text,
                            voice=voice,
                            check_cancelled=lambda: self._is_cancelled or not self.enable_tts
                        )

            results = self.council.run_debate(
                topic=self.topic,
                models_per_role=self.models_per_role,
                rounds=self.rounds,
                mode=self.mode,
                file_data=self.file_data,
                on_turn_start=on_start,
                on_turn_token=on_token,
                on_turn_finished=on_finish,
                is_cancelled=lambda: self._is_cancelled,
                get_user_intervention=self.get_intervention
            )
            if not self._is_cancelled:
                self.debate_completed.emit(results)
        except Exception as e:
            if not self._is_cancelled:
                self.debate_error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True
        if self.speaker:
            self.speaker.stop()


class F3nixStudio(QMainWindow):
    """
    F3NIX Studio: Workspace expandible inspirado en Hermes Desktop.
    Proporciona Chat enriquecido, edición visual de Bóveda de Memoria,
    Registro de actividad en vivo del agente, Base de conocimiento RAG local,
    Visor de documentos y Mesa Redonda Multi-IA.
    """
    chat_submitted = pyqtSignal(str)
    chat_message_received = pyqtSignal(str, str) # sender, message
    model_changed = pyqtSignal(str)
    voice_changed = pyqtSignal(str)
    memory_updated = pyqtSignal()
    file_loaded = pyqtSignal(str, str) # filename, content
    folder_indexed = pyqtSignal(str, int, int) # folder_path, files_count, chunks_count
    debate_concluded = pyqtSignal(str, str) # topic, synthesis
    open_model_store_requested = pyqtSignal()
    open_doctor_requested = pyqtSignal()
    turbo_mode_changed = pyqtSignal(bool)
    activity_logged = pyqtSignal(str, str, str) # category, action, details
    window_closed = pyqtSignal()

    def __init__(self, memory_vault: Optional[MemoryVault] = None, rag: Optional[LocalRAG] = None, council: Optional[MultiAgentCouncil] = None, speaker: Optional[VoiceSpeaker] = None, parent=None):
        super().__init__(parent)
        self.memory = memory_vault or MemoryVault()
        self.rag = rag or LocalRAG()
        self.council = council or MultiAgentCouncil()
        self.speaker = speaker
        self.council_tts_enabled = False
        self.council_worker: Optional[CouncilWorker] = None
        self.current_council_mode = "clasico"
        self._debate_turns_history = []
        self._current_turn_data = None
        self._current_playing_turn_idx = None
        self._debate_topic = ""
        self.chat_message_received.connect(self._safe_append_chat_message)
        self.activity_logged.connect(self._add_activity_row)
        self.setWindowTitle("F3NIX Studio — Workspace de Agente & Bóveda de Memoria")
        self.resize(1020, 750)
        self.setMinimumSize(850, 580)

        self._apply_theme()
        self._init_ui()
        self.refresh_memory_view()
        self._refresh_rag_status()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_models_from_ollama()

    def refresh_models_from_ollama(self):
        """Consulta directamente a Ollama y refresca todos los selectores de modelos en el Studio."""
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=1.5)
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                if models:
                    current_m = self.model_combo.currentText() or models[0]
                    v_id = self.voice_combo.currentData() or "es-MX-JorgeNeural"
                    self.sync_models_and_voices(models, current_m, v_id)
        except Exception:
            pass

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0D111A;
            }
            QWidget {
                color: #ECEFF4;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #232C3D;
                background: #141A26;
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                background: #101520;
                color: #8C99B2;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                border: 1px solid #1C2433;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background: #141A26;
                color: #00E5FF;
                border: 1px solid #232C3D;
                border-bottom: 2px solid #00E5FF;
            }
            QTabBar::tab:hover:!selected {
                background: #171E2D;
                color: #D8DEE9;
            }
            QFrame.panel {
                background-color: #171E2C;
                border: 1px solid #252F42;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #1E2738;
                color: #E5E9F0;
                border: 1px solid #2E3B52;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #29354C;
                border: 1px solid #00E5FF;
                color: #00E5FF;
            }
            QPushButton:pressed {
                background-color: #00B8D4;
                color: #000000;
            }
            QPushButton.primary {
                background-color: #00B8D4;
                color: #090D14;
                border: 1px solid #00E5FF;
            }
            QPushButton.primary:hover {
                background-color: #00E5FF;
                color: #000000;
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #0F141F;
                color: #ECEFF4;
                border: 1px solid #252F42;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #00E5FF;
            }
            QComboBox {
                background-color: #0F141F;
                color: #ECEFF4;
                border: 1px solid #252F42;
                border-radius: 6px;
                padding: 4px 10px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #141A26;
                color: #ECEFF4;
                selection-background-color: #00E5FF;
                selection-color: #000000;
                border: 1px solid #252F42;
            }
            QTableWidget {
                background-color: #0F141F;
                border: 1px solid #252F42;
                border-radius: 6px;
                gridline-color: #1E2738;
                color: #ECEFF4;
            }
            QHeaderView::section {
                background-color: #171E2C;
                color: #8C99B2;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #252F42;
                font-weight: bold;
            }
            QScrollBar:vertical {
                background: #0D111A;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #252F42;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00E5FF;
            }
        """)

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 12, 16, 16)
        main_layout.setSpacing(12)

        # Header Bar superior
        header = self._create_header()
        main_layout.addLayout(header)

        # Tabs de trabajo principales
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_chat_tab(), "💬 Chat & Canvas")
        self.tabs.addTab(self._create_memory_tab(), "🧠 Bóveda de Memoria (Vault)")
        self.tabs.addTab(self._create_activity_tab(), "⚡ Registro de Actividad")
        self.tabs.addTab(self._create_documents_tab(), "📁 Base de Conocimiento (RAG)")
        self.tabs.addTab(self._create_council_tab(), "🏛️ Mesa Redonda (Multi-IA)")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self.tabs)

        # Atajo Ctrl+Enter para enviar chat
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self._send_chat_message)

    def _on_tab_changed(self, index: int):
        if index == 4:  # Tab 5: Mesa Redonda
            if getattr(self, "_council_auto_scroll", True):
                self._scroll_council_to_bottom()

    def _create_header(self) -> QHBoxLayout:
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # Logo y Título
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("⚡ F3NIX STUDIO")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #00E5FF; letter-spacing: 1.5px;")
        sub_lbl = QLabel("Workspace de Agente Autónomo & Memoria Persistente (Hermes Desktop)")
        sub_lbl.setStyleSheet("font-size: 11px; color: #7F8C9F;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Selector rápido de modelo
        model_lbl = QLabel("🧠 Cerebro:")
        model_lbl.setStyleSheet("color: #8C99B2; font-weight: bold;")
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(160)
        self.model_combo.currentTextChanged.connect(self._on_model_combo_changed)

        header_layout.addWidget(model_lbl)
        header_layout.addWidget(self.model_combo)

        btn_refresh_models = QPushButton("Refrescar")
        btn_refresh_models.setToolTip("Refrescar lista de cerebros detectados en Ollama")
        btn_refresh_models.setStyleSheet("""
            QPushButton {
                background-color: #1A2333;
                color: #00E5FF;
                border: 1px solid #283952;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #223047;
                color: #FFFFFF;
            }
        """)
        btn_refresh_models.clicked.connect(self.refresh_models_from_ollama)
        header_layout.addWidget(btn_refresh_models)

        btn_doctor = QPushButton("🩺 Doctor")
        btn_doctor.setToolTip("Doctor F3NIX: Diagnóstico y Salud del Sistema")
        btn_doctor.setStyleSheet("""
            QPushButton {
                background-color: #1A2333;
                color: #FFB703;
                border: 1px solid #3D3219;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #282110;
                color: #FFD166;
            }
        """)
        btn_doctor.clicked.connect(self.open_doctor_requested.emit)
        header_layout.addWidget(btn_doctor)

        # Botón conmutador Modo Turbo (5-10s en CPU) vs Modo Reflexión
        self.btn_turbo_toggle = QPushButton("⚡ Turbo: 5-10s")
        self.btn_turbo_toggle.setCheckable(True)
        self.btn_turbo_toggle.setChecked(True)
        self.btn_turbo_toggle.setToolTip("Modo Turbo: Optimiza la inferencia para responder en 5-10 segundos en CPU")
        self.btn_turbo_toggle.setStyleSheet("""
            QPushButton {
                background-color: #0E2E2A;
                color: #00E676;
                border: 1px solid #00BFA5;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00BFA5;
                color: #0B0F17;
            }
        """)
        self.btn_turbo_toggle.toggled.connect(self._on_turbo_toggle_clicked)
        header_layout.addWidget(self.btn_turbo_toggle)

        # Selector de voz
        voice_lbl = QLabel("🔊 Voz:")
        voice_lbl.setStyleSheet("color: #8C99B2; font-weight: bold;")
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(150)
        voices = {
            "es-MX-JorgeNeural": "Jorge (México)",
            "es-ES-AlvaroNeural": "Álvaro (España)",
            "es-ES-ElviraNeural": "Elvira (España)",
            "es-MX-DaliaNeural": "Dalia (México)"
        }
        for v_id, v_lbl in voices.items():
            self.voice_combo.addItem(v_lbl, v_id)
        self.voice_combo.currentIndexChanged.connect(self._on_voice_combo_changed)

        header_layout.addWidget(voice_lbl)
        header_layout.addWidget(self.voice_combo)

        # Botón para minimizar al HUD flotante
        hide_btn = QPushButton("🗕 Minimizar al HUD")
        hide_btn.setToolTip("Oculta esta ventana y continúa usando F3NIX desde el HUD flotante")
        hide_btn.clicked.connect(self.close)
        header_layout.addWidget(hide_btn)

        return header_layout

    # ---------------------------------------------------------
    # TAB 1: Chat & Canvas
    # ---------------------------------------------------------
    def _create_chat_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Historial de conversación con burbujas y soporte Markdown/HTML
        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setStyleSheet("""
            QTextBrowser {
                background-color: #0E131F;
                border: 1px solid #1E2739;
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.chat_display, stretch=1)

        # Mensaje de bienvenida inicial
        self._append_system_bubble("Bienvenido al Workspace F3NIX Studio. Mantén <b>F12</b> en cualquier ventana para hablar o escribe aquí abajo.")

        # Barra inferior de entrada
        input_container = QHBoxLayout()
        input_container.setSpacing(8)

        self.chat_input = QTextEdit()
        self.chat_input.setFixedHeight(50)
        self.chat_input.setPlaceholderText("Escribe un mensaje, código o comando a F3nix... (Ctrl+Enter para enviar)")
        
        send_btn = QPushButton("Enviar ➔")
        send_btn.setProperty("class", "primary")
        send_btn.setStyleSheet("background-color: #00E5FF; color: #000000; font-weight: bold; font-size: 13px; height: 46px; min-width: 90px;")
        send_btn.clicked.connect(self._send_chat_message)

        # Botón toggle para forzar búsqueda en tiempo real
        self.btn_web_toggle_chat = QPushButton("🌐 Web")
        self.btn_web_toggle_chat.setCheckable(True)
        self.btn_web_toggle_chat.setFixedHeight(46)
        self.btn_web_toggle_chat.setToolTip("Forzar búsqueda de datos en tiempo real con DuckDuckGo para noticias, cotizaciones o datos de hoy")
        self.btn_web_toggle_chat.toggled.connect(self._on_web_chat_toggled)

        clear_btn = QPushButton("🗑 Limpiar")
        clear_btn.setFixedHeight(46)
        clear_btn.clicked.connect(self._clear_chat_display)

        input_container.addWidget(self.chat_input, stretch=1)
        input_container.addWidget(self.btn_web_toggle_chat)
        input_container.addWidget(send_btn)
        input_container.addWidget(clear_btn)

        layout.addLayout(input_container)
        return widget

    def _on_web_chat_toggled(self, checked: bool):
        if checked:
            self.btn_web_toggle_chat.setStyleSheet("background-color: #00838F; color: #FFFFFF; font-weight: bold; height: 46px; border: 1px solid #00E5FF;")
        else:
            self.btn_web_toggle_chat.setStyleSheet("")

    def _on_turbo_toggle_clicked(self, checked: bool):
        if checked:
            self.btn_turbo_toggle.setText("⚡ Turbo: 5-10s")
            self.btn_turbo_toggle.setStyleSheet("""
                QPushButton {
                    background-color: #0E2E2A;
                    color: #00E676;
                    border: 1px solid #00BFA5;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
            """)
        else:
            self.btn_turbo_toggle.setText("🧠 Modo Reflexión")
            self.btn_turbo_toggle.setStyleSheet("""
                QPushButton {
                    background-color: #1A2333;
                    color: #8C99B2;
                    border: 1px solid #283952;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
            """)
        self.turbo_mode_changed.emit(checked)
        self.log_activity("Sistema", "Modo Turbo", "Activado (5-10s)" if checked else "Desactivado (Reflexión)")

    def _send_chat_message(self):
        text = self.chat_input.toPlainText().strip()
        if text:
            if hasattr(self, "btn_web_toggle_chat") and self.btn_web_toggle_chat.isChecked():
                if not text.lower().startswith("busca en internet"):
                    text = f"busca en internet {text}"
            self.chat_input.clear()
            self.append_chat_message("Tú", text)
            self.chat_submitted.emit(text)

    def _clear_chat_display(self):
        self.chat_display.clear()
        self._append_system_bubble("Historial de conversación visual reiniciado.")

    def _append_system_bubble(self, message: str):
        html = f"""
        <div style="margin: 8px 0; padding: 6px 12px; background: rgba(0, 229, 255, 0.08); border-left: 3px solid #00E5FF; border-radius: 4px; color: #8BE9FD; font-size: 11px;">
            ℹ️ {message}
        </div>
        """
        self.chat_display.append(html)

    def append_chat_message(self, sender: str, message: str):
        """Método público seguro que emite señal Qt para agregar mensajes al chat desde cualquier hilo."""
        self.chat_message_received.emit(sender, message)

    def _safe_append_chat_message(self, sender: str, message: str):
        is_user = sender.lower() in ["tú", "tu", "user", "fenix"]

        bg_color = "#192233" if is_user else "#132130"
        border_color = "#2F3F5C" if is_user else "#00E5FF"
        name_color = "#64B5F6" if is_user else "#00E5FF"
        align = "right" if is_user else "left"

        # Dar formato amigable a saltos de línea y bloques de código
        clean_msg = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        html = f"""
        <div style="margin: 10px 0; text-align: {align};">
            <div style="display: inline-block; max-width: 85%; text-align: left; background: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 10px 14px;">
                <div style="color: {name_color}; font-weight: bold; font-size: 11px; margin-bottom: 4px;">
                    {'👤 ' + sender if is_user else '⚡ ' + sender}
                </div>
                <div style="color: #E2E8F0; font-size: 12px; line-height: 1.5;">
                    {clean_msg}
                </div>
            </div>
        </div>
        """
        self.chat_display.append(html)
        # Auto scroll al final
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    # ---------------------------------------------------------
    # TAB 2: Bóveda de Memoria (Hermes Vault)
    # ---------------------------------------------------------
    def _create_memory_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Banner explicativo
        banner = QLabel("🧠 Bóveda de Memoria a Largo Plazo: F3NIX consulta estos recuerdos automáticamente para personalizar cada respuesta.")
        banner.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 12px; padding: 4px;")
        layout.addWidget(banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel Izquierdo: Perfil y Proyectos
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(10)

        profile_box = QFrame()
        profile_box.setProperty("class", "panel")
        profile_layout = QVBoxLayout(profile_box)
        profile_layout.setSpacing(8)

        prof_title = QLabel("👤 Perfil e Identidad del Usuario")
        prof_title.setStyleSheet("font-weight: bold; color: #00E5FF; font-size: 13px;")
        profile_layout.addWidget(prof_title)

        self.user_name_edit = QLineEdit()
        self.user_name_edit.setPlaceholderText("¿Cómo debe llamarte la IA? (ej: Fenix, Laura, Carlos)")
        profile_layout.addWidget(QLabel("Nombre o Alias:"))
        profile_layout.addWidget(self.user_name_edit)

        self.user_gender_combo = QComboBox()
        self.user_gender_combo.addItem("👨 Hombre / Masculino (Él - Estimado / Bienvenido / Listo)", "Hombre")
        self.user_gender_combo.addItem("👩 Mujer / Femenino (Ella - Estimada / Bienvenida / Lista)", "Mujer")
        self.user_gender_combo.addItem("🧑 Neutro / No binario (Estimad@ / Bienvenid@)", "Neutro")
        profile_layout.addWidget(QLabel("Género / Tratamiento Gramatical:"))
        profile_layout.addWidget(self.user_gender_combo)

        self.user_salutation_edit = QLineEdit()
        self.user_salutation_edit.setPlaceholderText("Ej: Comandante, Jefe/a, Doctor/a, o vacío para trato por nombre")
        profile_layout.addWidget(QLabel("Título o Saludo preferido:"))
        profile_layout.addWidget(self.user_salutation_edit)

        self.role_edit = QLineEdit()
        self.role_edit.setPlaceholderText("Rol / Profesión (ej: Desarrollador, Emprendedor/a, etc.)")
        profile_layout.addWidget(QLabel("Rol / Ocupación:"))
        profile_layout.addWidget(self.role_edit)

        self.tone_edit = QLineEdit()
        self.tone_edit.setPlaceholderText("Preferencia de tono (ej: Directo, técnico, resolutivo y amigable)")
        profile_layout.addWidget(QLabel("Tono preferido:"))
        profile_layout.addWidget(self.tone_edit)

        save_prof_btn = QPushButton("💾 Guardar Perfil & Tratamiento")
        save_prof_btn.setProperty("class", "primary")
        save_prof_btn.clicked.connect(self._save_profile_fields)
        profile_layout.addWidget(save_prof_btn)

        left_layout.addWidget(profile_box)

        # Proyectos Activos
        proj_box = QFrame()
        proj_box.setProperty("class", "panel")
        proj_layout = QVBoxLayout(proj_box)
        proj_title = QLabel("🚀 Proyectos en Marcha")
        proj_title.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 13px;")
        proj_layout.addWidget(proj_title)

        self.proj_name_input = QLineEdit()
        self.proj_name_input.setPlaceholderText("Nombre del proyecto...")
        self.proj_desc_input = QLineEdit()
        self.proj_desc_input.setPlaceholderText("Descripción breve...")
        add_proj_btn = QPushButton("+ Registrar Proyecto")
        add_proj_btn.clicked.connect(self._add_project_from_ui)

        proj_layout.addWidget(self.proj_name_input)
        proj_layout.addWidget(self.proj_desc_input)
        proj_layout.addWidget(add_proj_btn)

        left_layout.addWidget(proj_box)
        left_layout.addStretch()

        splitter.addWidget(left_panel)

        # Panel Derecho: Hechos Aprendidos (Facts)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)

        facts_title_row = QHBoxLayout()
        facts_title = QLabel("📜 Recuerdos y Hechos Aprendidos")
        facts_title.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 13px;")
        facts_title_row.addWidget(facts_title)
        facts_title_row.addStretch()

        btn_constitution = QPushButton("📜 Constitución F3NIX (v1.0)")
        btn_constitution.setToolTip("Abrir la Constitución Mental F3NIX: 10 módulos, principios éticos y toma de decisiones")
        btn_constitution.setStyleSheet("""
            QPushButton {
                background-color: #0C262E;
                color: #00E5FF;
                border: 1px solid #00838F;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00838F;
                color: #FFFFFF;
            }
        """)
        btn_constitution.clicked.connect(self._open_constitution_dialog)
        facts_title_row.addWidget(btn_constitution)

        self.btn_life_cases = QPushButton("📖 Casos de Vida")
        self.btn_life_cases.setToolTip("Ver y registrar situaciones de la vida real para calibrar el razonamiento de F3NIX")
        self.btn_life_cases.setStyleSheet("""
            QPushButton {
                background-color: #0E241A;
                color: #00E676;
                border: 1px solid #00BFA5;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00BFA5;
                color: #0B0F17;
            }
        """)
        self.btn_life_cases.clicked.connect(self._open_life_case_dialog)
        facts_title_row.addWidget(self.btn_life_cases)

        refresh_btn = QPushButton("🔄 Recargar")
        refresh_btn.clicked.connect(self.refresh_memory_view)
        facts_title_row.addWidget(refresh_btn)
        right_layout.addLayout(facts_title_row)

        self.facts_table = QTableWidget(0, 4)
        self.facts_table.setHorizontalHeaderLabels(["ID", "Fecha", "Recuerdo Grabado", "Acción"])
        self.facts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.facts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.facts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.facts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.facts_table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.facts_table)

        # Agregar recuerdo manualmente
        add_fact_row = QHBoxLayout()
        self.new_fact_input = QLineEdit()
        self.new_fact_input.setPlaceholderText("Escribe un nuevo hecho para que F3NIX recuerde siempre...")
        self.new_fact_input.returnPressed.connect(self._add_fact_from_ui)

        add_fact_btn = QPushButton("+ Grabar Recuerdo")
        add_fact_btn.clicked.connect(self._add_fact_from_ui)
        add_fact_row.addWidget(self.new_fact_input, stretch=1)
        add_fact_row.addWidget(add_fact_btn)

        right_layout.addLayout(add_fact_row)
        splitter.addWidget(right_panel)

        splitter.setSizes([340, 640])
        layout.addWidget(splitter)
        return widget

    def refresh_memory_view(self):
        """Lee los datos de f3nix_memory.json y los pinta en la UI."""
        self.memory.data = self.memory._load()
        data = self.memory.data

        self.user_name_edit.setText(self.memory.get_user_name())
        gender = self.memory.get_user_gender().lower()
        if "mujer" in gender or "femenin" in gender:
            self.user_gender_combo.setCurrentIndex(1)
        elif "neutro" in gender or "no binario" in gender:
            self.user_gender_combo.setCurrentIndex(2)
        else:
            self.user_gender_combo.setCurrentIndex(0)

        self.user_salutation_edit.setText(data.get("salutation", "Comandante"))
        self.role_edit.setText(data.get("role", "Desarrollador"))
        self.tone_edit.setText(data.get("tone_preference", "Técnico y conciso"))

        if hasattr(self, "btn_life_cases"):
            c_count = len(data.get("life_cases", []))
            self.btn_life_cases.setText(f"📖 Casos de Vida ({c_count})" if c_count > 0 else "📖 Casos de Vida")

        # Llenar tabla de hechos
        facts = data.get("facts", [])
        self.facts_table.setRowCount(0)
        for f in facts:
            row = self.facts_table.rowCount()
            self.facts_table.insertRow(row)

            id_item = QTableWidgetItem(str(f.get("id", "")))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.facts_table.setItem(row, 0, id_item)

            date_item = QTableWidgetItem(f.get("date", ""))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.facts_table.setItem(row, 1, date_item)

            text_item = QTableWidgetItem(f.get("text", ""))
            self.facts_table.setItem(row, 2, text_item)

            del_btn = QPushButton("✕ Borrar")
            del_btn.setStyleSheet("background-color: #3A1820; color: #FF4D6D; border: 1px solid #5A202A; font-size: 11px; padding: 2px 6px;")
            fact_id = f.get("id")
            del_btn.clicked.connect(lambda checked, fid=fact_id: self._delete_fact(fid))
            self.facts_table.setCellWidget(row, 3, del_btn)

    def _save_profile_fields(self):
        user_name = self.user_name_edit.text().strip() or "Usuario"
        g_idx = self.user_gender_combo.currentIndex()
        gender_val = "Hombre" if g_idx == 0 else ("Mujer" if g_idx == 1 else "Neutro")
        salutation_val = self.user_salutation_edit.text().strip()

        self.memory.data["user_name"] = user_name
        self.memory.data["user_gender"] = gender_val
        self.memory.data["salutation"] = salutation_val
        self.memory.data["role"] = self.role_edit.text().strip()
        self.memory.data["tone_preference"] = self.tone_edit.text().strip()
        self.memory._save()

        self._update_user_identity_labels()
        self.memory_updated.emit()
        self.log_activity("Memoria", "Perfil Actualizado", f"Usuario: {user_name} ({gender_val})")
        QMessageBox.information(
            self,
            "Perfil Guardado",
            f"Perfil e identidad actualizados con éxito.\n\n"
            f"F3NIX te llamará «{user_name}» con tratamiento {gender_val} y título «{salutation_val or user_name}» "
            f"en la Mesa Redonda, en el chat y por voz."
        )

    def _add_fact_from_ui(self):
        text = self.new_fact_input.text().strip()
        if text:
            self.memory.add_fact(text)
            self.new_fact_input.clear()
            self.refresh_memory_view()
            self.memory_updated.emit()
            self.log_activity("Memoria", "Recuerdo Creado Manualmente", text)

    def _delete_fact(self, fact_id: int):
        if self.memory.delete_fact(fact_id):
            self.refresh_memory_view()
            self.memory_updated.emit()
            self.log_activity("Memoria", "Recuerdo Eliminado", f"ID {fact_id}")

    def _add_project_from_ui(self):
        name = self.proj_name_input.text().strip()
        desc = self.proj_desc_input.text().strip()
        if name and desc:
            self.memory.add_project(name, desc)
            self.proj_name_input.clear()
            self.proj_desc_input.clear()
            self.memory_updated.emit()
            self.log_activity("Memoria", "Proyecto Registrado", f"{name}: {desc}")
            QMessageBox.information(self, "Proyecto Guardado", f"Proyecto '{name}' registrado en la memoria de F3NIX.")

    # ---------------------------------------------------------
    # TAB 3: Registro de Actividad de Agente (Live Timeline)
    # ---------------------------------------------------------
    def _create_activity_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_lbl = QLabel("⚡ Registro de Acciones y Herramientas del Agente en Tiempo Real")
        header_lbl.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 13px;")
        header_row.addWidget(header_lbl)
        header_row.addStretch()

        clear_btn = QPushButton("🗑 Limpiar Registro")
        clear_btn.clicked.connect(self._clear_activity_log)
        header_row.addWidget(clear_btn)
        layout.addLayout(header_row)

        self.activity_table = QTableWidget(0, 4)
        self.activity_table.setHorizontalHeaderLabels(["Hora", "Categoría", "Acción Ejecutada", "Detalles"])
        self.activity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.activity_table.verticalHeader().setVisible(False)
        layout.addWidget(self.activity_table)

        # Registrar evento de inicio
        self.log_activity("Sistema", "F3NIX Studio Iniciado", "Escuchando eventos de herramientas y voz")

        return widget

    def log_activity(self, category: str, action: str, details: str = ""):
        """Emite la señal de registro de actividad de forma segura entre hilos."""
        try:
            self.activity_logged.emit(category, action, details)
        except Exception:
            pass

    def _add_activity_row(self, category: str, action: str, details: str = ""):
        """Añade una fila al registro de actividad en el hilo principal de la interfaz."""
        if not hasattr(self, "activity_table"):
            return
        row = self.activity_table.rowCount()
        self.activity_table.insertRow(row)

        time_str = time.strftime("%H:%M:%S")
        time_item = QTableWidgetItem(time_str)
        time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activity_table.setItem(row, 0, time_item)

        cat_item = QTableWidgetItem(category)
        cat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Color según categoría
        if category == "Memoria":
            cat_item.setForeground(QColor("#00E5FF"))
        elif category == "Búsqueda Web":
            cat_item.setForeground(QColor("#FFB703"))
        elif category == "Visión":
            cat_item.setForeground(QColor("#00E676"))
        elif category == "Herramientas":
            cat_item.setForeground(QColor("#3A86FF"))
        elif category == "Inferencia":
            cat_item.setForeground(QColor("#BB86FC"))
        else:
            cat_item.setForeground(QColor("#ECEFF4"))
        
        self.activity_table.setItem(row, 1, cat_item)

        act_item = QTableWidgetItem(action)
        act_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.activity_table.setItem(row, 2, act_item)

        det_item = QTableWidgetItem(details)
        self.activity_table.setItem(row, 3, det_item)

        self.activity_table.scrollToBottom()

    def _clear_activity_log(self):
        self.activity_table.setRowCount(0)

    # ---------------------------------------------------------
    # TAB 4: Base de Conocimiento (RAG Local) & Documentos
    # ---------------------------------------------------------
    def _create_documents_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 1. Panel de RAG Local (Indexación de Carpetas de Código)
        rag_box = QFrame()
        rag_box.setProperty("class", "panel")
        rag_layout = QVBoxLayout(rag_box)
        rag_layout.setContentsMargins(14, 12, 14, 12)
        rag_layout.setSpacing(10)

        rag_header_row = QHBoxLayout()
        rag_title = QLabel("📁 Base de Conocimiento de Proyecto (RAG Local)")
        rag_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00E5FF;")
        rag_header_row.addWidget(rag_title)
        rag_header_row.addStretch()

        index_folder_btn = QPushButton("📂 Indexar Carpeta de Proyecto...")
        index_folder_btn.setProperty("class", "primary")
        index_folder_btn.setStyleSheet("background-color: #00E5FF; color: #000000; font-weight: bold;")
        index_folder_btn.clicked.connect(self._select_and_index_folder)
        rag_header_row.addWidget(index_folder_btn)

        self.reindex_btn = QPushButton("🔄 Reindexar")
        self.reindex_btn.clicked.connect(self._reindex_folder)
        rag_header_row.addWidget(self.reindex_btn)

        self.clear_rag_btn = QPushButton("✕ Limpiar RAG")
        self.clear_rag_btn.clicked.connect(self._clear_rag_index)
        rag_header_row.addWidget(self.clear_rag_btn)

        rag_layout.addLayout(rag_header_row)

        self.rag_status_lbl = QLabel("Sin carpeta indexada.")
        self.rag_status_lbl.setStyleSheet("color: #8C99B2; font-size: 12px;")
        rag_layout.addWidget(self.rag_status_lbl)

        # Buscador / Probador rápido de RAG
        test_row = QHBoxLayout()
        test_row.setSpacing(8)
        self.rag_search_input = QLineEdit()
        self.rag_search_input.setPlaceholderText("Probar búsqueda semántica en la carpeta indexada (ej: floating avatar, telemetría, chat)...")
        self.rag_search_input.returnPressed.connect(self._test_rag_search)

        rag_search_btn = QPushButton("🔍 Probar RAG")
        rag_search_btn.clicked.connect(self._test_rag_search)

        test_row.addWidget(self.rag_search_input, stretch=1)
        test_row.addWidget(rag_search_btn)
        rag_layout.addLayout(test_row)

        self.rag_test_results = QTextBrowser()
        self.rag_test_results.setMaximumHeight(85)
        self.rag_test_results.setStyleSheet("background: #0E131F; border: 1px solid #1E2739; border-radius: 6px; font-size: 11px; padding: 6px;")
        self.rag_test_results.setPlaceholderText("Los fragmentos de código más relevantes recuperados por el RAG se mostrarán aquí...")
        rag_layout.addWidget(self.rag_test_results)

        layout.addWidget(rag_box)

        # 2. Panel de Archivo Individual (Drag & Drop)
        doc_box = QFrame()
        doc_box.setProperty("class", "panel")
        doc_layout = QVBoxLayout(doc_box)
        doc_layout.setContentsMargins(14, 12, 14, 12)
        doc_layout.setSpacing(8)

        top_doc_row = QHBoxLayout()
        self.doc_status_lbl = QLabel("📄 Ningún archivo individual cargado actualmente.")
        self.doc_status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #8C99B2;")
        top_doc_row.addWidget(self.doc_status_lbl)
        top_doc_row.addStretch()

        load_file_btn = QPushButton("📂 Cargar Archivo...")
        load_file_btn.clicked.connect(self._select_and_load_file)
        top_doc_row.addWidget(load_file_btn)

        self.clear_doc_btn = QPushButton("✕ Quitar")
        self.clear_doc_btn.setEnabled(False)
        self.clear_doc_btn.clicked.connect(self._clear_document)
        top_doc_row.addWidget(self.clear_doc_btn)
        doc_layout.addLayout(top_doc_row)

        self.doc_preview = QTextEdit()
        self.doc_preview.setReadOnly(True)
        self.doc_preview.setPlaceholderText("El contenido del archivo arrastrado al avatar o abierto aquí se mostrará para su análisis...")
        doc_layout.addWidget(self.doc_preview, stretch=1)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.btn_summarize = QPushButton("📝 Resumir Archivo")
        self.btn_summarize.setEnabled(False)
        self.btn_summarize.clicked.connect(lambda: self._trigger_doc_action("Genera un resumen ejecutivo claro y conciso de este documento."))

        self.btn_keypoints = QPushButton("🔍 Puntos Clave")
        self.btn_keypoints.setEnabled(False)
        self.btn_keypoints.clicked.connect(lambda: self._trigger_doc_action("Extrae los puntos clave y lecciones más importantes de este documento."))

        self.btn_review = QPushButton("💡 Mejoras o Errores")
        self.btn_review.setEnabled(False)
        self.btn_review.clicked.connect(lambda: self._trigger_doc_action("Revisa este documento o código en busca de posibles errores, inconsistencias o áreas de mejora."))

        action_row.addWidget(self.btn_summarize)
        action_row.addWidget(self.btn_keypoints)
        action_row.addWidget(self.btn_review)
        action_row.addStretch()
        doc_layout.addLayout(action_row)

        layout.addWidget(doc_box, stretch=1)
        return widget

    def _refresh_rag_status(self):
        stats = self.rag.get_stats()
        if stats["has_index"]:
            text = f"🟢 <b>Carpeta Activa:</b> {stats['folder_name']} — {stats['files_count']} archivos ({stats['chunks_count']} fragmentos). Actualizado: {stats['last_indexed_at']}"
            self.rag_status_lbl.setText(text)
            self.rag_status_lbl.setStyleSheet("color: #00E5FF; font-size: 12px;")
            self.reindex_btn.setEnabled(True)
            self.clear_rag_btn.setEnabled(True)
        else:
            self.rag_status_lbl.setText("⚪ Ninguna carpeta de proyecto indexada. Haz clic en 'Indexar Carpeta' para que F3NIX conozca todo tu repositorio.")
            self.rag_status_lbl.setStyleSheet("color: #8C99B2; font-size: 12px;")
            self.reindex_btn.setEnabled(False)
            self.clear_rag_btn.setEnabled(False)

    def _select_and_index_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de proyecto para indexar en F3NIX RAG")
        if folder:
            self._execute_folder_indexing(folder)

    def _reindex_folder(self):
        if self.rag.folder_path and os.path.exists(self.rag.folder_path):
            self._execute_folder_indexing(self.rag.folder_path)

    def _execute_folder_indexing(self, folder: str):
        try:
            stats = self.rag.index_directory(folder)
            self._refresh_rag_status()
            self.folder_indexed.emit(stats["folder"], stats["files"], stats["chunks"])
            self.log_activity("RAG Local", "Proyecto Indexado", f"{stats['folder_name']} ({stats['files']} archivos, {stats['chunks']} fragmentos)")
            QMessageBox.information(
                self,
                "RAG Actualizado",
                f"Se han indexado {stats['files']} archivos ({stats['chunks']} fragmentos) de '{stats['folder_name']}'.\n\nF3NIX ahora puede responderte sobre cualquier archivo o función de este proyecto."
            )
        except Exception as e:
            QMessageBox.warning(self, "Error al Indexar", f"No se pudo indexar la carpeta: {e}")

    def _clear_rag_index(self):
        self.rag.clear_index()
        self._refresh_rag_status()
        self.rag_test_results.clear()
        self.log_activity("RAG Local", "Índice Eliminado", "Base de conocimiento borrada")

    def _test_rag_search(self):
        query = self.rag_search_input.text().strip()
        if not query:
            return
        matches = self.rag.query(query, top_k=3)
        if not matches:
            self.rag_test_results.setText("<i>No se encontraron fragmentos relevantes para esta consulta.</i>")
            return
        html_lines = [f"<b>Coincidencias encontradas ({len(matches)}):</b><br>"]
        for m in matches:
            clean_content = m['content'][:140].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            html_lines.append(
                f"• <b>{m['rel_path']}</b> (Líneas {m['start_line']}-{m['end_line']}) — <i>Score: {m['score']}</i><br>"
                f"<span style='color: #7F8C9F;'>{clean_content}...</span><br>"
            )
        self.rag_test_results.setHtml("".join(html_lines))

    def set_active_document(self, filename: str, content: str):
        """Actualiza el visor de documentos cuando se arrastra o carga un archivo."""
        self.doc_status_lbl.setText(f"📄 Documento Activo: {filename} ({len(content)} caracteres)")
        self.doc_status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #00E5FF;")
        self.doc_preview.setText(content[:10000] + ("\n... [Contenido truncado en la previsualización]" if len(content) > 10000 else ""))
        self.clear_doc_btn.setEnabled(True)
        self.btn_summarize.setEnabled(True)
        self.btn_keypoints.setEnabled(True)
        self.btn_review.setEnabled(True)
        self.log_activity("Documentos", "Archivo Cargado en Workspace", filename)

    def _select_and_load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar documento para F3NIX",
            "",
            "Archivos de Texto y Código (*.txt *.py *.md *.json *.js *.html *.css *.csv);;Todos los archivos (*.*)"
        )
        if file_path:
            try:
                filename = os.path.basename(file_path)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self.set_active_document(filename, content)
                self.file_loaded.emit(filename, content)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo leer el archivo: {e}")

    def _clear_document(self):
        self.doc_status_lbl.setText("📄 Ningún archivo individual cargado actualmente.")
        self.doc_status_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #8C99B2;")
        self.doc_preview.clear()
        self.clear_doc_btn.setEnabled(False)
        self.btn_summarize.setEnabled(False)
        self.btn_keypoints.setEnabled(False)
        self.btn_review.setEnabled(False)
        self.file_loaded.emit("", "")
        self.log_activity("Documentos", "Archivo Removido", "")

    def _trigger_doc_action(self, prompt: str):
        self.tabs.setCurrentIndex(0) # Cambiar al tab de Chat
        self.append_chat_message("Tú", prompt)
        self.chat_submitted.emit(prompt)

    # ---------------------------------------------------------
    # TAB 5: Mesa Redonda Multi-IA (Hermes & Multi-Agent Debate)
    # ---------------------------------------------------------
    def _create_council_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 1. Barra Superior Compacta de Roles & Control (~36px)
        compact_bar = QFrame()
        compact_bar.setStyleSheet("""
            QFrame {
                background: #0E1522;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 4px 8px;
            }
        """)
        compact_layout = QHBoxLayout(compact_bar)
        compact_layout.setContentsMargins(6, 4, 6, 4)
        compact_layout.setSpacing(6)

        title_lbl = QLabel("🏛️ Mesa Redonda")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #00E5FF; padding-right: 4px;")
        compact_layout.addWidget(title_lbl)

        # Botón Selector de Modo de Pensamiento (10 Modos Especializados)
        self.btn_pick_mode = QPushButton("🏛️ Clásico ▾")
        self.btn_pick_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_mode.setToolTip("Modo de Pensamiento Dialéctico de la Mesa Redonda (Haz clic para cambiar)")
        self.btn_pick_mode.setStyleSheet("""
            QPushButton {
                background-color: #171E2D;
                color: #00E5FF;
                border: 1px solid #00E5FF;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00E5FF;
                color: #0B0F17;
            }
        """)
        self.btn_pick_mode.clicked.connect(lambda: self._show_council_modes_menu(self.btn_pick_mode))
        compact_layout.addWidget(self.btn_pick_mode)

        # 3 Botones Interactivos de Roles (Chips Plegables)
        self.btn_pick_estratega = QPushButton("🔵 Estratega: Seleccionar ▾")
        self.btn_pick_estratega.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_estratega.setToolTip("Haz clic para elegir la IA del Estratega")
        self.btn_pick_estratega.setStyleSheet("""
            QPushButton {
                background-color: #111A29;
                color: #8BE9FD;
                border: 1px solid #1E3A5F;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1A283D;
                border-color: #00E5FF;
            }
        """)
        self.btn_pick_estratega.clicked.connect(lambda: self._show_model_picker_menu("estratega", self.btn_pick_estratega))
        compact_layout.addWidget(self.btn_pick_estratega)

        self.btn_pick_critico = QPushButton("🔴 Crítico: Seleccionar ▾")
        self.btn_pick_critico.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_critico.setToolTip("Haz clic para elegir la IA del Crítico")
        self.btn_pick_critico.setStyleSheet("""
            QPushButton {
                background-color: #24141A;
                color: #FF8A80;
                border: 1px solid #4D1E27;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #381B23;
                border-color: #FF5252;
            }
        """)
        self.btn_pick_critico.clicked.connect(lambda: self._show_model_picker_menu("critico", self.btn_pick_critico))
        compact_layout.addWidget(self.btn_pick_critico)

        self.btn_pick_director = QPushButton("🟢 Director: Seleccionar ▾")
        self.btn_pick_director.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_director.setToolTip("Haz clic para elegir la IA del Director F3NIX")
        self.btn_pick_director.setStyleSheet("""
            QPushButton {
                background-color: #0E211A;
                color: #B9F6CA;
                border: 1px solid #184833;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16362A;
                border-color: #00E676;
            }
        """)
        self.btn_pick_director.clicked.connect(lambda: self._show_model_picker_menu("director", self.btn_pick_director))
        compact_layout.addWidget(self.btn_pick_director)

        # Botón de Selección de Rondas
        self.btn_pick_rounds = QPushButton("⚔️ 2 Rondas ▾")
        self.btn_pick_rounds.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_rounds.setToolTip("Modo de debate (1, 2 o 3 rondas dialécticas)")
        self.btn_pick_rounds.setStyleSheet("""
            QPushButton {
                background-color: #1C190D;
                color: #FFB703;
                border: 1px solid #6E5316;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2E2612;
                border-color: #FFB703;
            }
        """)
        self.btn_pick_rounds.clicked.connect(lambda: self._show_rounds_picker_menu(self.btn_pick_rounds))
        compact_layout.addWidget(self.btn_pick_rounds)

        # Botón Expandir/Plegar Panel Completo
        self.btn_toggle_config = QPushButton("⚙️ Ajustes ▾")
        self.btn_toggle_config.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_config.setToolTip("Mostrar/Ocultar detalles de roles y consejos de velocidad")
        self.btn_toggle_config.setStyleSheet("""
            QPushButton {
                background-color: #141A26;
                color: #8C99B2;
                border: 1px solid #232C3D;
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1E2738;
                color: #ECEFF4;
            }
        """)
        self.btn_toggle_config.clicked.connect(self._toggle_council_config_panel)
        compact_layout.addWidget(self.btn_toggle_config)

        help_btn = QPushButton("💡 Guía")
        help_btn.setToolTip("Aprende qué IA es mejor para cada rol y por qué")
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #162438;
                color: #00E5FF;
                border: 1px solid #00E5FF;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #00E5FF;
                color: #000000;
            }
        """)
        help_btn.clicked.connect(self._open_council_guide)
        compact_layout.addWidget(help_btn)

        btn_const_council = QPushButton("⚖️ Constitución")
        btn_const_council.setToolTip("Consultar la Constitución Mental F3NIX (10 módulos) que rige las decisiones del Director")
        btn_const_council.setStyleSheet("""
            QPushButton {
                background-color: #0E241A;
                color: #00E676;
                border: 1px solid #00BFA5;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #00BFA5;
                color: #0B0F17;
            }
        """)
        btn_const_council.clicked.connect(self._open_constitution_dialog)
        compact_layout.addWidget(btn_const_council)

        # Botón Toggle de Narración en Voz Alta con Voces Diferenciadas
        self.btn_toggle_council_voice = QPushButton("🔇 Narrar: OFF")
        self.btn_toggle_council_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_council_voice.setToolTip("Activar o desactivar la lectura en voz alta secuencial del debate con voces diferenciadas")
        self._update_council_voice_button_style()
        self.btn_toggle_council_voice.clicked.connect(self._toggle_council_voice)
        compact_layout.addWidget(self.btn_toggle_council_voice)

        self.council_status_badge = QLabel("⚪ Inactivo")
        self.council_status_badge.setStyleSheet("font-size: 11px; color: #8C99B2; background: #0E1521; padding: 3px 10px; border-radius: 10px; border: 1px solid #1E2738;")
        compact_layout.addWidget(self.council_status_badge)

        layout.addWidget(compact_bar)

        # Panel Extendido de Configuración (Colapsado por defecto para ganar máximo espacio)
        self.config_details_box = QFrame()
        self.config_details_box.setProperty("class", "panel")
        config_layout = QVBoxLayout(self.config_details_box)
        config_layout.setContentsMargins(10, 8, 10, 8)
        config_layout.setSpacing(6)

        desc_lbl = QLabel(
            "Debate universal con múltiples modelos locales: salud, entrenamiento físico, negocios, decisiones de vida, tecnología o filosofía. "
            "Selecciona entre 10 Modos de Pensamiento Dialéctico especializados para activar arquetipos y metodologías a medida."
        )
        desc_lbl.setStyleSheet("color: #8C99B2; font-size: 11px;")
        desc_lbl.setWordWrap(True)
        config_layout.addWidget(desc_lbl)

        # Selector de Modo de Pensamiento
        mode_select_row = QHBoxLayout()
        mode_select_row.setSpacing(8)
        mode_select_lbl = QLabel("🧠 Modo de Pensamiento:")
        mode_select_lbl.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 11px;")
        mode_select_row.addWidget(mode_select_lbl)

        self.combo_council_mode = QComboBox()
        for mode_k, mode_v in DEBATE_MODES.items():
            self.combo_council_mode.addItem(f"{mode_v['name']}", mode_k)
        self.combo_council_mode.setCurrentIndex(0)
        self.combo_council_mode.setStyleSheet("""
            QComboBox {
                background: #111A29;
                border: 1px solid #1E3A5F;
                color: #ECEFF4;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        self.combo_council_mode.currentIndexChanged.connect(lambda idx: self._set_council_mode(self.combo_council_mode.itemData(idx)))
        mode_select_row.addWidget(self.combo_council_mode, stretch=1)
        config_layout.addLayout(mode_select_row)

        # Selector de Rondas / Modo de Debate Dialéctico
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_lbl = QLabel("⚔️ Rondas de Debate:")
        mode_lbl.setStyleSheet("color: #FFB703; font-weight: bold; font-size: 11px;")
        mode_row.addWidget(mode_lbl)

        self.combo_council_rounds = QComboBox()
        self.combo_council_rounds.addItem("🔥 2 Rondas (Debate Dialéctico: Réplica y Contra-réplica)", 2)
        self.combo_council_rounds.addItem("⚡ 1 Ronda (Rápida: Tesis, Antítesis y Síntesis)", 1)
        self.combo_council_rounds.addItem("🧠 3 Rondas (Debate a Fondo: Máxima Confrontación)", 3)
        self.combo_council_rounds.setCurrentIndex(0)
        self.combo_council_rounds.setStyleSheet("""
            QComboBox {
                background: #111A29;
                border: 1px solid #1E3A5F;
                color: #ECEFF4;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        self.combo_council_rounds.currentIndexChanged.connect(lambda: self._update_role_chips_text())
        mode_row.addWidget(self.combo_council_rounds, stretch=1)
        config_layout.addLayout(mode_row)

        # 3 Cards para cada rol
        roles_layout = QHBoxLayout()
        roles_layout.setSpacing(10)

        # Rol 1: Estratega / Proponente
        card_estratega = QFrame()
        card_estratega.setStyleSheet("background: #111A29; border: 1px solid #1E3A5F; border-radius: 6px; padding: 6px;")
        c1_lay = QVBoxLayout(card_estratega)
        c1_lay.setContentsMargins(6, 6, 6, 6)
        c1_lay.setSpacing(4)
        self.card_title_1 = QLabel("🔵 Estratega Creativo")
        self.card_title_1.setStyleSheet("font-weight: bold; color: #00E5FF; font-size: 11px;")
        self.card_desc_1 = QLabel("Propone el plan y la estrategia inicial")
        self.card_desc_1.setStyleSheet("color: #7F8C9F; font-size: 10px;")
        self.combo_estratega = QComboBox()
        self.combo_estratega.currentTextChanged.connect(lambda: self._update_role_chips_text())
        c1_lay.addWidget(self.card_title_1)
        c1_lay.addWidget(self.card_desc_1)
        c1_lay.addWidget(self.combo_estratega)
        roles_layout.addWidget(card_estratega)

        # Rol 2: Crítico / Auditor
        card_critico = QFrame()
        card_critico.setStyleSheet("background: #24141A; border: 1px solid #4D1E27; border-radius: 6px; padding: 6px;")
        c2_lay = QVBoxLayout(card_critico)
        c2_lay.setContentsMargins(6, 6, 6, 6)
        c2_lay.setSpacing(4)
        self.card_title_2 = QLabel("🔴 Crítico de Riesgos")
        self.card_title_2.setStyleSheet("font-weight: bold; color: #FF5252; font-size: 11px;")
        self.card_desc_2 = QLabel("Audita riesgos, trampas y viabilidad")
        self.card_desc_2.setStyleSheet("color: #7F8C9F; font-size: 10px;")
        self.combo_critico = QComboBox()
        self.combo_critico.currentTextChanged.connect(lambda: self._update_role_chips_text())
        c2_lay.addWidget(self.card_title_2)
        c2_lay.addWidget(self.card_desc_2)
        c2_lay.addWidget(self.combo_critico)
        roles_layout.addWidget(card_critico)

        # Rol 3: Director / Juez / Síntesis
        card_director = QFrame()
        card_director.setStyleSheet("background: #0E211A; border: 1px solid #184833; border-radius: 6px; padding: 6px;")
        c3_lay = QVBoxLayout(card_director)
        c3_lay.setContentsMargins(6, 6, 6, 6)
        c3_lay.setSpacing(4)
        self.card_title_3 = QLabel("🟢 Director F3NIX (Constitución v1.0)")
        self.card_title_3.setStyleSheet("font-weight: bold; color: #00E676; font-size: 11px;")
        self.card_desc_3 = QLabel("Gobernado por la Constitución Mental F3NIX")
        self.card_desc_3.setStyleSheet("color: #7F8C9F; font-size: 10px;")
        self.combo_director = QComboBox()
        self.combo_director.currentTextChanged.connect(lambda: self._update_role_chips_text())
        c3_lay.addWidget(self.card_title_3)
        c3_lay.addWidget(self.card_desc_3)
        c3_lay.addWidget(self.combo_director)
        roles_layout.addWidget(card_director)

        config_layout.addLayout(roles_layout)

        # Consejo de velocidad para inferencia en CPU
        cpu_hint = QLabel("⚡ <i>Consejo de Velocidad:</i> Al ejecutar en procesador (CPU), los modelos 8B razonan a fondo y tardan ~1-3 min. Para respuestas ultrarrápidas (10-20 segundos), selecciona <b>llama3.2:3b</b> en uno o más roles.")
        cpu_hint.setStyleSheet("color: #7E8D9F; font-size: 10px; margin: 1px 4px;")
        config_layout.addWidget(cpu_hint)

        # Oculto por defecto para maximizar el espacio de lectura de la charla
        self.config_details_box.setVisible(False)
        layout.addWidget(self.config_details_box)

        # 2. Área Central: Visor del Debate
        self.debate_browser = QTextBrowser()
        self.debate_browser.setOpenExternalLinks(False)
        self.debate_browser.anchorClicked.connect(self._on_debate_anchor_clicked)
        self.debate_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #0B0F17;
                border: 1px solid #1E2739;
                border-radius: 8px;
                padding: 12px;
                font-size: 12px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.debate_browser, stretch=1)
        self._set_council_welcome_content()

        # Variables de control de autoscroll inteligente
        self._council_auto_scroll = True
        self._council_saved_scroll_pos = 0
        self._council_last_render_time = 0

        # Conectar señales del scrollbar para autoscroll inteligente y seguimiento en tiempo real
        sb = self.debate_browser.verticalScrollBar()
        sb.actionTriggered.connect(self._on_council_scroll_action_triggered)
        sb.rangeChanged.connect(self._on_council_scroll_range_changed)
        self.debate_browser.viewport().installEventFilter(self)

        # Botón flotante / indicador para volver al final cuando el usuario hace scroll hacia arriba
        self.btn_council_scroll_bottom = QPushButton("⬇️ Bajar al final & Seguir debate en vivo")
        self.btn_council_scroll_bottom.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_council_scroll_bottom.setStyleSheet("""
            QPushButton {
                background-color: #162438;
                color: #00E5FF;
                border: 1px solid #00E5FF;
                border-radius: 5px;
                padding: 5px 14px;
                font-weight: bold;
                font-size: 11px;
                margin: 2px 0;
            }
            QPushButton:hover {
                background-color: #00E5FF;
                color: #0B0F17;
            }
        """)
        self.btn_council_scroll_bottom.setVisible(False)
        self.btn_council_scroll_bottom.clicked.connect(self._scroll_council_to_bottom)
        layout.addWidget(self.btn_council_scroll_bottom)

        # Barra de Intervención en Vivo de Fenix (Presidente de Mesa)
        self.intervention_frame = QFrame()
        self.intervention_frame.setStyleSheet("""
            QFrame {
                background-color: #1F180A;
                border: 1px solid #6E5316;
                border-radius: 6px;
                padding: 4px 8px;
                margin-top: 4px;
            }
        """)
        interv_layout = QHBoxLayout(self.intervention_frame)
        interv_layout.setContentsMargins(4, 4, 4, 4)
        interv_layout.setSpacing(8)

        self.interv_lbl = QLabel(f"👑 <b>Orden de {self.memory.get_user_name()}:</b>")
        self.interv_lbl.setStyleSheet("color: #FFB703; font-size: 11px;")
        interv_layout.addWidget(self.interv_lbl)

        self.intervention_input = QLineEdit()
        self.intervention_input.setPlaceholderText(f"Escribe tu orden para la Mesa ({self.memory.get_user_name()})...")
        self.intervention_input.setStyleSheet("""
            QLineEdit {
                background: #0B0F17;
                border: 1px solid #6E5316;
                color: #FFF8E1;
                padding: 5px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        self.intervention_input.returnPressed.connect(self._submit_user_intervention)
        interv_layout.addWidget(self.intervention_input, stretch=1)

        self.btn_send_intervention = QPushButton("🚀 Enviar a la Mesa")
        self.btn_send_intervention.setStyleSheet("background-color: #FFB703; color: #000000; font-weight: bold; font-size: 11px; padding: 5px 12px; border-radius: 4px;")
        self.btn_send_intervention.clicked.connect(self._submit_user_intervention)
        interv_layout.addWidget(self.btn_send_intervention)

        btn_close_interv = QPushButton("✖")
        btn_close_interv.setFixedWidth(24)
        btn_close_interv.setStyleSheet("background: transparent; color: #8C99B2; border: none; font-weight: bold; font-size: 12px;")
        btn_close_interv.clicked.connect(lambda: self.intervention_frame.setVisible(False))
        interv_layout.addWidget(btn_close_interv)

        self.intervention_frame.setVisible(False)
        layout.addWidget(self.intervention_frame)

        # 3. Presets y Plantillas de debate (Totalmente personalizables por cada usuario)
        self.presets_container = QWidget()
        self.presets_layout = QHBoxLayout(self.presets_container)
        self.presets_layout.setContentsMargins(0, 0, 0, 0)
        self.presets_layout.setSpacing(6)
        layout.addWidget(self.presets_container)
        self._refresh_council_presets_bar()

        # 3.5 Barra de Archivo Adjunto (Modo Híbrido: Directo / Resumen Ejecutivo)
        self.attached_file_data: Optional[Dict[str, Any]] = None
        self._debate_attached_file: Optional[Dict[str, Any]] = None

        self.attached_file_frame = QFrame()
        self.attached_file_frame.setStyleSheet("""
            QFrame {
                background-color: #0E1624;
                border: 1px solid #1E3A5F;
                border-left: 4px solid #00E5FF;
                border-radius: 6px;
                padding: 3px 8px;
                margin-top: 2px;
                margin-bottom: 2px;
            }
        """)
        f_layout = QHBoxLayout(self.attached_file_frame)
        f_layout.setContentsMargins(4, 2, 4, 2)
        f_layout.setSpacing(8)

        self.lbl_attached_file_info = QLabel("📁 Archivo adjunto")
        self.lbl_attached_file_info.setStyleSheet("color: #ECEFF4; font-size: 11px; font-weight: 500;")
        f_layout.addWidget(self.lbl_attached_file_info, stretch=1)

        self.btn_attached_file_mode = QPushButton("⚡ Modo Directo 100% ▾")
        self.btn_attached_file_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_attached_file_mode.setToolTip("Haz clic para cambiar el modo de análisis del archivo")
        self.btn_attached_file_mode.clicked.connect(self._show_file_mode_menu)
        f_layout.addWidget(self.btn_attached_file_mode)

        btn_remove_file = QPushButton("✖")
        btn_remove_file.setFixedWidth(24)
        btn_remove_file.setToolTip("Quitar archivo adjunto")
        btn_remove_file.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove_file.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #FF8A80;
                border: none;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #FF5252;
                background: rgba(255, 82, 82, 0.15);
                border-radius: 3px;
            }
        """)
        btn_remove_file.clicked.connect(self._remove_attached_file)
        f_layout.addWidget(btn_remove_file)

        self.attached_file_frame.setVisible(False)
        layout.addWidget(self.attached_file_frame)

        # 4. Panel Inferior: Input y Botones de Acción
        bottom_box = QHBoxLayout()
        bottom_box.setSpacing(8)

        self.council_topic_input = QTextEdit()
        self.council_topic_input.setFixedHeight(52)
        self.council_topic_input.setPlaceholderText("Escribe aquí libremente tu consulta, dilema, proyecto o desafío... (Ctrl+Enter para debatir)")

        btn_box = QVBoxLayout()
        btn_box.setSpacing(4)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        self.btn_start_debate = QPushButton("▶️ Iniciar Debate Multi-IA")
        self.btn_start_debate.setProperty("class", "primary")
        self.btn_start_debate.setStyleSheet("background-color: #00E5FF; color: #000000; font-weight: bold; font-size: 12px; height: 32px;")
        self.btn_start_debate.clicked.connect(self._start_council_debate)

        self.btn_attach_file = QPushButton("📎 Adjuntar")
        self.btn_attach_file.setFixedHeight(32)
        self.btn_attach_file.setToolTip("Adjunta código (.py, .js), notas (.txt, .md), datos (.json, .csv) o documentos (.pdf) para auditar")
        self.btn_attach_file.setStyleSheet("""
            QPushButton {
                background-color: #111E30;
                color: #8BE9FD;
                border: 1px solid #1E3A5F;
                font-weight: bold;
                font-size: 11px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #1A2B44;
                border-color: #00E5FF;
                color: #00E5FF;
            }
        """)
        self.btn_attach_file.clicked.connect(self._attach_council_file)
        action_row.addWidget(self.btn_attach_file)

        self.btn_intervene = QPushButton(f"👑 Intervenir ({self.memory.get_user_name()})")
        self.btn_intervene.setEnabled(False)
        self.btn_intervene.setFixedHeight(32)
        self.btn_intervene.setStyleSheet("background-color: #2E220D; color: #FFB703; border: 1px solid #6E5316; font-weight: bold; font-size: 11px;")
        self.btn_intervene.setToolTip("Envía una orden directa a la Mesa Redonda para que las IAs ajusten su discusión")
        self.btn_intervene.clicked.connect(self._toggle_intervention_bar)

        self.btn_stop_debate = QPushButton("⏹️ Detener")
        self.btn_stop_debate.setEnabled(False)
        self.btn_stop_debate.setFixedHeight(32)
        self.btn_stop_debate.clicked.connect(self._stop_council_debate)

        self.btn_save_council_memory = QPushButton("💾 Guardar en Bóveda")
        self.btn_save_council_memory.setEnabled(False)
        self.btn_save_council_memory.setFixedHeight(32)
        self.btn_save_council_memory.setToolTip("Almacena la síntesis y el plan maestro en la memoria a largo plazo de F3NIX")
        self.btn_save_council_memory.clicked.connect(self._save_council_to_memory)

        self.btn_export_pdf = QPushButton("📄 Exportar PDF")
        self.btn_export_pdf.setEnabled(False)
        self.btn_export_pdf.setFixedHeight(32)
        self.btn_export_pdf.setToolTip("Exporta el informe completo del debate dialéctico a un documento PDF profesional")
        self.btn_export_pdf.setStyleSheet("""
            QPushButton {
                background-color: #102B1E;
                color: #00E676;
                border: 1px solid #1E5C3C;
                font-weight: bold;
                font-size: 11px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #184430;
                border-color: #00E676;
            }
            QPushButton:disabled {
                background-color: #0E1A14;
                color: #4A6354;
                border-color: #182A20;
            }
        """)
        self.btn_export_pdf.clicked.connect(self._export_council_to_pdf)

        self.btn_clear_debate = QPushButton("🗑 Limpiar")
        self.btn_clear_debate.setFixedHeight(32)
        self.btn_clear_debate.clicked.connect(self._clear_council_display)

        action_row.addWidget(self.btn_start_debate)
        action_row.addWidget(self.btn_intervene)
        action_row.addWidget(self.btn_stop_debate)
        action_row.addWidget(self.btn_save_council_memory)
        action_row.addWidget(self.btn_export_pdf)
        action_row.addWidget(self.btn_clear_debate)

        btn_box.addLayout(action_row)

        bottom_box.addWidget(self.council_topic_input, stretch=1)
        bottom_box.addLayout(btn_box)

        layout.addLayout(bottom_box)

        self._update_role_chips_text()
        return widget

    def _update_role_chips_text(self):
        """Actualiza el texto y tooltip de los 3 botones superiores de selección rápida de IA, modo y rondas."""
        mode_key = getattr(self, "current_council_mode", "clasico")
        mode_info = DEBATE_MODES.get(mode_key, DEBATE_MODES["clasico"])

        if hasattr(self, "btn_pick_mode"):
            self.btn_pick_mode.setText(f"{mode_info['short_name']} ▾")
            self.btn_pick_mode.setToolTip(f"{mode_info['name']}\n{mode_info['description']}")

        lbl_1 = mode_info.get("role_1_label", "🔵 Rol 1")
        lbl_2 = mode_info.get("role_2_label", "🔴 Rol 2")
        lbl_dir = mode_info.get("role_director_label", "🟢 Director F3NIX")

        if hasattr(self, "btn_pick_estratega") and hasattr(self, "combo_estratega"):
            m = self.combo_estratega.currentText().strip()
            short_m = m.split("/")[-1] if "/" in m else m
            short_m = short_m.split(":")[0] if ":" in short_m else short_m
            short_m = short_m if len(short_m) <= 12 else short_m[:10] + "…"
            self.btn_pick_estratega.setText(f"{lbl_1}: {short_m or 'Elegir'} ▾")
            self.btn_pick_estratega.setToolTip(f"{lbl_1}\nCerebro actual: {m or 'Ninguno'}")

        if hasattr(self, "btn_pick_critico") and hasattr(self, "combo_critico"):
            m = self.combo_critico.currentText().strip()
            short_m = m.split("/")[-1] if "/" in m else m
            short_m = short_m.split(":")[0] if ":" in short_m else short_m
            short_m = short_m if len(short_m) <= 12 else short_m[:10] + "…"
            self.btn_pick_critico.setText(f"{lbl_2}: {short_m or 'Elegir'} ▾")
            self.btn_pick_critico.setToolTip(f"{lbl_2}\nCerebro actual: {m or 'Ninguno'}")

        if hasattr(self, "btn_pick_director") and hasattr(self, "combo_director"):
            m = self.combo_director.currentText().strip()
            short_m = m.split("/")[-1] if "/" in m else m
            short_m = short_m.split(":")[0] if ":" in short_m else short_m
            short_m = short_m if len(short_m) <= 12 else short_m[:10] + "…"
            self.btn_pick_director.setText(f"{lbl_dir}: {short_m or 'Elegir'} ▾")
            self.btn_pick_director.setToolTip(f"{lbl_dir}\nCerebro actual: {m or 'Ninguno'}")

        if hasattr(self, "btn_pick_rounds") and hasattr(self, "combo_council_rounds"):
            rounds = self.combo_council_rounds.currentData() or 2
            self.btn_pick_rounds.setText(f"⚔️ {rounds} Rondas ▾")

    def _show_council_modes_menu(self, button: QPushButton):
        """Muestra un menú interactivo para alternar entre los 10 Modos de Pensamiento Dialéctico."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0E1522;
                color: #ECEFF4;
                border: 1px solid #1E3A5F;
                border-radius: 6px;
                padding: 4px;
                font-size: 11px;
            }
            QMenu::item {
                padding: 7px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #00E5FF;
                color: #0B0F17;
                font-weight: bold;
            }
        """)

        current_m = getattr(self, "current_council_mode", "clasico")
        for mode_id, mode_data in DEBATE_MODES.items():
            prefix = "✓ " if mode_id == current_m else "   "
            action = menu.addAction(f"{prefix}{mode_data['name']}")
            action.setToolTip(mode_data["description"])
            def make_handler(m_id=mode_id):
                def handler():
                    self._set_council_mode(m_id)
                return handler
            action.triggered.connect(make_handler(mode_id))

        menu.exec(button.mapToGlobal(QPoint(0, button.height() + 2)))

    def _set_council_mode(self, mode_id: str):
        """Aplica un nuevo modo de debate dialéctico, actualizando interfaz, roles y bienvenida."""
        if mode_id not in DEBATE_MODES:
            mode_id = "clasico"
        self.current_council_mode = mode_id

        if hasattr(self, "combo_council_mode"):
            for i in range(self.combo_council_mode.count()):
                if self.combo_council_mode.itemData(i) == mode_id:
                    self.combo_council_mode.blockSignals(True)
                    self.combo_council_mode.setCurrentIndex(i)
                    self.combo_council_mode.blockSignals(False)
                    break

        mode_info = DEBATE_MODES[mode_id]
        if hasattr(self, "card_title_1"):
            self.card_title_1.setText(mode_info.get("role_1_label", "🔵 Rol 1"))
        if hasattr(self, "card_title_2"):
            self.card_title_2.setText(mode_info.get("role_2_label", "🔴 Rol 2"))
        if hasattr(self, "card_title_3"):
            self.card_title_3.setText(mode_info.get("role_director_label", "🟢 Director"))

        self._update_role_chips_text()
        self.log_activity("Mesa Redonda", "Modo Activado", mode_info["name"])

        if not getattr(self, "_debate_turns_history", []):
            self._set_council_welcome_content()

    def _show_model_picker_menu(self, role: str, button: QPushButton):
        """Muestra un menú desplegable elegante para elegir la IA del rol. Se cierra automáticamente tras elegir."""
        combo = {
            "estratega": getattr(self, "combo_estratega", None),
            "critico": getattr(self, "combo_critico", None),
            "director": getattr(self, "combo_director", None)
        }.get(role)

        if not combo:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0E1522;
                color: #ECEFF4;
                border: 1px solid #1E3A5F;
                border-radius: 6px;
                padding: 4px;
                font-size: 11px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1E3A5F;
                color: #00E5FF;
            }
        """)

        current_model = combo.currentText()
        count = combo.count()
        models = [combo.itemText(i) for i in range(count)] if count > 0 else []
        if not models and hasattr(self, "model_combo"):
            models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]

        if not models:
            action = menu.addAction("No hay modelos detectados en Ollama")
            action.setEnabled(False)
        else:
            for m in models:
                prefix = "✓ " if m == current_model else "   "
                action = menu.addAction(f"{prefix}{m}")
                def make_handler(model_val=m):
                    def handler():
                        idx = combo.findText(model_val)
                        if idx >= 0:
                            combo.setCurrentIndex(idx)
                        else:
                            combo.addItem(model_val)
                            combo.setCurrentText(model_val)
                        self._update_role_chips_text()
                        self.log_activity("Mesa Redonda", f"Modelo {role.capitalize()}", model_val)
                    return handler
                action.triggered.connect(make_handler(m))

        menu.exec(button.mapToGlobal(QPoint(0, button.height() + 2)))

    def _show_rounds_picker_menu(self, button: QPushButton):
        """Muestra un menú desplegable elegante para elegir el número de rondas de debate."""
        if not hasattr(self, "combo_council_rounds"):
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0E1522;
                color: #ECEFF4;
                border: 1px solid #6E5316;
                border-radius: 6px;
                padding: 4px;
                font-size: 11px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2E2612;
                color: #FFB703;
            }
        """)

        current_r = self.combo_council_rounds.currentData() or 2
        options = [
            ("⚡ 1 Ronda (Rápida: Tesis, Antítesis y Síntesis)", 1),
            ("🔥 2 Rondas (Debate Dialéctico: Réplica y Contra-réplica)", 2),
            ("🧠 3 Rondas (Debate a Fondo: Máxima Confrontación)", 3),
        ]
        for title, val in options:
            prefix = "✓ " if val == current_r else "   "
            action = menu.addAction(f"{prefix}{title}")
            def make_handler(rounds_val=val):
                def handler():
                    for i in range(self.combo_council_rounds.count()):
                        if self.combo_council_rounds.itemData(i) == rounds_val:
                            self.combo_council_rounds.setCurrentIndex(i)
                            break
                    self._update_role_chips_text()
                    self.log_activity("Mesa Redonda", "Modo de Rondas", f"{rounds_val} Rondas")
                return handler
            action.triggered.connect(make_handler(val))

        menu.exec(button.mapToGlobal(QPoint(0, button.height() + 2)))

    def _toggle_council_config_panel(self):
        """Alterna la visibilidad del panel detallado de configuración para ahorrar espacio."""
        if hasattr(self, "config_details_box"):
            make_visible = self.config_details_box.isHidden()
            self.config_details_box.setVisible(make_visible)
            if hasattr(self, "btn_toggle_config"):
                self.btn_toggle_config.setText("⚙️ Ajustes ▲" if make_visible else "⚙️ Ajustes ▾")

    def _attach_council_file(self):
        """Abre un diálogo nativo para cargar un archivo (código, texto, JSON, PDF o imagen con texto) para el debate."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Archivo para la Mesa Redonda",
            "",
            "Archivos Compatibles (*.txt *.md *.py *.js *.ts *.html *.css *.json *.csv *.sql *.log *.pdf *.png *.jpg *.jpeg);;"
            "Documentos PDF (*.pdf);;"
            "Imágenes con Texto / Capturas (*.png *.jpg *.jpeg *.bmp *.webp);;"
            "Código Fuente (*.py *.js *.ts *.html *.css *.sql);;"
            "Texto y Datos (*.txt *.md *.json *.csv *.log);;"
            "Todos los archivos (*.*)"
        )
        if not file_path:
            return

        try:
            filename = os.path.basename(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            size_bytes = os.path.getsize(file_path)
            raw_text = ""
            page_count = 1
            ocr_used = False

            if ext == ".pdf":
                try:
                    import fitz  # PyMuPDF ultra-rápido
                    doc = fitz.open(file_path)
                    page_count = len(doc)
                    pages_text = [p.get_text() for p in doc]
                    raw_text = "\n".join(pages_text).strip()

                    # Fallback Inteligente OCR: Si el PDF es escaneado o basado en imagen (ej: capturas o correos impresos)
                    if not raw_text:
                        try:
                            import winocr
                            from PIL import Image
                            import io
                            ocr_pages = []
                            for p in doc:
                                pix = p.get_pixmap(dpi=150)
                                img = Image.open(io.BytesIO(pix.tobytes("png")))
                                res = winocr.recognize_pil_sync(img, "es")
                                if res and res.get("text"):
                                    ocr_pages.append(res["text"])
                            raw_text = "\n\n".join(ocr_pages).strip()
                            if raw_text:
                                ocr_used = True
                        except Exception as ocr_err:
                            logger.warning(f"Fallo OCR en PDF escaneado: {ocr_err}")

                    doc.close()
                except Exception as pdf_err:
                    QMessageBox.warning(self, "Error al Leer PDF", f"No se pudo extraer texto del PDF:\n{pdf_err}")
                    return
            elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
                try:
                    import winocr
                    from PIL import Image
                    img = Image.open(file_path)
                    res = winocr.recognize_pil_sync(img, "es")
                    if res and res.get("text"):
                        raw_text = res["text"].strip()
                        ocr_used = True
                except Exception as img_err:
                    QMessageBox.warning(self, "Error al Leer Imagen", f"No se pudo procesar la imagen:\n{img_err}")
                    return
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    raw_text = f.read().strip()

            if not raw_text:
                QMessageBox.warning(self, "Archivo Vacío", f"El archivo '{filename}' no contiene texto legible.")
                return

            char_count = len(raw_text)
            size_kb = size_bytes / 1024.0

            # Umbral híbrido automático: > 15.000 caracteres o > 8 páginas de PDF
            is_large = (char_count > 15000 or page_count > 8)
            default_mode = "summary" if is_large else "direct"

            self.attached_file_data = {
                "path": file_path,
                "filename": filename,
                "extension": ext,
                "size_bytes": size_bytes,
                "size_kb": size_kb,
                "char_count": char_count,
                "page_count": page_count,
                "raw_text": raw_text,
                "mode": default_mode,
                "ocr_used": ocr_used,
                "summary": "",
                "slice_info": "Primeros 12.000 caracteres" if is_large else ""
            }
            self._update_attached_file_ui()
            self.log_activity("Mesa Redonda", "Archivo Adjunto", f"{filename} ({size_kb:.1f} KB, modo: {default_mode}, ocr: {ocr_used})")
        except Exception as e:
            QMessageBox.critical(self, "Error al Cargar Archivo", f"Error inesperado al abrir el archivo:\n{e}")

    def _remove_attached_file(self):
        """Elimina el archivo adjunto actual."""
        self.attached_file_data = None
        if hasattr(self, "attached_file_frame"):
            self.attached_file_frame.setVisible(False)
        self.log_activity("Mesa Redonda", "Archivo Removido", "Sin archivo adjunto")

    def _update_attached_file_ui(self):
        """Actualiza la barra visual del archivo adjunto y el selector de modo híbrido."""
        if not getattr(self, "attached_file_data", None):
            if hasattr(self, "attached_file_frame"):
                self.attached_file_frame.setVisible(False)
            return

        f = self.attached_file_data
        fname = f["filename"]
        fsize = f["size_kb"]
        mode = f.get("mode", "direct")
        pages = f.get("page_count", 1)

        extra = f" • {pages} págs" if f["extension"] == ".pdf" else f" • {f['char_count']} caracteres"
        if f.get("ocr_used"):
            extra += " • 🔍 OCR"
        if hasattr(self, "lbl_attached_file_info"):
            self.lbl_attached_file_info.setText(f"📁 <b>{fname}</b> <span style='color: #8C99B2;'>({fsize:.1f} KB{extra})</span>")

        if hasattr(self, "btn_attached_file_mode"):
            if mode == "direct":
                self.btn_attached_file_mode.setText("⚡ Directo 100% ▾")
                self.btn_attached_file_mode.setStyleSheet("""
                    QPushButton {
                        background-color: #112638;
                        color: #00E5FF;
                        border: 1px solid #1E4E79;
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #1A3E5D; border-color: #00E5FF; }
                """)
            elif mode == "summary":
                self.btn_attached_file_mode.setText("🧠 Resumen Ejecutivo ▾")
                self.btn_attached_file_mode.setStyleSheet("""
                    QPushButton {
                        background-color: #261F0E;
                        color: #FFB703;
                        border: 1px solid #6E5316;
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #3D3012; border-color: #FFB703; }
                """)
            else:  # slice
                self.btn_attached_file_mode.setText("📑 Primeras Págs ▾")
                self.btn_attached_file_mode.setStyleSheet("""
                    QPushButton {
                        background-color: #1E1229;
                        color: #D18BFD;
                        border: 1px solid #4D2168;
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #311B45; border-color: #D18BFD; }
                """)

        if hasattr(self, "attached_file_frame"):
            self.attached_file_frame.setVisible(True)

    def _show_file_mode_menu(self):
        """Muestra el menú emergente para seleccionar el modo de análisis del archivo adjunto."""
        if not getattr(self, "attached_file_data", None) or not hasattr(self, "btn_attached_file_mode"):
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0E1522;
                color: #ECEFF4;
                border: 1px solid #1E3A5F;
                border-radius: 6px;
                padding: 4px;
                font-size: 11px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1A283D;
                color: #00E5FF;
            }
        """)

        current_mode = self.attached_file_data.get("mode", "direct")
        modes = [
            ("⚡ Modo Directo (100% de fidelidad palabra por palabra)", "direct"),
            ("🧠 Resumen Ejecutivo Previo (Extracción rápida sin saturar memoria)", "summary"),
            ("📑 Primeras Páginas / Extracto Seguro", "slice")
        ]

        for label, m_key in modes:
            prefix = "✓ " if m_key == current_mode else "   "
            action = menu.addAction(f"{prefix}{label}")
            def make_handler(mode_val=m_key):
                def handler():
                    self.attached_file_data["mode"] = mode_val
                    self._update_attached_file_ui()
                return handler
            action.triggered.connect(make_handler(m_key))

        btn = self.btn_attached_file_mode
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height() + 2)))

    def _export_council_to_pdf(self):
        """Exporta la deliberación completa de la Mesa Redonda a un PDF Ejecutivo de Élite (Estilo Consultoría / Inteligencia Estratégica)."""
        if not getattr(self, "_debate_turns_history", []):
            QMessageBox.warning(self, "Sin Contenido", "No hay ningún debate activo o completado para exportar a PDF.")
            return

        topic = getattr(self, "_debate_topic", "").strip() or "Consulta sin título"
        user_name = self.memory.get_user_name()
        grammar = self.memory.get_grammar_pronouns()
        salutation = self.memory.get_salutation()

        mode_id = getattr(self, "current_council_mode", "clasico")
        mode_info = DEBATE_MODES.get(mode_id, DEBATE_MODES["clasico"])
        mode_name = mode_info.get("name", "Modo Dialéctico Clásico")
        mode_desc = mode_info.get("description", "")

        clean_name = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ_-]', '_', topic[:32]).strip('_')
        date_stamp = datetime.now().strftime("%Y%m%d_%H%M")
        session_hash = hashlib.md5(f"{topic}_{date_stamp}".encode('utf-8')).hexdigest()[:6].upper()
        doc_id = f"F3NX-{date_stamp[:8]}-{session_hash}"
        default_filename = f"Informe_F3NIX_{clean_name}_{date_stamp}.pdf"

        docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
        if not os.path.exists(docs_dir):
            docs_dir = os.path.expanduser("~")
        suggested_path = os.path.join(docs_dir, default_filename)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Informe Ejecutivo de Mesa Redonda en PDF",
            suggested_path,
            "Archivos PDF (*.pdf)"
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        try:
            date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            role_1_label = mode_info.get("role_1_label", "🔵 Rol 1")
            role_2_label = mode_info.get("role_2_label", "🔴 Rol 2")
            role_dir_label = mode_info.get("role_director_label", "🟢 Director F3NIX")

            m1 = self.combo_estratega.currentText() or "Modelo 1"
            m2 = self.combo_critico.currentText() or "Modelo 2"
            m_dir = self.combo_director.currentText() or "Director"
            rounds_count = self.combo_council_rounds.currentData() or 2

            pdf_role_styles = {
                "estratega": {
                    "title": "🔵 Estratega Creativo & Propositivo",
                    "bg": "#F0F7FF",
                    "border": "#BBDEFB",
                    "accent": "#0288D1",
                    "badge_bg": "#E1F5FE",
                    "title_color": "#01579B"
                },
                "critico": {
                    "title": "🔴 Analista Crítico & Auditor de Riesgos",
                    "bg": "#FFF5F5",
                    "border": "#FFCDD2",
                    "accent": "#E53935",
                    "badge_bg": "#FFEBEE",
                    "title_color": "#B71C1C"
                },
                "cisne_negro": {
                    "title": "🦅 Auditor Cisne Negro (Chaos & Stress-Test de Taleb)",
                    "bg": "#FAF5FF",
                    "border": "#E9D5FF",
                    "accent": "#9333EA",
                    "badge_bg": "#F3E8FF",
                    "title_color": "#6B21A8"
                },
                "sendero_a": {
                    "title": "🅰️ Simulador Sendero A (Horizonte 3-6 Meses)",
                    "bg": "#F0F9FF",
                    "border": "#BAE6FD",
                    "accent": "#0284C7",
                    "badge_bg": "#E0F2FE",
                    "title_color": "#0369A1"
                },
                "sendero_b": {
                    "title": "🅱️ Simulador Sendero B (Horizonte 3-6 Meses)",
                    "bg": "#FFFBEB",
                    "border": "#FDE68A",
                    "accent": "#D97706",
                    "badge_bg": "#FEF3C7",
                    "title_color": "#B45309"
                },
                "fisiologo": {
                    "title": "🔵 Fisiólogo & Coach de Alto Rendimiento",
                    "bg": "#F0FDFA",
                    "border": "#99F6E4",
                    "accent": "#0D9488",
                    "badge_bg": "#CCFBF1",
                    "title_color": "#0F766E"
                },
                "traumatologo": {
                    "title": "🔴 Traumatólogo & Especialista en Longevidad",
                    "bg": "#FFF1F2",
                    "border": "#FECDD3",
                    "accent": "#E11D48",
                    "badge_bg": "#FFE4E6",
                    "title_color": "#BE123C"
                },
                "arquitecto": {
                    "title": "🔵 Arquitecto Clean Code & Escalabilidad",
                    "bg": "#EFF6FF",
                    "border": "#BFDBFE",
                    "accent": "#2563EB",
                    "badge_bg": "#DBEAFE",
                    "title_color": "#1D4ED8"
                },
                "seguridad_qa": {
                    "title": "🔴 Hacker de Seguridad & Auditor QA",
                    "bg": "#FDF2F8",
                    "border": "#FBCFE8",
                    "accent": "#DB2777",
                    "badge_bg": "#FCE7F3",
                    "title_color": "#BE185D"
                },
                "estoico": {
                    "title": "🔵 Filósofo Estoico (Marco Aurelio & Séneca)",
                    "bg": "#F5F3FF",
                    "border": "#DDD6FE",
                    "accent": "#7C3AED",
                    "badge_bg": "#EDE9FE",
                    "title_color": "#5B21B6"
                },
                "pragmatico": {
                    "title": "🔴 Pragmático Realista & Evaluador de Costos",
                    "bg": "#FFF7ED",
                    "border": "#FFEDD5",
                    "accent": "#EA580C",
                    "badge_bg": "#FFEDD5",
                    "title_color": "#C2410C"
                },
                "defensor": {
                    "title": "🔵 Abogado Defensor (Defensa de la Tesis)",
                    "bg": "#F0F9FF",
                    "border": "#BAE6FD",
                    "accent": "#0284C7",
                    "badge_bg": "#E0F2FE",
                    "title_color": "#0369A1"
                },
                "fiscal": {
                    "title": "🔴 Fiscal Acusador (Impugnación & Contrainterrogatorio)",
                    "bg": "#FEF2F2",
                    "border": "#FECACA",
                    "accent": "#DC2626",
                    "badge_bg": "#FEE2E2",
                    "title_color": "#B91C1C"
                },
                "evaluador_a": {
                    "title": "🔵 Evaluador Independiente Alpha",
                    "bg": "#ECFEFF",
                    "border": "#A5F3FC",
                    "accent": "#0891B2",
                    "badge_bg": "#CFFAFE",
                    "title_color": "#0E7490"
                },
                "evaluador_b": {
                    "title": "🟣 Evaluador Independiente Beta",
                    "bg": "#FAF5FF",
                    "border": "#E9D5FF",
                    "accent": "#9333EA",
                    "badge_bg": "#F3E8FF",
                    "title_color": "#7E22CE"
                },
                "socratico": {
                    "title": "🔍 Auditor Socrático (Interrogatorio Incisivo)",
                    "bg": "#EEF2FF",
                    "border": "#C7D2FE",
                    "accent": "#4F46E5",
                    "badge_bg": "#E0E7FF",
                    "title_color": "#3730A3"
                },
                "proponente": {
                    "title": "🔵 Proponente Inicial del Plan",
                    "bg": "#F0F7FF",
                    "border": "#BBDEFB",
                    "accent": "#0288D1",
                    "badge_bg": "#E1F5FE",
                    "title_color": "#01579B"
                },
                "steelman": {
                    "title": "🛡️ Auditor Steel-Man (Versión Invulnerable)",
                    "bg": "#F7FEE7",
                    "border": "#D9F99D",
                    "accent": "#65A30D",
                    "badge_bg": "#ECFCCB",
                    "title_color": "#4D7C0F"
                },
                "extractor": {
                    "title": "📄 Extracción y Síntesis Previa de Documento",
                    "bg": "#F8FAFC",
                    "border": "#CBD5E1",
                    "accent": "#475569",
                    "badge_bg": "#F1F5F9",
                    "title_color": "#334155"
                }
            }

            # Extracción del Veredicto y Síntesis para el Resumen Ejecutivo
            final_synthesis = ""
            for t in reversed(self._debate_turns_history):
                if t.get("role") == "director":
                    final_synthesis = t.get("reply", "")
                    break

            summary_bullets = []
            if final_synthesis:
                for line in final_synthesis.split("\n"):
                    l_strip = line.strip()
                    m = re.match(r'^(?:\d+[\.\)]|[-*•])\s*(.+)$', l_strip)
                    if m:
                        clean_line = re.sub(r'(\*\*|__)', '', m.group(1)).strip()
                        if len(clean_line) > 22 and not clean_line.lower().startswith("paso") and not clean_line.lower().startswith("fase"):
                            summary_bullets.append(clean_line)
                            if len(summary_bullets) >= 3:
                                break

            if not summary_bullets:
                summary_bullets = [
                    f"Deliberación dialéctica completada bajo el {mode_name}.",
                    "Identificación rigurosa de puntos ciegos, sobrecargas y salvaguardas operativas.",
                    "Consolidación del Plan Maestro ejecutable gobernado por la Constitución Mental F3NIX."
                ]

            # Extracción de Items para la Lista de Verificación / Checklist
            checklist_items = []
            if final_synthesis:
                for line in final_synthesis.split("\n"):
                    l_strip = line.strip()
                    m = re.match(r'^(?:(?:\d+[\.\)]|[-*•])\s*)?(?:[•\-\*]\s*)?(.+)$', l_strip)
                    if m:
                        text_item = re.sub(r'(\*\*|__)', '', m.group(1)).strip()
                        if 18 < len(text_item) < 140 and any(kw in text_item.lower() for kw in ["definir", "ejecutar", "revisar", "ajustar", "iniciar", "establecer", "crear", "preparar", "medir", "aplicar", "bloque", "paso", "fase"]):
                            checklist_items.append(text_item)
                            if len(checklist_items) >= 4:
                                break

            if not checklist_items:
                checklist_items = [
                    "Revisar el dictamen del Plan Maestro y confirmar la viabilidad táctica de inicio.",
                    "Implementar de inmediato las salvaguardas preventivas señaladas en la auditoría.",
                    "Poner en marcha la Fase 1 en las próximas 24 a 48 horas con métricas claras.",
                    "Registrar aprendizajes y retroalimentar a la Bóveda de Memoria Permanente de F3NIX."
                ]

            # Renderizado de Turnos del Debate
            turns_html = []
            total_turns = len(self._debate_turns_history)

            for i, turn in enumerate(self._debate_turns_history):
                role = turn.get("role", "")
                model = turn.get("model", "")
                reply = turn.get("reply", "")
                round_num = turn.get("round", 1)
                phase = turn.get("phase", "")
                is_final_result = (role == "director" and (i == total_turns - 1 or "Plan Maestro" in phase or "Síntesis" in phase or "Veredicto" in phase))

                clean_body = self._format_markdown_to_html(reply)

                if role == "fenix":
                    turns_html.append(f"""
                    <div style="margin-bottom: 14px; padding: 12px 16px; background-color: #FFFDE7; border: 1.5px solid #FDE68A; border-left: 6px solid #D97706; border-radius: 6px;">
                        <table style="width: 100%; border-collapse: collapse; margin-bottom: 5px;">
                            <tr>
                                <td style="color: #B45309; font-weight: bold; font-size: 10.5pt;">
                                    👑 ORDEN DIRECTA DE {user_name.upper()} ({grammar.get('president', 'Presidente/a')} de Mesa)
                                </td>
                                <td style="text-align: right;">
                                    <span style="background-color: #FEF3C7; color: #B45309; font-size: 8pt; font-weight: bold; padding: 2px 8px; border-radius: 4px; border: 1px solid #FDE68A;">
                                        Intervención Presidencial
                                    </span>
                                </td>
                            </tr>
                        </table>
                        <div style="font-size: 9.5pt; color: #451A03; line-height: 1.5; font-style: italic;">
                            «{clean_body}»
                        </div>
                    </div>
                    """)
                elif is_final_result:
                    turns_html.append(f"""
                    <div style="margin-top: 18px; margin-bottom: 16px; padding: 16px 18px; background-color: #ECFDF5; border: 2px solid #059669; border-left: 8px solid #047857; border-radius: 8px;">
                        <table style="width: 100%; border-collapse: collapse; margin-bottom: 10px;">
                            <tr>
                                <td style="background-color: #047857; color: #FFFFFF; padding: 7px 14px; border-radius: 4px; font-weight: bold; font-size: 11.5pt;">
                                    🏆 DICTAMEN DEFINITIVO &bull; PLAN MAESTRO CONSENSUADO
                                </td>
                                <td style="text-align: right; background-color: #047857; color: #A7F3D0; padding: 7px 14px; border-radius: 4px; font-size: 8.5pt;">
                                    Cerebro Moderador: <b>{model}</b>
                                </td>
                            </tr>
                        </table>
                        <div style="font-size: 9.5pt; color: #065F46; font-weight: bold; margin-bottom: 8px;">
                            🟢 Síntesis Ejecutiva bajo la Constitución Mental F3NIX v1.0 &bull; {phase}
                        </div>
                        <div style="font-size: 10pt; color: #064E3B; line-height: 1.6;">
                            {clean_body}
                        </div>
                    </div>
                    """)
                else:
                    st = pdf_role_styles.get(role, {
                        "title": turn.get("title") or role.capitalize(),
                        "bg": "#F8FAFC",
                        "border": "#E2E8F0",
                        "accent": "#475569",
                        "badge_bg": "#F1F5F9",
                        "title_color": "#1E293B"
                    })
                    round_txt = f"Ronda {round_num}" if round_num > 0 else "Turno de Análisis"
                    phase_txt = f" &bull; {phase}" if phase else ""
                    turns_html.append(f"""
                    <div style="margin-bottom: 14px; padding: 12px 16px; background-color: {st['bg']}; border: 1.5px solid {st['border']}; border-left: 6px solid {st['accent']}; border-radius: 6px;">
                        <table style="width: 100%; border-collapse: collapse; margin-bottom: 6px;">
                            <tr>
                                <td>
                                    <span style="color: {st['title_color']}; font-weight: bold; font-size: 10.5pt;">
                                        {st['title']}
                                    </span>
                                    <span style="color: #64748B; font-size: 8.5pt;">({round_txt}{phase_txt})</span>
                                </td>
                                <td style="text-align: right;">
                                    <span style="background-color: {st['badge_bg']}; color: {st['title_color']}; font-size: 8pt; font-weight: bold; padding: 3px 8px; border-radius: 4px; border: 1px solid {st['border']};">
                                        Cerebro: {model}
                                    </span>
                                </td>
                            </tr>
                        </table>
                        <div style="font-size: 9.5pt; color: #1E293B; line-height: 1.55;">
                            {clean_body}
                        </div>
                    </div>
                    """)

            topic_formatted = self._format_markdown_to_html(topic)

            # Generar Tablero Ejecutivo y Gráfica Visual con F3nixChartEngine
            dashboard_html = ""
            try:
                from core.f3nix_chart_engine import F3nixChartEngine
                visual_data = F3nixChartEngine.analyze_and_generate_visuals(
                    topic=topic,
                    debate_turns=self._debate_turns_history,
                    final_synthesis=final_synthesis
                )

                kpis = visual_data.get("kpis", [])
                kpi_cards_tds = []
                if kpis:
                    td_width = f"{100 // len(kpis)}%"
                    for k in kpis:
                        kpi_cards_tds.append(f"""
                        <td style="background-color: #FFFFFF; border: 1px solid #E2E8F0; padding: 10px 8px; text-align: center; border-radius: 6px;" width="{td_width}">
                            <div style="font-size: 15pt; font-weight: 800; color: {k.get('color', '#0284C7')}; margin-bottom: 2px;">
                                {k.get('val', '')}
                            </div>
                            <div style="font-size: 7.5pt; color: #64748B; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">
                                {k.get('lbl', '')}
                            </div>
                        </td>
                        """)
                    kpis_row = f"""
                    <table style="width: 100%; border-collapse: separate; border-spacing: 6px; margin-bottom: 12px;">
                        <tr>
                            {"".join(kpi_cards_tds)}
                        </tr>
                    </table>
                    """
                else:
                    kpis_row = ""

                chart_block = ""
                if visual_data.get("has_chart") and visual_data.get("chart_base64"):
                    b64_img = visual_data["chart_base64"]
                    chart_block = f"""
                    <div style="text-align: center; margin-bottom: 8px; background-color: #FFFFFF; border: 1px solid #E2E8F0; padding: 10px; border-radius: 6px;">
                        <img src="data:image/png;base64,{b64_img}" width="650" />
                    </div>
                    """

                if kpis_row or chart_block:
                    dashboard_html = f"""
                    <div style="margin-bottom: 16px; padding: 14px 16px; background-color: #F8FAFC; border: 1.5px solid #CBD5E1; border-left: 6px solid #16A34A; border-radius: 8px;">
                        <div style="color: #15803D; font-weight: bold; font-size: 9.5pt; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">
                            📊 TABLERO EJECUTIVO &bull; MATRIZ VISUAL DE IMPACTO
                        </div>
                        {kpis_row}
                        {chart_block}
                    </div>
                    """
            except Exception as chart_err:
                logger.warning(f"No se pudieron generar visuales para el PDF: {chart_err}")
                dashboard_html = ""

            file_meta_row = ""
            if getattr(self, "_debate_attached_file", None):
                f_info = self._debate_attached_file
                fname = f_info.get("filename", "archivo")
                fsize = f_info.get("size_kb", 0)
                fmode = f_info.get("mode", "direct")
                fpages = f_info.get("page_count", 1)
                fchars = f_info.get("char_count", 0)
                mode_lbl = "Modo Directo (100% Fidelidad)" if fmode == "direct" else ("Modo Resumen Ejecutivo" if fmode == "summary" else "Extracto de Páginas")
                badge_p = f" &bull; {fpages} pág(s)" if f_info.get("extension") == ".pdf" else f" &bull; {fchars} caracteres"
                file_meta_row = f"""
                <div style="margin-bottom: 12px; padding: 8px 12px; background-color: #F1F5F9; border: 1px solid #CBD5E1; border-left: 4px solid #64748B; border-radius: 4px; font-size: 8.5pt; color: #334155;">
                    <b>📁 Documento Adjunto Analizado:</b> {fname} ({fsize:.1f} KB{badge_p}) &nbsp;|&nbsp; <b>Modo de Procesamiento:</b> {mode_lbl}
                </div>
                """

            # Resumen Ejecutivo (TL;DR)
            sum_rows = []
            for b in summary_bullets:
                sum_rows.append(f"""
                <div style="margin-bottom: 5px; font-size: 9.5pt; color: #0F172A; line-height: 1.45;">
                    <b style="color: #0284C7;">&bull;</b> {b}
                </div>
                """)

            summary_box_html = f"""
            <div style="margin-bottom: 16px; padding: 12px 16px; background-color: #F0F9FF; border: 1.5px solid #BAE6FD; border-left: 6px solid #0284C7; border-radius: 6px;">
                <div style="font-size: 9.5pt; font-weight: bold; color: #0369A1; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px;">
                    📌 RESUMEN EJECUTIVO &bull; DICTAMEN RÁPIDO (TL;DR)
                </div>
                {"".join(sum_rows)}
            </div>
            """

            # Checklist Imprimible
            chk_rows = []
            for chk in checklist_items:
                chk_rows.append(f"""
                <tr>
                    <td style="width: 28px; vertical-align: top; padding: 4px 0;">
                        <div style="width: 13px; height: 13px; border: 2px solid #059669; border-radius: 3px; background-color: #FFFFFF;"></div>
                    </td>
                    <td style="padding: 3px 0; font-size: 9.5pt; color: #1E293B; line-height: 1.4;">
                        {chk}
                    </td>
                </tr>
                """)

            checklist_html = f"""
            <div style="margin-top: 16px; margin-bottom: 16px; padding: 12px 16px; background-color: #F8FAFC; border: 1.5px solid #CBD5E1; border-left: 6px solid #0284C7; border-radius: 6px;">
                <div style="font-size: 9.5pt; font-weight: bold; color: #0369A1; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">
                    📋 LISTA DE VERIFICACIÓN EJECUTIVA PARA ACCIÓN INMEDIATA
                </div>
                <table style="width: 100%; border-collapse: collapse;">
                    {"".join(chk_rows)}
                </table>
            </div>
            """

            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Segoe UI', -apple-system, Arial, sans-serif;
                    color: #1E293B;
                    font-size: 9.5pt;
                    line-height: 1.5;
                }}
            </style>
            </head>
            <body>
                <!-- Header Banner -->
                <table style="width: 100%; border-collapse: collapse; background-color: #0B132B; border-bottom: 4px solid #00E5FF; border-radius: 6px; margin-bottom: 12px;">
                    <tr>
                        <td style="padding: 16px 20px; vertical-align: middle;">
                            <div style="font-size: 7.5pt; font-weight: bold; color: #00E5FF; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 3px;">
                                SISTEMA AUTÓNOMO DE INTELIGENCIA ESTRATÉGICA F3NIX
                            </div>
                            <div style="font-size: 16pt; font-weight: 800; color: #FFFFFF; letter-spacing: 0.5px; margin-bottom: 3px;">
                                🏛️ INFORME OFICIAL DE MESA REDONDA
                            </div>
                            <div style="font-size: 9pt; color: #94A3B8;">
                                Deliberación Dialéctica Multi-Agente &bull; Evaluación de Riesgos &bull; Plan Maestro
                            </div>
                        </td>
                        <td style="padding: 16px 20px; text-align: right; vertical-align: middle; width: 170px;">
                            <div style="background-color: #1C2541; border: 1px solid #334155; border-radius: 6px; padding: 6px 10px; text-align: right;">
                                <div style="font-size: 7pt; color: #94A3B8; text-transform: uppercase; font-weight: bold;">CÓDIGO DE SESIÓN</div>
                                <div style="font-size: 10pt; font-weight: bold; color: #00E5FF; font-family: monospace;">{doc_id}</div>
                                <div style="font-size: 6.5pt; color: #64748B;">CLASIFICACIÓN: PRIVADO</div>
                            </div>
                        </td>
                    </tr>
                </table>

                <!-- Metadata Cards Grid -->
                <table style="width: 100%; border-collapse: separate; border-spacing: 6px; margin-bottom: 10px;">
                    <tr>
                        <td style="width: 50%; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; vertical-align: top;">
                            <div style="font-size: 7.5pt; font-weight: bold; color: #64748B; text-transform: uppercase;">👤 COMANDANTE / SOLICITANTE</div>
                            <div style="font-size: 10.5pt; font-weight: bold; color: #0F172A; margin-top: 2px;">{user_name} ({salutation})</div>
                        </td>
                        <td style="width: 50%; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; vertical-align: top;">
                            <div style="font-size: 7.5pt; font-weight: bold; color: #64748B; text-transform: uppercase;">📅 REGISTRO & CERTIFICACIÓN</div>
                            <div style="font-size: 10pt; font-weight: bold; color: #0F172A; margin-top: 2px;">{date_str}</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="width: 50%; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; vertical-align: top;">
                            <div style="font-size: 7.5pt; font-weight: bold; color: #0284C7; text-transform: uppercase;">🧠 MODO DE PENSAMIENTO DIALÉCTICO</div>
                            <div style="font-size: 10pt; font-weight: bold; color: #0369A1; margin-top: 2px;">{mode_info['name']}</div>
                            <div style="font-size: 8pt; color: #64748B; margin-top: 2px;">{mode_desc}</div>
                        </td>
                        <td style="width: 50%; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; vertical-align: top;">
                            <div style="font-size: 7.5pt; font-weight: bold; color: #64748B; text-transform: uppercase;">🤖 CONSEJO DE MODELOS ({rounds_count} RONDAS)</div>
                            <div style="font-size: 8.5pt; color: #1E293B; margin-top: 2px;">
                                &bull; {role_1_label}: <b>{m1}</b><br>
                                &bull; {role_2_label}: <b>{m2}</b><br>
                                &bull; {role_dir_label}: <b>{m_dir}</b>
                            </div>
                        </td>
                    </tr>
                </table>

                {file_meta_row}

                <!-- Topic Box -->
                <div style="margin-bottom: 14px; padding: 10px 14px; background-color: #F1F5F9; border: 1px solid #CBD5E1; border-left: 5px solid #00E5FF; border-radius: 6px;">
                    <div style="font-size: 7.5pt; font-weight: bold; color: #0891B2; text-transform: uppercase; margin-bottom: 3px;">
                        🎯 CONSULTA / DESAFÍO ESTRATÉGICO:
                    </div>
                    <div style="font-size: 10.5pt; font-weight: bold; color: #0F172A; line-height: 1.4;">
                        {topic_formatted}
                    </div>
                </div>

                <!-- Executive Brief (TL;DR) -->
                {summary_box_html}

                <!-- Tablero Visual y KPIs -->
                {dashboard_html}

                <!-- Deliberation History -->
                <div style="margin-top: 14px; margin-bottom: 10px; font-size: 10.5pt; font-weight: bold; color: #334155; border-bottom: 1.5px solid #E2E8F0; padding-bottom: 4px;">
                    📜 DELIBERACIÓN DIALÉCTICA SECUENCIAL
                </div>

                {"".join(turns_html)}

                <!-- Actionable Checklist -->
                {checklist_html}

                <!-- Footer -->
                <div style="margin-top: 20px; border-top: 1px solid #CBD5E1; padding-top: 8px; text-align: center; font-size: 7.5pt; color: #94A3B8;">
                    Documento de Inteligencia Estratégica F3NIX &bull; Sistema Autónomo Multi-Agente &bull; Clasificación: Privado / Uso Personal &bull; Autenticidad Verificada: {doc_id}
                </div>
            </body>
            </html>
            """

            writer = QPdfWriter(file_path)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            layout = QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                QMarginsF(12, 12, 12, 12),
                QPageLayout.Unit.Millimeter
            )
            writer.setPageLayout(layout)

            doc = QTextDocument()
            doc.setHtml(full_html)
            doc.print(writer)

            self.log_activity("Mesa Redonda", "Debate Exportado a PDF Ejecutivo", file_path)

            reply = QMessageBox.information(
                self,
                "PDF Exportado Exitosamente",
                f"El informe ejecutivo del debate ha sido exportado exitosamente:\n\n{file_path}\n\n¿Deseas abrir el archivo PDF ahora?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    os.startfile(file_path)
                except Exception as open_err:
                    logger.warning(f"No se pudo abrir automáticamente el PDF: {open_err}")

        except Exception as e:
            logger.error(f"Error exportando debate a PDF: {e}")
            QMessageBox.critical(self, "Error de Exportación", f"Ocurrió un error al exportar el debate a PDF:\n{e}")

        except Exception as e:
            logger.error(f"Error exportando debate a PDF: {e}")
            QMessageBox.critical(self, "Error de Exportación", f"Ocurrió un error al exportar el debate a PDF:\n{e}")

    def _open_council_guide(self):
        """Abre la ventana interactiva que explica qué IA es mejor para cada rol y por qué."""
        dialog = CouncilGuideDialog(parent=self)
        dialog.open_store_requested.connect(self.open_model_store_requested.emit)
        dialog.exec()

    def _open_constitution_dialog(self):
        """Abre el visor de los 10 módulos de la Constitución Mental F3NIX AI v1.0."""
        dialog = ConstitutionDialog(parent=self)
        dialog.exec()

    def _open_life_case_dialog(self):
        """Abre el registro interactivo de Casos Empíricos de Vida."""
        dialog = LifeCaseDialog(self.memory, parent=self)
        dialog.exec()
        self.refresh_memory_view()

    def _refresh_council_presets_bar(self):
        """Reconstruye la barra de plantillas y temas sugeridos, permitiendo personalización total."""
        if not hasattr(self, "presets_layout"):
            return

        while self.presets_layout.count():
            item = self.presets_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        preset_lbl = QLabel("💡 Temas & Plantillas:")
        preset_lbl.setStyleSheet("color: #8C99B2; font-size: 11px; font-weight: bold;")
        self.presets_layout.addWidget(preset_lbl)

        # Botón 1: Tema libre (En blanco)
        btn_blank = QPushButton("✏️ Tema Libre")
        btn_blank.setFixedHeight(26)
        btn_blank.setToolTip("Limpia el campo para que escribas libremente cualquier tema de debate")
        btn_blank.setStyleSheet("background-color: #1A2233; color: #ECEFF4; border: 1px solid #2B3852; font-size: 11px;")
        btn_blank.clicked.connect(self._set_blank_council_topic)
        self.presets_layout.addWidget(btn_blank)

        # Botón 2: Menú desplegable con plantillas por categorías
        btn_categories = QPushButton("📂 Plantillas por Categoría ▾")
        btn_categories.setFixedHeight(26)
        btn_categories.setStyleSheet("background-color: #122133; color: #8BE9FD; border: 1px solid #1E3A5F; font-size: 11px; font-weight: bold;")
        btn_categories.clicked.connect(self._show_council_templates_menu)
        self.presets_layout.addWidget(btn_categories)

        # Presets rápidos recomendados
        default_presets = [
            ("💪 Salud & Rutina", "Tengo 50 años y no puedo ir al gimnasio. ¿Qué rutina mensual sería la mejor para mí viviendo en la playa/costa aprovechando el terreno natural (arena, agua, médanos) y mi trayectoria en artes marciales? Sin aparatos, solo peso corporal, previniendo lesiones articulares y con una dieta natural de alimentos reales sin ultraprocesados."),
            ("💰 Negocio Rentable", "Quiero lanzar un nuevo proyecto o servicio digital rentable. ¿Cuál es la mejor propuesta de valor, cómo validar la demanda real y qué primeros pasos prácticos debo dar sin malgastar presupuesto?"),
            ("🧠 Decisión Compleja", "Tengo que tomar una decisión importante entre dos caminos alternativos:\n- Camino A: [Escribe aquí tu primera opción o propuesta]\n- Camino B: [Escribe aquí tu segunda opción o alternativa]\nContexto: [Describe brevemente tu situación actual y qué te preocupa]\nAnalicen a fondo los pros, contras, riesgos imprevistos a largo plazo y cuál es la mejor estrategia de resolución."),
            ("🚀 Lanzar Software / MVP", "Quiero desarrollar un producto de software (MVP) útil y escalable. ¿Cómo estructuro la validación, la arquitectura técnica y el lanzamiento para evitar construir algo que nadie use?")
        ]

        for p_title, p_topic in default_presets:
            p_btn = QPushButton(p_title)
            p_btn.setFixedHeight(26)
            p_btn.clicked.connect(lambda checked, t=p_topic: self._set_council_topic_preset(t))
            self.presets_layout.addWidget(p_btn)

        # Presets personalizados guardados por el usuario
        custom_presets = self.memory.get_custom_debate_presets()
        for cp in custom_presets:
            cp_title = cp.get("title", "Mi Tema")
            cp_topic = cp.get("topic", "")
            cp_btn = QPushButton(f"⭐ {cp_title}")
            cp_btn.setFixedHeight(26)
            cp_btn.setStyleSheet("background-color: #262011; color: #FFB703; border: 1px solid #634710; font-size: 11px;")
            cp_btn.setToolTip(f"Plantilla personalizada del usuario:\n«{cp_topic[:100]}...»\n(Clic derecho para eliminar)")
            cp_btn.clicked.connect(lambda checked, t=cp_topic: self._set_council_topic_preset(t))
            cp_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            cp_btn.customContextMenuRequested.connect(lambda pos, tit=cp_title: self._delete_custom_preset_prompt(tit))
            self.presets_layout.addWidget(cp_btn)

        # Botón para guardar el tema actual como plantilla personalizada
        btn_save_current = QPushButton("➕ Guardar Tema Actual...")
        btn_save_current.setFixedHeight(26)
        btn_save_current.setStyleSheet("background-color: #10261E; color: #00E676; border: 1px solid #194833; font-size: 11px;")
        btn_save_current.setToolTip("Guarda el texto que escribiste abajo como tu propio botón de plantilla permanente")
        btn_save_current.clicked.connect(self._save_current_topic_as_preset)
        self.presets_layout.addWidget(btn_save_current)

        self.presets_layout.addStretch()

    def _set_blank_council_topic(self):
        self.council_topic_input.clear()
        self.council_topic_input.setFocus()

    def _show_council_templates_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #121C2B;
                color: #ECEFF4;
                border: 1px solid #1E3A5F;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #00E5FF;
                color: #0B0F17;
                font-weight: bold;
            }
        """)

        templates = [
            ("🏋️ Salud & Entrenamiento Físico", "¿Cómo estructuro una rutina mensual de calistenia, fuerza y movilidad articular sin pesas ni gimnasio, cuidando tendones y articulaciones según mi edad y con nutrición de comida real?"),
            ("💼 Negocios & Modelo de Ingresos", "Tengo una idea de servicio o producto digital. Auditen el nicho de mercado, los costos operativos reales y los pasos prácticos para validar tracción sin invertir capital a ciegas."),
            ("🧠 Dilema Personal o Familiar", "Estoy frente a una situación personal/familiar compleja con dos caminos opuestos. Analicen objetivamente pros, contras, impactos emocionales a largo plazo y una estrategia madura de resolución."),
            ("💻 Arquitectura de Software & Backend", "¿Cuál es la mejor arquitectura y pila tecnológica para crear una aplicación rápida, escalable y mantenible minimizando la deuda técnica y complejidad innecesaria?"),
            ("⚖️ Análisis de Riesgos & Auditoría Crítica", "Tengo una propuesta o contrato para analizar. Auditen exhaustivamente todas las trampas, cláusulas desfavorables, puntos ciegos y qué condiciones mínimas debo exigir."),
            ("📚 Aprendizaje Acelerado & Maestría", "¿Cuál es el mejor método de estudio y práctica deliberada para dominar una habilidad compleja en 90 días con sesiones diarias de 1 hora?")
        ]

        for cat_title, cat_prompt in templates:
            act = menu.addAction(cat_title)
            act.triggered.connect(lambda checked, p=cat_prompt: self._set_council_topic_preset(p))

        sender_btn = self.sender()
        if sender_btn and isinstance(sender_btn, QWidget):
            menu.exec(sender_btn.mapToGlobal(QPoint(0, sender_btn.height())))
        else:
            menu.exec(self.cursor().pos())

    def _save_current_topic_as_preset(self):
        topic = self.council_topic_input.toPlainText().strip()
        if not topic:
            QMessageBox.warning(self, "Tema Vacío", "Escribe primero tu tema o consulta en el cuadro de texto inferior antes de guardarlo como plantilla.")
            return

        title, ok = QInputDialog.getText(
            self,
            "Guardar Plantilla de Debate",
            "Ingresa un nombre corto para tu plantilla (ej: Mi Rutina, Caso Legal, Inversiones):"
        )
        if ok and title.strip():
            self.memory.add_custom_debate_preset(title.strip(), topic)
            self._refresh_council_presets_bar()
            QMessageBox.information(self, "Plantilla Guardada", f"¡Plantilla «{title.strip()}» guardada con éxito! Aparecerá en tu barra de temas.")

    def _delete_custom_preset_prompt(self, title: str):
        reply = QMessageBox.question(
            self,
            "Eliminar Plantilla",
            f"¿Deseas eliminar la plantilla personalizada «{title}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.memory.delete_custom_debate_preset(title)
            self._refresh_council_presets_bar()

    def _update_user_identity_labels(self):
        """Actualiza todas las etiquetas de la UI para reflejar el nombre y género configurados."""
        user_name = self.memory.get_user_name()
        grammar = self.memory.get_grammar_pronouns()
        salutation = self.memory.get_salutation()

        if hasattr(self, "btn_intervene"):
            self.btn_intervene.setText(f"👑 Intervenir ({user_name})")
        if hasattr(self, "interv_lbl"):
            self.interv_lbl.setText(f"👑 <b>Orden de {user_name}:</b>")
        if hasattr(self, "intervention_input"):
            self.intervention_input.setPlaceholderText(f"Escribe tu orden para la Mesa ({user_name})...")

        if hasattr(self, "debate_browser") and not getattr(self, "_debate_turns_history", []):
            self._set_council_welcome_content()

        self._refresh_council_presets_bar()

    def _set_council_welcome_content(self):
        user_name = self.memory.get_user_name()
        grammar = self.memory.get_grammar_pronouns()
        mode_id = getattr(self, "current_council_mode", "clasico")
        mode_info = DEBATE_MODES.get(mode_id, DEBATE_MODES["clasico"])

        r1_lbl = mode_info.get("role_1_label", "🔵 Rol 1")
        r2_lbl = mode_info.get("role_2_label", "🔴 Rol 2")
        rd_lbl = mode_info.get("role_director_label", "🟢 Director F3NIX")

        html = f"""
        <div style="padding: 18px; text-align: center; color: #8C99B2;">
            <div style="font-size: 28px; margin-bottom: 8px;">{mode_info['icon']}</div>
            <div style="font-size: 15px; font-weight: bold; color: #00E5FF; margin-bottom: 6px;">Mesa Redonda Multi-IA — {mode_info['name']}</div>
            <div style="font-size: 12px; max-width: 620px; margin: 0 auto; line-height: 1.6;">
                {grammar['welcome'].capitalize()} a tu centro de deliberación inteligente, <b style="color: #FFF;">{user_name}</b>.<br>
                <i style="color: #FFB703;">{mode_info['description']}</i><br><br>
                <span style="color: #00E5FF;"><b>1. {r1_lbl}:</b> Análisis y desarrollo de la postura inicial.</span><br>
                <span style="color: #FF5252;"><b>2. {r2_lbl}:</b> Auditoría especializada, contra-análisis y stress-testing.</span><br>
                <span style="color: #00E676;"><b>3. {rd_lbl}:</b> Veredicto y síntesis bajo la Constitución Mental F3NIX.</span><br><br>
                Escribe libremente cualquier consulta abajo o presiona el botón del modo para alternar entre los 10 modos de pensamiento.<br><br>
                <span style="color: #8BE9FD; font-size: 11px;">💡 <i>Puedes alternar modos en cualquier momento desde el selector superior izquierdo.</i></span>
            </div>
        </div>
        """
        self.debate_browser.setHtml(html)

    def _toggle_intervention_bar(self):
        is_vis = not self.intervention_frame.isVisible()
        self.intervention_frame.setVisible(is_vis)
        if is_vis:
            self.intervention_input.setFocus()

    def _submit_user_intervention(self):
        text = self.intervention_input.text().strip()
        if not text:
            return

        if self.council_worker and self.council_worker.isRunning():
            self.council_worker.add_intervention(text)

        user_name = self.memory.get_user_name()
        grammar = self.memory.get_grammar_pronouns()
        salutation = self.memory.get_salutation()

        self._debate_turns_history.append({
            "role": "fenix",
            "model": salutation,
            "title": f"👑 {user_name} ({grammar['president']} de Mesa)",
            "round": 0,
            "phase": "Intervención Directa",
            "reply": text
        })
        self._render_council_display()
        self.log_activity("Mesa Redonda", f"Intervención de {user_name}", text[:50])

        self.intervention_input.clear()
        self.intervention_frame.setVisible(False)

    def _start_council_debate(self):
        topic = self.council_topic_input.toPlainText().strip()
        if not topic:
            QMessageBox.warning(self, "Atención", "Por favor ingresa un proyecto, tema o consulta para debatir.")
            return

        estratega_model = self.combo_estratega.currentText() or "llama3.1"
        critico_model = self.combo_critico.currentText() or "llama3.1"
        director_model = self.combo_director.currentText() or "llama3.1"

        mode = getattr(self, "current_council_mode", "clasico")
        mode_info = DEBATE_MODES.get(mode, DEBATE_MODES["clasico"])

        models_per_role = {
            "estratega": estratega_model,
            "critico": critico_model,
            "director": director_model,
            "role_1": estratega_model,
            "role_2": critico_model,
            mode_info["role_1"]: estratega_model,
            mode_info["role_2"]: critico_model,
            mode_info["role_director"]: director_model
        }

        rounds = self.combo_council_rounds.currentData() if hasattr(self, "combo_council_rounds") else 2
        if not rounds:
            rounds = 2

        self._debate_turns_history = []
        self._current_turn_data = None
        self._debate_topic = topic
        self._debate_completed_banner = False
        self._debate_interrupted_banner = False
        self._debate_error_banner = None
        self._council_auto_scroll = True
        self._council_saved_scroll_pos = 0
        if hasattr(self, "btn_council_scroll_bottom"):
            self.btn_council_scroll_bottom.setVisible(False)

        self.btn_start_debate.setEnabled(False)
        if hasattr(self, "btn_attach_file"):
            self.btn_attach_file.setEnabled(False)
        self.btn_intervene.setEnabled(True)
        self.btn_stop_debate.setEnabled(True)
        self.btn_save_council_memory.setEnabled(False)
        if hasattr(self, "btn_export_pdf"):
            self.btn_export_pdf.setEnabled(False)

        # Repliega automáticamente el panel detallado si estaba abierto para dar todo el espacio al debate
        if hasattr(self, "config_details_box") and not self.config_details_box.isHidden():
            self.config_details_box.setVisible(False)
            if hasattr(self, "btn_toggle_config"):
                self.btn_toggle_config.setText("⚙️ Ajustes ▾")

        self.council_status_badge.setText("🟡 Debate en Progreso...")
        self.council_status_badge.setStyleSheet("font-size: 11px; color: #FFB703; background: #231C0E; padding: 3px 10px; border-radius: 10px; border: 1px solid #6E5316;")

        self._debate_attached_file = self.attached_file_data.copy() if getattr(self, "attached_file_data", None) else None
        self._render_council_display()
        self.log_activity("Mesa Redonda", f"{mode_info['name']} ({rounds} rondas)", topic[:60])

        role_voices = self._get_council_role_voices(mode)
        self.council_worker = CouncilWorker(
            council=self.council,
            topic=topic,
            models_per_role=models_per_role,
            rounds=rounds,
            mode=mode,
            file_data=self._debate_attached_file,
            speaker=self.speaker,
            enable_tts=self.council_tts_enabled,
            role_voices=role_voices,
            parent=self
        )
        self.council_worker.turn_started.connect(self._on_council_turn_started)
        self.council_worker.token_received.connect(self._on_council_token_received)
        self.council_worker.turn_finished.connect(self._on_council_turn_finished)
        self.council_worker.debate_completed.connect(self._on_council_debate_completed)
        self.council_worker.debate_error.connect(self._on_council_debate_error)
        self.council_worker.start()

    def _stop_council_debate(self):
        if self.council_worker and self.council_worker.isRunning():
            self.council_worker.cancel()
            self.council_worker.terminate()
            self.council_worker = None
        if self.speaker:
            self.speaker.stop()

        self.btn_start_debate.setEnabled(True)
        if hasattr(self, "btn_attach_file"):
            self.btn_attach_file.setEnabled(True)
        self.btn_intervene.setEnabled(False)
        self.btn_stop_debate.setEnabled(False)
        if getattr(self, "_debate_turns_history", []):
            if hasattr(self, "btn_export_pdf"):
                self.btn_export_pdf.setEnabled(True)
        self.intervention_frame.setVisible(False)
        self._current_turn_data = None
        self._debate_interrupted_banner = True
        self.council_status_badge.setText("⚪ Detenido")
        self.council_status_badge.setStyleSheet("font-size: 11px; color: #8C99B2; background: #0E1521; padding: 3px 10px; border-radius: 10px; border: 1px solid #1E2738;")
        self._render_council_display()
        self.log_activity("Mesa Redonda", "Debate Interrumpido", "")

    def _on_council_turn_started(self, role: str, model: str, round_num: int = 1, phase_title: str = ""):
        role_info = ROLES_CONFIG.get(role, {}).get("title", role.capitalize())
        r_txt = f"Ronda {round_num}" if round_num > 0 else "Análisis"
        self.council_status_badge.setText(f"🟡 {role_info} ({r_txt})...")
        self._current_turn_data = {
            "role": role,
            "model": model,
            "round": round_num,
            "phase": phase_title,
            "content": ""
        }
        self._render_council_display()

    def _on_council_token_received(self, role: str, model: str, chunk: str):
        if self._current_turn_data and self._current_turn_data["role"] == role:
            self._current_turn_data["content"] += chunk
            self._render_council_display()

    def _on_council_turn_finished(self, role: str, model: str, reply: str, round_num: int = 1, phase_title: str = ""):
        role_title = ROLES_CONFIG.get(role, {}).get("title", role.capitalize())
        self._debate_turns_history.append({
            "role": role,
            "model": model,
            "title": role_title,
            "round": round_num,
            "phase": phase_title,
            "reply": reply
        })
        self._current_turn_data = None
        self._render_council_display()
        self.log_activity("Mesa Redonda", f"Turno: {role} ({phase_title})", f"Modelo {model}")

    def _on_council_debate_completed(self, results: dict):
        try:
            self.btn_start_debate.setEnabled(True)
            if hasattr(self, "btn_attach_file"):
                self.btn_attach_file.setEnabled(True)
            self.btn_intervene.setEnabled(False)
            self.btn_stop_debate.setEnabled(False)
            self.btn_save_council_memory.setEnabled(True)
            if hasattr(self, "btn_export_pdf"):
                self.btn_export_pdf.setEnabled(True)
            self.intervention_frame.setVisible(False)
            self._current_turn_data = None
            self._debate_completed_banner = True
            self.council_status_badge.setText("🟢 Debate Completado")
            self.council_status_badge.setStyleSheet("font-size: 11px; color: #00E676; background: #0F281B; padding: 3px 10px; border-radius: 10px; border: 1px solid #1E5C3C;")
            self._render_council_display()

            topic = results.get("topic", "")
            synthesis = results.get("final_synthesis", "")
            self.debate_concluded.emit(topic, synthesis)
            self.log_activity("Mesa Redonda", "Debate Concluido Exitosamente", f"Topic: {topic[:50]}")
        except Exception as e:
            logger.error(f"Error procesando conclusión de debate: {e}")

    def _on_council_debate_error(self, err: str):
        self.btn_start_debate.setEnabled(True)
        if hasattr(self, "btn_attach_file"):
            self.btn_attach_file.setEnabled(True)
        self.btn_intervene.setEnabled(False)
        self.btn_stop_debate.setEnabled(False)
        self.intervention_frame.setVisible(False)
        self._current_turn_data = None
        self._debate_error_banner = err
        self.council_status_badge.setText("🔴 Error")
        self.council_status_badge.setStyleSheet("font-size: 11px; color: #FF5252; background: #261216; padding: 3px 10px; border-radius: 10px; border: 1px solid #5C1E26;")
        self._render_council_display()
        self.log_activity("Mesa Redonda", "Error en Debate", err[:60])

    def _render_council_display(self):
        """Renderiza todo el flujo del debate en vivo con soporte para rondas dialécticas, streaming e intervenciones del usuario."""
        user_name = self.memory.get_user_name()
        grammar = self.memory.get_grammar_pronouns()

        configs = {}
        for r_k, r_v in ROLES_CONFIG.items():
            configs[r_k] = {
                "title": r_v.get("title", r_k.capitalize()),
                "bg": r_v.get("bg", "#141A26"),
                "border": r_v.get("border", "#232C3D"),
                "accent": r_v.get("accent", "#8C99B2"),
                "badge_bg": r_v.get("badge_bg", "#0E131F")
            }
        configs["fenix"] = {
            "title": f"👑 {user_name} ({grammar['president']} de Mesa)",
            "bg": "#211808",
            "border": "#634710",
            "accent": "#FFB703",
            "badge_bg": "#140F05"
        }

        html_parts = []
        if self._debate_topic:
            topic_clean = self._format_markdown_to_html(self._debate_topic)
            mode_id = getattr(self, "current_council_mode", "clasico")
            mode_info = DEBATE_MODES.get(mode_id, DEBATE_MODES["clasico"])
            html_parts.append(f"""
            <div style="margin-bottom: 8px; padding: 10px 14px; background: #131A26; border-left: 3px solid #00E5FF; border-radius: 6px;">
                <div style="font-size: 11px; color: #8C99B2; font-weight: bold; text-transform: uppercase;">Proyecto / Consulta de {user_name}:</div>
                <div style="font-size: 13px; color: #ECEFF4; margin-top: 4px; font-weight: 500;">{topic_clean}</div>
            </div>
            <div style="margin-bottom: 12px; padding: 6px 12px; background: #0E1624; border: 1px solid #1E3A5F; border-radius: 6px; font-size: 11px;">
                <span style="color: #00E5FF; font-weight: bold;">{mode_info['name']}</span>
                <span style="color: #8C99B2;"> &nbsp;|&nbsp; {mode_info['description']}</span>
            </div>
            """)

        if getattr(self, "_debate_attached_file", None):
            f_info = self._debate_attached_file
            fname = f_info.get("filename", "archivo")
            fsize = f_info.get("size_kb", 0)
            fmode = f_info.get("mode", "direct")
            fpages = f_info.get("page_count", 1)
            fchars = f_info.get("char_count", 0)
            mode_badge = "⚡ Modo Directo (100% Fidelidad)" if fmode == "direct" else ("🧠 Modo Resumen Ejecutivo" if fmode == "summary" else "📑 Extracto de Páginas")
            badge_pages = f" • {fpages} pág(s)" if f_info.get("extension") == ".pdf" else f" • {fchars} caracteres"
            html_parts.append(f"""
            <div style="margin-bottom: 12px; padding: 8px 12px; background: #0E1624; border: 1px solid #1E3A5F; border-left: 3px solid #8BE9FD; border-radius: 6px; font-size: 11px; color: #8BE9FD;">
                📁 <b>Documento Adjunto:</b> <span style="color: #FFF;">{fname}</span> ({fsize:.1f} KB{badge_pages}) &nbsp;|&nbsp; <span style="color: #FFB703;">{mode_badge}</span>
            </div>
            """)

        for idx, turn in enumerate(self._debate_turns_history):
            role = turn["role"]
            model = turn["model"]
            reply = turn["reply"]
            phase = turn.get("phase", "")
            cfg = configs.get(role, {
                "title": role.capitalize(),
                "bg": "#141A26",
                "border": "#232C3D",
                "accent": "#8C99B2",
                "badge_bg": "#0E131F"
            })
            clean_reply = self._format_markdown_to_html(reply)

            if role == "fenix":
                audio_btn = f'<a href="speak:{idx}" style="color: #FFB703; text-decoration: none; font-size: 11px; font-weight: bold; background: #261E0A; padding: 2px 8px; border: 1px solid #FFB703; border-radius: 4px;">🔊 Escuchar</a>'
                html_parts.append(f"""
                <div style="margin: 12px 0; background-color: {cfg['bg']}; border: 1px solid {cfg['border']}; border-left: 4px solid {cfg['accent']}; border-radius: 8px; padding: 12px 16px;">
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 6px;">
                        <tr>
                            <td align="left">
                                <span style="color: {cfg['accent']}; font-weight: bold; font-size: 12px;">{cfg['title']}</span>
                                &nbsp;
                                <span style="color: #FFE082; font-size: 10px; background: {cfg['badge_bg']}; padding: 2px 6px; border-radius: 4px; border: 1px solid {cfg['border']};">Orden Directa a la Mesa</span>
                            </td>
                            <td align="right">
                                {audio_btn}
                            </td>
                        </tr>
                    </table>
                    <div style="color: #FFF8E1; font-size: 12px; line-height: 1.6; font-style: italic;">
                        «{clean_reply}»
                    </div>
                </div>
                """)
                continue

            phase_badge = f'&nbsp;<span style="color: #8BE9FD; font-size: 10px; background: {cfg["badge_bg"]}; padding: 2px 6px; border-radius: 4px; border: 1px solid {cfg["border"]}; font-weight: bold;">{phase}</span>' if phase else ""
            audio_btn = f'<a href="speak:{idx}" style="color: #00E5FF; text-decoration: none; font-size: 11px; font-weight: bold; background: #0E1A29; padding: 2px 8px; border: 1px solid #00E5FF; border-radius: 4px;">🔊 Escuchar</a>'

            html_parts.append(f"""
            <div style="margin: 12px 0; background-color: {cfg['bg']}; border: 1px solid {cfg['border']}; border-left: 4px solid {cfg['accent']}; border-radius: 8px; padding: 12px 16px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 8px;">
                    <tr>
                        <td align="left">
                            <span style="color: {cfg['accent']}; font-weight: bold; font-size: 12px;">{cfg['title']}</span>
                            {phase_badge}
                            &nbsp;
                            <span style="color: #7F8C9F; font-size: 10px; background: {cfg['badge_bg']}; padding: 2px 6px; border-radius: 4px; border: 1px solid {cfg['border']};">Cerebro: {model}</span>
                        </td>
                        <td align="right">
                            {audio_btn}
                        </td>
                    </tr>
                </table>
                <div style="color: #ECEFF4; font-size: 12px; line-height: 1.6;">
                    {clean_reply}
                </div>
            </div>
            """)

        if self._current_turn_data:
            role = self._current_turn_data["role"]
            model = self._current_turn_data["model"]
            content = self._current_turn_data["content"]
            phase = self._current_turn_data.get("phase", "")
            cfg = configs.get(role, {
                "title": role.capitalize(),
                "bg": "#141A26",
                "border": "#232C3D",
                "accent": "#8C99B2",
                "badge_bg": "#0E131F"
            })
            phase_badge = f'&nbsp;<span style="color: #8BE9FD; font-size: 10px; background: {cfg["badge_bg"]}; padding: 2px 6px; border-radius: 4px; border: 1px solid {cfg["border"]}; font-weight: bold;">{phase}</span>' if phase else ""

            if not content:
                html_parts.append(f"""
                <div style="margin: 10px 0; padding: 10px 14px; background: rgba(255,255,255,0.02); border: 1px dashed {cfg['border']}; border-left: 4px solid {cfg['accent']}; border-radius: 8px;">
                    <div style="margin-bottom: 6px;">
                        <span style="color: {cfg['accent']}; font-weight: bold; font-size: 12px;">{cfg['title']}</span>
                        {phase_badge}
                        &nbsp;
                        <span style="color: #7F8C9F; font-size: 10px; background: {cfg['badge_bg']}; padding: 2px 6px; border-radius: 4px; border: 1px solid {cfg['border']};">Cerebro: {model}</span>
                    </div>
                    <div style="color: #8C99B2; font-size: 11px;">
                        ⏳ <i>Iniciando inferencia y redactando respuesta...</i>
                    </div>
                </div>
                """)
            else:
                clean_content = self._format_markdown_to_html(content)
                cursor = '<span style="color: #00E5FF; font-weight: bold;"> ▌</span>'
                html_parts.append(f"""
                <div style="margin: 12px 0; background-color: {cfg['bg']}; border: 1px solid {cfg['border']}; border-left: 4px solid {cfg['accent']}; border-radius: 8px; padding: 12px 16px;">
                    <div style="margin-bottom: 8px;">
                        <span style="color: {cfg['accent']}; font-weight: bold; font-size: 12px;">{cfg['title']}</span>
                        {phase_badge}
                        &nbsp;
                        <span style="color: #7F8C9F; font-size: 10px; background: {cfg['badge_bg']}; padding: 2px 6px; border-radius: 4px; border: 1px solid {cfg['border']};">Cerebro: {model}</span>
                        &nbsp;
                        <span style="color: #00E5FF; font-size: 10px; font-weight: bold;">(En vivo)</span>
                    </div>
                    <div style="color: #ECEFF4; font-size: 12px; line-height: 1.6;">
                        {clean_content}{cursor}
                    </div>
                </div>
                """)

        if getattr(self, "_debate_completed_banner", False):
            html_parts.append("""
            <div style="margin: 14px 0; padding: 10px 14px; background: rgba(0, 230, 118, 0.08); border: 1px solid #00E676; border-radius: 6px; color: #B9F6CA; text-align: center;">
                ✨ <b>Mesa Redonda Concluida:</b> El Plan Maestro definitivo ha sido sintetizado tras el debate dialéctico. Puedes pulsar <b>💾 Guardar en Bóveda</b> para preservarlo en tu memoria permanente.
            </div>
            """)

        if getattr(self, "_debate_interrupted_banner", False):
            html_parts.append("""
            <div style="margin: 10px 0; padding: 8px 12px; background: rgba(255, 82, 82, 0.1); border-left: 3px solid #FF5252; border-radius: 4px; color: #FF8A80;">
                ⏹️ El debate ha sido interrumpido por el usuario.
            </div>
            """)

        if getattr(self, "_debate_error_banner", None):
            err_text = self._debate_error_banner
            html_parts.append(f"""
            <div style="margin: 10px 0; padding: 8px 12px; background: rgba(255, 82, 82, 0.1); border-left: 3px solid #FF5252; border-radius: 4px; color: #FF8A80;">
                ⚠️ <b>Error en la Mesa Redonda:</b> {err_text}
            </div>
            """)

        sb = self.debate_browser.verticalScrollBar()
        pos_to_keep = sb.value() if not getattr(self, "_council_auto_scroll", True) else None

        self.debate_browser.setHtml("".join(html_parts))

        if getattr(self, "_council_auto_scroll", True):
            self.debate_browser.moveCursor(QTextCursor.MoveOperation.End)
            sb.setValue(sb.maximum())
        else:
            if pos_to_keep is not None:
                sb.setValue(pos_to_keep)

    def eventFilter(self, obj, event):
        if hasattr(self, "debate_browser") and obj == self.debate_browser.viewport():
            if event.type() == QEvent.Type.Wheel:
                delta = event.angleDelta().y()
                sb = self.debate_browser.verticalScrollBar()
                if delta > 0:
                    # Usuario gira rueda hacia arriba: quiere pausar y leer lo anterior
                    self._council_auto_scroll = False
                    self._council_saved_scroll_pos = sb.value()
                    if hasattr(self, "btn_council_scroll_bottom"):
                        self.btn_council_scroll_bottom.setVisible(True)
                elif delta < 0:
                    # Usuario gira rueda hacia abajo: si llega al fondo, reactiva autoscroll
                    if sb.value() >= sb.maximum() - 40:
                        self._council_auto_scroll = True
                        if hasattr(self, "btn_council_scroll_bottom"):
                            self.btn_council_scroll_bottom.setVisible(False)
                    else:
                        self._council_saved_scroll_pos = sb.value()
        return super().eventFilter(obj, event)

    def _on_council_scroll_action_triggered(self, action: int):
        sb = self.debate_browser.verticalScrollBar()
        val = sb.sliderPosition()
        if val >= sb.maximum() - 40:
            self._council_auto_scroll = True
            if hasattr(self, "btn_council_scroll_bottom"):
                self.btn_council_scroll_bottom.setVisible(False)
        else:
            self._council_auto_scroll = False
            self._council_saved_scroll_pos = val
            if hasattr(self, "btn_council_scroll_bottom"):
                self.btn_council_scroll_bottom.setVisible(True)

    def _on_council_scroll_range_changed(self, min_val: int, max_val: int):
        if getattr(self, "_council_auto_scroll", True):
            self.debate_browser.verticalScrollBar().setValue(max_val)

    def _scroll_council_to_bottom(self):
        self._council_auto_scroll = True
        if hasattr(self, "btn_council_scroll_bottom"):
            self.btn_council_scroll_bottom.setVisible(False)
        self.debate_browser.moveCursor(QTextCursor.MoveOperation.End)
        self.debate_browser.verticalScrollBar().setValue(self.debate_browser.verticalScrollBar().maximum())

    def _save_council_to_memory(self):
        try:
            topic = self.council_worker.topic if self.council_worker else self.council_topic_input.toPlainText().strip()
            fact = self.council.save_debate_conclusion_to_memory(
                vault=self.memory,
                topic=topic,
                project_name=topic[:40]
            )
            self.refresh_memory_view()
            self.memory_updated.emit()
            self.log_activity("Memoria", "Plan de Mesa Redonda Guardado", topic[:50])
            QMessageBox.information(
                self,
                "Guardado en Memoria",
                "El Plan Maestro y las conclusiones de la Mesa Redonda han sido grabadas en la Bóveda de Memoria a largo plazo.\n\n"
                "F3NIX recordará esta estrategia en futuras conversaciones y asistencias."
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar en la memoria: {e}")

    def _clear_council_display(self):
        self._debate_turns_history = []
        self._current_turn_data = None
        self._debate_topic = ""
        self._debate_completed_banner = False
        self._debate_interrupted_banner = False
        self._debate_error_banner = None
        self._council_auto_scroll = True
        self._council_saved_scroll_pos = 0
        if hasattr(self, "btn_council_scroll_bottom"):
            self.btn_council_scroll_bottom.setVisible(False)
        self._set_council_welcome_content()
        self.council_topic_input.clear()
        self.btn_save_council_memory.setEnabled(False)
        if hasattr(self, "btn_export_pdf"):
            self.btn_export_pdf.setEnabled(False)
        self.council_status_badge.setText("⚪ Inactivo")
        self.council_status_badge.setStyleSheet("font-size: 11px; color: #8C99B2; background: #0E1521; padding: 3px 10px; border-radius: 10px; border: 1px solid #1E2738;")

    def _set_council_topic_preset(self, text: str):
        self.council_topic_input.setText(text)
        self.council_topic_input.setFocus()

    def _format_markdown_to_html(self, text: str) -> str:
        """Convierte markdown básico y bloques <think> de DeepSeek a HTML estilizado."""
        if not text:
            return ""

        think_blocks = []
        def replace_closed_think(match):
            idx = len(think_blocks)
            think_blocks.append((True, match.group(1).strip()))
            return f"__THINK_BLOCK_{idx}__"

        def replace_open_think(match):
            idx = len(think_blocks)
            think_blocks.append((False, match.group(1).strip()))
            return f"__THINK_BLOCK_{idx}__"

        processed = re.sub(r'<think>(.*?)</think>', replace_closed_think, text, flags=re.DOTALL)
        processed = re.sub(r'<think>(.*)$', replace_open_think, processed, flags=re.DOTALL)

        clean = processed.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        clean = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', clean)
        clean = re.sub(r'\*(.*?)\*', r'<i>\1</i>', clean)
        clean = re.sub(r'^\s*[-*]\s+(.*)$', r'• \1', clean, flags=re.MULTILINE)
        clean = clean.replace("\n", "<br>")

        for idx, (is_closed, content) in enumerate(think_blocks):
            placeholder = f"__THINK_BLOCK_{idx}__"
            c_clean = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            c_clean = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', c_clean)
            c_clean = re.sub(r'\*(.*?)\*', r'<i>\1</i>', c_clean)

            status_header = "💭 Proceso de Razonamiento Interno (DeepSeek R1):" if is_closed else "💭 Razonando en tiempo real... ⏳"
            think_html = (
                f'<div style="margin: 8px 0; padding: 8px 12px; background: rgba(0, 229, 255, 0.05); '
                f'border: 1px solid #1A365D; border-left: 3px solid #00E5FF; border-radius: 6px; '
                f'font-size: 11px; color: #8BE9FD; line-height: 1.5;">'
                f'<div style="font-weight: bold; margin-bottom: 4px; color: #00E5FF;">{status_header}</div>'
                f'{c_clean}'
                f'</div>'
            )
            clean = clean.replace(placeholder, think_html)

        return clean

    # ---------------------------------------------------------
    # Sincronización de Modelos y Voces
    # ---------------------------------------------------------
    def sync_models_and_voices(self, installed_models: List[str], current_model: str, current_voice: str):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for m in installed_models:
            self.model_combo.addItem(m)
        idx = self.model_combo.findText(current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.blockSignals(False)

        self.voice_combo.blockSignals(True)
        v_idx = self.voice_combo.findData(current_voice)
        if v_idx >= 0:
            self.voice_combo.setCurrentIndex(v_idx)
        self.voice_combo.blockSignals(False)

        # Sincronizar selectores de la Mesa Redonda Multi-IA
        combos = [self.combo_estratega, self.combo_critico, self.combo_director]
        for combo in combos:
            combo.blockSignals(True)
            prev = combo.currentText()
            combo.clear()
            for m in installed_models:
                combo.addItem(m)
            p_idx = combo.findText(prev)
            if p_idx >= 0:
                combo.setCurrentIndex(p_idx)
            elif idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)
        self._update_role_chips_text()

    def _on_model_combo_changed(self, text: str):
        if text:
            self.model_changed.emit(text)
            self.log_activity("Sistema", "Cambio de Cerebro de IA", text)

    def _on_voice_combo_changed(self, idx: int):
        v_id = self.voice_combo.currentData()
        if v_id:
            self.voice_changed.emit(v_id)
            self.log_activity("Sistema", "Cambio de Voz", v_id)

    def refresh_models_from_ollama(self):
        """Consulta en vivo a Ollama y actualiza todos los selectores de modelos (cabecera y Mesa Redonda)."""
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=2.0)
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
                if models:
                    current = self.model_combo.currentText()
                    v_id = self.voice_combo.currentData()
                    self.sync_models_and_voices(models, current, v_id)
                    self.log_activity("Sistema", "Modelos sincronizados", f"{len(models)} cerebros detectados en Ollama")
        except Exception as e:
            logger.warning(f"No se pudo refrescar modelos desde Ollama: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_models_from_ollama()

    # ---------------------------------------------------------
    # Mesa Redonda: Narración en Voz Alta Multi-Voz
    # ---------------------------------------------------------
    def _toggle_council_voice(self):
        """Alterna el estado de narración en voz alta de la Mesa Redonda."""
        self.council_tts_enabled = not self.council_tts_enabled
        self._update_council_voice_button_style()
        if self.council_worker and self.council_worker.isRunning():
            self.council_worker.set_tts_enabled(self.council_tts_enabled)
        elif not self.council_tts_enabled and self.speaker:
            self.speaker.stop()
        state_str = "Activada" if self.council_tts_enabled else "Desactivada"
        self.log_activity("Mesa Redonda", f"Narración en Voz Alta {state_str}", "")

    def _update_council_voice_button_style(self):
        """Actualiza el texto y apariencia del botón de narración de la Mesa Redonda."""
        if not hasattr(self, "btn_toggle_council_voice"):
            return
        if self.council_tts_enabled:
            self.btn_toggle_council_voice.setText("🔊 Narrar: SÍ")
            self.btn_toggle_council_voice.setStyleSheet("""
                QPushButton {
                    background-color: #0E291C;
                    color: #00E676;
                    border: 1px solid #00E676;
                    border-radius: 5px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #16402C;
                }
            """)
        else:
            self.btn_toggle_council_voice.setText("🔇 Narrar: OFF")
            self.btn_toggle_council_voice.setStyleSheet("""
                QPushButton {
                    background-color: #141A26;
                    color: #8C99B2;
                    border: 1px solid #232C3D;
                    border-radius: 5px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1E2738;
                    color: #ECEFF4;
                }
            """)

    def _get_council_role_voices(self, mode: str) -> Dict[str, str]:
        """Asigna voces contrastantes e hiperrealistas por cada rol dialéctico."""
        mode_info = DEBATE_MODES.get(mode, DEBATE_MODES["clasico"])
        r1 = mode_info.get("role_1", "estratega")
        r2 = mode_info.get("role_2", "critico")
        rdir = mode_info.get("role_director", "director")

        v1 = "es-MX-JorgeNeural"       # Rol 1: Voz activa y asertiva masculina (México)
        v2 = "es-ES-AlvaroNeural"      # Rol 2: Voz analítica y crítica masculina (España)
        vdir = "es-MX-DaliaNeural"     # Director: Voz ecuánime y resolutiva femenina (México)
        vext = "es-ES-ElviraNeural"    # Extractor / Auditor: Voz técnica y formal femenina (España)

        return {
            r1: v1,
            r2: v2,
            rdir: vdir,
            "estratega": v1,
            "critico": v2,
            "director": vdir,
            "extractor": vext,
            "fenix": v1
        }

    def _on_debate_anchor_clicked(self, url):
        """Maneja clics en enlaces dentro del visor de debate (reproducción de turnos y enlaces web)."""
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        if url_str.startswith("speak:"):
            try:
                turn_idx = int(url_str.split(":")[-1])
                self._play_turn_audio(turn_idx)
            except Exception as e:
                logger.error(f"Error reproduciendo audio del turno: {e}")
        else:
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(url)

    def _play_turn_audio(self, turn_idx: int):
        """Reproduce en voz alta bajo demanda el turno seleccionado con su voz correspondiente."""
        if not self.speaker:
            return
        if self.speaker.is_speaking:
            self.speaker.stop()
            if getattr(self, "_current_playing_turn_idx", None) == turn_idx:
                self._current_playing_turn_idx = None
                return

        if 0 <= turn_idx < len(self._debate_turns_history):
            turn = self._debate_turns_history[turn_idx]
            role = turn.get("role", "")
            title = turn.get("title", role.capitalize())
            reply = turn.get("reply", "")

            mode = getattr(self, "current_council_mode", "clasico")
            role_voices = self._get_council_role_voices(mode)
            voice = role_voices.get(role, self.speaker.current_voice)

            role_name = re.sub(r'[^\w\s]', '', title).strip()
            text_to_speak = f"{role_name}. {reply}" if role_name else reply

            self._current_playing_turn_idx = turn_idx
            self.speaker.speak(
                text_to_speak,
                voice=voice,
                on_finish=lambda: setattr(self, "_current_playing_turn_idx", None)
            )

    def closeEvent(self, event):
        """Limpia procesos y silencia reproducción de audio al cerrar la ventana de F3NIX Studio."""
        if self.council_worker and self.council_worker.isRunning():
            self.council_worker.cancel()
        if self.speaker and self.speaker.is_speaking:
            self.speaker.stop()
        self.window_closed.emit()
        super().closeEvent(event)

