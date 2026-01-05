"""Simplified Settings GUI for WhisperLayer using GTK3."""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from .settings import get_settings, AVAILABLE_MODELS, AVAILABLE_MODEL_NAMES, DEVICE_OPTIONS, get_input_devices
from .hotkey import get_keyboard_devices


# Modern Light Theme - Clean, Spacious, Professional
SETTINGS_CSS = """
window {
    background-color: #f5f6f7;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

.header-bar {
    background-color: #ffffff;
    border-bottom: 1px solid #e1e4e8;
    padding: 16px 24px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.title-label {
    font-size: 20px;
    font-weight: 600;
    color: #1a1f36;
}

.save-button {
    background: #4f46e5;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    color: white;
    font-weight: 600;
    transition: all 0.2s;
}

.save-button:hover {
    background: #4338ca;
    box-shadow: 0 4px 6px rgba(79, 70, 229, 0.2);
}

.section-box {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px;
    margin: 8px 24px;
}

.section-title {
    font-size: 11px;
    font-weight: 700;
    color: #6b7280;
    margin-bottom: 12px;
}

.setting-label {
    font-size: 14px;
    color: #374151;
    font-weight: 500;
}

.setting-desc {
    font-size: 12px;
    color: #6b7280;
}

combobox {
    background-color: #f9fafb;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    color: #374151;
    padding: 6px;
    min-height: 36px;
}

combobox:focus {
    border-color: #6366f1;
    background-color: #ffffff;
}

scale trough {
    background-color: #e5e7eb;
    border-radius: 4px;
    min-height: 6px;
}

scale highlight {
    background: #4f46e5;
    border-radius: 4px;
}

scale slider {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 50%;
    min-width: 20px;
    min-height: 20px;
    margin: -7px 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

checkbutton {
    color: #374151;
    font-weight: 500;
}

checkbutton check {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    min-width: 18px;
    min-height: 18px;
}

checkbutton:checked check {
    background-color: #4f46e5;
    border-color: #4f46e5;
    color: white;
}

.hotkey-entry {
    background-color: #f3f4f6;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #1f2937;
    font-weight: 600;
    min-width: 140px;
}

.hotkey-button {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px 16px;
    color: #4b5563;
    font-weight: 500;
}

.hotkey-button:hover {
    background-color: #f9fafb;
    border-color: #9ca3af;
    color: #1f2937;
}

.refresh-btn {
    background: transparent;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    color: #6b7280;
    padding: 6px 10px;
}

.refresh-btn:hover {
    background-color: #f3f4f6;
    color: #4f46e5;
    border-color: #d1d5db;
}

.prompt-textview {
    background-color: #f9fafb;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #374151;
}

.prompt-textview:disabled {
    background-color: #e5e7eb;
    color: #9ca3af;
}

.status-label {
    font-size: 12px;
    color: #059669;
    font-weight: 500;
}

.status-error {
    color: #dc2626;
}

.add-model-entry {
    background-color: #f9fafb;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #374151;
}
"""


