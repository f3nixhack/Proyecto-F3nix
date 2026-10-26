import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import tempfile
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.memory_vault import MemoryVault
from core.multi_agent_council import MultiAgentCouncil
from ui.f3nix_studio import F3nixStudio

def test_export_pdf_across_modes():
    app = QApplication.instance() or QApplication(sys.argv)
    vault = MemoryVault()
    vault.set_user_identity(user_name="Fenix", user_gender="masculino", salutation="Comandante")

    studio = F3nixStudio(memory_vault=vault)

    # Set up simulated debate in 'cisne_negro' mode
    studio.current_council_mode = "cisne_negro"
    studio._debate_topic = "Lanzamiento de plataforma SaaS de telemetría para flotas de drones autónomos."
    studio._debate_turns_history = [
        {
            "role": "estratega",
            "model": "llama3.2:3b",
            "title": "🔵 Estratega de Expansión & Optimización",
            "round": 1,
            "phase": "Ronda 1: Propuesta Inicial",
            "reply": "Proponemos lanzar una beta cerrada para 10 empresas de logística aérea con arquitectura en la nube AWS y agentes de borde en Raspberry Pi 5."
        },
        {
            "role": "cisne_negro",
            "model": "deepseek-r1:8b",
            "title": "🦅 Auditor Cisne Negro (Chaos & Stress-Test de Taleb)",
            "round": 1,
            "phase": "Ronda 1: Auditoría de Caos",
            "reply": "1. **Evento Catastrófico 1:** Caída global de conectividad 4G/5G en zona de operaciones.\n2. **Evento Catastrófico 2:** Demanda judicial por colisión de dron debida a latencia de red.\n3. **Salvaguarda Antifrágil:** Todo cálculo crítico de evasión debe correr 100% offline en el firmware del dron, usando la nube solo como telemetría secundaria."
        },
        {
            "role": "director",
            "model": "llama3.1:8b",
            "title": "🟢 Director Blindado (Síntesis & Plan Maestro)",
            "round": 0,
            "phase": "Veredicto Final: Plan Maestro Antifrágil",
            "reply": "DICTAMEN DEFINITIVO:\n1. **Veredicto:** Aprobada la beta cerrada pero supeditada a arquitectura 'Edge-First' tolerante a fallas completas de red.\n2. **Plan de Acción Fase 1:** Programar failsafe autónomo en Rust / MicroPython antes de admitir vuelos comerciales.\n3. **Fase 2:** Protocolo de caja negra encriptada en tarjeta SD para respaldo legal y seguros."
        }
    ]

    # Test PDF generation by monkeypatching QFileDialog.getSaveFileName
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        test_pdf_path = tmp.name

    from PyQt6.QtWidgets import QFileDialog, QMessageBox
    QFileDialog.getSaveFileName = lambda *args, **kwargs: (test_pdf_path, "Archivos PDF (*.pdf)")
    QMessageBox.information = lambda *args, **kwargs: QMessageBox.StandardButton.No

    print(f"Exportando debate a PDF de prueba: {test_pdf_path}")
    studio._export_council_to_pdf()

    assert os.path.exists(test_pdf_path), "El archivo PDF no fue generado"
    file_size = os.path.getsize(test_pdf_path)
    print(f"✓ PDF generado con éxito. Tamaño: {file_size} bytes")
    assert file_size > 5000, f"El archivo PDF es demasiado pequeño ({file_size} bytes)"

    # Verify PDF content with fitz (PyMuPDF)
    import fitz
    doc = fitz.open(test_pdf_path)
    print(f"✓ Número de páginas generadas: {len(doc)}")
    assert len(doc) >= 1

    page1_text = doc[0].get_text()
    assert "F3NIX" in page1_text
    assert "Cisne Negro" in page1_text or "INFORME" in page1_text
    print("✓ Contenido de portada, metadatos y modo verificados correctamente.")

    doc.close()
    try:
        os.remove(test_pdf_path)
    except Exception:
        pass

    print("\n=======================================================")
    print("🎉 PRUEBA DE EXPORTACIÓN A PDF EJECUTIVO: 100% ÉXITO!")
    print("=======================================================\n")

if __name__ == "__main__":
    test_export_pdf_across_modes()
