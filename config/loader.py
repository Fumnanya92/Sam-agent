"""
config/loader.py — Unified config loader for Sam.

Load order:
  1. config/sam.yaml  — primary source of truth
  2. .env             — overrides / secrets (via python-dotenv)
  3. os.environ       — highest priority (CI / deployment overrides)

Returns a nested dict.  Scalar leaf values can be overridden by env vars
following the pattern SAM__SECTION__KEY (double-underscore delimited),
e.g. SAM__DAEMON__PORT=3142 overrides daemon.port.
"""

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("sam.config")

# Path to the canonical YAML config
_CONFIG_DIR = Path(__file__).resolve().parent
_YAML_PATH = _CONFIG_DIR / "sam.yaml"


def _load_yaml(path: Path) -> dict:
    """Load a YAML file.  Requires PyYAML (pip install pyyaml)."""
    try:
        import yaml  # type: ignore
    except ImportError:
        logger.warning("[config] PyYAML not installed — YAML config unavailable")
        return {}

    if not path.exists():
        logger.warning(f"[config] YAML config not found at {path}")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        logger.error(f"[config] YAML root must be a mapping, got {type(data)}")
        return {}

    return data


def _expand_paths(config: dict) -> dict:
    """Expand ~ in any string value that looks like a file path."""
    for section, values in config.items():
        if not isinstance(values, dict):
            continue
        for key, val in values.items():
            if isinstance(val, str) and val.startswith("~"):
                config[section][key] = str(Path(val).expanduser())
    return config


def _apply_env_overrides(config: dict) -> dict:
    """
    Apply SAM__SECTION__KEY env var overrides to the config dict.

    Example:
        SAM__DAEMON__PORT=4000  → config["daemon"]["port"] = "4000"
        SAM__LLM__PRIMARY__MODEL=llama3  → config["llm"]["primary"]["model"] = "llama3"
    """
    prefix = "SAM__"
    for key, val in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix):].lower().split("__")
        target = config
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = val
        logger.debug(f"[config] Env override: {key} = {val}")
    return config


def load_config(yaml_path: Path | None = None) -> dict:
    """
    Load and return the Sam config as a nested dict.

    Args:
        yaml_path: Override the default config/sam.yaml location.

    Returns:
        Merged config dict with env-var overrides applied.
    """
    # Load .env (if python-dotenv available) — must happen before env override scan
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    path = yaml_path or _YAML_PATH
    config = _load_yaml(path)
    config = _expand_paths(config)
    config = _apply_env_overrides(config)

    return config


def get(section: str, key: str, default: Any = None) -> Any:
    """
    Convenience accessor for a single config value.

    Example:
        port = get("daemon", "port", 3142)
    """
    return config().get(section, {}).get(key, default)


# Module-level cached config — call load_config() directly for a fresh load
_config: dict | None = None


def config() -> dict:
    """Return a module-level cached config (loaded once per process)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
