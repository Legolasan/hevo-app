"""
Retriever for getting relevant context from the vector store.

Provides context for LLM responses based on user queries.
"""

from typing import Optional

from hevo_assistant.config import get_config
from hevo_assistant.rag.vectorstore import VectorStore


class Retriever:
    """
    Retriever for fetching relevant documentation context.

    Searches the vector store and formats results for LLM consumption.
    """

    def __init__(self, vector_store: Optional[VectorStore] = None):
        """
        Initialize the retriever.

        Args:
            vector_store: VectorStore instance. If None, creates one.
        """
        self.vector_store = vector_store or VectorStore()
        self.config = get_config()

    def get_context(
        self,
        query: str,
        max_results: Optional[int] = None,
        doc_type: Optional[str] = None,
    ) -> str:
        """
        Get relevant context for a query.

        Args:
            query: User's question or request
            max_results: Maximum number of results (default from config)
            doc_type: Filter for "docs" or "api"

        Returns:
            Formatted context string for LLM
        """
        if max_results is None:
            max_results = self.config.rag.top_k

        # Search for relevant documents
        results = self.vector_store.search(
            query=query,
            n_results=max_results,
            doc_type=doc_type,
        )

        if not results:
            return "No relevant documentation found."

        # Format results for LLM
        context_parts = []

        for i, result in enumerate(results, 1):
            metadata = result.get("metadata", {})
            document = result.get("document", "")

            # Format each result
            source = metadata.get("url", "Unknown source")
            title = metadata.get("title", "Untitled")
            section = metadata.get("section", "General")

            context_parts.append(
                f"[Source {i}: {title}]\n"
                f"Section: {section}\n"
                f"URL: {source}\n"
                f"Content:\n{document}\n"
            )

        return "\n---\n".join(context_parts)

    def get_context_with_sources(
        self,
        query: str,
        max_results: Optional[int] = None,
        doc_type: Optional[str] = None,
    ) -> tuple[str, list[dict]]:
        """
        Get context along with source information.

        Args:
            query: User's question or request
            max_results: Maximum number of results
            doc_type: Filter for "docs" or "api"

        Returns:
            Tuple of (context string, list of source dictionaries)
        """
        if max_results is None:
            max_results = self.config.rag.top_k

        results = self.vector_store.search(
            query=query,
            n_results=max_results,
            doc_type=doc_type,
        )

        if not results:
            return "No relevant documentation found.", []

        # Extract sources
        sources = []
        seen_urls = set()

        for result in results:
            metadata = result.get("metadata", {})
            url = metadata.get("url", "")

            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append(
                    {
                        "url": url,
                        "title": metadata.get("title", "Untitled"),
                        "section": metadata.get("section", "General"),
                    }
                )

        # Format context
        context = self.get_context(query, max_results, doc_type)

        return context, sources

    def is_ready(self) -> bool:
        """Check if the retriever has indexed documentation."""
        stats = self.vector_store.get_stats()
        return stats.get("total_chunks", 0) > 0

    def get_stats(self) -> dict:
        """Get statistics about the indexed documentation."""
        return self.vector_store.get_stats()


class QueryAnalyzer:
    """
    Analyzes user queries to determine the best retrieval strategy.
    """

    # Keywords that suggest API-related queries
    API_KEYWORDS = [
        "api",
        "endpoint",
        "request",
        "response",
        "http",
        "get",
        "post",
        "put",
        "delete",
        "authentication",
        "token",
        "rate limit",
    ]

    # Keywords that suggest action queries
    ACTION_KEYWORDS = [
        "create",
        "delete",
        "pause",
        "resume",
        "run",
        "start",
        "stop",
        "update",
        "change",
        "modify",
        "add",
        "remove",
    ]

    # Keywords that suggest informational queries
    INFO_KEYWORDS = [
        "what is",
        "how to",
        "how do",
        "explain",
        "tell me about",
        "describe",
        "overview",
        "introduction",
    ]

    @classmethod
    def analyze(cls, query: str) -> dict:
        """
        Analyze a query to determine retrieval strategy.

        Args:
            query: User's query

        Returns:
            Dictionary with query type and suggested doc_type filter
        """
        query_lower = query.lower()

        # Check for API-related queries
        is_api_query = any(kw in query_lower for kw in cls.API_KEYWORDS)

        # Check for action queries
        is_action_query = any(kw in query_lower for kw in cls.ACTION_KEYWORDS)

        # Check for informational queries
        is_info_query = any(kw in query_lower for kw in cls.INFO_KEYWORDS)

        # Determine doc type filter
        doc_type = None
        if is_api_query and not is_info_query:
            doc_type = "api"

        return {
            "is_api_query": is_api_query,
            "is_action_query": is_action_query,
            "is_info_query": is_info_query,
            "suggested_doc_type": doc_type,
        }


def get_retriever() -> Retriever:
    """Get a retriever instance."""
    return Retriever()


# Add convenient methods for the Retriever class
Retriever.retrieve = lambda self, query, n_results=5: self.vector_store.search(query, n_results=n_results)
Retriever.format_context = lambda self, docs: "\n\n---\n\n".join(
    f"**{d.get('metadata', {}).get('title', 'Untitled')}**\n{d.get('document', '')}"
    for d in docs
) if docs else ""
