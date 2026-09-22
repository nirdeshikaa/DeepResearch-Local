from sentence_transformers import SentenceTransformer
import numpy as np


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingService:
    def __init__(self):
        print(f"Loading embedding model: {MODEL_NAME}")
        self.model = SentenceTransformer(MODEL_NAME)

        dimension = self.model.get_sentence_embedding_dimension()

        if dimension != 384:
            raise RuntimeError(
                f"Unexpected embedding dimension: {dimension}. "
                "DeepResearch FAISS index requires 384 dimensions."
            )

        print("Embedding model loaded successfully.")
        print(f"Embedding dimension: {dimension}")

    def encode_query(self, text: str) -> np.ndarray:
        text = text.strip()

        if not text:
            raise ValueError("Query cannot be empty.")

        embedding = self.model.encode(
            [text],
            convert_to_numpy=True
        )

        return embedding.astype("float32")


def encode_documents(
    service: EmbeddingService,
    texts: list[str]
) -> np.ndarray:
    if not texts:
        raise ValueError("No document chunks were provided.")

    cleaned = [
        text.strip()
        for text in texts
        if text and text.strip()
    ]

    if not cleaned:
        raise ValueError(
            "Document chunks contain no searchable text."
        )

    embeddings = service.model.encode(
        cleaned,
        convert_to_numpy=True,
        show_progress_bar=False
    )

    embeddings = embeddings.astype("float32")

    if embeddings.ndim != 2 or embeddings.shape[1] != 384:
        raise RuntimeError(
            f"Unexpected document embedding shape: "
            f"{embeddings.shape}"
        )

    return embeddings
