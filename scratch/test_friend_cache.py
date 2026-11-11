import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.instant_cache import InstantCache
from core.ai_engine import AIEngine

def test_cache():
    print("--- Probando Caché Inmediato en Modo Amigo / Llamada ---")
    ai = AIEngine()
    ai.set_friend_mode(True)
    
    for tone in ["amigo", "sin_filtro", "director"]:
        ai.set_call_tone(tone)
        t0 = time.time()
        # Generar respuesta para 'hola'
        chunks = list(ai.chat_stream("hola"))
        elapsed = time.time() - t0
        assert len(chunks) > 0, "No devolvió chunks"
        full_text = [c.get("content", "") for c in chunks if c.get("type") == "token"]
        assert len(full_text) > 0, "No devolvió texto de respuesta"
        reply = "".join(full_text)
        print(f"  ✓ [{tone.upper()}] Respuesta inmediata en {elapsed*1000:.2f}ms: '{reply}'")
        assert elapsed < 0.1, f"Fallo: El saludo tardó {elapsed:.3f}s (debía ser < 0.1s)"

if __name__ == "__main__":
    test_cache()
    print("\n✅ TODAS LAS PRUEBAS DE CACHÉ INMEDIATO PASARON AL 100%.")
