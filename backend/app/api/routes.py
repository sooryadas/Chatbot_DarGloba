"""REST endpoints for health checks and grounded chat responses."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse, HealthResponse
from app.services.answer import AnswerGenerationError, generate_grounded_answer
from app.services.retrieval import RetrievalError, retrieve_documents

LOGGER = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Report that the API process is responding."""
    return HealthResponse()


@router.post("/api/v1/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Retrieve source material and answer the user's latest question."""
    history = request.history[-12:]
    query_parts = [message.content for message in history[-4:] if message.role == "user"]
    query_parts.append(request.question)
    try:
        documents = retrieve_documents("\n".join(query_parts))
        return generate_grounded_answer(request.question, history, documents)
    except RetrievalError as exc:
        LOGGER.error("Chat retrieval failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The document search service is temporarily unavailable.",
        ) from exc
    except AnswerGenerationError as exc:
        LOGGER.error("Chat answer generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The answer service is temporarily unavailable.",
        ) from exc
