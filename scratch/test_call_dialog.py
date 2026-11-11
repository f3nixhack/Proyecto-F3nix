import sys
import os
import time

# Agregar directorio raíz
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.voice_listener import VoiceListener
from core.ai_engine import AIEngine
from PyQt6.QtWidgets import QApplication

def test_anti_echo():
    print("--- Probando Filtro Anti-Eco de ChoferPro ---")
    listener = VoiceListener()
    
    # 1. Caso Base: el asistente acaba de decir una frase
    assistant_phrase = "Hola, qué hacés che, todo bien por ahí?"
    listener.set_last_assistant_speech(assistant_phrase)
    
    # Audio del mic capturó eco exacto o casi exacto de los parlantes
    echo_input_1 = "hola que haces che"
    assert listener.is_echo(echo_input_1) is True, f"Fallo: '{echo_input_1}' debió ser detectado como eco."
    print("  ✓ Eco de subcadena detectado correctamente.")

    # Audio del mic capturó solapamiento significativo (> 35%)
    echo_input_2 = "todo bien por ahi amigo"
    assert listener.is_echo(echo_input_2) is True, f"Fallo: '{echo_input_2}' debió ser detectado como eco."
    print("  ✓ Eco por porcentaje de solapamiento detectado correctamente.")

    # Audio del mic es una frase genuina del usuario completamente diferente
    user_speech = "Abre Visual Studio Code y crea un archivo de python"
    assert listener.is_echo(user_speech) is False, f"Fallo: '{user_speech}' NO debió ser detectado como eco."
    print("  ✓ Frase genuina del usuario admitida sin falso positivo.")

def test_tones_and_prompts():
    print("\n--- Probando Personalidades y Tonos en Caliente ---")
    ai = AIEngine()
    ai.set_friend_mode(True)

    # 1. Tono Amigo
    ai.set_call_tone("amigo")
    p_amigo = ai._build_call_personality_prompt("Miguel", "[MEMORIA]: datos")
    assert "COLEGA AMIGO" in p_amigo
    assert "relajado, empático" in p_amigo
    print("  ✓ Tono 'amigo' verificado con éxito.")

    # 2. Tono Sin Filtro
    ai.set_call_tone("sin_filtro")
    p_filtro = ai._build_call_personality_prompt("Miguel", "[MEMORIA]: datos")
    assert "SIN FILTRO / HUMOR ÁCIDO" in p_filtro
    assert "directo al hueso" in p_filtro
    print("  ✓ Tono 'sin_filtro' verificado con éxito.")

    # 3. Tono Director
    ai.set_call_tone("director")
    p_director = ai._build_call_personality_prompt("Miguel", "[MEMORIA]: datos")
    assert "DIRECTOR ESTRATÉGICO" in p_director
    assert "asesor ejecutivo senior" in p_director
    print("  ✓ Tono 'director' verificado con éxito.")

def test_call_dialog_ui():
    print("\n--- Probando Instanciación de F3nixCallDialog ---")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv)
    
    from ui.call_dialog import F3nixCallDialog
    dialog = F3nixCallDialog(current_tone="amigo", hands_free=True)
    assert dialog is not None
    assert dialog.current_tone == "amigo"
    assert dialog.hands_free is True
    
    # Probar actualización de transcripciones
    dialog.update_user_speech("Hola F3NIX")
    assert "Hola F3NIX" in dialog.user_bubble.text()
    
    dialog.update_assistant_speech("Qué hacés che!", is_final=True)
    assert "Qué hacés che!" in dialog.assistant_bubble.text()
    
    # Probar ciclado de tonos
    dialog._cycle_tone()
    assert dialog.current_tone == "sin_filtro"
    dialog._cycle_tone()
    assert dialog.current_tone == "director"
    dialog._cycle_tone()
    assert dialog.current_tone == "amigo"
    print("  ✓ Ciclado de tonos en UI verificado.")

    dialog.end_call()
    print("  ✓ F3nixCallDialog instanciado y cerrado correctamente.")

if __name__ == "__main__":
    test_anti_echo()
    test_tones_and_prompts()
    test_call_dialog_ui()
    print("\n✅ TODAS LAS PRUEBAS DE LLAMADA VOZ A VOZ PASARON EXITOSAMENTE.")
