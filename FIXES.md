# Quick Setup Instructions

## Issue 1: Logging Cleanup Messages
✅ **FIXED** - Removed verbose "Cleaned up old log" messages from console output

## Issue 2: Sam Responses Not Showing
✅ **FIXED** - Added error handling and logging around intent routing
- Now logs detected intent and response
- Catches and reports any errors during intent handling
- Check logs for: `Intent detected: 'intent_name'`

## Issue 3: WhatsApp Not Using DOM
The WhatsApp integration uses different handlers:
- `read_messages` → Uses `assistant.message_reader.read_latest_whatsapp_message`
- `whatsapp_summary` → Uses `whatsapp_assistant.summarize_unread()`
- `read_whatsapp` → Uses `whatsapp_assistant.read_current_chat()`

For DOM-based WhatsApp reading:
```python
# Use these intents/commands:
"Check my messages" → read_messages (uses message_reader)
"WhatsApp summary" → whatsapp_summary (uses assistant)
```

The WhatsApp assistant in `automation/whatsapp_assistant.py` uses the DOM via Chrome debugging.

## Issue 4: Speech Webview Not Working

### Install pywebview
```bash
pip install pywebview
```

### Verify Installation
```bash
python -c "import webview; print('pywebview installed:', webview.__version__)"
```

### Troubleshooting
If pywebview fails to install or import:

**Windows:**
```bash
# Install dependencies
pip install pywebview[winforms]

# Or use EdgeChromium backend
pip install pywebview
```

**The browser fallback works fine**, but for embedded window:
1. Install pywebview: `pip install pywebview`
2. Restart Sam: `python main.py`
3. Should see: "Creating embedded speech client window" instead of "using browser fallback"

### Check Current Status
```bash
python -c "try:
    import webview
    print('✅ pywebview is installed')
except ImportError:
    print('❌ pywebview NOT installed - using browser fallback')
"
```

## Quick Test
```bash
python main.py
```

**Expected output:**
- NO "Cleaned up old log" messages (silenced)
- "Creating embedded speech client window" (if pywebview installed)
- OR "using browser fallback" (if pywebview missing)
- Sam responses should appear: "🤖 Sam: ..."
- Intent logging in log files

## Debug Commands

### Check Intent Detection
```bash
# Watch the logs
tail -f log/sam_main_*.log | grep "Intent detected"
```

### Test WhatsApp
```python
# Make sure Chrome is running with debugging:
scripts\start_chrome_debug.bat

# Then say:
"Sam, check my messages"
"Sam, WhatsApp summary"
```

### Test Basic Response
```python
# Say simple things that should get chat responses:
"Sam, what is 2 + 2"
"Sam, what's my CPU usage"
"Sam, hello"
```

If responses still don't show, check:
1. `log/sam_main_*.log` for "Intent detected" messages
2. Look for errors in intent handling
3. Verify edge-tts is working: `python -c "import edge_tts; print('TTS OK')"`
