import sys
import os
sys.path.insert(0, r"d:\Antigravity\Proyecto F3nix")
import unittest
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from ui.floating_avatar import FloatingAvatar

class TestAvatarCloseAndOpen(unittest.TestCase):
    def setUp(self):
        self.avatar = FloatingAvatar()

    def test_has_close_button(self):
        """Verifica que el avatar tenga un botón [✕] para cerrar el programa."""
        self.assertTrue(hasattr(self.avatar, "close_app_btn"))
        self.assertEqual(self.avatar.close_app_btn.text(), "✕")
        
        # Probar emisión de señal de cerrado
        quit_signals = []
        self.avatar.quit_requested.connect(lambda: quit_signals.append(True))
        self.avatar.close_app_btn.click()
        self.assertEqual(len(quit_signals), 1, "Hacer clic en [✕] debe emitir quit_requested.")

    def test_has_studio_button(self):
        """Verifica que el botón de Studio tenga el ícono 🏛️ y emita toggle_studio_requested."""
        self.assertTrue(hasattr(self.avatar, "studio_btn"))
        self.assertEqual(self.avatar.studio_btn.text(), "🏛️")
        
        studio_signals = []
        self.avatar.toggle_studio_requested.connect(lambda: studio_signals.append(True))
        self.avatar.studio_btn.click()
        self.assertEqual(len(studio_signals), 1, "Hacer clic en [🏛️] debe emitir toggle_studio_requested.")

    def test_double_click_opens_studio(self):
        """Verifica que hacer doble clic en el avatar emita toggle_studio_requested."""
        studio_signals = []
        self.avatar.toggle_studio_requested.connect(lambda: studio_signals.append(True))
        
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(50, 50),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        self.avatar.mouseDoubleClickEvent(event)
        self.assertEqual(len(studio_signals), 1, "Doble clic en el avatar debe abrir F3NIX Studio.")

if __name__ == "__main__":
    unittest.main()
