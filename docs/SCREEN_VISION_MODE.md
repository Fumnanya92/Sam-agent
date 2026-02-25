# Screen Vision Mode - Documentation

## Overview

Screen Vision Mode gives Sam the ability to **see and understand your screen** using OpenAI's GPT-4o-mini vision model. Sam can capture screenshots and provide intelligent analysis of what's visible on your display.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 SCREEN VISION MODE                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Voice Command                                           │
│       ↓                                                  │
│  Screen Capture (mss)                                    │
│       ↓                                                  │
│  Image → Base64 Encoding                                 │
│       ↓                                                  │
│  OpenAI Vision API (GPT-4o-mini)                        │
│       ↓                                                  │
│  Structured Analysis                                     │
│       ↓                                                  │
│  Sam Voice Response (TTS)                                │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Phase 1: Observation Mode (Current)

**Status**: ✅ Implemented

This is a **controlled, safe implementation** focused on observation only:
- 📸 Captures screenshots on command
- 🤖 Analyzes with AI vision model
- 🗣️ Provides verbal insights
- ❌ **No automation** - user must explicitly request
- ❌ **No clicks** - observation only

## Features

### Screen Capture
- Captures entire primary monitor
- Converts to PNG format
- Base64 encodes for API transmission
- Handles multiple monitor setups

### AI Vision Analysis
- Uses OpenAI GPT-4o-mini vision model
- Analyzes screen content intelligently
- Provides concise, professional descriptions
- Addresses user as "Sir" (Sam's style)
- Max 300 tokens per response

### Voice Integration
- Fully integrated with Sam's TTS
- Logs analysis to UI
- Threaded execution (non-blocking)
- Error handling and recovery

## Voice Commands

Sam responds to natural language requests:

| Command | Intent | Action |
|---------|--------|--------|
| "Sam, look at my screen" | screen_vision | Captures and analyzes display |
| "What am I seeing?" | screen_vision | Describes visible content |
| "Analyze my screen" | screen_vision | Provides detailed analysis |
| "Explain this error" | screen_vision | Focuses on error messages |
| "What am I looking at?" | screen_vision | General description |
| "Walk me through this" | screen_vision | Step-by-step explanation |

## Setup

### Dependencies

```bash
pip install mss              # Screen capture
pip install Pillow           # Image processing
pip install requests         # API calls
```

### OpenAI API Key

Screen Vision requires an OpenAI API key with GPT-4 Vision access.

**Option 1: Environment Variable**
```bash
set OPENAI_API_KEY=your_key_here  # Windows
export OPENAI_API_KEY=your_key_here  # Linux/Mac
```

**Option 2: Config File**
Add to `config/api_keys.json`:
```json
{
  "openai_api_key": "your_key_here"
}
```

Get your API key: https://platform.openai.com/api-keys

### Cost Considerations

GPT-4o-mini vision pricing (as of 2024):
- Input: ~$0.15 per million tokens
- Images: ~$0.003 per image (1024x1024)
- Each screen capture costs ~$0.003-0.01

**Estimated costs:**
- 10 screen analyses: ~$0.05
- 100 screen analyses: ~$0.50
- 1000 screen analyses: ~$5.00

## Usage Examples

### Example 1: Debugging Code Error

**You:** "Sam, explain this error"

**Sam:** 
```
Sir, I can see a Python error on your screen. The traceback shows a 
ModuleNotFoundError for 'mss'. This indicates the mss package is not 
installed. You should run 'pip install mss' to resolve this issue.
```

### Example 2: Understanding Interface

**You:** "What am I looking at?"

**Sam:**
```
Sir, your screen displays a Visual Studio Code editor with a Python 
file open. The file appears to be a system monitoring module with 
functions for CPU and RAM tracking. The terminal at the bottom shows 
a successful test run.
```

### Example 3: Website Analysis

**You:** "Sam, analyze my screen"

**Sam:**
```
Sir, the screen shows the OpenAI website's API platform page. The main 
message reads "Build leading AI products on OpenAI's platform" with 
call-to-action buttons for contacting sales and starting to build. 
Several partner company logos are displayed including Salesforce and Wix.
```

### Example 4: Document Review

**You:** "Walk me through this"

**Sam:**
```
Sir, I see a README file with setup instructions. The document outlines 
three main sections: Prerequisites, Installation, and Configuration. 
It appears to be a guide for setting up a Python project with specific 
dependencies listed.
```

## Implementation Details

### File Structure

```
system/
├── screen_vision.py         # Core vision module
    ├── capture_screen_base64()  # Screen capture function
    ├── get_openai_key()         # API key retrieval
    └── analyze_screen()         # Vision analysis
```

### Core Functions

#### `capture_screen_base64()`
Captures primary monitor and returns base64 encoded PNG.

**Returns:** `str` - Base64 encoded image

```python
from system.screen_vision import capture_screen_base64

image_data = capture_screen_base64()
# Returns: "iVBORw0KGgoAAAANSUhEUgAA..."
```

#### `get_openai_key()`
Retrieves OpenAI API key from environment or config file.

**Returns:** `str | None` - API key or None

**Priority:**
1. Environment variable: `OPENAI_API_KEY`
2. Config file: `config/api_keys.json`

#### `analyze_screen()`
Captures screen and analyzes with OpenAI Vision API.

**Returns:** `str` - Analysis result or error message

```python
from system.screen_vision import analyze_screen

analysis = analyze_screen()
# Returns: "Sir, I can see..."
```

### API Integration

**Model:** GPT-4o-mini (vision-enabled)
**Max Tokens:** 300
**System Prompt:** "You are Sam, a precise system assistant..."

**Request Format:**
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {
      "role": "system",
      "content": "You are Sam, a precise system assistant..."
    },
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "What is happening on this screen?"},
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,{base64_image}"
          }
        }
      ]
    }
  ],
  "max_tokens": 300
}
```

## Testing

### Unit Test

```bash
# Run comprehensive test
python tests/test_screen_vision.py
```

**Tests Include:**
1. Module import
2. Screen capture
3. API key detection
4. Vision analysis (if key available)
5. Intent configuration
6. Handler verification
7. Dependencies check
8. Sample commands

### Manual Testing

```bash
# Start Sam
python main.py

