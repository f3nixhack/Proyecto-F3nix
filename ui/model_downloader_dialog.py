import json
import logging
import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QScrollArea, QWidget, QFrame, QMessageBox
)
from core.environment_doctor import EnvironmentDoctor

logger = logging.getLogger(__name__)

AVAILABLE_MODELS_CATALOG = [
    {
        "id": "richardyoung/llama-3.1-8b-instruct-abliterated",
        "tag": "richardyoung/llama-3.1-8b-instruct-abliterated",
        "title": "Llama 3.1 8B (Abliterated / 100% Sin Censura)",
        "badge": "🔓 Liberado Total",
        "size": "~4.9 GB",
        "specs": "Requiere 8 GB RAM",
        "desc": "Llama 3.1 con los vectores de rechazo y censura eliminados quirúrgicamente (Abliteration). Nunca se niega a responder peticiones técnicas complejas o temas restringidos."
    },
    {
        "id": "deepseek-r1:8b",
        "tag": "deepseek-r1:8b",
        "title": "DeepSeek R1 8B (Razonamiento Puro)",
        "badge": "🧠 Pensamiento Paso a Paso",
        "size": "~4.9 GB",
        "specs": "Requiere 8 GB RAM",
        "desc": "El modelo de razonamiento profundo del momento. Desglosa su lógica internamente antes de dar la respuesta definitiva, ideal para programación difícil y lógica pura."
    },
    {
        "id": "hermes3",
        "tag": "hermes3",
        "title": "Nous Hermes 3 (Agente Autónomo)",
        "badge": "Recomendado F3NIX",
        "size": "~4.7 GB",
        "specs": "Requiere 8 GB RAM",
        "desc": "El cerebro definitivo para actuar como agente autónomo F3NIX: excelente en razonamiento, herramientas de sistema y conversación fluida sin sermones morales."
    },
    {
        "id": "qwen2.5-coder:7b",
        "tag": "qwen2.5-coder:7b",
        "title": "Qwen 2.5 Coder (Programación)",
        "badge": "Especialista Código",
        "size": "~4.7 GB",
        "specs": "Requiere 8 GB RAM",
        "desc": "El mejor modelo libre para desarrolladores. Detecta errores, refactoriza código, escribe scripts en Python, JS, C++ y resuelve dudas de arquitectura."
    },
    {
        "id": "moondream",
        "tag": "moondream",
        "title": "Moondream 2 (Ojos & Visión de Pantalla)",
        "badge": "👁️ Visión Ligera (1.7 GB)",
        "size": "~1.7 GB",
        "specs": "Requiere 4 GB RAM (Apto CPU y GPU)",
        "desc": "¡Le da ojos a F3NIX! Modelo de visión artificial ultrarrápido y liviano capaz de ver tu pantalla, describir ventanas, leer errores visuales y ayudarte."
    },
    {
        "id": "llava",
        "tag": "llava",
        "title": "LLaVA 7B (Visión y Razonamiento Avanzado)",
        "badge": "👁️ Visión Completa",
        "size": "~4.7 GB",
        "specs": "Requiere 8 GB RAM",
        "desc": "El modelo multimodal por excelencia. Inspecciona capturas de pantalla con gran detalle, reconoce código en imágenes, interfaces complejas y diagramas."
    },
    {
        "id": "llama3.1",
        "tag": "llama3.1",
        "title": "Llama 3.1 8B (Meta AI)",
        "badge": "Equilibrado",
        "size": "~4.9 GB",
        "specs": "Requiere 8 GB RAM",
        "desc": "El modelo insignia de Meta. Gran enciclopedia de conocimiento, muy natural en español y altamente versátil para cualquier tarea general."
    },
    {
        "id": "llama3.2:3b",
        "tag": "llama3.2:3b",
        "title": "Llama 3.2 3B (Ultraligero)",
        "badge": "Para Cualquier PC",
        "size": "~2.0 GB",
        "specs": "Requiere 4 GB RAM (Apto sin GPU)",
        "desc": "Modelo ultrarrápido y liviano diseñado para laptops o computadoras sin placa de video dedicada. Responde casi al instante."
    },
    {
        "id": "phi4",
        "tag": "phi4",
        "title": "Phi-4 14B (Microsoft)",
        "badge": "Alta Capacidad",
        "size": "~9.1 GB",
        "specs": "Requiere 16 GB RAM / GPU 8GB+",
        "desc": "El modelo avanzado de Microsoft para razonamiento lógico, científico y matemático de alta precisión."
    }
]

