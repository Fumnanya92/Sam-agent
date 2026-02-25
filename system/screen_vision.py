import base64
import io
import mss
from PIL import Image
import requests
import os
import json
from pathlib import Path


OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def get_openai_key():
    """Get OpenAI API key from environment or config file"""
    # Try environment variable first
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        # Try config file
        try:
            config_path = Path(__file__).parent.parent / "config" / "api_keys.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    api_key = config.get("openai_api_key")
        except Exception:
            pass
    
    return api_key


def capture_screen():
    """Capture entire screen and return as bytes"""
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Primary monitor
        screenshot = sct.grab(monitor)

        img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")

        return buffer.getvalue()


def capture_screen_base64():
    """Capture entire screen and return as base64 encoded string"""
    screenshot_bytes = capture_screen()
    return base64.b64encode(screenshot_bytes).decode("utf-8")


def analyze_screen():
    """Capture screen and analyze with OpenAI Vision model"""
    api_key = get_openai_key()
    
    if not api_key:
        return "Sir, I need an OpenAI API key to analyze the screen. Please set OPENAI_API_KEY environment variable or add openai_api_key to config/api_keys.json."

    try:
        image_base64 = capture_screen_base64()

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are Sam, a precise system assistant. Describe what is visible on the screen concisely and professionally. Address the user as 'Sir' when appropriate."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is happening on this screen?"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 300
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    except Exception as e:
        return f"Sir, I encountered an error analyzing the screen: {str(e)}"


def analyze_screen_for_errors(api_key: str) -> str:
    """
    Specialized error debugging mode.
    Focuses on stack traces, error dialogs, terminal logs, VSCode problems.
    """

    screenshot_bytes = capture_screen()

    if not screenshot_bytes:
        return "Sir, I could not capture the screen."

    encoded_image = base64.b64encode(screenshot_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = """
You are an elite debugging assistant.

Analyze the screenshot carefully.

If there is:
- A stack trace
- A Python error
- A Node/JS error
- A Flutter error
- A VSCode error
- A terminal failure
- A build failure
- A runtime exception

You must:

1. Identify the exact error message.
2. Explain clearly what caused it.
3. Provide a direct fix.
4. Provide step-by-step correction instructions.
5. Keep response concise but actionable.

If no error is visible, say:
"Sir, I do not detect a clear error on the screen."

Be precise. No fluff.
"""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encoded_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 800
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        data = response.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Sir, vision analysis failed: {str(e)}"
