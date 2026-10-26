import os
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QGridLayout
)

CATEGORIES = [
    {
        "category": "⚡ SUPERPODERES Y BÚSQUEDA LOCAL",
        "color": "#10B981",
        "actions": [
            {
                "title": "🎧 Resumir Audio de Video / Reunión",
                "desc": "Graba 20s del audio que suena en tu PC y genera un resumen en 3 viñetas.",
                "prompt": "resume el video"
            },
            {
                "title": "🔎 Buscar Archivo en Discos",
                "desc": "Localiza al instante cualquier documento o proyecto en tus discos C: y D:.",
                "prompt": "busca el archivo notas.txt"
            },
            {
                "title": "✨ Copiloto Flotante (Ctrl+Alt+C)",
                "desc": "Selecciona cualquier texto en Windows y presiona Ctrl + Alt + C para ver el menú flotante.",
                "prompt": "cómo uso el copiloto flotante"
            }
        ]
    },
    {
        "category": "💻 ASISTENTE DE CÓDIGO & DESARROLLO (Qwen / Llama)",
        "color": "#00E5FF",
        "actions": [
            {
                "title": "🔍 Explicar Código / Error",
                "desc": "Analiza la lógica o excepción que tienes copiada con Ctrl+C.",
                "prompt": "Explica detalladamente qué hace el código o por qué ocurre el error que tengo en el portapapeles."
            },
            {
                "title": "⚡ Optimizar y Refactorizar",
                "desc": "Mejora el rendimiento, legibilidad y estándares PEP8/clean code.",
                "prompt": "Optimiza y refactoriza el código que tengo copiado en el portapapeles para máxima eficiencia y legibilidad."
            },
            {
                "title": "🧪 Generar Tests Unitarios",
                "desc": "Crea casos de prueba (pytest/unittest) para la función copiada.",
                "prompt": "Genera una suite completa de pruebas unitarias con pytest para el código copiado en el portapapeles."
            },
            {
                "title": "📝 Documentar Código (Docstrings)",
                "desc": "Añade documentación clara de parámetros, retornos y ejemplos.",
                "prompt": "Agrega docstrings y comentarios claros explicando cada parámetro y retorno del código en el portapapeles."
            }
        ]
    },
    {
        "category": "🦾 CONTROL Y TELEMETRÍA DE SISTEMA (Hermes 3 / F3nix)",
        "color": "#FFB703",
        "actions": [
            {
                "title": "🖥️ Diagnóstico de Recursos PC",
                "desc": "Consulta el uso en tiempo real de CPU, memoria RAM y batería.",
                "prompt": "Cómo está el sistema"
            },
            {
                "title": "🚀 Abrir Entorno de Trabajo",
                "desc": "Lanza VS Code de inmediato para comenzar a programar.",
                "prompt": "Abre vscode"
            },
            {
                "title": "🕒 Hora y Calendario",
                "desc": "Verifica la hora precisa y fecha actual del sistema.",
                "prompt": "Qué hora es"
            },
            {
                "title": "🌐 Abrir Navegador Web",
                "desc": "Inicia Chrome o Edge para investigar o navegar.",
                "prompt": "Abre el navegador"
            }
        ]
    },
    {
        "category": "✍️ PRODUCTIVIDAD & ANÁLISIS DE DATOS",
        "color": "#FF2E63",
        "actions": [
            {
                "title": "📄 Resumen Ejecutivo Ultrarrápido",
                "desc": "Extrae los puntos clave de un correo, artículo o reporte copiado.",
                "prompt": "Resume en 3 a 5 puntos clave el texto que tengo copiado en el portapapeles."
            },
            {
                "title": "🌐 Traducir a Inglés Técnico",
                "desc": "Traduce con terminología precisa de desarrollo y negocios.",
                "prompt": "Traduce al inglés técnico el contenido copiado en el portapapeles con tono profesional."
            },
            {
                "title": "💡 Lluvia de Ideas / Pitch",
                "desc": "Genera 5 propuestas creativas para resolver un desafío o proyecto.",
                "prompt": "Dame 5 ideas innovadoras y viables para potenciar el proyecto que tengo en el portapapeles."
            },
            {
                "title": "✉️ Redactar Correo Profesional",
                "desc": "Convierte notas rápidas copiadas en un email formal impecable.",
                "prompt": "Redacta un correo electrónico profesional y persuasivo basado en las notas del portapapeles."
            }
        ]
    },
    {
        "category": "🎓 MODO TUTOR Y APRENDIZAJE ACELERADO",
        "color": "#A78BFA",
        "actions": [
            {
                "title": "🧒 Explicar como si tuviera 10 años",
                "desc": "Analogías simples y sin tecnicismos confusos.",
                "prompt": "Explícame de forma muy simple y con una analogía divertida el concepto que copié en el portapapeles."
            },
            {
                "title": "🗺️ Hoja de Ruta de Aprendizaje",
                "desc": "Paso a paso para dominar una tecnología o framework.",
                "prompt": "Crea una hoja de ruta paso a paso de 4 semanas para dominar el tema del portapapeles."
            }
        ]
    }
]

