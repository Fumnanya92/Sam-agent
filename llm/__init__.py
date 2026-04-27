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

# Ollama (local LLM) config — override via .env
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT  = int(os.getenv("OLLAMA_TIMEOUT", "30"))

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # __file__ is llm/__init__.py — go up one level to project root
    return Path(__file__).resolve().parent.parent

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
        return "You are Sam, a sharp personal AI assistant."


SYSTEM_PROMPT = load_system_prompt()

# ── Model tier ─────────────────────────────────────────────────────────────
# "local"  → Ollama (free, private)
# "cloud"  → OpenAI GPT-4o-mini (default fallback when Ollama not available)
MODEL_TIER = "local"

def is_ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _resolve_ollama_model() -> str:
    """Return the model to actually use.
    Prefers the configured OLLAMA_MODEL; auto-discovers the first installed
    model if the configured one is not present (e.g. user has a different
    model installed than the default 'llama3.2').
    """
    configured = OLLAMA_MODEL
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        if r.status_code != 200:
            return configured
        models = [m.get("name", "") for m in r.json().get("models", [])]
        if not models:
            return configured
        # If configured model (or its base name) is available, use it
        for m in models:
            if configured in m or m.startswith(configured.split(":")[0]):
                return m
        # Fall back to first available model
        logger.info(
            f"Configured OLLAMA_MODEL '{configured}' not found in Ollama. "
            f"Auto-selecting '{models[0]}' instead."
        )
        return models[0]
    except Exception:
        return configured


OLLAMA_AVAILABLE = is_ollama_available()
if OLLAMA_AVAILABLE:
    OLLAMA_MODEL = _resolve_ollama_model()
    logger.info(f"Ollama available at {OLLAMA_BASE_URL} — default tier: local ({OLLAMA_MODEL})")
else:
    logger.info("Ollama not reachable — defaulting to cloud tier")
    MODEL_TIER = "cloud"

# Intents that benefit from the cloud model. Sam will suggest switching once per session.
# Only include tasks that genuinely need cloud capability — Ollama handles all others.
COMPLEX_INTENTS = {
    "code_explainer", "explain_code",
    "summarise_text", "rephrase_text", "expand_text", "bullet_text",
    "make_formal", "make_casual", "text_transform",
    "debug_screen", "vscode_mode",
}

def get_model_tier() -> str:
    return MODEL_TIER

def set_model_tier(tier: str) -> str:
    """Switch between 'local' and 'cloud'. Returns a human-readable status message."""
    global MODEL_TIER
    if tier == "local":
        if OLLAMA_AVAILABLE:
            MODEL_TIER = "local"
            logger.info(f"Model tier switched to local ({OLLAMA_MODEL})")
            return f"Switched to local model ({OLLAMA_MODEL})."
        else:
            logger.warning("Tried to switch to local but Ollama is not available")
            return "Local model isn't reachable right now — staying on cloud."
    elif tier == "cloud":
        MODEL_TIER = "cloud"
        logger.info(f"Model tier switched to cloud ({MODEL})")
        return f"Switched to cloud model ({MODEL})."
    return "Unknown tier."

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
            "text": "Didn't catch that — could you say it again?",
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
            "text": "No API key found — check your config.",
            "memory_update": None
        }

    memory_str = "{}"
    if memory_block and isinstance(memory_block, dict):
        memory_str = json.dumps(memory_block, indent=2, ensure_ascii=False)

    skill_section = _consume_skill_context()

    user_prompt = f"""
    USER MESSAGE:
    {user_text}

    LONG-TERM MEMORY (JSON):
    {memory_str}

    INSTRUCTIONS:
    - Use memory when relevant to make your response feel personal and contextual.
    - If user shares new long-term personal information (identity, goals, projects, relationships),
      return it inside memory_update.
    - Do NOT store temporary conversation details.
    - Respond naturally, like a sharp intelligent person — not a robot.
    - Vary your language. Never use the same opener twice in a row.
    - The "text" field is what Sam will speak aloud. Make it worth hearing.
    - For actions (search, open app, etc.), the text is what Sam says while taking action.
      Keep it brief and natural (1-2 sentences).
    - For pure conversation, engage meaningfully. Ask a follow-up when it makes sense.
    {skill_section}
    """

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.45,
        "max_tokens": 500,
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
                "text": f"Got an API error — code {response.status_code}.",
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
                text = "On it."

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
            "text": "That request timed out — internet might be slow.",
            "memory_update": None
        }

    except (requests.exceptions.ConnectionError, requests.exceptions.DNSLookupError) as e:
        logger.error(f"OpenAI API connection error: {e}")
        return {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "Can't reach the AI service right now — check your connection.",
            "memory_update": None
        }

    except Exception as e:
        log_error(logger, "get_llm_output", e)
        result = {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "Something went wrong on my end — try again.",
            "memory_update": None
        }
        log_function_exit(logger, "get_llm_output", "error")
        return result


