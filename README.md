# Jarvis Desktop Assistant

An always-on desktop assistant with voice I/O, persistent memory, and OS control capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Jarvis Desktop Assistant                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│  │ Voice I/O    │   │ Assistant    │   │ Memory       │    │
│  │ Service      │   │ Core         │   │ Service      │    │
│  │ (STT/TTS)    │◄──┤ (LLM)        │◄──┤ (Chroma/PG)  │    │
│  └──────────────┘   │              │   └──────────────┘    │
│                     │ + Tool      │                       │
│                     │   Router     │                       │
│                     └──────┬───────┘                       │
│                            │                               │
│                     ┌──────▼───────┐                       │
│                     │ OS Operator  │                       │
│                     │ (PyAutoGUI)  │                       │
│                     └──────────────┘                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Components

### Voice Service (`services/voice/`)
- **STT**: Whisper for speech-to-text
- **TTS**: pyttsx3 for text-to-speech
- Hotkey activation support

### Assistant Core (`services/assistant/`)
- LLM orchestration with tool calling
- Session state management
- Memory integration
- Safety/confirmation handling

### Memory Service (`services/memory/`)
- **Vector DB**: Chroma for semantic search
- **Structured DB**: SQLite/PostgreSQL for profiles and playbooks
- Three-layer memory model:
  - Profile (static preferences)
  - Playbooks (procedural workflows)
  - Episodes (past conversations)

### OS Operator (`services/os_operator/`)
- Mouse/keyboard control via PyAutoGUI
- Window management
- Application launching
- Screenshot capture

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python -m scripts.init_db --seed

# Configure settings (edit config/settings.toml)
```

## Configuration

Edit `config/settings.toml`:

```toml
[llm]
provider = "openai"  # openai, anthropic, ollama
model = "gpt-4"
api_key = "your-key-here"

[voice]
stt_model = "base"  # Whisper model size
hotkey = "ctrl+alt+j"

[memory]
db_type = "sqlite"  # sqlite or postgres
vector_db = "chroma"
```

## Running

```bash
# Start the API server
python -m core.main

# Or with uvicorn
uvicorn core.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Voice
- `POST /voice/transcript` - Transcribe audio
- `POST /voice/speak` - Synthesize speech

### Memory
- `POST /memory/search` - Search memory
- `POST /memory/update` - Add memory
- `GET /memory/profile` - Get user profile

### OS Operator
- `POST /os/execute_actions` - Execute OS actions

### Assistant
- `POST /assistant/query` - Process query
- `POST /session/create` - Create session

## Memory Distillation

Import past chats:

```bash
python -m scripts.distill_memory path/to/chat_export.json chatgpt
```

## Supported Actions

| Action | Description |
|--------|-------------|
| `move_mouse` | Move cursor to x,y |
| `click` | Click mouse button |
| `scroll` | Scroll wheel |
| `type_text` | Type text |
| `hotkey` | Keyboard shortcut |
| `open_app` | Launch application |
| `focus_app` | Focus window |
| `screenshot` | Capture screen |

## Development Phases

1. **Phase 1**: Skeleton (Voice + OS + Basic Core)
2. **Phase 2**: LLM integration + tool schema
3. **Phase 3**: Memory Service (Postgres + Chroma)
4. **Phase 4**: Memory distillation pipeline
5. **Phase 5**: App-specific adapters (Browser, VSCode)

## License

MIT
