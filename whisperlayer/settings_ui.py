"""Simplified Settings GUI for WhisperLayer using GTK3."""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

# ... imports ...

class CommandMacroEditor(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.get_style_context().add_class("macro-editor")
        
        # Scrolled Text View
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER) # Horiz scroll only? No, wrap mode.
        self.scrolled.set_shadow_type(Gtk.ShadowType.IN)
        self.scrolled.set_hexpand(True)
        self.scrolled.set_min_content_height(40)
        
        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_left_margin(8)
        self.textview.set_right_margin(8)
        self.textview.set_top_margin(6)
        self.textview.set_bottom_margin(6)
        
        self.buffer = self.textview.get_buffer()
        self.buffer.connect("changed", self._on_text_changed)
        
        # Tags
        self.tag_cmd = self.buffer.create_tag("command", 
                                            foreground="#2563eb", 
                                            weight=Pango.Weight.BOLD)
        
        self.scrolled.add(self.textview)
        self.pack_start(self.scrolled, True, True, 0)
        
        # Record Button
        self.rec_btn = Gtk.Button(label="⌨️")
        self.rec_btn.set_tooltip_text("Record Keystrokes")
        self.rec_btn.connect("clicked", self._on_record_clicked)
        self.pack_start(self.rec_btn, False, False, 4)
        
        # Autocomplete Popover
        self.popover = Gtk.Popover(relative_to=self.textview)
        self.popover.set_position(Gtk.PositionType.BOTTOM)
        self.pop_list = Gtk.ListBox()
        self.pop_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.pop_list.connect("row-activated", self._on_suggestion_clicked)
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(150)
        scroll.set_min_content_width(200)
        scroll.add(self.pop_list)
        
        self.popover.add(scroll)
        
        # Internal state
        self._anchor_widgets = {} # anchor -> widget
        
    def get_text(self):
        """Serialize content including widgets."""
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        text = self.buffer.get_text(start, end, True) # include hidden char?
        # Actually proper way: iterate child anchors
        
        # Simplified: We know we insert anchors for arguments.
        # But GtkTextView serialization is hard.
        # Let's rely on a simpler trick: 
        # We store the widgets in a list matching the order? No.
        # We can iterate the buffer char by char? Slow.
        # We can use the text and assume user didn't mess up?
        # If we use child anchors, the text contains a replacement char (0xFFFC).
        
        final_text = ""
        current_iter = start
        
        while not current_iter.is_end():
            child_anchor = current_iter.get_child_anchor()
            if child_anchor:
                # Find widget for this anchor
                widget = self._anchor_widgets.get(child_anchor)
                if widget and isinstance(widget, Gtk.Entry):
                    final_text += f"[{widget.get_text()}]"
                else:
                    final_text += "" # Should not happen
            else:
                char = current_iter.get_char()
                if char != '\ufffc': # Skip anchor holder if get_char returns it
                    final_text += char
            
            if not current_iter.forward_char():
                break
                
        return final_text.strip()
        
    def set_text(self, text):
        self.buffer.set_text(text)
        # TODO: Parse text and reconstruct widgets if loading existing command? 
        # For now, just plain text loading.
        
    def _on_text_changed(self, buffer):
        # Check for @
        insert = buffer.get_insert()
        iter_cur = buffer.get_iter_at_mark(insert)
        
        # Look back
        iter_start = iter_cur.copy()
        # Search backwards for @ up to 20 chars
        # or find "word start"
        
        # Simple detection: Find '@' in recent text
        text_before = ""
        found_at = False
        
        # Walk back max 20 chars
        count = 0
        while count < 20 and iter_start.backward_char():
            char = iter_start.get_char()
            if char == '@':
                found_at = True
                break
            if char == ' ' or char == '\n':
                break # Stop at whitespace
            count += 1
            
        if found_at:
            # We have @... 
            query_iter = iter_start.copy()
            query_iter.forward_char() # skip @
            query = buffer.get_text(query_iter, buffer.get_iter_at_mark(insert), False)
            self._show_suggestions(query, iter_start)
        else:
            self.popover.popdown()
            
    def _show_suggestions(self, query, iter_start):
        # Clear list
        for child in self.pop_list.get_children():
            self.pop_list.remove(child)
            
        # Get commands
        import sys
        # Hack to access detector commands
        # In real app we should pass detector. 
        # For now assume we can get it from settings/app? 
        # Or just instantiate one (cached)
        
        # For this prototype, let's instantiate one locally or cache it class-level?
        if not hasattr(self, '_detector'):
             from .commands import VoiceCommandDetector
             self._detector = VoiceCommandDetector()
             
        cmds = self._detector.commands
        match_count = 0
        
        for name, cmd in cmds.items():
            if name.startswith(query):
                row = Gtk.ListBoxRow()
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                box.set_margin_top(4)
                box.set_margin_bottom(4)
                box.set_margin_left(4)
                
                lbl = Gtk.Label(label=f"@{name}")
                lbl.set_halign(Gtk.Align.START)
                if cmd.requires_end:
                     lbl.set_markup(f"<b>@{name}</b> <span size='small' color='gray'>[query]</span>")
                
                box.pack_start(lbl, True, True, 0)
                row.add(box)
                row.cmd_name = name
                row.cmd_obj = cmd
                self.pop_list.add(row)
                match_count += 1
                
        if match_count > 0:
            self.pop_list.show_all()
            # Position popover
            rect = self.textview.get_iter_location(iter_start)
            # convert buffer coords to window coords
            win_x, win_y = self.textview.buffer_to_window_coords(Gtk.TextWindowType.TEXT, rect.x, rect.y + rect.height)
            rect.x = win_x
            rect.y = win_y
            self.popover.set_pointing_to(rect)
            self.popover.popup()
            self._current_start_iter = iter_start.create_mark(None, True) # save where @ started
        else:
            self.popover.popdown()

    def _on_suggestion_clicked(self, box, row):
        name = row.cmd_name
        cmd = row.cmd_obj
        
        # Replace text from @ to cursor
        start = self.buffer.get_iter_at_mark(self._current_start_iter)
        end = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        self.buffer.delete(start, end)
        
        # Insert Command Tag
        self.buffer.insert_with_tags(start, f"@{name}", self.tag_cmd)
        
        # If requires end, insert Widget
        if cmd.requires_end:
            # Create Anchor
            anchor = self.buffer.create_child_anchor(start)
            
            # Create Entry (The "Box")
            entry = Gtk.Entry()
            entry.set_placeholder_text("query")
            entry.set_width_chars(15)
            entry.get_style_context().add_class("query-box")
            entry.set_has_frame(False)
            
            # We need to wrap it to style it like a box/chip
            # GtkEntry css background
            css = b"""
            .query-box {
                background: #eef2ff;
                border: 1px solid #c7d2fe;
                border-radius: 4px;
                color: #3730a3;
                padding: 0 4px;
                margin: 0 2px;
            }
            """
            provider = Gtk.CssProvider()
            provider.load_from_data(css)
            entry.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            
            self.textview.add_child_at_anchor(entry, anchor)
            entry.show()
            
            self._anchor_widgets[anchor] = entry
            
            # Insert closing space
            # self.buffer.insert(start, " ") <-- cursor moves with start iter?
            # get new iter
            # iter_now = self.buffer.get_iter_at_mark(self.buffer.get_insert())
            # self.buffer.insert(iter_now, " ")
        else:
             self.buffer.insert(start, " ")
            
        self.popover.popdown()
        self.textview.grab_focus()

    def _on_record_clicked(self, btn):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            buttons=Gtk.ButtonsType.CANCEL,
            text="Record Keystrokes"
        )
        dialog.format_secondary_text("Press keys now... (Click 'Add' when done)")
        
        content = dialog.get_content_area()
        lbl = Gtk.Label(label="...")
        lbl.get_style_context().add_class("key-label")
        lbl.set_margin_top(20)
        lbl.set_margin_bottom(20)
        content.pack_start(lbl, True, True, 0)
        
        dialog.add_button("Add", Gtk.ResponseType.OK)
        
        self.recorded_keys = set()
        self.final_combo = ""
        
        def on_key(widget, event):
            keyname = Gdk.keyval_name(event.keyval).lower()
            
            # Simple modifier logic
            # This is a bit duplicative of settings logic but simpler
            if "shift" in keyname: mods = "<shift>"
            elif "control" in keyname: mods = "<ctrl>"
            elif "alt" in keyname: mods = "<alt>"
            elif "super" in keyname: mods = "<super>"
            else:
                 # It's a key
                 # Combine with held modifiers?
                 # Simplified: Just <key> or <mod>+<key>
                 # We need to track held modifiers.
                 pass
            
            # Better: Append raw key to buffer?
            # User wants "auto convert to format".
            # Let's just use the existing _on_key_release logic concept.
            
            # Quick output
            if keyname in ['control_l', 'control_r', 'shift_l', 'shift_r', 'alt_l', 'alt_r', 'super_l', 'super_r']:
                return # ignore mod-only press for display updates (wait for combo)
                
            state = event.state
            parts = []
            if state & Gdk.ModifierType.CONTROL_MASK: parts.append("ctrl")
            if state & Gdk.ModifierType.MOD1_MASK: parts.append("alt") # Alt
            if state & Gdk.ModifierType.SHIFT_MASK: parts.append("shift")
            if state & Gdk.ModifierType.SUPER_MASK: parts.append("super")
            
            parts.append(keyname)
            self.final_combo = "+".join(parts)
            lbl.set_text(self.final_combo)
            
        dialog.connect("key-press-event", on_key)
        dialog.show_all()
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK and self.final_combo:
            # Insert into textview
            # Format: <ctrl>+c
            # The detector expects this format for keys?
            # detector._type_key uses re.match logic or splitting?
            # Let's assume standard format matches.
            
            self.buffer.insert_at_cursor(f"<{self.final_combo}> ")
            
        dialog.destroy()

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
        # We want to BLOCK the scroll event on this widget so it doesn't change the value.
        # BUT we want the parent ScrolledWindow to still receive the event.
        # In GTK3, returning FALSE propagates, TRUE stops.
        # Valid handling: connect to scroll-event, stop emission, but... 
        # easier workaround: Unset the SCROLL_MASK?
        # self.add_events(Gdk.EventMask.SCROLL_MASK) # Default has it
        self.connect("scroll-event", self._on_scroll)
    
    def _on_scroll(self, widget, event):
        # Return TRUE to say "I handled this", which stops default handler (changing value).
        # But this also stops propagation to parent.
        # To scroll the window, we'd need to manually pass it to parent?
        # Current implementation blocks scroll entirely on the widget area.
        # For now, this is better than accidental value changes.
        return True


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

        # --- NEW: Built-in Commands Section ---
        commands_section = self._create_section("SYSTEM COMMANDS")
        content.pack_start(commands_section, False, False, 0)
        
        cmd_desc = Gtk.Label(label="Manage triggers and built-in commands")
        cmd_desc.get_style_context().add_class("setting-desc")
        cmd_desc.set_halign(Gtk.Align.START)
        commands_section.pack_start(cmd_desc, False, False, 0)
        
        # Scrolled Expander
        self.built_in_switches = {} # Map original_trigger -> switch
        self.built_in_entries = {}  # Map original_trigger -> entry
        
        # Instantiate detector to get defaults
        from .commands import VoiceCommandDetector
        self.detector = VoiceCommandDetector() 
        # Note: detector.commands has EFFECTIVE triggers. We want triggers from registry without overrides logic 
        # effectively, need to access the defaults which are hardcoded in _register_default_commands.
        # But we can reconstruct it by iterating commands and checking overrides.
        
        # Actually easier: The detector has 'category' field.
        # But detector keys are EFFECTIVE triggers.
        # We need the ORIGINAL mapping.
        # Since overrides replace the key, we don't have the original key in self.commands easily if we look at detector alone.
        # Workaround: Re-instantiate detector with MOCKED settings that has empty overrides?
        # A bit hacky but guarantees we get canonical list.
        class MockSettings:
             builtin_overrides = {}
             disabled_commands = []
             custom_commands = []
             ollama_enabled = False # avoid checks
        
        # Temporarily patch settings for detector to get base commands
        import sys
        real_settings_mod = sys.modules['whisperlayer.settings']
        sys.modules['whisperlayer.settings'] = type('obj', (object,), {'get_settings': lambda: MockSettings()})
        base_detector = VoiceCommandDetector()
        sys.modules['whisperlayer.settings'] = real_settings_mod # Restore
        
        sorted_cmds = sorted(base_detector.commands.values(), key=lambda c: c.trigger)
        
        cmds_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        
        for cmd in sorted_cmds:
            if cmd.category == "custom": continue
            
            orig_trigger = cmd.trigger
            current_trigger = self.settings.builtin_overrides.get(orig_trigger, orig_trigger)
            
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            
            # Status Badge (End required?)
            status_icon = "media-playlist-repeat" if cmd.requires_end else "media-flash"
            status_tooltip = "Wait for 'Okay Done'" if cmd.requires_end else "Immediate Action"
            icon = Gtk.Image.new_from_icon_name(status_icon, Gtk.IconSize.MENU)
            icon.set_tooltip_text(status_tooltip)
            row.pack_start(icon, False, False, 0)
            
            # Label (Original Name)
            # label = Gtk.Label(label=orig_trigger.title())
            # label.set_halign(Gtk.Align.START)
            # label.set_width_chars(15)
            # row.pack_start(label, False, False, 0)
            
            # Entry (Editable Trigger)
            entry = Gtk.Entry()
            entry.set_text(current_trigger)
            entry.set_width_chars(20)
            entry.connect("focus-out-event", self._on_builtin_trigger_changed, orig_trigger)
            entry.connect("activate", lambda w, t=orig_trigger: self._on_builtin_trigger_changed(w, None, t))
            self.built_in_entries[orig_trigger] = entry
            row.pack_start(entry, True, True, 0)
            
            # Switch (Enable/Disable)
            switch = Gtk.Switch()
            switch.set_active(orig_trigger not in self.settings.disabled_commands)
            switch.connect("state-set", self._on_command_toggled, orig_trigger)
            self.built_in_switches[orig_trigger] = switch
            row.pack_start(switch, False, False, 0)
            
            cmds_box.pack_start(row, False, False, 0)
            
        self.cmds_expander = Gtk.Expander(label="Manage System Commands")
        self.cmds_expander.add(cmds_box)
        commands_section.pack_start(self.cmds_expander, False, False, 0)

        # --- NEW: Custom Commands Section ---
        custom_section = self._create_section("CUSTOM COMMANDS")
        content.pack_start(custom_section, False, False, 0)
        
        custom_desc = Gtk.Label(label="Add commands or references (e.g. Value '@delta write code')")
        custom_desc.get_style_context().add_class("setting-desc")
        custom_desc.set_halign(Gtk.Align.START)
        custom_section.pack_start(custom_desc, False, False, 0)
        
        # List of custom commands
        self.custom_listbox = Gtk.ListBox()
        self.custom_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        custom_section.pack_start(self.custom_listbox, False, False, 0)
        
        # Add New Command Form
        add_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        add_box.get_style_context().add_class("section-box")
        add_box.set_margin_top(10)
        
        add_title = Gtk.Label(label="Add New Command")
        add_title.get_style_context().add_class("section-title")
        add_title.set_halign(Gtk.Align.START)
        add_box.pack_start(add_title, False, False, 0)
        
        # Trigger
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row1.pack_start(Gtk.Label(label="Trigger: Okay..."), False, False, 0)
        self.new_cmd_trigger = Gtk.Entry()
        self.new_cmd_trigger.set_placeholder_text("e.g. explain code")
        row1.pack_start(self.new_cmd_trigger, True, True, 0)
        add_box.pack_start(row1, False, False, 0)
        
        # Value (Macro Editor)
        row3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row3.pack_start(Gtk.Label(label="Action (Text, Keys, or @commands):"), False, False, 0)
        
        self.new_cmd_editor = CommandMacroEditor()
        self.new_cmd_editor.set_height_request(80) # Give it some height
        row3.pack_start(self.new_cmd_editor, True, True, 0)
        add_box.pack_start(row3, True, True, 0)
        
        # Options
        row4 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.new_cmd_end = Gtk.CheckButton(label="Require 'Okay Done'?")
        self.new_cmd_end.set_active(False)
        row4.pack_start(self.new_cmd_end, False, False, 0)
        
        add_btn = Gtk.Button(label="Add Command")
        add_btn.get_style_context().add_class("save-button")
        add_btn.connect("clicked", self._on_add_custom_command)
        row4.pack_end(add_btn, False, False, 0)
        add_box.pack_start(row4, False, False, 0)
        
        custom_section.pack_start(add_box, False, False, 0)

    # ... (other methods) ...

    def _refresh_custom_commands(self):
        """Rebuild the custom commands listbox."""
        for child in self.custom_listbox.get_children():
            self.custom_listbox.remove(child)
            
        for i, cmd in enumerate(self.settings.custom_commands):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.set_margin_bottom(4)
            
            # Status Badge (End required?)
            # Improved icons:
            # Instant -> lightning (media-flash was ok, but maybe weather-storm?) 
            # Block -> stop sign (process-stop)
            status_icon = "process-stop" if cmd.get("requires_end") else "weather-storm" 
            status_tooltip = "Requires 'Okay Done'" if cmd.get("requires_end") else "Instant Action"
            icon = Gtk.Image.new_from_icon_name(status_icon, Gtk.IconSize.MENU)
            icon.set_tooltip_text(status_tooltip)
            row.pack_start(icon, False, False, 0)
            
            # Info
            trigger = cmd.get("trigger", "??")
            # ctype = cmd.get("type", "??") # Type is now implicitly macro
            value = cmd.get("value", "??")
            
            label = Gtk.Label()
            enabled = cmd.get("enabled", True)
            fmt_trigger = f"<b>{trigger}</b>" if enabled else f"<s>{trigger}</s>"
            # Truncate value if too long
            disp_value = (value[:30] + '..') if len(value) > 30 else value
            label.set_markup(f"{fmt_trigger}: <span font_family='monospace'>{disp_value}</span>")
            label.set_halign(Gtk.Align.START)
            if not enabled:
                label.set_opacity(0.6)
            row.pack_start(label, True, True, 0)
            
            # Enable Switch
            switch = Gtk.Switch()
            switch.set_active(enabled)
            # connect using a closure to capture index safely? 
            # lambda w, s, idx=i: ...
            switch.connect("state-set", self._on_custom_command_toggled, i)
            row.pack_start(switch, False, False, 0)
            
            # Delete button
            del_btn = Gtk.Button(label="🗑️")
            del_btn.get_style_context().add_class("refresh-btn")
            del_btn.connect("clicked", self._on_delete_custom_command, i)
            row.pack_start(del_btn, False, False, 0)
            
            self.custom_listbox.add(row)
        
        self.custom_listbox.show_all()
        
    def _on_custom_command_toggled(self, switch, state, index):
        """Toggle enabled state of custom command."""
        commands = self.settings.custom_commands
        if 0 <= index < len(commands):
            commands[index]["enabled"] = state
            # Do NOT refresh listbox here to avoid destroying the switch user is clicking
            # Just update label opacity if we can find it?
            # Iterating children is messy. Let's just trust state is saved.
            # Visual feedback is the switch itself toggling.
            return True
        return False

    def _on_add_custom_command(self, button):
        trigger = self.new_cmd_trigger.get_text().strip().lower()
        val = self.new_cmd_editor.get_text().strip()
        req_end = self.new_cmd_end.get_active()
        
        if not trigger or not val:
            return
            
        # Check duplicate
        for cmd in self.settings.custom_commands:
            if cmd['trigger'] == trigger:
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Duplicate Trigger"
                )
                dialog.format_secondary_text(f"Command 'okay {trigger}' already exists.")
                dialog.run()
                dialog.destroy()
                return

        new_cmd = {
            "trigger": trigger,
            "type": "macro", # Always macro now
            "value": val,
            "requires_end": req_end,
            "enabled": True
        }
        
        cmds = list(self.settings.custom_commands)
        cmds.append(new_cmd)
        
        self.settings._settings["custom_commands"] = cmds 
        
        self._refresh_custom_commands()
        
        # Clear form
        self.new_cmd_trigger.set_text("")
        self.new_cmd_editor.set_text("")
        self.new_cmd_end.set_active(False)

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
        model_section.pack_start(self.model_combo, False, False, 0)

        # Model Info Label
        self.model_info_label = Gtk.Label()
        self.model_info_label.get_style_context().add_class("setting-desc")
        self.model_info_label.set_halign(Gtk.Align.START)
        self.model_info_label.set_margin_top(8)
        self.model_info_label.set_line_wrap(True)
        model_section.pack_start(self.model_info_label, False, False, 0)
        
        self.model_combo.connect("changed", self._on_model_changed)
        
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
        self.ollama_prompt_textview.set_sensitive(self.settings.ollama_custom_prompt_enabled)
        self._update_ollama_status()
        
        # Load Model Info
        self._on_model_changed(self.model_combo)
        
        # Load Custom Commands
        self._refresh_custom_commands()
        
        # Load Built-in commands (handled in init but update needed?)
        # Switches already set in init assuming settings loaded.
        # But if settings reloaded...
        for trigger, switch in self.built_in_switches.items():
            switch.set_active(trigger not in self.settings.disabled_commands)
    
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
        prompt_text = self.ollama_prompt_buffer.get_text(start_iter, end_iter, True)
        self.settings.set("ollama_system_prompt", prompt_text, save=False, notify=True)
        
        # Save disabled commands
        # Save disabled commands and overrides
        disabled = []
        overrides = {}
        
        for trigger, switch in self.built_in_switches.items():
            if not switch.get_active():
                disabled.append(trigger)
                
        for trigger, entry in self.built_in_entries.items():
            new_val = entry.get_text().strip().lower()
            if new_val and new_val != trigger:
                overrides[trigger] = new_val
                
        self.settings.set("disabled_commands", disabled, save=False, notify=True)
        self.settings.set("builtin_overrides", overrides, save=False, notify=True)
        
        # Custom Commands already updated in memory list, just trigger save
        # self.settings.set("custom_commands", ...) # unnecessary if we modified inplace
        
        self.settings.save()
        
        if self.on_save:
            self.on_save()
        
        self.hide()
    
    def _on_model_changed(self, combo):
        """Update model info when selection changes."""
        model_id = combo.get_active_id()
        if not model_id: return
        
        # Find model info
        info = ""
        for mid, desc in AVAILABLE_MODELS:
            if mid == model_id:
                info = desc
                break
        
        # Add detail based on ID
        details = {
            "tiny": "Fastest. Uses ~400MB RAM. Good for basic commands.",
            "base": "Balanced speed/accuracy. ~500MB RAM.",
            "small": "Good accuracy. ~1GB RAM.",
            "medium": "High accuracy. ~1.5GB RAM. Slower.",
            "large": "Highest accuracy. ~3GB RAM. Requires good GPU.",
            "turbo": "Optimized. Near-large accuracy with small model speed. Recommended.",
        }
        
        detail = details.get(model_id, "")
        self.model_info_label.set_text(f"{info}\n{detail}")

    def _on_command_toggled(self, switch, state, trigger):
        """Handle toggling built-in commands."""
        # We don't save immediately, we update our local set of disabled commands
        # Then save on "Save". But since switch state is persistent in UI...
        # We need to track it.
        # Actually easier to just read all switches on Save.
        pass

    def _on_builtin_trigger_changed(self, widget, event, orig_trigger):
        """Handle renaming a builtin command trigger."""
        # We handle actual saving in _on_save
        pass

    def _refresh_custom_commands(self):
        """Rebuild the custom commands listbox."""
        for child in self.custom_listbox.get_children():
            self.custom_listbox.remove(child)
            
        for i, cmd in enumerate(self.settings.custom_commands):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.set_margin_bottom(4)
            
            # Status Badge (End required?)
            status_icon = "media-playlist-repeat" if cmd.get("requires_end") else "media-flash"
            status_tooltip = "Wait for 'Okay Done'" if cmd.get("requires_end") else "Immediate Action"
            icon = Gtk.Image.new_from_icon_name(status_icon, Gtk.IconSize.MENU)
            icon.set_tooltip_text(status_tooltip)
            row.pack_start(icon, False, False, 0)
            
            # Info
            trigger = cmd.get("trigger", "??")
            ctype = cmd.get("type", "??")
            value = cmd.get("value", "??")
            
            label = Gtk.Label()
            # Mark disabled with strikethrough or grey
            enabled = cmd.get("enabled", True)
            fmt_trigger = f"<b>{trigger}</b>" if enabled else f"<s>{trigger}</s>"
            label.set_markup(f"{fmt_trigger} ({ctype}): <i>{value}</i>")
            label.set_halign(Gtk.Align.START)
            if not enabled:
                label.set_opacity(0.6)
            row.pack_start(label, True, True, 0)
            
            # Enable Switch
            switch = Gtk.Switch()
            switch.set_active(enabled)
            switch.connect("state-set", self._on_custom_command_toggled, i)
            row.pack_start(switch, False, False, 0)
            
            # Delete button
            del_btn = Gtk.Button(label="🗑️")
            del_btn.get_style_context().add_class("refresh-btn")
            del_btn.connect("clicked", self._on_delete_custom_command, i)
            row.pack_start(del_btn, False, False, 0)
            
            self.custom_listbox.add(row)
        
        self.custom_listbox.show_all()
        
    def _on_custom_command_toggled(self, switch, state, index):
        """Toggle enabled state of custom command."""
        commands = self.settings.custom_commands
        if 0 <= index < len(commands):
            commands[index]["enabled"] = state
            # Not saving to file yet, just updating object
            self._refresh_custom_commands() # To update label style
            return True
        return False

    def _on_add_custom_command(self, button):
        trigger = self.new_cmd_trigger.get_text().strip().lower()
        val = self.new_cmd_value.get_text().strip()
        ctype = self.new_cmd_type.get_active_id()
        req_end = self.new_cmd_end.get_active()
        
        if not trigger or not val:
            return
            
        # Check duplicate
        for cmd in self.settings.custom_commands:
            if cmd['trigger'] == trigger:
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Duplicate Trigger"
                )
                dialog.format_secondary_text(f"Command 'okay {trigger}' already exists.")
                dialog.run()
                dialog.destroy()
                return

        new_cmd = {
            "trigger": trigger,
            "type": ctype,
            "value": val,
            "requires_end": req_end,
            "enabled": True
        }
        
        cmds = list(self.settings.custom_commands)
        cmds.append(new_cmd)
        
        # Direct modify of singleton list
        self.settings._settings["custom_commands"] = cmds 
        
        self._refresh_custom_commands()
        
        # Clear form
        self.new_cmd_trigger.set_text("")
        self.new_cmd_value.set_text("")
        self.new_cmd_end.set_active(False)

    def _on_delete_custom_command(self, button, index):
        cmds = list(self.settings.custom_commands)
        if 0 <= index < len(cmds):
            cmds.pop(index)
            self.settings._settings["custom_commands"] = cmds
            self._refresh_custom_commands()

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