"""Dataclasses for AI messaging and responses.

Separated into its own module to avoid circular imports between ai_manager and providers.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AIMessage:
    """Represents a message in an AI conversation."""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: float = 0.0


@dataclass
class AIResponse:
    """Represents an AI response returned by a provider.

    Attributes
    ----------
    content: str
        The textual content extracted from the provider.
    tokens_used: int
        Total tokens consumed for the request. If the provider does not return
        this information, it will be 0.
    model_used: str
        Identifier of the underlying model that generated the response.
    success: bool
        Whether the call was successful.
    error: Optional[str]
        Error message (if any occurred).
    raw_response: Optional[object]
        The raw provider-specific response parsed into a dataclass defined in
        this module (e.g. `OpenAIChatCompletion`).  Having a strongly-typed
        object attached allows callers to access additional OpenAI-specific
        metadata without littering provider-agnostic code with indexing logic.
    """
    content: str
    tokens_used: int = 0
    model_used: str = ""
    success: bool = True
    error: Optional[str] = None
    raw_response: Optional[object] = None


# ---------------------------------------------------------------------------
# OpenAI specific response models
# ---------------------------------------------------------------------------
from typing import Any, List, Dict, Union


def _get(data: Dict, key: str, default=None):
    """Utility to safely get a key from a dict with default."""
    return data.get(key, default)


@dataclass
class OpenAIUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # Extra sub-objects (e.g., details) retained for forward compatibility
    extra: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OpenAIUsage":
        return OpenAIUsage(
            prompt_tokens=_get(data, "prompt_tokens", 0),
            completion_tokens=_get(data, "completion_tokens", 0),
            total_tokens=_get(data, "total_tokens", 0),
            extra={k: v for k, v in data.items() if k not in {"prompt_tokens", "completion_tokens", "total_tokens"}},
        )


@dataclass
class OpenAIMessage:
    role: str
    content: Optional[str]
    # Keep entire original dict to preserve unknown fields (tool_calls, etc.)
    extra: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OpenAIMessage":
        return OpenAIMessage(
            role=_get(data, "role", "assistant"),
            content=_get(data, "content"),
            extra={k: v for k, v in data.items() if k not in {"role", "content"}},
        )


@dataclass
class OpenAIChoice:
    index: int
    message: OpenAIMessage
    finish_reason: Optional[str] = None
    logprobs: Any = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OpenAIChoice":
        return OpenAIChoice(
            index=data.get("index", 0),
            message=OpenAIMessage.from_dict(data.get("message", {})),
            finish_reason=data.get("finish_reason"),
            logprobs=data.get("logprobs"),
        )


@dataclass
class OpenAIChatCompletion:
    id: str
    model: str
    choices: List[OpenAIChoice]
    usage: OpenAIUsage
    created: int = 0
    object: str = "chat.completion"
    service_tier: str = "default"
    # Any additional keys preserved
    extra: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OpenAIChatCompletion":
        return OpenAIChatCompletion(
            id=data.get("id", ""),
            model=data.get("model", ""),
            choices=[OpenAIChoice.from_dict(c) for c in data.get("choices", [])],
            usage=OpenAIUsage.from_dict(data.get("usage", {})),
            created=data.get("created", 0),
            object=data.get("object", ""),
            service_tier=data.get("service_tier", "default"),
            extra={k: v for k, v in data.items() if k not in {"id", "model", "choices", "usage", "created", "object", "service_tier"}},
        )


# Streaming chunk models -----------------------------------------------------
@dataclass
class OpenAIStreamDelta:
    content: Optional[str] = None
    # keep rest of keys for future compatibility
    extra: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OpenAIStreamDelta":
        return OpenAIStreamDelta(
            content=data.get("content"),
            extra={k: v for k, v in data.items() if k != "content"},
        )


@dataclass
class OpenAIStreamChoice:
    index: int
    delta: OpenAIStreamDelta
    finish_reason: Optional[str] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OpenAIStreamChoice":
        return OpenAIStreamChoice(
            index=data.get("index", 0),
            delta=OpenAIStreamDelta.from_dict(data.get("delta", {})),
            finish_reason=data.get("finish_reason"),
        )


@dataclass
class OpenAIStreamChunk:
    id: str
    model: str
    choices: List[OpenAIStreamChoice]
    created: int = 0
    object: str = "chat.completion.chunk"
    # preserve extra
    extra: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OpenAIStreamChunk":
        return OpenAIStreamChunk(
            id=data.get("id", ""),
            model=data.get("model", ""),
            choices=[OpenAIStreamChoice.from_dict(c) for c in data.get("choices", [])],
            created=data.get("created", 0),
            object=data.get("object", ""),
            extra={k: v for k, v in data.items() if k not in {"id", "model", "choices", "created", "object"}},
        )
