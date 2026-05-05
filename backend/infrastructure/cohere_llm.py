import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

from domain.privacy import redact_messages, redact_text


env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=env_path, override=True)

COHERE_API_BASE_URL = os.environ.get("COHERE_API_BASE_URL", "https://api.cohere.com")
DEFAULT_CHAT_MODEL = os.environ.get("COHERE_MODEL", "command-a-03-2025")
DEFAULT_EMBED_MODEL = os.environ.get("COHERE_EMBED_MODEL", "embed-v4.0")
COHERE_EMBED_OUTPUT_DIMENSION = int(os.environ.get("COHERE_EMBED_OUTPUT_DIMENSION", "1024"))
PGVECTOR_DIMENSION = int(os.environ.get("PGVECTOR_DIMENSION", "768"))


def _load_api_key() -> str:
    load_dotenv(dotenv_path=env_path, override=True)
    return os.environ.get("COHERE_API_KEY", "")


def _post_json(path: str, payload: dict) -> dict:
    api_key = _load_api_key()
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is not configured.")

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{COHERE_API_BASE_URL.rstrip('/')}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Cohere API request failed ({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cohere API request failed: {e}") from e


def _extract_chat_text(response: dict) -> str:
    message = response.get("message") or {}
    content = message.get("content") or []
    if isinstance(content, list):
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type", "text") == "text"
        ]
        text = "\n".join(part for part in text_parts if part).strip()
        if text:
            return text

    if isinstance(content, str):
        return content.strip()

    text = response.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    raise RuntimeError("Cohere chat response did not include text content.")


def _normalize_embedding(values: list[float]) -> list[float]:
    if len(values) == PGVECTOR_DIMENSION:
        return values
    if len(values) > PGVECTOR_DIMENSION:
        return values[:PGVECTOR_DIMENSION]
    return values + [0.0] * (PGVECTOR_DIMENSION - len(values))


class CohereDraftingClient:
    @staticmethod
    def generate_draft(prompt: str) -> str:
        """
        Calls Cohere strictly to generate draft text.
        Does not ask the LLM for entity tracking or routing decisions.
        """
        try:
            response = _post_json(
                "/v2/chat",
                {
                    "model": os.environ.get("COHERE_MODEL", DEFAULT_CHAT_MODEL),
                    "messages": [{"role": "user", "content": redact_text(prompt)}],
                },
            )
            return _extract_chat_text(response)
        except Exception as e:
            raise RuntimeError(f"Cohere draft generation failed: {e}") from e

    @staticmethod
    def summarize_thread(messages: list[dict]) -> str:
        """
        Calls Cohere to create a concise summary of the provided thread messages.
        """
        try:
            safe_messages = redact_messages(messages)
            formatted = "\n".join([f"{m['author']}: {m['text']}" for m in safe_messages])
            prompt = f"Please provide a concise, high-level summary of the following message thread:\n\n{formatted}"
            response = _post_json(
                "/v2/chat",
                {
                    "model": os.environ.get("COHERE_MODEL", DEFAULT_CHAT_MODEL),
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            return _extract_chat_text(response)
        except Exception:
            return "Summary unavailable because the AI provider could not be reached or quota was exceeded."

    @staticmethod
    def get_embedding(text: str, input_type: str = "search_query") -> list[float]:
        safe_text = redact_text(text)
        response = _post_json(
            "/v2/embed",
            {
                "model": os.environ.get("COHERE_EMBED_MODEL", DEFAULT_EMBED_MODEL),
                "input_type": input_type,
                "embedding_types": ["float"],
                "output_dimension": COHERE_EMBED_OUTPUT_DIMENSION,
                "inputs": [
                    {
                        "content": [
                            {"type": "text", "text": safe_text},
                        ]
                    }
                ],
            },
        )

        embeddings = response.get("embeddings") or {}
        values = None
        if isinstance(embeddings, dict):
            float_embeddings = embeddings.get("float")
            if isinstance(float_embeddings, list) and float_embeddings:
                values = float_embeddings[0]
        elif isinstance(embeddings, list) and embeddings:
            values = embeddings[0]

        if not isinstance(values, list):
            raise RuntimeError("Cohere embed response did not include float embeddings.")

        return _normalize_embedding(values)


# Backwards-compatible symbol for older imports and tests.
GeminiDraftingClient = CohereDraftingClient
