# Hevo Assistant

A chat-to-action CLI tool for managing Hevo Data pipelines using natural language. Ask questions, check status, pause/resume pipelines, and more - all through conversation.

## Features

- **Natural Language Interface**: Interact with your Hevo pipelines using plain English
- **RAG-Powered Responses**: Get accurate answers based on Hevo documentation
- **Multiple LLM Providers**: Choose between OpenAI, Anthropic Claude, or local Ollama
- **Pipeline Management**: List, pause, resume, and run pipelines
- **Model & Workflow Support**: Manage dbt models and workflows
- **Secure Configuration**: Credentials stored locally in `~/.hevo/`

## Installation

```bash
# Clone the repository
git clone https://github.com/Legolasan/hevo-app.git
cd hevo-app

# Install in development mode
pip install -e .

# Or install directly
pip install .
```

## Quick Start

### 1. Setup Configuration

Run the interactive setup wizard:

```bash
hevo setup
```

You'll be prompted for:
- **Hevo API credentials**: Get from [Hevo Dashboard > Settings > API Keys](https://app.hevodata.com/settings/api-keys)
- **LLM provider**: Choose OpenAI, Anthropic, or Ollama
- **LLM API key**: Your provider's API key (not needed for Ollama)

### 2. Index Documentation

Crawl and index Hevo documentation for accurate responses:

```bash
hevo docs update
```

This will:
- Crawl docs.hevodata.com (public documentation)
- Crawl api-docs.hevodata.com (API reference)
- Generate embeddings and store in local vector database

### 3. Start Chatting

```bash
# Interactive chat mode
hevo chat

# Or ask a one-shot question
hevo ask "List my pipelines"
```

## Usage Examples

```bash
# Check pipeline status
hevo ask "What's the status of my Salesforce pipeline?"

# List all pipelines
hevo ask "Show me all my pipelines"

# Pause a pipeline
hevo ask "Pause the MySQL pipeline"

# Resume a pipeline
hevo ask "Resume the MySQL pipeline"

# Run a pipeline now
hevo ask "Run the Salesforce pipeline now"

# Ask about Hevo features
hevo ask "How do I create a new destination?"

# List models
hevo ask "What models do I have?"

# Run a model
hevo ask "Run my revenue model"
```

## Commands

| Command | Description |
|---------|-------------|
| `hevo setup` | Interactive setup wizard |
| `hevo config show` | Show current configuration |
| `hevo docs update` | Crawl and index documentation |
| `hevo docs status` | Show documentation index status |
| `hevo chat` | Start interactive chat session |
| `hevo ask "query"` | Ask a one-shot question |

## Configuration

Configuration is stored in `~/.hevo/config.json`:

```json
{
  "hevo": {
    "api_key": "your-api-key",
    "api_secret": "your-api-secret",
    "region": "us"
  },
  "llm": {
    "provider": "openai",
    "api_key": "sk-...",
    "model": "gpt-4"
  },
  "rag": {
    "db_path": "~/.hevo/vectordb",
    "embedding_model": "all-MiniLM-L6-v2"
  }
}
```

### Supported Regions

- `us` - United States (default)
- `eu` - Europe
- `in` - India
- `apac` - Asia Pacific

### Supported LLM Providers

| Provider | Models | Notes |
|----------|--------|-------|
| OpenAI | gpt-4, gpt-4-turbo, gpt-3.5-turbo | Recommended for best results |
| Anthropic | claude-3-opus, claude-3-sonnet | Great for detailed explanations |
| Ollama | llama3, mistral, etc. | Local, free, no API key needed |

## Available Actions

The assistant can execute these actions on your behalf:

### Pipeline Actions
- List all pipelines
- Get pipeline status
- Pause a pipeline
- Resume a pipeline
- Run a pipeline immediately

### Object Actions
- List objects in a pipeline
- Skip a failed object
- Restart an object

### Model Actions
- List all models
- Run a model

### Workflow Actions
- List all workflows
- Run a workflow

### Destination Actions
- List all destinations

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      hevo-assistant CLI                         │
├─────────────────────────────────────────────────────────────────┤
│  User Query ──► Intent Parser ──► RAG Context ──► LLM ──► Action│
│                      │                │              │          │
│                      ▼                ▼              ▼          │
│              ChromaDB Vector    Hevo Docs     Hevo API Client   │
│                 Store           Embeddings    (HTTP Requests)   │
└─────────────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.10+
- Hevo Data account with API access
- LLM API key (OpenAI, Anthropic) or local Ollama installation

## Troubleshooting

### "Configuration incomplete" error
Run `hevo setup` to configure your API credentials.

### "Documentation not indexed" warning
Run `hevo docs update` to index the Hevo documentation.

### API authentication errors
1. Verify your Hevo API key and secret are correct
2. Check that your API key has the required permissions
3. Ensure you've selected the correct region

### LLM errors
1. Verify your LLM API key is valid
2. For Ollama, ensure the service is running (`ollama serve`)
3. Check that the model name is correct

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please read the contributing guidelines first.
