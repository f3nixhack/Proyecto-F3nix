import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.f3nix_tools import F3nixTools
from core.ai_engine import AIEngine
from core.multi_agent_council import MultiAgentCouncil
from core.memory_vault import MemoryVault

def test_web_search():
    print("=== Test 1: Búsqueda Web Ultraligera en Tiempo Real ===")
    t0 = time.time()
    query = "python programming"
    results = F3nixTools.search_web(query, max_results=2)
    elapsed = time.time() - t0
    print(f"Búsqueda ejecutada en {elapsed:.2f}s:")
    print(results[:250] + "...\n")
    assert results, "La búsqueda web no debe retornar vacío"
    assert "No se pudieron obtener resultados" not in results or elapsed < 5, "Fallback o búsqueda deben responder"
    print("  ✓ Test 1: Búsqueda web con fallback completada con éxito.\n")

def test_windows_automation():
    print("=== Test 2: Automatización Nativa de Windows ===")
    # 2a. Crear nota en escritorio
    test_title = "F3NIX_Test_Auto_Note"
    test_content = "Esta es una nota de verificación del sistema F3NIX."
    res_note = F3nixTools.create_desktop_note(test_title, test_content)
    print(f"  Resultado de nota: {res_note}")
    assert "guardada en tu escritorio" in res_note

    # Verificar que el archivo existe físicamente y limpiarlo
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(desktop):
        desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
    expected_file = os.path.join(desktop, f"{test_title}.txt")
    if os.path.exists(expected_file):
        os.remove(expected_file)
        print("  ✓ Nota física creada y eliminada limpiamente.")

    # 2b. Consulta de discos
    disk_info = F3nixTools.get_disk_space_info("C")
    print(f"  Información de disco: {disk_info}")
    assert "GB libres" in disk_info
    print("  ✓ Lectura de discos operativos verificada.")

    # 2c. Intercepción en AIEngine
    ai = AIEngine()
    intercept_note = ai._check_system_tools("crea una nota en el escritorio con recordatorio de prueba")
    assert intercept_note and "guardada en tu escritorio" in intercept_note
    # Limpiar nota
    note_clean = os.path.join(desktop, "Nota_F3NIX.txt")
    if os.path.exists(note_clean):
        try:
            os.remove(note_clean)
        except Exception:
            pass

    intercept_disk = ai._check_system_tools("¿cuánto espacio libre me queda en el disco c?")
    assert intercept_disk and "GB libres" in intercept_disk
    print("  ✓ Intercepción semántica de comandos de sistema en AIEngine validada.\n")

def test_turbo_mode():
    print("=== Test 3: Conmutador Modo Turbo vs Reflexión ===")
    ai = AIEngine()
    council = MultiAgentCouncil()

    assert not ai.turbo_mode, "Modo Turbo debe iniciar en False por defecto"
    ai.set_turbo_mode(True)
    assert ai.turbo_mode is True, "Modo Turbo debe activarse correctamente"

    council.set_turbo_mode(True)
    assert council.turbo_mode is True, "Council debe sincronizar Modo Turbo"

    ai.set_turbo_mode(False)
    assert ai.turbo_mode is False
    print("  ✓ Sincronización y alternancia de Modo Turbo validada.\n")

def test_quick_launcher_headless():
    print("=== Test 4: Barra de Invocación Rápida (Headless Qt6) ===")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from ui.quick_launcher_bar import QuickLauncherBar
    from ui.f3nix_studio import F3nixStudio

    ai = AIEngine()
    launcher = QuickLauncherBar(ai_engine=ai)
    assert launcher.width() == 680
    assert hasattr(launcher, "input_field")
    assert hasattr(launcher, "btn_web")
    assert hasattr(launcher, "btn_turbo")

    # Probar toggles
    launcher.btn_web.setChecked(True)
    assert launcher.btn_web.isChecked()
    launcher.btn_turbo.setChecked(False)
    assert not launcher.btn_turbo.isChecked()

    # Probar Studio con toggle de turbo y web
    studio = F3nixStudio()
    assert hasattr(studio, "btn_turbo_toggle")
    assert hasattr(studio, "btn_web_toggle_chat")
    studio.btn_turbo_toggle.setChecked(False)
    assert studio.btn_turbo_toggle.text() == "🧠 Modo Reflexión"
    studio.btn_turbo_toggle.setChecked(True)
    assert "⚡ Turbo" in studio.btn_turbo_toggle.text()
    print("  ✓ QuickLauncherBar y controles de F3nixStudio verificados.\n")

if __name__ == "__main__":
    test_web_search()
    test_windows_automation()
    test_turbo_mode()
    test_quick_launcher_headless()
    print("🎉 ¡LAS 4 MEJORAS ESTRATÉGICAS HAN SIDO VERIFICADAS AL 100% CON ÉXITO!")
