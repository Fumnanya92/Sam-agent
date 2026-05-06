# agent/executor.py
# Runs a plan step-by-step with retries, context injection, and replanning.
# Gemini replaced with Sam's llm_bridge. Import paths fixed for Sam's layout.

import json
import re
import sys
import threading
import subprocess
import tempfile
import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from agent.planner       import create_plan, replan
from agent.error_handler import analyze_error, generate_fix, ErrorDecision
from agent.llm_bridge    import agent_llm_call


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE_DIR = get_base_dir()

_CODEGEN_SYSTEM = (
    "You are an expert Python developer writing scripts that ACTUALLY perform "
    "the task on the user's machine. "
    "Write clean, complete, working Python code that runs as a standalone "
    "script (a __main__ entry point is fine). "
    "Use standard library + common packages. "
    "Install missing packages with subprocess + pip if needed. "
    "\n\n"
    "DO THE THING. Do not just open windows, search for instructions, or "
    "describe how it would be done. If the user said 'empty my recycle bin', "
    "your code must actually empty it (e.g. on Windows: "
    "`subprocess.run(['powershell','-NoProfile','-Command','Clear-RecycleBin -Force -ErrorAction SilentlyContinue'])` "
    "or `winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=False)`). "
    "If the user said 'kill all chrome processes', kill them — don't open Task Manager. "
    "\n\n"
    "VERIFY AND REPORT. After the action, your script MUST print exactly ONE "
    "of these on the LAST line of stdout: \n"
    "  VERIFIED: <one-line description of what changed and how you measured it>\n"
    "  NOT_DONE: <one-line reason — say WHY you couldn't actually do it>\n"
    "Examples that count as VERIFIED: 'VERIFIED: emptied 12 items from recycle bin (was 12, now 0)', "
    "'VERIFIED: killed 7 chrome.exe processes', 'VERIFIED: deleted 23 .tmp files (148MB freed)'. "
    "If you only opened a window, ran a search, or printed instructions, that is NOT_DONE — "
    "say so honestly. The user prefers an honest 'I couldn't' over a confident lie. "
    "\n\n"
    "Print useful intermediate output too, but the final line must be the "
    "VERIFIED/NOT_DONE marker. The summarizer reads it. "
    "\n\n"
    "NEVER paste the code into the chat. The runtime saves to "
    "~/.sam/scripts/ and executes it for you. Return ONLY the Python code. "
    "No explanation, no markdown, no backticks."
)

_SUMMARIZE_SYSTEM = (
    "You are a helpful assistant. Write a single natural sentence summarizing "
    "what was accomplished. Be direct and positive."
)


_SCRIPTS_DIR = Path.home() / ".sam" / "scripts"


def _save_generated_script(code: str, description: str) -> Path:
    """Persist generated code to ~/.sam/scripts/ so Sam can find/rerun it."""
    _SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    # Build a friendly slug from the description so the filename is meaningful.
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", description.lower()).strip("_")[:40] or "script"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = _SCRIPTS_DIR / f"sam_{slug}_{stamp}.py"
    target.write_text(code, encoding="utf-8")
    # Register with the file-controller registry so "run my last script" works.
    try:
        from actions.file_controller import _register_written
        _register_written(target, "create_file")
    except Exception:
        pass
    return target


def run_script(path: str | Path, timeout: int = 120) -> str:
    """Run a Python script by absolute path and return stdout/stderr summary."""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return f"Script not found: {target}"
    home = Path.home()
    result = subprocess.run(
        [sys.executable, str(target)],
        capture_output=True, text=True,
        timeout=timeout, cwd=str(home),
    )
    output = (result.stdout or "").strip()
    error  = (result.stderr or "").strip()
    header = f"[ran {target.name} → {target}]\n"
    if result.returncode == 0 and output:
        return header + output
    if result.returncode == 0:
        return header + "(no output — script completed successfully)"
    if error:
        raise RuntimeError(f"Code error in {target}: {error[:400]}")
    return header + "Completed."


def run_last_script(extension: str = "py", timeout: int = 120) -> str:
    """Re-run the most recently written script (default: last .py file)."""
    try:
        from actions.file_controller import get_last_written_file
    except Exception as e:
        return f"Could not access file registry: {e}"
    entry = get_last_written_file(extension)
    if not entry:
        return f"No recent .{extension.lstrip('.')} file to run."
    return run_script(entry["path"], timeout=timeout)


