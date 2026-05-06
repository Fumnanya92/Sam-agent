import base64
import requests
from system.screen_vision import capture_screen


def analyze_vscode_screen(api_key: str) -> str:
    """
    VSCode Intelligent Coding Mode.
    Understands code, errors, structure, and suggests exact edits.
    """

    screenshot_bytes = capture_screen()

    if not screenshot_bytes:
        return "I could not capture the screen."

    encoded_image = base64.b64encode(screenshot_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = """
You are an elite senior software architect.

You are looking at a VSCode screen.

Your job:

1. Identify:
   - Programming language
   - Current file purpose
   - Any visible errors
   - Bad architecture
   - Inefficient logic

2. If error exists:
   - Explain root cause
   - Show exact corrected code snippet

3. If improvement opportunity exists:
   - Suggest clean refactor
   - Suggest better structure
   - Suggest performance improvements

4. Speak concisely but technically.
5. Do not use "Sir" in any output.

If this is not VSCode, say:
"This does not appear to be VSCode."

Be precise.
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
        "max_tokens": 900
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
        return f"VSCode analysis failed: {str(e)}"
