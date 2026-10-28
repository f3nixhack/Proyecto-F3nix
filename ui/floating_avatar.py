import os
import sys
from PyQt6.QtCore import Qt, QPoint, QRectF, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath, QPixmap,
    QRadialGradient, QLinearGradient, QFont, QAction, QCursor
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMenu,
    QGraphicsDropShadowEffect, QApplication, QLineEdit, QPushButton,
    QScrollArea, QCheckBox
)

STATE_COLORS = {
    "idle": QColor(0, 229, 255),        # Cyan brillante
    "listening": QColor(255, 46, 99),   # Rojo neón (F12 presionado)
    "thinking": QColor(255, 183, 3),    # Ámbar / Dorado (procesando IA)
    "speaking": QColor(58, 134, 255),   # Azul eléctrico (reproduciendo voz)
    "alarm": QColor(255, 0, 128),       # Magenta / Neón (alarma/pomodoro cumplido)
}

AVATAR_THEMES = {
    "cyberpunk": {
        "name": "Cyan Cyberpunk (Original)",
        "colors": {
            "idle": QColor(0, 229, 255),
            "listening": QColor(255, 46, 99),
            "thinking": QColor(255, 183, 3),
            "speaking": QColor(58, 134, 255),
            "alarm": QColor(255, 0, 128)
        },
        "accent": "#00E5FF",
        "bg_hud": "rgba(10, 18, 30, 0.94)"
    },
    "iron_man": {
        "name": "Iron Man Arc Reactor (Oro & Carmesí)",
        "colors": {
            "idle": QColor(255, 215, 0),        # Oro
            "listening": QColor(230, 20, 30),    # Carmesí
            "thinking": QColor(255, 140, 0),    # Fuego
            "speaking": QColor(255, 235, 150),  # Oro brillante
            "alarm": QColor(255, 50, 50)
        },
        "accent": "#FFD700",
        "bg_hud": "rgba(30, 12, 14, 0.94)"
    },
    "matrix": {
        "name": "Matrix Hacker (Verde Terminal)",
        "colors": {
            "idle": QColor(0, 255, 102),        # Verde Neón
            "listening": QColor(255, 50, 70),    # Alerta Roja
            "thinking": QColor(160, 255, 0),    # Lima Hacker
            "speaking": QColor(0, 230, 118),    # Verde Terminal
            "alarm": QColor(255, 0, 80)
        },
        "accent": "#00FF66",
        "bg_hud": "rgba(6, 24, 12, 0.94)"
    },
    "synthwave": {
        "name": "Neon Synthwave (Fucsia & Púrpura)",
        "colors": {
            "idle": QColor(213, 0, 249),        # Violeta Neón
            "listening": QColor(255, 23, 68),    # Rojo Neón
            "thinking": QColor(255, 0, 128),    # Magenta
            "speaking": QColor(0, 229, 255),    # Cyan Neón
            "alarm": QColor(255, 110, 0)
        },
        "accent": "#D500F9",
        "bg_hud": "rgba(24, 10, 34, 0.94)"
    }
}

STATE_LABELS = {
    "idle": "En línea (F12)",
    "listening": "Escuchando...",
    "thinking": "Pensando...",
    "speaking": "Hablando...",
    "alarm": "¡Alarma Cumplida!",
}

