"""
Crawler for Hevo public documentation at docs.hevodata.com.

Crawls the documentation site and extracts content for RAG indexing.
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


class DocsCrawler:
    """Crawler for docs.hevodata.com documentation."""

    BASE_URL = "https://docs.hevodata.com"

    # Sections to prioritize crawling
    PRIORITY_SECTIONS = [
        "/pipelines",
        "/sources",
        "/destinations",
        "/transformations",
        "/schema-mapper",
        "/models",
        "/workflows",
        "/getting-started",
        "/faqs",
    ]

    # Patterns to skip
    SKIP_PATTERNS = [
        r"/release-notes",
        r"/changelog",
        r"/api-reference",  # Handled by API crawler
        r"\.(pdf|png|jpg|jpeg|gif|svg|zip)$",
    ]

    def __init__(
        self,
        max_pages: int = 200,
        delay: float = 0.5,
        timeout: int = 30,
    ):
        """
        Initialize the documentation crawler.

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
                "User-Agent": "HevoAssistant/1.0 (Documentation Crawler)",
                "Accept": "text/html,application/xhtml+xml",
            }
        )

    def crawl(self) -> Generator[ParsedDocument, None, None]:
        """
        Crawl the documentation site and yield parsed documents.

        Yields:
            ParsedDocument objects for each successfully parsed page
        """
        visited: Set[str] = set()
        to_visit: list[str] = []

        # Start with priority sections
        for section in self.PRIORITY_SECTIONS:
            to_visit.append(urljoin(self.BASE_URL, section))

        # Also add the main page
        to_visit.insert(0, self.BASE_URL)

        pages_crawled = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Crawling docs.hevodata.com...", total=None)

            while to_visit and pages_crawled < self.max_pages:
                url = to_visit.pop(0)

                # Normalize URL
                url = self._normalize_url(url)

                # Skip if already visited or should be skipped
                if url in visited or self._should_skip(url):
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
                    new_links = self._extract_links(url, doc.content)
                    for link in new_links:
                        if link not in visited and link not in to_visit:
                            to_visit.append(link)

                # Rate limiting
                time.sleep(self.delay)

            progress.update(task, description=f"Completed: {pages_crawled} pages crawled")

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and query parameters."""
        parsed = urlparse(url)
        # Remove fragment and most query parameters
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    def _should_skip(self, url: str) -> bool:
        """Check if URL should be skipped."""
        # Must be from docs.hevodata.com
        if not url.startswith(self.BASE_URL):
            return True

        # Check skip patterns
        for pattern in self.SKIP_PATTERNS:
            if re.search(pattern, url, re.I):
                return True

        return False

    def _fetch_and_parse(self, url: str) -> Optional[ParsedDocument]:
        """Fetch a URL and parse its content."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            # Only process HTML
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None

            return self.parser.parse_docs_page(response.text, url)

        except requests.RequestException as e:
            console.print(f"[dim]Error fetching {url}: {e}[/dim]")
            return None
        except Exception as e:
            console.print(f"[dim]Error parsing {url}: {e}[/dim]")
            return None

    def _extract_links(self, base_url: str, content: str) -> list[str]:
        """
        Extract links from page content for further crawling.

        Note: This is a simplified version. The actual implementation
        would re-fetch the page and extract links from HTML.
        """
        # For now, return empty - links are extracted during HTML parsing
        # In a full implementation, we'd store links during parsing
        return []

    def crawl_page(self, url: str) -> Optional[ParsedDocument]:
        """
        Crawl a single page.

        Args:
            url: URL to crawl

        Returns:
            ParsedDocument or None
        """
        return self._fetch_and_parse(url)


class SitemapCrawler:
    """Crawl using sitemap.xml if available."""

    def __init__(self, base_url: str = "https://docs.hevodata.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "HevoAssistant/1.0 (Documentation Crawler)",
            }
        )

    def get_urls_from_sitemap(self) -> list[str]:
        """
        Try to get URLs from sitemap.xml.

        Returns:
            List of URLs from sitemap, or empty list if not available
        """
        sitemap_urls = [
            f"{self.base_url}/sitemap.xml",
            f"{self.base_url}/sitemap_index.xml",
        ]

        for sitemap_url in sitemap_urls:
            try:
                response = self.session.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    return self._parse_sitemap(response.text)
            except requests.RequestException:
                continue

        return []

    def _parse_sitemap(self, xml_content: str) -> list[str]:
        """Parse sitemap XML and extract URLs."""
        soup = BeautifulSoup(xml_content, "lxml-xml")
        urls = []

        # Handle regular sitemap
        for loc in soup.find_all("loc"):
            url = loc.get_text(strip=True)
            if url:
                urls.append(url)

        # Handle sitemap index (contains links to other sitemaps)
        for sitemap in soup.find_all("sitemap"):
            loc = sitemap.find("loc")
            if loc:
                nested_urls = self._fetch_nested_sitemap(loc.get_text(strip=True))
                urls.extend(nested_urls)

        return urls

    def _fetch_nested_sitemap(self, url: str) -> list[str]:
        """Fetch and parse a nested sitemap."""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return self._parse_sitemap(response.text)
        except requests.RequestException:
            pass
        return []
