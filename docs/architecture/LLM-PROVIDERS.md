---
priority: reference
topics: [census, batch, findagrave, testing, ui]
---

# LLM Providers Architecture

RMCitecraft now supports multiple LLM providers for photo classification and census transcription tasks, with a clean abstraction layer that allows easy switching between providers.

## Supported Providers

### 1. LLM (Datasette)
- **Best for**: Local development, conversation history, CLI integration
- **Installation**: `pip install rmcitecraft[llm]`
- **Configuration**: Configure API keys using `llm keys set openai`
- **Pros**: Local tool, conversation history, shell integration
- **Cons**: Requires separate API key configuration, limited vision support

### 2. OpenRouter
- **Best for**: Production, multi-model support, automatic fallbacks
- **Installation**: `pip install rmcitecraft[openrouter]`
- **Configuration**: Set `OPENROUTER_API_KEY` in `.env`
- **Pros**: Access to many models, cost routing, built-in vision support
- **Cons**: Requires internet connection, API costs

## Installation

```bash
# Install with both providers
pip install rmcitecraft[all-llm]

# Or install individually
pip install rmcitecraft[llm]        # LLM Datasette only
pip install rmcitecraft[openrouter] # OpenRouter only
```

## Configuration

Update your `.env` file:

```env
# Choose default provider
DEFAULT_LLM_PROVIDER=openrouter  # or "llm"

# OpenRouter configuration
OPENROUTER_API_KEY=sk-or-xxxxx
OPENROUTER_SITE_URL=https://rmcitecraft.app
OPENROUTER_APP_NAME=RMCitecraft

# Task-specific models
PHOTO_CLASSIFICATION_MODEL=anthropic/claude-3-haiku
CENSUS_TRANSCRIPTION_MODEL=openai/gpt-4-vision-preview
```

For LLM Datasette, configure API keys using the CLI:
```bash
llm keys set openai sk-xxxxx
llm keys set anthropic sk-ant-xxxxx
```

## Usage Examples

### Photo Classification

```python
from rmcitecraft.services.photo_classifier import PhotoClassifier

# Create classifier (uses config from environment)
classifier = PhotoClassifier()

# Classify a Find a Grave photo
result = classifier.classify_photo("path/to/photo.jpg")
print(f"Category: {result.category}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Reasoning: {result.reasoning}")

# Classify multiple photos
results = classifier.classify_batch(["photo1.jpg", "photo2.jpg"])
```

### Census Transcription

```python
from rmcitecraft.services.census_transcriber import CensusTranscriber

# Create transcriber
transcriber = CensusTranscriber()

# Transcribe 1900 census image
result = transcriber.transcribe_census("census_1900.jpg", 1900)
print(f"Extracted data: {result.data}")
print(f"Confidence: {result.confidence:.2%}")

# Extract family group
family = transcriber.extract_family_group(result.data, "John Smith")
```

### Direct Provider Usage

```python
from rmcitecraft.llm import create_provider

# Create provider from config
config = {
    "provider": "openrouter",
    "openrouter_api_key": "your-key"
}
provider = create_provider(config)

# Use provider directly
response = provider.complete("What is genealogy?")
print(response.text)

# Stream responses
for chunk in provider.stream_complete("Tell me about census records"):
    print(chunk, end="", flush=True)

# Vision tasks
response = provider.complete_with_image(
    "Describe this headstone",
    "grave_photo.jpg",
    model="anthropic/claude-3-opus"
)
```

## Provider Capabilities

| Feature | LLM Datasette | OpenRouter |
|---------|---------------|------------|
| Text Completion | ✅ | ✅ |
| Streaming | ✅ | ✅ |
| Vision/Images | ⚠️ Limited | ✅ |
| Function Calling | ⚠️ Model-dependent | ✅ |
| JSON Mode | ⚠️ Model-dependent | ✅ |
| Cost Tracking | ❌ | ✅ |
| Local Models | ✅ (via plugins) | ❌ |
| Rate Limiting | Manual | Automatic |