class FloatingAvatar(QWidget):
    """
    HUD flotante transparente, arrastrable y siempre visible con estados visuales
    de animación y burbuja de texto.
    """
    state_changed = pyqtSignal(str)
    subtitle_received = pyqtSignal(str, str)
    text_submitted = pyqtSignal(str)
    model_change_requested = pyqtSignal(str)
    voice_change_requested = pyqtSignal(str)
    file_dropped = pyqtSignal(str)
    analyze_clipboard_requested = pyqtSignal()
    open_model_store_requested = pyqtSignal()
    open_command_deck_requested = pyqtSignal()
    open_quick_guide_requested = pyqtSignal()
    toggle_studio_requested = pyqtSignal()
    open_doctor_requested = pyqtSignal()
    toggle_quick_launcher_requested = pyqtSignal()
    toggle_turbo_requested = pyqtSignal()
    clear_history_requested = pyqtSignal()
    trigger_screen_analysis_requested = pyqtSignal()
    trigger_system_audio_summary_requested = pyqtSignal()
    trigger_selection_copilot_requested = pyqtSignal()
    brain_badge_changed = pyqtSignal(str)
    task_added = pyqtSignal(str)
    task_toggled = pyqtSignal(str)
    task_deleted = pyqtSignal(str)
    clear_completed_tasks_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    position_changed = pyqtSignal(int, int)
    interrupt_requested = pyqtSignal()
    skin_changed = pyqtSignal(str)
    avatar_image_changed = pyqtSignal(str)
    hands_free_toggled = pyqtSignal(bool)

    def __init__(self, avatar_path: str = "thruster_avatar.jpg"):
        super().__init__()
        self.avatar_path = avatar_path
        self.current_state = "idle"
        self.drag_position = QPoint()
        self.glow_radius = 10.0
        self.glow_step = 0.5
        self.show_subtitles = True
        self.available_models = []
        self.active_model = ""
        self.current_voice = "es-MX-JorgeNeural"
        self.is_mini_mode = False
        self.current_skin = "cyberpunk"
        self.state_colors = dict(AVATAR_THEMES["cyberpunk"]["colors"])
        self.hands_free_active = False

        # Habilitar arrastrar y soltar archivos directamente sobre el avatar
        self.setAcceptDrops(True)

        # Tamaño del widget principal
        self.avatar_size = 110
        self.setFixedSize(380, 260)

        # Configuración de ventana flotante sin bordes y transparente
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._setup_ui()
        self._load_avatar()

        # Conectar señales internas
        self.state_changed.connect(self.set_state)
        self.subtitle_received.connect(self.show_subtitle_message)
        self.brain_badge_changed.connect(self.set_brain_badge)

        # Timer para animación de respiración / brillo (pulsing glow)
        self.glow_timer = QTimer(self)
        self.glow_timer.timeout.connect(self._animate_glow)
        self.glow_timer.start(50)

        # Ubicar en la esquina inferior derecha de la pantalla
        self._position_on_screen()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # Contenedor superior para el avatar y la etiqueta de estado
        top_container = QHBoxLayout()
        top_container.setSpacing(12)

        # Espacio reservado a la izquierda para el avatar pintado en paintEvent
        self.avatar_spacer = QWidget()
        self.avatar_spacer.setFixedSize(self.avatar_size, self.avatar_size)
        top_container.addWidget(self.avatar_spacer)

        # Panel de estado lateral
        self.info_container = QWidget()
        info_layout = QVBoxLayout(self.info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        info_layout.setSpacing(4)

        # Fila de Título con botón de ayuda [?]
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self.title_label = QLabel("PROYECTO F3NIX")
        self.title_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 13px; letter-spacing: 1px;")

        self.help_btn = QPushButton("?")
        self.help_btn.setFixedSize(18, 18)
        self.help_btn.setToolTip("¿Cómo usar a F3NIX? Ver guía de comandos y ejemplos")
        self.help_btn.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.15); color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.4); border-radius: 9px; font-weight: bold; font-size: 11px; padding: 0; }"
            "QPushButton:hover { background: #00E5FF; color: #000000; }"
        )
        self.help_btn.clicked.connect(self.open_quick_guide_requested.emit)

        # Botón 'Mira esto' (Visión de Pantalla en tiempo real con Moondream)
        self.vision_btn = QPushButton("👁️")
        self.vision_btn.setFixedSize(18, 18)
        self.vision_btn.setToolTip("Mira esto (Captura y analiza pantalla con Moondream / Ctrl+Alt+S)")
        self.vision_btn.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.15); color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.4); border-radius: 9px; font-size: 10px; padding: 0; }"
            "QPushButton:hover { background: #00E5FF; color: #000000; }"
        )
        self.vision_btn.clicked.connect(self.trigger_screen_analysis_requested.emit)

        # Botón de Tareas To-Do
        self.tasks_btn = QPushButton("✓ 0")
        self.tasks_btn.setFixedHeight(18)
        self.tasks_btn.setToolTip("Ver tareas pendientes del día")
        self.tasks_btn.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.15); color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.4); border-radius: 9px; font-size: 10px; font-weight: bold; padding: 0 5px; }"
            "QPushButton:hover { background: #00E5FF; color: #000000; }"
        )
        self.tasks_btn.clicked.connect(self.toggle_tasks_panel)

        self.studio_btn = QPushButton("🏛️")
        self.studio_btn.setFixedSize(20, 18)
        self.studio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.studio_btn.setToolTip("Abrir F3NIX Studio & Mesa Redonda (Workspace)")
        self.studio_btn.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.2); color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.6); border-radius: 9px; font-size: 11px; padding: 0; }"
            "QPushButton:hover { background: #00E5FF; color: #000000; }"
        )
        self.studio_btn.clicked.connect(self.toggle_studio_requested.emit)

        # Botón de Resumen de Audio (Videos/Reuniones)
        self.audio_summary_btn = QPushButton("🎧")
        self.audio_summary_btn.setFixedSize(18, 18)
        self.audio_summary_btn.setToolTip("Resumir audio del sistema (Videos / Reuniones)")
        self.audio_summary_btn.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.15); color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.4); border-radius: 9px; font-size: 10px; padding: 0; }"
            "QPushButton:hover { background: #00E5FF; color: #000000; }"
        )
        self.audio_summary_btn.clicked.connect(self.trigger_system_audio_summary_requested.emit)

        # Botón Modo Mini-Orbe Zen (🔮)
        self.mini_mode_btn = QPushButton("🔮")
        self.mini_mode_btn.setFixedSize(18, 18)
        self.mini_mode_btn.setToolTip("Modo Mini-Orbe Compacto (Zen)")
        self.mini_mode_btn.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.15); color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.4); border-radius: 9px; font-size: 10px; padding: 0; }"
            "QPushButton:hover { background: #00E5FF; color: #000000; }"
        )
        self.mini_mode_btn.clicked.connect(self.toggle_mini_mode)

        # Insignia de Cerebro Activo (Smart Router)
        self.brain_badge_label = QLabel("⚡")
        self.brain_badge_label.setToolTip("Cerebro activo (Smart Router)")
        self.brain_badge_label.setStyleSheet("font-size: 11px; padding: 0 2px;")

        # Botón para Cerrar F3NIX por completo
        self.close_app_btn = QPushButton("✕")
        self.close_app_btn.setFixedSize(18, 18)
        self.close_app_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_app_btn.setToolTip("Cerrar F3NIX por completo")
        self.close_app_btn.setStyleSheet(
            "QPushButton { background: rgba(255, 82, 82, 0.2); color: #FF5252; border: 1px solid rgba(255, 82, 82, 0.5); border-radius: 9px; font-weight: bold; font-size: 11px; padding: 0; }"
            "QPushButton:hover { background: #FF5252; color: #FFFFFF; border-color: #FF5252; }"
        )
        self.close_app_btn.clicked.connect(self.quit_requested.emit)

        title_row.addWidget(self.title_label)
        title_row.addWidget(self.help_btn)
        title_row.addWidget(self.vision_btn)
        title_row.addWidget(self.audio_summary_btn)
        title_row.addWidget(self.tasks_btn)
        title_row.addWidget(self.studio_btn)
        title_row.addWidget(self.mini_mode_btn)
        title_row.addWidget(self.brain_badge_label)
        title_row.addWidget(self.close_app_btn)

        title_row.addStretch()

        self.status_label = QLabel(STATE_LABELS["idle"])
        self.status_label.setStyleSheet(f"color: {STATE_COLORS['idle'].name()}; font-size: 12px; font-weight: 600;")

        self.hints_list = [
            "Mantén F12 para hablar",
            "💡 Doble clic en el avatar para abrir F3NIX Studio",
            "💡 Clic en [🏛️] para abrir Mesa Redonda y Studio",
            "💡 Clic en [✕] para cerrar el programa por completo",
            "💡 Clic derecho para ver todos los ajustes y opciones",
            "💡 Clic en [🔮] para activar Modo Mini-Orbe Zen",
            "💡 Di 'Dame mi reporte' para tu briefing matutino",
            "💡 Di 'Activa modo programación' o 'modo enfoque'",
            "💡 Di 'Qué ventana tengo abierta' para ver tu app actual",
            "💡 Di 'Historial de portapapeles' para ver tus copias"
        ]
        self.current_hint_idx = 0
        self.hint_label = QLabel(self.hints_list[0])
        self.hint_label.setStyleSheet("color: #00E5FF; font-size: 10px;")

        # Timer para rotar sugerencias útiles cada 6 segundos
        self.hint_timer = QTimer(self)
        self.hint_timer.timeout.connect(self._rotate_hint)
        self.hint_timer.start(6000)

        info_layout.addLayout(title_row)
        info_layout.addWidget(self.status_label)
        info_layout.addWidget(self.hint_label)
        top_container.addWidget(self.info_container)
        top_container.addStretch()

        layout.addLayout(top_container)

        # Tarjeta de subtítulos / texto inferior
        self.subtitle_box = QLabel("")
        self.subtitle_box.setWordWrap(True)
        self.subtitle_box.setStyleSheet(
            "background-color: rgba(18, 22, 34, 0.85);"
            "color: #F0F4F8;"
            "border: 1px solid rgba(255, 255, 255, 0.15);"
            "border-radius: 8px;"
            "padding: 8px 10px;"
            "font-size: 11px;"
        )
        self.subtitle_box.setMaximumHeight(70)
        self.subtitle_box.hide()
        layout.addWidget(self.subtitle_box)

        # Entrada de texto opcional para escribir o probar sin micrófono
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Escribe aquí o mantén F12...")
        self.text_input.setStyleSheet(
            "QLineEdit {"
            "  background-color: rgba(22, 27, 42, 0.9);"
            "  color: #FFFFFF;"
            "  border: 1px solid rgba(0, 229, 255, 0.3);"
            "  border-radius: 6px;"
            "  padding: 4px 8px;"
            "  font-size: 11px;"
            "}"
            "QLineEdit:focus {"
            "  border: 1px solid #00E5FF;"
            "}"
        )
        self.text_input.returnPressed.connect(self._on_text_submitted)
        layout.addWidget(self.text_input)

        # Panel desplegable de Tareas To-Do
        self.tasks_card = QWidget()
        self.tasks_card.setStyleSheet(
            "background-color: rgba(14, 18, 28, 0.95);"
            "border: 1px solid rgba(0, 229, 255, 0.35);"
            "border-radius: 8px;"
        )
        tasks_layout = QVBoxLayout(self.tasks_card)
        tasks_layout.setContentsMargins(8, 6, 8, 6)
        tasks_layout.setSpacing(4)

        t_header = QHBoxLayout()
        t_title = QLabel("TAREAS DEL DÍA")
        t_title.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 10px; letter-spacing: 1px;")
        t_header.addWidget(t_title)
        t_header.addStretch()

        clear_btn = QPushButton("Limpiar ✓")
        clear_btn.setStyleSheet("color: #8892B0; font-size: 10px; background: transparent; border: none; font-weight: bold;")
        clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear_btn.clicked.connect(self.clear_completed_tasks_requested.emit)
        t_header.addWidget(clear_btn)

        close_t_btn = QPushButton("✕")
        close_t_btn.setFixedSize(16, 16)
        close_t_btn.setStyleSheet("color: #AAAAAA; font-size: 10px; background: transparent; border: none;")
        close_t_btn.clicked.connect(self.toggle_tasks_panel)
        t_header.addWidget(close_t_btn)

        tasks_layout.addLayout(t_header)

        self.tasks_scroll = QScrollArea()
        self.tasks_scroll.setWidgetResizable(True)
        self.tasks_scroll.setStyleSheet("background: transparent; border: none;")
        self.tasks_scroll.setMaximumHeight(105)

        self.tasks_container = QWidget()
        self.tasks_container_layout = QVBoxLayout(self.tasks_container)
        self.tasks_container_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_container_layout.setSpacing(3)
        self.tasks_scroll.setWidget(self.tasks_container)
        tasks_layout.addWidget(self.tasks_scroll)

        self.new_task_input = QLineEdit()
        self.new_task_input.setPlaceholderText("+ Nueva tarea (Enter)...")
        self.new_task_input.setStyleSheet(
            "background: rgba(22, 27, 42, 0.9); color: #FFFFFF; border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 4px; padding: 2px 6px; font-size: 10px;"
        )
        self.new_task_input.returnPressed.connect(self._on_new_task_submitted)
        tasks_layout.addWidget(self.new_task_input)

        self.tasks_card.hide()
        layout.addWidget(self.tasks_card)

    def toggle_tasks_panel(self):
        """Muestra u oculta la tarjeta desplegable de tareas To-Do."""
        if self.tasks_card.isVisible():
            self.tasks_card.hide()
            self.setFixedSize(380, 260)
        else:
            self.tasks_card.show()
            self.setFixedSize(380, 420)

    def _on_new_task_submitted(self):
        txt = self.new_task_input.text().strip()
        if txt:
            self.new_task_input.clear()
            self.task_added.emit(txt)

    def update_tasks(self, tasks_list):
        """Actualiza la lista visual de tareas y el contador del botón."""
        # Limpiar widgets previos
        while self.tasks_container_layout.count():
            item = self.tasks_container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        active_count = 0
        for task in tasks_list:
            t_id = task.get("id", "")
            t_text = task.get("text", "")
            is_done = task.get("done", False)
            if not is_done:
                active_count += 1

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            cb = QCheckBox(t_text)
            cb.setChecked(is_done)
            style = "color: #8892B0; text-decoration: line-through; font-size: 10px;" if is_done else "color: #FFFFFF; font-size: 10px;"
            cb.setStyleSheet(f"QCheckBox {{ {style} }}")
            cb.toggled.connect(lambda checked, tid=t_id: self.task_toggled.emit(tid))
            row_layout.addWidget(cb)
            row_layout.addStretch()

            del_btn = QPushButton("×")
            del_btn.setFixedSize(14, 14)
            del_btn.setStyleSheet("color: #FF2E63; background: transparent; border: none; font-size: 12px; font-weight: bold;")
            del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            del_btn.clicked.connect(lambda _, tid=t_id: self.task_deleted.emit(tid))
            row_layout.addWidget(del_btn)

            self.tasks_container_layout.addWidget(row)

        self.tasks_container_layout.addStretch()
        self.tasks_btn.setText(f"✓ {active_count}")

    def set_brain_badge(self, badge: str):
        """Actualiza la insignia del cerebro activo en el HUD."""
        icon_map = {
            "Código": "💻",
            "Razonamiento": "🧠",
            "Abogado": "⚖️",
            "Steelman": "⚖️",
            "Planificador": "🎯",
            "Visión": "👁️",
            "Turbo": "⚡",
            "Ágil": "⚡",
            "Sistema": "⚙️",
            "Instantáneo": "⚡",
            "Briefing": "☀️",
            "Rutinas": "🚀",
            "Portapapeles": "📋",
            "Zen": "🔮"
        }
        icon = "⚡"
        for k, v in icon_map.items():
            if k in badge:
                icon = v
                break
        self.brain_badge_label.setText(icon)
        self.brain_badge_label.setToolTip(f"Cerebro: {badge}")

    def _on_text_submitted(self):
        txt = self.text_input.text().strip()
        if txt:
            self.text_input.clear()
            self.text_submitted.emit(txt)

    def _resolve_image_path(self, path: str) -> str:
        """Resuelve la ruta absoluta del archivo de imagen asegurando soporte para PyInstaller (_internal / sys._MEIPASS)."""
        if not path:
            return ""
        if os.path.isabs(path) and os.path.exists(path):
            return path
        # 1. Chequeo de bundle PyInstaller
        if hasattr(sys, "_MEIPASS"):
            p = os.path.join(sys._MEIPASS, path)
            if os.path.exists(p):
                return p
            p_int = os.path.join(sys._MEIPASS, "_internal", path)
            if os.path.exists(p_int):
                return p_int

        # 2. Directorio del ejecutable o script
        exe_dir = os.path.dirname(sys.executable)
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        for base in [
            exe_dir,
            os.path.join(exe_dir, "_internal"),
            os.getcwd(),
            os.path.join(os.getcwd(), "_internal"),
            curr_dir,
            os.path.abspath(os.path.join(curr_dir, "..")),
            os.path.abspath(os.path.join(curr_dir, "..", "_internal")),
            os.path.abspath(os.path.join(curr_dir, "..", "release", "F3NIX")),
            os.path.abspath(os.path.join(curr_dir, "..", "release", "F3NIX", "_internal")),
            os.path.abspath(os.path.join(curr_dir, "..", "dist", "F3NIX")),
            os.path.abspath(os.path.join(curr_dir, "..", "dist", "F3NIX", "_internal")),
        ]:
            cand = os.path.join(base, path)
            if os.path.exists(cand):
                return os.path.abspath(cand)
        return path

    def _load_avatar(self):
        self.avatar_pixmap = None
        real_path = self._resolve_image_path(self.avatar_path)
        if real_path and os.path.exists(real_path):
            pix = QPixmap(real_path)
            if not pix.isNull():
                self.avatar_pixmap = pix.scaled(
                    self.avatar_size, self.avatar_size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )

    def _position_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            x = rect.right() - self.width() - 30
            y = rect.bottom() - self.height() - 40
            self.move(x, y)

    def restore_position(self, x=None, y=None):
        """Restaura la posición guardada en pantalla comprobando que sea visible en algún monitor activo."""
        if x is not None and y is not None:
            point = QPoint(int(x), int(y))
            for screen in QApplication.screens():
                if screen.availableGeometry().contains(point):
                    self.move(int(x), int(y))
                    return
        self._position_on_screen()

    def _animate_glow(self):
        self.glow_radius += self.glow_step
        if self.glow_radius > 16.0:
            self.glow_radius = 16.0
            self.glow_step = -0.5
        elif self.glow_radius < 8.0:
            self.glow_radius = 8.0
            self.glow_step = 0.5
        self.update()

    def get_state_color(self, state: str) -> QColor:
        colors = getattr(self, "state_colors", STATE_COLORS)
        return colors.get(state, colors.get("idle", STATE_COLORS["idle"]))

    def apply_skin(self, skin_key: str):
        """Aplica un tema visual / skin al HUD, orbe y animaciones del Avatar."""
        if skin_key not in AVATAR_THEMES:
            skin_key = "cyberpunk"
        self.current_skin = skin_key
        theme = AVATAR_THEMES[skin_key]
        self.state_colors = dict(theme["colors"])
        accent = theme["accent"]

        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {accent}; letter-spacing: 1px;")
        if hasattr(self, "status_label"):
            self.status_label.setStyleSheet(f"color: {self.get_state_color(self.current_state).name()}; font-size: 12px; font-weight: 600;")
        self.skin_changed.emit(skin_key)
        self.update()

    def set_avatar_image(self, image_path: str):
        """Cambia dinámicamente la imagen visual del avatar."""
        if image_path and os.path.exists(image_path):
            self.avatar_path = image_path
            self._load_avatar()
            self.avatar_image_changed.emit(image_path)
            self.update()

    @pyqtSlot(str)
    def set_state(self, state: str):
        if state in STATE_LABELS or state in STATE_COLORS:
            self.current_state = state
            color = self.get_state_color(state).name()
            self.status_label.setText(STATE_LABELS.get(state, state))
            self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
            self.update()

    @pyqtSlot(str, str)
    def show_subtitle_message(self, sender: str, message: str):
        if not self.show_subtitles or not message.strip():
            return
        
        # Limitar longitud visible en la tarjeta rápida
        display_text = message.strip()
        if len(display_text) > 160:
            display_text = display_text[:157] + "..."
            
        prefix = f"<b>{sender}:</b> " if sender else ""
        self.subtitle_box.setText(f"{prefix}{display_text}")
        self.subtitle_box.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Kill-Switch: Clic sobre el avatar interrumpe inmediatamente el habla o pensamiento
            if self.current_state in ["speaking", "thinking", "alarm"]:
                self.interrupt_requested.emit()
                event.accept()
                return

            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_start_pos = self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, "_drag_start_pos") and self._drag_start_pos != self.pos():
                self.position_changed.emit(self.x(), self.y())
            event.accept()

    def dragEnterEvent(self, event):
        """Permite arrastrar archivos sobre el HUD."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.show_subtitle_message("F3nix", "Suelta el archivo aquí para analizarlo...")

    def dropEvent(self, event):
        """Procesa el archivo soltado sobre el HUD."""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path and os.path.exists(file_path):
                self.file_dropped.emit(file_path)
                event.acceptProposedAction()
                break

    def toggle_mini_mode(self):
        """Alterna entre el modo HUD extendido y el modo Mini-Orbe Zen preservando la posición en pantalla."""
        self.is_mini_mode = not getattr(self, "is_mini_mode", False)
        curr_x, curr_y = self.x(), self.y()
        if self.is_mini_mode:
            self.info_container.hide()
            self.subtitle_box.hide()
            self.text_input.hide()
            self.tasks_card.hide()
            self.setFixedSize(self.avatar_size + 30, self.avatar_size + 30)
            self.setToolTip("F3NIX (Modo Mini-Orbe Zen)\n• Clic para interrumpir\n• Doble clic para expandir\n• Mantén F12 para hablar")
        else:
            self.setFixedSize(380, 260)
            self.info_container.show()
            self.text_input.show()
            self.setToolTip("")
        self.move(curr_x, curr_y)
        self.position_changed.emit(self.x(), self.y())
        self.update()

    def mouseDoubleClickEvent(self, event):
        """Doble clic sobre el avatar abre F3NIX Studio / Mesa Redonda o restaura modo Mini-Orbe."""
        if getattr(self, "is_mini_mode", False):
            self.toggle_mini_mode()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_studio_requested.emit()
            event.accept()

    def _rotate_hint(self):
        """Rota periódicamente los consejos de uso en el HUD."""
        if self.current_state == "idle" and self.hints_list:
            self.current_hint_idx = (self.current_hint_idx + 1) % len(self.hints_list)
            self.hint_label.setText(self.hints_list[self.current_hint_idx])

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1A1E29; color: #FFFFFF; border: 1px solid #2E384D; padding: 4px; border-radius: 6px; }"
            "QMenu::item { padding: 6px 20px; border-radius: 4px; }"
            "QMenu::item:selected { background-color: #00E5FF; color: #000000; font-weight: bold; }"
        )

        title_act = menu.addAction("⚡ SISTEMA F3NIX AI")
        title_act.setEnabled(False)
        menu.addSeparator()

        # F3NIX Studio (Hermes Desktop Workspace)
        studio_act = menu.addAction("🏛️ Abrir F3NIX Studio / Mesa Redonda")
        launcher_act = menu.addAction("🔍 Barra Rápida Global (Alt + F)")
        mini_act = menu.addAction("🔮 Modo Mini-Orbe Zen" if not getattr(self, "is_mini_mode", False) else "🔮 Expandir HUD Completo")
        is_turbo = getattr(self, "turbo_mode", True)
        turbo_act = menu.addAction("⚡ Modo Turbo: Activo (5-10s)" if is_turbo else "⚡ Activar Modo Turbo (5-10s)")

        # Guía Rápida visual para no tener que adivinar comandos
        guide_act = menu.addAction("📖 ¿Cómo usar a F3NIX? (Guía de Superpoderes)")

        # Centro de Comando de Habilidades
        cmd_deck_act = menu.addAction("⚡ Centro de Comando (Habilidades y Casos de Uso)")

        # Actualizar lista de modelos instalados en vivo desde Ollama
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=1.5)
            if r.status_code == 200:
                self.available_models = [m.get("name", "") for m in r.json().get("models", [])]
        except Exception:
            pass

        # Submenú dinámico de modelos de IA
        model_menu = menu.addMenu("🧠 Cambiar Cerebro / Modelo")
        model_menu.setStyleSheet(menu.styleSheet())
        model_actions = {}
        if self.available_models:
            for m in self.available_models:
                display_name = f"✓  {m}" if m == self.active_model else f"    {m}"
                act = model_menu.addAction(display_name)
                model_actions[act] = m
        else:
            act_empty = model_menu.addAction("(Buscando modelos...)")
            act_empty.setEnabled(False)

        # Tienda / Centro de descargas visual
        download_store_act = menu.addAction("📥 Instalar Nuevos Cerebros (Hermes, Qwen...)")
        doctor_act = menu.addAction("🩺 Doctor F3NIX (Diagnóstico y Salud)")

        # Submenú de Voces TTS
        voice_menu = menu.addMenu("🔊 Voz del Asistente")
        voice_menu.setStyleSheet(menu.styleSheet())
        voice_actions = {}
        voices_catalog = {
            "es-MX-JorgeNeural": "Jorge (México - Masculino)",
            "es-ES-AlvaroNeural": "Álvaro (España - Masculino)",
            "es-ES-ElviraNeural": "Elvira (España - Femenino)",
            "es-MX-DaliaNeural": "Dalia (México - Femenino)"
        }
        for v_id, v_label in voices_catalog.items():
            disp = f"✓  {v_label}" if v_id == self.current_voice else f"    {v_label}"
            v_act = voice_menu.addAction(disp)
            voice_actions[v_act] = v_id

        # Submenú de Skins y Personalización Visual
        skin_menu = menu.addMenu("🎨 Skins & Apariencia")
        skin_menu.setStyleSheet(menu.styleSheet())
        skin_actions = {}
        for s_key, s_data in AVATAR_THEMES.items():
            disp = f"✓  {s_data['name']}" if s_key == getattr(self, "current_skin", "cyberpunk") else f"    {s_data['name']}"
            s_act = skin_menu.addAction(disp)
            skin_actions[s_act] = s_key
        skin_menu.addSeparator()
        change_avatar_img_act = skin_menu.addAction("🖼️ Cambiar Imagen de Avatar...")

        # Modo Manos Libres continuo
        is_hf = getattr(self, "hands_free_active", False)
        hf_act = menu.addAction("🎙️ Modo Manos Libres: ACTIVO (Sin F12)" if is_hf else "🎙️ Activar Modo Manos Libres (Sin F12)")

        menu.addSeparator()
        clip_act = menu.addAction("📋 Analizar Portapapeles (Ctrl+C actual)")
        toggle_sub_act = menu.addAction("Ocultar Subtítulos" if self.show_subtitles else "Mostrar Subtítulos")
        clear_hist_act = menu.addAction("Reiniciar Conversación")
        menu.addSeparator()

        quit_act = menu.addAction("❌ Cerrar F3NIX (Salir por completo)")

        action = menu.exec(QCursor.pos())

        if action in model_actions:
            selected_model = model_actions[action]
            self.active_model = selected_model
            self.model_change_requested.emit(selected_model)
            self.show_subtitle_message("Sistema", f"Modelo cambiado a: {selected_model}")
        elif action in voice_actions:
            v_id = voice_actions[action]
            self.current_voice = v_id
            self.voice_change_requested.emit(v_id)
            self.show_subtitle_message("Sistema", f"Voz cambiada a: {voices_catalog[v_id]}")
        elif action in skin_actions:
            chosen_skin = skin_actions[action]
            self.apply_skin(chosen_skin)
            self.show_subtitle_message("Sistema", f"Skin aplicado: {AVATAR_THEMES[chosen_skin]['name']}")
        elif action == change_avatar_img_act:
            from PyQt6.QtWidgets import QFileDialog
            fpath, _ = QFileDialog.getOpenFileName(
                self,
                "Seleccionar Imagen para el Avatar",
                "",
                "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp *.ico)"
            )
            if fpath:
                self.set_avatar_image(fpath)
                self.show_subtitle_message("Sistema", "Imagen de avatar actualizada")
        elif action == hf_act:
            new_hf = not getattr(self, "hands_free_active", False)
            self.hands_free_active = new_hf
            self.hands_free_toggled.emit(new_hf)
            msg = "🎙️ Manos Libres ACTIVADO: habla directamente sin presionar F12" if new_hf else "🎙️ Manos Libres DESACTIVADO: mantén F12 para hablar"
            self.show_subtitle_message("Sistema", msg)
        elif action == studio_act:
            self.toggle_studio_requested.emit()
        elif action == mini_act:
            self.toggle_mini_mode()
        elif action == launcher_act:
            self.toggle_quick_launcher_requested.emit()
        elif action == turbo_act:
            self.turbo_mode = not getattr(self, "turbo_mode", True)
            self.toggle_turbo_requested.emit()
            self.show_subtitle_message("Sistema", f"Modo Turbo {'activado (5-10s)' if self.turbo_mode else 'desactivado (Reflexión)'}")
        elif action == guide_act:
            self.open_quick_guide_requested.emit()
        elif action == cmd_deck_act:
            self.open_command_deck_requested.emit()
        elif action == download_store_act:
            self.open_model_store_requested.emit()
        elif action == doctor_act:
            self.open_doctor_requested.emit()
        elif action == clip_act:
            self.analyze_clipboard_requested.emit()
        elif action == toggle_sub_act:
            self.show_subtitles = not self.show_subtitles
            if not self.show_subtitles:
                self.subtitle_box.hide()
        elif action == clear_hist_act:
            self.clear_history_requested.emit()
            self.show_subtitle_message("Sistema", "Memoria de conversación reiniciada.")
        elif action == quit_act:
            self.quit_requested.emit()
            self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = 15 + self.avatar_size / 2.0
        center_y = 15 + self.avatar_size / 2.0
        radius = (self.avatar_size - 16) / 2.0

        state_color = self.get_state_color(self.current_state)

        # 1. Resplandor exterior (Glow ring)
        glow_grad = QRadialGradient(center_x, center_y, radius + self.glow_radius)
        glow_grad.setColorAt(0.0, QColor(state_color.red(), state_color.green(), state_color.blue(), 180))
        glow_grad.setColorAt(0.8, QColor(state_color.red(), state_color.green(), state_color.blue(), 60))
        glow_grad.setColorAt(1.0, QColor(state_color.red(), state_color.green(), state_color.blue(), 0))
        painter.setBrush(QBrush(glow_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(int(center_x), int(center_y)), int(radius + self.glow_radius), int(radius + self.glow_radius))

        # 2. Borde circular principal
        pen = QPen(state_color, 3.5)
        painter.setPen(pen)
        painter.setBrush(QColor(15, 18, 28))
        painter.drawEllipse(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2))

        # 3. Dibujar avatar circular recortado o icono estilizado de F3nix
        clip_path = QPainterPath()
        clip_path.addEllipse(QRectF(center_x - radius + 2, center_y - radius + 2, (radius - 2) * 2, (radius - 2) * 2))
        painter.save()
        painter.setClipPath(clip_path)

        if self.avatar_pixmap and not self.avatar_pixmap.isNull():
            target_rect = QRectF(center_x - radius + 2, center_y - radius + 2, (radius - 2) * 2, (radius - 2) * 2)
            painter.drawPixmap(target_rect.toRect(), self.avatar_pixmap)
        else:
            # Renderizado de respaldo estilizado: Fénix neón con degradado
            gradient = QLinearGradient(center_x - radius, center_y - radius, center_x + radius, center_y + radius)
            gradient.setColorAt(0.0, QColor(255, 94, 0))
            gradient.setColorAt(0.5, QColor(255, 0, 128))
            gradient.setColorAt(1.0, QColor(102, 0, 255))
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(QRectF(center_x - radius + 2, center_y - radius + 2, (radius - 2) * 2, (radius - 2) * 2))

            painter.setPen(QColor(255, 255, 255))
            font = QFont("Segoe UI", 24, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2), Qt.AlignmentFlag.AlignCenter, "F3")

        painter.restore()
