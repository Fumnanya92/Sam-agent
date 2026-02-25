# Sam Agent - AI Voice Assistant

Sam is an intelligent voice-activated assistant that can perform various tasks including WhatsApp automation, web searches, weather reports, and more.

## Features

- **Voice Interaction**: Speak naturally with Sam using speech-to-text
- **WhatsApp Automation**: 
  - Read unread messages
  - Draft AI-powered replies
  - Open specific chats
  - Manual send workflow (safe, no auto-send)
- **System Monitoring**:
  - Check CPU, RAM, and disk usage
  - Monitor battery status
  - Verify internet connectivity
  - Identify top processes
  - **Kill heavy processes on command**
  - **Background performance tracking**
  - **Autonomous system management**
  - **Auto-intervention when overloaded**
- **Screen Vision Mode**:
  - **Sam can see your screen** using AI vision
  - Analyze errors and interface elements
  - Voice-activated screen capture and analysis
  - Powered by OpenAI GPT-4o-mini vision model
  - Safe observation mode (no automation)
- **Web Search**: Search the web using voice commands
- **Weather Reports**: Get current weather information
- **Task Management**: Daily planner and morning briefing
- **Extensible**: Easy to add new actions and capabilities

## Quick Start

### Prerequisites
- Python 3.13+
- Chrome browser
- OpenAI API key (for AI reply generation)
- SerpAPI key (for web searches)

### Installation

1. Clone the repository:
```bash
cd c:\Users\DELL.COM\Desktop\Darey\Sam-Agent
```

2. Install dependencies:
```bash
pip install -r REQUIREMENTS.txt
```

3. Configure API keys:
```bash
cp config/api_keys.json.example config/api_keys.json
# Edit config/api_keys.json with your actual API keys
```

4. Set up Chrome remote debugging:
```bash
scripts\start_chrome_debug.bat
```

### Running Sam

```bash
python main.py
```

Or use the UI interface:
```bash
python ui.py
```

## WhatsApp Integration

Sam uses Chrome remote debugging to interact with WhatsApp Web safely:

### First Time Setup
1. Run `scripts\start_chrome_debug.bat` to launch Chrome with debugging enabled
2. Navigate to WhatsApp Web and scan QR code
3. Start Sam: `python main.py`
4. Say "Check my messages"

### Voice Commands

- **"Check my messages"** - Sam reads your unread WhatsApp messages
- **"Reply to [name]"** - Draft an AI reply to a specific contact
- **"Send it"** - Copy draft to clipboard for manual paste
- **"Cancel"** - Cancel current draft
- **"Edit"** - Edit current draft
- **"I'm ready"** - Continue after QR code scan

### Draft & Confirm Workflow

Sam uses a safe draft-and-confirm workflow:
1. Sam analyzes the message and drafts a reply using AI
2. Sam reads the draft aloud and asks for confirmation
3. You say "send it" and Sam copies it to your clipboard
4. You manually paste and send in WhatsApp (Ctrl+V, Enter)

**Why no auto-send?** Safety first! Manual confirmation prevents accidental sends.

## Project Structure

```
Sam-Agent/
├── actions/              # Action modules (send_message, web_search, weather, etc.)
├── assistant/            # Assistant modules (message_reader, daily_planner, etc.)
├── automation/           # WhatsApp automation core
│   ├── chrome_debug.py       # Chrome remote debugging interface
│   ├── whatsapp_dom.py       # WhatsApp DOM manipulation
│   ├── whatsapp_assistant.py # High-level WhatsApp actions
│   ├── whatsapp_ai_engine.py # AI reply engine
│   ├── reply_drafter.py      # AI reply generation
│   └── reply_controller.py   # Draft management & clipboard
├── backup/               # Backup files
├── config/               # Configuration files
│   ├── api_keys.json        # API keys (create from .example)
│   └── api_keys.json.example
├── core/                 # Core modules
│   └── prompt.txt           # Intent detection rules
├── debug/                # Debug files (gitignored)
│   ├── json/                # JSON debug output
│   ├── html/                # HTML test files
│   └── old_tests/           # Archived test files
├── docs/                 # Documentation
│   ├── README.md            # Documentation index
│   ├── SAM_MASTER_ARCHITECTURE_PLAN.md
│   ├── WHATSAPP_AI_COMPLETE.md
│   └── ... (all .md files)
├── log/                  # Logging module
├── memory/               # Memory management
│   ├── memory_manager.py
│   └── memory.json
├── scripts/              # Utility scripts
│   ├── start_chrome_debug.bat   # Launch Chrome with debugging
│   ├── cleanup_repo.py          # Repository organization
│   └── cleanup_tests.py         # Test organization
├── static/               # Static files
├── system/               # System monitoring
│   ├── __init__.py
│   ├── system_monitor.py        # CPU, RAM, disk, battery monitoring
│   ├── process_control.py       # Process detection and termination
│   ├── system_watcher.py        # Background monitoring and auto-intervention
│   └── screen_vision.py         # Screen capture and AI vision analysis
├── tests/                # Test files
│   ├── test_sam_whatsapp_complete.py  # Integration test
│   ├── test_message_content.py        # Message extraction test
│   ├── test_draft_system.py           # Draft system test
│   ├── test_sam_status.py             # Status check
│   └── archive/                       # Old diagnostic tests
├── main.py               # Main entry point
├── ui.py                 # UI interface
├── llm.py                # LLM integration
├── tts.py                # Text-to-speech
├── conversation_state.py # Conversation state management
├── shared_state.py       # Shared state
├── websocket_server.py   # WebSocket server for speech
├── speech_to_text_websocket.py  # Speech-to-text
├── README.md             # This file
└── REQUIREMENTS.txt      # Python dependencies
```

