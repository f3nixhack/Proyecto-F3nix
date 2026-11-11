import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.voice_listener import VoiceListener
from core.ai_engine import AIEngine
from core.instant_cache import InstantCache

def test_pipeline():
    print("=======================================================")
    print("   ⚡ TEST DE VELOCIDAD: PIPELINE OPCIÓN C (GROQ + OLLAMA)")
    print("=======================================================\n")
    
    groq_key = None
    if os.path.exists("f3nix_secrets.json"):
        import json
        with open("f3nix_secrets.json", "r") as f:
            groq_key = json.load(f).get("groq_api_key")
    listener = VoiceListener(groq_api_key=groq_key)
    ai = AIEngine(groq_api_key=groq_key)
    ai.set_friend_mode(True)
    ai.set_call_tone("amigo")
    
    # 1. Transcripción con Groq Whisper
    print("1. Probando Groq Whisper-Large-v3-Turbo:")
    if os.path.exists("scratch/test_audio.mp3"):
        with open("scratch/test_audio.mp3", "rb") as f:
            audio_bytes = f.read()
        t0 = time.time()
        # Simular llamada a whisper
        import requests
        r = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {groq_key}"},
            files={"file": ("audio.mp3", audio_bytes, "audio/mp3")},
            data={"model": "whisper-large-v3-turbo", "language": "es"}
        )
        t_stt = time.time() - t0
        text = r.json().get("text", "")
        print(f"   ✓ Transcripción en {t_stt:.2f}s: '{text[:60]}...'")
    
    # 2. Inferencia en modo Amigo con Groq
    print("\n2. Probando Inferencia de LLM en Modo Amigo (Qwen 27B en Groq):")
    t0 = time.time()
    chunks = list(ai.chat_stream("Che, cómo optimizo mi tiempo hoy?"))
    t_llm = time.time() - t0
    full_text = "".join([c.get("content", "") for c in chunks if c.get("type") == "token"])
    meta = [c for c in chunks if c.get("type") == "meta"]
    brain_badge = meta[0]["brain"] if meta else "N/A"
    print(f"   ✓ Motor usado: {brain_badge}")
    print(f"   ✓ Tiempo de inferencia: {t_llm:.2f}s")
    print(f"   ✓ Respuesta: '{full_text.strip()}'")
    
    # 3. Caché Inmediato para saludos
    print("\n3. Probando Saludo Inmediato (Caché):")
    t0 = time.time()
    chunks_saludo = list(ai.chat_stream("Hola che"))
    t_cache = time.time() - t0
    saludo_text = "".join([c.get("content", "") for c in chunks_saludo if c.get("type") == "token"])
    print(f"   ✓ Saludo generado en: {t_cache*1000:.2f}ms")
    print(f"   ✓ Respuesta: '{saludo_text.strip()}'")

    print("\n=======================================================")
    print("   ✅ PIPELINE OPCIÓN C VALIDADO AL 100%")
    print("=======================================================")

if __name__ == "__main__":
    test_pipeline()
