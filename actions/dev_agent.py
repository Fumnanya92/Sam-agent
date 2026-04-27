# actions/dev_agent.py
# AI-powered development agent — adapted from Mark-XXX-main.
# Gemini calls replaced with agent/llm_bridge.py (Ollama-first, OpenAI fallback).
#
# Flow:
#   Describe project -> AI plans file structure -> Files written one by one
#   -> VSCode opened -> Entry point executed -> Error? -> Identify file -> Fix -> Retry
#   -> Speaks only when done (success or failure)

import subprocess
import sys
import json
import re
import time
from pathlib import Path
from agent.utils import clean_code as _clean_code, has_error as _has_error

# _clean_json is identical to _clean_code
_clean_json = _clean_code

PROJECTS_DIR     = Path.home() / "Desktop" / "SamProjects"
MAX_FIX_ATTEMPTS = 4


def _identify_error_file(error_output: str, project_files: list) -> str | None:
    for line in error_output.splitlines():
        for f in project_files:
            if Path(f).name in line or f in line:
                return f
    return None


def _plan_project(description: str, language: str) -> dict:
    """Ask AI to plan the full project structure as JSON."""
    from agent.llm_bridge import agent_llm_call

    system_prompt = (
        "You are a senior software architect. "
        "Return ONLY a valid JSON object with this exact structure: "
        '{"project_name": "short_snake_case_name", "entry_point": "main.py", '
        '"files": [{"path": "main.py", "description": "what this file does"}], '
        '"run_command": "python main.py", "dependencies": ["package1"]}. '
        "No explanation, no markdown, no backticks. Pure JSON only."
    )
    user_prompt = (
        f"Language: {language}\n"
        f"Description: {description}\n\n"
        f"Rules:\n"
        f"- Keep it simple. Only include files that are truly necessary.\n"
        f"- Entry point must be one of the files listed.\n"
        f"- Use relative paths only.\n\n"
        f"JSON:"
    )

    try:
        raw = agent_llm_call(system_prompt, user_prompt, require_json=True)
        raw = _clean_json(raw)
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner returned invalid JSON: {e}")


def _write_file(
    file_path:           str,
    file_description:    str,
    project_description: str,
    all_files:           list,
    language:            str,
    project_dir:         Path,
) -> str:
    """Write one project file. Returns the generated code."""
    from agent.llm_bridge import agent_llm_call

    file_list = "\n".join(f"  - {f['path']}: {f['description']}" for f in all_files)

    system_prompt = f"You are an expert {language} developer. Output ONLY code — no explanation, no markdown, no backticks."
    user_prompt = (
        f"Project goal: {project_description}\n\n"
        f"All files in this project:\n{file_list}\n\n"
        f"Write ONLY the file: {file_path}\n"
        f"Purpose: {file_description}\n\n"
        f"Rules:\n"
        f"- Import from other project files using relative imports where needed.\n"
        f"- Add helpful inline comments.\n"
        f"- Handle errors properly.\n"
        f"- Use modern best practices.\n\n"
        f"Code for {file_path}:"
    )

    code      = agent_llm_call(system_prompt, user_prompt, require_json=False)
    code      = _clean_code(code)
    full_path = project_dir / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(code, encoding="utf-8")
    print(f"[DevAgent] Written: {file_path}")
    return code


def _install_dependencies(dependencies: list, project_dir: Path) -> str:
    if not dependencies:
        return "No dependencies to install."

    print(f"[DevAgent] Installing: {dependencies}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + dependencies,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=120, cwd=str(project_dir)
        )
        if result.returncode == 0:
            return f"Installed: {', '.join(dependencies)}"
        return f"Install warning: {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return "Dependency install timed out."
    except Exception as e:
        return f"Install error: {e}"


