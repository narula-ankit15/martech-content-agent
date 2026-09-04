from app.agents.image_text_agent import ImageOverlayTextAgent


class FakeLLMClient:
    def __init__(self, response: dict):
        self._response = response
        self.last_system = None
        self.last_prompt = None

    def generate_json(self, *, system: str, prompt: str) -> dict:
        self.last_system = system
        self.last_prompt = prompt
        return self._response


def test_suggest_returns_llm_suggestions(sample_campaign_brief):
    fake_llm = FakeLLMClient({"suggestions": ["Book Your 3BHK Today", "Limited Units Left", "Visit This Weekend", "Prices From 87L"]})
    agent = ImageOverlayTextAgent(fake_llm)

    suggestions = agent.suggest(sample_campaign_brief)

    assert suggestions == ["Book Your 3BHK Today", "Limited Units Left", "Visit This Weekend", "Prices From 87L"]
    assert "drive site visits for the 3BHK launch" in fake_llm.last_prompt
    assert "overlay text" in fake_llm.last_prompt.lower()
