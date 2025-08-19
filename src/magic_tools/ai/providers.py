"""AI providers for Magic Tools."""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncGenerator

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
    async def list_models(self) -> List[str]:
        """List available model identifiers for this provider.
        
        Returns:
            List of model IDs (strings). Empty if unavailable.
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
        # Don't keep a persistent session - create a new one for each request
        # This avoids issues with closed event loops
    
    async def _create_session(self, streaming: bool = False, timeout: Optional[float] = 60.0):
        """Create a new aiohttp session for the current request.

        Args:
            streaming: If True, configure timeouts suitable for streaming.
            timeout: Total timeout (seconds) for non-streaming requests.
        """
        try:
            import aiohttp
            if self.api_key:
                # Always create a fresh session for each request
                if streaming:
                    timeout_cfg = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=300)
                else:
                    timeout_cfg = aiohttp.ClientTimeout(total=timeout)
                session = aiohttp.ClientSession(
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    timeout=timeout_cfg
                )
                self.logger.info("OpenAI aiohttp session created")
                return session
            else:
                self.logger.warning("OpenAI API key not provided")
                return None
        except ImportError:
            self.logger.error("aiohttp library not installed. Run: pip install aiohttp")
            return None
        except Exception as e:
            self.logger.error(f"Failed to create aiohttp session: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if OpenAI provider is available."""
        return bool(self.api_key)
    
    async def list_models(self) -> List[str]:
        """Fetch available models from OpenAI /models endpoint.
        
        Returns:
            A list of model IDs, or empty list on failure.
        """
        if not bool(self.api_key):
            return []
        session = None
        try:
            session = await self._create_session(timeout=15.0)
            if not session:
                return []
            async with session.get(f"{self.base_url}/models") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("data", []) if isinstance(data, dict) else []
                    ids = []
                    for it in items:
                        try:
                            mid = it.get("id") if isinstance(it, dict) else None
                            if isinstance(mid, str) and mid:
                                ids.append(mid)
                        except Exception:
                            continue
                    # Optional: de-duplicate and sort for UX
                    ids = sorted(list(dict.fromkeys(ids)))
                    return ids
                else:
                    try:
                        text = await resp.text()
                    except Exception:
                        text = ""
                    self.logger.error(f"OpenAI list_models error HTTP {resp.status}: {text[:200]}")
                    return []
        except Exception as e:
            self.logger.error(f"OpenAI list_models exception: {e}")
            return []
        finally:
            if session:
                try:
                    await session.close()
                except Exception:
                    pass
    
    async def generate_response(self, messages: List[Dict[str, str]]) -> AIResponse:
        """Generate response using OpenAI API."""
        if not bool(self.api_key):  # Check API key without relying on is_available
            return AIResponse(
                content="OpenAI provider is not available. Please check your API key.",
                success=False,
                error="Provider not available"
            )
        
        try:
            # Create a fresh session for this request
            session = await self._create_session()
            
            if not session:
                return AIResponse(
                    content="Failed to create OpenAI session. Please try again.",
                    success=False,
                    error="Session creation failed"
                )
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }
            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Convert to typed model for easier downstream access
                        chat_completion = OpenAIChatCompletion.from_dict(data)
                        # Safely extract content and token usage
                        content = ""
                        if chat_completion.choices:
                            msg = chat_completion.choices[0].message
                            content = (msg.content or "")
                        tokens_used = getattr(chat_completion.usage, "total_tokens", 0) or 0
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
                        try:
                            import json
                            err_msg = None
                            data = json.loads(error_text)
                            if isinstance(data, dict):
                                err_msg = (data.get("error", {}) or {}).get("message") or data.get("message")
                        except Exception:
                            err_msg = None
                        msg = f"HTTP {response.status}: {err_msg or error_text}"
                        self.logger.error(f"OpenAI API error {msg}")
                        return AIResponse(
                            content=f"API Error {msg}",
                            success=False,
                            error=msg
                        )
            finally:
                try:
                    await session.close()
                except Exception:
                    pass
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            return AIResponse(
                content=f"Error: {str(e)}",
                success=False,
                error=str(e)
            )
    
    async def stream_response(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Stream response using OpenAI API."""
        if not bool(self.api_key):  # Check API key without relying on is_available
            yield "OpenAI provider is not available. Please check your API key."
            return
        
        try:
            # Create a fresh session for this request
            session = await self._create_session(streaming=True)
            
            if not session:
                yield "Failed to create OpenAI session. Please try again."
                return
                
            import json
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": True
            }
            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    if response.status == 200:
                        buffer = ""
                        done = False
                        async for raw_chunk in response.content:
                            if done:
                                break
                            try:
                                chunk = raw_chunk.decode('utf-8')
                            except UnicodeDecodeError:
                                chunk = raw_chunk.decode('utf-8', errors='ignore')
                            buffer += chunk
                            while '\n' in buffer:
                                line, _, buffer = buffer.partition('\n')
                                line = line.strip()
                                if not line:
                                    continue
                                if not line.startswith('data: '):
                                    continue
                                data_str = line[6:].strip()
                                if data_str == '[DONE]':
                                    done = True
                                    break
                                try:
                                    stream_data = json.loads(data_str)
                                    stream_chunk = OpenAIStreamChunk.from_dict(stream_data)
                                    if (stream_chunk.choices and
                                        stream_chunk.choices[0].delta.content is not None):
                                        yield stream_chunk.choices[0].delta.content
                                except json.JSONDecodeError:
                                    continue
                    else:
                        err_text = await response.text()
                        err_msg = None
                        try:
                            err_data = json.loads(err_text)
                            if isinstance(err_data, dict):
                                err_msg = (err_data.get("error", {}) or {}).get("message") or err_data.get("message")
                        except Exception:
                            pass
                        msg = f"HTTP {response.status}: {err_msg or err_text}"
                        self.logger.error(f"OpenAI streaming error {msg}")
                        yield f"Error: {msg}"
            finally:
                try:
                    await session.close()
                except Exception:
                    pass
                    
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
            # Sessions are created per request; nothing to clean up here.
    
    def cleanup(self):
        """Clean up resources."""
        # No need to clean up persistent sessions since we create new ones for each request
        self.logger.info("OpenAI provider cleanup completed")
 