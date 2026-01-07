
import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock modules
sys.modules['whisperlayer.audio'] = MagicMock()
sys.modules['whisperlayer.hotkey'] = MagicMock()
sys.modules['sounddevice'] = MagicMock()
sys.modules['ydotool'] = MagicMock()

# Mock settings module
class MockSettings:
    def __init__(self):
        self.disabled_commands = []
        self.builtin_overrides = {}
        self.custom_commands = []
        self.ollama_enabled = True
        self.ollama_model = "test"

settings_mock = MagicMock()
settings_mock.get_settings = lambda: MockSettings()
sys.modules['whisperlayer.settings'] = settings_mock

from whisperlayer.commands import VoiceCommandDetector

class TestMacros(unittest.TestCase):
    def setUp(self):
        self.detector = VoiceCommandDetector()
        
        # Mock low-level output methods
        self.detector._type_key = MagicMock()
        self.detector._type_text = MagicMock()
        
        # Register a dummy command for referencing
        self.detector.register("dummy", lambda arg="": print(f"Dummy called with {arg}"), requires_content=True)

    def test_macro_plain_text(self):
        self.detector._execute_macro("Hello World")
        self.detector._type_text.assert_called_with("Hello World")

    def test_macro_keys(self):
        self.detector._execute_macro("<ctrl+c>")
        self.detector._type_key.assert_called_with("ctrl+c")
        
    def test_macro_mixed(self):
        self.detector._execute_macro("Copying <ctrl+c> now")
        # Should call type_text("Copying "), type_key("ctrl+c"), type_text(" now")
        # Note: Order matters.
        calls = []
        self.detector._type_text.side_effect = lambda x: calls.append(f"text:{x}")
        self.detector._type_key.side_effect = lambda x: calls.append(f"key:{x}")
        
        self.detector._execute_macro("Copying <ctrl+c> now")
        
        self.assertEqual(calls, ["text:Copying ", "key:ctrl+c", "text: now"])

    def test_macro_command_ref(self):
        # Mock action for dummy
        dummy_action = MagicMock()
        self.detector.commands["dummy"].action = dummy_action
        
        self.detector._execute_macro("@dummy[test arg]")
        dummy_action.assert_called_with("test arg")
        
    def test_macro_content_placeholder(self):
        # Test {content} substitution
        calls = []
        self.detector._type_text.side_effect = lambda x: calls.append(f"text:{x}")
        
        self.detector._execute_macro("You said: {content}", content="Banana")
        self.assertEqual(calls, ["text:You said: Banana"])

if __name__ == '__main__':
    unittest.main()
