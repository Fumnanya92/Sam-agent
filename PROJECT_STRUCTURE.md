# Sam Agent - Project Structure

## Core Files
- `main.py` - Main Sam application entry point
- `speech_to_text_websocket.py` - Voice input interface (simplified)
- `websocket_server.py` - WebSocket server for speech communication
- `llm.py` - Language model interface
- `tts.py` - Text-to-speech functionality
- `ui.py` - User interface components
- `conversation_state.py` - State management
- `shared_state.py` - Shared state variables

## Configuration
- `config/` - API keys and configuration files
- `REQUIREMENTS.txt` - Python dependencies
- `.env` / `.env.example` - Environment variables

## Speech Interface
- `speech_client.html` - Full Web Speech API interface  
- `speech_client_compact.html` - Compact interface with auto-hide

## Data & Actions
- `actions/` - Available actions (weather, web search, etc.)
- `memory/` - Memory management and storage
- `core/` - Core prompt and configuration
- `log/` - Application logs
- `static/` - Static assets (images, etc.)

## Backup
- `backup/` - Old/unused files moved here for cleaner repository

## Voice Interface Notes
- Uses Web Speech API (requires browser)
- Browser window auto-hides/minimizes when possible
- WebSocket communication for real-time transcription
- Simplified interface removed native tkinter and pywebview dependencies