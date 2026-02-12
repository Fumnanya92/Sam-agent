# Sam Agent - AI Voice Assistant

<p align="center">
  <img src="face.png" alt="Sam AI Assistant" width="200"/>
</p>

Sam is an AI voice assistant built with Python that combines real-time speech recognition, large language model processing, and text-to-speech capabilities to create a conversational AI experience. Sam can perform tasks including web searches, weather reports, app launching, message sending, and general conversation.

## Features

### Core Capabilities
- **Real-time Voice Recognition** - Uses Web Speech API with WebSocket communication
- **AI-Powered Responses** - Integrates with OpenRouter and various LLM providers
- **Natural Text-to-Speech** - Microsoft Edge TTS for high-quality voice output
- **Memory Management** - Persistent memory for user preferences and context
- **Intent Recognition** - Classification of user requests

### Available Actions
- **Weather Reports** - Get current weather for any location
- **Web Search** - Search the internet and get summarized results
- **App Launcher** - Open applications with voice commands
- **Message Sending** - Send messages through various platforms
- **Aircraft Reports** - Aviation-related information and reports
- **General Chat** - Natural conversation with context awareness

### User Interface
- **Modern tkinter GUI** - Animated face with visual feedback
- **Embedded Speech Client** - Hidden browser-based speech recognition
- **Real-time Logging** - Comprehensive logging system with rotating files
- **Visual State Indicators** - Feedback for listening/thinking/speaking states

## Quick Start

### Prerequisites
- Python 3.10 or higher
- Windows 10/11 (for Edge WebView2)
- Microphone and speakers
- Internet connection

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/sam-agent.git
   cd sam-agent
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\\Scripts\\activate  # On Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r REQUIREMENTS.txt
   ```

4. **Set up API keys**
   - Copy `config/api_keys.json.example` to `config/api_keys.json`
   - Add your API keys:
     ```json
     {
       "openrouter_api_key": "your-openrouter-key",
       "serpapi_api_key": "your-serpapi-key"
     }
     ```

5. **Run Sam**
   ```bash
   python main.py
   ```

## Configuration

### API Keys
Sam requires the following API keys:
- **OpenRouter** - For AI model access (required)
- **SerpAPI** - For web search functionality (optional)

### Environment Variables
Create a `.env` file (see `.env.example`):
```env
SAM_SHOW_SPEECH_WINDOW=0    # Set to 1 to show speech recognition window
LOG_LEVEL=INFO              # Logging level (DEBUG, INFO, WARNING, ERROR)
```

### Speech Recognition
- Uses Chrome/Edge Web Speech API for accuracy
- Embedded WebView2 window keeps microphone permissions persistent
- Falls back to a regular browser tab if WebView2 is unavailable

## Architecture

### Core Components

**Main Application (`main.py`)**
- Multi-threaded architecture
- UI thread for tkinter interface
- AI thread for conversation processing
- Main thread for embedded speech WebView

**Speech System (`speech_to_text_websocket.py`)**
- WebSocket server for real-time communication
- Embedded browser with Web Speech API
- Thread-safe command broadcasting

**AI Processing (`llm.py`)**
- OpenRouter integration
- Intent classification
- Parameter extraction
- Response generation

**Memory System (`memory/`)**
- Long-term user memory storage
- Temporary session context
- Preferences and relationship tracking

**User Interface (`ui.py`)**
- Animated Sam face with visual feedback
- Real-time logging display
- Thread-safe UI updates

### Data Flow
1. User speaks → Web Speech API → WebSocket
2. WebSocket → Speech-to-text transcription
3. Transcription → LLM processing
4. LLM → Intent classification + parameters
5. Intent → Action execution
6. Action result → Text-to-speech → Audio output

## Project Structure

```
Sam-Agent/
├── main.py                           # Application entry point
├── speech_to_text_websocket.py       # Voice input system
├── websocket_server.py               # WebSocket communication
├── llm.py                            # AI language model interface
├── tts.py                            # Text-to-speech system
├── ui.py                             # User interface
├── conversation_state.py             # State management
├── actions/                          # Available actions
│   ├── weather_report.py
│   ├── web_search.py
│   ├── open_app.py
│   ├── send_message.py
│   └── aircraft_report.py
├── config/                           # Configuration files
│   └── api_keys.json
├── memory/                           # Memory management
│   ├── memory_manager.py
+│   ├── temporary_memory.py
│   └── memory.json
├── log/                              # Application logs
├── core/                             # Core prompts and config
├── speech_client_compact.html        # Speech recognition interface
└── face.png                          # Sam's visual representation
```

## Usage Examples

### Voice Commands
- "Hey Sam, what's the weather in New York?"
- "Search for the latest tech news"
- "Open WhatsApp"
- "Send a message to John saying I'll be late"
- "Tell me about flight AA123"

### Intent System
Sam automatically classifies your requests into intents:
- **chat** - General conversation
- **weather_report** - Weather information
- **search** - Web search queries
- **open_app** - Application launching
- **send_message** - Message sending

## Advanced Configuration

### Custom Actions
Add new actions by creating Python files in the `actions/` directory:

```python
def my_action(parameters, player, session_memory):
    """Custom action implementation"""
    # Your action logic here
    player.write_log("Action completed")
    # Return response text
    return "Action completed successfully"
```

### Memory Customization
Modify memory categories in `memory/memory_manager.py`:
- **identity** - User personal information
- **preferences** - User likes/dislikes
- **relationships** - People and connections
- **emotional_state** - Emotional context

### LLM Configuration
Update `llm.py` to use different models or providers:
- Change model names
- Adjust temperature settings
- Modify system prompts

## Troubleshooting

### Common Issues

**Speech Recognition Not Working**
- Ensure microphone permissions are granted
- Check if running in Chrome/Edge compatible environment
- Verify WebSocket server is running (port 8765)

**API Key Errors**
- Verify API keys in `config/api_keys.json`
- Check key validity and account credits
- Ensure proper JSON formatting

**Memory Issues**
- Check `memory/memory.json` exists and is valid JSON
- Verify write permissions in project directory
- Reset memory by deleting `memory.json` if corrupted

**UI Not Appearing**
- Verify tkinter is properly installed
- Check if `face.png` exists
- Review error logs in `log/` directory

### Log Analysis
Sam creates detailed logs in the `log/` directory:
- `sam_main_*.log` - Main application events
- `sam_components_*.log` - Component-specific logs
- `sam_errors_*.log` - Error messages and exceptions

## Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Install development dependencies
4. Make your changes
5. Add tests if applicable
6. Submit a pull request

### Code Style
- Follow PEP 8 guidelines
- Use type hints where possible
- Add docstrings for functions and classes
- Keep functions focused and modular

### Testing
- Test voice recognition with various accents
- Verify multithread stability
- Check memory persistence
- Validate error handling

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Links

- [Setup Video Tutorial](https://youtu.be/w_AGre6-9TM?si=gE5xc4_aKhy4DwnA)
- [Python Downloads](https://www.python.org/downloads/)
- [OpenRouter API](https://openrouter.ai/)
- [SerpAPI](https://serpapi.com/)

## Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section above
- Review the logs for error details

---

Note: Sam is an actively developed project. Features and APIs may change between versions. Always check the latest documentation for updates.