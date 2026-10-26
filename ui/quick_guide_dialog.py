from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QGridLayout
)

GUIDE_SECTIONS = [
    {
        "icon": "☀️",
        "title": "Briefing Ejecutivo del Día",
        "desc": "Resumen matutino ejecutivo con estado de salud de tu PC, hora y tus tareas prioritarias.",
        "examples": [
            "\"Dame mi reporte\"",
            "\"Buenos días F3nix\"",
            "\"¿Cómo pinta el día?\""
        ],
        "color": "#F59E0B"
    },
    {
        "icon": "🚀",
        "title": "Rutinas y Macros Operativas",
        "desc": "Ejecuta combos de acciones por voz: abre herramientas, inicia pomodoro y configura volumen.",
        "examples": [
            "\"Activa modo programación\" (VS Code + Pomodoro 45m + Turbo)",
            "\"Activa modo enfoque\" (Volumen bajo + 25m concentración)",
            "\"Cierra mi jornada\" (Archiva tareas completadas y balance)"
        ],
        "color": "#10B981"
    },
    {
        "icon": "🪟",
        "title": "Conciencia de Ventana Activa",
        "desc": "F3NIX sabe qué aplicación tienes en primer plano en <0.1ms sin consumir CPU en capturas.",
        "examples": [
            "\"¿Qué atajo uso aquí?\"",
            "\"¿Qué ventana tengo abierta?\"",
            "\"Explica el error en este programa\""
        ],
        "color": "#3B82F6"
    },
    {
        "icon": "🔮",
        "title": "Modo Mini-Orbe Zen & Bandeja de Sistema",
        "desc": "Contrae el HUD a un orbe mínimo con [🔮] o doble clic para no tapar ventanas mientras trabajas.",
        "examples": [
            "Clic en [🔮] en la cabecera del avatar",
            "Doble clic para alternar entre orbe y HUD completo",
            "Icono en la bandeja junto al reloj de Windows"
        ],
        "color": "#8B5CF6"
    },
    {
        "icon": "✨",
        "title": "Copiloto Flotante de Selección (Ctrl+Alt+C)",
        "desc": "Selecciona cualquier texto o código en Windows y pulsa Ctrl + Alt + C para desplegar el menú contextual flotante.",
        "examples": [
            "\"💡 Explicar texto o código seleccionado\"",
            "\"🌐 Traducir al instante\"",
            "\"🛠️ Corregir ortografía y estilo\"",
            "\"📋 Resumir en puntos clave\""
        ],
        "color": "#00E5FF"
    },
    {
        "icon": "🔎",
        "title": "Buscador Local Universal",
        "desc": "Encuentra y abre cualquier archivo o carpeta en tus discos C: y D: al instante.",
        "examples": [
            "\"Busca el archivo notas.txt\"",
            "\"¿Dónde guardé el informe trimestral?\"",
            "\"Abre el archivo proyecto_final.py\""
        ],
        "color": "#06B6D4"
    },
    {
        "icon": "🎧",
        "title": "Resumen de Audio (Videos / Reuniones)",
        "desc": "Captura el audio que suena en tu PC (YouTube, conferencias, podcasts) y te da un resumen en 3 viñetas.",
        "examples": [
            "\"Resume el video\"",
            "\"Resume la reunión\"",
            "Tocar el botón 🎧 en el avatar"
        ],
        "color": "#A855F7"
    },
    {
        "icon": "📋",
        "title": "Portapapeles Inteligente",
        "desc": "Copia cualquier código, texto o error en Windows con Ctrl+C y luego mantén F12.",
        "examples": [
            "\"Explica lo que acabo de copiar\"",
            "\"¿Por qué ocurre este error?\"",
            "\"Optimiza esta función\"",
            "\"Traduce este texto al inglés\""
        ],
        "color": "#00E5FF"
    },
    {
        "icon": "📁",
        "title": "Arrastrar Archivos (Drag & Drop)",
        "desc": "Toma un archivo (.py, .txt, .json, .csv, .md, etc.) de tu explorador y suéltalo sobre el avatar.",
        "examples": [
            "\"Resume el archivo que te pasé\"",
            "\"Encuentra bugs en este script\"",
            "\"¿Cuáles son las conclusiones del documento?\""
        ],
        "color": "#10B981"
    },
    {
        "icon": "🌐",
        "title": "Búsqueda Web en Vivo",
        "desc": "Pregunta sobre noticias, precios o eventos actuales sin costo gracias a DuckDuckGo.",
        "examples": [
            "\"Busca en internet el precio de Bitcoin hoy\"",
            "\"¿Quién ganó el partido de la Champions anoche?\"",
            "\"Últimas noticias de inteligencia artificial\""
        ],
        "color": "#3B82F6"
    },
    {
        "icon": "⏰",
        "title": "Temporizadores y Pomodoro",
        "desc": "F3nix medirá el tiempo y te avisará por voz y con alarma visual cuando termine.",
        "examples": [
            "\"Pon un pomodoro de 25 minutos\"",
            "\"Avísame en 10 minutos para revisar el horno\"",
            "\"Alarma de 5 minutos\""
        ],
        "color": "#F59E0B"
    },
    {
        "icon": "✍️",
        "title": "Dictado Mágico al Cursor",
        "desc": "Deja el cursor en Word, WhatsApp, Discord o VS Code y dicta lo que necesitas.",
        "examples": [
            "\"Escribe: Hola equipo, confirmo la reunión de mañana.\"",
            "\"Dicta: una respuesta formal disculpando la demora.\""
        ],
        "color": "#EC4899"
    },
    {
        "icon": "🖥️",
        "title": "Control del Sistema y Telemetría",
        "desc": "Diagnóstico de hardware y apertura de aplicaciones por voz.",
        "examples": [
            "\"¿Cómo está el sistema?\" (CPU, RAM, batería)",
            "\"Abre VS Code\" o \"Abre el navegador\"",
            "\"¿Qué hora es?\""
        ],
        "color": "#8B5CF6"
    }
]

