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
    "You are an expert Python developer. "
    "Write clean, complete, working Python code. "
    "Use standard library + common packages. "
    "Install missing packages with subprocess + pip if needed. "
    "Return ONLY the Python code. No explanation, no markdown, no backticks."
)

_SUMMARIZE_SYSTEM = (
    "You are a helpful assistant. Write a single natural sentence summarizing "
    "what was accomplished. Be direct and positive."
)


def _run_generated_code(description: str, speak: Callable | None = None) -> str:
    """Generate Python code for an arbitrary task and execute it."""
    if speak:
        speak("Writing custom code for this task.")

    home = Path.home()
    code = agent_llm_call(
        _CODEGEN_SYSTEM,
        f"Write Python code to accomplish this task:\n\n{description}",
        require_json=False,
    )
    code = re.sub(r"```(?:python)?", "", code).strip().rstrip("`").strip()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    print(f"[Executor] Running generated code: {tmp_path}")

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True,
            timeout=120, cwd=str(home),
        )
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    output = result.stdout.strip()
    error  = result.stderr.strip()

    if result.returncode == 0 and output:
        return output
    elif result.returncode == 0:
        return "Task completed successfully."
    elif error:
        raise RuntimeError(f"Code error: {error[:400]}")
    return "Completed."


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
                            completed_steps.append(step)
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
                return self._summarize(goal, completed_steps, speak)

            if replan_attempts >= self.MAX_REPLAN_ATTEMPTS:
                msg = f"Task could not be completed after {replan_attempts} attempts."
                if speak:
                    speak(msg)
                return msg

            if speak:
                speak("Adjusting my approach.")

            replan_attempts += 1
            plan = replan(goal, completed_steps, failed_step, failed_error)

    def _summarize(self, goal: str, completed_steps: list, speak: Callable | None) -> str:
        fallback  = f"All done. Completed {len(completed_steps)} steps for: {goal[:60]}."
        steps_str = "\n".join(f"- {s.get('description', '')}" for s in completed_steps)
        prompt    = (
            f'User goal: "{goal}"\n'
            f"Completed steps:\n{steps_str}\n\n"
            "Write a single natural sentence summarizing what was accomplished. "
            "Be concise and positive."
        )
        try:
            summary = agent_llm_call(_SUMMARIZE_SYSTEM, prompt, require_json=False)
            summary = summary.strip() or fallback
            if speak:
                speak(summary)
            return summary
        except Exception:
            if speak:
                speak(fallback)
            return fallback
