from pathlib import Path
import pickle

# IMPORTANT:
# Load SentenceTransformer/PyTorch before FAISS.
# On this Intel macOS environment, loading FAISS first caused
# a native segmentation fault when MiniLM was initialized.
from backend.services.embedding_service import EmbeddingService

import faiss


BASE_DIR = Path(__file__).resolve().parents[2]
INDEX_PATH = BASE_DIR / "data" / "index" / "papers.index"
METADATA_PATH = BASE_DIR / "data" / "index" / "metadata.pkl"


class RAGService:
    def __init__(self):
        print("Loading FAISS index...")

        if not INDEX_PATH.exists():
            raise FileNotFoundError(f"FAISS index not found: {INDEX_PATH}")

        if not METADATA_PATH.exists():
            raise FileNotFoundError(f"Metadata not found: {METADATA_PATH}")

        self.index = faiss.read_index(str(INDEX_PATH))

        with open(METADATA_PATH, "rb") as f:
            self.metadata = pickle.load(f)

        if self.index.ntotal != len(self.metadata):
            raise RuntimeError(
                f"FAISS/metadata mismatch: "
                f"{self.index.ntotal} vectors vs "
                f"{len(self.metadata)} metadata rows."
            )

        if self.index.d != 384:
            raise RuntimeError(
                f"Unexpected FAISS dimension: {self.index.d}"
            )

        self.embedding_service = EmbeddingService()

        print(f"FAISS vectors: {self.index.ntotal}")
        print(f"Metadata rows: {len(self.metadata)}")
        print("RAG service loaded successfully.")

    def retrieve(self, query: str, top_k: int = 5):
        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        query_embedding = self.embedding_service.encode_query(query)

        distances, indices = self.index.search(
            query_embedding,
            min(top_k, self.index.ntotal)
        )

        results = []

        for rank, (idx, distance) in enumerate(
            zip(indices[0], distances[0]),
            start=1
        ):
            if idx < 0:
                continue

            item = self.metadata[idx]

            results.append({
                "rank": rank,
                "source": item.get("source", "Unknown source"),
                "text": item.get("text", ""),
                "distance": float(distance)
            })

        return results


def build_rag_prompt(query: str, results: list) -> str:
    if not results:
        return (
            f"Question:\n{query}\n\n"
            "No relevant research context was retrieved. "
            "State that the available research collection does not "
            "provide enough evidence to answer confidently."
        )

    context_parts = []

    for result in results:
        context_parts.append(
            f"[Source {result['rank']}: {result['source']}]\n"
            f"{result['text']}"
        )

    context = "\n\n".join(context_parts)

    return f"""Use the research excerpts below to answer the question.

Important rules:
- Base the answer on the supplied research context.
- Do not invent information that is not supported by the context.
- If the context is insufficient, say so clearly.
- Write a clear academic answer.
- Do not create fake citations or references.
- The source filenames are provided separately to the user.

RESEARCH CONTEXT:
{context}

QUESTION:
{query}

ANSWER:
"""


def ingest_chunks(
    service: RAGService,
    filename: str,
    chunks: list[str]
) -> dict:
    """
    Embed new PDF chunks, add them to FAISS, and persist
    FAISS + metadata while maintaining strict alignment.
    """
    import os
    import shutil
    import tempfile

    from backend.services.embedding_service import encode_documents

    if not filename or not filename.strip():
        raise ValueError("Filename cannot be empty.")

    if not chunks:
        raise ValueError("No PDF chunks were provided.")

    # Prevent accidental duplicate ingestion.
    existing_sources = {
        item.get("source")
        for item in service.metadata
        if item.get("source")
    }

    if filename in existing_sources:
        raise ValueError(
            f"This PDF is already indexed: {filename}"
        )

    # Verify current state BEFORE modification.
    before_vectors = service.index.ntotal
    before_metadata = len(service.metadata)

    if before_vectors != before_metadata:
        raise RuntimeError(
            "Existing FAISS index and metadata are not aligned."
        )

    # Embed all new chunks.
    embeddings = encode_documents(
        service.embedding_service,
        chunks
    )

    if embeddings.shape[0] != len(chunks):
        raise RuntimeError(
            "Embedding count does not match chunk count."
        )

    # Build metadata in memory first.
    new_metadata = []

    for chunk_number, chunk in enumerate(chunks):
        new_metadata.append({
            "source": filename,
            "text": chunk,
            "chunk_number": chunk_number,
            "document_type": "user_upload",
        })

    # Backup current persistent files before modification.
    index_backup = Path(str(INDEX_PATH) + ".backup")
    metadata_backup = Path(str(METADATA_PATH) + ".backup")

    shutil.copy2(INDEX_PATH, index_backup)
    shutil.copy2(METADATA_PATH, metadata_backup)

    try:
        # Modify in-memory state.
        service.index.add(embeddings)
        service.metadata.extend(new_metadata)

        after_vectors = service.index.ntotal
        after_metadata = len(service.metadata)

        expected_total = before_vectors + len(chunks)

        if after_vectors != expected_total:
            raise RuntimeError(
                "Unexpected FAISS vector count after ingestion."
            )

        if after_metadata != expected_total:
            raise RuntimeError(
                "Unexpected metadata count after ingestion."
            )

        if after_vectors != after_metadata:
            raise RuntimeError(
                "FAISS and metadata became misaligned."
            )

        # Write temporary files first.
        index_tmp = Path(
            tempfile.mktemp(
                prefix="deepresearch_index_",
                suffix=".index",
                dir=str(INDEX_PATH.parent)
            )
        )

        metadata_tmp = Path(
            tempfile.mktemp(
                prefix="deepresearch_metadata_",
                suffix=".pkl",
                dir=str(METADATA_PATH.parent)
            )
        )

        faiss.write_index(
            service.index,
            str(index_tmp)
        )

        with open(metadata_tmp, "wb") as f:
            pickle.dump(
                service.metadata,
                f
            )

        # Atomic replacement of persistent files.
        os.replace(index_tmp, INDEX_PATH)
        os.replace(metadata_tmp, METADATA_PATH)

    except Exception:
        # Restore persistent files.
        shutil.copy2(index_backup, INDEX_PATH)
        shutil.copy2(metadata_backup, METADATA_PATH)

        # Reload in-memory state from restored files.
        service.index = faiss.read_index(
            str(INDEX_PATH)
        )

        with open(METADATA_PATH, "rb") as f:
            service.metadata = pickle.load(f)

        raise

    return {
        "filename": filename,
        "chunks_added": len(chunks),
        "vectors_before": before_vectors,
        "vectors_after": service.index.ntotal,
        "metadata_after": len(service.metadata),
        "aligned": (
            service.index.ntotal ==
            len(service.metadata)
        ),
    }
