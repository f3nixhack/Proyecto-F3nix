import time
import logging
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextBrowser, QFrame, QApplication
)
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

from core.ai_engine import AIEngine
from core.voice_speaker import VoiceSpeaker

logger = logging.getLogger(__name__)

class LauncherWorker(QThread):
    finished = pyqtSignal(str, float) # reply, elapsed_seconds
    error = pyqtSignal(str)

    def __init__(self, ai_engine: AIEngine, query: str, force_web: bool = False, is_turbo: bool = False, parent=None):
        super().__init__(parent)
        self.ai = ai_engine
        self.query = query
        self.force_web = force_web
        self.is_turbo = is_turbo

    def run(self):
        t0 = time.time()
        try:
            reply = self.ai.chat(
                user_prompt=self.query,
                force_web_search=self.force_web,
                turbo=self.is_turbo
            )
            elapsed = time.time() - t0
            self.finished.emit(reply, elapsed)
        except Exception as e:
            self.error.emit(str(e))

class QuickLauncherBar(QWidget):
    """
    Barra de Invocación Rápida Global estilo Raycast / Spotlight para Windows 11.
    Se activa globalmente con Alt + F desde cualquier aplicación.
    Permite consultas instantáneas, órdenes del sistema y búsqueda web sin abrir el Studio completo.
    """
    open_studio_requested = pyqtSignal()
    query_submitted = pyqtSignal(str)

    def __init__(self, ai_engine: Optional[AIEngine] = None, speaker: Optional[VoiceSpeaker] = None, parent=None):
        super().__init__(parent)
        self.ai = ai_engine or AIEngine()
        self.speaker = speaker
        self.worker: Optional[LauncherWorker] = None
        self.last_reply: str = ""

        # Flags para ventana flotante tipo HUD por encima de todo
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(680)

        self._apply_theme()
        self._init_ui()
        self._center_on_screen()

        # Atajo Esc para cerrar
        esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        esc_shortcut.activated.connect(self.hide_launcher)

    def _apply_theme(self):
        self.setStyleSheet("""
            QWidget {
                color: #ECEFF4;
                font-family: 'Segoe UI', sans-serif;
            }
            QFrame.main_card {
                background-color: rgba(14, 20, 31, 0.97);
                border: 1.5px solid #00E5FF;
                border-radius: 12px;
            }
            QLineEdit {
                background: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 500;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                outline: none;
            }
            QPushButton {
                background-color: #1A2436;
                color: #B0BEC5;
                border: 1px solid #283952;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #22324A;
                color: #00E5FF;
                border-color: #00E5FF;
            }
            QPushButton.toggle_active {
                background-color: #00838F;
                color: #FFFFFF;
                border-color: #00E5FF;
                font-weight: bold;
            }
            QTextBrowser {
                background-color: #101622;
                border: 1px solid #1E2D42;
                border-radius: 8px;
                padding: 10px 14px;
                color: #ECEFF4;
                font-size: 12px;
                line-height: 1.5;
            }
        """)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(0)

        self.main_card = QFrame()
        self.main_card.setProperty("class", "main_card")
        card_layout = QVBoxLayout(self.main_card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        # Fila Superior: Barra de Búsqueda y Botones Rápidos
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        logo_lbl = QLabel("⚡ F3NIX")
        logo_lbl.setStyleSheet("color: #00E5FF; font-weight: 900; font-size: 13px; letter-spacing: 1px;")
        search_row.addWidget(logo_lbl)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Pregúntale a F3NIX o dale una orden (Alt + F para alternar)...")
        self.input_field.returnPressed.connect(self._on_submit)
        search_row.addWidget(self.input_field, stretch=1)

        # Botón Toggle Web
        self.btn_web = QPushButton("🌐 Web")
        self.btn_web.setCheckable(True)
        self.btn_web.setToolTip("Forzar búsqueda de datos en tiempo real con DuckDuckGo")
        self.btn_web.toggled.connect(self._on_web_toggled)
        search_row.addWidget(self.btn_web)

        # Botón Toggle Turbo
        self.btn_turbo = QPushButton("⚡ Turbo")
        self.btn_turbo.setCheckable(True)
        self.btn_turbo.setChecked(True)
        self.btn_turbo.setProperty("class", "toggle_active")
        self.btn_turbo.setToolTip("Modo Turbo: respuestas en 5-10s en CPU")
        self.btn_turbo.toggled.connect(self._on_turbo_toggled)
        search_row.addWidget(self.btn_turbo)

        # Botón Cerrar
        btn_close = QPushButton("✕")
        btn_close.setFixedWidth(26)
        btn_close.setStyleSheet("background: transparent; border: none; color: #78909C; font-size: 13px; font-weight: bold;")
        btn_close.clicked.connect(self.hide_launcher)
        search_row.addWidget(btn_close)

        card_layout.addLayout(search_row)

        # Panel de Respuesta (Oculto hasta que haya consulta)
        self.result_box = QFrame()
        res_layout = QVBoxLayout(self.result_box)
        res_layout.setContentsMargins(0, 4, 0, 0)
        res_layout.setSpacing(6)

        self.result_browser = QTextBrowser()
        self.result_browser.setMaximumHeight(260)
        self.result_browser.setOpenExternalLinks(True)
        res_layout.addWidget(self.result_browser)

        # Footer de Acciones Rápidas
        footer_row = QHBoxLayout()
        footer_row.setSpacing(8)

        self.lbl_status = QLabel("Listo")
        self.lbl_status.setStyleSheet("color: #78909C; font-size: 10.5px;")
        footer_row.addWidget(self.lbl_status, stretch=1)

        self.btn_listen = QPushButton("🔊 Escuchar")
        self.btn_listen.setToolTip("Leer la respuesta con voz natural")
        self.btn_listen.clicked.connect(self._speak_reply)
        footer_row.addWidget(self.btn_listen)

        self.btn_copy = QPushButton("📋 Copiar")
        self.btn_copy.setToolTip("Copiar texto al portapapeles")
        self.btn_copy.clicked.connect(self._copy_reply)
        footer_row.addWidget(self.btn_copy)

        btn_studio = QPushButton("💬 Abrir Studio")
        btn_studio.clicked.connect(self._open_studio)
        footer_row.addWidget(btn_studio)

        res_layout.addLayout(footer_row)
        self.result_box.setVisible(False)
        card_layout.addWidget(self.result_box)

        root_layout.addWidget(self.main_card)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + (geom.height() // 4)
            self.move(x, y)

    def show_launcher(self):
        self._center_on_screen()
        self.show()
        self.raise_()
        self.activateWindow()
        self.input_field.setFocus()
        self.input_field.selectAll()

    def hide_launcher(self):
        self.hide()

    def toggle_launcher(self):
        if self.isVisible():
            self.hide_launcher()
        else:
            self.show_launcher()

    def toggle_bar(self):
        """Alias conveniente para toggle_launcher."""
        self.toggle_launcher()

    def _on_web_toggled(self, checked: bool):
        if checked:
            self.btn_web.setStyleSheet("background-color: #00838F; color: #FFFFFF; border: 1px solid #00E5FF; font-weight: bold;")
        else:
            self.btn_web.setStyleSheet("")

    def _on_turbo_toggled(self, checked: bool):
        if checked:
            self.btn_turbo.setStyleSheet("background-color: #00838F; color: #FFFFFF; border: 1px solid #00E5FF; font-weight: bold;")
        else:
            self.btn_turbo.setStyleSheet("")

    def _on_submit(self):
        text = self.input_field.text().strip()
        if not text:
            return

        self.lbl_status.setText("⏳ Razonando...")
        self.result_box.setVisible(True)
        self.result_browser.setHtml(f"<i>Consultando a F3NIX: «{text}»...</i>")
        self.adjustSize()

        force_web = self.btn_web.isChecked()
        is_turbo = self.btn_turbo.isChecked()

        self.worker = LauncherWorker(
            ai_engine=self.ai,
            query=text,
            force_web=force_web,
            is_turbo=is_turbo
        )
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    def _on_worker_finished(self, reply: str, elapsed: float):
        self.last_reply = reply
        self.lbl_status.setText(f"✓ Respondido en {elapsed:.1f}s • Modo: {'Turbo ⚡' if self.btn_turbo.isChecked() else 'Estándar'}")
        
        # Formato Markdown básico a HTML
        formatted = reply.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        import re
        formatted = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', formatted)
        formatted = re.sub(r'\*(.*?)\*', r'<i>\1</i>', formatted)
        formatted = formatted.replace("\n", "<br>")
        
        self.result_browser.setHtml(formatted)
        self.adjustSize()

    def _on_worker_error(self, err_msg: str):
        self.lbl_status.setText("⚠️ Error en consulta")
        self.result_browser.setHtml(f"<span style='color: #FF5252;'>Error: {err_msg}</span>")

    def _speak_reply(self):
        if self.last_reply and self.speaker:
            self.speaker.speak(self.last_reply[:400])

    def _copy_reply(self):
        if self.last_reply:
            QApplication.clipboard().setText(self.last_reply)
            self.lbl_status.setText("✓ ¡Copiado al portapapeles!")

    def _open_studio(self):
        self.hide_launcher()
        self.open_studio_requested.emit()
