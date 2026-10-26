import sys
import os
sys.path.insert(0, r"d:\Antigravity\Proyecto F3nix")
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from ui.f3nix_studio import F3nixStudio

class TestSmartAvatarLifecycle(unittest.TestCase):
    def setUp(self):
        self.mock_vault = MagicMock()
        vault_data = {
            "user_name": "Fenix", "salutation": "Comandante",
            "role": "Líder", "user_gender": "male", "gender": "male",
            "tone_preference": "Técnico", "preferred_voice": "es-MX-JorgeNeural",
            "facts": [], "life_cases": [], "profile": {}, "permanent_rules": [],
            "custom_instructions": "", "active_tasks": [], "completed_tasks": [],
            "recent_context": []
        }
        self.mock_vault.data = vault_data
        self.mock_vault._load.return_value = vault_data
        self.mock_vault.get_user_name.return_value = "Fenix"
        self.mock_vault.get_user_gender.return_value = "male"
        self.mock_vault.get_grammar_pronouns.return_value = {
            "welcome": "Bienvenido", "user": "usuario", "boss": "jefe", "president": "Presidente"
        }
        self.mock_vault.get_salutation.return_value = "Comandante"
        self.mock_vault.get_mental_constitution_prompt.return_value = "Constitución"

        self.mock_council = MagicMock()
        self.mock_speaker = MagicMock()
        self.mock_speaker.is_speaking = False
        self.mock_speaker.current_voice = "es-MX-JorgeNeural"

        self.studio = F3nixStudio(
            memory_vault=self.mock_vault,
            rag=MagicMock(),
            council=self.mock_council,
            speaker=self.mock_speaker
        )

    def test_studio_emits_window_closed_on_close(self):
        """Verifica que F3nixStudio emita window_closed al cerrarse."""
        signal_received = []
        self.studio.window_closed.connect(lambda: signal_received.append(True))
        self.studio.close()
        self.assertTrue(len(signal_received) > 0, "F3nixStudio debe emitir window_closed al cerrarse.")

    def test_toggle_studio_logic(self):
        """Simula la lógica de alternancia inteligente de thruster.py."""
        mock_hud = MagicMock()
        mock_hud.isVisible.return_value = True

        # Estado inicial: Studio oculto, HUD visible
        self.studio.hide()

        # Simular toggle_studio hacia visible
        if self.studio.isVisible():
            self.studio.hide()
            mock_hud.show()
        else:
            mock_hud.hide()
            self.studio.show()

        mock_hud.hide.assert_called_once()
        self.assertTrue(self.studio.isVisible())

        # Ahora simular cerrar Studio: debe restaurar el HUD
        def on_studio_closed():
            mock_hud.show()

        self.studio.window_closed.connect(on_studio_closed)
        self.studio.close()
        mock_hud.show.assert_called_once()

if __name__ == "__main__":
    unittest.main()
