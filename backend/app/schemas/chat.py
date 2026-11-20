"""Chat request and response models exchanged through the REST API."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """One previous message in the client-managed conversation history."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


class ChatRequest(BaseModel):
    """Question plus recent chat messages, sent by the frontend each turn."""

    question: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)


class SourceReference(BaseModel):
    """A retrieved source that supports the answer."""

    title: str = ""
    source_url: str
    website_name: str


class ChatResponse(BaseModel):
    """Answer and citations returned to the frontend."""

    answer: str
    sources: list[SourceReference] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Simple liveness response."""

    status: Literal["ok"] = "ok"
