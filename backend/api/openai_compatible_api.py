"""
OpenAI-Compatible API for OpenWebUI Integration
================================================
Provides OpenAI-compatible endpoints for chat completions using KRAI's search capabilities.
"""

import json
import logging

# Import KRAI services
import sys
import time
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).parent.parent))

from backend.services.ai_service import AIService
from backend.services.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models (OpenAI Compatible)
# ============================================================================


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="krai-assistant", description="Model name")
    messages: list[Message]
    temperature: float | None = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=2000, ge=1)
    stream: bool | None = Field(default=False)
    top_p: float | None = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=0.0, ge=-2.0, le=2.0)


class ChatCompletionChoice(BaseModel):
    index: int
    message: Message
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: dict[str, int]


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "krai"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]


# ============================================================================
# OpenAI Compatible API
# ============================================================================


class OpenAICompatibleAPI:
    """OpenAI-compatible API for OpenWebUI integration"""

    def __init__(self, database_service: DatabaseAdapter, ai_service: AIService):
        self.database_service = database_service
        self.ai_service = ai_service
        self.logger = logging.getLogger("krai.api.openai")

        # Create router
        self.router = APIRouter(prefix="/v1", tags=["openai-compatible"])
        self._setup_routes()

    def _setup_routes(self):
        """Setup OpenAI-compatible routes"""

        @self.router.get("/models")
        async def list_models():
            """List available models (OpenAI compatible)"""
            return ModelsResponse(
                object="list", data=[ModelInfo(id="krai-assistant", created=int(time.time()), owned_by="krai")]
            )

        @self.router.post("/chat/completions")
        async def create_chat_completion(request: ChatCompletionRequest):
            """Create chat completion (OpenAI compatible)"""
            try:
                if request.stream:
                    return StreamingResponse(self._stream_chat_completion(request), media_type="text/event-stream")
                return await self._create_chat_completion(request)

            except Exception as e:
                self.logger.error(f"Chat completion failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def _create_chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Create non-streaming chat completion"""

        # Get the last user message
        user_message = None
        for msg in reversed(request.messages):
            if msg.role == "user":
                user_message = msg.content
                break

        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")

        # Process the query
        response_text = await self._process_query(user_message)

        # Create response
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"

        return ChatCompletionResponse(
            id=completion_id,
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0, message=Message(role="assistant", content=response_text), finish_reason="stop"
                )
            ],
            usage={
                "prompt_tokens": len(user_message.split()),
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(user_message.split()) + len(response_text.split()),
            },
        )

    async def _stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        """Stream chat completion with progressive search (SSE format)"""

        # Get the last user message
        user_message = None
        for msg in reversed(request.messages):
            if msg.role == "user":
                user_message = msg.content
                break

        if not user_message:
            yield f"data: {json.dumps({'error': 'No user message found'})}\n\n"
            return

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"

        # Helper to send a chunk
        def make_chunk(content: str):
            return {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model,
                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
            }

        # Progressive search with real-time streaming
        try:
            async for chunk_text in self._process_query_progressive(user_message):
                yield f"data: {json.dumps(make_chunk(chunk_text))}\n\n"
        except Exception as e:
            self.logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps(make_chunk(f'âŒ Fehler: {e!s}'))}\n\n"

        # Send final chunk
        final_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    async def _process_query_progressive(self, query: str) -> AsyncGenerator[str, None]:
        """Process query progressively, yielding results as they're found"""
        from backend.api.progressive_search import process_query_progressive

        async for chunk in process_query_progressive(query, self.database_service, self.ai_service):
            yield chunk

    async def _process_query(self, query: str) -> str:
        """Process query and return complete response (non-streaming)"""
        # Collect all chunks from progressive search
        result = []
        async for chunk in self._process_query_progressive(query):
            result.append(chunk)
        return "".join(result)

    def _extract_solution_from_chunks(self, error_code: str, chunks: list[dict]) -> str:
        """Extract complete solution text from chunks containing the error code"""
        import re

        # Sort chunks by relevance - PRIORITIZE technician actions
        sorted_chunks = sorted(
            chunks,
            key=lambda c: (
                "call-center agents" in c.get("text_chunk", "").lower()
                or "onsite technicians" in c.get("text_chunk", "").lower(),
                "Procedure" in c.get("text_chunk", ""),
                "Recommended action" in c.get("text_chunk", ""),
                error_code in c.get("text_chunk", ""),
            ),
            reverse=True,
        )

        # Look for chunks with solution sections
        for chunk in sorted_chunks[:5]:
            text = chunk.get("text_chunk", "")

            # Skip table of contents
            if "Contents" in text and text.count(".") > 20:
                continue

            # Try to find "Procedure" section
            if "Procedure" in text:
                match = re.search(r"Procedure\s*\n((?:\d+\.\s+.+?\n(?:\s+.+?\n)*)+)", text, re.MULTILINE)
                if match:
                    procedure_text = match.group(1).strip()
                    procedure_text = re.split(r"\n\s*\d+\.\d+\s+[A-Z]|Contents\s*\n", procedure_text)[0]
                    return procedure_text.strip()

            # Try "Recommended action for call-center agents" (HP format) - PRIORITIZE THIS
            if "call-center agents" in text.lower() or "onsite technicians" in text.lower():
                # More flexible regex to catch variations
                match = re.search(
                    r"Recommended action for (?:call-center agents|onsite technicians).*?\n(.+)",
                    text,
                    re.DOTALL | re.IGNORECASE,
                )
                if match:
                    solution = match.group(1).strip()
                    # Extract numbered steps (more flexible pattern)
                    steps = re.findall(r"^\s*\d+\.\s+.+?(?=\n\s*\d+\.|\n\n|$)", solution, re.MULTILINE | re.DOTALL)
                    if steps:
                        # Clean up steps
                        cleaned_steps = []
                        for step in steps:
                            step = step.strip()
                            # Remove line breaks within step
                            step = re.sub(r"\s+", " ", step)
                            cleaned_steps.append(step)
                        return "\n".join(cleaned_steps)
                    # Fallback: return first 500 chars
                    return solution[:500]

            # Fallback: Look for "Recommended action for customers"
            if "Recommended action for customers" in text:
                match = re.search(
                    r"Recommended action for customers[^\n]*\n(.+?)(?=Recommended action for|$)", text, re.DOTALL
                )
                if match:
                    solution = match.group(1).strip()
                    steps = re.findall(r"\d+\.\s+[^\n]+", solution)
                    if steps:
                        return "\n".join(steps)

        return ""

    def _format_solution_text(self, text: str) -> str:
        """Format solution text for better readability"""
        import re

        if not text or len(text) < 10:
            return text

        # Split by lines
        lines = text.split("\n")
        formatted_lines = []
        current_step = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line starts with number (main step)
            step_match = re.match(r"^(\d+)\.\s+(.+)$", line)
            if step_match:
                step_num = step_match.group(1)
                step_text = step_match.group(2)
                # Simple numbered format
                formatted_lines.append(f"{step_num}. {step_text}")
                current_step = step_num
            # Sub-items (bullet points)
            elif line.startswith("â€¢"):
                formatted_lines.append(f"  - {line[1:].strip()}")  # Remove bullet, add indent
            # Continuation of previous step
            elif current_step and not re.match(r"^\d+\.", line):
                # Only add if it's meaningful content (not just connectors/IDs)
                if len(line) > 5 and not line.startswith("Location"):
                    formatted_lines.append(f"  {line}")

        # Join with single newlines for markdown list
        result = "\n".join(formatted_lines)

        # Clean up excessive whitespace
        result = re.sub(r"\n{3,}", "\n\n", result)

        return result.strip()


# ============================================================================
# Factory function
# ============================================================================


def create_openai_api(database_service: DatabaseAdapter, ai_service: AIService) -> OpenAICompatibleAPI:
    """Create OpenAI-compatible API instance"""
    return OpenAICompatibleAPI(database_service, ai_service)
