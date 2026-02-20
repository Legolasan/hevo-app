"""
Crawler for Hevo API documentation at api-docs.hevodata.com.

Crawls the API reference and extracts endpoint documentation.
"""

import re
import time
from typing import Generator, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from hevo_assistant.crawler.parser import HTMLParser, ParsedDocument

console = Console()


class APICrawler:
    """Crawler for api-docs.hevodata.com API documentation."""

    BASE_URL = "https://api-docs.hevodata.com"

    # Known API documentation sections
    API_SECTIONS = [
        "/reference/introduction",
        "/reference/authentication",
        "/reference/pipelines",
        "/reference/destinations",
        "/reference/objects",
        "/reference/transformations",
        "/reference/schema-mappings",
        "/reference/event-types",
        "/reference/models",
        "/reference/workflows",
        "/reference/users",
        "/reference/rate-limits",
        "/reference/response-codes",
    ]

    def __init__(
        self,
        max_pages: int = 100,
        delay: float = 0.5,
        timeout: int = 30,
    ):
        """
        Initialize the API documentation crawler.

        Args:
            max_pages: Maximum number of pages to crawl
            delay: Delay between requests (seconds)
            timeout: Request timeout (seconds)
        """
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout
        self.parser = HTMLParser()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "HevoAssistant/1.0 (API Documentation Crawler)",
                "Accept": "text/html,application/xhtml+xml,application/json",
            }
        )

    def crawl(self) -> Generator[ParsedDocument, None, None]:
        """
        Crawl the API documentation site and yield parsed documents.

        Yields:
            ParsedDocument objects for each successfully parsed page
        """
        visited: Set[str] = set()
        to_visit: list[str] = []

        # Start with known API sections
        for section in self.API_SECTIONS:
            to_visit.append(urljoin(self.BASE_URL, section))

        pages_crawled = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Crawling api-docs.hevodata.com...", total=None)

            while to_visit and pages_crawled < self.max_pages:
                url = to_visit.pop(0)

                # Normalize URL
                url = self._normalize_url(url)

                # Skip if already visited
                if url in visited:
                    continue

                # Must be from API docs
                if not url.startswith(self.BASE_URL):
                    continue

                visited.add(url)
                progress.update(
                    task, description=f"Crawling ({pages_crawled}/{self.max_pages}): {url[:60]}..."
                )

                # Fetch and parse the page
                doc = self._fetch_and_parse(url)

                if doc:
                    pages_crawled += 1
                    yield doc

                    # Extract links for further crawling
                    new_links = self._extract_links_from_page(url)
                    for link in new_links:
                        if link not in visited and link not in to_visit:
                            to_visit.append(link)

                # Rate limiting
                time.sleep(self.delay)

            progress.update(task, description=f"Completed: {pages_crawled} API pages crawled")

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and query parameters."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    def _fetch_and_parse(self, url: str) -> Optional[ParsedDocument]:
        """Fetch a URL and parse its content."""
        try:
            response = self.session.get(url, timeout=self.timeout)

            # Handle 404s gracefully for API docs
            if response.status_code == 404:
                return None

            response.raise_for_status()

            # Only process HTML
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None

            return self.parser.parse_api_page(response.text, url)

        except requests.RequestException as e:
            console.print(f"[dim]Error fetching {url}: {e}[/dim]")
            return None
        except Exception as e:
            console.print(f"[dim]Error parsing {url}: {e}[/dim]")
            return None

    def _extract_links_from_page(self, url: str) -> list[str]:
        """
        Re-fetch page and extract links for further crawling.
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "lxml")
            links = []

            for a in soup.find_all("a", href=True):
                href = a["href"]

                # Convert relative to absolute
                if href.startswith("/"):
                    href = urljoin(self.BASE_URL, href)

                # Only include API docs links
                if href.startswith(self.BASE_URL) and "/reference/" in href:
                    links.append(self._normalize_url(href))

            return links

        except Exception:
            return []

    def crawl_endpoints(self) -> list[dict]:
        """
        Crawl and extract API endpoint information.

        Returns:
            List of endpoint dictionaries with method, path, description
        """
        endpoints = []

        for doc in self.crawl():
            # Try to extract endpoint info from content
            endpoint_info = self._extract_endpoint_info(doc)
            if endpoint_info:
                endpoints.append(endpoint_info)

        return endpoints

    def _extract_endpoint_info(self, doc: ParsedDocument) -> Optional[dict]:
        """
        Extract structured endpoint information from a parsed document.

        Args:
            doc: Parsed API documentation page

        Returns:
            Dictionary with endpoint details or None
        """
        content = doc.content

        # Try to find HTTP method and path
        method_pattern = r"(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/{}\-\.]+)"
        match = re.search(method_pattern, content)

        if match:
            return {
                "method": match.group(1),
                "path": match.group(2),
                "title": doc.title,
                "url": doc.url,
                "description": content[:500],  # First 500 chars as description
            }

        return None


def crawl_all_docs() -> tuple[list[ParsedDocument], list[ParsedDocument]]:
    """
    Convenience function to crawl both docs and API documentation.

    Returns:
        Tuple of (docs_pages, api_pages)
    """
    docs_crawler = DocsCrawler()
    api_crawler = APICrawler()

    docs_pages = list(docs_crawler.crawl())
    api_pages = list(api_crawler.crawl())

    return docs_pages, api_pages


# Import DocsCrawler for convenience
from hevo_assistant.crawler.docs_crawler import DocsCrawler

__all__ = ["APICrawler", "DocsCrawler", "crawl_all_docs"]