# Test commands
"Sam, look at my screen"       # Full analysis
"What am I seeing?"            # Quick description
"Explain this error"           # Error-focused
```

## Error Handling

### No API Key
```
Sir, I need an OpenAI API key to analyze the screen. Please set 
OPENAI_API_KEY environment variable or add openai_api_key to 
config/api_keys.json.
```

### Network Error
```
Sir, I encountered an error analyzing the screen: Connection timeout
```

### Invalid API Key
```
Sir, I encountered an error analyzing the screen: Invalid authentication
```

## Performance

### Response Time
- Screen capture: ~100-200ms
- API call: ~2-5 seconds
- Total: ~2-6 seconds

### Resource Usage
- Memory: ~5-10 MB per capture
- CPU: Low (mostly waiting for API)
- Network: ~500KB per request

## Security & Privacy

### ⚠️ Important Considerations

**What Gets Sent:**
- Entire primary monitor screenshot
- Sent to OpenAI's servers
- Stored temporarily for processing

**Privacy Recommendations:**
1. Close sensitive windows before using
2. Use only when necessary
3. Remember everything visible is sent to OpenAI
4. Review OpenAI's data usage policy

**Best Practices:**
- Don't capture screens with passwords visible
- Close banking/financial apps before analysis
- Be aware of sensitive information on screen
- Consider using on non-production environments

## Limitations (Phase 1)

### Current Limitations
- ❌ No region selection (captures full screen)
- ❌ No multi-monitor selection
- ❌ No cursor assistance
- ❌ No click suggestions
- ❌ No automated actions
- ❌ No continuous monitoring

### Why These Limitations?
**Controlled, safe implementation approach:**
1. Master observation first
2. Build trust in accuracy
3. Understand use cases
4. Then add automation carefully

## Future Phases (Planned)

### Phase 2: Interactive Guidance
- Multi-turn conversations about screen
- Follow-up questions
- Detailed explanations
- Context retention

### Phase 3: Click Suggestion Overlay
- Visual overlay with suggestions
- Highlight clickable elements
- Show recommended actions
- Still requires user approval

### Phase 4: Autonomous Cursor Assistance (Far Future)
- Automated cursor movement
- Click execution with consent
- Guided workflows
- Full task automation

**⚠️ Phases 2-4 not yet implemented - Phase 1 only**

## Troubleshooting

### "mss not installed"
```bash
pip install mss
```

### "Pillow not installed"
```bash
pip install pillow
```

### "API key not found"
1. Check environment variable: `echo %OPENAI_API_KEY%`
2. Check config file: `config/api_keys.json`
3. Verify key is valid on OpenAI platform

### "Screen capture failed"
- Check if any screen capture software is blocking
- Try running as administrator (Windows)
- Check display drivers are up to date

### "Analysis taking too long"
- Normal response time: 2-6 seconds
- Check internet connection
- Verify OpenAI API status
- Consider timeout (30 seconds default)

### "Invalid response from API"
- Check API key is valid
- Verify you have GPT-4 vision access
- Check OpenAI account has credits

## Advanced Customization

### Modify Model Parameters

Edit `system/screen_vision.py`:

```python
payload = {
    "model": "gpt-4o-mini",        # Change model
    "max_tokens": 500,              # Increase response length
    "temperature": 0.7,             # Add creativity
    ...
}
```

### Change System Prompt

```python
"content": "You are Sam, a [custom personality]. [Custom instructions]."
```

### Capture Specific Monitor

```python
def capture_screen_base64(monitor_number=1):
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_number]  # Change monitor
        ...
```

## API Reference

### `capture_screen_base64()`
**Purpose:** Capture screen and encode to base64

**Returns:** `str` - Base64 encoded PNG image

**Raises:** `Exception` - If screen capture fails

### `get_openai_key()`
**Purpose:** Retrieve OpenAI API key from environment or config

**Returns:** `str | None` - API key or None if not found

**Sources:** 
1. Environment variable: `OPENAI_API_KEY`
2. Config file: `config/api_keys.json` → `openai_api_key`

### `analyze_screen()`
**Purpose:** Capture and analyze screen with OpenAI Vision

**Returns:** `str` - Analysis text or error message

**Network:** Makes HTTPS request to OpenAI API

**Timeout:** 30 seconds default

## Summary

Screen Vision Mode gives Sam visual awareness with:

✅ **Screen capture** - Capture display on command
✅ **AI vision** - Understand what's visible
✅ **Voice output** - Speak analysis naturally
✅ **Safe mode** - Observation only, no automation
✅ **Error handling** - Graceful fallbacks
✅ **Privacy aware** - User-initiated only

**Use Cases:**
- 🐛 Debugging error messages
- 📖 Understanding interfaces
- 🎓 Learning new software
- 👀 Quick screen descriptions
- 🔍 Analyzing documents

**This is Sam's first step toward visual intelligence.**

---

**Status:** ✅ Phase 1 Complete
**Model:** GPT-4o-mini (vision)
**Cost:** ~$0.003-0.01 per analysis
**Response Time:** 2-6 seconds
**Privacy:** User-initiated only

**⚠️ Remember: Everything on your screen gets sent to OpenAI's API**
