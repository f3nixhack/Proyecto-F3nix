"""
F3NIX Call Dialog - Ventana de Llamada Telefónica en Tiempo Real (Voz a Voz)
Inspirada en el diseño de llamada telefónica de ChoferPro y Salud:
- Cronómetro de llamada activa con indicador pulsante
- Avatar central reactivo con ondas y anillos de pulso
- Burbuja de diálogo bidireccional en vivo (Tú / F3NIX)
- Carrusel de Quick Pills con disparadores instantáneos de conversación
- Barra de control telefónico: Mute, Botón central interactivo de Micrófono y Colgar (botón rojo)
- Selector de tono/personalidad en caliente: Colega Amigo, Sin Filtro y Director Estratégico
"""

import time
import re
from typing import Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QRadialGradient, QLinearGradient, QFont, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QFrame, QScrollArea, QGraphicsDropShadowEffect
)

TONE_INFO = {
    "amigo": {
        "label": "☕ Colega Amigo",
        "color": "#FFB703",
        "border": "rgba(255, 183, 3, 0.4)",
        "bg": "rgba(255, 183, 3, 0.15)",
        "desc": "Relajado, empático y con humor"
    },
    "sin_filtro": {
        "label": "🐺 Sin Filtro",
        "color": "#FF3366",
        "border": "rgba(255, 51, 102, 0.4)",
        "bg": "rgba(255, 51, 102, 0.15)",
        "desc": "Humor ácido, directo al hueso y sarcasmo"
    },
    "director": {
        "label": "🏛️ Director",
        "color": "#00E5FF",
        "border": "rgba(0, 229, 255, 0.4)",
        "bg": "rgba(0, 229, 255, 0.15)",
        "desc": "Asesor ejecutivo senior de alto impacto"
    }
}

QUICK_PILLS = [
    ("☕ ¿Qué opinás de mi día?", "Che, ¿qué opinás de cómo vengo llevando mi día hoy?"),
    ("🧠 Dame un consejo", "Necesito un buen consejo tuyo, sincero y práctico."),
    ("😂 Contame algo gracioso", "Tirame algo con humor para descomprimir y reírnos un rato."),
    ("🐺 Decime la verdad sin filtro", "Sé sincero conmigo y decime la verdad sin filtro."),
    ("🚀 Sube mi código a GitHub", "Sube todos mis cambios actuales del proyecto a GitHub con commit automático."),
    ("⚡ ¿Cómo optimizo mi tiempo?", "¿Qué estrategia me recomendás para optimizar mi tiempo en las próximas horas?"),
    ("🏛️ Analicemos mi próximo paso", "Hagamos un análisis estratégico rápido: ¿cuál debería ser mi jugada crítica ahora?")
]