class NoScrollComboBox(Gtk.ComboBoxText):
    """ComboBox that ignores scroll wheel events to prevent accidental changes."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect("scroll-event", self._on_scroll)
    
    def _on_scroll(self, widget, event):
        return True  # Block scroll events


class SettingsWindow(Gtk.Window):
    """Simplified GTK3 Settings window for WhisperLayer."""
    
    def __init__(self, on_save=None, on_close=None, on_capture_start=None, on_capture_end=None):
        super().__init__(title="WhisperLayer Settings")
        self.on_save = on_save
        self.on_close_callback = on_close
        self.on_capture_start = on_capture_start
        self.on_capture_end = on_capture_end
        
        self.settings = get_settings()
        self._capturing_hotkey = False
        self._pressed_keys = set()
        self._current_hotkey = self.settings.hotkey
        self._input_devices = []
        self._keyboard_devices = []
        
        self.set_default_size(500, 600)  # Slightly larger for comfort
        self.set_border_width(0)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(True)
        
        self._apply_css()
        self.connect("delete-event", self._on_delete)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)
        
        # Ollama state
        self._ollama_models = []
        
        self._build_ui()
        self._load_values()
    
    def _apply_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(SETTINGS_CSS.encode())
        screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    
    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)
        
        # Header with Save button at top
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.get_style_context().add_class("header-bar")
        
        title = Gtk.Label(label="Settings")
        title.get_style_context().add_class("title-label")
        title.set_halign(Gtk.Align.START)
        header.pack_start(title, True, True, 0)
        
        # Guide Button
        guide_btn = Gtk.Button(label="Open Guide")
        guide_btn.get_style_context().add_class("refresh-btn") # Re-use generic style or add specific
        guide_btn.connect("clicked", self._on_open_guide)
        guide_btn.set_tooltip_text("Open Command Guide (README)")
        header.pack_end(guide_btn, False, False, 0)
        
        save_btn = Gtk.Button(label="Save")
        save_btn.get_style_context().add_class("save-button")
        save_btn.connect("clicked", self._on_save)
        save_btn.set_tooltip_text("Save all settings")
        header.pack_end(save_btn, False, False, 0)
        
        main_box.pack_start(header, False, False, 0)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        main_box.pack_start(scrolled, True, True, 0)
        
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(10)
        content.set_margin_bottom(16)
        scrolled.add(content)
        
        # Microphone Section
        mic_section = self._create_section("MICROPHONE")
        content.pack_start(mic_section, False, False, 0)
        
        mic_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mic_row.set_margin_top(4)
        
        self.input_combo = NoScrollComboBox()
        self.input_combo.set_hexpand(True)
        mic_row.pack_start(self.input_combo, True, True, 0)
        
        refresh_btn = Gtk.Button(label="↻")
        refresh_btn.get_style_context().add_class("refresh-btn")
        refresh_btn.set_tooltip_text("Refresh device list")
        refresh_btn.connect("clicked", self._on_refresh_devices)
        mic_row.pack_start(refresh_btn, False, False, 0)
        
        mic_section.pack_start(mic_row, False, False, 0)
        
        # Hotkey Section
        hotkey_section = self._create_section("HOTKEY")
        content.pack_start(hotkey_section, False, False, 0)
        
        hotkey_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hotkey_row.set_margin_top(4)
        
        self.hotkey_label = Gtk.Label()
        self.hotkey_label.get_style_context().add_class("hotkey-entry")
        self.hotkey_label.set_xalign(0.5)
        hotkey_row.pack_start(self.hotkey_label, False, False, 0)
        
        self.hotkey_button = Gtk.Button(label="Change...")
        self.hotkey_button.get_style_context().add_class("hotkey-button")
        self.hotkey_button.connect("clicked", self._on_hotkey_button_clicked)
        hotkey_row.pack_start(self.hotkey_button, False, False, 0)
        
        hotkey_section.pack_start(hotkey_row, False, False, 0)
        
        # Keyboard Input Device Section
        keyboard_section = self._create_section("KEYBOARD INPUT DEVICE")
        content.pack_start(keyboard_section, False, False, 0)
        
        keyboard_desc = Gtk.Label(label="Device used for hotkey detection")
        keyboard_desc.get_style_context().add_class("setting-desc")
        keyboard_desc.set_halign(Gtk.Align.START)
        keyboard_section.pack_start(keyboard_desc, False, False, 0)
        
        keyboard_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        keyboard_row.set_margin_top(4)
        
        self.keyboard_combo = NoScrollComboBox()
        self.keyboard_combo.set_hexpand(True)
        keyboard_row.pack_start(self.keyboard_combo, True, True, 0)
        
        keyboard_refresh_btn = Gtk.Button(label="↻")
        keyboard_refresh_btn.get_style_context().add_class("refresh-btn")
        keyboard_refresh_btn.set_tooltip_text("Refresh keyboard device list")
        keyboard_refresh_btn.connect("clicked", self._on_refresh_keyboards)
        keyboard_row.pack_start(keyboard_refresh_btn, False, False, 0)
        
        keyboard_section.pack_start(keyboard_row, False, False, 0)
        
        # Model Section
        model_section = self._create_section("AI MODEL")
        content.pack_start(model_section, False, False, 0)
        
        model_desc = Gtk.Label(label="Larger = more accurate but slower")
        model_desc.get_style_context().add_class("setting-desc")
        model_desc.set_halign(Gtk.Align.START)
        model_section.pack_start(model_desc, False, False, 0)
        
        self.model_combo = NoScrollComboBox()
        for name, desc in AVAILABLE_MODELS:
            self.model_combo.append(name, desc)
        self.model_combo.set_margin_top(6)
        model_section.pack_start(self.model_combo, False, False, 0)
        
        # Device Section
        device_section = self._create_section("COMPUTE DEVICE")
        content.pack_start(device_section, False, False, 0)
        
        device_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        device_box.set_margin_top(4)
        
        self.device_radios = {}
        first_radio = None
        for device in DEVICE_OPTIONS:
            label = device.upper()
            if device == "cuda":
                label = "GPU (CUDA)"
            elif device == "auto":
                label = "Auto"
            
            if first_radio is None:
                radio = Gtk.RadioButton.new_with_label_from_widget(None, label)
                first_radio = radio
            else:
                radio = Gtk.RadioButton.new_with_label_from_widget(first_radio, label)
            self.device_radios[device] = radio
            device_box.pack_start(radio, False, False, 0)
        
        device_section.pack_start(device_box, False, False, 0)
        
        # Behavior Section
        behavior_section = self._create_section("BEHAVIOR")
        content.pack_start(behavior_section, False, False, 0)
        
        silence_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        silence_row.set_margin_top(4)
        
        silence_label = Gtk.Label(label="Auto-stop after silence:")
        silence_label.get_style_context().add_class("setting-label")
        silence_row.pack_start(silence_label, False, False, 0)
        
        self.silence_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 5.0, 0.5)
        self.silence_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.silence_scale.set_digits(1)
        self.silence_scale.set_hexpand(True)
        silence_row.pack_start(self.silence_scale, True, True, 0)
        
        silence_suffix = Gtk.Label(label="sec")
        silence_suffix.get_style_context().add_class("setting-desc")
        silence_row.pack_start(silence_suffix, False, False, 0)
        
        behavior_section.pack_start(silence_row, False, False, 0)
        
        autostart_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        autostart_row.set_margin_top(10)
        
        self.autostart_check = Gtk.CheckButton(label="Start WhisperLayer on login")
        autostart_row.pack_start(self.autostart_check, False, False, 0)
        
        behavior_section.pack_start(autostart_row, False, False, 0)
        
        # Ollama AI Section
        ollama_section = self._create_section("OLLAMA AI")
        content.pack_start(ollama_section, False, False, 0)
        
        # Enable checkbox
        self.ollama_enable_check = Gtk.CheckButton(label="Enable Ollama AI queries (say 'okay delta')")
        self.ollama_enable_check.set_margin_top(4)
        ollama_section.pack_start(self.ollama_enable_check, False, False, 0)
        
        # Model selection row
        model_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        model_row.set_margin_top(10)
        
        model_label = Gtk.Label(label="Model:")
        model_label.get_style_context().add_class("setting-label")
        model_row.pack_start(model_label, False, False, 0)
        
        self.ollama_model_combo = NoScrollComboBox()
        self.ollama_model_combo.set_hexpand(True)
        model_row.pack_start(self.ollama_model_combo, True, True, 0)
        
        ollama_refresh_btn = Gtk.Button(label="↻")
        ollama_refresh_btn.get_style_context().add_class("refresh-btn")
        ollama_refresh_btn.set_tooltip_text("Refresh model list")
        ollama_refresh_btn.connect("clicked", self._on_refresh_ollama_models)
        model_row.pack_start(ollama_refresh_btn, False, False, 0)
        
        ollama_section.pack_start(model_row, False, False, 0)
        
        # Add model row
        add_model_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        add_model_row.set_margin_top(8)
        
        add_label = Gtk.Label(label="Add model:")
        add_label.get_style_context().add_class("setting-desc")
        add_model_row.pack_start(add_label, False, False, 0)
        
        self.ollama_add_entry = Gtk.Entry()
        self.ollama_add_entry.get_style_context().add_class("add-model-entry")
        self.ollama_add_entry.set_placeholder_text("e.g. mistral:7b")
        self.ollama_add_entry.set_hexpand(True)
        add_model_row.pack_start(self.ollama_add_entry, True, True, 0)
        
        add_btn = Gtk.Button(label="Add")
        add_btn.get_style_context().add_class("refresh-btn")
        add_btn.connect("clicked", self._on_add_ollama_model)
        add_model_row.pack_start(add_btn, False, False, 0)
        
        ollama_section.pack_start(add_model_row, False, False, 0)
        
        # Custom prompt toggle
        prompt_toggle_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        prompt_toggle_row.set_margin_top(12)
        
        self.ollama_custom_prompt_check = Gtk.CheckButton(label="Custom system prompt (change at your own risk)")
        self.ollama_custom_prompt_check.connect("toggled", self._on_custom_prompt_toggled)
        prompt_toggle_row.pack_start(self.ollama_custom_prompt_check, False, False, 0)
        
        ollama_section.pack_start(prompt_toggle_row, False, False, 0)
        
        # Prompt text view
        prompt_scroll = Gtk.ScrolledWindow()
        prompt_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        prompt_scroll.set_min_content_height(80)
        prompt_scroll.set_max_content_height(120)
        prompt_scroll.set_margin_top(6)
        
        self.ollama_prompt_textview = Gtk.TextView()
        self.ollama_prompt_textview.get_style_context().add_class("prompt-textview")
        self.ollama_prompt_textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.ollama_prompt_textview.set_sensitive(False)  # Disabled by default
        self.ollama_prompt_buffer = self.ollama_prompt_textview.get_buffer()
        prompt_scroll.add(self.ollama_prompt_textview)
        
        ollama_section.pack_start(prompt_scroll, False, False, 0)
        
        # Status label
        self.ollama_status_label = Gtk.Label()
        self.ollama_status_label.get_style_context().add_class("status-label")
        self.ollama_status_label.set_halign(Gtk.Align.START)
        self.ollama_status_label.set_margin_top(8)
        ollama_section.pack_start(self.ollama_status_label, False, False, 0)
    
    def _create_section(self, title):
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        section.get_style_context().add_class("section-box")
        
        title_label = Gtk.Label(label=title)
        title_label.get_style_context().add_class("section-title")
        title_label.set_halign(Gtk.Align.START)
        section.pack_start(title_label, False, False, 0)
        
        return section
    
    def _refresh_input_devices(self):
        self.input_combo.remove_all()
        self._input_devices = get_input_devices()
        
        for device in self._input_devices:
            device_id = str(device.get('id', 'default'))
            friendly_name = device.get('friendly_name', device.get('name', 'Unknown'))
            self.input_combo.append(device_id, friendly_name)
    
    def _on_refresh_devices(self, button):
        current_id = self.input_combo.get_active_id()
        self._refresh_input_devices()
        
        if current_id:
            self.input_combo.set_active_id(current_id)
        if not self.input_combo.get_active_id():
            self.input_combo.set_active(0)
    
    def _refresh_keyboard_devices(self):
        """Refresh the keyboard device dropdown."""
        self.keyboard_combo.remove_all()
        self._keyboard_devices = get_keyboard_devices()
        
        for device in self._keyboard_devices:
            device_path = device.get('path', '')
            friendly_name = device.get('friendly_name', device.get('name', 'Unknown'))
            self.keyboard_combo.append(device_path, friendly_name)
    
    def _on_refresh_keyboards(self, button):
        """Handler for keyboard refresh button click."""
        current_path = self.keyboard_combo.get_active_id()
        self._refresh_keyboard_devices()
        
        if current_path:
            self.keyboard_combo.set_active_id(current_path)
        if not self.keyboard_combo.get_active_id():
            self.keyboard_combo.set_active(0)
    
    def _load_values(self):
        self._refresh_input_devices()
        
        model = self.settings.model
        if model in AVAILABLE_MODEL_NAMES:
            self.model_combo.set_active_id(model)
        else:
            self.model_combo.set_active(5)
        
        device = self.settings.device
        if device in self.device_radios:
            self.device_radios[device].set_active(True)
        
        input_device_name = self.settings.input_device_name
        input_device_id = self.settings.input_device
        
        matched = False
        if input_device_name:
            for device in self._input_devices:
                if device.get('name') == input_device_name or device.get('friendly_name') == input_device_name:
                    device_id = str(device.get('id', 'None'))
                    self.input_combo.set_active_id(device_id)
                    matched = True
                    break
        
        if not matched and input_device_id is not None:
            self.input_combo.set_active_id(str(input_device_id))
            matched = self.input_combo.get_active_id() is not None
        
        if not matched:
            self.input_combo.set_active(0)
        
        self._current_hotkey = self.settings.hotkey
        self.hotkey_label.set_text(self._current_hotkey)
        self.silence_scale.set_value(self.settings.silence_duration)
        self.autostart_check.set_active(self.settings.auto_start)
        
        # Load keyboard device settings
        self._refresh_keyboard_devices()
        saved_keyboard_path = self.settings.keyboard_device
        if saved_keyboard_path:
            self.keyboard_combo.set_active_id(saved_keyboard_path)
        if not self.keyboard_combo.get_active_id():
            self.keyboard_combo.set_active(0)  # Default to auto-detect
        
        # Load Ollama settings
        self.ollama_enable_check.set_active(self.settings.ollama_enabled)
        self._refresh_ollama_models_internal()
        self.ollama_custom_prompt_check.set_active(self.settings.ollama_custom_prompt_enabled)
        self.ollama_prompt_buffer.set_text(self.settings.ollama_system_prompt)
        self.ollama_prompt_textview.set_sensitive(self.settings.ollama_custom_prompt_enabled)
        self._update_ollama_status()
    
    def _on_hotkey_button_clicked(self, button):
        if self._capturing_hotkey:
            return
        
        # Pause global listener
        if self.on_capture_start:
            self.on_capture_start()
            
        self._capturing_hotkey = True
        self.hotkey_button.set_label("Press keys...")
        self.hotkey_label.set_text("...")
        self._pressed_keys = set()
    
    def _on_key_press(self, widget, event):
        if not self._capturing_hotkey:
            return False
        
        keyname = Gdk.keyval_name(event.keyval).lower()
        self._pressed_keys.add(keyname)
        return True
    
    def _on_key_release(self, widget, event):
        if not self._capturing_hotkey:
            return False
        
        modifiers = []
        main_key = None
        
        for key in self._pressed_keys:
            if key in ('control_l', 'control_r'):
                modifiers.append('<ctrl>')
            elif key in ('alt_l', 'alt_r'):
                modifiers.append('<alt>')
            elif key in ('shift_l', 'shift_r'):
                modifiers.append('<shift>')
            elif key in ('super_l', 'super_r'):
                modifiers.append('<super>')
            else:
                main_key = key
        
        # Only finish if we have a main key (modifiers only don't count)
        if main_key:
            if modifiers:
                hotkey = '+'.join(sorted(set(modifiers))) + '+' + main_key
            else:
                hotkey = main_key
                
            self._current_hotkey = hotkey
            self.hotkey_label.set_text(hotkey)
            
            self._capturing_hotkey = False
            self.hotkey_button.set_label("Change...")
            self._pressed_keys.clear()
            
            # Resume global listener
            if self.on_capture_end:
                self.on_capture_end()
                
        return True
    
    def _on_save(self, button):
        model_id = self.model_combo.get_active_id()
        if model_id:
            # notify=True to trigger hot-reload in app.py
            self.settings.set("model", model_id, save=False, notify=True)
        
        for device, radio in self.device_radios.items():
            if radio.get_active():
                self.settings.set("device", device, save=False, notify=True)
                break
        
        active_idx = self.input_combo.get_active()
        if active_idx >= 0 and active_idx < len(self._input_devices):
            selected_device = self._input_devices[active_idx]
            device_id = selected_device.get('id')
            device_name = selected_device.get('friendly_name', selected_device.get('name'))
            self.settings.set("input_device", device_name, save=False, notify=True)
            self.settings.set("input_device_id", device_id, save=False, notify=True)
        else:
            self.settings.set("input_device", None, save=False, notify=True)
            self.settings.set("input_device_id", None, save=False, notify=True)
        
        self.settings.set("hotkey", self._current_hotkey, save=False, notify=True)
        self.settings.set("silence_duration", self.silence_scale.get_value(), save=False, notify=True)
        self.settings.set("auto_start", self.autostart_check.get_active(), save=False, notify=True)
        
        # Save keyboard device settings
        keyboard_idx = self.keyboard_combo.get_active()
        if keyboard_idx >= 0 and keyboard_idx < len(self._keyboard_devices):
            selected_keyboard = self._keyboard_devices[keyboard_idx]
            keyboard_path = selected_keyboard.get('path', '')
            keyboard_name = selected_keyboard.get('friendly_name', selected_keyboard.get('name', ''))
            self.settings.set("keyboard_device", keyboard_path, save=False, notify=True)
            self.settings.set("keyboard_device_name", keyboard_name, save=False, notify=True)
        else:
            self.settings.set("keyboard_device", "", save=False, notify=True)
            self.settings.set("keyboard_device_name", "", save=False, notify=True)
        
        # Save Ollama settings
        self.settings.set("ollama_enabled", self.ollama_enable_check.get_active(), save=False, notify=True)
        
        ollama_model = self.ollama_model_combo.get_active_id()
        if ollama_model:
            self.settings.set("ollama_model", ollama_model, save=False, notify=True)
        
        self.settings.set("ollama_custom_prompt_enabled", self.ollama_custom_prompt_check.get_active(), save=False, notify=True)
        
        # Get prompt text
        start_iter = self.ollama_prompt_buffer.get_start_iter()
        end_iter = self.ollama_prompt_buffer.get_end_iter()
        prompt_text = self.ollama_prompt_buffer.get_text(start_iter, end_iter, True)
        self.settings.set("ollama_system_prompt", prompt_text, save=False, notify=True)
        
        self.settings.save()
        
        if self.on_save:
            self.on_save()
        
        self.hide()
    
    def _refresh_ollama_models_internal(self):
        """Internal method to refresh Ollama models list."""
        self.ollama_model_combo.remove_all()
        self._ollama_models = []
        
        try:
            from .ollama_service import get_ollama_service
            service = get_ollama_service()
            
            if service.is_available():
                self._ollama_models = service.list_models()
        except Exception as e:
            print(f"Error listing Ollama models: {e}")
        
        # Add custom models from settings
        custom_models = self.settings.ollama_custom_models or []
        for model in custom_models:
            if model and model not in self._ollama_models:
                self._ollama_models.append(model)
        
        # Populate combo box
        for model in self._ollama_models:
            self.ollama_model_combo.append(model, model)
        
        # Set current selection
        current_model = self.settings.ollama_model
        if current_model:
            if current_model not in self._ollama_models:
                # Add current model even if not in list
                self.ollama_model_combo.append(current_model, current_model)
                self._ollama_models.append(current_model)
            self.ollama_model_combo.set_active_id(current_model)
        
        if not self.ollama_model_combo.get_active_id() and self._ollama_models:
            self.ollama_model_combo.set_active(0)
    
    def _on_refresh_ollama_models(self, button):
        """Handler for refresh button click."""
        self._refresh_ollama_models_internal()
        self._update_ollama_status()
    
    def _on_add_ollama_model(self, button):
        """Handler for add model button click."""
        model_name = self.ollama_add_entry.get_text().strip()
        if not model_name:
            return
        
        # Add to custom models in settings
        custom_models = list(self.settings.ollama_custom_models or [])
        if model_name not in custom_models:
            custom_models.append(model_name)
            self.settings.set("ollama_custom_models", custom_models, save=True, notify=False)
        
        # Add to combo and select
        if model_name not in self._ollama_models:
            self.ollama_model_combo.append(model_name, model_name)
            self._ollama_models.append(model_name)
        
        self.ollama_model_combo.set_active_id(model_name)
        self.ollama_add_entry.set_text("")
        
        self._update_ollama_status()
    
    def _on_custom_prompt_toggled(self, button):
        """Handler for custom prompt checkbox toggle."""
        enabled = button.get_active()
        self.ollama_prompt_textview.set_sensitive(enabled)
    
    def _update_ollama_status(self):
        """Update the Ollama status label."""
        try:
            from .ollama_service import get_ollama_service
            service = get_ollama_service()
            
            if service.is_available():
                model_count = len(self._ollama_models)
                self.ollama_status_label.set_text(f"✓ Connected ({model_count} models available)")
                self.ollama_status_label.get_style_context().remove_class("status-error")
            else:
                self.ollama_status_label.set_text("✗ Ollama not running (run 'ollama serve')")
                self.ollama_status_label.get_style_context().add_class("status-error")
        except Exception as e:
            self.ollama_status_label.set_text(f"✗ Error: {str(e)[:30]}")
            self.ollama_status_label.get_style_context().add_class("status-error")
        
    def _on_open_guide(self, button):
        """Open the online GitHub guide."""
        import webbrowser
        
        url = "https://github.com/BlackPool25/WhisperLayer/blob/main/README.md"
        
        try:
            print(f"Opening guide: {url}")
            webbrowser.open(url)
        except Exception as e:
            print(f"Failed to open guide: {e}")
    
    def _on_delete(self, widget, event):
        self.hide()
        if self.on_close_callback:
            self.on_close_callback()
        return True


def show_settings(on_save=None):
    window = SettingsWindow(on_save=on_save)
    window.show_all()
    return window