from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QTextEdit, QFrame, QMessageBox
)
from core.memory_vault import MemoryVault

class LifeCaseDialog(QDialog):
    """
    Ventana para registrar y gestionar Casos Empíricos de Vida (Sección 19).
    Permite registrar situaciones reales con el esquema:
    Situación → Acción tomada → Motivo → Principio derivado.
    """

    def __init__(self, memory_vault: MemoryVault, parent=None):
        super().__init__(parent)
        self.memory = memory_vault
        self.setWindowTitle("📖 F3NIX — Casos Empíricos de Vida (Calibración Moral)")
        self.resize(850, 600)
        self.setMinimumSize(720, 480)
        self._apply_theme()
        self._init_ui()
        self._refresh_table()

    def _apply_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0D111A;
            }
            QWidget {
                color: #ECEFF4;
                font-family: 'Segoe UI', sans-serif;
            }
            QTableWidget {
                background-color: #101522;
                border: 1px solid #1E2838;
                border-radius: 6px;
                gridline-color: #1E2738;
                color: #ECEFF4;
            }
            QHeaderView::section {
                background-color: #171E2C;
                color: #8C99B2;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #252F42;
                font-weight: bold;
            }
            QLineEdit, QTextEdit {
                background-color: #101622;
                border: 1px solid #1E2D42;
                border-radius: 5px;
                padding: 6px;
                color: #FFFFFF;
                font-size: 11.5px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #00E5FF;
            }
            QPushButton {
                background-color: #1E2738;
                color: #ECEFF4;
                border: 1px solid #2E3B52;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background-color: #29354C;
                border-color: #00E5FF;
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        icon_lbl = QLabel("📖")
        icon_lbl.setStyleSheet("font-size: 30px;")
        header_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("CASOS EMPÍRICOS DE VIDA & CALIBRACIÓN (F3NIX)")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #00E5FF; letter-spacing: 1px;")
        sub_lbl = QLabel("Registra situaciones de la vida real para nutrir la memoria y afinar el criterio del Director Supremo.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #8C99B2;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Tabla de casos
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Fecha", "Principio Derivado", "Situación", "Acción Tomada", "Acción"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(2, 160)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        # Panel de ingreso de nuevo caso
        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: #121824; border: 1px solid #1E2838; border-radius: 8px; padding: 8px;")
        form_lay = QVBoxLayout(form_frame)
        form_lay.setSpacing(8)

        form_title = QLabel("➕ Registrar Nuevo Caso Real (Formato Constitución v1.0)")
        form_title.setStyleSheet("font-weight: bold; color: #00E676; font-size: 12px;")
        form_lay.addWidget(form_title)

        row1 = QHBoxLayout()
        self.in_principle = QLineEdit()
        self.in_principle.setPlaceholderText("Principio derivado (ej: Lealtad vs Conveniencia, Límites firmes, Respeto mutuo)")
        row1.addWidget(QLabel("Principio:"))
        row1.addWidget(self.in_principle, stretch=1)
        form_lay.addLayout(row1)

        row2 = QHBoxLayout()
        self.in_situation = QLineEdit()
        self.in_situation.setPlaceholderText("Situación: ¿Qué ocurrió exactamente?")
        row2.addWidget(QLabel("Situación:"))
        row2.addWidget(self.in_situation, stretch=1)
        form_lay.addLayout(row2)

        row3 = QHBoxLayout()
        self.in_action = QLineEdit()
        self.in_action.setPlaceholderText("Acción tomada: ¿Qué hiciste tú?")
        row3.addWidget(QLabel("Acción:"))
        row3.addWidget(self.in_action, stretch=1)

        self.in_motive = QLineEdit()
        self.in_motive.setPlaceholderText("Motivo: ¿Por qué lo hiciste?")
        row3.addWidget(QLabel("Motivo:"))
        row3.addWidget(self.in_motive, stretch=1)
        form_lay.addLayout(row3)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        add_btn = QPushButton("+ Grabar Caso en Bóveda")
        add_btn.setProperty("class", "primary")
        add_btn.clicked.connect(self._save_case)
        btn_row.addWidget(add_btn)
        form_lay.addLayout(btn_row)

        layout.addWidget(form_frame)

        # Botón Cerrar
        footer_row = QHBoxLayout()
        footer_row.addStretch()
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        footer_row.addWidget(close_btn)
        layout.addLayout(footer_row)

    def _refresh_table(self):
        cases = self.memory.get_life_cases()
        self.table.setRowCount(0)
        for c in cases:
            row = self.table.rowCount()
            self.table.insertRow(row)

            id_item = QTableWidgetItem(str(c.get("id", "")))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, id_item)

            date_item = QTableWidgetItem(c.get("date", ""))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, date_item)

            princ_item = QTableWidgetItem(c.get("principle", ""))
            princ_item.setStyleSheet("color: #00E5FF; font-weight: bold;")
            self.table.setItem(row, 2, princ_item)

            sit_item = QTableWidgetItem(c.get("situation", ""))
            self.table.setItem(row, 3, sit_item)

            act_item = QTableWidgetItem(f"{c.get('action', '')} (Motivo: {c.get('motive', '')})")
            self.table.setItem(row, 4, act_item)

            del_btn = QPushButton("✕")
            del_btn.setStyleSheet("background-color: #3A1820; color: #FF4D6D; border: 1px solid #5A202A; font-size: 11px; padding: 2px 6px;")
            case_id = c.get("id")
            del_btn.clicked.connect(lambda checked, cid=case_id: self._delete_case(cid))
            self.table.setCellWidget(row, 5, del_btn)

    def _save_case(self):
        principle = self.in_principle.text().strip()
        situation = self.in_situation.text().strip()
        action = self.in_action.text().strip()
        motive = self.in_motive.text().strip()

        if not principle or not situation or not action:
            QMessageBox.warning(self, "Campos requeridos", "Por favor completa al menos el Principio, la Situación y la Acción tomada.")
            return

        self.memory.record_life_case(situation, action, motive, principle)
        self.in_principle.clear()
        self.in_situation.clear()
        self.in_action.clear()
        self.in_motive.clear()
        self._refresh_table()
        QMessageBox.information(self, "Caso Registrado", f"Caso '{principle}' guardado exitosamente en la Bóveda de Memoria.")

    def _delete_case(self, case_id: int):
        if self.memory.delete_life_case(case_id):
            self._refresh_table()