## Architecture

### Core Components

1. **Speech Interface**: WebSocket-based speech-to-text using browser's native API
2. **Intent Detection**: LLM-based intent classification using OpenAI
3. **Action Routing**: Main loop routes intents to appropriate action handlers
4. **WhatsApp Automation**: Chrome DevTools Protocol for safe DOM access
5. **Memory System**: Persistent memory for context and user preferences
6. **TTS Engine**: Edge TTS for natural voice output

### WhatsApp System Architecture

```
Voice Input → Intent Detection → WhatsApp Assistant
                                        ↓
                              Chrome Debug Controller
                                        ↓
                          ┌─────────────┴─────────────┐
                          │                           │
                    WhatsApp DOM              AI Reply Engine
                          │                           │
                   (Read Messages)              Reply Drafter
                          │                           │
                          └─────────────┬─────────────┘
                                        ↓
                                Reply Controller
                                        ↓
                                   Clipboard
                                        ↓
                                Manual Paste/Send
```

## Testing

Run tests to verify system functionality:

```bash
# All tests
python -m pytest tests/

# Specific tests
python tests/test_sam_status.py              # Quick status check
python tests/test_message_content.py         # Message extraction
python tests/test_draft_system.py            # Draft & clipboard
python tests/test_sam_whatsapp_complete.py   # Full integration
```

## Development

### Adding New Actions

1. Create action file in `actions/` directory
2. Implement action function
3. Add intent rule to `core/prompt.txt`
4. Add intent handler to `main.py`

### Debug Mode

Chrome debugging output and diagnostic files are stored in `debug/`:
- `debug/json/` - JSON debug output
- `debug/html/` - HTML test files
- `debug/old_tests/` - Archived diagnostic scripts

## Documentation

See the `docs/` directory for detailed documentation:
- [Master Architecture Plan](docs/SAM_MASTER_ARCHITECTURE_PLAN.md)
- [WhatsApp AI Complete Guide](docs/WHATSAPP_AI_COMPLETE.md)
- [Screen Vision Mode Guide](docs/SCREEN_VISION_MODE.md)
- [Advanced System Mode](docs/ADVANCED_SYSTEM_MODE.md)
- [Implementation Guide](docs/IMPLEMENTATION_GUIDE.md)
- [Setup Instructions](docs/SETUP_LAPTOP.md)

## Dependencies

Key dependencies (see `REQUIREMENTS.txt` for full list):
- `openai` - AI reply generation + vision analysis
- `edge-tts` - Text-to-speech
- `websockets` - Speech interface
- `psutil` - Process management
- `mss` - Screen capture for vision mode
- `Pillow` - Image processing
- `pyperclip` - Clipboard operations
- `rapidfuzz` - Fuzzy name matching
- `google-search-results` - Web search (SerpAPI)

## Safety & Privacy

- **No Auto-Send**: All messages require manual confirmation
- **Local Processing**: Message analysis happens locally
- **API Usage**: Only OpenAI for reply drafting (encrypted)
- **No Storage**: Messages are not stored permanently
- **Manual Control**: You always have final say on what gets sent

## License

Private project - All rights reserved

## Support

For issues or questions, check:
1. `docs/` directory for detailed documentation
2. `tests/` for working examples
3. Debug logs in `debug/` directory

---

**Built with ♥ by Sam's Team**
