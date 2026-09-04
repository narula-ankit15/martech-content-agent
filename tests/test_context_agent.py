from app.agents.context_agent import ContextAgent
from app.models import ProjectFacts, RetrievedChunk


class FakeFactsStore:
    def __init__(self, facts: ProjectFacts):
        self._facts = facts

    def get(self, project_id: str) -> ProjectFacts:
        return self._facts


class FakeEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeVectorStore:
    def __init__(self, chunks: list[RetrievedChunk]):
        self._chunks = chunks
        self.last_query_kwargs = None

    def query(self, *, project_id: str, embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        self.last_query_kwargs = {"project_id": project_id, "embedding": embedding, "top_k": top_k}
        return self._chunks[:top_k]


def test_context_agent_combines_facts_and_retrieved_chunks():
    facts = ProjectFacts(project_name="Skyline Heights", rera_number="P51700012345")
    chunks = [
        RetrievedChunk(text="chunk one", source="brochure.pdf", score=0.9),
        RetrievedChunk(text="chunk two", source="brochure.pdf", score=0.7),
    ]
    facts_store = FakeFactsStore(facts)
    vector_store = FakeVectorStore(chunks)
    embedding_client = FakeEmbeddingClient()

    agent = ContextAgent(facts_store, vector_store, embedding_client, top_k=1)
    context = agent.get_context(project_id="proj-skyline", query_text="riverside 3BHK")

    assert context.facts.rera_number == "P51700012345"
    assert len(context.retrieved_chunks) == 1
    assert context.retrieved_chunks[0].text == "chunk one"
    assert vector_store.last_query_kwargs["project_id"] == "proj-skyline"
    assert vector_store.last_query_kwargs["top_k"] == 1