def _run_generated_code(description: str, speak: Callable | None = None) -> str:
    """Generate Python code for an arbitrary task and execute it."""
    if speak:
        speak("Writing custom code for this task.")

    code = agent_llm_call(
        _CODEGEN_SYSTEM,
        f"Write Python code to accomplish this task:\n\n{description}",
        require_json=False,
    )
    code = re.sub(r"```(?:python)?", "", code).strip().rstrip("`").strip()

    # Persist to ~/.sam/scripts so Sam can rerun / locate it later. This
    # replaces the old tempfile-and-delete flow that lost the file the moment
    # it finished executing.
    script_path = _save_generated_script(code, description)
    print(f"[Executor] Saved generated code to: {script_path}")

    try:
        return run_script(script_path)
    except RuntimeError:
        # Bubble up so the upstream replanner sees the error,
        # but the script stays on disk for inspection.
        raise


def _inject_context(params: dict, tool: str, step_results: dict, goal: str = "") -> dict:
    """For file_controller write steps, inject prior step results as content."""
    if not step_results:
        return params
    params = dict(params)
    if tool == "file_controller" and params.get("action") in ("write", "create_file"):
        content = params.get("content", "")
        if not content or len(content) < 50:
            all_results = [
                v for v in step_results.values()
                if v and len(v) > 100 and v not in ("Done.", "Completed.")
            ]
            if all_results:
                params["content"] = "\n\n---\n\n".join(all_results)
                print("[Executor] Injected prior step results as content")
    return params


def _call_tool(tool: str, parameters: dict, speak: Callable | None) -> str:
    """Dispatch a tool name to the correct action module."""

    if tool == "open_app":
        from actions.open_app import open_app
        return open_app(parameters=parameters, player=None) or "Done."

    elif tool == "web_search":
        from actions.web_search import web_search
        return web_search(parameters=parameters, player=None) or "Done."

    elif tool == "browser_control":
        from actions.browser_control import browser_control
        return browser_control(parameters=parameters, player=None) or "Done."

    elif tool == "file_controller":
        from actions.file_controller import file_controller
        return file_controller(parameters=parameters, player=None) or "Done."

    elif tool == "cmd_control":
        from actions.cmd_control import cmd_control
        return cmd_control(parameters=parameters, player=None) or "Done."

    elif tool == "code_helper":
        from actions.code_helper import code_helper
        return code_helper(parameters=parameters, player=None, speak=speak) or "Done."

    elif tool == "dev_agent":
        from actions.dev_agent import dev_agent
        return dev_agent(parameters=parameters, player=None, speak=speak) or "Done."

    elif tool == "screen_process":
        # Sam's screen vision module (replaces Mark's screen_processor)
        from system.screen_vision import analyze_screen_for_errors
        from config.api_keys import get_openai_key  # best-effort
        try:
            import json as _json
            cfg = _BASE_DIR / "config" / "api_keys.json"
            key = _json.loads(cfg.read_text())["openai_api_key"]
            return analyze_screen_for_errors(key) or "Screen analyzed."
        except Exception as e:
            return f"Screen vision error: {e}"

    elif tool == "send_message":
        from actions.send_message import send_message
        return send_message(parameters=parameters, player=None) or "Done."

    elif tool in ("reminder", "set_reminder"):
        from actions.windows_alarm import set_windows_alarm
        from datetime import datetime as _dt, timedelta as _td
        msg  = parameters.get("message", parameters.get("text", "Reminder"))
        date = parameters.get("date", "")
        time_str = parameters.get("time", "")
        when = f"{date} {time_str}".strip() if date or time_str else ""
        try:
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%H:%M", "%H:%M:%S"):
                try:
                    alarm_dt = _dt.strptime(when, fmt)
                    if fmt in ("%H:%M", "%H:%M:%S"):
                        now = _dt.now()
                        alarm_dt = alarm_dt.replace(year=now.year, month=now.month, day=now.day)
                    break
                except ValueError:
                    continue
            else:
                alarm_dt = _dt.now() + _td(minutes=5)
            ok, result_msg = set_windows_alarm(alarm_dt, label=msg)
            return result_msg or "Reminder set."
        except Exception as e:
            return f"Could not set reminder: {e}"

    elif tool == "youtube_video":
        from actions.youtube_video import youtube_video
        return youtube_video(parameters=parameters, player=None) or "Done."

    elif tool == "weather_report":
        from actions.weather_report import weather_action
        return weather_action(parameters=parameters, player=None) or "Done."

    elif tool == "computer_settings":
        from actions.computer_settings import computer_settings
        return computer_settings(parameters=parameters, player=None) or "Done."

    elif tool == "desktop_control":
        from actions.desktop import desktop_control
        return desktop_control(parameters=parameters, player=None) or "Done."

    elif tool == "computer_control":
        from actions.computer_control import computer_control
        return computer_control(parameters=parameters, player=None) or "Done."

    elif tool == "flight_finder":
        from actions.flight_finder import flight_finder
        return flight_finder(parameters=parameters, player=None, speak=speak) or "Done."

    elif tool == "generated_code":
        description = parameters.get("description", "")
        if not description:
            raise ValueError("generated_code requires a 'description' parameter.")
        return _run_generated_code(description, speak=speak)

    else:
        print(f"[Executor] Unknown tool '{tool}' — falling back to generated_code")
        return _run_generated_code(f"Accomplish this task: {parameters}", speak=speak)


