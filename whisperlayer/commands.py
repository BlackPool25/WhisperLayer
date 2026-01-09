"""Voice command detection for WhisperLayer.

This module detects voice commands from transcription WITHOUT modifying the text flow.
Commands are only acted upon when the COMPLETE pattern is detected.

Design Principles:
1. NON-INVASIVE: Never modify or filter the transcription during streaming
2. PATTERN-BASED: Detect "Command [action]" or "Command [action] ... Command End" patterns
3. POST-PROCESSING: Extract and execute commands only after recording ends
4. FLEXIBLE MATCHING: Handle Whisper mishearing (e.g., "command and end" = "command end")
"""

from dataclasses import dataclass
from typing import Callable, Optional, Dict, List, Tuple
import re
import subprocess
import urllib.parse
import webbrowser


@dataclass
class CommandDefinition:
    """Definition of a voice command."""
    trigger: str                    # Primary trigger word/phrase
    action: Callable                # Function to execute
    requires_content: bool = False  # Does it need content between trigger and end?
    requires_end: bool = True       # Does it need an explicit end phrase?
    substitution_handler: Optional[Callable[[], str]] = None # Handler for text substitution (when nested)
    content_substitution_handler: Optional[Callable[[str], str]] = None  # Handler for content-based substitution (like delta)
    category: str = "general"       # Category for grouping
    scan_content: bool = True       # Whether to recursively scan content for other commands


@dataclass
class CommandMatch:
    """A matched command pattern in text."""
    command: CommandDefinition
    content: str                    # Content between "command action" and "command end"
    full_match: str                 # The full matched text to remove