class CallAvatarWidget(QWidget):
    """Widget de avatar central animado con pulsos de llamada telefónica."""
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.call_state = "listening"  # "listening", "speaking", "thinking", "idle", "muted"
        self.tone = "amigo"
        self.pulse_phase = 0.0
        self.avatar_pixmap: Optional[QPixmap] = None

        # Animación continua de pulso (30 FPS)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._step_animation)
        self.anim_timer.start(33)

    def set_avatar_pixmap(self, pixmap: Optional[QPixmap]):
        self.avatar_pixmap = pixmap
        self.update()

    def set_call_state(self, state: str):
        self.call_state = state
        self.update()

    def set_tone(self, tone: str):
        self.tone = tone
        self.update()

    def _step_animation(self):
        self.pulse_phase += 0.08
        if self.pulse_phase > 6.283:
            self.pulse_phase = 0.0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        base_radius = 56.0

        # Colores según estado y tono
        tone_color = QColor(TONE_INFO.get(self.tone, {}).get("color", "#FFB703"))
        if self.call_state == "speaking":
            glow_color = tone_color
            pulse_amp = 12.0
        elif self.call_state == "listening":
            glow_color = QColor(16, 185, 129)  # Verde esmeralda
            pulse_amp = 7.0
        elif self.call_state == "thinking":
            glow_color = QColor(255, 183, 3)   # Amarillo ámbar
            pulse_amp = 5.0
        else:
            glow_color = QColor(100, 116, 139) # Gris azulado
            pulse_amp = 2.0

        import math
        dynamic_offset = math.sin(self.pulse_phase) * pulse_amp

        # 1. Anillo de ondas exterior pulsante
        outer_radius = base_radius + 18.0 + dynamic_offset
        pen_outer = QPen(QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 60), 2.5)
        painter.setPen(pen_outer)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPoint(int(center_x), int(center_y)), int(outer_radius), int(outer_radius))

        # 2. Resplandor radial intermedio
        radial = QRadialGradient(center_x, center_y, outer_radius)
        radial.setColorAt(0.0, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 100))
        radial.setColorAt(0.6, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 35))
        radial.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(radial))
        painter.drawEllipse(QPoint(int(center_x), int(center_y)), int(outer_radius), int(outer_radius))

        # 3. Círculo principal del Avatar
        inner_r = int(base_radius)
        if self.avatar_pixmap and not self.avatar_pixmap.isNull():
            # Dibujar avatar personalizado enmascarado
            painter.setPen(QPen(glow_color, 3.0))
            painter.setBrush(QBrush(QColor(15, 23, 42)))
            painter.drawEllipse(QPoint(int(center_x), int(center_y)), inner_r, inner_r)

            from PyQt6.QtGui import QPainterPath
            path = QPainterPath()
            path.addEllipse(center_x - inner_r, center_y - inner_r, inner_r * 2, inner_r * 2)
            painter.save()
            painter.setClipPath(path)
            scaled = self.avatar_pixmap.scaled(
                inner_r * 2, inner_r * 2,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(int(center_x - inner_r), int(center_y - inner_r), scaled)
            painter.restore()
        else:
            # Monograma degradado de F3NIX
            grad = QLinearGradient(0, center_y - inner_r, 0, center_y + inner_r)
            grad.setColorAt(0.0, QColor(255, 42, 109))
            grad.setColorAt(1.0, glow_color)

            painter.setPen(QPen(QColor(255, 255, 255, 180), 2.0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPoint(int(center_x), int(center_y)), inner_r, inner_r)

            # Texto "F3"
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Segoe UI", 26, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(int(center_x - inner_r), int(center_y - inner_r), inner_r * 2, inner_r * 2,
                             Qt.AlignmentFlag.AlignCenter, "F3")

        painter.end()


class F3nixCallDialog(QDialog):
    """
    Diálogo modal flotante de llamada telefónica bidireccional.
    Emite señales para integración con ThrusterApp, VoiceListener y AIEngine.
    """
    call_ended = pyqtSignal()
    query_submitted = pyqtSignal(str)
    hands_free_toggled = pyqtSignal(bool)
    tone_changed = pyqtSignal(str)
    mute_toggled = pyqtSignal(bool)
    barge_in_requested = pyqtSignal()

    def __init__(self, parent=None, current_tone: str = "amigo", hands_free: bool = True):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(390, 590)

        self.current_tone = current_tone if current_tone in TONE_INFO else "amigo"
        self.hands_free = hands_free
        self.is_muted = False
        self.call_start_time = time.time()
        self.drag_position = QPoint()

        # Configurar UI
        self._init_ui()

        # Timer de duración de llamada (1s)
        self.call_timer = QTimer(self)
        self.call_timer.timeout.connect(self._update_call_timer)
        self.call_timer.start(1000)

    def _init_ui(self):
        # Contenedor con borde glowing y esquinas redondeadas
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)

        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("mainFrame")
        self.main_frame.setStyleSheet("""
            QFrame#mainFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0B0F19, stop:0.5 #0F172A, stop:1 #080C14);
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 20px;
            }
        """)

        # Sombra exterior
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 229, 255, 80))
        shadow.setOffset(0, 6)
        self.main_frame.setGraphicsEffect(shadow)

        frame_layout = QVBoxLayout(self.main_frame)
        frame_layout.setContentsMargins(18, 14, 18, 16)
        frame_layout.setSpacing(10)

        # 1. Barra de cabecera (Header de la llamada)
        header = QHBoxLayout()
        header.setSpacing(8)

        # Indicador de llamada activa y temporizador
        self.timer_label = QLabel("🟢 00:00", self)
        self.timer_label.setStyleSheet("color: #10B981; font-weight: bold; font-size: 13px; font-family: 'Segoe UI', monospace;")
        header.addWidget(self.timer_label)

        header.addStretch()

        # Selector de Tono/Personalidad en caliente
        self.tone_btn = QPushButton(self)
        self.tone_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_tone_button_style()
        self.tone_btn.clicked.connect(self._cycle_tone)
        header.addWidget(self.tone_btn)

        # Botón Manos Libres vs PTT
        self.hf_btn = QPushButton(self)
        self.hf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_hf_button_style()
        self.hf_btn.clicked.connect(self._toggle_hands_free)
        header.addWidget(self.hf_btn)

        # Botón de cerrar/minimizar superior
        close_btn = QPushButton("✕", self)
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Finalizar y cerrar llamada")
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 11px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #EF4444;
                color: #FFFFFF;
                border-color: #EF4444;
            }
        """)
        close_btn.clicked.connect(self.end_call)
        header.addWidget(close_btn)

        frame_layout.addLayout(header)

        # 2. Título de llamada y estado
        self.call_title = QLabel("Llamada F3NIX", self)
        self.call_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.call_title.setStyleSheet("color: #F8FAFC; font-size: 16px; font-weight: 700; margin-top: 2px;")
        frame_layout.addWidget(self.call_title)

        self.status_subtitle = QLabel("Conectado • Escuchando tu voz", self)
        self.status_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_subtitle.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 600;")
        frame_layout.addWidget(self.status_subtitle)

        # 3. Avatar Central Animado con Pulso
        avatar_container = QHBoxLayout()
        avatar_container.addStretch()
        self.call_avatar = CallAvatarWidget(self)
        self.call_avatar.set_tone(self.current_tone)
        self.call_avatar.clicked.connect(self._on_avatar_clicked)
        avatar_container.addWidget(self.call_avatar)
        avatar_container.addStretch()
        frame_layout.addLayout(avatar_container)

        hint_label = QLabel("Toca el orbe o mantén F12 para hablar / interrumpir", self)
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setStyleSheet("color: #64748B; font-size: 10px;")
        frame_layout.addWidget(hint_label)

        # 4. Burbuja de diálogo bidireccional en vivo
        self.transcript_box = QFrame(self)
        self.transcript_box.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 6px;
            }
        """)
        transcript_layout = QVBoxLayout(self.transcript_box)
        transcript_layout.setContentsMargins(10, 8, 10, 8)
        transcript_layout.setSpacing(4)

        self.user_bubble = QLabel("Tú: Esperando tu voz...", self)
        self.user_bubble.setWordWrap(True)
        self.user_bubble.setStyleSheet("color: #94A3B8; font-size: 11px; font-style: italic;")
        transcript_layout.addWidget(self.user_bubble)

        self.assistant_bubble = QLabel("F3NIX: ¡Hola! Acá estoy, tirame lo que quieras que charlemos.", self)
        self.assistant_bubble.setWordWrap(True)
        self.assistant_bubble.setStyleSheet("color: #F1F5F9; font-size: 12px; font-weight: 500;")
        transcript_layout.addWidget(self.assistant_bubble)

        frame_layout.addWidget(self.transcript_box)

        # 5. Carrusel de Quick Pills horizontales
        pills_scroll = QScrollArea(self)
        pills_scroll.setFixedHeight(36)
        pills_scroll.setWidgetResizable(True)
        pills_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pills_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pills_scroll.setStyleSheet("background: transparent; border: none;")

        pills_widget = QWidget()
        pills_widget.setStyleSheet("background: transparent;")
        pills_layout = QHBoxLayout(pills_widget)
        pills_layout.setContentsMargins(0, 0, 0, 0)
        pills_layout.setSpacing(6)

        for label_text, prompt_text in QUICK_PILLS:
            pill = QPushButton(label_text, pills_widget)
            pill.setCursor(Qt.CursorShape.PointingHandCursor)
            pill.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.06);
                    color: #E2E8F0;
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 13px;
                    padding: 4px 10px;
                    font-size: 11px;
                    white-space: nowrap;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255, 0.2);
                    border-color: #00E5FF;
                    color: #FFFFFF;
                }
            """)
            pill.clicked.connect(lambda checked, p=prompt_text: self.submit_quick_prompt(p))
            pills_layout.addWidget(pill)

        pills_scroll.setWidget(pills_widget)
        frame_layout.addWidget(pills_scroll)

        # 6. Barra de controles de teléfono
        controls = QHBoxLayout()
        controls.setSpacing(18)
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Botón Mute / Altavoz
        self.mute_btn = QPushButton("🔊", self)
        self.mute_btn.setFixedSize(48, 48)
        self.mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mute_btn.setToolTip("Silenciar o reactivar altavoz")
        self.mute_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 24px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.16);
            }
        """)
        self.mute_btn.clicked.connect(self._toggle_mute)
        controls.addWidget(self.mute_btn)

        # Botón Central de Micrófono (Grande y llamativo)
        self.mic_btn = QPushButton("🎙️", self)
        self.mic_btn.setFixedSize(62, 62)
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setToolTip("Hablar / Interrumpir (Barge-in)")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10B981, stop:1 #059669);
                color: #FFFFFF;
                border: 2px solid rgba(255, 255, 255, 0.4);
                border-radius: 31px;
                font-size: 24px;
            }
            QPushButton:hover {
                background: #34D399;
                border-color: #FFFFFF;
            }
        """)
        self.mic_btn.clicked.connect(self._on_mic_button_clicked)
        controls.addWidget(self.mic_btn)

        # Botón Colgar / Finalizar llamada (Rojo telefónico)
        self.hangup_btn = QPushButton("📞", self)
        self.hangup_btn.setFixedSize(48, 48)
        self.hangup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hangup_btn.setToolTip("Colgar y finalizar llamada")
        self.hangup_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EF4444, stop:1 #DC2626);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 24px;
                font-size: 20px;
            }
            QPushButton:hover {
                background: #F87171;
            }
        """)
        self.hangup_btn.clicked.connect(self.end_call)
        controls.addWidget(self.hangup_btn)

        frame_layout.addLayout(controls)
        root_layout.addWidget(self.main_frame)

    # ------------------ ESTILOS DINÁMICOS ------------------
    def _update_tone_button_style(self):
        info = TONE_INFO.get(self.current_tone, TONE_INFO["amigo"])
        self.tone_btn.setText(info["label"])
        self.tone_btn.setToolTip(f"Personalidad: {info['desc']} (Clic para cambiar)")
        self.tone_btn.setStyleSheet(f"""
            QPushButton {{
                background: {info['bg']};
                color: {info['color']};
                border: 1px solid {info['border']};
                border-radius: 12px;
                padding: 3px 9px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {info['color']};
                color: #000000;
            }}
        """)
        if hasattr(self, "call_avatar"):
            self.call_avatar.set_tone(self.current_tone)

    def _update_hf_button_style(self):
        if self.hands_free:
            self.hf_btn.setText("🎙️ Manos Libres")
            self.hf_btn.setToolTip("Modo Manos Libres: Escucha automática continua")
            self.hf_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(16, 185, 129, 0.15);
                    color: #10B981;
                    border: 1px solid rgba(16, 185, 129, 0.4);
                    border-radius: 12px;
                    padding: 3px 9px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: rgba(16, 185, 129, 0.3);
                }
            """)
        else:
            self.hf_btn.setText("🔘 PTT (F12)")
            self.hf_btn.setToolTip("Modo Push-To-Talk: Mantén F12 para hablar")
            self.hf_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(148, 163, 184, 0.15);
                    color: #94A3B8;
                    border: 1px solid rgba(148, 163, 184, 0.3);
                    border-radius: 12px;
                    padding: 3px 9px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: rgba(148, 163, 184, 0.25);
                    color: #F8FAFC;
                }
            """)

    def _cycle_tone(self):
        tones = ["amigo", "sin_filtro", "director"]
        idx = (tones.index(self.current_tone) + 1) % len(tones)
        self.current_tone = tones[idx]
        self._update_tone_button_style()
        self.tone_changed.emit(self.current_tone)

    def _toggle_hands_free(self):
        self.hands_free = not self.hands_free
        self._update_hf_button_style()
        self.hands_free_toggled.emit(self.hands_free)

    def _toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            self.mute_btn.setText("🔇")
            self.mute_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(239, 68, 68, 0.2);
                    color: #EF4444;
                    border: 1px solid rgba(239, 68, 68, 0.5);
                    border-radius: 24px;
                    font-size: 18px;
                }
            """)
            self.status_subtitle.setText("Altavoz silenciado")
            self.status_subtitle.setStyleSheet("color: #EF4444; font-size: 12px;")
        else:
            self.mute_btn.setText("🔊")
            self.mute_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.08);
                    color: #FFFFFF;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 24px;
                    font-size: 18px;
                }
            """)
            self.status_subtitle.setText("Conectado • Escuchando tu voz")
            self.status_subtitle.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 600;")
        self.mute_toggled.emit(self.is_muted)

    def _on_avatar_clicked(self):
        """Interrumpe al asistente o fuerza la escucha."""
        self.barge_in_requested.emit()

    def _on_mic_button_clicked(self):
        """Dispara barge-in o solicita hablar."""
        self.barge_in_requested.emit()

    def _update_call_timer(self):
        elapsed = int(time.time() - self.call_start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        dot = "🟢" if (secs % 2 == 0) else "⚪"
        self.timer_label.setText(f"{dot} {mins:02d}:{secs:02d}")

    # ------------------ EVENTOS DE DIÁLOGO Y CONVERSACIÓN ------------------
    def update_user_speech(self, text: str):
        """Muestra lo que dijo el usuario."""
        if text.strip():
            self.user_bubble.setText(f"Tú: \"{text.strip()}\"")
            self.status_subtitle.setText("Pensando respuesta...")
            self.status_subtitle.setStyleSheet("color: #FFB703; font-size: 12px; font-weight: 600;")
            self.call_avatar.set_call_state("thinking")

    def update_assistant_speech(self, text: str, is_final: bool = False):
        """Muestra lo que responde F3NIX."""
        if text.strip():
            self.assistant_bubble.setText(f"F3NIX: \"{text.strip()}\"")
            if not is_final:
                self.status_subtitle.setText("F3NIX hablando...")
                self.status_subtitle.setStyleSheet("color: #00E5FF; font-size: 12px; font-weight: 600;")
                self.call_avatar.set_call_state("speaking")
            else:
                self.status_subtitle.setText("Conectado • Escuchándote...")
                self.status_subtitle.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 600;")
                self.call_avatar.set_call_state("listening")

    def submit_quick_prompt(self, prompt: str):
        """Ejecuta una Quick Pill como si el usuario la hubiera hablado."""
        self.user_bubble.setText(f"Tú: \"{prompt}\"")
        self.status_subtitle.setText("Pensando respuesta...")
        self.status_subtitle.setStyleSheet("color: #FFB703; font-size: 12px; font-weight: 600;")
        self.call_avatar.set_call_state("thinking")
        self.query_submitted.emit(prompt)

    def set_avatar_image(self, pixmap: Optional[QPixmap]):
        if hasattr(self, "call_avatar"):
            self.call_avatar.set_avatar_pixmap(pixmap)

    def end_call(self):
        """Finaliza la llamada y cierra la ventana."""
        self.call_timer.stop()
        self.call_ended.emit()
        self.close()

    # ------------------ SOPORTE PARA ARRASTRAR LA VENTANA ------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
