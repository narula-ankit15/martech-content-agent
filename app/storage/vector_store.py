from typing import Protocol

from app.models import RetrievedChunk


class VectorStore(Protocol):
    """Thin abstraction over "store embeddings, retrieve nearest neighbors"
    so swapping Pinecone for Chroma (or anything else) later is a new class
    here, not a rewrite of the Context agent or the ingestion CLI.
    """

    def upsert(self, *, project_id: str, records: list[dict]) -> None:
        """records: [{"chunk_id": str, "text": str, "source": str, "embedding": list[float]}]"""
        ...

    def query(self, *, project_id: str, embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        ...


class PineconeVectorStore:
    def __init__(self, api_key: str, index_name: str, dimension: int):
        from pinecone import Pinecone, ServerlessSpec

        self._pc = Pinecone(api_key=api_key)
        existing = [idx["name"] for idx in self._pc.list_indexes()]
        if index_name not in existing:
            self._pc.create_index(
                name=index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        self._index = self._pc.Index(index_name)

    def upsert(self, *, project_id: str, records: list[dict]) -> None:
        # One Pinecone namespace per project_id keeps projects isolated from
        # each other in a single shared index (fits the free-tier one-index limit)
        # and makes re-indexing a single project a scoped delete, not a full wipe.
        vectors = [
            {
                "id": f"{project_id}::{r['chunk_id']}",
                "values": r["embedding"],
                "metadata": {"project_id": project_id, "text": r["text"], "source": r["source"]},
            }
            for r in records
        ]
        self._index.upsert(vectors=vectors, namespace=project_id)

    def query(self, *, project_id: str, embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        result = self._index.query(
            vector=embedding, top_k=top_k, namespace=project_id, include_metadata=True
        )
        return [
            RetrievedChunk(
                text=match["metadata"]["text"],
                source=match["metadata"]["source"],
                score=match["score"],
            )
            for match in result["matches"]
        ]
