"""One-time-per-project indexing: brochure PDFs -> chunks -> embeddings -> Pinecone.

Run any time a project's brochures change:

    python -m app.ingest.brochure_ingest --project-id proj-skyline --pdf-dir data/projects/proj-skyline/brochures
"""

import argparse
import uuid
from pathlib import Path

from dotenv import load_dotenv
from pypdf import PdfReader

from app.agents.embedding_client import GeminiEmbeddingClient
from app.config import get_settings
from app.storage.vector_store import PineconeVectorStore

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def ingest_project(project_id: str, pdf_dir: Path) -> None:
    settings = get_settings()
    embedding_client = GeminiEmbeddingClient(settings.gemini_api_key, settings.gemini_embedding_model)
    vector_store = PineconeVectorStore(
        settings.pinecone_api_key, settings.pinecone_index_name, settings.pinecone_embedding_dim
    )

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {pdf_dir}")
        return

    for pdf_path in pdf_files:
        text = extract_text(pdf_path)
        if not text.strip():
            print(f"WARNING: no extractable text in {pdf_path.name} (scanned image? needs OCR) -- skipping")
            continue

        chunks = chunk_text(text)
        embeddings = embedding_client.embed(chunks)
        records = [
            {
                "chunk_id": f"{pdf_path.stem}-{i}-{uuid.uuid4().hex[:6]}",
                "text": chunk,
                "source": pdf_path.name,
                "embedding": embedding,
            }
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        vector_store.upsert(project_id=project_id, records=records)
        print(f"Indexed {len(records)} chunks from {pdf_path.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--pdf-dir", required=True, help="Folder of brochure PDFs for this project")
    args = parser.parse_args()

    load_dotenv()
    ingest_project(args.project_id, Path(args.pdf_dir))


if __name__ == "__main__":
    main()
