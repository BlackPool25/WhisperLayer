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
    
    # ... prompt hint methods ...

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
        self.register("tab", lambda: self._type_key("Tab"), requires_end=False)
        
        # --- Content Commands (need "command action ... command end") ---
        self.register("search", self._browser_search, requires_content=True, requires_end=True)
        self.register("google", self._browser_search, requires_content=True, requires_end=True)
        # Delta uses content_substitution_handler - response replaces command text in buffer
        self.register("delta", lambda x: None, requires_content=True, requires_end=True,
                      content_substitution_handler=self._ollama_get_response)
    
    def register(self, trigger: str, action: Callable, 
                 requires_content: bool = False, requires_end: bool = True,
                 substitution_handler: Optional[Callable[[], str]] = None,
                 content_substitution_handler: Optional[Callable[[str], str]] = None,
                 category: str = "general"):
        """Register a new voice command."""
        self.commands[trigger.lower().strip()] = CommandDefinition(
            trigger=trigger.lower().strip(),
            action=action,
            requires_content=requires_content,
            requires_end=requires_end,
            substitution_handler=substitution_handler,
            content_substitution_handler=content_substitution_handler,
            category=category
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
                 # Use non-greedy match for content
                 full_pat = f"(?P<CMD_{cmd.trigger.replace(' ', '_')}>{base_pat}{SEP}(?P<CONTENT_{cmd.trigger.replace(' ', '_')}>.+?){SEP}{trigger_regex}{SEP}{filler_regex}{end_regex})"
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
                                content = match.groupdict().get(content_key, "").strip()
                            
                            # Extract original case content if possible
                            start, end = match.span(name)
                            full_match_orig = text[start:end]
                            
                            content_orig = ""
                            if content:
                                c_start, c_end = match.span(f"CONTENT_{name[4:]}")
                                content_orig = text[c_start:c_end]
                            
                            # CONTENT SUBSTITUTION CHECK:
                            # If this command has a content_substitution_handler (like delta),
                            # execute it now and use the result as replacement text.
                            if cmd_def.content_substitution_handler:
                                # First, recursively process nested commands in content
                                if content_orig:
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
        
        # Clean up double spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

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
        if self._injector:
            self._injector.type_key(key)
        else:
            try:
                subprocess.run(["ydotool", "key", key], check=True, timeout=5)
            except Exception as e:
                print(f"Key type error: {e}")
    
    def _browser_search(self, query: str):
        """Open browser with search query."""
        if query and query.strip():
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query.strip())}"
            print(f"Searching: {query}")
            webbrowser.open(url)
        else:
            # Default to homepage if no query
            print("Opening browser home")
            webbrowser.open("https://www.google.com")
    
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
        
        # Sanitize the response for clean output:
        # 1. Remove markdown formatting (*, **, ``, etc.)
        # 2. Remove bullet points
        # 3. Collapse newlines into spaces
        # 4. Clean up excessive whitespace
        
        sanitized = response
        
        # Remove bold/italic markdown
        sanitized = re.sub(r'\*\*(.+?)\*\*', r'\1', sanitized)  # **bold**
        sanitized = re.sub(r'\*(.+?)\*', r'\1', sanitized)      # *italic*
        sanitized = re.sub(r'__(.+?)__', r'\1', sanitized)      # __bold__
        sanitized = re.sub(r'_(.+?)_', r'\1', sanitized)        # _italic_
        sanitized = re.sub(r'`(.+?)`', r'\1', sanitized)        # `code`
        
        # Remove markdown bullet points
        sanitized = re.sub(r'^\s*[\*\-\+]\s+', '', sanitized, flags=re.MULTILINE)
        
        # Collapse newlines into spaces (for clean single-line output)
        sanitized = sanitized.replace('\n', ' ').replace('\r', '')
        
        # Clean up multiple spaces
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        print(f"Ollama response sanitized: {len(sanitized)} chars")
        return sanitized


# Simple test
if __name__ == "__main__":
    detector = VoiceCommandDetector()
    
    test_cases = [
        "hello world",
        "hello jarvis copy world",
        "jarvis and search what is python jarvis stop more text",
        "jarvis search what is the best recipe jarvis and stop text",
        "before jarvis paste after",
        "jarvis new line",
        "jarvis please copy",
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
