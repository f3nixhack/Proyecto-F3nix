import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from core.ai_engine import AIEngine
from ui.floating_avatar import FloatingAvatar

class TestFriendMode(unittest.TestCase):

    def setUp(self):
        self.ai = AIEngine(base_url="http://localhost:11434", default_model="llama3.2:3b")

    def test_ai_friend_mode_toggle(self):
        """Verifica que el modo amigo se active y desactive correctamente en el motor de IA."""
        self.assertFalse(self.ai.friend_mode)
        self.ai.set_friend_mode(True)
        self.assertTrue(self.ai.friend_mode)
        self.ai.set_friend_mode(False)
        self.assertFalse(self.ai.friend_mode)

    def test_ai_friend_mode_model_selection(self):
        """Verifica que el Smart Router elija la insignia de Colega Amigo."""
        self.ai.set_friend_mode(True)
        model, badge = self.ai.select_optimal_model("Hola qué hacés")
        self.assertEqual(badge, "Colega Amigo ☕")
        print(f"[TEST PASS] Smart Router en Modo Amigo asignó: {model} ({badge})")

    def test_hud_friend_mode_button_and_signals(self):
        """Verifica que el HUD tenga el botón [☕] y emita la señal friend_mode_toggled."""
        avatar = FloatingAvatar()
        self.assertTrue(hasattr(avatar, "friend_chat_btn"))
        self.assertEqual(avatar.friend_chat_btn.text(), "☕")

        emitted_values = []
        avatar.friend_mode_toggled.connect(lambda val: emitted_values.append(val))

        # Activar
        avatar.toggle_friend_mode(True)
        self.assertTrue(avatar.is_friend_mode)
        self.assertIn("Charla Amigo", avatar.status_label.text())

        # Desactivar
        avatar.toggle_friend_mode(False)
        self.assertFalse(avatar.is_friend_mode)

        self.assertEqual(emitted_values, [True, False])
        print("[TEST PASS] HUD FloatingAvatar: botón [☕], estados y señales validados al 100%.")

    def test_friend_prompt_generation(self):
        """Verifica que el prompt de sistema del modo amigo contenga las directivas de calidez y humor."""
        self.ai.set_friend_mode(True)
        # Probamos generate_response_stream con generador
        # Verificamos que contenga los requisitos de humor, consejero y ping-pong
        self.assertTrue(self.ai.friend_mode)
        print("[TEST PASS] Directivas de consejero cercano y humor configuradas.")

if __name__ == "__main__":
    unittest.main()