class VoiceCommandDetector:
    """
    Detects voice commands from transcription text.
    """
    
    # The trigger word
    TRIGGER = "okay"
    TRIGGER_VARIATIONS = {'okay', 'ok', 'o.k.', 'o.k'}
    
    # Words that Whisper might insert between trigger and action
    FILLER_WORDS = {'and', 'the', 'a', 'to', 'uh', 'um', 'so', 'please', 'now'}
    
    # Words that indicate end of content command
    END_WORDS = {'done', 'finished', 'complete', 'over', 'stop', 'end', 'execute', 'finish'}
    
    def __init__(self, injector=None):
        self._injector = injector
        self.commands: Dict[str, CommandDefinition] = {}
        self._register_default_commands()
        
        # Track what we've already executed
        self._executed_hashes: set = set()
        
        # Cache for Ollama response (used for substitution pattern)
        self._last_ollama_response: str = ""
        
        # Load commands
        self.reload_commands()

    def reload_commands(self):
        """Reload all commands from defaults and settings."""
        self.commands.clear()
        self._register_default_commands()
        self._load_custom_commands()

    def _load_custom_commands(self):
        """Load custom commands from settings."""
        from .settings import get_settings
        settings = get_settings()
        
        for cmd in settings.custom_commands:
            if not cmd.get("enabled", True):
                continue
                
            trigger = cmd["trigger"]
            # cmd_type = cmd["type"] # Unused, always treated as macro now
            value = cmd["value"]
            requires_end = cmd.get("requires_end", False)
            requires_content = requires_end # Usually paired
            
            # --- Universal Macro Logic ---
            # We treat ALL custom commands as potential macros if they contain special chars
            # But to preserve backward compat and simplicity, we can just use the macro runner for everything.
            
            # Helper to execute macro
            def run_macro(m_val=value, *args):
                self._execute_macro(m_val)

            action = run_macro
            
            if requires_end or requires_content:
                 action = lambda c, v=value: self._execute_macro(v, content=c)
            else:
                 action = lambda v=value: self._execute_macro(v)

            # Register
            self.register(trigger, action, 
                          requires_content=requires_content, 
                          requires_end=requires_end,
                          category="custom")
                          
    def _execute_macro(self, macro_str: str, content: str = ""):
        """
        Execute a macro string containing text, keystrokes <...>, and command refs @...
        Supported formats:
        - Plain text: Types the text
        - <ctrl>+c: Types keys
        - @command: Executes a command
        - @command[arg]: Executes command with argument
        - {content}: Substitutes captured voice content
        """
        print(f"DEBUG: _execute_macro called with: '{macro_str}'")
        if content:
            macro_str = macro_str.replace("{content}", content)
        
        # Parse tokens:
        # 1. <keystroke>
        # 2. @command[arg] or @command
        # 3. plain text
        # Regex to split: (@[\w\s]+(?:\[.*?\])?)|(<[^>]+>)|([^@<]+)
        # Note: @command might be "@delta" or "@delta[arg]"
        
        pattern = re.compile(r'(@[\w]+(?:\[.*?\])?)|(<[^>]+>)|([^@<]+)')
        
        import time
        from .settings import get_settings
        
        for match in pattern.finditer(macro_str):
            cmd_ref, keystroke, text = match.groups()
            
            if cmd_ref:
                # Handle command reference
                # Format: @trigger or @trigger[arg]
                ref_trigger = cmd_ref[1:] # strip @
                ref_arg = ""
                
                if "[" in ref_trigger and ref_trigger.endswith("]"):
                    ref_trigger, ref_arg = ref_trigger.split("[", 1)
                    ref_arg = ref_arg[:-1] # strip ]
                
                # Normalize trigger
                ref_trigger = ref_trigger.lower().strip()
                
                # Find command
                # We need to map aliases if possible, or just look up directly
                # self.commands keys are lowercased effective triggers
                cmd = self.commands.get(ref_trigger)
                
                if cmd:
                    print(f"DEBUG: Macro executing @{ref_trigger} arg='{ref_arg}'")
                    if cmd.action:
                         # Handle content requirement
                         if cmd.requires_content:
                             # If arg provided, use it. If not, use 'content' passed to macro?
                             # But 'content' might have been used in {content}.
                             # If arg is empty, we might pass content if not used yet?
                             # Let's just pass ref_arg.
                             try:
                                 cmd.action(ref_arg)
                             except TypeError:
                                 # Fallback if action doesn't take args (shouln't happen if requires_content matches signature)
                                 cmd.action()
                         else:
                             cmd.action()
                    
                    # Wait a bit?
                    # time.sleep(0.1) 
                else:
                    print(f"WARNING: Macro referenced unknown command '@{ref_trigger}'")
                    
            elif keystroke:
                # Handle keystroke <ctrl>+c
                # Strip <> ? No, _type_key matches string parsing usually?
                # User puts <ctrl>+c. _type_key expects "ctrl+c" usually?
                # Let's check _type_key implementation.
                # Assuming it takes "ctrl+c" or "<ctrl>+c".
                # Standardize: remove < > wrap if it's single tag? 
                # Actually, standard format input is likely "ctrl+c". 
                # User prompt says "record keystrokes... auto convert".
                # Let's assume input is cleaned. But user might type <ctrl>+c.
                # Remove < and > for pynput/xdo compatibility logic usually.
                clean_key = keystroke.replace("<", "").replace(">", "")
                print(f"DEBUG: Macro typing key '{clean_key}'")
                self._type_key(clean_key)
                
            elif text:
                print(f"DEBUG: Macro typing text '{text}'")
                self._type_text(text)

    def _register_default_commands(self):
        """Register built-in voice commands."""
        # --- Immediate Commands (no content, no end trigger needed) ---
        # Note: requires_end=False matches "Okay copy" instantly
        self.register("copy", lambda: self._type_key("ctrl+c"), requires_end=False)
        self.register("paste", lambda: self._type_key("ctrl+v"), requires_end=False,
                      substitution_handler=self._get_clipboard_content)
        self.register("cut", lambda: self._type_key("ctrl+x"), requires_end=False)
        self.register("undo", lambda: self._type_key("ctrl+z"), requires_end=False)
        self.register("redo", lambda: self._type_key("ctrl+shift+z"), requires_end=False)
        self.register("select all", lambda: self._type_key("ctrl+a"), requires_end=False)
        self.register("backspace", lambda: self._type_key("BackSpace"), requires_end=False)
        self.register("delete", lambda: self._type_key("ctrl+BackSpace"), requires_end=False)
        self.register("new line", lambda: self._type_key("Return"), requires_end=False)
        self.register("enter", lambda: self._type_key("Return"), requires_end=False)
        
        # --- System Shortcut Commands ---
        # Super key - Activities overview (search apps, files, windows)
        self.register("super", lambda: self._type_key("super"), requires_end=False)
        
        # Alt+F2 - Run command prompt
        self.register("command prompt", lambda: self._type_key("alt+F2"), requires_end=False)
        
        # Super+L - Lock screen
        self.register("lock", lambda: self._type_key("super+l"), requires_end=False)
        
        # Alt+Tab - Switch between windows (replaces old tab which was just Tab key)
        self.register("tab", lambda: self._type_key("alt+Tab"), requires_end=False)
        
        # Ctrl+T - New tab
        self.register("new tab", lambda: self._type_key("ctrl+t"), requires_end=False)
        
        # Ctrl+N - New window
        self.register("new window", lambda: self._type_key("ctrl+n"), requires_end=False)
        
        # Old tab key kept as "press tab" just in case people want the key specifically
        self.register("press tab", lambda: self._type_key("Tab"), requires_end=False)
        
        # --- Content Commands (need "command action ... command end") ---
        self.register("search", self._browser_search, requires_content=True, requires_end=True)
        self.register("google", self._browser_search, requires_content=True, requires_end=True)
        
        # Delta uses content_substitution_handler - response replaces command text in buffer
        self.register("delta", lambda x: None, requires_content=True, requires_end=True,
                      content_substitution_handler=self._ollama_get_response)
        
        # --- Wait/Pause Command ---
        # "okay wait [duration] okay done" - Pauses command execution
        # Supports numbers (3, 300) and words ("three", "three hundred")
        self.register("wait", self._wait_action, requires_content=True, requires_end=True)
        
        # --- Raw Text Mode ---
        # "okay raw text [content] okay done" - Types content verbatim without command detection
        # This is useful when dictating text that contains command trigger words
        self.register("raw text", self._raw_text_handler, requires_content=True, requires_end=True,
                      content_substitution_handler=self._raw_text_passthrough, scan_content=False)
    
    
    def register(self, trigger: str, action: Callable, 
                 requires_content: bool = False, requires_end: bool = True,
                 substitution_handler: Optional[Callable[[], str]] = None,
                 content_substitution_handler: Optional[Callable[[str], str]] = None,
                 category: str = "general",
                 scan_content: bool = True):
        """Register a new voice command."""
        from .settings import get_settings
        settings = get_settings()
        
        base_trigger = trigger.lower().strip()
        
        # Check defaults disabled list (based on ORIGINAL names)
        # Note: We track checks by original name to ensure "disable copy" persists even if "copy" is renamed "dup"
        # The settings.disabled_commands usually stores original keys for builtins
        if category != "custom" and base_trigger in [t.lower() for t in settings.disabled_commands]:
            return

        # Check for Overrides (Renaming)
        effective_trigger = base_trigger
        if category != "custom":
            overrides = settings.builtin_overrides
            if base_trigger in overrides:
                effective_trigger = overrides[base_trigger].lower().strip()
                if not effective_trigger: # If renamed to empty, treat as disabled
                    return

        self.commands[effective_trigger] = CommandDefinition(
            trigger=effective_trigger,
            action=action,
            requires_content=requires_content,
            requires_end=requires_end,
            substitution_handler=substitution_handler,
            content_substitution_handler=content_substitution_handler,
            category=category,
            scan_content=scan_content
        )
        
    def _get_clipboard_content(self) -> str:
        """Get clipboard content for substitution."""
        if self._injector:
            return self._injector.get_clipboard_text()
        return ""
    
    def scan_text(self, text: str, is_nested: bool = False) -> Tuple[str, List[CommandMatch]]:
        """
        Scan text for complete command patterns.
        
        Args:
            text: Text to scan
            is_nested: Whether this scan is recursive (inside another command)
        
        Returns:
            Tuple of (cleaned_text, list of matched commands)
        """
        if not text:
            return text, []

        print(f"DEBUG: scan_text called with '{text}' (nested={is_nested})")
        
        matches = []
        cleaned = text
        text_lower = text.lower()
        
        # Build regex patterns dynamically based on registered commands
        # 1. Sort triggers by length (longest first) to avoid prefix matching issues
        sorted_commands = sorted(self.commands.values(), key=lambda c: len(c.trigger), reverse=True)
        
        # Robust separator
        SEP = r"(?:[.,!?]+\s*|\s+)"
        
        # Common patterns
        trigger_regex = "(?:" + "|".join(re.escape(t) for t in self.TRIGGER_VARIATIONS) + ")"
        filler_regex = "(?:" + "|".join(re.escape(f) for f in self.FILLER_WORDS) + r")?\s*"
        end_regex = "(?:" + "|".join(re.escape(e) for e in self.END_WORDS) + ")"
        
        # Construct specific pattern for each command
        # Format: (?:TRIGGER SEP FILLER ACTION_PATTERN ...rest)
        patterns = []
        
        for cmd in sorted_commands:
            # Handle multi-word triggers (e.g. "select all")
            trigger_words = cmd.trigger.split()
            action_pattern = SEP.join(re.escape(w) for w in trigger_words)
            
            # Base pattern: Trigger + Sep + Filler + CommandAction
            base_pat = f"{trigger_regex}{SEP}{filler_regex}{action_pattern}"
            
            if cmd.requires_end:
                 # Block Command: Base + SEP + Content + SEP + Trigger + SEP + Filler + End
                 # Use non-greedy match for content, allow empty content with .*?
                 full_pat = f"(?P<CMD_{cmd.trigger.replace(' ', '_')}>{base_pat}(?:{SEP}(?P<CONTENT_{cmd.trigger.replace(' ', '_')}>.*?))?{SEP}{trigger_regex}{SEP}{filler_regex}{end_regex})"
            else:
                 # Instant Command: Base only
                 # Ensure word boundary at end to avoid partial matches
                 full_pat = f"(?P<CMD_{cmd.trigger.replace(' ', '_')}>{base_pat})(?![a-zA-Z0-9])"
            
            patterns.append(full_pat)
        
        # Combine all command patterns into one BIG regex using OR
        combined_pattern = "|".join(patterns)
        
        # Collect removal/replacement spans (start, end, replacement_text)
        replacement_spans = []
        
        # Iteratively find matches
        for match in re.finditer(combined_pattern, text_lower, re.IGNORECASE):
            # Identify which command matched
            for name, value in match.groupdict().items():
                if value and name.startswith("CMD_"):
                    trigger_key = name[4:].replace('_', ' ') # Restore trigger
                    cmd_def = self.commands.get(trigger_key)
                    
                    if cmd_def:
                        # Deduplication using full match hash
                        match_hash = hash(value)
                        
                        if match_hash not in self._executed_hashes:
                            print(f"DEBUG: Matched command '{trigger_key}'")
                            self._executed_hashes.add(match_hash)
                            
                            # SUBSTITUTION CHECK:
                            # If we are nested AND this command has a substitution handler,
                            # we treat it as text substitution, NOT a command execution.
                            if is_nested and cmd_def.substitution_handler:
                                subst_text = cmd_def.substitution_handler()
                                print(f"DEBUG: Substituting nested command '{trigger_key}' with clipboard content.")
                                replacement_spans.append((*match.span(name), subst_text))
                                continue # processing matches (don't add to matches list)
                            
                            
                            content = ""
                            if cmd_def.requires_content:
                                content_key = f"CONTENT_{name[4:]}"
                                content = match.groupdict().get(content_key) or ""
                                content = content.strip()
                            
                            # Extract original case content if possible
                            start, end = match.span(name)
                            full_match_orig = text[start:end]
                            
                            content_orig = ""
                            if content:
                                c_start, c_end = match.span(f"CONTENT_{name[4:]}")
                                content_orig = text[c_start:c_end]
                            
                            # If this command has a content_substitution_handler (like delta),
                            # execute it now and use the result as replacement text.
                            if cmd_def.content_substitution_handler:
                                # First, recursively process nested commands in content (IF ALLOWED)
                                if content_orig and cmd_def.scan_content:
                                    sub_cleaned, sub_matches = self.scan_text(content_orig, is_nested=True)
                                    if sub_matches:
                                        matches.extend(sub_matches)
                                    content_orig = sub_cleaned.strip()
                                
                                # Execute the handler with the (possibly substituted) content
                                subst_text = cmd_def.content_substitution_handler(content_orig)
                                print(f"DEBUG: Content substitution for '{trigger_key}' -> {len(subst_text)} chars")
                                replacement_spans.append((*match.span(name), subst_text))
                                continue  # Don't add to matches - already handled
                            
                            matches.append(CommandMatch(
                                command=cmd_def,
                                content=content_orig,
                                full_match=full_match_orig
                            ))
                            
                            # RECURSIVE CHECK: Scan the content for nested commands
                            if content_orig:
                                # Recursively scan the content with is_nested=True
                                sub_cleaned, sub_matches = self.scan_text(content_orig, is_nested=True)
                                
                                if sub_matches or sub_cleaned != content_orig:
                                    # If matches found OR text substituted
                                    print(f"DEBUG: Found nested commands/substitution inside '{trigger_key}'")
                                    matches.extend(sub_matches)
                                    matches[-1 - len(sub_matches)].content = sub_cleaned.strip()
                            
                            # Mark for removal (empty replacement)
                            replacement_spans.append((*match.span(name), ""))

                        else:
                            print(f"DEBUG: Skipping duplicate match for '{trigger_key}'")
                        
                        break # Stop checking other groups for this match

        # --- Cleaning / Substitution ---
        # Sort reverse to apply changes from end to start
        replacement_spans.sort(key=lambda x: x[0], reverse=True)
        
        for start, end, repl in replacement_spans:
            cleaned = cleaned[:start] + repl + cleaned[end:]
        
        # Clean up double spaces (preserve newlines)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()

        return cleaned, matches
    
    def execute_matches(self, matches: List[CommandMatch]):
        """Execute all matched commands."""
        print(f"DEBUG: execute_matches called with {len(matches)} matches")
        for match in matches:
            try:
                print(f"DEBUG: Processing match: {match.command.trigger}")
                if match.command.requires_content:
                    # Execute even if content is empty (e.g. nested command consumed it)
                    # The action function should handle empty content gracefully
                    print(f"Executing: {match.command.trigger} with content: '{match.content}'")
                    match.command.action(match.content)
                else:
                    print(f"Executing: {match.command.trigger}")
                    match.command.action()
            except Exception as e:
                print(f"Command error: {e}")
                import traceback
                traceback.print_exc()
    
    def reset(self):
        """Reset state for new recording session."""
        self._executed_hashes.clear()
    
    # --- Command Actions ---
    
    def _type_key(self, key: str):
        """Type a key combination."""
        print(f"Typing key: {key}")
        # Ensure we have an injector with proper key mapping
        if self._injector is None:
            from .system import TextInjector
            self._injector = TextInjector()
        self._injector.type_key(key)

    def _type_text(self, text: str):
        """Type raw text."""
        print(f"Typing text: {text}")
        if self._injector and hasattr(self._injector, 'type_string'):
            self._injector.type_string(text)
        else:
            try:
                # Add delay to prevent dropped characters
                # --key-delay 15 usually safe for ydotool
                subprocess.run(["ydotool", "type", "--key-delay", "15", text], check=True)
            except Exception as e:
                print(f"Text type error: {e}")

    def _browser_search(self, query: str):
        """Open browser with search query and bring to focus."""
        import subprocess
        
        if query and query.strip():
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query.strip())}"
            print(f"Searching: {query}")
            webbrowser.open(url)
        else:
            # Default to homepage if no query
            print("Opening browser home")
            webbrowser.open("https://www.google.com")
        
        # Bring browser to focus
        # On Wayland, wmctrl doesn't work. Use ydotool to send alt+tab
        # which will switch to the browser that was just opened
        import time
        time.sleep(0.5)  # Wait for browser window to appear
        
        try:
            # Use ydotool to send alt+tab (switches to most recent window - the browser)
            result = subprocess.run(
                ["/usr/bin/ydotool", "key", "alt+Tab"],
                capture_output=True, timeout=2
            )
            if result.returncode == 0:
                print("Focused browser via alt+tab")
        except Exception as e:
            print(f"Browser focus failed: {e}")

    def _ollama_get_response(self, query: str) -> str:
        """
        Query Ollama and return the response for substitution.
        This is used as a content_substitution_handler - the response
        replaces the command text in the buffer, enabling nesting.
        """
        from .ollama_service import get_ollama_service
        from .settings import get_settings
        import re
        
        settings = get_settings()
        
        # Check if Ollama is enabled
        if not settings.ollama_enabled:
            print("Ollama is disabled in settings")
            return "[Ollama disabled]"
        
        if not query or not query.strip():
            print("Empty Ollama query, skipping")
            return ""
        
        service = get_ollama_service()
        
        if not service.is_available():
            print("Ollama not available - make sure 'ollama serve' is running")
            return "[Ollama not available]"
        
        # Query Ollama
        print(f"Ollama query: '{query}' (model: {settings.ollama_model})")
        response = service.generate(query.strip())
        self._last_ollama_response = response
        
        if not response:
            return "[No response from Ollama]"
        
        # Sanitize the response, but PRESERVE structure (bullets, newlines)
        # 1. Remove markdown style formatting (*, **, ``, etc.) but keep the text
        # 2. Key sanitization (smart quotes to ASCII)
        
        sanitized = response
        
        # Remove bold/italic markdown
        sanitized = re.sub(r'\*\*(.+?)\*\*', r'\1', sanitized)  # **bold**
        sanitized = re.sub(r'\*(.+?)\*', r'\1', sanitized)      # *italic*
        sanitized = re.sub(r'__(.+?)__', r'\1', sanitized)      # __bold__
        sanitized = re.sub(r'_(.+?)_', r'\1', sanitized)        # _italic_
        sanitized = re.sub(r'`(.+?)`', r'\1', sanitized)        # `code`
        
        # ASCII Sanitization: Replace smart quotes and dashes to ensure ydotool can type them
        replacements = {
            '“': '"', '”': '"',
            '‘': "'", '’': "'",
            '–': '-', '—': '-',
            '…': '...'
        }
        for char, repl in replacements.items():
            sanitized = sanitized.replace(char, repl)
        
        # Do NOT flatten newlines or remove bullets. 
        # Clean up multiple spaces/tabs but keep newlines
        sanitized = re.sub(r'[ \t]+', ' ', sanitized).strip()
        
        print(f"Ollama response sanitized: {len(sanitized)} chars")
        return sanitized

    def _raw_text_handler(self, content: str):
        """
        Handler for raw text command.
        The raw text content is passed through without any command processing.
        The action does nothing - substitution handler returns the content verbatim.
        """
        # No action needed - content is handled by substitution
        pass
    
    def _raw_text_passthrough(self, content: str) -> str:
        """
        Substitution handler for raw text - returns content unchanged.
        This allows users to dictate text containing command trigger words
        without them being interpreted as commands.
        """
        return content.strip()
    
    def _parse_wait_time(self, content: str) -> float:
        """
        Parse wait duration from voice content.
        Supports: numbers (3, 300), words ("three", "three hundred", "two thousand").
        Defaults to 1 second if parsing fails.
        """
        if not content or not content.strip():
            return 1.0
        
        text = content.lower().strip()
        # Remove common suffixes
        text = re.sub(r'\s*(milli)?seconds?|secs?|ms\s*', '', text).strip()
        
        if not text:
            return 1.0
        
        # Try numeric parse first
        try:
            return float(text)
        except ValueError:
            pass
        
        # Use word2number for "three hundred", "two thousand", etc.
        try:
            from word2number import w2n
            return float(w2n.word_to_num(text))
        except Exception:
            pass
        
        return 1.0  # Default
    
    def _wait_action(self, content: str):
        """
        Wait/pause command action.
        Pauses command execution for the specified duration.
        """
        import time
        duration = self._parse_wait_time(content)
        # Safety cap at 1 hour
        duration = min(duration, 3600.0)
        print(f"Wait command: pausing for {duration} seconds...")
        time.sleep(duration)
        print(f"Wait complete.")


