"""Main application entry point for WhisperLayer."""

import signal
import sys
import time
import threading
import numpy as np
from typing import Optional

from . import config
from .audio import AudioCapture
from .transcriber import Transcriber, TranscriptionResult
from .overlay import OverlayController
from .system import TextInjector, WindowInfo
from .hotkey import HotkeyManager
from .tray import SystemTray
from .settings import get_settings
from .commands import VoiceCommandDetector


class WhisperLayerApp:
    """Main application controller for WhisperLayer."""
    
    def __init__(self, use_tray: bool = True):
        self.settings = get_settings()
        
        self.audio = AudioCapture()
        self.transcriber = Transcriber(on_transcription=self._on_transcription)
        self.overlay = OverlayController(on_cancel=self._on_overlay_cancel)
        self.injector = TextInjector()
        self.window_info = WindowInfo()
        self.hotkey = HotkeyManager(on_toggle=self._toggle_recording)
        
        # Voice command detector (non-invasive, only acts on complete patterns)
        self.command_detector = VoiceCommandDetector(injector=self.injector)
        
        # System tray
        self.use_tray = use_tray
        self.tray = SystemTray(
            on_toggle=self._toggle_recording,
            on_settings=self._show_settings,
            on_quit=self._on_quit
        ) if use_tray else None
        
        self._settings_window = None
        
        self._is_recording = False
        self._recording_lock = threading.Lock()
        self._accumulated_audio: list[np.ndarray] = []
        self._last_speech_time = 0.0
        self._transcription_thread: Optional[threading.Thread] = None
        self._stop_transcription = threading.Event()
        
        # Final text to type after recording stops
        self._final_text = ""
        
        # Register for specific settings changes for hot-reload
        self.settings.on_change("hotkey", self._on_hotkey_change)
        self.settings.on_change("model", self._on_model_change)
        self.settings.on_change("device", self._on_device_change)
        self.settings.on_change("input_device_id", self._on_audio_device_change)
        self.settings.on_change("silence_duration", self._on_silence_change)
    
    def _on_hotkey_change(self, new_value, old_value):
        """Handle hotkey change - restart hotkey listener."""
        print(f"Hotkey changed: {old_value} -> {new_value}")
        self.hotkey.stop()
        time.sleep(0.1)  # Brief delay for cleanup
        self.hotkey = HotkeyManager(on_toggle=self._toggle_recording, hotkey=new_value)
        self.hotkey.start()
        if self.tray:
            self.tray.show_notification("WhisperLayer", f"Hotkey updated to {new_value}")
    
    def _on_model_change(self, new_value, old_value):
        """Handle model change - unload and mark for reload."""
        print(f"Model changed: {old_value} -> {new_value}")
        # Properly unload the model to free GPU memory
        self.transcriber.unload_model()
        if self.tray:
            self.tray.show_notification("WhisperLayer", f"Model will reload: {new_value}")
    
    def _on_device_change(self, new_value, old_value):
        """Handle compute device change - requires model reload."""
        print(f"Compute device changed: {old_value} -> {new_value}")
        # Need to unload and reload on different device
        self.transcriber.unload_model()
    
    def _on_audio_device_change(self, new_value, old_value):
        """Handle audio input device change."""
        print(f"Audio device changed: {old_value} -> {new_value}")
        self.audio.device = new_value
    
    def _on_silence_change(self, new_value, old_value):
        """Handle silence duration change."""
        print(f"Silence duration changed: {old_value} -> {new_value}")
        config.SILENCE_DURATION = new_value
    
    def _show_settings(self):
        """Show settings window."""
        from .settings_ui import SettingsWindow
        
        # Callbacks to pause/resume hotkey listener during capture
        def on_capture_start():
            print("Pausing hotkey listener for capture...")
            if self.hotkey:
                self.hotkey.stop()
        
        def on_capture_end():
            print("Resuming hotkey listener...")
            # Reload settings to get new hotkey
            settings = get_settings()
            self.hotkey = HotkeyManager(on_toggle=self._toggle_recording, hotkey=settings.hotkey)
            self.hotkey.start()
            
        if self._settings_window:
            try:
                self._settings_window.destroy()
            except:
                pass
                
        try:
            self._settings_window = SettingsWindow(
                on_save=self._on_settings_saved,
                on_capture_start=on_capture_start,
                on_capture_end=on_capture_end
            )
            self._settings_window.show_all()
        except Exception as e:
            print(f"Error creating settings window: {e}")
            if self.tray:
                self.tray.show_notification("Error", f"Could not open settings: {e}")
    
    def _on_settings_saved(self):
        """Handle settings save - settings are now hot-reloaded via callbacks."""
        # Reload config values for backward compatibility
        config.reload_settings()
        
        if self.tray:
            self.tray.show_notification("WhisperLayer", "Settings applied!")
        
        print("Settings saved and applied!")
    
    def _on_quit(self):
        """Handle quit from tray."""
        print("Quit requested, shutting down...")
        self.shutdown()
        import os
        os._exit(0)
    
    def _toggle_recording(self):
        """Toggle recording state (called from hotkey)."""
        with self._recording_lock:
            if self._is_recording:
                self._stop_recording()
            else:
                self._start_recording()
    
    def _on_overlay_cancel(self):
        """Handle cancel button click from overlay."""
        print("Cancel clicked - stopping and hiding...")
        with self._recording_lock:
            if self._is_recording:
                self._stop_recording()
        # Always hide overlay when cancel is clicked
        self.overlay.hide()
    
    def _start_recording(self):
        """Start recording and transcription."""
        self._is_recording = True
        self._accumulated_audio = []
        self._final_text = ""
        self._stop_transcription.clear()
        
        # Update tray icon state
        if self.tray:
            self.tray.set_recording(True)
        
        # Update window name
        window_name = self.window_info.get_active_window_name()
        self.overlay.set_window_name(window_name)
        
        # Show overlay during recording to display live transcription
        self.overlay.set_recording(True)
        self.overlay.set_transcription("Listening...")
        self.overlay.set_status("🎤 Recording")
        self.overlay.show()  # Show overlay now
        
        # Initialize streaming transcription state
        self._confirmed_text = ""  # Text that is finalized
        self._pending_text = ""    # Current sliding window transcription
        
        # Reset command detector for new session
        self.command_detector.reset()
        
        # Start audio capture
        self.audio.clear_buffer()
        self._accumulated_audio = []  # CRITICAL: Clear local audio buffer from previous session
        self.audio.start()
        
        # Start transcription thread
        self._transcription_thread = threading.Thread(
            target=self._transcription_loop, 
            daemon=True
        )
        self._transcription_thread.start()
        
        self._last_speech_time = time.time()
        self._last_confirm_time = time.time()
        print("Recording started (tray icon shows status)")
    
    def _stop_recording(self):
        """Stop recording and finalize transcription."""
        self._is_recording = False
        self._stop_transcription.set()
        
        # Update tray icon state
        if self.tray:
            self.tray.set_recording(False)
        
        # Stop audio capture
        self.audio.stop()
        
        # Update overlay
        self.overlay.set_recording(False)
        self.overlay.set_status("Processing...")
        
        # Wait for transcription thread to finish
        if self._transcription_thread and self._transcription_thread.is_alive():
            self._transcription_thread.join(timeout=2.0)
        
        # Combine confirmed text + pending text
        # Since we use Full Buffer Transcription now, pending_text usually has everything
        final_text = (self._confirmed_text + " " + self._pending_text).strip()
        
        # Only do a final transcription if we have absolutely nothing
        # The streaming loop (Full Buffer) is accurate and we shouldn't risk
        # a final glitch/corruption by re-transcribing the same buffer again
        if self._accumulated_audio and not final_text:
            try:
                full_audio = np.concatenate(self._accumulated_audio)
                if len(full_audio) > config.SAMPLE_RATE * 0.3:
                    result = self.transcriber.transcribe(full_audio)
                    if result.text:
                        final_text = result.text.strip()
            except Exception as e:
                print(f"Final transcription failed: {e}")
        
        self._final_text = final_text
        print(f"Final text: '{self._final_text}'")
        
        # Detect and execute voice commands from the final text
        # This is POST-PROCESSING: only complete patterns are detected
        if self._final_text.strip():
            cleaned_text, matches = self.command_detector.scan_text(self._final_text)
            if matches:
                print(f"Detected {len(matches)} command(s)")
                # Execute all detected commands
                self.command_detector.execute_matches(matches)
                # Use cleaned text (with command patterns removed)
                self._final_text = cleaned_text
                print(f"Text after commands: '{self._final_text}'")
        
        # Type the final text (with commands removed)
        if self._final_text.strip():
            # Brief overlay showing final result
            self.overlay.set_transcription(self._final_text)
            self.overlay.set_status("Typing...")
            self.overlay.show()  # Only show now, after recording done
            time.sleep(0.3)
            
            print(f"Typing text: '{self._final_text}'")
            success = self.injector.type_text(self._final_text)
            print(f"Type result: {success}")
            if success:
                self.overlay.set_status("Done!")
            else:
                self.overlay.set_status("Type failed")
        else:
            self.overlay.set_transcription("(No speech detected)")
            self.overlay.set_status("Done")
            self.overlay.show()
        
        # Hide overlay after a short delay
        def hide_later():
            time.sleep(1.0)
            self.overlay.hide()
        
        threading.Thread(target=hide_later, daemon=True).start()
        print("Recording stopped")
    
    def _transcription_loop(self):
        """Background loop for live transcription updates."""
        # Ensure model is loaded
        self.transcriber.load_model()
        
        chunk_interval = config.CHUNK_DURATION
        last_process_time = time.time()
        
        while not self._stop_transcription.is_set():
            # Get audio chunks from queue
            chunk = self.audio.get_chunk(timeout=0.1)
            if chunk is not None:
                self._accumulated_audio.append(chunk)
                
                # Calculate audio level for voice-reactive overlay
                rms = self.audio.calculate_rms(chunk)
                # Normalize RMS to 0-1 range - boost significantly for visible waves
                audio_level = min(1.0, rms * 15.0)  # Increased from 5x to 15x
                if audio_level > 0.1:  # Only log significant audio
                    print(f"Audio level: {audio_level:.2f}")
                self.overlay.set_audio_level(audio_level)
                
                # Check if it's speech
                if not self.audio.is_silence(chunk):
                    self._last_speech_time = time.time()
            
            # Process periodically for live updates - SLIDING WINDOW for speed
            current_time = time.time()
            if current_time - last_process_time >= chunk_interval and self._accumulated_audio:
                last_process_time = current_time
                
                # --- FULL BUFFER TRANSCRIPTION ---
                # Transcribing the full buffer avoids duplication issues caused by 
                # sliding windows and audio trimming boundaries.
                # Whisper is fast enough for typical command lengths (< 30s).
                full_audio = np.concatenate(self._accumulated_audio)
                window_audio = full_audio
                
                if len(window_audio) > config.SAMPLE_RATE * 0.5:  # At least 500ms
                    result = self.transcriber.transcribe(window_audio)
                    if result.text:
                        # Use transcription directly
                        self._pending_text = result.text.strip()
                        
                        # Full text is just the pending text (since we process full audio)
                        display_text = self._pending_text
                        print(f"Streaming: '{display_text}'")
                        self._final_text = display_text
                        
                        # Update overlay with live transcription
                        self.overlay.set_transcription(display_text[-100:] if len(display_text) > 100 else display_text)
                
                # Note: We removed the periodic confirmation/audio trimming logic
                # because it was causing text duplication on overlap boundaries.
                # The buffer is fully cleared when recording stops.
            
            # Auto-stop after silence (use settings value)
            silence_timeout = self.settings.silence_duration
            silence_duration = current_time - self._last_speech_time
            if silence_duration > silence_timeout:
                print(f"Auto-stopping after {silence_duration:.1f}s silence")
                self._stop_transcription.set()
                # Trigger stop from main context
                with self._recording_lock:
                    if self._is_recording:
                        self._is_recording = False
                        threading.Thread(target=self._finalize_recording, daemon=True).start()
    
    def _finalize_recording(self):
        """Finalize recording after auto-stop."""
        print("DEBUG: Finalizing recording (auto-stop)...")
        # Delegate to the main stop method to ensure consistent behavior
        # (Command execution, overlay updates, typing, etc.)
        self._stop_recording()
        print("Recording finalized (auto-stop)")
    
    def _on_transcription(self, result: TranscriptionResult):
        """Callback for transcription results."""
        if result.text:
            self._final_text = result.text
            self.overlay.set_transcription(result.text)
    
    def run(self):
        """Run the application."""
        print("=" * 50)
        print("WhisperLayer - Linux Native STT Voice Typing")
        print("=" * 50)
        print(f"Session: {self.window_info.get_session_info()}")
        print(f"Hotkey: {config.HOTKEY}")
        print(f"Model: {config.WHISPER_MODEL}")
        print("-" * 50)
        print("Press the hotkey to start/stop recording.")
        print("Press Ctrl+C to exit.")
        print("-" * 50)
        
        # Pre-load model (takes a few seconds)
        print("\nLoading Whisper model (this may take a moment)...")
        self.transcriber.load_model()
        
        # Start overlay (runs GTK in background thread)
        self.overlay.start()
        
        # Start system tray if enabled
        if self.tray:
            self.tray.start()
        
        # Start hotkey listener
        self.hotkey.start()
        
        # Set up signal handler for clean exit
        def signal_handler(sig, frame):
            print("\nShutting down...")
            self.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep running
        print("\nReady! Waiting for hotkey...")
        try:
            self.hotkey.wait()
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown of all components."""
        if self._is_recording:
            self.audio.stop()
        
        self.hotkey.stop()
        self.overlay.stop()
        self.transcriber.stop_worker()
        print("Shutdown complete")


def main():
    """Entry point."""
    app = WhisperLayerApp()
    app.run()


if __name__ == "__main__":
    main()