def _open_vscode(project_dir: Path) -> bool:
    vscode_paths = [
        "code",
        r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd".format(
            Path.home().name
        ),
    ]
    for cmd in vscode_paths:
        try:
            subprocess.Popen(
                [cmd, str(project_dir)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True,
            )
            time.sleep(2)
            print(f"[DevAgent] VSCode opened: {project_dir}")
            return True
        except Exception:
            continue
    print("[DevAgent] VSCode not found.")
    return False


def _run_project(run_command: str, project_dir: Path, timeout: int = 30) -> str:
    """Run the project entry point, return output."""
    print(f"[DevAgent] Running: {run_command}")
    try:
        parts = run_command.split()
        if parts[0] == "python":
            parts[0] = sys.executable

        result = subprocess.run(
            parts,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(project_dir)
        )

        output = result.stdout.strip()
        error  = result.stderr.strip()
        parts_out = []
        if output: parts_out.append(f"Output:\n{output}")
        if error:  parts_out.append(f"Stderr:\n{error}")
        return "\n\n".join(parts_out) if parts_out else "Ran with no output."

    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s. (Long-running app may be working fine.)"
    except FileNotFoundError as e:
        return f"Command not found: {e}"
    except Exception as e:
        return f"Run error: {e}"


def _fix_file(
    file_path:           str,
    current_code:        str,
    error_output:        str,
    project_description: str,
    all_files:           list,
    language:            str,
    project_dir:         Path,
) -> str:
    """Ask AI to fix a specific file based on error output."""
    from agent.llm_bridge import agent_llm_call

    file_list = "\n".join(f"  - {f['path']}: {f['description']}" for f in all_files)

    system_prompt = (
        f"You are an expert {language} debugger. "
        "Return ONLY the fixed code — no explanation, no markdown, no backticks."
    )
    user_prompt = (
        f"Project goal: {project_description}\n\n"
        f"All files:\n{file_list}\n\n"
        f"File to fix: {file_path}\n\n"
        f"Error output:\n{error_output[:3000]}\n\n"
        f"Current code:\n{current_code}\n\n"
        f"Fixed code:"
    )

    fixed = agent_llm_call(system_prompt, user_prompt, require_json=False)
    fixed = _clean_code(fixed)

    full_path = project_dir / file_path
    full_path.write_text(fixed, encoding="utf-8")
    print(f"[DevAgent] Fixed: {file_path}")
    return fixed


def _build_project(
    description:  str,
    language:     str,
    project_name: str,
    timeout:      int,
    speak=None,
    player=None,
) -> str:
    """Full build loop: Plan -> Write files -> Install deps -> Open VSCode -> Run -> Fix loop."""

    def log(msg: str):
        print(f"[DevAgent] {msg}")
        if player:
            player.write_log(f"[DevAgent] {msg}")

    log("Planning project structure...")
    try:
        plan = _plan_project(description, language)
    except ValueError as e:
        msg = f"Planning failed: {e}"
        if speak: speak(msg)
        return msg

    proj_name   = project_name or plan.get("project_name", "sam_project")
    proj_name   = re.sub(r"[^\w\-]", "_", proj_name)
    project_dir = PROJECTS_DIR / proj_name
    project_dir.mkdir(parents=True, exist_ok=True)

    files        = plan.get("files", [])
    entry_point  = plan.get("entry_point", "main.py")
    run_command  = plan.get("run_command", f"python {entry_point}")
    dependencies = plan.get("dependencies", [])

    log(f"Project: {proj_name} | Files: {len(files)} | Entry: {entry_point}")

    file_codes: dict = {}

    for file_info in files:
        file_path = file_info.get("path", "")
        file_desc = file_info.get("description", "")
        if not file_path:
            continue

        log(f"Writing {file_path}...")
        try:
            code = _write_file(
                file_path, file_desc, description,
                files, language, project_dir
            )
            file_codes[file_path] = code
        except Exception as e:
            log(f"Failed to write {file_path}: {e}")
            continue

    if not file_codes:
        msg = "I could not write any files for this project."
        if speak: speak(msg)
        return msg

    if dependencies:
        log(f"Installing dependencies: {dependencies}")
        _install_dependencies(dependencies, project_dir)

    _open_vscode(project_dir)

    last_output = ""
    for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
        log(f"Running project (attempt {attempt}/{MAX_FIX_ATTEMPTS})...")

        last_output = _run_project(run_command, project_dir, timeout)
        log(f"Output: {last_output[:150]}")

        if not _has_error(last_output):
            msg = (
                f"Project '{proj_name}' is working. "
                f"Built in {attempt} attempt{'s' if attempt > 1 else ''}. "
                f"Opened in VSCode at {project_dir}."
            )
            if speak: speak(msg)
            return f"{msg}\n\nOutput:\n{last_output}"

        if attempt == MAX_FIX_ATTEMPTS:
            break

        error_file = _identify_error_file(last_output, list(file_codes.keys()))
        if not error_file:
            error_file = entry_point

        log(f"Error in '{error_file}', fixing...")
        try:
            fixed = _fix_file(
                error_file,
                file_codes.get(error_file, ""),
                last_output,
                description,
                files,
                language,
                project_dir,
            )
            file_codes[error_file] = fixed
        except Exception as e:
            log(f"Fix failed: {e}")

    msg = (
        f"Unable to get '{proj_name}' working after {MAX_FIX_ATTEMPTS} attempts. "
        f"The project is saved at {project_dir} — you can open it in VSCode and check manually."
    )
    if speak: speak(msg)
    return f"{msg}\n\nLast error:\n{last_output[:500]}"


def dev_agent(
    parameters:    dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    """
    AI development agent.

    parameters:
        description  : What the project should do (required)
        language     : Programming language (default: python)
        project_name : Optional folder name (auto-generated if not given)
        timeout      : Run timeout in seconds (default: 30)
    """
    p            = parameters or {}
    description  = p.get("description", "").strip()
    language     = p.get("language", "python").strip()
    project_name = p.get("project_name", "").strip()
    timeout      = int(p.get("timeout", 30))

    if not description:
        return "Please describe the project you want me to build."

    return _build_project(
        description  = description,
        language     = language,
        project_name = project_name,
        timeout      = timeout,
        speak        = speak,
        player       = player,
    )
