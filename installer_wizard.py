import sys
import os
import subprocess
import shutil
import requests

BANNER = r"""
============================================================
           PROYECTO F3NIX - ASISTENTE DE IA LOCAL           
============================================================
  Avatar Flotante | Push-to-Talk (F12) | Voz TTS | Ollama  
============================================================
"""

RECOMMENDED_MODELS = [
    {
        "name": "llama3.1:8b",
        "tag": "llama3.1",
        "desc": "El modelo insignia de Meta. Gran balance general y excelente español.",
        "vram": "~5 GB VRAM / 8 GB RAM"
    },
    {
        "name": "qwen2.5-coder:7b",
        "tag": "qwen2.5-coder",
        "desc": "El mejor modelo gratuito para programar, depurar y crear código.",
        "vram": "~5 GB VRAM / 8 GB RAM"
    },
    {
        "name": "hermes3:8b",
        "tag": "hermes3",
        "desc": "Especializado en agentes, enrutamiento entre IAs y llamadas a funciones.",
        "vram": "~5.5 GB VRAM / 8 GB RAM"
    },
    {
        "name": "phi4:14b",
        "tag": "phi4",
        "desc": "Lo último de Microsoft en razonamiento matemático y lógica profunda.",
        "vram": "~9 GB VRAM / 16 GB RAM"
    },
    {
        "name": "llama3.2:3b",
        "tag": "llama3.2",
        "desc": "Ultraligero y ultra veloz. Ideal para laptops sin tarjeta gráfica.",
        "vram": "~2.5 GB VRAM / 4 GB RAM"
    }
]

def check_ollama_installed() -> bool:
    return shutil.which("ollama") is not None

def check_ollama_running() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def get_installed_models():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            return [m.get("name") for m in r.json().get("models", [])]
    except Exception:
        pass
    return []

def main():
    print(BANNER)

    print("[*] Comprobando entorno del sistema...")
    if not check_ollama_installed():
        print("\n[!] ALERTA: No se detectó Ollama en tu PATH.")
        print("    Descárgalo e instálalo gratis desde: https://ollama.com")
        input("\nPresiona ENTER cuando lo hayas instalado para reintentar...")
        if not check_ollama_installed():
            print("[X] No se pudo encontrar Ollama. Saliendo...")
            return

    print("[OK] Ollama está instalado en el sistema.")

    if not check_ollama_running():
        print("[*] Iniciando servicio de Ollama en segundo plano...")
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import time
            time.sleep(2)
        except Exception as e:
            print(f"[!] No se pudo iniciar automáticamente: {e}")

    if check_ollama_running():
        print("[OK] Servidor local de Ollama está activo (http://localhost:11434).\n")
    else:
        print("[!] Advertencia: No se pudo verificar la API de Ollama. Asegúrate de tener la app abierta.")

    while True:
        installed = get_installed_models()
        print("------------------------------------------------------------")
        print("MODELOS INSTALADOS ACTUALMENTE:")
        if installed:
            for i, m in enumerate(installed, 1):
                print(f"  [{i}] {m}")
        else:
            print("  (Ningún modelo descargado todavía)")
        print("------------------------------------------------------------")

        print("\n¿Qué deseas hacer?")
        print(" 1. Descargar un modelo recomendado (Llama 3.1, Qwen Coder, Hermes 3...)")
        print(" 2. Compilar la personalidad de F3nix (Modelfile -> thruster_ai)")
        print(" 3. Probar una consulta rápida a la IA")
        print(" 4. Iniciar Asistente F3nix (HUD flotante + Voz F12)")
        print(" 5. Salir")

        choice = input("\nElige una opción (1-5): ").strip()

        if choice == "1":
            print("\nCATÁLOGO DE MODELOS RECOMENDADOS:")
            for idx, item in enumerate(RECOMMENDED_MODELS, 1):
                print(f"  {idx}. {item['name']} ({item['vram']})")
                print(f"     -> {item['desc']}")
            print("  0. Cancelar")

            sub = input("\nSelecciona el modelo a descargar: ").strip()
            if sub.isdigit() and 1 <= int(sub) <= len(RECOMMENDED_MODELS):
                target = RECOMMENDED_MODELS[int(sub) - 1]["tag"]
                print(f"\n[*] Descargando '{target}' mediante Ollama (esto puede tardar según tu conexión)...")
                subprocess.run(["ollama", "pull", target])
                print("\n[OK] Modelo listo.")
            input("\nPresiona ENTER para continuar...")

        elif choice == "2":
            if not os.path.exists("Modelfile"):
                print("[X] No se encontró el archivo Modelfile en esta carpeta.")
            else:
                print("\n[*] Creando el modelo 'thruster_ai' con la personalidad de F3nix...")
                subprocess.run(["ollama", "create", "thruster_ai", "-f", "Modelfile"])
                print("\n[OK] Modelo 'thruster_ai' configurado exitosamente.")
            input("\nPresiona ENTER para continuar...")

        elif choice == "3":
            if not installed:
                print("\n[!] No tienes modelos instalados. Descarga uno primero con la opción 1.")
            else:
                model_name = "thruster_ai" if "thruster_ai:latest" in installed or "thruster_ai" in installed else installed[0]
                prompt = input(f"\nEscribe una pregunta para probar [{model_name}]: ").strip()
                if prompt:
                    print(f"[*] Consultando a {model_name}...")
                    from core.ai_engine import AIEngine
                    engine = AIEngine(default_model=model_name)
                    ans = engine.chat(prompt)
                    print(f"\nRespuesta:\n{ans}\n")
            input("\nPresiona ENTER para continuar...")

        elif choice == "4":
            print("\n[*] Iniciando Proyecto F3nix...")
            subprocess.Popen([sys.executable, "thruster.py"])
            print("[OK] Asistente lanzado. Revisa tu pantalla para ver el HUD flotante.")
            break

        elif choice == "5":
            print("\n¡Hasta luego!")
            break

if __name__ == "__main__":
    main()