class AgentExecutor:

    MAX_REPLAN_ATTEMPTS = 2

    def execute(
        self,
        goal:        str,
        speak:       Callable | None        = None,
        cancel_flag: threading.Event | None = None,
    ) -> str:
        print(f"\n[Executor] Goal: {goal}")

        replan_attempts = 0
        completed_steps: list = []
        skipped_steps:   list = []      # honest accounting — steps we gave up on
        step_results:    dict = {}
        plan = create_plan(goal)

        while True:
            steps = plan.get("steps", [])

            if not steps:
                msg = "I couldn't create a valid plan for this task."
                if speak:
                    speak(msg)
                return msg

            success      = True
            failed_step  = None
            failed_error = ""

            for step in steps:
                if cancel_flag and cancel_flag.is_set():
                    if speak:
                        speak("Task cancelled.")
                    return "Task cancelled."

                step_num = step.get("step", "?")
                tool     = step.get("tool", "generated_code")
                desc     = step.get("description", "")
                params   = step.get("parameters", {})

                params = _inject_context(params, tool, step_results, goal=goal)

                print(f"\n[Executor] Step {step_num}: [{tool}] {desc}")

                attempt = 1
                step_ok = False

                while attempt <= 3:
                    if cancel_flag and cancel_flag.is_set():
                        break
                    try:
                        result             = _call_tool(tool, params, speak)
                        step_results[step_num] = result
                        completed_steps.append(step)
                        print(f"[Executor] Step {step_num} done: {str(result)[:100]}")
                        step_ok = True
                        break

                    except Exception as e:
                        error_msg = str(e)
                        print(f"[Executor] Step {step_num} attempt {attempt} failed: {error_msg}")

                        recovery = analyze_error(step, error_msg, attempt=attempt)
                        decision = recovery["decision"]
                        user_msg = recovery.get("user_message", "")

                        if speak and user_msg:
                            speak(user_msg)

                        if decision == ErrorDecision.RETRY:
                            attempt += 1
                            import time as _time
                            _time.sleep(2)
                            continue

                        elif decision == ErrorDecision.SKIP:
                            print(f"[Executor] Skipping step {step_num}")
                            # IMPORTANT: skipped steps are NOT successes. Track
                            # them separately so the summarizer can be honest
                            # about what actually happened. Counting them as
                            # completed is how Sam ends up claiming success on
                            # tasks he never did.
                            skipped_steps.append(step)
                            step_results[step_num] = (
                                f"SKIPPED: {error_msg[:200]}"
                            )
                            step_ok = True
                            break

                        elif decision == ErrorDecision.ABORT:
                            msg = f"Task aborted. {recovery.get('reason', '')}"
                            if speak:
                                speak(msg)
                            return msg

                        else:  # REPLAN
                            fix_suggestion = recovery.get("fix_suggestion", "")
                            if fix_suggestion and tool != "generated_code":
                                try:
                                    fixed_step = generate_fix(step, error_msg, fix_suggestion)
                                    if speak:
                                        speak("Trying an alternative approach.")
                                    res = _call_tool(
                                        fixed_step["tool"],
                                        fixed_step["parameters"],
                                        speak,
                                    )
                                    step_results[step_num] = res
                                    completed_steps.append(step)
                                    step_ok = True
                                    break
                                except Exception as fix_err:
                                    print(f"[Executor] Fix failed: {fix_err}")

                            failed_step  = step
                            failed_error = error_msg
                            success      = False
                            break

                if not step_ok and not failed_step:
                    failed_step  = step
                    failed_error = "Max retries exceeded"
                    success      = False

                if not success:
                    break

            if success:
                return self._summarize(
                    goal, completed_steps, skipped_steps, step_results, speak,
                )

            if replan_attempts >= self.MAX_REPLAN_ATTEMPTS:
                msg = f"Task could not be completed after {replan_attempts} attempts."
                if speak:
                    speak(msg)
                return msg

            if speak:
                speak("Adjusting my approach.")

            replan_attempts += 1
            plan = replan(goal, completed_steps, failed_step, failed_error)

    def _summarize(
        self,
        goal: str,
        completed_steps: list,
        skipped_steps: list,
        step_results: dict,
        speak: Callable | None,
    ) -> str:
        # Build an evidence trail the summarizer LLM can actually reason over.
        # Critically: include the actual step OUTPUTS, not just the planner's
        # descriptions of what each step was supposed to do. Without this, the
        # summarizer hallucinates success based on the plan's intent — exactly
        # the bug that made Sam claim he emptied the recycle bin when he had
        # only opened the window.
        def _format_step(s: dict, marker: str) -> str:
            num = s.get("step", "?")
            desc = s.get("description", "")
            tool = s.get("tool", "")
            raw = step_results.get(num, "")
            out = str(raw)[:400] if raw else "(no output)"
            return f"  {marker} step {num} [{tool}] {desc}\n      → {out}"

        completed_lines = [_format_step(s, "✓") for s in completed_steps]
        skipped_lines   = [_format_step(s, "⚠ SKIPPED") for s in skipped_steps]

        # Detect explicit "didn't actually do it" markers from generated_code.
        haystack = "\n".join(str(v) for v in step_results.values()).upper()
        likely_failed = any(
            marker in haystack
            for marker in ("NOT_DONE", "TASK_NOT_COMPLETED", "NOT COMPLETED",
                           "FAILED:", "ERROR:")
        )
        likely_inconclusive = (
            len(skipped_steps) > 0
            or any(
                str(v).strip() in ("", "Done.", "Completed.", "(no output)")
                for v in step_results.values()
            )
        )

        fallback = (
            f"Completed {len(completed_steps)} of {len(completed_steps) + len(skipped_steps)} "
            f"step(s) for: {goal[:60]}."
            + (f" {len(skipped_steps)} skipped." if skipped_steps else "")
        )

        prompt_lines = [
            f'User goal: "{goal}"',
            "",
            "Step evidence (description + actual output):",
            *completed_lines,
        ]
        if skipped_lines:
            prompt_lines += ["", "Steps that were skipped (NOT done):", *skipped_lines]
        prompt_lines += [
            "",
            "Write a single short sentence summarizing what ACTUALLY happened, "
            "based on the step outputs above — not on the step descriptions. "
            "Rules:",
            "- If the outputs do not provide concrete evidence the user's goal "
            "  was achieved, DO NOT claim it was achieved. Say what was done "
            "  and what was not.",
            "- If any step was SKIPPED or output is empty / 'Done.' / "
            "  'Completed.' for an action that should produce evidence, treat "
            "  the goal as NOT verified and say so plainly.",
            "- If a step output contains 'NOT_DONE', 'FAILED:', or 'ERROR:', "
            "  surface that to the user — do not paper over it.",
            "- Be honest. Never say a task is done when the evidence is "
            "  inconclusive. Better to say 'I tried X and Y; please verify' "
            "  than to claim success.",
        ]
        prompt = "\n".join(prompt_lines)

        try:
            summary = agent_llm_call(_SUMMARIZE_SYSTEM, prompt, require_json=False)
            summary = summary.strip() or fallback

            # Defensive guardrail: if our evidence shows the task likely
            # didn't happen but the summarizer still claims unconditional
            # success, prepend an honesty caveat so the user is warned.
            if (likely_failed or likely_inconclusive):
                low = summary.lower()
                makes_success_claim = any(
                    p in low for p in (
                        "all set", "all done", "done.", "emptied", "completed.",
                        "successfully", "task complete", "you're all set",
                    )
                )
                if makes_success_claim:
                    summary = (
                        "I attempted the task but the evidence is "
                        "inconclusive — please verify it actually happened. "
                        + summary
                    )

            if speak:
                speak(summary)
            return summary
        except Exception:
            if speak:
                speak(fallback)
            return fallback
