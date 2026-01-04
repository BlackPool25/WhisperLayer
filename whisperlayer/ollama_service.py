"""Ollama integration service for WhisperLayer."""

from typing import Optional, List
import threading


# Default system prompt for STT-compatible output
DEFAULT_OLLAMA_PROMPT = """You are a helpful assistant for a speech-to-text application.
Respond with plain text only. No markdown, no code blocks, no bullet points, no numbered lists.
Keep responses concise and suitable for direct typing into any text field.
Do not use special formatting characters like asterisks, backticks, or hashes."""


class OllamaService:
    """Singleton service for Ollama model management and queries."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self._client = None
        self._current_model: Optional[str] = None
        self._available = None  # Cached availability status
        
        # Get settings
        from .settings import get_settings
        self._settings = get_settings()
    
    def _get_client(self):
        """Lazily initialize the Ollama client."""
        if self._client is None:
            try:
                import ollama
                self._client = ollama.Client()
            except ImportError:
                print("Warning: ollama package not installed. Run: pip install ollama")
                return None
            except Exception as e:
                print(f"Error initializing Ollama client: {e}")
                return None
        return self._client
    
    def is_available(self) -> bool:
        """Check if Ollama server is running and accessible."""
        client = self._get_client()
        if client is None:
            return False
        
        try:
            # Quick ping by listing models
            client.list()
            self._available = True
            return True
        except Exception as e:
            print(f"Ollama not available: {e}")
            self._available = False
            return False
    
    def list_models(self) -> List[str]:
        """Get list of available models from Ollama."""
        client = self._get_client()
        if client is None:
            return []
        
        try:
            response = client.list()
            models = []
            for model in response.get('models', []):
                name = model.get('name', '')
                if name:
                    models.append(name)
            return sorted(models)
        except Exception as e:
            print(f"Error listing Ollama models: {e}")
            return []
    
    def load_model(self, model_name: str) -> bool:
        """Pre-load a model for faster responses."""
        client = self._get_client()
        if client is None:
            return False
        
        try:
            print(f"Loading Ollama model: {model_name}")
            # Generate with empty prompt to trigger model load
            client.generate(model=model_name, prompt="", keep_alive="5m")
            self._current_model = model_name
            print(f"Ollama model loaded: {model_name}")
            return True
        except Exception as e:
            print(f"Error loading Ollama model '{model_name}': {e}")
            return False
    
    def unload_model(self) -> bool:
        """Unload the current model to free memory."""
        if not self._current_model:
            return True
        
        client = self._get_client()
        if client is None:
            return False
        
        try:
            print(f"Unloading Ollama model: {self._current_model}")
            # Set keep_alive to 0 to unload immediately
            client.generate(model=self._current_model, prompt="", keep_alive="0")
            self._current_model = None
            return True
        except Exception as e:
            print(f"Error unloading Ollama model: {e}")
            return False
    
    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Generate a response from Ollama.
        
        Args:
            prompt: The user's query
            model: Model to use (defaults to settings value)
            
        Returns:
            The model's response as plain text
        """
        client = self._get_client()
        if client is None:
            return ""
        
        if not prompt or not prompt.strip():
            return ""
        
        # Get model from settings if not specified
        if model is None:
            model = self._settings.get("ollama_model", "llama3.2:3b")
        
        # Get system prompt
        if self._settings.get("ollama_custom_prompt_enabled", False):
            system_prompt = self._settings.get("ollama_system_prompt", DEFAULT_OLLAMA_PROMPT)
        else:
            system_prompt = DEFAULT_OLLAMA_PROMPT
        
        try:
            print(f"Ollama query: '{prompt}' (model: {model})")
            
            response = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                options={"temperature": 0.7}
            )
            
            result = response.get('message', {}).get('content', '').strip()
            print(f"Ollama response: '{result[:100]}...'")
            return result
            
        except Exception as e:
            print(f"Ollama generation error: {e}")
            return f"[Error: {str(e)[:50]}]"
    
    def pull_model(self, model_name: str) -> tuple[bool, str]:
        """
        Pull (download) a model from Ollama registry.
        
        Returns:
            Tuple of (success, message)
        """
        client = self._get_client()
        if client is None:
            return False, "Ollama client not available"
        
        try:
            print(f"Pulling Ollama model: {model_name}")
            # This can take a while for large models
            client.pull(model_name)
            return True, f"Model '{model_name}' pulled successfully"
        except Exception as e:
            error_msg = str(e)
            print(f"Error pulling model '{model_name}': {error_msg}")
            return False, error_msg


# Global service instance
_service: Optional[OllamaService] = None


def get_ollama_service() -> OllamaService:
    """Get the global Ollama service instance."""
    global _service
    if _service is None:
        _service = OllamaService()
    return _service
