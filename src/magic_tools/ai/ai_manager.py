"""AI Manager for Magic Tools."""

import logging
from typing import Dict, List, Optional, AsyncGenerator

from ..config.settings import AISettings
from .models import AIMessage, AIResponse
from .providers import OpenAIProvider, LocalProvider



class AIManager:
    """Manages AI integration and providers."""

    def __init__(self, settings: AISettings):
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.providers: Dict[str, object] = {}
        self.current_provider: Optional[object] = None
        self.conversation_history: List[AIMessage] = []

        # Initialize providers
        self._initialize_providers()

        # Set current provider
        self._set_current_provider()

    def _initialize_providers(self):
        """Initialize available AI providers."""
        try:
            # OpenAI Provider
            self.providers['openai'] = OpenAIProvider(
                api_key=self.settings.api_key,
                base_url=self.settings.base_url,
                model=self.settings.model,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature
            )

            # Local Provider (for local models)
            self.providers['local'] = LocalProvider(
                model_path=self.settings.local_model_path,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature
            )

            self.logger.info(f"Initialized {len(self.providers)} AI providers")

        except Exception as e:
            self.logger.error(f"Failed to initialize AI providers: {e}")

    def _set_current_provider(self):
        """Set the current AI provider based on settings."""
        if self.settings.provider in self.providers:
            self.current_provider = self.providers[self.settings.provider]
            self.logger.info(f"Set current AI provider to: {self.settings.provider}")
        else:
            self.logger.warning(f"Provider '{self.settings.provider}' not available")
            # Fallback to first available provider
            if self.providers:
                provider_name = list(self.providers.keys())[0]
                self.current_provider = self.providers[provider_name]
                self.logger.info(f"Fallback to provider: {provider_name}")

    def is_available(self) -> bool:
        """Check if AI functionality is available."""
        print('settings enabled', self.settings.enabled)
        print('current provider', self.current_provider)
        print('current provider available', self.current_provider.is_available())
        return (self.settings.enabled and
                self.current_provider is not None and
                self.current_provider.is_available())

    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return [name for name, provider in self.providers.items()
                if provider.is_available()]

    def switch_provider(self, provider_name: str) -> bool:
        """Switch to a different AI provider.
        
        Args:
            provider_name: Name of the provider to switch to
            
        Returns:
            True if switched successfully
        """
        if provider_name not in self.providers:
            self.logger.error(f"Provider '{provider_name}' not available")
            return False

        if not self.providers[provider_name].is_available():
            self.logger.error(f"Provider '{provider_name}' is not available")
            return False

        self.current_provider = self.providers[provider_name]
        self.settings.provider = provider_name
        self.logger.info(f"Switched to AI provider: {provider_name}")
        return True

    async def send_message(self, message: str, context: Optional[str] = None) -> AIResponse:
        """Send a message to the AI and get response.
        
        Args:
            message: User message
            context: Optional context information
            
        Returns:
            AI response
        """
        if not self.is_available():
            return AIResponse(
                content="AI is not available. Please check your configuration.",
                success=False,
                error="AI not available"
            )

        try:
            # Add user message to history
            user_message = AIMessage(role="user", content=message)
            self.conversation_history.append(user_message)

            # Prepare messages for the provider
            messages = self._prepare_messages(context)

            # Get response from current provider
            response = await self.current_provider.generate_response(messages)

            # Add assistant response to history
            if response.success:
                assistant_message = AIMessage(role="assistant", content=response.content)
                self.conversation_history.append(assistant_message)

            return response

        except Exception as e:
            self.logger.error(f"Error sending message to AI: {e}")
            return AIResponse(
                content=f"Error: {str(e)}",
                success=False,
                error=str(e)
            )

    async def stream_response(self, message: str, context: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Stream AI response as it's generated.
        
        Args:
            message: User message
            context: Optional context information
            
        Yields:
            Chunks of AI response
        """
        if not self.is_available():
            yield "AI is not available. Please check your configuration."
            return

        try:
            # Add user message to history
            user_message = AIMessage(role="user", content=message)
            self.conversation_history.append(user_message)

            # Prepare messages for the provider
            messages = self._prepare_messages(context)

            # Stream response from current provider
            full_response = ""
            async for chunk in self.current_provider.stream_response(messages):
                full_response += chunk
                yield chunk

            # Add complete response to history
            assistant_message = AIMessage(role="assistant", content=full_response)
            self.conversation_history.append(assistant_message)

        except Exception as e:
            self.logger.error(f"Error streaming AI response: {e}")
            yield f"Error: {str(e)}"

    def _prepare_messages(self, context: Optional[str] = None) -> List[Dict[str, str]]:
        """Prepare messages for the AI provider.
        
        Args:
            context: Optional context information
            
        Returns:
            List of messages formatted for the provider
        """
        messages = []

        # Add system message with context if provided
        if context:
            messages.append({
                "role": "system",
                "content": f"Context: {context}"
            })

        # Add conversation history (last 10 messages to avoid token limits)
        for message in self.conversation_history[-10:]:
            messages.append({
                "role": message.role,
                "content": message.content
            })

        return messages

    def clear_conversation(self):
        """Clear the conversation history."""
        self.conversation_history.clear()
        self.logger.info("Cleared conversation history")

    def get_conversation_history(self) -> List[AIMessage]:
        """Get the conversation history."""
        return self.conversation_history.copy()

    def update_settings(self, settings: AISettings):
        """Update AI settings and reconfigure providers.
        
        Args:
            settings: New AI settings
        """
        self.settings = settings

        # Reconfigure providers
        try:
            for provider_name, provider in self.providers.items():
                if hasattr(provider, 'update_settings'):
                    provider.update_settings(settings)

            # Update current provider
            self._set_current_provider()

            self.logger.info("Updated AI settings")

        except Exception as e:
            self.logger.error(f"Failed to update AI settings: {e}")

    def get_model_info(self) -> Dict[str, str]:
        """Get information about the current model."""
        if not self.current_provider:
            return {"status": "No provider available"}

        return {
            "provider": self.settings.provider,
            "model": self.settings.model,
            "status": "Available" if self.is_available() else "Unavailable",
            "tokens_used": str(getattr(self.current_provider, 'tokens_used', 0))
        }

    def cleanup(self):
        """Clean up AI resources."""
        self.logger.info("Cleaning up AI manager")

        # Clean up providers
        for provider in self.providers.values():
            if hasattr(provider, 'cleanup'):
                provider.cleanup()

        # Clear conversation history
        self.clear_conversation()

        self.logger.info("AI manager cleanup completed")