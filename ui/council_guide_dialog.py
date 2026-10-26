from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame
)

class CouncilGuideDialog(QDialog):
    """
    Ventana interactiva de ayuda para la Mesa Redonda Multi-IA.
    Explica la diversidad cognitiva, qué modelo elegir para cada rol y por qué,
    con combos recomendados para economía, software y finanzas.
    """
    open_store_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🏛️ Guía Estratégica: ¿Qué IAs elegir para la Mesa Redonda y por qué?")
        self.resize(780, 640)
        self.setMinimumSize(680, 520)
        self._apply_theme()
        self._init_ui()

    def _apply_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0D111A;
            }
            QWidget {
                color: #ECEFF4;
                font-family: 'Segoe UI', sans-serif;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
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
            QPushButton {
                background-color: #1E2738;
                color: #ECEFF4;
                border: 1px solid #2E3B52;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #29354C;
                border: 1px solid #00E5FF;
                color: #00E5FF;
            }
            QPushButton.primary {
                background-color: #00B8D4;
                color: #000000;
                font-weight: bold;
                border: 1px solid #00E5FF;
            }
            QPushButton.primary:hover {
                background-color: #00E5FF;
            }
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 16)
        main_layout.setSpacing(12)

        # Header superior
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        icon_lbl = QLabel("🏛️")
        icon_lbl.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("GUÍA DE MODELOS Y ROLES MULTI-IA")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #00E5FF; letter-spacing: 1px;")
        sub_lbl = QLabel("Aprende a combinar cerebros con personalidades opuestas para validar proyectos reales sin sesgos.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #8C99B2;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Contenido scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(0, 4, 10, 8)
        content_layout.setSpacing(14)

        # 1. Tarjeta: La Regla de Oro
        rule_box = QFrame()
        rule_box.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #101E33, stop:1 #171E2D);
                border: 1px solid #00E5FF;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        rule_lay = QVBoxLayout(rule_box)
        rule_lay.setSpacing(6)
        rule_title = QLabel("⚡ La Regla de Oro: Diversidad Cognitiva")
        rule_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #00E5FF;")
        rule_desc = QLabel(
            "Si colocas el mismo modelo en los 3 roles, no habrá un debate real: ambos tendrán los mismos sesgos y se darán la razón. "
            "La verdadera potencia ocurre cuando juntas <b>entrenamientos y filosofías opuestas</b>: un creativo audaz que proponga sin miedo, "
            "un escéptico implacable que busque fallos y números reales, y un director que consolide el plan maestro paso a paso."
        )
        rule_desc.setStyleSheet("font-size: 11px; color: #E2E8F0; line-height: 1.5;")
        rule_desc.setWordWrap(True)
        rule_lay.addWidget(rule_title)
        rule_lay.addWidget(rule_desc)
        content_layout.addWidget(rule_box)

        # 2. Catálogo de Cerebros
        sec1_title = QLabel("🧠 Los 5 Mejores Cerebros Locales y su Especialidad:")
        sec1_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #ECEFF4; margin-top: 4px;")
        content_layout.addWidget(sec1_title)

        models_data = [
            {
                "name": "richardyoung/llama-3.1-8b-instruct-abliterated",
                "badge": "4.9 GB • Sin Censura",
                "role": "🔵 El Estratega Audaz",
                "role_color": "#00E5FF",
                "card_border": "#1E3A5F",
                "card_bg": "#111C2B",
                "why": "<b>Por qué usarlo:</b> Tiene los filtros morales corporativos neutralizados (*abliterated*). Ofrece estrategias audaces, directas y sin rodeos, ya sea para planes de entrenamiento físico intenso, decisiones difíciles o proyectos sin filtros.",
                "best_for": "Estrategias audaces, planes de acción directos, rutinas de alto impacto y debates sin censura ni respuestas corporativas tibias."
            },
            {
                "name": "deepseek-r1:8b",
                "badge": "4.9 GB • Razonamiento Puro",
                "role": "🔴 El Auditor & Crítico de Riesgos",
                "role_color": "#FF5252",
                "card_border": "#4D1E27",
                "card_bg": "#241318",
                "why": "<b>Por qué usarlo:</b> Utiliza árboles de cadena de pensamiento (`<think>`). Piensa minuciosamente antes de responder y calcula riesgos y puntos ciegos. Si el Estratega propone una rutina lesiva o un plan inviable, DeepSeek R1 auditará riesgos de salud, trampas y fallas lógicas.",
                "best_for": "Auditar riesgos de lesiones/salud, inconsistencias lógicas, trampas financieras y viabilidad práctica paso a paso."
            },
            {
                "name": "qwen2.5-coder:7b",
                "badge": "4.7 GB • Programación & MVPs",
                "role": "💻 El Constructor Técnico",
                "role_color": "#FFB703",
                "card_border": "#5C4312",
                "card_bg": "#231B0D",
                "why": "<b>Por qué usarlo:</b> Entrenado exclusivamente con cientos de miles de millones de tokens de código. Supera a casi todos los modelos 8B en Python, APIs, bases de datos y scripts de automatización para negocios.",
                "best_for": "Diseñar la arquitectura técnica, los scripts en Python y el código del MVP para ejecutar rápido."
            },
            {
                "name": "llama3.1:8b / thruster_ai",
                "badge": "4.9 GB • Equilibrado (Instalado)",
                "role": "🟢 El Director General F3NIX",
                "role_color": "#00E676",
                "card_border": "#194833",
                "card_bg": "#0E2117",
                "why": "<b>Por qué usarlo:</b> Gran capacidad de síntesis e instrucción equilibrada. Es el diplomático: toma el optimismo del Estratega y el pesimismo del Crítico para redactar la hoja de ruta definitiva en Fase 1, Fase 2 y Fase 3.",
                "best_for": "Sintetizar debates, formular cronogramas de acción y unificar opiniones."
            },
            {
                "name": "moondream",
                "badge": "1.7 GB • Visión Ultraligera",
                "role": "👁️ El Ojo Observador de Pantalla",
                "role_color": "#BB86FC",
                "card_border": "#3B1E5C",
                "card_bg": "#1C1129",
                "why": "<b>Por qué usarlo:</b> Pesa menos de 2 GB. No participa en discusiones abstractas, pero puede mirar tu pantalla (un gráfico de trading, una web competidora, un Excel o un diseño) y alimentar de datos visuales reales al debate.",
                "best_for": "Auditorías de interfaces de usuario, análisis de gráficos y lectura de capturas de pantalla."
            }
        ]

        for m in models_data:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {m['card_bg']};
                    border: 1px solid {m['card_border']};
                    border-radius: 8px;
                    padding: 10px 14px;
                }}
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setSpacing(5)

            top_row = QHBoxLayout()
            role_badge = QLabel(m["role"])
            role_badge.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {m['role_color']};")
            model_tag = QLabel(m["badge"])
            model_tag.setStyleSheet("font-size: 10px; color: #8C99B2; background: rgba(0,0,0,0.3); padding: 2px 8px; border-radius: 4px;")
            top_row.addWidget(role_badge)
            top_row.addStretch()
            top_row.addWidget(model_tag)
            c_lay.addLayout(top_row)

            m_name = QLabel(f"Cerebro: <code>{m['name']}</code>")
            m_name.setStyleSheet("font-size: 11px; color: #8BE9FD; font-family: 'Consolas', monospace;")
            c_lay.addWidget(m_name)

            m_why = QLabel(m["why"])
            m_why.setStyleSheet("font-size: 11px; color: #ECEFF4; line-height: 1.4;")
            m_why.setWordWrap(True)
            c_lay.addWidget(m_why)

            m_best = QLabel(f"🎯 <b>Ideal para:</b> {m['best_for']}")
            m_best.setStyleSheet("font-size: 11px; color: #A0AEC0;")
            m_best.setWordWrap(True)
            c_lay.addWidget(m_best)

            content_layout.addWidget(card)

        # 3. Sección: Los 10 Modos de Razonamiento Dialéctico
        sec_modes_title = QLabel("🏛️ Los 10 Modos de Pensamiento Dialéctico:")
        sec_modes_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00E5FF; margin-top: 6px;")
        content_layout.addWidget(sec_modes_title)

        modes_guide = [
            ("🏛️ Modo Clásico", "Tesis, Antítesis y Síntesis: El Estratega diseña, el Crítico busca fallas y el Director consolida el Plan Maestro."),
            ("🦅 Asesor Cisne Negro", "Stress-test de Taleb: Audita los peores escenarios improbables de impacto catastrófico para blindar tu plan ante colapsos."),
            ("⏳ Futuros Bifurcados", "Simulación A/B: Proyecta tu realidad fáctica a 3 y 6 meses si tomas el Sendero A vs el Sendero B, con matriz comparativa final."),
            ("🏋️ Sabios: Salud & Rendimiento", "Fisiólogo de alto rendimiento vs Médico Traumatólogo experto en articulaciones, longevidad y recuperación."),
            ("💻 Sabios: Código & Ciberseguridad", "Arquitecto Senior Clean Code vs Hacker de Seguridad / QA implacable buscando memory leaks y exploits."),
            ("🧠 Sabios: Filosofía & Vida", "Filósofo Estoico (autodominio y virtud) vs Pragmático Realista (costos de energía, tiempo y consecuencias directas)."),
            ("⚖️ Tribunal Dialéctico", "Fiscal Acusador impugna contradicciones y costos ocultos; Abogado Defensor rescata el valor; Juez F3NIX dicta sentencia."),
            ("🗳️ Votación a Ciegas & Consenso", "Dos evaluadores analizan de forma independiente con notas 1-10; el Director sintetiza acuerdos y divergencias."),
            ("🔍 Interrogatorio Socrático", "El auditor formula 2 preguntas incisivas y trampa en cada ronda, forzando definiciones numéricas y operativas."),
            ("🛡️ Dialéctica Steel-Manning", "El crítico primero reconstruye la propuesta en su versión más invulnerable y solo después expone el riesgo estructural.")
        ]

        for m_name, m_desc in modes_guide:
            m_card = QFrame()
            m_card.setStyleSheet("""
                QFrame {
                    background: #111A29;
                    border: 1px solid #1E3A5F;
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)
            mc_lay = QVBoxLayout(m_card)
            mc_lay.setSpacing(2)
            lbl_m_name = QLabel(m_name)
            lbl_m_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #00E5FF;")
            lbl_m_desc = QLabel(m_desc)
            lbl_m_desc.setStyleSheet("font-size: 10px; color: #ECEFF4;")
            lbl_m_desc.setWordWrap(True)
            mc_lay.addWidget(lbl_m_name)
            mc_lay.addWidget(lbl_m_desc)
            content_layout.addWidget(m_card)

        # 4. Sección: Combos Recomendados
        sec2_title = QLabel("🎯 Fórmulas Ganadoras según tu Objetivo:")
        sec2_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #ECEFF4; margin-top: 6px;")
        content_layout.addWidget(sec2_title)

        combos = [
            {
                "title": "💪 Combo Salud, Alto Rendimiento & Hábitos",
                "desc": "<b>Estratega:</b> Hermes 3 o Llama 3.1 &nbsp;➔&nbsp; <b>Crítico:</b> DeepSeek R1 &nbsp;➔&nbsp; <b>Director:</b> Llama 3.1 o Phi-4",
                "goal": "Para diseñar rutinas de entrenamiento físico natural, nutrición real, prevención de lesiones articulares y hábitos según edad y entorno."
            },
            {
                "title": "💰 Combo Monetización & Nuevos Negocios",
                "desc": "<b>Estratega:</b> Llama 3.1 Abliterated &nbsp;➔&nbsp; <b>Crítico:</b> DeepSeek R1 &nbsp;➔&nbsp; <b>Director:</b> Llama 3.1",
                "goal": "Para encontrar nichos rentables, validar modelos de cobro y evitar riesgos de mercado antes de invertir dinero."
            },
            {
                "title": "💻 Combo Creación de Software & Automatizaciones",
                "desc": "<b>Estratega:</b> Llama 3.1 &nbsp;➔&nbsp; <b>Crítico:</b> DeepSeek R1 &nbsp;➔&nbsp; <b>Director Técnico:</b> Qwen 2.5 Coder",
                "goal": "Para crear bots, APIs o scripts que resuelvan problemas a clientes sin perder tiempo programando de más."
            },
            {
                "title": "🧠 Combo Toma de Decisiones Complejas / Dilemas",
                "desc": "<b>Estratega:</b> Hermes 3 &nbsp;➔&nbsp; <b>Crítico:</b> DeepSeek R1 &nbsp;➔&nbsp; <b>Director:</b> Llama 3.1",
                "goal": "Para destrabar encrucijadas personales o profesionales contrastando sesgos, riesgos a largo plazo y una síntesis balanceada."
            }
        ]

        for combo in combos:
            c_box = QFrame()
            c_box.setStyleSheet("""
                QFrame {
                    background: #141A26;
                    border: 1px solid #232C3D;
                    border-left: 3px solid #00E5FF;
                    border-radius: 6px;
                    padding: 8px 12px;
                }
            """)
            cb_lay = QVBoxLayout(c_box)
            cb_lay.setSpacing(3)
            ctitle = QLabel(combo["title"])
            ctitle.setStyleSheet("font-weight: bold; font-size: 12px; color: #00E5FF;")
            cdesc = QLabel(combo["desc"])
            cdesc.setStyleSheet("font-size: 11px; color: #ECEFF4;")
            cgoal = QLabel(f"<i>{combo['goal']}</i>")
            cgoal.setStyleSheet("font-size: 10px; color: #8C99B2;")
            cgoal.setWordWrap(True)
            cb_lay.addWidget(ctitle)
            cb_lay.addWidget(cdesc)
            cb_lay.addWidget(cgoal)
            content_layout.addWidget(c_box)

        scroll.setWidget(container)
        main_layout.addWidget(scroll, stretch=1)

        # Barra inferior de botones
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        store_btn = QPushButton("📥 Abrir Tienda de Cerebros (Descargar IAs)")
        store_btn.setProperty("class", "primary")
        store_btn.setStyleSheet("background-color: #00E5FF; color: #000000; font-weight: bold; padding: 8px 16px;")
        store_btn.clicked.connect(self._on_store_clicked)

        close_btn = QPushButton("✅ Entendido")
        close_btn.clicked.connect(self.accept)

        bottom_bar.addWidget(store_btn)
        bottom_bar.addStretch()
        bottom_bar.addWidget(close_btn)

        main_layout.addLayout(bottom_bar)

    def _on_store_clicked(self):
        self.open_store_requested.emit()
        self.accept()
