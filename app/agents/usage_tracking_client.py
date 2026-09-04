from app.agents.embedding_client import EmbeddingClient
from app.agents.llm_client import LLMClient
from app.storage.usage_store import UsageStore


def _is_rate_limit_error(e: Exception) -> bool:
    # Best-effort, SDK-version-agnostic: match on the error text rather than
    # a specific google-genai exception class, since that hierarchy isn't
    # guaranteed stable across SDK versions.
    text = str(e).lower()
    return any(marker in text for marker in ("429", "resource_exhausted", "quota", "rate limit"))


class UsageTrackingLLMClient:
    """Wraps any LLMClient to record every call in UsageStore -- a thin
    decorator, not a new agent, so no content agent has to know usage is
    being tracked at all.
    """

    def __init__(self, inner: LLMClient, usage_store: UsageStore, purpose: str):
        self._inner = inner
        self._usage_store = usage_store
        self._purpose = purpose

    def generate_json(self, *, system: str, prompt: str) -> dict:
        try:
            result = self._inner.generate_json(system=system, prompt=prompt)
        except Exception as e:
            self._usage_store.record(self._purpose, status="rate_limited" if _is_rate_limit_error(e) else "error")
            raise
        self._usage_store.record(self._purpose, status="ok")
        return result


class UsageTrackingEmbeddingClient:
    def __init__(self, inner: EmbeddingClient, usage_store: UsageStore, purpose: str):
        self._inner = inner
        self._usage_store = usage_store
        self._purpose = purpose

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            result = self._inner.embed(texts)
        except Exception as e:
            self._usage_store.record(self._purpose, status="rate_limited" if _is_rate_limit_error(e) else "error")
            raise
        self._usage_store.record(self._purpose, status="ok")
        return result
