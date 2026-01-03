"""Simplified Settings GUI for VoiceType using GTK3."""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from .settings import get_settings, AVAILABLE_MODELS, AVAILABLE_MODEL_NAMES, DEVICE_OPTIONS, get_input_devices


# Modern dark theme CSS - minimal and clean
SETTINGS_CSS = """
window {
    background-color: #1e1e24;
}

.header-bar {
    background: linear-gradient(180deg, #2a2a35, #252530);
    border-bottom: 1px solid #3a3a45;
    padding: 12px 16px;
}

.title-label {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}

.save-button {
    background: linear-gradient(180deg, #2e8b57, #228b22);
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    color: white;
    font-weight: bold;
    min-width: 80px;
}

.save-button:hover {
    background: linear-gradient(180deg, #3cb371, #2e8b57);
}

.section-box {
    background-color: #252530;
    border-radius: 10px;
    padding: 16px;
    margin: 6px 16px;
}

.section-title {
    font-size: 12px;
    font-weight: bold;
    color: #7799dd;
    margin-bottom: 10px;
}

.setting-label {
    font-size: 13px;
    color: #e0e0e0;
}

.setting-desc {
    font-size: 10px;
    color: #808090;
}

combobox, combobox button, combobox cellview {
    background-color: #333340;
    border: 1px solid #444455;
    border-radius: 6px;
    color: #e0e0e0;
    min-height: 34px;
    padding: 4px 8px;
}

combobox:focus, combobox button:focus {
    border-color: #5577cc;
}

scale {
    min-height: 30px;
}

scale trough {
    background-color: #333340;
    border-radius: 3px;
    min-height: 6px;
}

scale highlight {
    background: linear-gradient(90deg, #4477cc, #6655bb);
    border-radius: 3px;
}

scale slider {
    background-color: #ffffff;
    border-radius: 50%;
    min-width: 16px;
    min-height: 16px;
}

checkbutton {
    color: #e0e0e0;
}

checkbutton check {
    background-color: #333340;
    border: 2px solid #555566;
    border-radius: 4px;
    min-width: 18px;
    min-height: 18px;
}

checkbutton:checked check {
    background: linear-gradient(135deg, #4477cc, #6655bb);
    border-color: #5588dd;
}

.hotkey-entry {
    background-color: #333340;
    border: 1px solid #444455;
    border-radius: 6px;
    padding: 8px 12px;
    font-family: monospace;
    font-size: 12px;
    color: #99bbff;
    min-width: 140px;
}

.hotkey-button {
    background-color: #3a3a48;
    border: 1px solid #505060;
    border-radius: 6px;
    padding: 8px 14px;
    color: #c0c0d0;
}

.hotkey-button:hover {
    background-color: #454555;
    border-color: #6677aa;
}

.refresh-btn {
    background-color: transparent;
    border: 1px solid #444455;
    border-radius: 6px;
    padding: 4px 10px;
    color: #a0a0b0;
    min-width: 30px;
}

.refresh-btn:hover {
    background-color: #333340;
    border-color: #6677aa;
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
    """Simplified GTK3 Settings window for VoiceType."""
    
    def __init__(self, on_save=None, on_close=None):
        super().__init__(title="VoiceType Settings")
        self.on_save = on_save
        self.on_close_callback = on_close
        
        self.settings = get_settings()
        self._capturing_hotkey = False
        self._pressed_keys = set()
        self._current_hotkey = self.settings.hotkey
        self._input_devices = []
        
        self.set_default_size(440, 520)
        self.set_border_width(0)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(True)
        
        self._apply_css()
        self.connect("delete-event", self._on_delete)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)
        
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
        
        self.autostart_check = Gtk.CheckButton(label="Start VoiceType on login")
        autostart_row.pack_start(self.autostart_check, False, False, 0)
        
        behavior_section.pack_start(autostart_row, False, False, 0)
    
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
    
    def _on_hotkey_button_clicked(self, button):
        if self._capturing_hotkey:
            return
        
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
        
        if modifiers and main_key:
            hotkey = '+'.join(sorted(set(modifiers))) + '+' + main_key
            self._current_hotkey = hotkey
            self.hotkey_label.set_text(hotkey)
        
        self._capturing_hotkey = False
        self.hotkey_button.set_label("Change...")
        self._pressed_keys.clear()
        return True
    
    def _on_save(self, button):
        model_id = self.model_combo.get_active_id()
        if model_id:
            self.settings.set("model", model_id, save=False, notify=False)
        
        for device, radio in self.device_radios.items():
            if radio.get_active():
                self.settings.set("device", device, save=False, notify=False)
                break
        
        active_idx = self.input_combo.get_active()
        if active_idx >= 0 and active_idx < len(self._input_devices):
            selected_device = self._input_devices[active_idx]
            device_id = selected_device.get('id')
            device_name = selected_device.get('friendly_name', selected_device.get('name'))
            self.settings.set("input_device", device_name, save=False, notify=False)
            self.settings.set("input_device_id", device_id, save=False, notify=False)
        else:
            self.settings.set("input_device", None, save=False, notify=False)
            self.settings.set("input_device_id", None, save=False, notify=False)
        
        self.settings.set("hotkey", self._current_hotkey, save=False, notify=False)
        self.settings.set("silence_duration", self.silence_scale.get_value(), save=False, notify=False)
        self.settings.set("auto_start", self.autostart_check.get_active(), save=False, notify=False)
        
        self.settings.save()
        
        if self.on_save:
            self.on_save()
        
        self.hide()
    
    def _on_delete(self, widget, event):
        self.hide()
        if self.on_close_callback:
            self.on_close_callback()
        return True


def show_settings(on_save=None):
    window = SettingsWindow(on_save=on_save)
    window.show_all()
    return window