class CommandDeckDialog(QDialog):
    """
    Panel de Control y Casos de Uso rápidos para Proyecto F3nix.
    Permite activar cualquier habilidad de IA con un solo clic.
    """
    action_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("F3NIX - Centro de Comando y Habilidades IA")
        self.setFixedSize(680, 650)
        self.setStyleSheet("""
            QDialog {
                background-color: #0D111A;
                color: #FFFFFF;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #FFFFFF;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #141A29;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #00E5FF;
                border-radius: 4px;
                min-height: 20px;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # Header
        title = QLabel("⚡ Centro de Comando y Casos de Uso")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00E5FF;")
        subtitle = QLabel("Haz clic en cualquier habilidad para que F3nix la ejecute de inmediato con tu IA local.")
        subtitle.setStyleSheet("font-size: 12px; color: #8F9CAE;")

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        # Scroll Area con categorías
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        categories_layout = QVBoxLayout(content_widget)
        categories_layout.setSpacing(16)

        for cat in CATEGORIES:
            cat_label = QLabel(cat["category"])
            cat_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {cat['color']}; margin-top: 6px;")
            categories_layout.addWidget(cat_label)

            grid = QGridLayout()
            grid.setSpacing(10)

            for idx, act in enumerate(cat["actions"]):
                row = idx // 2
                col = idx % 2
                btn = self._create_action_card(act, cat["color"])
                grid.addWidget(btn, row, col)

            categories_layout.addLayout(grid)

        categories_layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # Botón cerrar
        btn_close = QPushButton("Cerrar Centro de Comando")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #1A2133;
                color: #A0B2C6;
                border: 1px solid #2C3852;
                padding: 8px 18px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #26314D;
                color: white;
            }
        """)
        btn_close.clicked.connect(self.close)
        main_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _create_action_card(self, act, border_color) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #151B28;
                border: 1px solid #242E42;
                border-radius: 8px;
                padding: 10px;
            }}
            QFrame:hover {{
                border: 1px solid {border_color};
                background-color: #1B2335;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title_btn = QPushButton(act["title"])
        title_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: bold;
                color: #FFFFFF;
                padding: 0;
            }
            QPushButton:hover {
                color: #00E5FF;
            }
        """)

        desc_lbl = QLabel(act["desc"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 11px; color: #8F9CAE;")

        layout.addWidget(title_btn)
        layout.addWidget(desc_lbl)

        # Hacer clic en la tarjeta o en el título activa la acción
        title_btn.clicked.connect(lambda _, p=act["prompt"]: self._execute_action(p))

        return frame

    def _execute_action(self, prompt: str):
        self.action_triggered.emit(prompt)
        self.close()
