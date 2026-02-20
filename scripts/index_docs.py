#!/usr/bin/env python3
"""
Index Hevo documentation into Pinecone.

This script crawls Hevo documentation and indexes it into Pinecone
for RAG-powered responses.

Usage:
    PINECONE_API_KEY=pc-xxx OPENAI_API_KEY=sk-xxx python scripts/index_docs.py

Or with hevo-assistant installed:
    python -m scripts.index_docs
"""

import os
import sys
import hashlib
from typing import Generator

# Add src to path if running from repo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks


def generate_doc_id(url: str, chunk_index: int) -> str:
    """Generate a unique document ID."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{url_hash}_{chunk_index}"


def crawl_and_prepare_docs() -> Generator[dict, None, None]:
    """Crawl Hevo docs and yield document chunks."""
    from hevo_assistant.crawler.docs_crawler import HevoDocsCrawler
    from hevo_assistant.crawler.api_crawler import HevoAPICrawler

    # Crawl main docs
    console.print("[blue]Crawling docs.hevodata.com...[/blue]")
    docs_crawler = HevoDocsCrawler()
    docs = docs_crawler.crawl()

    for doc in docs:
        content = doc.get("content", "")
        url = doc.get("url", "")
        title = doc.get("title", "Untitled")
        section = doc.get("section", "General")

        chunks = chunk_text(content)
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                yield {
                    "id": generate_doc_id(url, i),
                    "content": chunk,
                    "title": title,
                    "url": url,
                    "section": section,
                    "doc_type": "docs",
                }

    # Crawl API docs
    console.print("[blue]Crawling api-docs.hevodata.com...[/blue]")
    api_crawler = HevoAPICrawler()
    api_docs = api_crawler.crawl()

    for doc in api_docs:
        content = doc.get("content", "")
        url = doc.get("url", "")
        title = doc.get("title", "Untitled")
        section = doc.get("section", "API")

        chunks = chunk_text(content)
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                yield {
                    "id": generate_doc_id(url, i),
                    "content": chunk,
                    "title": title,
                    "url": url,
                    "section": section,
                    "doc_type": "api",
                }


def main():
    """Main entry point."""
    # Check for required environment variables
    pinecone_key = os.environ.get("PINECONE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not pinecone_key:
        console.print("[red]Error: PINECONE_API_KEY environment variable not set[/red]")
        sys.exit(1)

    if not openai_key:
        console.print("[red]Error: OPENAI_API_KEY environment variable not set[/red]")
        sys.exit(1)

    console.print("[bold blue]Hevo Documentation Indexer[/bold blue]\n")

    # Initialize Pinecone store
    from hevo_assistant.rag.pinecone_store import PineconeVectorStore

    try:
        store = PineconeVectorStore(api_key=pinecone_key)
        console.print(f"[green]Connected to Pinecone index: {store.index_name}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to connect to Pinecone: {e}[/red]")
        sys.exit(1)

    # Collect all documents
    console.print("\n[bold]Crawling documentation...[/bold]")
    documents = list(crawl_and_prepare_docs())
    console.print(f"Found {len(documents)} document chunks")

    if not documents:
        console.print("[yellow]No documents found. Exiting.[/yellow]")
        return

    # Index documents
    console.print("\n[bold]Indexing into Pinecone...[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing...", total=len(documents))

        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            store.upsert(batch)
            progress.update(task, advance=len(batch))

    # Show stats
    stats = store.get_stats()
    console.print(f"\n[green]Indexing complete![/green]")
    console.print(f"  Total vectors: {stats.get('total_chunks', 0)}")

    console.print("\n[bold]Users can now use the indexed documentation.[/bold]")
    console.print("They just need to run: [cyan]hevo setup[/cyan] and enter their Pinecone API key.")


if __name__ == "__main__":
    main()
