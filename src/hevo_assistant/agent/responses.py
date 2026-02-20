"""
Response formatting for chat output.

Formats LLM responses and action results for display.
"""

from dataclasses import dataclass
from typing import Any, Optional, List, Dict

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from hevo_assistant.agent.actions import ActionResult


console = Console()


class ResponseSummarizer:
    """
    Summarizes API responses in human-friendly format.

    Transforms raw data into readable summaries with tables and bullet points.
    """

    def summarize(self, action_name: str, data: Any) -> str:
        """
        Summarize API response data based on action type.

        Args:
            action_name: Name of the action that produced this data
            data: Raw data from the action

        Returns:
            Human-friendly summary string
        """
        summarizers = {
            "list_pipelines": self._summarize_pipelines,
            "get_pipeline": self._summarize_pipeline_detail,
            "list_destinations": self._summarize_destinations,
            "list_objects": self._summarize_objects,
            "list_models": self._summarize_models,
            "list_workflows": self._summarize_workflows,
        }

        summarizer = summarizers.get(action_name)
        if summarizer:
            return summarizer(data)

        return self._default_summary(data)

    def _summarize_pipelines(self, pipelines: list) -> str:
        """Summarize pipeline list."""
        if not pipelines:
            return "You don't have any pipelines yet."

        active = sum(1 for p in pipelines if isinstance(p, dict) and p.get("status") == "ACTIVE")
        paused = sum(1 for p in pipelines if isinstance(p, dict) and p.get("status") == "PAUSED")
        total = len(pipelines)

        lines = [f"You have **{total} pipelines**: {active} active, {paused} paused\n"]
        lines.append("| Pipeline | Source | Status |")
        lines.append("|----------|--------|--------|")

        for p in pipelines[:10]:
            if isinstance(p, dict):
                name = p.get("name", "Unnamed")[:30]
                source = p.get("source", {}).get("type", "Unknown") if isinstance(p.get("source"), dict) else "Unknown"
                status = p.get("status", "Unknown")
                emoji = {"ACTIVE": "🟢", "PAUSED": "🟡", "DRAFT": "⚪"}.get(status, "🔴")
                lines.append(f"| {name} | {source} | {emoji} {status} |")

        if len(pipelines) > 10:
            lines.append(f"\n...and {len(pipelines) - 10} more.")

        return "\n".join(lines)

    def _summarize_pipeline_detail(self, pipeline) -> str:
        """Summarize a single pipeline's details."""
        if isinstance(pipeline, dict):
            data = pipeline
        elif hasattr(pipeline, "__dict__"):
            data = {
                "name": getattr(pipeline, "name", "Unknown"),
                "status": getattr(pipeline, "status", "Unknown"),
                "source_type": getattr(pipeline, "source_type", "Unknown"),
                "objects_count": getattr(pipeline, "objects_count", 0),
                "active_objects": getattr(pipeline, "active_objects", 0),
                "failed_objects": getattr(pipeline, "failed_objects", 0),
            }
        else:
            return str(pipeline)

        status = data.get("status", "Unknown")
        emoji = {"ACTIVE": "🟢", "PAUSED": "🟡", "DRAFT": "⚪"}.get(status, "🔴")

        lines = [
            f"{emoji} **{data.get('name', 'Unknown')}**",
            "",
            f"- **Status:** {status}",
            f"- **Source:** {data.get('source_type', 'Unknown')}",
        ]

        objects_count = data.get("objects_count", 0)
        if objects_count:
            active = data.get("active_objects", 0)
            failed = data.get("failed_objects", 0)
            lines.append(f"- **Objects:** {objects_count} total, {active} active, {failed} failed")

        return "\n".join(lines)

    def _summarize_destinations(self, destinations: list) -> str:
        """Summarize destination list."""
        if not destinations:
            return "You don't have any destinations configured."

        # Group by type
        by_type: Dict[str, int] = {}
        for d in destinations:
            if hasattr(d, "type"):
                dtype = d.type
            elif isinstance(d, dict):
                dtype = d.get("type", "Unknown")
            else:
                dtype = "Unknown"
            by_type[dtype] = by_type.get(dtype, 0) + 1

        lines = [f"You have **{len(destinations)} destinations**:\n"]

        for dtype, count in sorted(by_type.items()):
            lines.append(f"- {dtype}: {count}")

        return "\n".join(lines)

    def _summarize_objects(self, objects: list) -> str:
        """Summarize objects list."""
        if not objects:
            return "No objects found in this pipeline."

        active = sum(1 for o in objects if isinstance(o, dict) and o.get("status") == "ACTIVE")
        failed = sum(1 for o in objects if isinstance(o, dict) and o.get("status") in ("FAILED", "PERMISSION_DENIED"))
        total = len(objects)

        lines = [f"**{total} objects**: {active} active"]
        if failed > 0:
            lines[0] += f", {failed} failed"

        lines.append("")
        lines.append("| Object | Status |")
        lines.append("|--------|--------|")

        for obj in objects[:15]:
            if isinstance(obj, dict):
                name = obj.get("name", "Unknown")[:30]
                status = obj.get("status", "Unknown")
                emoji = {"ACTIVE": "🟢", "PAUSED": "🟡", "SKIPPED": "⏭️", "FINISHED": "✅"}.get(status, "🔴")
                lines.append(f"| {name} | {emoji} {status} |")

        if len(objects) > 15:
            lines.append(f"\n...and {len(objects) - 15} more.")

        return "\n".join(lines)

    def _summarize_models(self, models: list) -> str:
        """Summarize models list."""
        if not models:
            return "You don't have any models yet."

        lines = [f"You have **{len(models)} models**:\n"]

        for m in models[:10]:
            if hasattr(m, "name"):
                name = m.name
                status = m.status
            elif isinstance(m, dict):
                name = m.get("name", "Unknown")
                status = m.get("status", "Unknown")
            else:
                continue

            emoji = "🟢" if status == "ACTIVE" else "🟡"
            lines.append(f"- {emoji} {name} ({status})")

        return "\n".join(lines)

    def _summarize_workflows(self, workflows: list) -> str:
        """Summarize workflows list."""
        if not workflows:
            return "You don't have any workflows yet."

        lines = [f"You have **{len(workflows)} workflows**:\n"]

        for w in workflows[:10]:
            if hasattr(w, "name"):
                name = w.name
                status = w.status
            elif isinstance(w, dict):
                name = w.get("name", "Unknown")
                status = w.get("status", "Unknown")
            else:
                continue

            emoji = "🟢" if status == "ACTIVE" else "🟡"
            lines.append(f"- {emoji} {name} ({status})")

        return "\n".join(lines)

    def _default_summary(self, data: Any) -> str:
        """Default summarization for unknown data types."""
        if isinstance(data, list):
            return f"Found {len(data)} items."
        elif isinstance(data, dict):
            return "Operation completed successfully."
        elif data is None:
            return "No data returned."
        return str(data)


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
            "I'm your Hevo Data Engineer assistant. I can help you manage your pipelines, "
            "destinations, models, and workflows.\n\n"
            "[dim]Examples:[/dim]\n"
            "• What can I do? [dim](see all available functions)[/dim]\n"
            "• List my pipelines\n"
            "• Check the status of my Salesforce pipeline\n"
            "• Pause the MySQL pipeline\n"
            "• Run my daily_summary model\n\n"
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


def get_response_summarizer() -> ResponseSummarizer:
    """Get a ResponseSummarizer instance."""
    return ResponseSummarizer()
