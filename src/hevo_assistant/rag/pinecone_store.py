"""
Pinecone vector store for RAG.

Uses Pinecone cloud service + OpenAI embeddings for lightweight client installation.
"""

from typing import Any, Optional

from hevo_assistant.config import get_config


class PineconeVectorStore:
    """
    Vector store using Pinecone cloud service.

    Uses OpenAI embeddings API instead of local sentence-transformers
    to avoid heavy PyTorch dependencies.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
    ):
        """
        Initialize Pinecone vector store.

        Args:
            api_key: Pinecone API key. If None, loads from config.
            index_name: Pinecone index name. If None, loads from config.
        """
        from pinecone import Pinecone
        from openai import OpenAI

        cfg = get_config()

        self.api_key = api_key or cfg.rag.pinecone_api_key.get_secret_value()
        self.index_name = index_name or cfg.rag.pinecone_index

        if not self.api_key:
            raise ValueError(
                "Pinecone API key not configured. Run 'hevo setup' or set PINECONE_API_KEY."
            )

        # Initialize clients
        self.pc = Pinecone(api_key=self.api_key)
        self.index = self.pc.Index(self.index_name)
        self.openai = OpenAI()  # Uses OPENAI_API_KEY env var or config

        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimension = 1536

    def embed(self, text: str) -> list[float]:
        """
        Get embedding vector using OpenAI.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (1536 dimensions)
        """
        response = self.openai.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        response = self.openai.embeddings.create(
            model=self.embedding_model,
            input=texts
        )
        return [item.embedding for item in response.data]

    def search(
        self,
        query: str,
        n_results: int = 5,
        doc_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Search for similar documents.

        Args:
            query: Query text
            n_results: Number of results to return
            doc_type: Optional filter for document type ("docs" or "api")

        Returns:
            List of matching documents with metadata
        """
        embedding = self.embed(query)

        # Build filter if doc_type specified
        filter_dict = None
        if doc_type:
            filter_dict = {"doc_type": doc_type}

        results = self.index.query(
            vector=embedding,
            top_k=n_results,
            include_metadata=True,
            filter=filter_dict,
        )

        return [
            {
                "document": match.metadata.get("content", ""),
                "metadata": {
                    "title": match.metadata.get("title", ""),
                    "url": match.metadata.get("url", ""),
                    "section": match.metadata.get("section", ""),
                    "doc_type": match.metadata.get("doc_type", ""),
                },
                "score": match.score,
            }
            for match in results.matches
        ]

    def upsert(self, documents: list[dict], batch_size: int = 100) -> int:
        """
        Index documents into Pinecone.

        Args:
            documents: List of documents with 'id', 'content', and optional metadata
            batch_size: Number of documents to upsert per batch

        Returns:
            Number of documents indexed
        """
        total = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            # Get embeddings for batch
            texts = [doc["content"] for doc in batch]
            embeddings = self.embed_batch(texts)

            # Prepare vectors for upsert
            vectors = []
            for doc, embedding in zip(batch, embeddings):
                vectors.append({
                    "id": doc["id"],
                    "values": embedding,
                    "metadata": {
                        "content": doc["content"][:1000],  # Pinecone metadata limit
                        "title": doc.get("title", ""),
                        "url": doc.get("url", ""),
                        "section": doc.get("section", ""),
                        "doc_type": doc.get("doc_type", "docs"),
                    }
                })

            self.index.upsert(vectors=vectors)
            total += len(vectors)

        return total

    def delete_all(self) -> None:
        """Delete all vectors from the index."""
        self.index.delete(delete_all=True)

    def get_stats(self) -> dict:
        """Get index statistics."""
        stats = self.index.describe_index_stats()
        return {
            "total_chunks": stats.total_vector_count,
            "dimension": stats.dimension,
        }


def get_pinecone_store() -> PineconeVectorStore:
    """Get a PineconeVectorStore instance."""
    return PineconeVectorStore()