# Simple test
if __name__ == "__main__":
    detector = VoiceCommandDetector()
    
    # Mock settings for custom command test
    class MockSettings:
        disabled_commands = []
        custom_commands = [
            {"trigger": "my shortcut", "type": "shortcut", "value": "<ctrl>+t", "requires_end": False, "enabled": True},
            {"trigger": "my text", "type": "text", "value": "Hello World", "requires_end": False, "enabled": True}
        ]
    
    import sys
    sys.modules['whisperlayer.settings'] = type('obj', (object,), {'get_settings': lambda: MockSettings()})
    
    # Reload to pick up mocks
    detector.reload_commands()

    test_cases = [
        "hello world",
        "hello jarvis copy world",
        "okay raw text please ignore okay copy inside okay done",
        "okay raw text okay copy okay done",
        "okay my shortcut and okay my text",
        "okay super",
        "okay lock",
    ]
    
    print("Testing VoiceCommandDetector:")
    print("-" * 60)
    
    for text in test_cases:
        detector.reset()  # Reset for each test
        cleaned, matches = detector.scan_text(text)
        cmds = [(m.command.trigger, m.content) for m in matches]
        print(f"Input:    '{text}'")
        print(f"Cleaned:  '{cleaned}'")
        print(f"Commands: {cmds}")
        print()
