"""
Embedding generation using sentence-transformers.

Uses all-MiniLM-L6-v2 model for fast, high-quality embeddings.
"""

from typing import Union

from rich.console import Console

console = Console()

# Lazy loading for sentence-transformers (heavy import)
_model = None


def get_embedding_model():
    """Get or create the embedding model (lazy loaded)."""
    global _model
    if _model is None:
        console.print("[dim]Loading embedding model...[/dim]")
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")
        console.print("[dim]Embedding model loaded.[/dim]")
    return _model


def generate_embeddings(
    texts: Union[str, list[str]],
    show_progress: bool = False,
) -> list[list[float]]:
    """
    Generate embeddings for text(s).

    Args:
        texts: Single text or list of texts to embed
        show_progress: Whether to show progress bar

    Returns:
        List of embedding vectors (each vector is a list of floats)
    """
    model = get_embedding_model()

    if isinstance(texts, str):
        texts = [texts]

    # Generate embeddings
    embeddings = model.encode(
        texts,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )

    # Convert to list of lists for ChromaDB compatibility
    return embeddings.tolist()


def generate_query_embedding(query: str) -> list[float]:
    """
    Generate embedding for a search query.

    Args:
        query: Search query text

    Returns:
        Embedding vector as list of floats
    """
    embeddings = generate_embeddings(query)
    return embeddings[0]


class EmbeddingFunction:
    """
    ChromaDB-compatible embedding function.

    Can be passed to ChromaDB collection for automatic embedding.
    """

    def __init__(self):
        self._model = None

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        return generate_embeddings(input)


def get_embedding_dimension() -> int:
    """Get the dimension of embeddings from the model."""
    # all-MiniLM-L6-v2 produces 384-dimensional embeddings
    return 384
