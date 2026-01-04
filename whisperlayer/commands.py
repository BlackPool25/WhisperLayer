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
    
    Uses 'jarvis' as the trigger word - it's distinctive and Whisper recognizes it well.
    
    Patterns:
    - "jarvis copy" → Execute copy
    - "jarvis search what is python jarvis stop" → Search for "what is python"
    - Also handles: "jarvis and search", "jarvis stop", etc.
    """
    
    # The trigger word - 'okay' is simple, common, and Whisper always recognizes it
    # We also match variations like "OK", "O.K."
    TRIGGER = "okay"
    TRIGGER_VARIATIONS = {'okay', 'ok', 'o.k.', 'o.k'}
    
    # Words that Whisper might insert between trigger and action
    FILLER_WORDS = {'and', 'the', 'a', 'to', 'uh', 'um', 'so', 'please', 'now'}
    
    # Words that indicate end of content command
    # Using 'done' as primary since it's very distinctive
    END_WORDS = {'done', 'finished', 'complete', 'over', 'stop', 'end', 'execute', 'finish'}
    
    def __init__(self, injector=None):
        self._injector = injector
        self.commands: Dict[str, CommandDefinition] = {}
        self._register_default_commands()
        
        # Track what we've already executed
        self._executed_hashes: set = set()
    
    def get_prompt_hint(self) -> str:
        """Get hint text to add to Whisper prompt for better recognition."""
        # Include trigger word and common commands to help Whisper recognize them
        cmds = list(self.commands.keys())[:10]  # Top 10 commands
        return f"Voice commands use the trigger word 'Jarvis'. Commands: {', '.join(cmds)}. Say 'Jarvis stop' to end."
    
    def set_injector(self, injector):
        """Set the text injector for keyboard simulation."""
        self._injector = injector
    
    def _register_default_commands(self):
        """Register built-in voice commands."""
        # --- Immediate Commands (no content needed) ---
        self.register("copy", lambda: self._type_key("ctrl+c"))
        self.register("paste", lambda: self._type_key("ctrl+v"))
        self.register("cut", lambda: self._type_key("ctrl+x"))
        self.register("undo", lambda: self._type_key("ctrl+z"))
        self.register("redo", lambda: self._type_key("ctrl+shift+z"))
        self.register("select all", lambda: self._type_key("ctrl+a"))
        self.register("backspace", lambda: self._type_key("BackSpace"))
        self.register("delete", lambda: self._type_key("ctrl+BackSpace"))
        self.register("new line", lambda: self._type_key("Return"))
        self.register("enter", lambda: self._type_key("Return"))
        self.register("tab", lambda: self._type_key("Tab"))
        
        # --- Content Commands (need "command action ... command end") ---
        self.register("search", self._browser_search, requires_content=True)
        self.register("google", self._browser_search, requires_content=True)
        self.register("ollama", self._ollama_query, requires_content=True)
    
    def register(self, trigger: str, action: Callable, requires_content: bool = False,
                 category: str = "general"):
        """Register a new voice command."""
        self.commands[trigger.lower().strip()] = CommandDefinition(
            trigger=trigger.lower().strip(),
            action=action,
            requires_content=requires_content,
            category=category
        )
    
    def scan_text(self, text: str) -> Tuple[str, List[CommandMatch]]:
        """
        Scan text for complete command patterns.
        
        Returns:
            Tuple of (raw_text, cleaned_text, list of matched commands)
        """
        if not text:
            return text, []
        
        matches = []
        cleaned = text
        
        # Normalize for pattern matching
        text_lower = text.lower()
        
        # Build trigger pattern that matches any variation (okay, ok, o.k., etc.)
        trigger_regex = "(?:" + "|".join(re.escape(t) for t in self.TRIGGER_VARIATIONS) + ")"
        
        # Find all content commands first (they're more complex)
        # Pattern: okay [filler?] [action] ... okay [filler?] done
        for trigger, cmd in self.commands.items():
            if cmd.requires_content:
                # Build regex pattern that allows filler words
                filler_pattern = "(?:" + "|".join(self.FILLER_WORDS) + r")?\s*"
                end_pattern = "(?:" + "|".join(self.END_WORDS) + ")"
                
                # Handle multi-word triggers
                trigger_words = trigger.split()
                action_pattern = r"\s+".join(trigger_words)
                
                pattern = (
                    trigger_regex + r"\s+" + filler_pattern + action_pattern + 
                    r"\s+(.+?)\s+" + trigger_regex + r"\s+" + filler_pattern + end_pattern
                )
                
                for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                    content = match.group(1).strip()
                    full_match = text[match.start():match.end()]
                    
                    # Hash to avoid re-execution
                    match_hash = hash(full_match.lower())
                    if match_hash not in self._executed_hashes:
                        self._executed_hashes.add(match_hash)
                        
                        # Get original case content from the text
                        orig_content = text[match.start() + text_lower[match.start():].find(content.split()[0]) if content else match.start():match.end()]
                        # Extract just the content part using action_pattern
                        content_match = re.search(action_pattern + r"\s+(.+?)\s+" + trigger_regex, orig_content, re.IGNORECASE)
                        if content_match:
                            orig_content = content_match.group(1).strip()
                        else:
                            orig_content = content
                        
                        matches.append(CommandMatch(
                            command=cmd,
                            content=orig_content,
                            full_match=full_match
                        ))
                        
                        # Remove from cleaned text
                        cleaned = cleaned.replace(full_match, " ")
        
        # Find immediate commands (simpler pattern)
        # Pattern: okay [filler?] [action]
        for trigger, cmd in self.commands.items():
            if not cmd.requires_content:
                # Build regex
                filler_pattern = "(?:" + "|".join(self.FILLER_WORDS) + r")?\s*"
                trigger_words = trigger.split()
                action_pattern = r"\s+".join(trigger_words)
                
                pattern = trigger_regex + r"\s+" + filler_pattern + action_pattern + r"(?:\s|$|[.,!?])"
                
                for match in re.finditer(pattern, cleaned.lower(), re.IGNORECASE):
                    full_match = cleaned[match.start():match.end()].strip()
                    
                    match_hash = hash(full_match.lower())
                    if match_hash not in self._executed_hashes:
                        self._executed_hashes.add(match_hash)
                        
                        matches.append(CommandMatch(
                            command=cmd,
                            content="",
                            full_match=full_match
                        ))
                        
                        # Remove from cleaned text
                        cleaned = cleaned[:match.start()] + " " + cleaned[match.end():]
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned, matches
    
    def execute_matches(self, matches: List[CommandMatch]):
        """Execute all matched commands."""
        for match in matches:
            try:
                if match.command.requires_content:
                    if match.content:
                        print(f"Executing: {match.command.trigger} with content: '{match.content}'")
                        match.command.action(match.content)
                    else:
                        print(f"Skipping {match.command.trigger}: no content")
                else:
                    print(f"Executing: {match.command.trigger}")
                    match.command.action()
            except Exception as e:
                print(f"Command error: {e}")
    
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
    
    def _ollama_query(self, query: str):
        """Send query to Ollama (placeholder)."""
        if query and query.strip():
            print(f"Ollama: {query}")
            self._browser_search(f"AI {query}")


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