class QuickGuideDialog(QDialog):
    """
    Guía interactiva y visual para que ningún usuario tenga que adivinar cómo usar F3NIX.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("F3NIX - Guía Rápida de Comandos y Superpoderes")
        self.setFixedSize(660, 620)
        self.setStyleSheet("""
            QDialog {
                background-color: #0F131D;
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
                background: #161B29;
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
        title = QLabel("📖 ¿Cómo usar a F3NIX? (Guía de Superpoderes)")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00E5FF;")
        subtitle = QLabel("Aquí tienes todo lo que puedes pedirle a tu asistente. ¡Sin adivinanzas!")
        subtitle.setStyleSheet("font-size: 12px; color: #8F9CAE;")

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        cards_layout = QVBoxLayout(content_widget)
        cards_layout.setSpacing(12)

        for sec in GUIDE_SECTIONS:
            card = self._create_guide_card(sec)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # Footer
        footer_layout = QHBoxLayout()
        hint = QLabel("💡 <b>Atajo:</b> Mantén <b>F12</b> para hablar o escribe en el cuadro inferior del HUD.")
        hint.setStyleSheet("font-size: 11px; color: #A0B2C6;")

        btn_close = QPushButton("¡Entendido!")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #00E5FF;
                color: #000000;
                font-weight: bold;
                border: none;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #38EDFF;
            }
        """)
        btn_close.clicked.connect(self.close)

        footer_layout.addWidget(hint)
        footer_layout.addStretch()
        footer_layout.addWidget(btn_close)
        main_layout.addLayout(footer_layout)

    def _create_guide_card(self, sec) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #161B29;
                border: 1px solid #242E44;
                border-radius: 10px;
                padding: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {sec['color']};
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setSpacing(6)

        # Fila superior
        top_row = QHBoxLayout()
        title_lbl = QLabel(f"{sec['icon']} {sec['title']}")
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {sec['color']};")
        top_row.addWidget(title_lbl)
        top_row.addStretch()

        desc_lbl = QLabel(sec["desc"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 11px; color: #BAC7D5;")

        # Ejemplos de voz
        ex_container = QWidget()
        ex_layout = QVBoxLayout(ex_container)
        ex_layout.setContentsMargins(0, 4, 0, 0)
        ex_layout.setSpacing(3)

        ex_title = QLabel("Ejemplos que puedes decir con F12:")
        ex_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #8F9CAE;")
        ex_layout.addWidget(ex_title)

        for ex in sec["examples"]:
            item_lbl = QLabel(f"  • {ex}")
            item_lbl.setStyleSheet("font-size: 11px; color: #E2E8F0; font-family: monospace;")
            ex_layout.addWidget(item_lbl)

        layout.addLayout(top_row)
        layout.addWidget(desc_lbl)
        layout.addWidget(ex_container)

        return frame
