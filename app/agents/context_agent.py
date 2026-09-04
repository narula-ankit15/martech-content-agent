from app.agents.embedding_client import EmbeddingClient
from app.models import ProjectContext
from app.storage.project_facts_store import ProjectFactsStore
from app.storage.vector_store import VectorStore


class ContextAgent:
    def __init__(
        self,
        facts_store: ProjectFactsStore,
        vector_store: VectorStore,
        embedding_client: EmbeddingClient,
        top_k: int = 5,
    ):
        self._facts_store = facts_store
        self._vector_store = vector_store
        self._embedding_client = embedding_client
        self._top_k = top_k

    def get_context(self, *, project_id: str, query_text: str) -> ProjectContext:
        facts = self._facts_store.get(project_id)
        [embedding] = self._embedding_client.embed([query_text])
        chunks = self._vector_store.query(project_id=project_id, embedding=embedding, top_k=self._top_k)
        return ProjectContext(project_id=project_id, facts=facts, retrieved_chunks=chunks)
