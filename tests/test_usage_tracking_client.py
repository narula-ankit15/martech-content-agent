import pytest

from app.agents.usage_tracking_client import UsageTrackingEmbeddingClient, UsageTrackingLLMClient
from app.storage.usage_store import UsageStore


class FakeLLMClient:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def generate_json(self, *, system: str, prompt: str) -> dict:
        if self._error:
            raise self._error
        return self._result


class FakeEmbeddingClient:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def embed(self, texts):
        if self._error:
            raise self._error
        return self._result


def test_llm_client_records_ok_and_passes_result_through(tmp_path):
    store = UsageStore(str(tmp_path / "usage.db"))
    inner = FakeLLMClient(result={"hi": "there"})
    client = UsageTrackingLLMClient(inner, store, purpose="content_generation")

    result = client.generate_json(system="sys", prompt="prompt")

    assert result == {"hi": "there"}
    summary = store.summary()
    assert summary.requests_today == 1
    assert summary.requests_by_purpose == {"content_generation": 1}
    assert summary.rate_limited_today is False


def test_llm_client_records_rate_limited_and_reraises(tmp_path):
    store = UsageStore(str(tmp_path / "usage.db"))
    inner = FakeLLMClient(error=RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"))
    client = UsageTrackingLLMClient(inner, store, purpose="content_generation")

    with pytest.raises(RuntimeError):
        client.generate_json(system="sys", prompt="prompt")

    summary = store.summary()
    assert summary.requests_today == 1
    assert summary.rate_limited_today is True


def test_llm_client_records_generic_error_as_error_not_rate_limited(tmp_path):
    store = UsageStore(str(tmp_path / "usage.db"))
    inner = FakeLLMClient(error=ValueError("invalid json"))
    client = UsageTrackingLLMClient(inner, store, purpose="content_generation")

    with pytest.raises(ValueError):
        client.generate_json(system="sys", prompt="prompt")

    summary = store.summary()
    assert summary.requests_today == 1
    assert summary.rate_limited_today is False


def test_embedding_client_records_ok(tmp_path):
    store = UsageStore(str(tmp_path / "usage.db"))
    inner = FakeEmbeddingClient(result=[[0.1, 0.2]])
    client = UsageTrackingEmbeddingClient(inner, store, purpose="embedding")

    result = client.embed(["hello"])

    assert result == [[0.1, 0.2]]
    summary = store.summary()
    assert summary.requests_by_purpose == {"embedding": 1}
