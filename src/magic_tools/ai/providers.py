"""AI providers for Magic Tools."""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncGenerator
import asyncio

from .models import (
    AIResponse,
    OpenAIChatCompletion,
    OpenAIStreamChunk,
)


class BaseAIProvider(ABC):
    """Base class for AI providers."""
    
    def __init__(self, max_tokens: int = 1000, temperature: float = 0.7):
        self.logger = logging.getLogger(__name__)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.tokens_used = 0
    
    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, str]]) -> AIResponse:
        """Generate a response from the AI model.
        
        Args:
            messages: List of messages in chat format
            
        Returns:
            AI response
        """
        pass
    
    @abstractmethod
    async def stream_response(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Stream response from the AI model.
        
        Args:
            messages: List of messages in chat format
            
        Yields:
            Response chunks
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available."""
        pass
    
    def update_settings(self, settings):
        """Update provider settings."""
        self.max_tokens = settings.max_tokens
        self.temperature = settings.temperature
    
    def cleanup(self):
        """Clean up provider resources."""
        pass


class OpenAIProvider(BaseAIProvider):
    """OpenAI API provider using aiohttp."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", 
                 model: str = "gpt-3.5-turbo", max_tokens: int = 1000, temperature: float = 0.7):
        super().__init__(max_tokens, temperature)
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.session = None
        
        # Initialize aiohttp session
        self._initialize_session()
    
    def _initialize_session(self):
        """Initialize aiohttp session."""
        try:
            import aiohttp
            if self.api_key:
                self.session = aiohttp.ClientSession(
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    }
                )
                self.logger.info("OpenAI aiohttp session initialized")
            else:
                self.logger.warning("OpenAI API key not provided")
        except ImportError:
            self.logger.error("aiohttp library not installed. Run: pip install aiohttp")
        except Exception as e:
            self.logger.error(f"Failed to initialize aiohttp session: {e}")
    
    def is_available(self) -> bool:
        """Check if OpenAI provider is available."""
        return self.session is not None and bool(self.api_key)
    
    async def generate_response(self, messages: List[Dict[str, str]]) -> AIResponse:
        """Generate response using OpenAI API."""
        if not self.is_available():
            return AIResponse(
                content="OpenAI provider is not available. Please check your API key.",
                success=False,
                error="Provider not available"
            )
        
        try:
            import aiohttp
            import json
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }
            
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Convert to typed model for easier downstream access
                    chat_completion = OpenAIChatCompletion.from_dict(data)
                    
                    content = chat_completion.choices[0].message.content
                    tokens_used = chat_completion.usage.total_tokens
                    self.tokens_used += tokens_used
                    
                    return AIResponse(
                        content=content,
                        tokens_used=tokens_used,
                        model_used=chat_completion.model,
                        success=True,
                        raw_response=chat_completion
                    )
                else:
                    error_text = await response.text()
                    self.logger.error(f"OpenAI API error {response.status}: {error_text}")
                    return AIResponse(
                        content=f"API Error {response.status}: {error_text}",
                        success=False,
                        error=f"HTTP {response.status}: {error_text}"
                    )
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            return AIResponse(
                content=f"Error: {str(e)}",
                success=False,
                error=str(e)
            )
    
    async def stream_response(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Stream response using OpenAI API."""
        if not self.is_available():
            yield "OpenAI provider is not available. Please check your API key."
            return
        
        try:
            import aiohttp
            import json
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": True
            }
            
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                if response.status == 200:
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data_str = line[6:]  # Remove 'data: ' prefix
                            if data_str == '[DONE]':
                                break
                            
                            try:
                                stream_data = json.loads(data_str)
                                stream_chunk = OpenAIStreamChunk.from_dict(stream_data)
                                if stream_chunk.choices and stream_chunk.choices[0].delta.content is not None:
                                    yield stream_chunk.choices[0].delta.content
                            except json.JSONDecodeError:
                                continue
                else:
                    error_text = await response.text()
                    self.logger.error(f"OpenAI streaming error {response.status}: {error_text}")
                    yield f"Error {response.status}: {error_text}"
                    
        except Exception as e:
            self.logger.error(f"OpenAI streaming error: {e}")
            yield f"Error: {str(e)}"
    
    def update_settings(self, settings):
        """Update OpenAI provider settings."""
        super().update_settings(settings)
        self.model = settings.model
        
        # Update API key or base URL if changed
        if (settings.api_key != self.api_key or 
            settings.base_url != self.base_url):
            self.api_key = settings.api_key
            self.base_url = settings.base_url.rstrip('/')
            
            # Close old session and create new one
            if self.session:
                asyncio.create_task(self.session.close())
            self._initialize_session()
    
    def cleanup(self):
        """Clean up aiohttp session."""
        if self.session:
            asyncio.create_task(self.session.close())
            self.session = None
        super().cleanup()


class LocalProvider(BaseAIProvider):
    """Local AI model provider (placeholder for local models)."""
    
    def __init__(self, model_path: str = "", max_tokens: int = 1000, temperature: float = 0.7):
        super().__init__(max_tokens, temperature)
        self.model_path = model_path
        self.model = None
        
        # Try to initialize local model
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize local model."""
        try:
            if self.model_path:
                # This is a placeholder for local model initialization
                # You would typically use libraries like transformers, llama-cpp-python, etc.
                self.logger.info(f"Would initialize local model from: {self.model_path}")
                # self.model = load_model(self.model_path)
            else:
                self.logger.warning("Local model path not provided")
        except Exception as e:
            self.logger.error(f"Failed to initialize local model: {e}")
    
    def is_available(self) -> bool:
        """Check if local provider is available."""
        # For now, always return False as this is a placeholder
        return False and bool(self.model_path)
    
    async def generate_response(self, messages: List[Dict[str, str]]) -> AIResponse:
        """Generate response using local model."""
        if not self.is_available():
            return AIResponse(
                content="Local AI provider is not yet implemented. Please use OpenAI provider.",
                success=False,
                error="Provider not implemented"
            )
        
        try:
            # This is a placeholder for local model inference
            # You would implement the actual model inference here
            content = "This is a placeholder response from local model."
            
            return AIResponse(
                content=content,
                tokens_used=len(content.split()),
                model_used="local",
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Local model error: {e}")
            return AIResponse(
                content=f"Error: {str(e)}",
                success=False,
                error=str(e)
            )
    
    async def stream_response(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Stream response using local model."""
        if not self.is_available():
            yield "Local AI provider is not yet implemented. Please use OpenAI provider."
            return
        
        try:
            # This is a placeholder for local model streaming
            response = "This is a placeholder streaming response from local model."
            for word in response.split():
                yield word + " "
                await asyncio.sleep(0.1)  # Simulate streaming delay
                
        except Exception as e:
            self.logger.error(f"Local model streaming error: {e}")
            yield f"Error: {str(e)}"
    
    def update_settings(self, settings):
        """Update local provider settings."""
        super().update_settings(settings)
        
        # Update model path if changed
        if settings.local_model_path != self.model_path:
            self.model_path = settings.local_model_path
            self._initialize_model()


class MockProvider(BaseAIProvider):
    """Mock AI provider for testing and development."""
    
    def __init__(self, max_tokens: int = 1000, temperature: float = 0.7):
        super().__init__(max_tokens, temperature)
    
    def is_available(self) -> bool:
        """Mock provider is always available."""
        return True
    
    async def generate_response(self, messages: List[Dict[str, str]]) -> AIResponse:
        """Generate mock response."""
        try:
            # Create a mock response based on the last message
            last_message = messages[-1]["content"] if messages else "Hello"
            
            mock_responses = [
                f"This is a mock response to: '{last_message}'",
                "I'm a mock AI assistant. In a real implementation, I would provide helpful responses.",
                "Mock AI is ready to help! (This is just a placeholder)",
                f"You asked: '{last_message}'. This is a simulated response."
            ]
            
            # Simple hash-based selection for consistent responses
            response_idx = hash(last_message) % len(mock_responses)
            content = mock_responses[response_idx]
            
            return AIResponse(
                content=content,
                tokens_used=len(content.split()),
                model_used="mock",
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Mock provider error: {e}")
            return AIResponse(
                content=f"Mock error: {str(e)}",
                success=False,
                error=str(e)
            )
    
    async def stream_response(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Stream mock response."""
        try:
            response = await self.generate_response(messages)
            
            # Stream the response word by word
            for word in response.content.split():
                yield word + " "
                await asyncio.sleep(0.05)  # Simulate streaming delay
                
        except Exception as e:
            self.logger.error(f"Mock streaming error: {e}")
            yield f"Mock streaming error: {str(e)}" 