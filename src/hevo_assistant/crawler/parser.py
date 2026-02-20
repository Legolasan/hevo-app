"""
HTML parser utilities for documentation crawling.

Extracts clean text content from HTML pages.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup, NavigableString


@dataclass
class ParsedDocument:
    """Represents a parsed documentation page."""

    url: str
    title: str
    content: str
    section: str
    doc_type: str  # "docs" or "api"
    last_crawled: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "section": self.section,
            "doc_type": self.doc_type,
            "last_crawled": self.last_crawled.isoformat(),
        }


class HTMLParser:
    """Parser for extracting clean content from HTML documentation pages."""

    # Tags to remove completely (including content)
    REMOVE_TAGS = [
        "script",
        "style",
        "nav",
        "footer",
        "header",
        "aside",
        "noscript",
        "iframe",
        "svg",
        "button",
        "form",
    ]

    # Tags that typically contain navigation/UI elements
    REMOVE_CLASSES = [
        "nav",
        "navigation",
        "sidebar",
        "menu",
        "footer",
        "header",
        "breadcrumb",
        "toc",
        "table-of-contents",
        "edit-page",
        "share",
        "social",
    ]

    def __init__(self):
        pass

    def parse_docs_page(self, html: str, url: str) -> Optional[ParsedDocument]:
        """
        Parse a documentation page from docs.hevodata.com.

        Args:
            html: Raw HTML content
            url: URL of the page

        Returns:
            ParsedDocument or None if parsing fails
        """
        soup = BeautifulSoup(html, "lxml")

        # Remove unwanted elements
        self._remove_unwanted_elements(soup)

        # Extract title
        title = self._extract_title(soup)
        if not title:
            return None

        # Extract main content
        content = self._extract_main_content(soup)
        if not content or len(content.strip()) < 50:  # Skip very short pages
            return None

        # Extract section from URL
        section = self._extract_section_from_url(url)

        return ParsedDocument(
            url=url,
            title=title,
            content=content,
            section=section,
            doc_type="docs",
            last_crawled=datetime.now(),
        )

    def parse_api_page(self, html: str, url: str) -> Optional[ParsedDocument]:
        """
        Parse an API documentation page from api-docs.hevodata.com.

        Args:
            html: Raw HTML content
            url: URL of the page

        Returns:
            ParsedDocument or None if parsing fails
        """
        soup = BeautifulSoup(html, "lxml")

        # Remove unwanted elements
        self._remove_unwanted_elements(soup)

        # Extract title (API pages often have different structure)
        title = self._extract_title(soup)
        if not title:
            # Try to get from h1 or first heading
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else "API Reference"

        # Extract content
        content = self._extract_api_content(soup)
        if not content or len(content.strip()) < 50:
            return None

        # Section is typically "API" for API docs
        section = "API"

        return ParsedDocument(
            url=url,
            title=title,
            content=content,
            section=section,
            doc_type="api",
            last_crawled=datetime.now(),
        )

    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """Remove unwanted HTML elements from the soup."""
        # Remove tags completely
        for tag in self.REMOVE_TAGS:
            for element in soup.find_all(tag):
                element.decompose()

        # Remove elements with navigation-related classes
        for class_pattern in self.REMOVE_CLASSES:
            for element in soup.find_all(class_=re.compile(class_pattern, re.I)):
                element.decompose()

        # Remove elements with navigation-related IDs
        for id_pattern in self.REMOVE_CLASSES:
            for element in soup.find_all(id=re.compile(id_pattern, re.I)):
                element.decompose()

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract page title."""
        # Try meta title first
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Clean up common suffixes
            for suffix in [" | Hevo", " - Hevo", " | Hevo Data", " - Hevo Data"]:
                if title.endswith(suffix):
                    title = title[: -len(suffix)]
            return title

        # Try h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return None

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from a documentation page."""
        # Try to find main content area
        main_content = None

        # Common content containers
        content_selectors = [
            ("main", {}),
            ("article", {}),
            ("div", {"class": re.compile(r"content|main|body", re.I)}),
            ("div", {"id": re.compile(r"content|main|body", re.I)}),
            ("div", {"class": "markdown-body"}),
            ("div", {"class": "documentation"}),
        ]

        for tag, attrs in content_selectors:
            main_content = soup.find(tag, attrs)
            if main_content:
                break

        if not main_content:
            main_content = soup.find("body")

        if not main_content:
            return ""

        # Extract text with some structure
        return self._extract_text_with_structure(main_content)

    def _extract_api_content(self, soup: BeautifulSoup) -> str:
        """Extract content specifically for API documentation pages."""
        # API docs often have endpoint information, parameters, etc.
        content_parts = []

        # Look for API-specific elements
        for section in soup.find_all(["div", "section"]):
            text = section.get_text(strip=True)
            if len(text) > 20:  # Skip very short sections
                content_parts.append(text)

        if content_parts:
            return "\n\n".join(content_parts[:20])  # Limit sections

        # Fallback to main content extraction
        return self._extract_main_content(soup)

    def _extract_text_with_structure(self, element) -> str:
        """
        Extract text while preserving some structure (headings, paragraphs).
        """
        if element is None:
            return ""

        parts = []

        for child in element.descendants:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    parts.append(text)
            elif child.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                # Add newlines around headings
                text = child.get_text(strip=True)
                if text:
                    parts.append(f"\n\n## {text}\n")
            elif child.name in ["p", "div", "section"]:
                # Just let content flow
                pass
            elif child.name == "li":
                text = child.get_text(strip=True)
                if text:
                    parts.append(f"- {text}")
            elif child.name in ["pre", "code"]:
                text = child.get_text(strip=True)
                if text:
                    parts.append(f"\n```\n{text}\n```\n")

        # Clean up the result
        text = " ".join(parts)
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        return text.strip()

    def _extract_section_from_url(self, url: str) -> str:
        """Extract section name from URL path."""
        # Parse URL path
        from urllib.parse import urlparse

        path = urlparse(url).path.strip("/")
        parts = path.split("/")

        if parts:
            # First part is usually the section
            section = parts[0].replace("-", " ").title()
            return section

        return "General"


def chunk_text(
    text: str, chunk_size: int = 500, chunk_overlap: int = 50
) -> list[str]:
    """
    Split text into overlapping chunks for embedding.

    Args:
        text: Text to split
        chunk_size: Target size of each chunk (in characters)
        chunk_overlap: Overlap between consecutive chunks

    Returns:
        List of text chunks
    """
    if not text:
        return []

    # Split by paragraphs first
    paragraphs = re.split(r"\n\n+", text)

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph exceeds chunk size, save current and start new
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # Start new chunk with overlap from previous
            if chunk_overlap > 0:
                overlap_text = current_chunk[-chunk_overlap:]
                current_chunk = overlap_text + " " + para
            else:
                current_chunk = para
        else:
            current_chunk += " " + para if current_chunk else para

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks
