"""Streamlit chat interface for the Real Estate Intelligence API."""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

DEFAULT_BACKEND_URL = "http://localhost:8000"
API_TIMEOUT_SECONDS = 60
HISTORY_MESSAGES_TO_SEND = 12

st.set_page_config(
    page_title="Real Estate Intelligence",
    page_icon="🏙️",
    layout="centered",
)


def _backend_url() -> str:
    """Return the configured backend URL without a trailing slash."""
    return os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")


def _request_answer(question: str, history: list[dict[str, str]]) -> dict[str, Any]:
    """Send a question and previous conversation messages to FastAPI."""
    response = requests.post(
        f"{_backend_url()}/api/v1/chat",
        json={"question": question, "history": history[-HISTORY_MESSAGES_TO_SEND:]},
        timeout=API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
        raise ValueError("The backend returned an invalid chat response.")
    return result


def _render_sources(sources: list[dict[str, Any]]) -> None:
    """Show source links returned by the backend below an answer."""
    if not sources:
        return
    with st.expander("Sources", expanded=False):
        for source in sources:
            url = source.get("source_url", "")
            title = source.get("title") or url
            website = source.get("website_name") or "Source"
            if url:
                st.markdown(f"- **{website}:** [{title}]({url})")


def _render_conversation() -> None:
    """Render the messages retained in this browser session."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _render_sources(message.get("sources", []))


def main() -> None:
    """Render the chat interface and handle a submitted question."""
    st.title("Real Estate Intelligence")
    st.caption("Ask questions about publicly available DarGlobal and Wasalt information.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.subheader("Conversation")
        st.caption("Chat history stays in this browser session.")
        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        st.divider()
        st.caption("Answers use information retrieved from the connected public sources.")

    _render_conversation()

    question = st.chat_input("Ask about a project, property, or service…")
    if not question:
        return

    # Keep a copy of prior turns to send before this question is added to history.
    prior_messages = [
        {"role": item["role"], "content": item["content"]}
        for item in st.session_state.messages
    ]
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching the available sources…"):
            try:
                result = _request_answer(question, prior_messages)
                answer = result["answer"]
                sources = result.get("sources", [])
                if not isinstance(sources, list):
                    sources = []
            except requests.Timeout:
                answer = "The backend took too long to respond. Please try again."
                sources = []
            except requests.RequestException:
                answer = "I couldn't connect to the backend. Please try again in a moment."
                sources = []
            except (ValueError, KeyError):
                answer = "The backend returned an unexpected response. Please try again."
                sources = []

        st.markdown(answer)
        _render_sources(sources)
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )


if __name__ == "__main__":
    main()
