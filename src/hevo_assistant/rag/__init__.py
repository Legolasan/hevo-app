"""RAG (Retrieval Augmented Generation) system.

Supports two backends:
- Pinecone (default): Lightweight, uses cloud service + OpenAI embeddings
- Local: Uses ChromaDB + sentence-transformers (requires local-rag extra)
"""

from hevo_assistant.rag.retriever import Retriever, get_retriever

# Pinecone store is always available (lightweight client)
from hevo_assistant.rag.pinecone_store import PineconeVectorStore, get_pinecone_store

# Local VectorStore is optional (heavy dependencies)
try:
    from hevo_assistant.rag.vectorstore import VectorStore, get_vectorstore
except ImportError:
    VectorStore = None
    get_vectorstore = None

__all__ = [
    "Retriever",
    "get_retriever",
    "PineconeVectorStore",
    "get_pinecone_store",
    "VectorStore",
    "get_vectorstore",
]