def get_ollama_output(user_text: str, memory_block: dict | None = None) -> dict:
    """Call the local Ollama model with the same prompt format as the cloud path."""
    log_function_entry(logger, "get_ollama_output", user_text=user_text[:50] + "..." if user_text else None)
    start_time = time.time()

    if not user_text or not user_text.strip():
        return {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "Didn't catch that — could you say it again?",
            "memory_update": None
        }

    memory_str = "{}"
    if memory_block and isinstance(memory_block, dict):
        memory_str = json.dumps(memory_block, indent=2, ensure_ascii=False)

    skill_section = _consume_skill_context()

    user_prompt = f"""
    USER MESSAGE:
    {user_text}

    LONG-TERM MEMORY (JSON):
    {memory_str}

    INSTRUCTIONS:
    - Use memory when relevant to make your response feel personal and contextual.
    - If user shares new long-term personal information (identity, goals, projects, relationships),
      return it inside memory_update.
    - Do NOT store temporary conversation details.
    - Respond naturally, like a sharp intelligent person — not a robot.
    - Vary your language. Never use the same opener twice in a row.
    - The "text" field is what Sam will speak aloud. Make it worth hearing.
    - For actions (search, open app, etc.), the text is what Sam says while taking action.
      Keep it brief and natural (1-2 sentences).
    - For pure conversation, engage meaningfully. Ask a follow-up when it makes sense.
    {skill_section}
    """

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
    }

    try:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json=payload,
                    timeout=OLLAMA_TIMEOUT,
                )
                break
            except (requests.exceptions.ConnectionError,) as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Ollama attempt {attempt + 1} failed, retrying...")
                time.sleep(1 * (attempt + 1))

        if response.status_code != 200:
            logger.error(f"Ollama error: {response.status_code} — {response.text[:200]}")
            return {
                "intent": "chat",
                "parameters": {},
                "needs_clarification": False,
                "text": f"Local model returned an error — code {response.status_code}.",
                "memory_update": None
            }

        data = response.json()
        content = data.get("message", {}).get("content", "")
        logger.debug(f"Ollama raw response: {content[:200]}")

        parsed = safe_json_parse(content)
        if parsed:
            text = parsed.get("text") or "On it."
            return {
                "intent": parsed.get("intent", "chat"),
                "parameters": parsed.get("parameters", {}),
                "needs_clarification": parsed.get("needs_clarification", False),
                "text": text,
                "memory_update": parsed.get("memory_update"),
            }

        # Fallback: treat raw content as chat
        return {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": content or "On it.",
            "memory_update": None
        }

    except requests.exceptions.Timeout:
        logger.error(f"Ollama request timed out ({OLLAMA_TIMEOUT}s)")
        return {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "Local model timed out — you might want to switch to cloud.",
            "memory_update": None
        }
    except Exception as e:
        log_error(logger, "get_ollama_output", e)
        return {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "Local model ran into an issue — try again or switch to cloud.",
            "memory_update": None
        }
    finally:
        log_performance(logger, "Ollama processing", time.time() - start_time)


def get_ai_response(user_text: str, memory_block: dict | None = None) -> dict:
    """Unified LLM entry point — routes to local (Ollama) or cloud based on MODEL_TIER."""
    if MODEL_TIER == "local" and OLLAMA_AVAILABLE:
        return get_ollama_output(user_text, memory_block)
    return get_llm_output(user_text, memory_block)


# ── Skill context injection ──────────────────────────────────────────────────
_pending_skill_content: str | None = None
_pending_skill_name: str | None = None


def prime_skill_context(content: str | None, name: str | None = None):
    """Set skill context to be injected into the very next LLM call."""
    global _pending_skill_content, _pending_skill_name
    _pending_skill_content = content
    _pending_skill_name    = name


def _consume_skill_context() -> str:
    """Pop and return the current skill context section (empty string if none)."""
    global _pending_skill_content, _pending_skill_name
    content = _pending_skill_content
    name    = _pending_skill_name
    _pending_skill_content = None
    _pending_skill_name    = None
    if not content:
        return ""
    header = f"\n\n#ACTIVE_SKILL: {name or 'unnamed'}\n" if name else "\n\n#ACTIVE_SKILL:\n"
    return header + content[:3000]  # cap to avoid token overflow
