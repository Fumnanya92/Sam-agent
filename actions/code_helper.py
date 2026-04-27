# actions/code_helper.py
# AI-powered code assistant — adapted from Mark-XXX-main.
# Gemini calls replaced with agent/llm_bridge.py (Ollama-first, OpenAI fallback).
# screen_debug uses system/screen_vision.py for capture + OpenAI vision for analysis.
#
# Actions:
#   write        : Describe what you want, AI writes it, saves to file
#   edit         : Read existing file, apply natural language change
#   explain      : Explain what a piece of code or file does
#   run          : Execute a script file, return output
#   build        : Write -> Run -> Fix loop (max 3 attempts), speaks when done
#   screen_debug : Screenshot the screen, analyze with vision AI
#   optimize     : Optimize existing code (performance, readability, best practices)
#   auto         : Intent auto-detected from context

import subprocess
import sys
import json
import re
import time
from pathlib import Path
from agent.utils import clean_code as _clean_code, has_error as _has_error

DESKTOP            = Path.home() / "Desktop"
MAX_BUILD_ATTEMPTS = 3


def _resolve_save_path(output_path: str, language: str) -> Path:
    ext_map = {
        "python": ".py", "py": ".py",
        "javascript": ".js", "js": ".js",
        "typescript": ".ts", "ts": ".ts",
        "html": ".html", "css": ".css",
        "java": ".java", "cpp": ".cpp", "c": ".c",
        "bash": ".sh", "shell": ".sh", "powershell": ".ps1",
        "sql": ".sql", "json": ".json", "rust": ".rs", "go": ".go",
    }
    if output_path:
        p = Path(output_path)
        return p if p.is_absolute() else DESKTOP / p
    ext = ext_map.get((language or "python").lower(), ".py")
    return DESKTOP / f"sam_code{ext}"


def _read_file(file_path: str) -> tuple:
    if not file_path:
        return "", "No file path provided."
    p = Path(file_path)
    if not p.exists():
        return "", f"File not found: {file_path}"
    try:
        return p.read_text(encoding="utf-8"), ""
    except Exception as e:
        return "", f"Could not read file: {e}"


def _save_file(path: Path, content: str) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Saved to: {path}"
    except Exception as e:
        return f"Could not save: {e}"


def _preview(code: str, lines: int = 10) -> str:
    all_lines = code.splitlines()
    preview   = "\n".join(all_lines[:lines])
    suffix    = f"\n... ({len(all_lines) - lines} more lines)" if len(all_lines) > lines else ""
    return preview + suffix


def _detect_intent(description: str, file_path: str, code: str) -> str:
    desc = (description or "").lower()

    screen_kw = ["screen", "this error", "why am i getting", "what's wrong",
                 "screenshot", "on screen", "on my screen"]
    if any(k in desc for k in screen_kw):
        return "screen_debug"

    optimize_kw = ["optimize", "refactor", "clean up", "improve",
                   "make it better", "make it faster"]
    if any(k in desc for k in optimize_kw) and (code or file_path):
        return "optimize"

    if file_path:
        p = Path(file_path)
        edit_kw  = ["edit", "update", "modify", "change", "add", "remove",
                    "refactor", "fix", "rename", "replace"]
        run_kw   = ["run", "execute", "launch", "start"]
        build_kw = ["build", "make it work", "try", "attempt"]

        if p.exists() and any(k in desc for k in edit_kw):
            return "edit"
        if p.exists() and any(k in desc for k in run_kw):
            return "run"
        if any(k in desc for k in build_kw):
            return "build"
        if p.exists():
            return "explain"

    explain_kw = ["explain", "what does", "describe", "analyze"]
    if any(k in desc for k in explain_kw) and (code or file_path):
        return "explain"

    build_kw = ["build", "make it work", "try and", "attempt"]
    if any(k in desc for k in build_kw):
        return "build"

    return "write"


