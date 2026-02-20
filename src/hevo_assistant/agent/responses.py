"""
Response formatting for chat output.

Formats LLM responses and action results for display.
"""

from dataclasses import dataclass
from typing import Any, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from hevo_assistant.agent.actions import ActionResult


console = Console()


@dataclass
class FormattedResponse:
    """A formatted response ready for display."""

    text: str
    action_result: Optional[ActionResult] = None
    citations: list[dict] = None

    def __post_init__(self):
        if self.citations is None:
            self.citations = []


class ResponseFormatter:
    """
    Formats responses for CLI display.

    Handles both LLM text responses and action results.
    """

    def format_chat_response(
        self,
        llm_response: str,
        action_result: Optional[ActionResult] = None,
        citations: list[dict] = None,
    ) -> FormattedResponse:
        """
        Format a chat response for display.

        Args:
            llm_response: Raw LLM response text
            action_result: Result of any executed action
            citations: RAG citations used for the response

        Returns:
            FormattedResponse ready for display
        """
        # Clean up the response (remove action JSON if present)
        text = self._clean_response(llm_response)

        return FormattedResponse(
            text=text,
            action_result=action_result,
            citations=citations or [],
        )

    def _clean_response(self, response: str) -> str:
        """Remove action JSON blocks from response text."""
        import re

        # Remove markdown JSON blocks
        cleaned = re.sub(r"```json\s*\{.*?\}\s*```", "", response, flags=re.DOTALL)
        # Remove inline JSON actions
        cleaned = re.sub(r'\{"action":\s*"[^"]+",\s*"params":\s*\{[^}]*\}\}', "", cleaned)
        # Clean up extra whitespace
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def display(self, response: FormattedResponse) -> None:
        """
        Display a formatted response in the CLI.

        Args:
            response: FormattedResponse to display
        """
        # Display main response text
        if response.text:
            console.print()
            console.print(Markdown(response.text))

        # Display action result if present
        if response.action_result:
            self._display_action_result(response.action_result)

        # Display citations if present
        if response.citations:
            self._display_citations(response.citations)

        console.print()

    def _display_action_result(self, result: ActionResult) -> None:
        """Display an action result."""
        if result.success:
            style = "green"
            icon = "✓"
        else:
            style = "red"
            icon = "✗"

        console.print()
        console.print(Panel(
            f"[{style}]{icon} {result.message}[/{style}]",
            title="Action Result",
            border_style=style,
        ))

        # Display data if it's a list or summary
        if result.data and isinstance(result.data, list) and len(result.data) > 0:
            self._display_data_table(result.data)

    def _display_data_table(self, data: list) -> None:
        """Display data as a table."""
        if not data:
            return

        # Get keys from first item
        first = data[0]
        if isinstance(first, dict):
            keys = list(first.keys())[:5]  # Limit columns

            table = Table(show_header=True, header_style="bold cyan")
            for key in keys:
                table.add_column(key.replace("_", " ").title())

            for item in data[:10]:  # Limit rows
                row = [str(item.get(k, ""))[:30] for k in keys]
                table.add_row(*row)

            console.print(table)

    def _display_citations(self, citations: list[dict]) -> None:
        """Display RAG citations."""
        if not citations:
            return

        console.print()
        console.print("[dim]Sources:[/dim]")
        for i, citation in enumerate(citations[:3], 1):
            title = citation.get("title", "Unknown")
            url = citation.get("url", "")
            console.print(f"  [dim]{i}. {title}[/dim]")
            if url:
                console.print(f"     [link={url}]{url}[/link]")

    def format_error(self, error: str) -> None:
        """Display an error message."""
        console.print()
        console.print(Panel(
            f"[red]{error}[/red]",
            title="Error",
            border_style="red",
        ))

    def format_welcome(self) -> None:
        """Display welcome message."""
        console.print()
        console.print(Panel(
            "[bold cyan]Hevo Assistant[/bold cyan]\n\n"
            "I can help you manage your Hevo pipelines, destinations, models, and workflows.\n\n"
            "[dim]Examples:[/dim]\n"
            "• List my pipelines\n"
            "• Check the status of my Salesforce pipeline\n"
            "• Pause the MySQL pipeline\n"
            "• How do I create a new destination?\n\n"
            "[dim]Type 'exit' or 'quit' to end the chat.[/dim]",
            title="Welcome",
            border_style="cyan",
        ))

    def format_thinking(self) -> None:
        """Display thinking indicator."""
        console.print("[dim]Thinking...[/dim]", end="\r")

    def clear_thinking(self) -> None:
        """Clear thinking indicator."""
        console.print(" " * 20, end="\r")


def get_response_formatter() -> ResponseFormatter:
    """Get a ResponseFormatter instance."""
    return ResponseFormatter()
