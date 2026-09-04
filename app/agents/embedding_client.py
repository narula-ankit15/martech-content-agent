from typing import Protocol


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class GeminiEmbeddingClient:
    def __init__(self, api_key: str, model: str):
        from google import genai  # lazy import, same reasoning as GeminiClient

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._client.models.embed_content(model=self._model, contents=texts)
        return [e.values for e in result.embeddings]
