"""Settings GUI for VoiceType using GTK3."""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from .settings import get_settings, AVAILABLE_MODELS, DEVICE_OPTIONS, get_input_devices


class SettingsWindow(Gtk.Window):
    """GTK3 Settings window for VoiceType."""
    
    def __init__(self, on_save: callable = None, on_close: callable = None):
        super().__init__(title="VoiceType Settings")
        self.on_save = on_save
        self.on_close_callback = on_close
        
        self.settings = get_settings()
        self._capturing_hotkey = False
        
        self.set_default_size(450, 500)
        self.set_border_width(20)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        
        # Connect close event
        self.connect("delete-event", self._on_delete)
        
        self._build_ui()
        self._load_values()
    
    def _build_ui(self):
        """Build the settings UI."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.add(main_box)
        
        # Title
        title = Gtk.Label()
        title.set_markup("<big><b>VoiceType Settings</b></big>")
        title.set_halign(Gtk.Align.START)
        main_box.pack_start(title, False, False, 0)
        
        # Settings grid
        grid = Gtk.Grid()
        grid.set_column_spacing(15)
        grid.set_row_spacing(15)
        main_box.pack_start(grid, True, True, 0)
        
        row = 0
        
        # Model selection
        label = Gtk.Label(label="Whisper Model:")
        label.set_halign(Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)
        
        self.model_combo = Gtk.ComboBoxText()
        for model in AVAILABLE_MODELS:
            self.model_combo.append_text(model)
        self.model_combo.set_hexpand(True)
        grid.attach(self.model_combo, 1, row, 1, 1)
        
        row += 1
        
        # Device selection
        label = Gtk.Label(label="Compute Device:")
        label.set_halign(Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)
        
        device_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.device_radios = {}
        first_radio = None
        for device in DEVICE_OPTIONS:
            if first_radio is None:
                radio = Gtk.RadioButton.new_with_label_from_widget(None, device.upper())
                first_radio = radio
            else:
                radio = Gtk.RadioButton.new_with_label_from_widget(first_radio, device.upper())
            self.device_radios[device] = radio
            device_box.pack_start(radio, False, False, 0)
        grid.attach(device_box, 1, row, 1, 1)
        
        row += 1
        
        # Input device
        label = Gtk.Label(label="Microphone:")
        label.set_halign(Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)
        
        self.input_combo = Gtk.ComboBoxText()
        self.input_combo.append("default", "Default")
        self._input_devices = get_input_devices()
        for device in self._input_devices:
            self.input_combo.append(str(device['id']), device['name'])
        self.input_combo.set_hexpand(True)
        grid.attach(self.input_combo, 1, row, 1, 1)
        
        row += 1
        
        # Hotkey
        label = Gtk.Label(label="Hotkey:")
        label.set_halign(Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)
        
        hotkey_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.hotkey_label = Gtk.Label(label="")
        self.hotkey_label.set_hexpand(True)
        self.hotkey_label.set_halign(Gtk.Align.START)
        hotkey_box.pack_start(self.hotkey_label, True, True, 0)
        
        self.hotkey_button = Gtk.Button(label="Change...")
        self.hotkey_button.connect("clicked", self._on_hotkey_button_clicked)
        hotkey_box.pack_start(self.hotkey_button, False, False, 0)
        grid.attach(hotkey_box, 1, row, 1, 1)
        
        row += 1
        
        # Silence duration
        label = Gtk.Label(label="Silence Timeout:")
        label.set_halign(Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)
        
        silence_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.silence_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.5, 5.0, 0.5
        )
        self.silence_scale.set_hexpand(True)
        self.silence_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.silence_scale.set_digits(1)
        silence_box.pack_start(self.silence_scale, True, True, 0)
        
        silence_label = Gtk.Label(label="seconds")
        silence_box.pack_start(silence_label, False, False, 0)
        grid.attach(silence_box, 1, row, 1, 1)
        
        row += 1
        
        # Auto-start
        label = Gtk.Label(label="Auto-start:")
        label.set_halign(Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)
        
        self.autostart_check = Gtk.CheckButton(label="Start VoiceType when I log in")
        grid.attach(self.autostart_check, 1, row, 1, 1)
        
        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.END)
        
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", self._on_cancel)
        button_box.pack_start(cancel_button, False, False, 0)
        
        save_button = Gtk.Button(label="Save")
        save_button.get_style_context().add_class("suggested-action")
        save_button.connect("clicked", self._on_save)
        button_box.pack_start(save_button, False, False, 0)
        
        main_box.pack_end(button_box, False, False, 0)
    
    def _load_values(self):
        """Load current settings into UI."""
        # Model
        model = self.settings.model
        model_index = AVAILABLE_MODELS.index(model) if model in AVAILABLE_MODELS else 0
        self.model_combo.set_active(model_index)
        
        # Device
        device = self.settings.device
        if device in self.device_radios:
            self.device_radios[device].set_active(True)
        
        # Input device
        input_device = self.settings.input_device
        if input_device is None:
            self.input_combo.set_active_id("default")
        else:
            self.input_combo.set_active_id(str(input_device))
        
        # Hotkey
        self.hotkey_label.set_text(self.settings.hotkey)
        self._current_hotkey = self.settings.hotkey
        
        # Silence duration
        self.silence_scale.set_value(self.settings.silence_duration)
        
        # Auto-start
        self.autostart_check.set_active(self.settings.auto_start)
    
    def _on_hotkey_button_clicked(self, button):
        """Start capturing hotkey."""
        if self._capturing_hotkey:
            return
        
        self._capturing_hotkey = True
        self.hotkey_button.set_label("Press keys...")
        self.hotkey_label.set_text("Waiting...")
        
        # Connect key events
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)
        self._pressed_keys = set()
    
    def _on_key_press(self, widget, event):
        """Handle key press during hotkey capture."""
        if not self._capturing_hotkey:
            return False
        
        keyname = Gdk.keyval_name(event.keyval).lower()
        self._pressed_keys.add(keyname)
        return True
    
    def _on_key_release(self, widget, event):
        """Handle key release during hotkey capture."""
        if not self._capturing_hotkey:
            return False
        
        # Build hotkey string
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
        """Save settings."""
        # Model
        model_text = self.model_combo.get_active_text()
        if model_text:
            self.settings.set("model", model_text, save=False)
        
        # Device
        for device, radio in self.device_radios.items():
            if radio.get_active():
                self.settings.set("device", device, save=False)
                break
        
        # Input device
        input_id = self.input_combo.get_active_id()
        if input_id == "default":
            self.settings.set("input_device", None, save=False)
        else:
            self.settings.set("input_device", int(input_id), save=False)
        
        # Hotkey
        self.settings.set("hotkey", self._current_hotkey, save=False)
        
        # Silence duration
        self.settings.set("silence_duration", self.silence_scale.get_value(), save=False)
        
        # Auto-start
        self.settings.set("auto_start", self.autostart_check.get_active(), save=False)
        
        # Save all
        self.settings.save()
        
        if self.on_save:
            self.on_save()
        
        self.hide()
    
    def _on_cancel(self, button):
        """Cancel and close."""
        self._load_values()  # Reset to saved values
        self.hide()
    
    def _on_delete(self, widget, event):
        """Handle window close."""
        self.hide()
        if self.on_close_callback:
            self.on_close_callback()
        return True  # Prevent destruction


def show_settings(on_save: callable = None):
    """Show the settings window."""
    window = SettingsWindow(on_save=on_save)
    window.show_all()
    return window