def _write_code(description: str, language: str, output_path: str, player=None) -> tuple:
    from agent.llm_bridge import agent_llm_call

    lang          = language or "python"
    system_prompt = (
        f"You are an expert {lang} developer. "
        "Output ONLY the code. No explanation, no markdown, no backticks. "
        "Add helpful inline comments. Handle errors and edge cases properly. "
        "Use modern best practices."
    )
    user_prompt = f"Description: {description}\n\nCode:"

    code = agent_llm_call(system_prompt, user_prompt, require_json=False)
    code = _clean_code(code)
    path = _resolve_save_path(output_path, lang)
    _save_file(path, code)
    return code, path


def _fix_code(code: str, error_output: str, description: str) -> str:
    from agent.llm_bridge import agent_llm_call

    system_prompt = (
        "You are an expert debugger. "
        "Return ONLY the corrected code — no explanation, no markdown, no backticks."
    )
    user_prompt = (
        f"Original goal: {description}\n\n"
        f"Error:\n{error_output[:2000]}\n\n"
        f"Broken code:\n{code}\n\n"
        f"Fixed code:"
    )
    return _clean_code(agent_llm_call(system_prompt, user_prompt, require_json=False))


def _run_file(path: Path, args: list, timeout: int) -> str:
    interpreters = {
        ".py":  [sys.executable],
        ".js":  ["node"],
        ".ts":  ["ts-node"],
        ".sh":  ["bash"],
        ".ps1": ["powershell", "-File"],
        ".rb":  ["ruby"],
        ".php": ["php"],
    }
    interp = interpreters.get(path.suffix.lower())
    if not interp:
        return f"No interpreter for {path.suffix}."

    try:
        result = subprocess.run(
            interp + [str(path)] + (args or []),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(path.parent)
        )
        output = result.stdout.strip()
        error  = result.stderr.strip()
        parts  = []
        if output: parts.append(f"Output:\n{output}")
        if error:  parts.append(f"Stderr:\n{error}")
        return "\n\n".join(parts) if parts else "Executed with no output."

    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s."
    except FileNotFoundError:
        return f"Interpreter not found: {interp[0]}."
    except Exception as e:
        return f"Execution error: {e}"


def _build(description, language, output_path, args, timeout, speak=None, player=None) -> str:
    if not description:
        return "Please describe what you want me to build."

    if player:
        player.write_log("[Code] Build started...")

    lang = language or "python"

    try:
        code, path = _write_code(description, lang, output_path, player)
        print(f"[Code] Written: {path}")
    except Exception as e:
        msg = f"Could not write initial code: {e}"
        if speak: speak(msg)
        return msg

    last_output = ""
    for attempt in range(1, MAX_BUILD_ATTEMPTS + 1):
        print(f"[Code] Attempt {attempt}/{MAX_BUILD_ATTEMPTS}")
        if player:
            player.write_log(f"[Code] Attempt {attempt}...")

        last_output = _run_file(path, args, timeout)

        if not _has_error(last_output):
            msg = (
                f"Build complete. "
                f"The code is working after {attempt} attempt{'s' if attempt > 1 else ''}. "
                f"Saved to {path}."
            )
            if speak: speak(msg)
            return f"{msg}\n\nOutput:\n{last_output}"

        print(f"[Code] Error on attempt {attempt}, fixing...")
        if player:
            player.write_log(f"[Code] Fixing (attempt {attempt})...")

        try:
            code = _fix_code(code, last_output, description)
            _save_file(path, code)
        except Exception as e:
            msg = f"Could not fix code on attempt {attempt}: {e}"
            if speak: speak(msg)
            return msg

    msg = (
        f"Unable to build a working version after {MAX_BUILD_ATTEMPTS} attempts. "
        f"Last error: {last_output[:200]}"
    )
    if speak: speak(msg)
    return f"{msg}\n\nLast code saved to: {path}"


def _write_action(description, language, output_path, player) -> str:
    if not description:
        return "Please describe what you want me to write."
    if player:
        player.write_log("[Code] Writing code...")
    try:
        code, path = _write_code(description, language, output_path, player)
        print(f"[Code] Written: {path}")
        return f"Code written. Saved to: {path}\n\nPreview:\n{_preview(code)}"
    except Exception as e:
        return f"Could not generate code: {e}"


