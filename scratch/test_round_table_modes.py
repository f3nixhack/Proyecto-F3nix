import os
import sys
from typing import Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.memory_vault import MemoryVault
from core.multi_agent_council import MultiAgentCouncil, ROLES_CONFIG, DEBATE_MODES
from PyQt6.QtWidgets import QApplication

def test_1_debate_modes_catalog():
    print("=== TEST 1: Verificación de Catálogo de 10 Modos de Razonamiento ===")
    assert len(DEBATE_MODES) == 10, f"Se esperaban 10 modos, encontrados {len(DEBATE_MODES)}"
    
    expected_modes = [
        "clasico", "cisne_negro", "bifurcado", "sabios_salud",
        "sabios_codigo", "sabios_vida", "tribunal", "consenso_ciego",
        "socratico", "steelman"
    ]
    for mode_id in expected_modes:
        assert mode_id in DEBATE_MODES, f"Falta el modo {mode_id} en DEBATE_MODES"
        mode_data = DEBATE_MODES[mode_id]
        assert "name" in mode_data
        assert "short_name" in mode_data
        assert "icon" in mode_data
        assert "description" in mode_data
        assert "role_1" in mode_data
        assert "role_2" in mode_data
        assert "role_director" in mode_data
        assert mode_data["role_1"] in ROLES_CONFIG, f"Rol {mode_data['role_1']} no está en ROLES_CONFIG"
        assert mode_data["role_2"] in ROLES_CONFIG, f"Rol {mode_data['role_2']} no está en ROLES_CONFIG"
        print(f"  ✓ {mode_data['icon']} {mode_data['name']} [Roles: {mode_data['role_1']} vs {mode_data['role_2']}]")

    print("TEST 1 PASSED: Todos los 10 modos están perfectamente configurados.\n")

def test_2_system_prompts_for_all_roles():
    print("=== TEST 2: Generación de Prompts Personalizados para Todos los Roles ===")
    vault = MemoryVault()
    vault.set_user_identity(user_name="Fenix", user_gender="masculino", salutation="Comandante")
    council = MultiAgentCouncil(vault=vault)

    for mode_id, mode_data in DEBATE_MODES.items():
        r1 = mode_data["role_1"]
        r2 = mode_data["role_2"]
        rdir = mode_data["role_director"]
        
        prompt_1 = council.get_role_system_prompt(r1, mode=mode_id)
        prompt_2 = council.get_role_system_prompt(r2, mode=mode_id)
        prompt_dir = council.get_role_system_prompt(rdir, mode=mode_id)
        
        assert "Fenix" in prompt_1 or "Comandante" in prompt_1
        assert "REGLA DE CONCISIÓN Y RENDIMIENTO" in prompt_1
        assert "Fenix" in prompt_2 or "Comandante" in prompt_2
        assert "REGLA DE CONCISIÓN Y RENDIMIENTO" in prompt_2
        assert len(prompt_dir) > 100
        print(f"  ✓ Prompts validados para Modo: {mode_id}")

    print("TEST 2 PASSED: Todos los prompts se generan dinámicamente con cero humo y límites de concisión.\n")

def test_3_run_debate_with_mocked_ollama():
    print("=== TEST 3: Simulación de Debate en los 10 Modos Dialécticos ===")
    council = MultiAgentCouncil()
    
    # Mock _call_ollama to avoid needing live Ollama server during automated test
    calls_log = []
    def mock_call(model, system_prompt, prompt, on_token=None, is_cancelled=None):
        calls_log.append({"model": model, "prompt": prompt})
        reply = f"[Respuesta simulada de {model} para turno {len(calls_log)}]"
        if on_token:
            on_token("TokenChunk ")
        return reply

    council._call_ollama = mock_call

    for mode_id in DEBATE_MODES:
        calls_log.clear()
        results = council.run_debate(
            topic="¿Cómo estructurar mi nuevo proyecto?",
            models_per_role={"estratega": "llama3.2:3b", "critico": "qwen2.5:7b", "director": "llama3.1:8b"},
            rounds=2,
            mode=mode_id
        )
        assert results["mode"] == mode_id
        assert len(results["turns"]) >= 3 # Role 1 (R1), Role 2 (R1), ..., Director
        assert results["final_synthesis"] != ""
        print(f"  ✓ Debate completado con éxito en Modo: {mode_id} ({len(results['turns'])} turnos)")

    print("TEST 3 PASSED: El bucle de rondas dialécticas ejecutó los 10 modos sin errores.\n")

def test_4_studio_ui_mode_switching():
    print("=== TEST 4: Verificación de Interfaz F3NIX Studio y Conmutador de Modos ===")
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.f3nix_studio import F3nixStudio, CouncilWorker

    studio = F3nixStudio()
    assert studio.current_council_mode == "clasico"

    # Conmutar al modo Cisne Negro
    studio._set_council_mode("cisne_negro")
    assert studio.current_council_mode == "cisne_negro"
    assert "Cisne Negro" in studio.btn_pick_mode.text()
    assert "Cisne Negro" in studio.card_title_2.text()
    assert "Cisne Negro" in studio.btn_pick_critico.text()
    print("  ✓ Conmutación a Cisne Negro: chips, botones y tarjetas actualizados")

    # Conmutar a Futuros Bifurcados
    studio._set_council_mode("bifurcado")
    assert studio.current_council_mode == "bifurcado"
    assert "Sendero A" in studio.btn_pick_estratega.text()
    assert "Sendero B" in studio.btn_pick_critico.text()
    print("  ✓ Conmutación a Futuros Bifurcados: roles Sendero A / Sendero B actualizados")

    # Conmutar a Tribunal
    studio._set_council_mode("tribunal")
    assert studio.current_council_mode == "tribunal"
    assert "Defensor" in studio.btn_pick_estratega.text()
    assert "Fiscal" in studio.btn_pick_critico.text()
    print("  ✓ Conmutación a Tribunal Dialéctico: roles Defensor / Fiscal actualizados")

    # Conmutar a Sabios Salud
    studio._set_council_mode("sabios_salud")
    assert studio.current_council_mode == "sabios_salud"
    assert "Fisiólogo" in studio.btn_pick_estratega.text()
    assert "Traumatólogo" in studio.btn_pick_critico.text()
    print("  ✓ Conmutación a Sabios Salud: roles Fisiólogo / Traumatólogo actualizados")

    # Verificar CouncilWorker inicialización con modo
    worker = CouncilWorker(
        council=studio.council,
        topic="Mi consulta",
        models_per_role={"role_1": "llama3.2:3b"},
        rounds=1,
        mode="sabios_salud"
    )
    assert worker.mode == "sabios_salud"
    print("  ✓ CouncilWorker configurado correctamente con el modo seleccionado")

    print("TEST 4 PASSED: Interfaz gráfica y selectores sincronizados a la perfección.\n")

if __name__ == "__main__":
    print("\n=======================================================")
    print("🚀 EJECUTANDO SUITE DE PRUEBAS: 10 MODOS MESA REDONDA F3NIX")
    print("=======================================================\n")
    test_1_debate_modes_catalog()
    test_2_system_prompts_for_all_roles()
    test_3_run_debate_with_mocked_ollama()
    test_4_studio_ui_mode_switching()
    print("=======================================================")
    print("🎉 ¡TODAS LAS PRUEBAS PASARON AL 100% CON ÉXITO ROTUNDO!")
    print("=======================================================\n")