class DownloadWorker(QThread):
    progress_signal = pyqtSignal(int, str)  # porcentaje (0-100), estado
    finished_signal = pyqtSignal(bool, str)  # éxito, mensaje

    def __init__(self, model_tag: str, base_url: str = "http://localhost:11434"):
        super().__init__()
        self.model_tag = model_tag
        self.base_url = base_url.rstrip("/")
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            url = f"{self.base_url}/api/pull"
            payload = {"name": self.model_tag, "stream": True}
            
            with requests.post(url, json=payload, stream=True, timeout=3600) as response:
                if response.status_code != 200:
                    self.finished_signal.emit(False, f"Error HTTP {response.status_code}: {response.text}")
                    return

                total_bytes = 0
                completed_bytes = 0
                is_success = False

                for line in response.iter_lines():
                    if self._is_cancelled:
                        self.finished_signal.emit(False, "Descarga cancelada por el usuario.")
                        return

                    if not line:
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                        
                        if "error" in data:
                            self.finished_signal.emit(False, f"Error de Ollama: {data['error']}")
                            return

                        status = data.get("status", "")
                        
                        if "total" in data and "completed" in data:
                            total_bytes = data["total"]
                            completed_bytes = data["completed"]
                            if total_bytes > 0:
                                percent = int((completed_bytes / total_bytes) * 100)
                                mb_done = round(completed_bytes / (1024 * 1024), 1)
                                mb_total = round(total_bytes / (1024 * 1024), 1)
                                self.progress_signal.emit(percent, f"{status} ({mb_done}/{mb_total} MB - {percent}%)")
                        else:
                            self.progress_signal.emit(-1, status)

                        if status == "success":
                            is_success = True
                            self.finished_signal.emit(True, f"¡Modelo {self.model_tag} instalado con éxito!")
                            return
                    except Exception:
                        pass

                if is_success:
                    self.finished_signal.emit(True, f"Descarga de {self.model_tag} completada.")
                else:
                    self.finished_signal.emit(False, f"La descarga de {self.model_tag} no finalizó o fue interrumpida.")
        except requests.exceptions.ConnectionError:
            if not self._is_cancelled:
                self.finished_signal.emit(
                    False,
                    "No se pudo conectar con el motor Ollama en el puerto 11434.\n"
                    "El servicio local parece estar apagado o fue detenido."
                )
        except Exception as e:
            if not self._is_cancelled:
                err_text = str(e)
                if "10061" in err_text or "denegó expresamente" in err_text or "refused" in err_text.lower():
                    err_text = "Conexión rechazada: El motor Ollama no está en ejecución en http://localhost:11434."
                self.finished_signal.emit(False, err_text)