def _edit_action(file_path, instruction, player) -> str:
    if not file_path:
        return "Please provide a file path to edit."
    if not instruction:
        return "Please describe what change to make."

    content, err = _read_file(file_path)
    if err:
        return err

    if player:
        player.write_log("[Code] Editing file...")

    from agent.llm_bridge import agent_llm_call

    system_prompt = (
        "You are an expert code editor. "
        "Return ONLY the complete updated code — no explanation, no markdown, no backticks."
    )
    user_prompt = (
        f"Change: {instruction}\n\n"
        f"Original code:\n{content}\n\n"
        f"Updated code:"
    )

    try:
        edited = _clean_code(agent_llm_call(system_prompt, user_prompt, require_json=False))
    except Exception as e:
        return f"Could not edit code: {e}"

    # Show diff preview in output panel before saving
    preview = _preview(edited)
    if player:
        player.append_output(f"[code edit] Changes to {Path(file_path).name}:\n{preview}", "warn")

    # Store a pending action — Sam will only write the file after user confirms
    try:
        from conversation_state import controller, PendingAction
        def _do_save():
            result = _save_file(Path(file_path), edited)
            if player:
                player.write_log(f"[Code] {result}")
                player.append_output(f"[code edit] Saved: {file_path}", "ok")

        controller.set_pending(PendingAction(
            intent="code_edit",
            parameters={"file_path": file_path},
            description=f"Edit {Path(file_path).name}: {instruction[:60]}",
            callback=_do_save,
        ))
        return f"Here's the edit to {Path(file_path).name}. Say 'apply it' to save, or 'cancel' to discard."
    except Exception:
        # Fallback: save directly if pending action system is unavailable
        status = _save_file(Path(file_path), edited)
        return f"File edited. {status}\n\nPreview:\n{preview}"


def _explain_action(file_path, code, player) -> str:
    if file_path and not code:
        code, err = _read_file(file_path)
        if err:
            return err
    if not code:
        return "Please provide code or a file path to explain."

    if player:
        player.write_log("[Code] Analyzing code...")

    from agent.llm_bridge import agent_llm_call

    system_prompt = (
        "Explain what this code does in simple, clear language. "
        "Focus on: what it does, how it works, and any important details. "
        "Be concise — 3 to 6 sentences maximum."
    )
    user_prompt = f"Code:\n{code[:4000]}\n\nExplanation:"

    try:
        return agent_llm_call(system_prompt, user_prompt, require_json=False).strip()
    except Exception as e:
        return f"Could not explain code: {e}"


def _run_action(file_path, args, timeout, player) -> str:
    if not file_path:
        return "Please provide a file path to run."
    p = Path(file_path)
    if not p.exists():
        return f"File not found: {file_path}"
    if player:
        player.write_log(f"[Code] Running {p.name}...")
    return _run_file(p, args, timeout)


def _optimize_action(file_path, code, language, output_path, player) -> str:
    if file_path and not code:
        code, err = _read_file(file_path)
        if err:
            return err
    if not code:
        return "Please provide code or a file path to optimize."

    if player:
        player.write_log("[Code] Optimizing code...")

    from agent.llm_bridge import agent_llm_call

    lang          = language or "python"
    system_prompt = (
        f"You are an expert {lang} developer and code reviewer. "
        "Optimize the following code for performance, readability, and best practices. "
        "Remove dead code, redundant comments, and unnecessary complexity. "
        "Return ONLY the optimized code — no explanation, no markdown, no backticks."
    )
    user_prompt = f"Original code:\n{code[:6000]}\n\nOptimized code:"

    try:
        optimized = _clean_code(agent_llm_call(system_prompt, user_prompt, require_json=False))
    except Exception as e:
        return f"Could not optimize code: {e}"

    save_path = Path(file_path) if file_path else _resolve_save_path(output_path, lang)
    status    = _save_file(save_path, optimized)
    print(f"[Code] Optimized: {save_path}")

    original_lines  = len(code.splitlines())
    optimized_lines = len(optimized.splitlines())
    diff = original_lines - optimized_lines

    return (
        f"Code optimized. {status}\n"
        f"Lines: {original_lines} -> {optimized_lines} "
        f"({'-' if diff > 0 else '+'}{abs(diff)} lines)\n\n"
        f"Preview:\n{_preview(optimized)}"
    )


