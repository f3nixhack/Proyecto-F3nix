import os
import threading
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QApplication, QGraphicsDropShadowEffect
)

class SelectionCopilotWidget(QWidget):
    """
    Mini Copiloto Flotante contextual para Windows 11.
    Aparece junto al cursor tras seleccionar texto y presionar el atajo global (Ctrl + Alt + C).
    Permite Explicar, Traducir, Corregir o Resumir al instante.
    """
    closed = pyqtSignal()
    action_requested = pyqtSignal(str, str)  # (action_type, text)
    chunk_received = pyqtSignal(str)
    status_updated = pyqtSignal(str)

    def __init__(self, ai_engine=None):
        super().__init__()
        self.ai = ai_engine
        self.selected_text = ""
        self._is_busy = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(380, 290)

        self._setup_ui()

        self.chunk_received.connect(self.result_box.setText)
        self.status_updated.connect(self.status_label.setText)

    def _setup_ui(self):
        # Contenedor principal con sombra
        self.main_container = QWidget(self)
        self.main_container.setGeometry(10, 10, 360, 270)
        self.main_container.setStyleSheet(
            "background-color: rgba(14, 18, 28, 0.96);"
            "border: 1px solid rgba(0, 229, 255, 0.45);"
            "border-radius: 10px;"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 229, 255, 90))
        shadow.setOffset(0, 4)
        self.main_container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.main_container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        title = QLabel("✨ F3NIX COPILOTO")
        title.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 11px; letter-spacing: 1px;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet(
            "QPushButton { color: #8892B0; background: transparent; border: none; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { color: #FF2E63; }"
        )
        close_btn.clicked.connect(self.hide_copilot)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Vista previa del texto seleccionado
        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        self.preview_label.setMaximumHeight(35)
        self.preview_label.setStyleSheet("color: #8892B0; font-size: 10px; font-style: italic; background: rgba(255,255,255,0.03); border-radius: 4px; padding: 2px 4px;")
        layout.addWidget(self.preview_label)

        # Botones de Acción Rápida
        actions_row = QHBoxLayout()
        actions_row.setSpacing(4)

        btn_style = (
            "QPushButton {"
            "  background: rgba(0, 229, 255, 0.12);"
            "  color: #FFFFFF;"
            "  border: 1px solid rgba(0, 229, 255, 0.35);"
            "  border-radius: 6px;"
            "  font-size: 10px;"
            "  font-weight: 600;"
            "  padding: 4px 6px;"
            "}"
            "QPushButton:hover {"
            "  background: #00E5FF;"
            "  color: #0E121C;"
            "}"
        )

        self.btn_explain = QPushButton("💡 Explicar")
        self.btn_explain.setStyleSheet(btn_style)
        self.btn_explain.clicked.connect(lambda: self.trigger_action("explicar"))

        self.btn_translate = QPushButton("🌐 Traducir")
        self.btn_translate.setStyleSheet(btn_style)
        self.btn_translate.clicked.connect(lambda: self.trigger_action("traducir"))

        self.btn_fix = QPushButton("🛠️ Corregir")
        self.btn_fix.setStyleSheet(btn_style)
        self.btn_fix.clicked.connect(lambda: self.trigger_action("corregir"))

        self.btn_summary = QPushButton("📋 Resumir")
        self.btn_summary.setStyleSheet(btn_style)
        self.btn_summary.clicked.connect(lambda: self.trigger_action("resumir"))

        for b in [self.btn_explain, self.btn_translate, self.btn_fix, self.btn_summary]:
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            actions_row.addWidget(b)

        layout.addLayout(actions_row)

        # Área de Resultado
        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setPlaceholderText("Selecciona una acción arriba...")
        self.result_box.setStyleSheet(
            "QTextEdit {"
            "  background: rgba(8, 12, 20, 0.85);"
            "  color: #E2E8F0;"
            "  border: 1px solid rgba(255, 255, 255, 0.1);"
            "  border-radius: 6px;"
            "  font-size: 11px;"
            "  padding: 4px;"
            "}"
        )
        layout.addWidget(self.result_box)

        # Footer con botón Copiar
        footer = QHBoxLayout()
        self.status_label = QLabel("Presiona Esc para cerrar")
        self.status_label.setStyleSheet("color: #64748B; font-size: 9px;")
        footer.addWidget(self.status_label)
        footer.addStretch()

        self.copy_btn = QPushButton("📋 Copiar")
        self.copy_btn.setFixedSize(65, 22)
        self.copy_btn.setStyleSheet(
            "QPushButton { background: rgba(255, 255, 255, 0.08); color: #F1F5F9; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 4px; font-size: 10px; }"
            "QPushButton:hover { background: rgba(0, 229, 255, 0.25); color: #00E5FF; border-color: #00E5FF; }"
        )
        self.copy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_btn.clicked.connect(self._copy_result)
        footer.addWidget(self.copy_btn)

        layout.addLayout(footer)

    def show_at_cursor(self, text: str):
        """Muestra el widget cerca de la posición actual del cursor."""
        self.selected_text = text.strip()
        if not self.selected_text:
            return

        try:
            from core.f3nix_tools import F3nixTools
            F3nixTools.clipboard_ring.add(self.selected_text)
        except Exception:
            pass

        preview = self.selected_text.replace("\n", " ")
        if len(preview) > 100:
            preview = preview[:97] + "..."
        self.preview_label.setText(f"«{preview}»")
        self.result_box.clear()
        self.status_label.setText("Elige una acción")

        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            x = cursor_pos.x() + 15
            y = cursor_pos.y() + 15

            # Evitar salirse por el borde derecho o inferior
            if x + self.width() > geom.right():
                x = cursor_pos.x() - self.width() - 15
            if y + self.height() > geom.bottom():
                y = cursor_pos.y() - self.height() - 15

            self.move(max(geom.left(), x), max(geom.top(), y))

        self.show()
        self.raise_()
        self.activateWindow()

    def trigger_action(self, action_type: str):
        """Ejecuta una acción usando el motor de IA."""
        if self._is_busy or not self.selected_text:
            return

        self._is_busy = True
        self.status_label.setText(f"Procesando {action_type}...")
        self.result_box.setPlaceholderText("Generando respuesta en streaming...")

        prompts = {
            "explicar": f"Explica de forma concisa y clara en español el siguiente texto o código:\n\n{self.selected_text}",
            "traducir": f"Traduce fiel y naturalmente al español el siguiente texto:\n\n{self.selected_text}",
            "corregir": f"Corrige la ortografía, redacción o sintaxis del siguiente texto, manteniendo el sentido original:\n\n{self.selected_text}",
            "resumir": f"Genera un resumen breve en viñetas en español de los puntos clave del siguiente texto:\n\n{self.selected_text}"
        }

        prompt = prompts.get(action_type, prompts["explicar"])

        threading.Thread(
            target=self._process_action_thread,
            args=(prompt,),
            daemon=True
        ).start()

    def _process_action_thread(self, prompt: str):
        try:
            if not self.ai:
                self.chunk_received.emit("Motor de IA no conectado.")
                return

            accumulated = ""
            for chunk in self.ai.chat_stream(prompt):
                if chunk.get("type") == "token":
                    accumulated += chunk.get("content", "")
                    self.chunk_received.emit(accumulated)
                elif chunk.get("type") == "error":
                    self.chunk_received.emit(f"Error: {chunk.get('content')}")
                    break

            self.status_updated.emit("Completado")
        except Exception as e:
            self.chunk_received.emit(f"Error procesando acción: {e}")
            self.status_updated.emit("Error")
        finally:
            self._is_busy = False

    def _copy_result(self):
        txt = self.result_box.toPlainText().strip()
        if txt:
            QApplication.clipboard().setText(txt)
            self.status_label.setText("¡Copiado al portapapeles!")

    def hide_copilot(self):
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide_copilot()
        else:
            super().keyPressEvent(event)
