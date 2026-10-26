import os
import sys
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Agregar raíz del proyecto al path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.fenix_reasoning import FenixReasoningEngine, CONSTITUTION_DIR
from core.memory_vault import MemoryVault
from core.multi_agent_council import MultiAgentCouncil

def test_constitution_modules():
    print("=== Test 1: Carga de 10 Módulos de la Constitución Mental ===")
    engine = FenixReasoningEngine()
    meta = engine.get_constitution_metadata()
    print(f"Versión: {meta['version']}, Módulos cargados: {meta['modules_count']}")
    assert meta["modules_count"] == 10, f"Se esperaban 10 módulos, se encontraron {meta['modules_count']}"

    expected_modules = [
        "constitution", "core_values", "reasoning_engine",
        "ethics_and_relationships", "conflict_and_limits", "fighter_mindset",
        "communication", "epistemology", "case_studies", "evaluation"
    ]
    for mod in expected_modules:
        content = engine.get_module(mod)
        assert content, f"Módulo {mod} está vacío o no se cargó"
        assert len(content) > 100, f"Módulo {mod} es demasiado corto ({len(content)} caracteres)"
        print(f"  ✓ {mod}.md cargado ({len(content)} caracteres)")
    print("Test 1 completado exitosamente.\n")

def test_prompt_generation():
    print("=== Test 2: Generación de Prompts Constitucionales ===")
    engine = FenixReasoningEngine()
    prompt = engine.build_director_system_prompt(user_name="Fenix")
    assert "CONSTITUCIÓN MENTAL F3NIX" in prompt
    assert "Director Supremo" in prompt
    assert "PROTOCOLO DE CONFLICTO Y TRAICIÓN" in prompt
    assert "MENTALIDAD MARCIAL" in prompt
    print("  ✓ System Prompt del Director F3NIX validado correctamente.")

    delib = engine.build_deliberation_prompt("¿Debo asociarme con un inversor que exige control total?", user_name="Fenix")
    assert "MODELO DE TOMA DE DECISIONES F3NIX" in delib
    assert "STEELMAN" in delib
    assert "FILTRO ÉTICO Y DE RECIPROCIDAD" in delib
    print("  ✓ Deliberation Prompt (12 pasos) validado correctamente.\n")

def test_council_integration():
    print("=== Test 3: Integración en MultiAgentCouncil ===")
    vault = MemoryVault()
    council = MultiAgentCouncil(vault=vault)
    assert hasattr(council, "reasoning_engine")
    director_sys = council.get_role_system_prompt("director")
    assert "CONSTITUCIÓN MENTAL F3NIX" in director_sys
    print("  ✓ MultiAgentCouncil instancia el motor y provee el prompt constitucional al Director.\n")

def test_memory_vault_life_cases():
    print("=== Test 4: Registro y Recuperación de Casos de Vida en MemoryVault ===")
    vault = MemoryVault()
    test_case = vault.record_life_case(
        situation="Propuesta de negocio dudosa con dinero rápido",
        action="Rechazo inmediato y preservación del principio",
        motive="La palabra y la honestidad no se negocian por conveniencia",
        principle="Honestidad y dignidad sobre conveniencia"
    )
    assert test_case.get("id"), "El caso debe tener un ID asignado"
    assert test_case.get("principle") == "Honestidad y dignidad sobre conveniencia"
    print(f"  ✓ Caso grabado con ID: {test_case['id']}")

    cases = vault.get_life_cases()
    assert any(c.get("id") == test_case["id"] for c in cases)
    print(f"  ✓ Total de casos empíricos en memoria: {len(cases)}")

    ctx = vault.get_memory_context()
    assert "Casos empíricos de vida aprendidos:" in ctx
    assert "Honestidad y dignidad sobre conveniencia" in ctx
    print("  ✓ Caso reflejado correctamente en el contexto inyectado de memoria.")

    # Limpiar caso de prueba
    deleted = vault.delete_life_case(test_case["id"])
    assert deleted, "El caso de prueba debe poder eliminarse"
    print("  ✓ Caso de prueba limpiado exitosamente.\n")

def test_eight_scenarios_calibration():
    print("=== Test 5: Verificación de los 8 Escenarios Canónicos (Sección 18) ===")
    engine = FenixReasoningEngine()
    for sid in range(1, 9):
        case = engine.evaluate_test_scenario(sid)
        assert case, f"Escenario {sid} no encontrado"
        assert "name" in case and "prompt" in case and "expected" in case
        print(f"  Escenario {sid}: [{case['name']}] -> Regla: {case['expected']}")
    print("Test 5 completado exitosamente: Los 8 escenarios canónicos están calibrados.\n")

def test_ui_components_headless():
    print("=== Test 6: Verificación de Componentes UI (Headless) ===")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from ui.constitution_dialog import ConstitutionDialog
    from ui.life_case_dialog import LifeCaseDialog
    from ui.f3nix_studio import F3nixStudio

    vault = MemoryVault()

    # Probar diálogo constitucional
    c_dialog = ConstitutionDialog()
    assert c_dialog.module_list.count() == 10
    c_dialog.module_list.setCurrentRow(1)
    assert "Valores Fundamentales" in c_dialog.module_header_lbl.text()
    print("  ✓ ConstitutionDialog creado y 10 módulos navegables.")

    # Probar diálogo de casos de vida
    lc_dialog = LifeCaseDialog(vault)
    assert hasattr(lc_dialog, "table")
    print("  ✓ LifeCaseDialog creado con tabla y formulario interactivo.")

    # Probar F3nixStudio con los nuevos botones
    studio = F3nixStudio(memory_vault=vault)
    assert hasattr(studio, "btn_life_cases")
    assert hasattr(studio, "combo_director")
    print("  ✓ F3nixStudio inicializado correctamente con botones e indicadores constitucionales.\n")

if __name__ == "__main__":
    test_constitution_modules()
    test_prompt_generation()
    test_council_integration()
    test_memory_vault_life_cases()
    test_eight_scenarios_calibration()
    test_ui_components_headless()
    print("🎉 ¡TODOS LOS TESTS DE LA CONSTITUCIÓN F3NIX v1.0 PASARON EXITOSAMENTE!")
