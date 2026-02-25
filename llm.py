import os
import json
import requests
import sys
import time
from pathlib import Path

# Initialize logging
from log.logger import get_logger, log_function_entry, log_function_exit, log_error, log_api_call, log_performance
logger = get_logger("LLM")

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()

PROMPT_PATH = BASE_DIR / "core" / "prompt.txt"
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

def load_api_keys() -> dict:
    if not os.path.exists(API_CONFIG_PATH):
        return {}

    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to read api_keys.json: {e}")
        return {}


def get_openai_key() -> str | None:
    # Try .env first, then api_keys.json
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    
    keys = load_api_keys()
    return keys.get("openai_api_key")

def load_system_prompt() -> str:
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"⚠️ prompt.txt couldn't be loaded: {e}")
        return "You are Jarvis, a helpful AI assistant."


SYSTEM_PROMPT = load_system_prompt()

def safe_json_parse(text: str) -> dict | None:
    if not text:
        return None

    text = text.strip()

    if "```json" in text:
        try:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        except:
            pass
    elif "```" in text:
        try:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()
        except:
            pass

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        json_str = text[start:end]
        return json.loads(json_str)
    except Exception as e:
        print(f"⚠️ JSON parse error: {e}")
        print(f"⚠️ Raw text preview: {text[:200]}")
        return None

def get_llm_output(user_text: str, memory_block: dict | None = None) -> dict:
    log_function_entry(logger, "get_llm_output", user_text=user_text[:50] + "..." if user_text else None)
    start_time = time.time()
    
    if not user_text or not user_text.strip():
        logger.warning("Empty user input received")
        result = {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "Sir, I didn't catch that.",
            "memory_update": None
        }
        log_function_exit(logger, "get_llm_output", "empty_input_response")
        return result

    api_key = get_openai_key()
    if not api_key:
        print("❌ OPENAI API KEY NOT FOUND")
        return {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "OpenAI API key is missing, Sir.",
            "memory_update": None
        }

    memory_str = "{}"
    if memory_block and isinstance(memory_block, dict):
        memory_str = json.dumps(memory_block, indent=2, ensure_ascii=False)

    user_prompt = f"""
    USER MESSAGE:
    {user_text}

    LONG-TERM MEMORY (JSON):
    {memory_str}

    INSTRUCTIONS:
    - Use memory only when relevant.
    - If user shares new long-term personal information (identity, goals, projects),
      return it inside memory_update.
    - Do NOT store temporary conversation.
    - Maintain formal tone.
    """

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 250,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        logger.debug(f"Making OpenAI API request with model: {MODEL}")
        log_api_call(logger, "OpenAI")
        
        api_start = time.time()
        
        # Add retry logic for network issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    OPENAI_URL,
                    headers=headers,
                    json=payload,
                    timeout=15
                )
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.DNSLookupError) as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Connection attempt {attempt + 1} failed, retrying...")
                time.sleep(1 * (attempt + 1))  # Progressive delay
        
        api_duration = time.time() - api_start
        log_api_call(logger, "OpenAI", response.status_code, api_duration)
        
        if response.status_code != 200:
            logger.error(f"OpenAI API Error: {response.status_code} - {response.text}")
            return {
                "intent": "chat",
                "parameters": {},
                "needs_clarification": False,
                "text": f"Sir, API error ({response.status_code}).",
                "memory_update": None
            }

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        # Debug: Log raw LLM response
        logger.debug(f"Raw LLM response: {content}")

        parsed = safe_json_parse(content)

        if parsed:
            intent = parsed.get("intent", "chat")
            text = parsed.get("text")
            
            # Debug: Check if text field is missing
            if text is None or text == "":
                logger.warning(f"LLM response missing 'text' field. Parsed JSON: {parsed}")
                # Use a fallback if text is missing but we have intent
                text = "Sir, I processed your request."
            
            return {
                "intent": intent,
                "parameters": parsed.get("parameters", {}),
                "needs_clarification": parsed.get("needs_clarification", False),
                "text": text,
                "memory_update": parsed.get("memory_update")
            }

        result = {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": content,
            "memory_update": None
        }
        
        total_duration = time.time() - start_time
        log_performance(logger, "LLM processing", total_duration)
        log_function_exit(logger, "get_llm_output", f"success_{result['intent']}")
        return result

    except requests.exceptions.Timeout:
        logger.error("OpenAI API timeout (15s)")
        return {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "Sir, the request timed out. Please check your internet connection.",
            "memory_update": None
        }
        
    except (requests.exceptions.ConnectionError, requests.exceptions.DNSLookupError) as e:
        logger.error(f"OpenAI API connection error: {e}")
        return {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "Sir, I'm having trouble connecting to the AI service. Please check your internet connection.",
            "memory_update": None
        }

    except Exception as e:
        log_error(logger, "get_llm_output", e)
        result = {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "Sir, there was an error processing your request.",
            "memory_update": None
        }
        log_function_exit(logger, "get_llm_output", "error")
        return result