## Available Models

### OpenRouter Models

**Vision Models** (for photo classification and census transcription):
- `anthropic/claude-3-opus` - Best quality, highest cost
- `anthropic/claude-3-sonnet` - Good balance
- `anthropic/claude-3-haiku` - Fast and cheap
- `openai/gpt-4-vision-preview` - OpenAI's vision model
- `google/gemini-pro-vision` - Google's vision model

**Text Models** (for general tasks):
- `openai/gpt-4-turbo` - Latest GPT-4
- `openai/gpt-3.5-turbo` - Fast and cheap
- `meta-llama/llama-3-70b-instruct` - Open source alternative

### LLM Datasette Models

Available models depend on installed plugins:
- OpenAI models (via `llm-openai` plugin)
- Anthropic models (via `llm-claude` plugin)
- Local models (via `llm-gpt4all` or `llm-ollama` plugins)

Check available models:
```bash
llm models list
```

## Cost Optimization

### OpenRouter Cost Management

OpenRouter automatically routes to the cheapest available model that meets your requirements. You can also specify preferred models:

```python
# Use cheaper model for simple classification
classifier = PhotoClassifier(model="anthropic/claude-3-haiku")

# Use powerful model for complex transcription
transcriber = CensusTranscriber(model="openai/gpt-4-vision-preview")
```

### Batch Processing

Process multiple items to amortize API overhead:

```python
# Process all photos at once
photos = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
results = classifier.classify_batch(photos)

# Progress callback for UI
def on_progress(current, total, path):
    print(f"Processing {current}/{total}: {path}")

results = classifier.classify_batch(photos, progress_callback=on_progress)
```

## Error Handling

The abstraction layer provides consistent error handling:

```python
from rmcitecraft.llm import (
    ModelNotFoundError,
    RateLimitError,
    ConfigurationError,
    LLMError
)

try:
    result = classifier.classify_photo("photo.jpg")
except ModelNotFoundError as e:
    print(f"Model not available: {e}")
except RateLimitError as e:
    print(f"Rate limit hit, please wait: {e}")
except ConfigurationError as e:
    print(f"Provider not configured: {e}")
except LLMError as e:
    print(f"General LLM error: {e}")
```

## Testing

Run tests for LLM providers:

```bash
# Run all LLM tests
pytest tests/test_llm_providers.py -v

# Test specific provider
pytest tests/test_llm_providers.py::TestOpenRouterProvider -v

# Test services
pytest tests/test_llm_providers.py::TestPhotoClassifier -v
pytest tests/test_llm_providers.py::TestCensusTranscriber -v
```

## Extending the System

### Adding New Providers

1. Create provider class inheriting from `LLMProvider`
2. Implement required methods
3. Update factory in `llm/factory.py`
4. Add configuration support

### Adding New Tasks

1. Use high-level methods on `LLMProvider`:
   - `classify_image()` for categorization
   - `extract_structured_data()` for data extraction
   - `transcribe_census_image()` for census-specific tasks

2. Or create new service classes like `PhotoClassifier` and `CensusTranscriber`

## Troubleshooting

### LLM Datasette Issues

```bash
# Check if models are available
llm models list

# Test a model
echo "Hello" | llm -m gpt-3.5-turbo

# Check API keys
llm keys
```

### OpenRouter Issues

```bash
# Test API key
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"

# Check rate limits in response headers
# X-RateLimit-Remaining
# X-RateLimit-Reset
```

### Vision Not Working

- Ensure you're using a vision-capable model
- Check image file exists and is readable
- For LLM Datasette, vision support is limited
- For OpenRouter, use models ending in `-vision`

## Future Enhancements

Planned improvements:
- Ollama support for fully local operation
- Batch API support for cost savings
- Caching layer for repeated queries
- Fine-tuned models for genealogy tasks
- Auto-retry with exponential backoff
- Cost tracking and budgets