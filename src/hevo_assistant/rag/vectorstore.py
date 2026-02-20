"""
Vector store using ChromaDB for document storage and retrieval.
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from rich.console import Console

from hevo_assistant.config import get_config
from hevo_assistant.crawler.parser import ParsedDocument, chunk_text
from hevo_assistant.rag.embeddings import generate_embeddings

console = Console()


class VectorStore:
    """
    ChromaDB-based vector store for Hevo documentation.

    Manages two collections:
    - hevo_docs: Public documentation from docs.hevodata.com
    - hevo_api: API reference from api-docs.hevodata.com
    """

    DOCS_COLLECTION = "hevo_docs"
    API_COLLECTION = "hevo_api"

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the vector store.

        Args:
            db_path: Path to ChromaDB storage. If None, uses config.
        """
        if db_path is None:
            config = get_config()
            db_path = config.rag.resolved_db_path

        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Get or create collections
        self._docs_collection = None
        self._api_collection = None

    @property
    def docs_collection(self):
        """Get the docs collection (lazy loaded)."""
        if self._docs_collection is None:
            self._docs_collection = self.client.get_or_create_collection(
                name=self.DOCS_COLLECTION,
                metadata={"description": "Hevo public documentation"},
            )
        return self._docs_collection

    @property
    def api_collection(self):
        """Get the API collection (lazy loaded)."""
        if self._api_collection is None:
            self._api_collection = self.client.get_or_create_collection(
                name=self.API_COLLECTION,
                metadata={"description": "Hevo API reference"},
            )
        return self._api_collection

    def add_document(self, doc: ParsedDocument) -> int:
        """
        Add a parsed document to the appropriate collection.

        Args:
            doc: Parsed document to add

        Returns:
            Number of chunks added
        """
        # Get config for chunking parameters
        config = get_config()

        # Split content into chunks
        chunks = chunk_text(
            doc.content,
            chunk_size=config.rag.chunk_size,
            chunk_overlap=config.rag.chunk_overlap,
        )

        if not chunks:
            return 0

        # Select collection based on doc type
        collection = (
            self.api_collection if doc.doc_type == "api" else self.docs_collection
        )

        # Generate embeddings for all chunks
        embeddings = generate_embeddings(chunks, show_progress=False)

        # Prepare data for ChromaDB
        ids = []
        documents = []
        metadatas = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Generate unique ID based on URL and chunk index
            chunk_id = self._generate_id(doc.url, i)

            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(
                {
                    "url": doc.url,
                    "title": doc.title,
                    "section": doc.section,
                    "doc_type": doc.doc_type,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
            )

        # Add to collection
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        return len(chunks)

    def add_documents(self, docs: list[ParsedDocument]) -> dict:
        """
        Add multiple documents to the vector store.

        Args:
            docs: List of parsed documents

        Returns:
            Dictionary with counts: {"docs": n, "api": m, "chunks": total}
        """
        docs_count = 0
        api_count = 0
        total_chunks = 0

        for doc in docs:
            chunks_added = self.add_document(doc)
            total_chunks += chunks_added

            if doc.doc_type == "api":
                api_count += 1
            else:
                docs_count += 1

        return {
            "docs": docs_count,
            "api": api_count,
            "chunks": total_chunks,
        }

    def search(
        self,
        query: str,
        n_results: int = 5,
        doc_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Search for relevant documents.

        Args:
            query: Search query
            n_results: Number of results to return
            doc_type: Optional filter for "docs" or "api"

        Returns:
            List of search results with document, metadata, and distance
        """
        # Generate query embedding
        query_embedding = generate_embeddings(query)[0]

        results = []

        # Determine which collections to search
        if doc_type == "docs":
            collections = [self.docs_collection]
        elif doc_type == "api":
            collections = [self.api_collection]
        else:
            collections = [self.docs_collection, self.api_collection]

        # Search each collection
        for collection in collections:
            try:
                search_results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                )

                # Process results
                if search_results and search_results["documents"]:
                    for i, doc in enumerate(search_results["documents"][0]):
                        results.append(
                            {
                                "document": doc,
                                "metadata": search_results["metadatas"][0][i],
                                "distance": search_results["distances"][0][i]
                                if search_results.get("distances")
                                else None,
                            }
                        )
            except Exception as e:
                console.print(f"[dim]Search error in {collection.name}: {e}[/dim]")

        # Sort by distance (lower is better) and return top n
        results.sort(key=lambda x: x.get("distance", float("inf")))
        return results[:n_results]

    def get_stats(self) -> dict:
        """
        Get statistics about the vector store.

        Returns:
            Dictionary with collection counts and metadata
        """
        docs_count = self.docs_collection.count()
        api_count = self.api_collection.count()

        return {
            "docs_chunks": docs_count,
            "api_chunks": api_count,
            "total_chunks": docs_count + api_count,
            "db_path": str(self.db_path),
        }

    def clear(self, doc_type: Optional[str] = None) -> None:
        """
        Clear documents from the vector store.

        Args:
            doc_type: "docs", "api", or None for both
        """
        if doc_type in (None, "docs"):
            self.client.delete_collection(self.DOCS_COLLECTION)
            self._docs_collection = None

        if doc_type in (None, "api"):
            self.client.delete_collection(self.API_COLLECTION)
            self._api_collection = None

    def _generate_id(self, url: str, chunk_index: int) -> str:
        """Generate a unique ID for a document chunk."""
        content = f"{url}:{chunk_index}"
        return hashlib.md5(content.encode()).hexdigest()


def update_documentation() -> dict:
    """
    Convenience function to crawl and update all documentation.

    Returns:
        Statistics about the update
    """
    from hevo_assistant.crawler.docs_crawler import DocsCrawler
    from hevo_assistant.crawler.api_crawler import APICrawler

    console.print("[bold]Updating documentation index...[/bold]\n")

    # Initialize vector store
    store = VectorStore()

    # Clear existing data
    console.print("Clearing existing index...")
    store.clear()

    # Crawl docs
    console.print("\n[bold]Crawling public documentation...[/bold]")
    docs_crawler = DocsCrawler(max_pages=150)
    docs_pages = list(docs_crawler.crawl())

    # Crawl API docs
    console.print("\n[bold]Crawling API documentation...[/bold]")
    api_crawler = APICrawler(max_pages=50)
    api_pages = list(api_crawler.crawl())

    # Add to vector store
    console.print("\n[bold]Indexing documents...[/bold]")
    all_docs = docs_pages + api_pages
    stats = store.add_documents(all_docs)

    # Update config with last update time
    from hevo_assistant.config import get_config, save_config

    config = get_config()
    config.rag.last_updated = datetime.now()
    save_config(config)

    console.print(f"\n[green]Documentation index updated![/green]")
    console.print(f"  - Docs pages: {stats['docs']}")
    console.print(f"  - API pages: {stats['api']}")
    console.print(f"  - Total chunks: {stats['chunks']}")

    return stats


def get_vectorstore() -> VectorStore:
    """Get a VectorStore instance."""
    return VectorStore()
