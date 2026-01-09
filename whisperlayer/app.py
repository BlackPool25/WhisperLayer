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
        self._completion_event = threading.Event() # Main loop keep-alive
        
        # Final text to type after recording stops
        self._final_text = ""
        
        # Register for specific settings changes for hot-reload
        self.settings.on_change("hotkey", self._on_hotkey_change)
        self.settings.on_change("model", self._on_model_change)
        self.settings.on_change("device", self._on_device_change)
        self.settings.on_change("input_device_id", self._on_audio_device_change)
        self.settings.on_change("silence_duration", self._on_silence_change)
        self.settings.on_change("ollama_model", self._on_ollama_model_change)
        self.settings.on_change("custom_commands", self._on_custom_commands_change)

    # ... (skipping methods) ...

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
        
        # Set application name for task managers
        try:
            import gi
            gi.require_version('GLib', '2.0')
            from gi.repository import GLib
            GLib.set_prgname('whisperlayer')
            GLib.set_application_name('WhisperLayer')
        except Exception as e:
            print(f"Warning: Could not set application name: {e}")

        # Set up signal handler for clean exit
        def signal_handler(sig, frame):
            print("\nShutting down...")
            # Signal the main loop to exit
            self._completion_event.set()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep running until shutdown is requested
        print("\nReady! Waiting for hotkey...")
        try:
            self._completion_event.wait()
        except KeyboardInterrupt:
            # Should be handled by signal handler, but just in case
            pass
            
        # Perform clean shutdown
        self.shutdown()
        
        # Verify if we should force exit to avoid segfaults from mixed Qt/GTK usage
        # Hard exit via C library to bypass ALL cleanup
        import sys
        sys.stdout.flush()
        import ctypes
        try:
            ctypes.CDLL(None)._exit(0)
        except:
            import os
            os._exit(0)
    
    def shutdown(self):
        """Clean shutdown of all components."""
        # Ensure it is set (in case called from elsewhere)
        self._completion_event.set()
        
        if self._is_recording:
            self.audio.stop()
        
        if self.hotkey:
            self.hotkey.stop()
        
        if self.tray:
            try:
                self.tray.stop()
            except:
                pass
        
        if self.overlay:
            self.overlay.stop()
            
        if self.transcriber:
            self.transcriber.stop_worker()
            
        print("Shutdown complete")
    
    def _on_hotkey_change(self, new_value, old_value):
        """Handle hotkey change - update hotkey configuration (thread-safe)."""
        print(f"Hotkey changed: {old_value} -> {new_value}")
        # Use thread-safe update instead of stop/start to avoid Qt threading issues
        if self.hotkey:
            self.hotkey.update_hotkey(new_value)
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
    
    def _on_ollama_model_change(self, new_value, old_value):
        """Handle Ollama model change - reload model in real-time."""
        print(f"Ollama model changed: {old_value} -> {new_value}")
        try:
            from .ollama_service import get_ollama_service
            service = get_ollama_service()
            if service.is_available():
                service.load_model(new_value)
                if self.tray:
                    self.tray.show_notification("WhisperLayer", f"Ollama model: {new_value}")
        except Exception as e:
            print(f"Error loading Ollama model: {e}")
    
    def _on_custom_commands_change(self, new_value, old_value):
        """Handle custom commands change - reload command detector for hot-reload."""
        print("Custom commands changed, reloading command detector...")
        self.command_detector.reload_commands()
        if self.tray:
            self.tray.show_notification("WhisperLayer", "Custom commands updated!")
    
    def _show_settings(self):
        """Show settings window."""
        from .settings_ui import SettingsWindow
        
        # Callbacks to pause/resume hotkey listener during capture
        def on_capture_start():
            print("Pausing hotkey listener for capture...")
            if self.hotkey:
                self.hotkey.pause()
        
        def on_capture_end():
            print("Resuming hotkey listener...")
            if self.hotkey:
                self.hotkey.resume()
            
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
            
            # Execute any detected commands
            if matches:
                print(f"Detected {len(matches)} command(s)")
                self.command_detector.execute_matches(matches)
            
            # Use cleaned text if it changed (commands removed OR substitutions applied)
            if cleaned_text != self._final_text:
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
                        
                        # --- SAFE SLIDING WINDOW ---
                        # Keep buffer size manageable by finalizing segments that are "safe"
                        # (i.e. ended long enough ago to not be part of an active command)
                        
                        # Current buffer duration (approx)
                        buffer_duration = len(window_audio) / config.SAMPLE_RATE
                        
                        # If buffer gets too long (> 20s), we must slice safely
                        if buffer_duration > 20.0 and result.segments:
                            safe_point = 0
                            committed_text_chunk = ""
                            
                            # Find segments that end at least 5.0 seconds before the current audio end
                            # This KEEPS the last 5s of audio no matter what, protecting active commands
                            cutoff_time = buffer_duration - 5.0
                            
                            keep_idx = 0
                            for i, seg in enumerate(result.segments):
                                if seg['end'] < cutoff_time:
                                    committed_text_chunk += seg['text'] + " "
                                    safe_point = seg['end']
                                    keep_idx = i + 1
                                else:
                                    break
                            
                            if safe_point > 0:
                                print(f"DEBUG: Sliding Window - Committing {safe_point:.2f}s audio. Keeping last {buffer_duration - safe_point:.2f}s.")
                                
                                # 1. Update Confirmed Text
                                self._confirmed_text = (self._confirmed_text + " " + committed_text_chunk).strip()
                                
                                # 2. Slice Audio Buffer
                                # Convert seconds to samples
                                samples_to_remove = int(safe_point * config.SAMPLE_RATE)
                                # Since _accumulated_audio is a list of chunks, this is tricky.
                                # Easier to replace it with a single chunk of the remainder
                                # (Whisper handles numpy arrays fine)
                                remaining_audio = window_audio[samples_to_remove:]
                                self._accumulated_audio = [remaining_audio]
                                
                                # 3. Update Pending Text to only show the REMAINDER
                                # (The committed part is now in _confirmed_text)
                                # We can't easily slice text, so we rely on the next loop to re-transcribe the remainder.
                                # But for display NOW, we try to approximate or just wait for next tick.
                                # Actually, result.text contained the whole thing.
                                # The NEXT loop will transcribe only `remaining_audio`.
                                # So `_pending_text` will update then.
                                # For now, we leave `_pending_text` as is? No, duplication!
                                # If we display confirmed + pending, and confirmed has chunk A, and pending has A+B...
                                # We must remove A from pending!
                                
                                # Re-construct pending from remaining segments
                                remaining_segments = result.segments[keep_idx:]
                                self._pending_text = "".join([s['text'] for s in remaining_segments]).strip()
                        
                        # Full text is confirmed + pending
                        full_display_text = (self._confirmed_text + " " + self._pending_text).strip()
                        print(f"Streaming: '{full_display_text}'")
                        self._final_text = full_display_text
                        
                        # Update overlay with live transcription
                        self.overlay.set_transcription(full_display_text[-100:] if len(full_display_text) > 100 else full_display_text)
                
                # Note: We implemented logical sliding window above.
                # The buffer is now safely trimmed when it gets too long.
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
