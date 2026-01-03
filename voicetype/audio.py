"""Audio capture module using sounddevice for real-time streaming."""

import numpy as np
import sounddevice as sd
import threading
import queue
from typing import Callable, Optional

from . import config


class AudioCapture:
    """Captures audio from microphone with streaming support."""
    
    def __init__(self, on_audio_chunk: Optional[Callable[[np.ndarray], None]] = None):
        """
        Initialize audio capture.
        
        Args:
            on_audio_chunk: Callback function called with each audio chunk
        """
        self.sample_rate = config.SAMPLE_RATE
        self.chunk_samples = int(config.CHUNK_DURATION * self.sample_rate)
        self.buffer_samples = int(config.BUFFER_DURATION * self.sample_rate)
        
        self.on_audio_chunk = on_audio_chunk
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self.is_recording = False
        self.stream: Optional[sd.InputStream] = None
        
        # Rolling buffer for context
        self._buffer = np.zeros(self.buffer_samples, dtype=np.float32)
        self._buffer_lock = threading.Lock()
        
    def _audio_callback(self, indata: np.ndarray, frames: int, 
                        time_info: dict, status: sd.CallbackFlags) -> None:
        """Called by sounddevice for each audio chunk."""
        if status:
            print(f"Audio status: {status}")
        
        if self.is_recording:
            # Flatten to mono and add to queue
            audio_data = indata[:, 0].copy() if indata.ndim > 1 else indata.flatten().copy()
            self.audio_queue.put(audio_data)
            
            # Update rolling buffer
            with self._buffer_lock:
                self._buffer = np.roll(self._buffer, -len(audio_data))
                self._buffer[-len(audio_data):] = audio_data
            
            # Call callback if set
            if self.on_audio_chunk:
                self.on_audio_chunk(audio_data)
    
    def start(self) -> None:
        """Start audio capture."""
        if self.stream is not None:
            return
            
        self.is_recording = True
        self.stream = sd.InputStream(
            callback=self._audio_callback,
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            blocksize=self.chunk_samples
        )
        self.stream.start()
        
    def stop(self) -> None:
        """Stop audio capture."""
        self.is_recording = False
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        # Clear the queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
    
    def get_buffer(self) -> np.ndarray:
        """Get the current rolling buffer contents."""
        with self._buffer_lock:
            return self._buffer.copy()
    
    def get_chunk(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """Get the next audio chunk from the queue."""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def clear_buffer(self) -> None:
        """Clear the rolling buffer."""
        with self._buffer_lock:
            self._buffer = np.zeros(self.buffer_samples, dtype=np.float32)
        
        # Clear queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
    
    @staticmethod
    def calculate_rms(audio: np.ndarray) -> float:
        """Calculate RMS (root mean square) of audio for silence detection."""
        return float(np.sqrt(np.mean(audio ** 2)))
    
    def is_silence(self, audio: np.ndarray) -> bool:
        """Check if audio chunk is silence based on threshold."""
        return self.calculate_rms(audio) < config.SILENCE_THRESHOLD
