"""
Hevo Assistant CLI - Main entry point.

Commands:
- hevo setup: Interactive setup wizard
- hevo config show: Show current configuration
- hevo docs update: Crawl and update documentation
- hevo docs status: Show documentation status
- hevo chat: Start interactive chat
- hevo ask "query": One-shot question
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from hevo_assistant import __version__
from hevo_assistant.config import Config, get_config, save_config

console = Console()


def process_query(query: str, cfg: Config, conversation_history: list = None) -> str:
    """
    Process a user query through the multi-agent pipeline.

    Uses two-agent architecture:
    - Coordinator Agent: Understands intent, gathers parameters
    - Executor Agent: Executes actions via Hevo API

    Falls back to legacy single-agent pipeline if multi-agent is disabled.

    Args:
        query: User's natural language query
        cfg: Application configuration
        conversation_history: Previous messages for context

    Returns:
        Response message to display
    """
    # Check if multi-agent mode is enabled
    if cfg.agents.enabled:
        return _process_query_multiagent(query, cfg, conversation_history)
    else:
        return _process_query_legacy(query, cfg, conversation_history)


def _process_query_multiagent(query: str, cfg: Config, conversation_history: list = None) -> str:
    """
    Process query using multi-agent architecture.

    Flow: User → Coordinator → Executor → Response
    """
    from hevo_assistant.agents import AgentOrchestrator
    from hevo_assistant.rag import get_retriever
    from hevo_assistant.agent.responses import FormattedResponse, get_response_formatter

    formatter = get_response_formatter()

    # Get RAG context
    rag_context = ""
    try:
        retriever = get_retriever()
        context_docs = retriever.retrieve(query, n_results=5)
        rag_context = retriever.format_context(context_docs)
    except Exception:
        pass  # Continue without RAG context

    # Process through orchestrator
    try:
        orchestrator = AgentOrchestrator()
        response = orchestrator.process(
            user_message=query,
            conversation_history=conversation_history,
            rag_context=rag_context,
        )

        # Display response
        formatted = FormattedResponse(text=response)
        formatter.display(formatted)

        return response

    except Exception as e:
        error_msg = f"Error processing query: {str(e)}"
        formatter.format_error(error_msg)
        return error_msg


def _process_query_legacy(query: str, cfg: Config, conversation_history: list = None) -> str:
    """
    Legacy single-agent processing (fallback).

    Includes:
    - Capability discovery ("what can I do?")
    - Unsupported request handling
    - Prerequisites validation
    - Follow-up suggestions
    """
    from hevo_assistant.agent import (
        get_action_executor,
        get_intent_parser,
        get_response_formatter,
        get_followup_suggester,
        check_unsupported_query,
        IntentType,
    )
    from hevo_assistant.domain.capabilities import format_capabilities_list
    from hevo_assistant.llm import get_llm
    from hevo_assistant.rag import get_retriever

    intent_parser = get_intent_parser()
    action_executor = get_action_executor()
    formatter = get_response_formatter()
    followup_suggester = get_followup_suggester()

    # Parse intent first
    intent = intent_parser.parse(query)

    # Handle capability discovery directly
    if intent.intent_type == IntentType.CAPABILITIES:
        capabilities_text = format_capabilities_list()
        from hevo_assistant.agent.responses import FormattedResponse
        response = FormattedResponse(text=capabilities_text)
        formatter.display(response)
        return capabilities_text

    # Check for unsupported requests
    unsupported_msg = check_unsupported_query(query)
    if unsupported_msg:
        from hevo_assistant.agent.responses import FormattedResponse
        response = FormattedResponse(text=f"I'm sorry, {unsupported_msg}")
        formatter.display(response)
        return unsupported_msg

    # Get intent hint for LLM
    intent_hint = intent_parser.to_action_hint(intent)

    # Retrieve relevant context from RAG
    try:
        retriever = get_retriever()
        context_docs = retriever.retrieve(query, n_results=5)
        context = retriever.format_context(context_docs)
        citations = [{"title": d.get("title", ""), "url": d.get("url", "")} for d in context_docs]
    except Exception:
        context = ""
        citations = []

    # Build the prompt with context
    system_parts = []
    if context:
        system_parts.append(f"Use this documentation context to help answer:\n\n{context}")
    if intent_hint:
        system_parts.append(f"User intent hint: {intent_hint}")

    additional_context = "\n\n".join(system_parts) if system_parts else None

    # Get LLM response
    try:
        llm = get_llm()
        llm_response = llm.chat(
            query,
            conversation_history=conversation_history or [],
            additional_context=additional_context,
        )
    except Exception as e:
        formatter.format_error(f"LLM error: {str(e)}")
        return None

    # Check if LLM requested an action
    action_result = action_executor.execute_from_response(llm_response)

    # Get follow-up suggestions if action was executed
    followup_text = ""
    if action_result:
        action = action_executor.parse_action(llm_response)
        if action:
            action_name = action.get("action", "")
            followups = followup_suggester.get_followups(
                action_name,
                action_result.success,
                action_result.data
            )
            if followups:
                followup_text = followup_suggester.format_followups(followups)

    # Format and display response
    response_text = llm_response
    if followup_text:
        response_text = llm_response + "\n" + followup_text

    response = formatter.format_chat_response(
        llm_response=response_text,
        action_result=action_result,
        citations=citations,
    )
    formatter.display(response)

    return llm_response


@click.group()
@click.version_option(version=__version__, prog_name="hevo")
def main():
    """Hevo Assistant - Chat-to-Action CLI for Hevo Data pipelines."""
    pass


@main.command()
def setup():
    """Interactive setup wizard for Hevo Assistant."""
    console.print(
        Panel.fit(
            "[bold blue]Hevo Assistant Setup[/bold blue]\n"
            "Configure your Hevo API credentials and LLM provider.",
            border_style="blue",
        )
    )

    config = get_config()

    # Hevo credentials
    console.print("\n[bold]Step 1: Hevo API Credentials[/bold]")
    console.print(
        "Get your API key and secret from: "
        "[link=https://app.hevodata.com/settings/api-keys]"
        "Hevo Dashboard > Settings > API Keys[/link]\n"
    )

    api_key = Prompt.ask(
        "Hevo API Key",
        default=config.hevo.api_key.get_secret_value() or None,
        password=True,
    )
    api_secret = Prompt.ask(
        "Hevo API Secret",
        default=config.hevo.api_secret.get_secret_value() or None,
        password=True,
    )
    region = Prompt.ask(
        "Hevo Region",
        choices=["us", "us2", "eu", "in", "asia", "au"],
        default=config.hevo.region,
    )

    # LLM configuration
    console.print("\n[bold]Step 2: LLM Provider[/bold]")
    provider = Prompt.ask(
        "LLM Provider",
        choices=["openai", "anthropic", "ollama"],
        default=config.llm.provider,
    )

    llm_api_key = ""
    if provider != "ollama":
        llm_api_key = Prompt.ask(
            f"{provider.capitalize()} API Key",
            default=config.llm.api_key.get_secret_value() or None,
            password=True,
        )

    # Model selection
    default_models = {
        "openai": "gpt-4",
        "anthropic": "claude-3-sonnet-20240229",
        "ollama": "llama3",
    }
    model = Prompt.ask(
        "Model name",
        default=default_models.get(provider, config.llm.model),
    )

    # Pinecone configuration (for RAG)
    console.print("\n[bold]Step 3: Pinecone (RAG Backend)[/bold]")
    console.print(
        "Pinecone provides documentation search. "
        "Get a free API key from: [link=https://pinecone.io]pinecone.io[/link]\n"
    )

    pinecone_api_key = Prompt.ask(
        "Pinecone API Key",
        default=config.rag.pinecone_api_key.get_secret_value() or None,
        password=True,
    )

    # Create new config
    from pydantic import SecretStr

    new_config = Config(
        hevo=config.hevo.model_copy(
            update={
                "api_key": SecretStr(api_key),
                "api_secret": SecretStr(api_secret),
                "region": region,
            }
        ),
        llm=config.llm.model_copy(
            update={
                "provider": provider,
                "api_key": SecretStr(llm_api_key),
                "model": model,
            }
        ),
        rag=config.rag.model_copy(
            update={
                "backend": "pinecone",
                "pinecone_api_key": SecretStr(pinecone_api_key) if pinecone_api_key else SecretStr(""),
            }
        ),
    )

    # Save configuration
    save_config(new_config)

    console.print("\n[green]Configuration saved![/green]")
    console.print(f"Config file: {Config.get_config_path()}")

    # Next steps
    console.print("\n[bold]Next steps:[/bold]")
    console.print("Run [cyan]hevo chat[/cyan] to start chatting")


@main.group()
def config():
    """Manage configuration."""
    pass


@config.command("show")
def config_show():
    """Show current configuration."""
    cfg = get_config()

    table = Table(title="Hevo Assistant Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Hevo settings
    table.add_row("Hevo API Key", "***" if cfg.hevo.api_key.get_secret_value() else "[red]Not set[/red]")
    table.add_row("Hevo API Secret", "***" if cfg.hevo.api_secret.get_secret_value() else "[red]Not set[/red]")
    table.add_row("Hevo Region", cfg.hevo.region)
    table.add_row("Hevo Base URL", cfg.hevo.base_url)
    table.add_row("", "")

    # LLM settings
    table.add_row("LLM Provider", cfg.llm.provider)
    table.add_row("LLM API Key", "***" if cfg.llm.api_key.get_secret_value() else "[red]Not set[/red]" if cfg.llm.provider != "ollama" else "N/A")
    table.add_row("LLM Model", cfg.llm.model)
    table.add_row("", "")

    # RAG settings
    table.add_row("RAG Backend", cfg.rag.backend)
    if cfg.rag.backend == "pinecone":
        table.add_row("Pinecone API Key", "***" if cfg.rag.pinecone_api_key.get_secret_value() else "[red]Not set[/red]")
        table.add_row("Pinecone Index", cfg.rag.pinecone_index)
    else:
        table.add_row("Vector DB Path", cfg.rag.db_path)
        table.add_row("Embedding Model", cfg.rag.embedding_model)
    table.add_row("Last Updated", str(cfg.rag.last_updated) if cfg.rag.last_updated else "[yellow]Never[/yellow]")
    table.add_row("", "")

    # Agent settings
    table.add_row("Multi-Agent Mode", "[green]Enabled[/green]" if cfg.agents.enabled else "[yellow]Disabled[/yellow]")
    table.add_row("Coordinator Model", cfg.agents.coordinator_model)
    table.add_row("Executor Model", cfg.agents.executor_model)

    console.print(table)


@main.group()
def docs():
    """Manage documentation index."""
    pass


@docs.command("update")
def docs_update():
    """Crawl and update the documentation index."""
    from datetime import datetime
    from hevo_assistant.rag.vectorstore import update_documentation

    console.print(Panel.fit(
        "[bold blue]Updating Documentation Index[/bold blue]\n"
        "This will crawl Hevo documentation and update the vector database.",
        border_style="blue",
    ))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Crawling and indexing documentation...", total=None)

            stats = update_documentation()

            progress.update(task, completed=True)

        # Update config with last updated time
        cfg = get_config()
        cfg.rag.last_updated = datetime.now()
        save_config(cfg)

        console.print("\n[green]Documentation updated successfully![/green]")
        console.print(f"  Docs indexed: {stats.get('docs_chunks', 0)} chunks")
        console.print(f"  API indexed: {stats.get('api_chunks', 0)} chunks")

    except Exception as e:
        console.print(f"\n[red]Error updating documentation: {str(e)}[/red]")


@docs.command("status")
def docs_status():
    """Show documentation index status."""
    cfg = get_config()

    try:
        from hevo_assistant.rag import get_vectorstore
        store = get_vectorstore()
        stats = store.get_stats()

        table = Table(title="Documentation Index Status")
        table.add_column("Collection", style="cyan")
        table.add_column("Documents", style="green")

        for collection, count in stats.items():
            table.add_row(collection, str(count))

        console.print(table)

        if cfg.rag.last_updated:
            console.print(f"\nLast updated: {cfg.rag.last_updated}")
        else:
            console.print("\n[yellow]Documentation has never been indexed.[/yellow]")
            console.print("Run [cyan]hevo docs update[/cyan] to index documentation.")

    except Exception as e:
        console.print(f"[red]Error getting status: {str(e)}[/red]")
        console.print("\n[yellow]Run [cyan]hevo docs update[/cyan] to initialize the index.[/yellow]")


@main.command()
def chat():
    """Start interactive chat session."""
    from hevo_assistant.agent import get_response_formatter

    cfg = get_config()
    is_ready, missing = cfg.is_ready()

    if not is_ready:
        console.print("[red]Configuration incomplete:[/red]")
        for item in missing:
            console.print(f"  - {item}")
        console.print("\nRun [cyan]hevo setup[/cyan] to configure.")
        return

    formatter = get_response_formatter()
    formatter.format_welcome()

    # Track conversation history
    conversation_history = []

    while True:
        try:
            console.print()
            user_input = Prompt.ask("[bold blue]You[/bold blue]")

            if not user_input.strip():
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            # Show thinking indicator
            with console.status("[dim]Thinking...[/dim]"):
                response = process_query(user_input, cfg, conversation_history)

            # Add to conversation history
            if response:
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response})

                # Keep history manageable (last 10 exchanges)
                if len(conversation_history) > 20:
                    conversation_history = conversation_history[-20:]

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {str(e)}[/red]")


@main.command()
@click.argument("query")
def ask(query: str):
    """Ask a one-shot question."""
    cfg = get_config()
    is_ready, missing = cfg.is_ready()

    if not is_ready:
        console.print("[red]Configuration incomplete:[/red]")
        for item in missing:
            console.print(f"  - {item}")
        console.print("\nRun [cyan]hevo setup[/cyan] to configure.")
        return

    console.print(f"\n[bold blue]Question:[/bold blue] {query}")

    with console.status("[dim]Thinking...[/dim]"):
        process_query(query, cfg)


if __name__ == "__main__":
    main()
