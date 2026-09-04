import json
from typing import Protocol


class LLMClient(Protocol):
    """Agents depend on this, not on google-genai directly — swapping the
    LLM provider later (per the doc's "swap the LLM provider" assumption)
    means writing one new class, not touching any agent's prompt logic.
    """

    def generate_json(self, *, system: str, prompt: str) -> dict:
        ...


class GeminiClient:
    def __init__(self, api_key: str, model: str):
        # imported lazily so unit tests that use a fake client don't need
        # the google-genai package installed at all
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate_json(self, *, system: str, prompt: str) -> dict:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
            },
        )
        return json.loads(response.text)
