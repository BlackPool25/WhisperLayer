"""Main application entry point for VoiceType."""

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


class VoiceTypeApp:
    """Main application controller for VoiceType."""
    
    def __init__(self, use_tray: bool = True):
        self.settings = get_settings()
        
        self.audio = AudioCapture()
        self.transcriber = Transcriber(on_transcription=self._on_transcription)
        self.overlay = OverlayController(on_cancel=self._on_overlay_cancel)
        self.injector = TextInjector()
        self.window_info = WindowInfo()
        self.hotkey = HotkeyManager(on_toggle=self._toggle_recording)
        
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
            self.tray.show_notification("VoiceType", f"Hotkey updated to {new_value}")
    
    def _on_model_change(self, new_value, old_value):
        """Handle model change - mark for reload."""
        print(f"Model changed: {old_value} -> {new_value}")
        self.transcriber._is_loaded = False
        self.transcriber.model = None
        if self.tray:
            self.tray.show_notification("VoiceType", f"Model will reload: {new_value}")
    
    def _on_device_change(self, new_value, old_value):
        """Handle compute device change."""
        print(f"Compute device changed: {old_value} -> {new_value}")
        self.transcriber._is_loaded = False
        self.transcriber.model = None
    
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
            self.tray.show_notification("VoiceType", "Settings applied!")
        
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
        
        # DON'T show overlay during recording - prevents focus stealing
        # Just use tray icon indicator instead
        # Overlay will appear at the end with results
        self.overlay.set_recording(True)
        self.overlay.set_transcription("")
        
        # Initialize streaming transcription state
        self._confirmed_text = ""  # Text that is finalized
        self._pending_text = ""    # Current sliding window transcription
        
        # Start audio capture
        self.audio.clear_buffer()
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
        
        # Combine confirmed text + any pending text for final result
        final_text = (self._confirmed_text + " " + self._pending_text).strip()
        
        # If we have significant pending audio, do one final transcription
        if self._accumulated_audio and not final_text:
            full_audio = np.concatenate(self._accumulated_audio)
            if len(full_audio) > config.SAMPLE_RATE * 0.3:
                result = self.transcriber.transcribe(full_audio)
                if result.text:
                    final_text = result.text.strip()
        
        self._final_text = final_text
        print(f"Final text: '{self._final_text}'")
        
        # Type the final text
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
                
                # --- SLIDING WINDOW TRANSCRIPTION ---
                # Only transcribe last ~5 seconds for constant speed
                window_samples = config.SAMPLE_RATE * 5  # 5 seconds
                full_audio = np.concatenate(self._accumulated_audio)
                
                if len(full_audio) > window_samples:
                    # Use sliding window - last 5 seconds only
                    window_audio = full_audio[-window_samples:]
                else:
                    window_audio = full_audio
                
                if len(window_audio) > config.SAMPLE_RATE * 0.5:  # At least 500ms
                    result = self.transcriber.transcribe(window_audio)
                    if result.text:
                        self._pending_text = result.text.strip()
                        # Combine confirmed + pending for display
                        display_text = (self._confirmed_text + " " + self._pending_text).strip()
                        print(f"Streaming: '{display_text}'")
                        self._final_text = display_text
                
                # Periodically confirm text (every ~3 seconds of audio)
                # This moves pending text to confirmed
                if current_time - self._last_confirm_time > 3.0 and self._pending_text:
                    self._confirmed_text = (self._confirmed_text + " " + self._pending_text).strip()
                    self._pending_text = ""
                    self._last_confirm_time = current_time
                    # Clear old audio, keep last 1 second for continuity
                    keep_samples = config.SAMPLE_RATE * 1
                    if len(full_audio) > keep_samples:
                        self._accumulated_audio = [full_audio[-keep_samples:]]
            
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
        # Stop audio capture
        self.audio.stop()
        
        # Update tray icon state
        if self.tray:
            self.tray.set_recording(False)
        
        # Update overlay
        self.overlay.set_recording(False)
        
        # Type the final text
        if self._final_text.strip():
            self.overlay.set_status("Typing...")
            time.sleep(0.2)
            
            success = self.injector.type_text(self._final_text)
            if success:
                self.overlay.set_status("Done!")
            else:
                self.overlay.set_status("Type failed")
        else:
            self.overlay.set_status("Done")
        
        # Hide overlay after a delay
        time.sleep(1.5)
        self.overlay.hide()
        print("Recording finalized (auto-stop)")
    
    def _on_transcription(self, result: TranscriptionResult):
        """Callback for transcription results."""
        if result.text:
            self._final_text = result.text
            self.overlay.set_transcription(result.text)
    
    def run(self):
        """Run the application."""
        print("=" * 50)
        print("VoiceType - Linux Native STT Voice Typing")
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
    app = VoiceTypeApp()
    app.run()


if __name__ == "__main__":
    main()
