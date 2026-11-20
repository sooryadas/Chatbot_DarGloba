"""Small, deterministic replies for conversational messages before RAG."""

import re


GREETING_MESSAGES = {
    "hi", "hello", "hey", "hi there", "hello there", "hey there",
    "good morning", "good afternoon", "good evening", "greetings",
}
CAPABILITY_MESSAGES = {
    "help", "what can you do", "what do you do", "how can you help me",
    "what can i ask", "what can i ask you", "what is this chatbot for",
    "what does this model do", "what does the model do", "what is your purpose",
}
IDENTITY_MESSAGES = {
    "who are you", "what is your name", "what's your name", "your name",
}
MODEL_MESSAGES = {
    "what model are you", "which model are you", "what model do you use",
    "which model do you use", "which ai model are you using",
    "what model is this", "are you chatgpt",
}
NAME_QUESTIONS = {"what is my name", "what's my name", "do you remember my name"}
CAPABILITIES = (
    "I can answer questions about DarGlobal and Wasalt using the collected public "
    "pages, and show source links. Ask about projects, locations, amenities, or "
    "company information. I will say when a detail is unavailable; I don't have "
    "live prices or availability unless those details are in the collected data."
)


def _normalize(text: str) -> str:
    return " ".join(text.replace("’", "'").casefold().split()).strip(" .,!?👋")


def _introduced_name(text: str) -> str | None:
    """Only accept an explicit introduction, never guess from a project name."""
    match = re.fullmatch(
        r"(?:my name is|call me)\s+([^\W\d_]+(?:[-'][^\W\d_]+)*"
        r"(?:\s+[^\W\d_]+(?:[-'][^\W\d_]+)*){0,3})",
        text.strip().strip(".! "),
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    name = match.group(1)
    # Avoid consuming a factual request appended to an introduction.
    if set(name.casefold().split()) & {"and", "tell", "about", "what", "where", "please"}:
        return None
    return name


def get_conversation_reply(
    question: str, history: list[dict[str, str]], model_name: str
) -> str | None:
    """Return a conversational reply, or None to continue with retrieval.

    Match whole messages, not keywords, so greeting-prefixed property questions
    and standalone project names remain factual requests. Names are read only
    from user messages supplied by the current client session.
    """
    normalized = _normalize(question)
    if normalized in GREETING_MESSAGES:
        return "Hello! I can help with DarGlobal and Wasalt information. What would you like to know?"

    # Allow a greeting before another supported conversational message.
    message = re.sub(r"^(?:hi|hello|hey)[,!. ]+", "", question.strip(), flags=re.IGNORECASE)
    normalized = _normalize(message)
    if normalized in IDENTITY_MESSAGES:
        return "I'm the Real Estate Intelligence Assistant for DarGlobal and Wasalt. " + CAPABILITIES
    if normalized in CAPABILITY_MESSAGES:
        return CAPABILITIES
    if normalized in MODEL_MESSAGES:
        if model_name == "openrouter/free":
            return (
                "This chatbot is configured to use OpenRouter's openrouter/free router "
                "for grounded answers. The underlying model can vary, so I can't claim "
                "a fixed model identity from this setting."
            )
        if not model_name:
            return "The chatbot uses OpenRouter, but no answer model is configured."
        return f"The configured answer model is {model_name}, accessed through OpenRouter."
    if normalized in {"how are you", "how are you doing"}:
        return "I'm ready to help. What would you like to know about DarGlobal or Wasalt?"
    if normalized in {"thanks", "thank you", "thanks a lot", "thank you very much"}:
        return "You're welcome! Let me know if you have another property question."
    if normalized in {"bye", "goodbye", "see you", "see you later"}:
        return "Goodbye! Come back whenever you have another question."

    name = _introduced_name(message)
    if name:
        return f"Nice to meet you, {name}! What would you like to know about DarGlobal or Wasalt?"
    if normalized in NAME_QUESTIONS:
        for previous in reversed(history):
            if previous.get("role") != "user":
                continue
            introduction = re.sub(
                r"^(?:hi|hello|hey)[,!. ]+", "", previous.get("content", "").strip(),
                flags=re.IGNORECASE,
            )
            name = _introduced_name(introduction)
            if name:
                return f"You told me your name is {name}."
        return "I don't have your name in the recent chat history. You can say 'My name is …'."
    return None