class ModelDownloaderDialog(QDialog):
    """
    Tienda visual de modelos de IA para que cualquier usuario principiante
    pueda instalar modelos como Hermes o Qwen con un solo clic.
    """
    model_installed = pyqtSignal(str)

    def __init__(self, installed_models=None, parent=None):
        super().__init__(parent)
        self.installed_models = installed_models or []
        self.current_worker = None

        self.setWindowTitle("F3NIX - Centro de Descarga de Cerebros de IA")
        self.setFixedSize(580, 620)
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
        main_layout.setSpacing(15)

        # Encabezado
        title = QLabel("⚡ Centro de Inteligencias Artificiales")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00E5FF;")
        subtitle = QLabel("Elige e instala con un solo clic el cerebro que desees para tu asistente.")
        subtitle.setStyleSheet("font-size: 12px; color: #8F9CAE;")

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        # Banner de estado de Ollama si el servicio está detenido
        self.banner_ollama = QFrame()
        self.banner_ollama.setStyleSheet("""
            QFrame {
                background-color: #2D1A08;
                border: 1px solid #FFB703;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        banner_layout = QHBoxLayout(self.banner_ollama)
        banner_layout.setContentsMargins(0, 0, 0, 0)
        self.banner_label = QLabel("⚠️ El motor Ollama está apagado. Inícialo para poder descargar o usar cerebros.")
        self.banner_label.setStyleSheet("color: #FFD166; font-size: 11px;")
        self.banner_label.setWordWrap(True)
        self.btn_banner_start = QPushButton("🚀 Iniciar Ollama")
        self.btn_banner_start.setStyleSheet("""
            QPushButton {
                background-color: #FFB703;
                color: #000000;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #FFC933;
            }
        """)
        self.btn_banner_start.clicked.connect(self._start_ollama_from_banner)
        banner_layout.addWidget(self.banner_label, stretch=1)
        banner_layout.addWidget(self.btn_banner_start)
        main_layout.addWidget(self.banner_ollama)

        if EnvironmentDoctor.is_ollama_running():
            self.banner_ollama.hide()

        # Barra de progreso global
        self.progress_container = QWidget()
        prog_layout = QVBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(0, 5, 0, 5)

        self.status_label = QLabel("Listo para descargar.")
        self.status_label.setStyleSheet("font-size: 11px; color: #FFB703;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #2B3347;
                border-radius: 6px;
                background-color: #171C2B;
                text-align: center;
                color: white;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #00E5FF;
                border-radius: 5px;
            }
        """)
        self.progress_bar.setValue(0)
        self.progress_container.hide()

        prog_layout.addWidget(self.status_label)
        prog_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.progress_container)

        # Scroll Area con tarjetas de modelos
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        cards_layout = QVBoxLayout(scroll_content)
        cards_layout.setSpacing(12)

        self.cards_buttons = {}

        for item in AVAILABLE_MODELS_CATALOG:
            card = self._create_model_card(item)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Botón inferior para cerrar
        btn_close = QPushButton("Cerrar")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #22293D;
                color: white;
                border: 1px solid #364260;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2D3752;
            }
        """)
        btn_close.clicked.connect(self.close)
        main_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def closeEvent(self, event):
        if self.current_worker and self.current_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Descarga en curso",
                "Hay una descarga de modelo en progreso. ¿Deseas cancelarla y salir?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.current_worker.cancel()
                self.current_worker.terminate()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def _is_model_installed(self, tag: str) -> bool:
        norm_tag = tag.lower().strip()
        tag_no_latest = norm_tag[:-7] if norm_tag.endswith(":latest") else norm_tag
        tag_short = norm_tag.split("/")[-1]
        tag_short_no_latest = tag_short[:-7] if tag_short.endswith(":latest") else tag_short

        for m in self.installed_models:
            norm_m = m.lower().strip()
            m_no_latest = norm_m[:-7] if norm_m.endswith(":latest") else norm_m
            m_short = norm_m.split("/")[-1]
            m_short_no_latest = m_short[:-7] if m_short.endswith(":latest") else m_short

            if (norm_tag == norm_m or 
                tag_no_latest == m_no_latest or 
                norm_tag == m_short or 
                tag_short == norm_m or
                tag_short_no_latest == m_short_no_latest):
                return True
        return False

    def _create_model_card(self, item) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #161B29;
                border: 1px solid #283248;
                border-radius: 10px;
                padding: 12px;
            }
            QFrame:hover {
                border: 1px solid #00E5FF;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setSpacing(6)

        # Fila superior: Título y Badge
        top_row = QHBoxLayout()
        title_lbl = QLabel(item["title"])
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")

        badge_lbl = QLabel(f" {item['badge']} ")
        badge_lbl.setStyleSheet("background-color: #005662; color: #00E5FF; border-radius: 4px; font-size: 10px; font-weight: bold; padding: 2px 4px;")

        top_row.addWidget(title_lbl)
        top_row.addWidget(badge_lbl)
        top_row.addStretch()

        size_lbl = QLabel(f"Tamaño: {item['size']} | {item['specs']}")
        size_lbl.setStyleSheet("color: #7E8D9F; font-size: 11px;")

        desc_lbl = QLabel(item["desc"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #BAC7D5; font-size: 11px; margin-top: 2px;")

        # Botón de acción
        btn = QPushButton()
        is_installed = self._is_model_installed(item["tag"])

        if is_installed:
            btn.setText("✓ Instalado")
            btn.setEnabled(False)
            btn.setStyleSheet("background-color: #1F362A; color: #4ADE80; border: 1px solid #2E6544; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        else:
            btn.setText("⬇ Descargar e Instalar")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #00E5FF;
                    color: #000000;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #4DEBFF;
                }
            """)
            btn.clicked.connect(lambda _, t=item["tag"], b=btn: self.start_download(t, b))

        self.cards_buttons[item["tag"]] = btn

        action_row = QHBoxLayout()
        action_row.addWidget(size_lbl)
        action_row.addStretch()
        action_row.addWidget(btn)

        layout.addLayout(top_row)
        layout.addWidget(desc_lbl)
        layout.addLayout(action_row)

        return frame

    def _start_ollama_from_banner(self):
        self.btn_banner_start.setText("Iniciando...")
        self.btn_banner_start.setEnabled(False)
        ok, msg = EnvironmentDoctor.auto_start_ollama(wait_seconds=8)
        self.btn_banner_start.setText("🚀 Iniciar Ollama")
        self.btn_banner_start.setEnabled(True)
        if ok:
            self.banner_ollama.hide()
            self._refresh_installed_list()
            QMessageBox.information(self, "Ollama Iniciado", "El motor Ollama se ha iniciado correctamente.")
        else:
            QMessageBox.warning(self, "No se pudo iniciar", msg)

    def _refresh_installed_list(self):
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=2.0)
            if r.status_code == 200:
                self.installed_models = [m.get("name", "") for m in r.json().get("models", [])]
                for tag, btn in self.cards_buttons.items():
                    if self._is_model_installed(tag):
                        btn.setText("✓ Instalado")
                        btn.setEnabled(False)
                        btn.setStyleSheet("background-color: #1F362A; color: #4ADE80; border: 1px solid #2E6544; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        except Exception:
            pass

    def start_download(self, model_tag: str, button: QPushButton):
        if self.current_worker and self.current_worker.isRunning():
            QMessageBox.warning(self, "Descarga en curso", "Ya hay un modelo descargándose. Espera a que termine.")
            return

        # Comprobar que Ollama esté activo antes de iniciar
        if not EnvironmentDoctor.is_ollama_running():
            self.status_label.setText("Ollama está apagado. Intentando arrancar el motor...")
            self.progress_container.show()
            ok, msg = EnvironmentDoctor.auto_start_ollama(wait_seconds=8)
            if not ok:
                self.progress_container.hide()
                self.banner_ollama.show()
                QMessageBox.warning(
                    self,
                    "Ollama Apagado",
                    "El motor de Inteligencia Artificial (Ollama) no está en ejecución en el puerto 11434.\n\n"
                    "Por favor pulsa '🚀 Iniciar Ollama' en la barra superior o ábrelo desde el menú de inicio."
                )
                return
            else:
                self.banner_ollama.hide()
                self._refresh_installed_list()

        button.setText("Descargando...")
        button.setEnabled(False)
        button.setStyleSheet("background-color: #384259; color: #FFFFFF; border-radius: 6px; padding: 6px;")

        self.progress_container.show()
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Iniciando descarga de {model_tag}...")

        self.current_worker = DownloadWorker(model_tag)
        self.current_worker.progress_signal.connect(self._on_progress)
        self.current_worker.finished_signal.connect(lambda ok, msg, t=model_tag, b=button: self._on_finished(ok, msg, t, b))
        self.current_worker.start()

    def _on_progress(self, percent: int, status_text: str):
        self.status_label.setText(status_text)
        if percent >= 0:
            self.progress_bar.setValue(percent)

    def _on_finished(self, success: bool, message: str, model_tag: str, button: QPushButton):
        if success:
            self.status_label.setText(f"¡{model_tag} instalado con éxito!")
            self.progress_bar.setValue(100)
            button.setText("✓ Instalado")
            button.setEnabled(False)
            button.setStyleSheet("background-color: #1F362A; color: #4ADE80; border: 1px solid #2E6544; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
            
            # Consultar lista real de Ollama para registrar el nombre exacto
            try:
                r = requests.get("http://localhost:11434/api/tags", timeout=3)
                if r.status_code == 200:
                    real_installed = [m.get("name", "") for m in r.json().get("models", [])]
                    self.installed_models = real_installed
            except Exception:
                if model_tag not in self.installed_models:
                    self.installed_models.append(model_tag)

            self.model_installed.emit(model_tag)
            QMessageBox.information(self, "Instalación Completada", f"El modelo {model_tag} ha sido instalado.\nAhora puedes seleccionarlo en 'Cambiar Cerebro / Modelo' o en la Mesa Redonda.")
        else:
            self.status_label.setText(f"Error: {message}")
            button.setText("Reintentar")
            button.setEnabled(True)
            button.setStyleSheet("background-color: #FF2E63; color: white; border-radius: 6px; padding: 6px;")
            QMessageBox.warning(self, "Descarga Incompleta", f"No se pudo completar la descarga:\n{message}")
