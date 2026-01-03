"""Speech-to-text transcription using OpenAI Whisper with AMD GPU support."""

import numpy as np
import threading
import queue
import torch
from typing import Optional, Callable
from dataclasses import dataclass

from . import config


@dataclass
class TranscriptionResult:
    """Result from transcription."""
    text: str
    is_partial: bool
    language: str = "en"
    confidence: float = 1.0


class Transcriber:
    """Handles speech-to-text using OpenAI Whisper with GPU acceleration."""
    
    def __init__(self, on_transcription: Optional[Callable[[TranscriptionResult], None]] = None):
        """
        Initialize the transcriber.
        
        Args:
            on_transcription: Callback for transcription results
        """
        self.on_transcription = on_transcription
        self.model = None
        self._model_lock = threading.Lock()
        self._is_loaded = False
        
        # Processing state
        self._processing_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        
        # Track last transcription to avoid duplicates
        self._last_text = ""
        
        # Detect device
        if torch.cuda.is_available():
            self.device = "cuda"
            self.device_name = torch.cuda.get_device_name(0)
        else:
            self.device = "cpu"
            self.device_name = "CPU"
        
    def load_model(self) -> None:
        """Load the Whisper model. Should be called before transcription."""
        if self._is_loaded:
            return
            
        with self._model_lock:
            if self._is_loaded:
                return
                
            print(f"Loading Whisper model: {config.WHISPER_MODEL}...")
            print(f"Device: {self.device} ({self.device_name})")
            
            import whisper
            
            self.model = whisper.load_model(
                config.WHISPER_MODEL,
                device=self.device
            )
            self._is_loaded = True
            print("Model loaded successfully!")
    
    def transcribe(self, audio: np.ndarray) -> TranscriptionResult:
        """
        Transcribe audio buffer synchronously.
        
        Args:
            audio: Audio data as numpy array (float32, 16kHz mono)
            
        Returns:
            TranscriptionResult with transcribed text
        """
        if not self._is_loaded:
            self.load_model()
        
        if self.model is None:
            return TranscriptionResult(text="", is_partial=False)
        
        # Ensure audio is in correct format
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # Normalize if needed
        max_val = np.max(np.abs(audio))
        if max_val > 1.0:
            audio = audio / max_val
        elif max_val < 0.02:
            # Too quiet, probably no speech (increased threshold)
            return TranscriptionResult(text="", is_partial=False)
        
        try:
            # Transcribe with whisper
            result = self.model.transcribe(
                audio,
                language=config.WHISPER_LANGUAGE,
                fp16=(self.device == "cuda"),
                condition_on_previous_text=False,
                no_speech_threshold=0.6,  # Higher = more aggressive filtering
                logprob_threshold=-0.8    # Higher = filter low confidence
            )
            
            text = result.get("text", "").strip()
            language = result.get("language", "en")
            
            # Filter out common Whisper hallucinations
            hallucination_phrases = [
                "ready?", "thank you", "thanks for watching", "subscribe",
                "like and subscribe", "see you", "bye", "goodbye",
                "music", "applause", "laughter", "..."
            ]
            text_lower = text.lower().strip('.,!?')
            if text_lower in hallucination_phrases or len(text_lower) < 3:
                return TranscriptionResult(text="", is_partial=False)
            
            return TranscriptionResult(
                text=text,
                is_partial=False,
                language=language,
                confidence=1.0
            )
            
        except Exception as e:
            print(f"Transcription error: {e}")
            return TranscriptionResult(text="", is_partial=False)
    
    def start_worker(self) -> None:
        """Start background transcription worker thread."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
            
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
    
    def stop_worker(self) -> None:
        """Stop the background worker thread."""
        self._stop_event.set()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None
    
    def queue_audio(self, audio: np.ndarray) -> None:
        """Queue audio for background transcription."""
        self._processing_queue.put(audio.copy())
    
    def _worker_loop(self) -> None:
        """Background worker that processes audio from queue."""
        # Ensure model is loaded
        self.load_model()
        
        while not self._stop_event.is_set():
            try:
                audio = self._processing_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            # Skip if too short
            if len(audio) < config.SAMPLE_RATE * 0.3:  # Minimum 300ms
                continue
            
            result = self.transcribe(audio)
            
            # Avoid duplicate callbacks
            if result.text and result.text != self._last_text:
                self._last_text = result.text
                if self.on_transcription:
                    self.on_transcription(result)
    
    def clear_queue(self) -> None:
        """Clear pending audio from the processing queue."""
        while not self._processing_queue.empty():
            try:
                self._processing_queue.get_nowait()
            except queue.Empty:
                break
        self._last_text = ""
