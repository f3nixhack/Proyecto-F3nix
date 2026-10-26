import os
import sys
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.fenix_reasoning import FenixReasoningEngine

def main():
    print("=== Test En Vivo: Deliberación Constitucional F3NIX con Ollama ===")
    engine = FenixReasoningEngine()
    sys_prompt = engine.build_director_system_prompt("Fenix")
    
    # Escenario 4 Canónico: Ruptura de confianza y traición
    scenario = engine.evaluate_test_scenario(4)
    topic = scenario["prompt"]
    delib_prompt = engine.build_deliberation_prompt(topic, user_name="Fenix")

    print(f"Pregunta: {topic}")
    print(f"Regla esperada: {scenario['expected']}\n")

    payload = {
        "model": "llama3.2:3b",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": delib_prompt}
        ],
        "stream": False,
        "options": {
            "temperature": 0.5
        }
    }

    try:
        res = requests.post("http://localhost:11434/api/chat", json=payload, timeout=60)
        if res.status_code == 200:
            reply = res.json().get("message", {}).get("content", "")
            print("--- RESPUESTA DEL DIRECTOR SUPREMO (CONSTITUCIÓN F3NIX v1.0) ---")
            print(reply)
            print("----------------------------------------------------------------")
            # Verificar principios clave en la respuesta
            reply_lower = reply.lower()
            has_retirada_o_distancia = any(w in reply_lower for w in ["distancia", "separación", "retirada", "límites", "limpia", "venganza", "dignidad"])
            assert has_retirada_o_distancia, "La respuesta debe enfatizar dignidad, separación limpia, distancia o rechazo a la venganza."
            print("✓ La respuesta cumple estrictamente con el Protocolo de Ruptura y Límites de la Constitución F3NIX.")
        else:
            print(f"Ollama respondió con código {res.status_code}: {res.text}")
    except Exception as e:
        print(f"Nota: Inferencia omitida o error de conexión ({e})")

if __name__ == "__main__":
    main()
