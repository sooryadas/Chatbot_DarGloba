"""Use retrieved excerpts and recent chat history to answer a question."""

import logging

import requests

from app.core.config import settings
from app.schemas.chat import ChatMessage, ChatResponse, SourceReference

LOGGER = logging.getLogger(__name__)
UNAVAILABLE_ANSWER = (
    "I couldn't find that information in the available DarGlobal and Wasalt sources."
)


class AnswerGenerationError(RuntimeError):
    """Raised when OpenRouter cannot return an answer."""


def _format_context(documents: list[dict]) -> tuple[str, list[SourceReference]]:
    """Format retrieved chunks and build the deduplicated citation list."""
    context_sections: list[str] = []
    sources: list[SourceReference] = []
    seen_urls: set[str] = set()

    for index, document in enumerate(documents, start=1):
        url = document["source_url"]
        title = document.get("title") or url
        site = document.get("website_name") or "Website"
        context_sections.append(
            f"[Source {index}] {title}\nWebsite: {site}\nURL: {url}\n"
            f"Excerpt: {document['content']}"
        )
        if url not in seen_urls:
            seen_urls.add(url)
            sources.append(
                SourceReference(title=title, source_url=url, website_name=site)
            )
    return "\n\n".join(context_sections), sources


def generate_grounded_answer(
    question: str,
    history: list[ChatMessage],
    documents: list[dict],
) -> ChatResponse:
    """Ask OpenRouter to answer from retrieved excerpts and cite their numbers."""
    if not documents:
        return ChatResponse(answer=UNAVAILABLE_ANSWER, sources=[])
    if not settings.openrouter_api_key:
        raise AnswerGenerationError("OPENROUTER_API_KEY is not configured.")

    context, sources = _format_context(documents)
    history_limit = max(0, settings.chat_history_turn_limit * 2)
    recent_history = history[-history_limit:] if history_limit else []
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are a real estate information assistant for DarGlobal and Wasalt. "
                "Answer factual questions only from the source excerpts supplied in "
                "the latest user message. Use earlier conversation only to understand "
                "references in the current question; earlier assistant messages are not "
                "evidence. If the excerpts do not contain the answer, say you could not "
                "find it in the available sources. Do not guess or use outside knowledge. "
                "Cite supporting excerpts inline using [Source 1], [Source 2], etc."
            ),
        }
    ]
    messages.extend({"role": item.role, "content": item.content} for item in recent_history)
    messages.append(
        {
            "role": "user",
            "content": (
                f"Current question: {question}\n\n"
                f"Retrieved source excerpts:\n{context}"
            ),
        }
    )

    endpoint = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "X-Title": "Real Estate Intelligence Chatbot",
    }
    payload = {"model": settings.openrouter_model, "messages": messages, "temperature": 0.1}
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=settings.openrouter_timeout_seconds,
        )
        response.raise_for_status()
        answer_text = response.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        LOGGER.exception("OpenRouter request failed")
        raise AnswerGenerationError("The answer service could not complete the request.") from exc

    if not answer_text:
        raise AnswerGenerationError("The answer service returned an empty response.")
    return ChatResponse(answer=answer_text, sources=sources)
