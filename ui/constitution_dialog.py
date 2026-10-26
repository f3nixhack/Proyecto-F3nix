import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QListWidget, QListWidgetItem, QSplitter, QFrame
)
from core.fenix_reasoning import FenixReasoningEngine

MODULE_LABELS = [
    ("constitution", "📜 0. Instrucción Maestra & Seguridad"),
    ("core_values", "💎 1. Valores Fundamentales & Libertad"),
    ("reasoning_engine", "⚙️ 2. Motor de 12 Pasos & Pipeline"),
    ("ethics_and_relationships", "🤝 3. Ética, Reciprocidad & Límites"),
    ("conflict_and_limits", "🛡️ 4. Protocolo de Traición & Anti-patrones"),
    ("fighter_mindset", "🥋 5. Mentalidad Marcial & Autocontrol"),
    ("communication", "🗣️ 6. Estilo Directo & Controversial"),
    ("epistemology", "🔍 7. Epistemología, Verdad & Steelman"),
    ("case_studies", "📖 8. Casos Empíricos de Calibración"),
    ("evaluation", "🎯 9. Escenarios Canónicos de Prueba"),
]

class ConstitutionDialog(QDialog):
    """
    Visor interactivo de la Constitución Mental y Motor Cognitivo F3NIX AI v1.0.
    Permite consultar todos los módulos de razonamiento ético, epistemológico,
    marcial y de toma de decisiones definidos por Fabián Ibáñez.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📜 F3NIX AI — Constitución Mental & Especificación de Razonamiento (v1.0)")
        self.resize(920, 680)
        self.setMinimumSize(780, 540)
        self.engine = FenixReasoningEngine()
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
            QListWidget {
                background-color: #111724;
                border: 1px solid #1E2B3E;
                border-radius: 8px;
                padding: 6px;
                outline: none;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 6px;
                color: #B0BEC5;
                font-size: 11.5px;
                font-weight: 500;
                margin-bottom: 3px;
            }
            QListWidget::item:hover {
                background-color: #1A2436;
                color: #FFFFFF;
            }
            QListWidget::item:selected {
                background-color: #00838F;
                color: #FFFFFF;
                font-weight: bold;
            }
            QTextBrowser {
                background-color: #101520;
                border: 1px solid #1E2838;
                border-radius: 8px;
                padding: 16px;
                color: #ECEFF4;
                font-size: 12.5px;
                line-height: 1.6;
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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        icon_lbl = QLabel("⚖️")
        icon_lbl.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("CONSTITUCIÓN MENTAL F3NIX AI (v1.0)")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #00E5FF; letter-spacing: 1px;")
        sub_lbl = QLabel("Especificación filosófica, toma de decisiones en 12 pasos, protocolo de límites y mentalidad marcial de Fabián Ibáñez.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #8C99B2;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        badge = QLabel("🛡️ 10 MÓDULOS ACTIVOS")
        badge.setStyleSheet("background: #0C2E2B; color: #00E676; border: 1px solid #00BFA5; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 12px;")
        header_layout.addWidget(badge)

        main_layout.addLayout(header_layout)

        # Splitter con Lista de Módulos a la izquierda y Visor a la derecha
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Lista de módulos
        self.module_list = QListWidget()
        for mod_key, mod_label in MODULE_LABELS:
            item = QListWidgetItem(mod_label)
            item.setData(Qt.ItemDataRole.UserRole, mod_key)
            self.module_list.addItem(item)

        self.module_list.currentRowChanged.connect(self._on_module_selected)
        splitter.addWidget(self.module_list)

        # Visor de módulo
        right_container = QFrame()
        right_lay = QVBoxLayout(right_container)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(8)

        self.module_header_lbl = QLabel("Seleccione un módulo")
        self.module_header_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #00E5FF; padding: 2px 4px;")
        right_lay.addWidget(self.module_header_lbl)

        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)
        right_lay.addWidget(self.content_browser)

        splitter.addWidget(right_container)
        splitter.setSizes([260, 620])

        main_layout.addWidget(splitter, stretch=1)

        # Footer
        footer_layout = QHBoxLayout()
        hint = QLabel("💡 <i>El Director Supremo en la Mesa Redonda razona automáticamente bajo este marco constitucional.</i>")
        hint.setStyleSheet("color: #78909C; font-size: 11px;")
        footer_layout.addWidget(hint)
        footer_layout.addStretch()

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)

        main_layout.addLayout(footer_layout)

        # Seleccionar primer módulo por defecto
        if self.module_list.count() > 0:
            self.module_list.setCurrentRow(0)

    def _on_module_selected(self, row: int):
        item = self.module_list.item(row)
        if not item:
            return
        mod_key = item.data(Qt.ItemDataRole.UserRole)
        label_text = item.text()
        self.module_header_lbl.setText(label_text)

        content = self.engine.get_module(mod_key)
        if content:
            self.content_browser.setMarkdown(content)
        else:
            self.content_browser.setText(f"[Módulo {mod_key} no encontrado o vacío]")
