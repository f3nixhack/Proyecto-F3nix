"""
ui/environment_doctor_dialog.py
Ventana visual del Doctor F3NIX para diagnóstico, verificación de salud
y auto-reparación del entorno (Ollama, librerías, modelos y rutas).
"""

import os
import sys
import webbrowser
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QMessageBox, QProgressBar
)
from core.environment_doctor import EnvironmentDoctor

class StartOllamaWorker(QThread):
    finished_signal = pyqtSignal(bool, str)

    def run(self):
        ok, msg = EnvironmentDoctor.auto_start_ollama(wait_seconds=8)
        self.finished_signal.emit(ok, msg)

class EnvironmentDoctorDialog(QDialog):
    """
    Diálogo interactivo para diagnosticar el estado del sistema,
    iniciar Ollama, corregir dependencias o guiar al usuario.
    """
    open_model_store_requested = pyqtSignal()

    def __init__(self, parent=None, auto_heal: bool = True):
        super().__init__(parent)
        self.setWindowTitle("🩺 Doctor F3NIX - Diagnóstico y Salud del Sistema")
        self.setFixedSize(560, 600)
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
                background: transparent;
            }
        """)

        self.start_worker = None
        self._init_ui()
        self.run_diagnostics()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        # Encabezado
        title_row = QHBoxLayout()
        icon_lbl = QLabel("🩺")
        icon_lbl.setStyleSheet("font-size: 26px;")
        
        header_text = QVBoxLayout()
        title = QLabel("Doctor F3NIX — Diagnóstico de Entorno")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #00E5FF;")
        subtitle = QLabel("Comprobando que todo lo necesario para ejecutar la IA esté en orden.")
        subtitle.setStyleSheet("font-size: 11px; color: #8F9CAE;")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)

        title_row.addWidget(icon_lbl)
        title_row.addLayout(header_text)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Barra de progreso para acciones en segundo plano
        self.action_progress = QProgressBar()
        self.action_progress.setRange(0, 0)  # indeterminado
        self.action_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #1E2738;
                border-radius: 4px;
                background-color: #161B29;
                height: 10px;
            }
            QProgressBar::chunk {
                background-color: #00E5FF;
            }
        """)
        self.action_progress.hide()
        layout.addWidget(self.action_progress)

        # Contenedor de tarjetas
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)

        # Barra inferior de botones
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_refresh = QPushButton("🔄 Re-analizar")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #1E2638;
                color: #BAC7D5;
                border: 1px solid #2B374E;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #26324A;
                color: #FFFFFF;
            }
        """)
        self.btn_refresh.clicked.connect(self.run_diagnostics)

        self.btn_close = QPushButton("Continuar a F3NIX")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #00E5FF;
                color: #000000;
                border: none;
                padding: 8px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4DEBFF;
            }
        """)
        self.btn_close.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

    def run_diagnostics(self):
        """Ejecuta el chequeo y reconstruye las tarjetas de estado."""
        # Limpiar tarjetas previas
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        diag = EnvironmentDoctor.get_full_diagnostics()

        # 1. Tarjeta de Rutas Healed (si se reparó algo)
        if diag.get("healed_paths"):
            card_paths = self._create_card(
                icon="🛠️",
                title="Ruta de Modelos Recuperada",
                subtitle="Se detectó una ruta o disco no disponible. El sistema restauró automáticamente la ubicación en tu disco C:.",
                status_badge="✓ Auto-Reparado",
                status_color="#4ADE80",
                badge_bg="#132B1F"
            )
            self.cards_layout.addWidget(card_paths)

        # 2. Tarjeta del Motor Ollama
        is_running = diag["ollama_running"]
        is_installed = diag["ollama_installed"]

        if is_running:
            card_ollama = self._create_card(
                icon="⚡",
                title="Motor de Inteligencia Artificial (Ollama)",
                subtitle=f"En ejecución y listo en http://localhost:11434.\nUbicación: {diag['ollama_path'] or 'Estándar'}",
                status_badge="● En Línea",
                status_color="#4ADE80",
                badge_bg="#132B1F"
            )
        elif is_installed:
            card_ollama = self._create_card(
                icon="⚡",
                title="Motor de Inteligencia Artificial (Ollama)",
                subtitle="Ollama está instalado pero se encuentra apagado.",
                status_badge="● Detenido",
                status_color="#FFB703",
                badge_bg="#2D2208",
                action_btn_text="🚀 Iniciar Ollama Ahora",
                action_callback=self._start_ollama
            )
        else:
            card_ollama = self._create_card(
                icon="⚡",
                title="Motor de Inteligencia Artificial (Ollama)",
                subtitle="Ollama no se encontró instalado en esta computadora.",
                status_badge="● No Instalado",
                status_color="#FF4D6D",
                badge_bg="#2D0D15",
                action_btn_text="📥 Descargar Ollama Oficial",
                action_callback=lambda: webbrowser.open("https://ollama.com/download")
            )
        self.cards_layout.addWidget(card_ollama)

        # 3. Tarjeta de Cerebros (Modelos)
        count = diag["models_count"]
        if count > 0:
            m_list = ", ".join(diag["models"][:3])
            if count > 3:
                m_list += f" (+{count - 3} más)"
            card_models = self._create_card(
                icon="🧠",
                title="Cerebros Locales Instalados",
                subtitle=f"{count} modelo(s) listos para usar: {m_list}",
                status_badge=f"✓ {count} Listos",
                status_color="#4ADE80",
                badge_bg="#132B1F",
                action_btn_text="📥 Instalar Más Cerebros",
                action_callback=self._open_store
            )
        else:
            card_models = self._create_card(
                icon="🧠",
                title="Cerebros Locales de IA",
                subtitle="No hay cerebros descargados aún en tu disco C:. Puedes instalar Moondream (1.7 GB) o Llama 3.1 con un solo clic.",
                status_badge="⚠️ Requiere 1 Cerebro",
                status_color="#FFB703",
                badge_bg="#2D2208",
                action_btn_text="📥 Abrir Tienda de Cerebros",
                action_callback=self._open_store
            )
        self.cards_layout.addWidget(card_models)

        # 4. Tarjeta de Espacio en Disco
        free_gb = diag["free_disk_gb"]
        if free_gb >= 10.0:
            card_disk = self._create_card(
                icon="💾",
                title="Almacenamiento en Disco",
                subtitle=f"{free_gb} GB disponibles en tu unidad del sistema. Espacio óptimo para múltiples modelos.",
                status_badge=f"✓ {free_gb} GB Libres",
                status_color="#4ADE80",
                badge_bg="#132B1F"
            )
        elif free_gb >= 3.0:
            card_disk = self._create_card(
                icon="💾",
                title="Almacenamiento en Disco",
                subtitle=f"{free_gb} GB disponibles. Suficiente para 1 modelo mediano.",
                status_badge=f"● {free_gb} GB",
                status_color="#FFB703",
                badge_bg="#2D2208"
            )
        else:
            card_disk = self._create_card(
                icon="💾",
                title="Almacenamiento en Disco",
                subtitle=f"Solo {free_gb} GB libres. Se recomienda liberar espacio para descargar modelos grandes.",
                status_badge="⚠️ Espacio Bajo",
                status_color="#FF4D6D",
                badge_bg="#2D0D15"
            )
        self.cards_layout.addWidget(card_disk)

        # 5. Tarjeta de Librerías de Python
        deps = diag["python_dependencies"]
        missing_deps = [pkg for pkg, ok in deps.items() if not ok]

        if not missing_deps:
            card_deps = self._create_card(
                icon="📦",
                title="Dependencias y Audio de Python",
                subtitle="Todas las librerías activas (PyQt6, Audio TTS/STT, Edge-TTS, Pygame).",
                status_badge="✓ Todo en Orden",
                status_color="#4ADE80",
                badge_bg="#132B1F"
            )
        else:
            card_deps = self._create_card(
                icon="📦",
                title="Dependencias de Python",
                subtitle=f"Librerías pendientes: {', '.join(missing_deps)}.",
                status_badge="⚠️ Faltan Librerías",
                status_color="#FFB703",
                badge_bg="#2D2208",
                action_btn_text="⚡ Instalar Faltantes (pip)",
                action_callback=lambda: self._install_python_packages(missing_deps)
            )
        self.cards_layout.addWidget(card_deps)

        self.cards_layout.addStretch()

    def _create_card(
        self,
        icon: str,
        title: str,
        subtitle: str,
        status_badge: str,
        status_color: str,
        badge_bg: str,
        action_btn_text: str = None,
        action_callback = None
    ) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #141A28;
                border: 1px solid #202A3C;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        icn = QLabel(icon)
        icn.setStyleSheet("font-size: 18px;")
        
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #FFFFFF;")
        
        badge = QLabel(f" {status_badge} ")
        badge.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {status_color};
            font-size: 10px;
            font-weight: bold;
            border-radius: 4px;
            padding: 3px 6px;
            border: 1px solid {status_color}44;
        """)

        top_row.addWidget(icn)
        top_row.addWidget(t_lbl)
        top_row.addStretch()
        top_row.addWidget(badge)
        layout.addLayout(top_row)

        desc = QLabel(subtitle)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8F9CAE; font-size: 11px;")
        layout.addWidget(desc)

        if action_btn_text and action_callback:
            act_row = QHBoxLayout()
            act_row.addStretch()
            btn = QPushButton(action_btn_text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #00E5FF;
                    color: #000000;
                    border: none;
                    border-radius: 5px;
                    padding: 5px 12px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4DEBFF;
                }
            """)
            btn.clicked.connect(action_callback)
            act_row.addWidget(btn)
            layout.addLayout(act_row)

        return frame

    def _start_ollama(self):
        self.action_progress.show()
        self.btn_refresh.setEnabled(False)
        self.start_worker = StartOllamaWorker()
        self.start_worker.finished_signal.connect(self._on_ollama_started)
        self.start_worker.start()

    def _on_ollama_started(self, success: bool, message: str):
        self.action_progress.hide()
        self.btn_refresh.setEnabled(True)
        if success:
            QMessageBox.information(self, "Ollama Iniciado", message)
            self.run_diagnostics()
        else:
            QMessageBox.warning(self, "Aviso", message)

    def _install_python_packages(self, packages):
        self.action_progress.show()
        ok, msg = EnvironmentDoctor.install_missing_packages(packages)
        self.action_progress.hide()
        if ok:
            QMessageBox.information(self, "Librerías Instaladas", msg)
            self.run_diagnostics()
        else:
            QMessageBox.warning(self, "Error en Instalación", msg)

    def _open_store(self):
        self.open_model_store_requested.emit()
        self.accept()
