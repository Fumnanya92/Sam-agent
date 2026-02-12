# 🚀 Sam Setup Guide - Laptop Optimized Configuration

## ✅ Current Setup (Balanced for Laptop)

- **STT**: Whisper tiny (local, fastest for laptops)
- **LLM**: phi3:mini via Ollama (local, fast)
- **TTS**: Edge TTS (lightweight, high quality)

This setup keeps RAM manageable (~1-3GB for STT + LLM), allows automation, and feels responsive.

---

## 📋 Installation Steps

### 1. Install Python Dependencies

```powershell
pip install sounddevice soundfile numpy openai-whisper edge-tts google-search-results Pillow requests pyautogui python-dotenv
```

### 2. Verify Ollama & phi3:mini

```powershell
# Check if phi3:mini is installed
ollama list

# If not installed, pull it:
ollama pull phi3:mini

# Start Ollama server (if not running)
ollama serve
```

### 3. Test Whisper Model Download

When you first run Sam, Whisper will auto-download the model you choose via `WHISPER_MODEL` in `.env`.
By default Sam uses `tiny` (very small, ~70MB) for faster CPU inference on low-RAM laptops.

---

## 🎯 Quick Start

```powershell
# Activate venv (if using one)
.\.venv\Scripts\Activate.ps1

# Run Sam
python main.py
```

---

## ⚙️ Configuration Files

### `.env` - Active Settings
- `AI_PROVIDER=ollama`
- `OLLAMA_MODEL=phi3:mini`
- `STT_PROVIDER=whisper`
- `WHISPER_MODEL=tiny`  # change to `base`/`small` if you have more RAM and want higher accuracy

### `main.py` - STT Selection
Currently using:
```python
from speech_to_text_whisper import record_voice  # Whisper (configurable via .env, default=tiny)
```

To switch back to Vosk (faster but less accurate):
```python
from speech_to_text import record_voice  # Vosk
```

---

## 🔧 Troubleshooting

### Ollama Connection Error
**Error**: "Ollama is not running. Please start it with 'ollama serve'."

**Fix**:
```powershell
ollama serve
```

### Whisper Model Not Found
**Error**: Model not downloaded

**Fix**: First run will download automatically. Or manually (choose a model):
```powershell
python -c "import whisper; whisper.load_model('tiny')"
```

### High RAM Usage
- Whisper `tiny`: ~70MB (recommended)
- Whisper `base`/`small`: larger (~500MB-2GB) and slower on CPU
- phi3:mini: ~2-3GB RAM

---

## 🎨 Switching Configurations

### Go Back to OpenAI (Cloud)
1. Uncomment OpenAI code in `llm.py`
2. Update `.env`: `AI_PROVIDER=openai`
3. Add OpenAI key to `.env`

### Use Vosk STT (Faster, Offline)
In `main.py`:
```python
from speech_to_text import record_voice  # Vosk
```

---

## 📊 Performance Comparison

| Component | Option | Speed | Accuracy | RAM | Internet |
|-----------|--------|-------|----------|-----|----------|
| STT | Vosk | ⚡⚡⚡ | ⭐⭐ | 200MB | ❌ |
| STT | Whisper tiny | ⚡⚡⚡ | ⭐⭐⭐ | 70MB | ❌ |
| STT | Whisper base/small | ⚡⚡ | ⭐⭐⭐⭐ | 500MB-2GB | ❌ |
| LLM | phi3:mini | ⚡⚡⚡ | ⭐⭐⭐ | 2GB | ❌ |
| LLM | gpt-3.5-turbo | ⚡⚡ | ⭐⭐⭐⭐ | 0 | ✅ |
| TTS | Edge TTS | ⚡⚡⚡ | ⭐⭐⭐⭐ | 50MB | ✅ |

**Current = All local except TTS (Edge requires internet)**

---

## 🎯 Recommended Next Steps

1. Test the new setup: `python main.py`
2. Monitor RAM usage in Task Manager
3. If slow, switch back to Vosk STT
4. If Ollama crashes, reduce model size or use OpenAI

Enjoy Sam! 🤖