def _screen_debug_action(description, file_path, player, speak=None) -> str:
    if player:
        player.write_log("[Code] Taking screenshot for analysis...")

    print("[Code] Capturing screen for debug...")

    try:
        from system.screen_vision import capture_screen_base64
        image_b64 = capture_screen_base64()
    except Exception as e:
        return f"Could not capture screen: {e}"

    file_content = ""
    if file_path:
        file_content, err = _read_file(file_path)
        if err:
            print(f"[Code] Could not read file: {err}")

    from agent.llm_bridge import agent_llm_call

    user_question = description or "What error or problem do you see on the screen? How can it be fixed?"
    context       = f"\n\nRelated file content:\n```\n{file_content[:4000]}\n```" if file_content else ""

    system_prompt = (
        "You are an expert programmer and debugger analyzing a screenshot. "
        "Identify any errors, exceptions, or problems visible on the screen. "
        "Explain what is causing the problem and provide a concrete fix. "
        "If there's code visible, show the corrected version. Be specific and actionable."
    )
    user_prompt = f"User's question: {user_question}{context}"

    try:
        analysis = agent_llm_call(
            system_prompt,
            user_prompt,
            require_json=False,
            need_vision=True,
            image_b64=image_b64,
        ).strip()

        print("[Code] Screen analysis complete")

        if file_path and file_content:
            code_match = re.search(r"```[a-zA-Z]*\n(.*?)```", analysis, re.DOTALL)
            if code_match:
                fixed_code = code_match.group(1).strip()
                save_path  = Path(file_path)
                _save_file(save_path, fixed_code)
                analysis += f"\n\nFixed code saved to: {file_path}"
                print(f"[Code] Fixed code saved: {file_path}")

        return analysis

    except Exception as e:
        return f"Screen analysis failed: {e}"


def code_helper(
    parameters:    dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    """
    AI code assistant.

    parameters:
        action      : write | edit | explain | run | build | screen_debug | optimize | auto
        description : What the code should do / what change to make / what to analyze
        language    : Programming language (default: python)
        output_path : Where to save (full path or filename)
        file_path   : Path to existing file (edit/explain/run/build/optimize)
        code        : Raw code string (explain/optimize without a file)
        args        : CLI argument list for run/build
        timeout     : Execution timeout in seconds (default: 30)
    """
    p           = parameters or {}
    action      = p.get("action", "auto").lower().strip()
    description = p.get("description", "").strip()
    language    = p.get("language", "python").strip()
    output_path = p.get("output_path", "").strip()
    file_path   = p.get("file_path", "").strip()
    code        = p.get("code", "").strip()
    args        = p.get("args", [])
    timeout     = int(p.get("timeout", 30))

    if action == "auto":
        action = _detect_intent(description, file_path, code)
        print(f"[Code] Auto-detected: {action}")

    if action == "write":
        return _write_action(description, language, output_path, player)
    elif action == "edit":
        return _edit_action(file_path, description or p.get("instruction", ""), player)
    elif action == "explain":
        return _explain_action(file_path, code, player)
    elif action == "run":
        return _run_action(file_path, args, timeout, player)
    elif action == "build":
        return _build(description, language, output_path, args, timeout, speak, player)
    elif action == "optimize":
        return _optimize_action(file_path, code, language, output_path, player)
    elif action == "screen_debug":
        return _screen_debug_action(description, file_path, player, speak)
    else:
        return f"Unknown action: '{action}'. Use write, edit, explain, run, build, optimize, or screen_debug."
