"""
core/capabilities.py — Single source of truth for everything Sam can do.

Each Capability entry declares:
  name         — unique slug
  description  — human-readable summary
  intents      — all LLM intent strings that trigger this (first is canonical)
  handler      — function name in intents/handlers.py (or "skill:<module>" for skill-loader)
  status       — working | broken | wip | planned
  last_verified — ISO date of last successful e2e test
  test         — path to the capability's test file
  dependencies — external things this needs (browser profile, service, etc.)
  tags         — for filtering in the dashboard
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

Status = Literal["working", "broken", "wip", "planned"]


@dataclass
class Capability:
    name: str
    description: str
    intents: list[str]
    handler: str                              # "_handle_*" or "skill:<module_name>"
    status: Status = "working"
    last_verified: str = ""
    test: str = ""
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


# ── Registry ──────────────────────────────────────────────────────────────────
# Order: messaging → system → productivity → dev → browser → media → misc

REGISTRY: list[Capability] = [

    # ── Messaging ──────────────────────────────────────────────────────────
    Capability(
        name="send_message",
        description="Send a message via WhatsApp or other platform",
        intents=["send_message"],
        handler="_handle_send_message",
        status="working",
        tags=["messaging"],
    ),
    Capability(
        name="whatsapp_summary",
        description="Summarise recent unread WhatsApp messages",
        intents=["whatsapp_summary", "check_whatsapp"],
        handler="_handle_whatsapp_summary",
        status="broken",
        last_verified="",
        test="tests/test_whatsapp_capability.py",
        dependencies=["chrome_profile", "whatsapp_web_session"],
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="read_messages",
        description="Read unread messages from WhatsApp",
        intents=["read_messages"],
        handler="_handle_read_messages",
        status="broken",
        dependencies=["chrome_profile", "whatsapp_web_session"],
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="whatsapp_ready",
        description="Continue WhatsApp session after QR scan",
        intents=["whatsapp_ready"],
        handler="_handle_whatsapp_ready",
        status="broken",
        dependencies=["chrome_profile", "whatsapp_web_session"],
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="open_whatsapp_chat",
        description="Open a specific WhatsApp chat by contact name",
        intents=["open_whatsapp_chat"],
        handler="_handle_open_whatsapp_chat",
        status="broken",
        dependencies=["chrome_profile", "whatsapp_web_session"],
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="read_whatsapp",
        description="Read the currently open WhatsApp chat",
        intents=["read_whatsapp"],
        handler="_handle_read_whatsapp",
        status="broken",
        dependencies=["chrome_profile", "whatsapp_web_session"],
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="reply_whatsapp",
        description="Generate and send a reply in the open WhatsApp chat",
        intents=["reply_whatsapp"],
        handler="_handle_reply_whatsapp",
        status="broken",
        dependencies=["chrome_profile", "whatsapp_web_session"],
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="reply_to_contact",
        description="Open a specific contact's chat and draft a reply",
        intents=["reply_to_contact"],
        handler="_handle_reply_to_contact",
        status="broken",
        dependencies=["chrome_profile", "whatsapp_web_session"],
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="confirm_send",
        description="Confirm sending a drafted WhatsApp message",
        intents=["confirm_send"],
        handler="_handle_confirm_send",
        status="working",
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="cancel_reply",
        description="Cancel a drafted WhatsApp reply",
        intents=["cancel_reply"],
        handler="_handle_cancel_reply",
        status="working",
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="edit_reply",
        description="Edit a drafted WhatsApp reply with new text",
        intents=["edit_reply"],
        handler="_handle_edit_reply",
        status="working",
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="whatsapp_call",
        description="Initiate a WhatsApp call with a contact",
        intents=["whatsapp_call"],
        handler="_handle_whatsapp_call",
        status="broken",
        dependencies=["chrome_profile", "whatsapp_web_session"],
        tags=["messaging", "whatsapp"],
    ),
    Capability(
        name="send_email",
        description="Send an email via workspace (Gmail)",
        intents=["send_email_workspace", "compose_email", "email_contact"],
        handler="_handle_send_email_workspace",
        status="wip",
        tags=["messaging", "email"],
    ),
    Capability(
        name="read_email",
        description="Read recent unread emails",
        intents=["read_email"],
        handler="_handle_read_email",
        status="wip",
        tags=["messaging", "email"],
    ),
    Capability(
        name="send_to_channel",
        description="Post a message to Discord or Telegram channel",
        intents=["send_to_channel"],
        handler="_handle_send_to_channel",
        status="working",
        dependencies=["DISCORD_BOT_TOKEN or TELEGRAM_BOT_TOKEN"],
        tags=["messaging", "channels"],
    ),

    # ── System ─────────────────────────────────────────────────────────────
    Capability(
        name="get_time",
        description="Tell the current time and date",
        intents=["get_time"],
        handler="_handle_get_time",
        status="working",
        tags=["system"],
    ),
    Capability(
        name="list_processes",
        description="List currently running user-visible processes",
        intents=["list_processes"],
        handler="_handle_list_processes",
        status="working",
        tags=["system"],
    ),
    Capability(
        name="system_status",
        description="Report CPU, RAM, battery, disk usage",
        intents=["system_status"],
        handler="_handle_system_status",
        status="working",
        tags=["system"],
    ),
    Capability(
        name="kill_process",
        description="Terminate a running process by name",
        intents=["kill_process"],
        handler="_handle_kill_process",
        status="working",
        tags=["system"],
    ),
    Capability(
        name="performance_mode",
        description="Identify and report the heaviest running processes",
        intents=["performance_mode"],
        handler="_handle_performance_mode",
        status="working",
        tags=["system"],
    ),
    Capability(
        name="auto_mode",
        description="Enable autonomous system management mode",
        intents=["auto_mode"],
        handler="_handle_auto_mode",
        status="working",
        tags=["system"],
    ),
    Capability(
        name="system_trend",
        description="Show system performance trend over time",
        intents=["system_trend"],
        handler="_handle_system_trend",
        status="working",
        tags=["system"],
    ),
    Capability(
        name="screen_vision",
        description="Capture and analyze the current screen",
        intents=["screen_vision"],
        handler="_handle_screen_vision",
        status="working",
        tags=["system", "vision"],
    ),
    Capability(
        name="debug_screen",
        description="Analyze the screen for errors and suggest fixes",
        intents=["debug_screen"],
        handler="_handle_debug_screen",
        status="working",
        tags=["system", "vision", "dev"],
    ),
    Capability(
        name="vscode_mode",
        description="Analyze open code in VS Code and suggest improvements",
        intents=["vscode_mode"],
        handler="_handle_vscode_mode",
        status="working",
        tags=["system", "dev"],
    ),
    Capability(
        name="computer_settings",
        description="Control system settings: volume, brightness, dark mode, WiFi, etc.",
        intents=["computer_settings"],
        handler="_handle_computer_settings",
        status="working",
        tags=["system"],
    ),
    Capability(
        name="computer_control",
        description="Low-level screen/GUI automation: click, type, drag, hotkey",
        intents=["computer_control"],
        handler="_handle_computer_control",
        status="working",
        tags=["system", "automation"],
    ),
    Capability(
        name="desktop_control",
        description="Manage the desktop: wallpaper, organize, clean, list files",
        intents=["desktop_control"],
        handler="_handle_desktop_control",
        status="working",
        tags=["system"],
    ),
    Capability(
        name="quick_command",
        description="Run a quick safe shell command (IP, disk, network, etc.)",
        intents=["quick_command"],
        handler="_handle_quick_command",
        status="working",
        tags=["system", "terminal"],
    ),
    Capability(
        name="send_notification",
        description="Send a Windows desktop notification popup",
        intents=["send_notification"],
        handler="_handle_send_notification",
        status="working",
        tags=["system"],
    ),

    # ── Apps & Files ───────────────────────────────────────────────────────
    Capability(
        name="open_app",
        description="Open an application by name",
        intents=["open_app"],
        handler="_handle_open_app",
        status="working",
        tags=["apps"],
    ),
    Capability(
        name="project_index",
        description="Auto-discover and index project directories on disk for fast fuzzy lookup",
        intents=[],
        handler="",
        status="working",
        tags=["dev", "system"],
        dependencies=[],
    ),
    Capability(
        name="open_project",
        description="Find a project folder and open it in VS Code",
        intents=["open_project"],
        handler="_handle_open_project",
        status="working",
        tags=["apps", "dev"],
        dependencies=["project_index"],
    ),
    Capability(
        name="file_manage",
        description="File operations: list, create, delete, move, copy, rename, read, write, find",
        intents=["file_manage"],
        handler="_handle_file_manage",
        status="working",
        tags=["files"],
    ),
    Capability(
        name="find_file",
        description="Search for a file by name or pattern",
        intents=["find_file"],
        handler="_handle_find_file",
        status="working",
        tags=["files"],
    ),
    Capability(
        name="open_file",
        description="Open a specific file",
        intents=["open_file"],
        handler="_handle_open_file",
        status="working",
        tags=["files"],
    ),
    Capability(
        name="housekeeping",
        description="Organize downloads, archive screenshots, clean temp files",
        intents=["housekeeping", "organise_downloads", "organize_downloads",
                 "housekeeping_report", "archive_screenshots", "clean_temp"],
        handler="_handle_housekeeping",
        status="working",
        tags=["files"],
    ),
    Capability(
        name="organize_files",
        description="Intelligently organize files on the desktop or in a folder",
        intents=["organize_files", "prepare_workspace"],
        handler="_handle_organize_files",
        status="working",
        tags=["files"],
    ),
    Capability(
        name="start_dictation",
        description="Open Notepad for voice dictation",
        intents=["start_dictation"],
        handler="_handle_start_dictation",
        status="working",
        tags=["productivity"],
    ),
    Capability(
        name="read_clipboard",
        description="Read what's currently on the clipboard",
        intents=["read_clipboard"],
        handler="_handle_read_clipboard",
        status="working",
        tags=["productivity"],
    ),
    Capability(
        name="create_note",
        description="Create and save a note with title and content",
        intents=["create_note"],
        handler="_handle_create_note",
        status="working",
        tags=["productivity"],
    ),
    Capability(
        name="log_entry",
        description="Append an entry to the session log",
        intents=["log_entry"],
        handler="_handle_log_entry",
        status="working",
        tags=["productivity"],
    ),

    # ── Reminders & Calendar ───────────────────────────────────────────────
    Capability(
        name="set_reminder",
        description="Set a timed reminder with a label",
        intents=["set_reminder"],
        handler="_handle_set_reminder",
        status="working",
        tags=["reminders"],
    ),
    Capability(
        name="set_alarm",
        description="Set a system alarm at a specific clock time",
        intents=["set_alarm"],
        handler="_handle_set_alarm",
        status="working",
        tags=["reminders"],
    ),
    Capability(
        name="list_reminders",
        description="List all active reminders",
        intents=["list_reminders"],
        handler="_handle_list_reminders",
        status="working",
        tags=["reminders"],
    ),
    Capability(
        name="cancel_reminder",
        description="Cancel a reminder by label or ID",
        intents=["cancel_reminder"],
        handler="_handle_cancel_reminder",
        status="working",
        tags=["reminders"],
    ),
    Capability(
        name="calendar_today",
        description="Show today's calendar events",
        intents=["calendar_today", "my_schedule", "check_calendar"],
        handler="_handle_calendar_today",
        status="wip",
        dependencies=["Google Calendar auth"],
        tags=["calendar"],
    ),
    Capability(
        name="next_meeting",
        description="Tell the user their next upcoming meeting",
        intents=["next_meeting"],
        handler="_handle_next_meeting",
        status="wip",
        dependencies=["Google Calendar auth"],
        tags=["calendar"],
    ),

    # ── Web & Search ───────────────────────────────────────────────────────
    Capability(
        name="search",
        description="Search the web for information",
        intents=["search"],
        handler="_handle_search",
        status="working",
        tags=["web"],
    ),
    Capability(
        name="weather_report",
        description="Get weather for a city",
        intents=["weather_report"],
        handler="_handle_weather_report",
        status="working",
        tags=["web"],
    ),
    Capability(
        name="browser_control",
        description="Control the browser: navigate, click, fill forms, scrape",
        intents=["browser_control"],
        handler="_handle_browser_control",
        status="working",
        tags=["web", "browser"],
    ),
    Capability(
        name="aircraft_radar",
        description="Show live aircraft over a city or country",
        intents=["aircraft_radar"],
        handler="_handle_aircraft_radar",
        status="working",
        tags=["web"],
    ),
    Capability(
        name="find_flights",
        description="Search for flights between two cities",
        intents=["find_flights"],
        handler="_handle_find_flights",
        status="working",
        tags=["web"],
    ),

    # ── Media ──────────────────────────────────────────────────────────────
    Capability(
        name="media_play_pause",
        description="Play, pause, or resume media playback",
        intents=["media_play", "media_pause", "media_play_pause"],
        handler="_handle_media_play_pause",
        status="working",
        tags=["media"],
    ),
    Capability(
        name="media_next",
        description="Skip to next media track",
        intents=["media_next"],
        handler="_handle_media_next",
        status="working",
        tags=["media"],
    ),
    Capability(
        name="media_prev",
        description="Go back to previous media track",
        intents=["media_prev"],
        handler="_handle_media_prev",
        status="working",
        tags=["media"],
    ),
    Capability(
        name="media_volume_up",
        description="Increase media volume",
        intents=["media_volume_up"],
        handler="_handle_media_volume_up",
        status="working",
        tags=["media"],
    ),
    Capability(
        name="media_volume_down",
        description="Decrease media volume",
        intents=["media_volume_down"],
        handler="_handle_media_volume_down",
        status="working",
        tags=["media"],
    ),
    Capability(
        name="media_mute",
        description="Mute or unmute media",
        intents=["media_mute"],
        handler="_handle_media_mute",
        status="working",
        tags=["media"],
    ),
    Capability(
        name="play_youtube",
        description="Search for and play a YouTube video",
        intents=["play_youtube"],
        handler="_handle_youtube_video",
        status="working",
        tags=["media", "youtube"],
    ),
    Capability(
        name="youtube_summary",
        description="Summarise the currently playing YouTube video",
        intents=["youtube_summary"],
        handler="_handle_youtube_video",
        status="working",
        tags=["media", "youtube"],
    ),
    Capability(
        name="youtube_trending",
        description="Show trending YouTube videos for a region",
        intents=["youtube_trending"],
        handler="_handle_youtube_video",
        status="working",
        tags=["media", "youtube"],
    ),
    Capability(
        name="set_speed",
        description="Change Sam's speech speed",
        intents=["set_speed"],
        handler="_handle_set_speed",
        status="working",
        tags=["sam"],
    ),

    # ── Dev tools ──────────────────────────────────────────────────────────
    Capability(
        name="code_helper",
        description="Write, edit, explain, run, or optimize code",
        intents=["code_helper"],
        handler="_handle_code_helper",
        status="working",
        tags=["dev"],
    ),
    Capability(
        name="build_project",
        description="Build a new project from a natural-language description",
        intents=["build_project"],
        handler="_handle_build_project",
        status="working",
        tags=["dev"],
    ),
    Capability(
        name="debug_app",
        description="End-to-end bug diagnosis: locate project, reproduce error, LLM-diagnose, patch, verify",
        intents=["debug_app", "debug_bug", "fix_bug"],
        handler="_handle_debug_app",
        status="working",
        tags=["dev"],
        dependencies=["project_index"],
    ),
    Capability(
        name="run_tests",
        description="Stack-aware test runner: auto-detects Flutter/Node/Python/Rust/Go, reports pass/fail, gates shipping",
        intents=["run_tests", "run_test"],
        handler="_handle_run_tests",
        status="working",
        tags=["dev", "terminal"],
        dependencies=["project_index"],
    ),
    Capability(
        name="post_to",
        description="Post content to Twitter/X, LinkedIn, Facebook, or Reddit via Sam's browser session",
        intents=["post_to", "social_post"],
        handler="_handle_post_to",
        status="working",
        tags=["browser", "social"],
    ),
    Capability(
        name="summarize_inbox",
        description="Read and summarize unread inbox messages (Gmail) via Sam's browser session",
        intents=["summarize_inbox", "read_inbox", "check_email"],
        handler="_handle_summarize_inbox",
        status="working",
        tags=["browser", "email"],
    ),
    Capability(
        name="do_in_browser",
        description="Navigate to a site and follow a natural-language instruction using the browser",
        intents=["do_in_browser", "browser_task"],
        handler="_handle_do_in_browser",
        status="working",
        tags=["browser"],
    ),
    Capability(
        name="start_dev_server",
        description="Start the project development server",
        intents=["start_dev_server", "start_server", "run_app"],
        handler="_handle_start_dev_server",
        status="working",
        tags=["dev", "terminal"],
    ),
    Capability(
        name="install_dependencies",
        description="Install project dependencies (npm/pip/etc.)",
        intents=["install_dependencies", "install_deps", "run_install"],
        handler="_handle_install_dependencies",
        status="working",
        tags=["dev", "terminal"],
    ),
    Capability(
        name="run_command",
        description="Run a shell command (with confirmation gate)",
        intents=["run_command", "execute_command"],
        handler="_handle_run_command",
        status="working",
        tags=["dev", "terminal"],
    ),
    Capability(
        name="confirm_terminal",
        description="Confirm and execute a pending terminal command",
        intents=["confirm_terminal", "confirm_command", "run_it"],
        handler="_handle_confirm_terminal",
        status="working",
        tags=["dev", "terminal"],
    ),
    Capability(
        name="cancel_command",
        description="Cancel a pending terminal command",
        intents=["cancel_command", "cancel_terminal"],
        handler="_handle_cancel_command",
        status="working",
        tags=["dev", "terminal"],
    ),
    Capability(
        name="agent_task",
        description="Execute a complex multi-step autonomous task via the agent orchestrator",
        intents=["agent_task"],
        handler="_handle_agent_task",
        status="wip",
        tags=["dev", "agent"],
    ),
    Capability(
        name="guide_task",
        description="Guide the user step-by-step through a complex task (co-pilot mode)",
        intents=["guide_task"],
        handler="_handle_guide_task",
        status="working",
        tags=["dev", "productivity"],
    ),
    Capability(
        name="save_test_credentials",
        description="Save test login credentials for a project",
        intents=["save_test_credentials"],
        handler="_handle_save_test_credentials",
        status="working",
        tags=["dev"],
    ),
    Capability(
        name="stop_test",
        description="Stop a running UI test",
        intents=["stop_test", "cancel_test"],
        handler="_handle_stop_test",
        status="working",
        tags=["dev"],
    ),

    # ── Skills (handled by skills/loader.py) ───────────────────────────────
    Capability(
        name="pomodoro",
        description="25-minute focus timer with break reminders",
        intents=["pomodoro", "start_pomodoro", "focus_timer"],
        handler="skill:pomodoro",
        status="working",
        test="skills/pomodoro.py",
        tags=["productivity", "skill"],
    ),
    Capability(
        name="standup",
        description="Generate a daily standup report from session activity",
        intents=["standup", "daily_standup"],
        handler="skill:standup",
        status="working",
        tags=["productivity", "skill"],
    ),
    Capability(
        name="commit_writer",
        description="Generate a conventional commit message from staged changes",
        intents=["commit_writer", "write_commit", "commit_message"],
        handler="skill:commit_writer",
        status="working",
        tags=["dev", "skill"],
    ),
    Capability(
        name="code_explainer",
        description="Explain what a block of code does in plain English",
        intents=["code_explainer", "explain_code"],
        handler="skill:code_explainer",
        status="working",
        tags=["dev", "skill"],
    ),
    Capability(
        name="text_transform",
        description="Transform text: summarise, rephrase, expand, bullet, formal, casual",
        intents=["text_transform", "summarise_text", "rephrase_text",
                 "expand_text", "bullet_text", "make_formal", "make_casual"],
        handler="skill:text_transform",
        status="working",
        tags=["productivity", "skill"],
    ),
    Capability(
        name="focus_stats",
        description="Show focus and productivity stats for the current session",
        intents=["focus_stats", "productivity_report", "my_stats"],
        handler="skill:focus_stats",
        status="working",
        tags=["productivity", "skill"],
    ),
    Capability(
        name="git_workflow",
        description="Git operations: commit, branch, diff, status",
        intents=["git_commit", "commit_changes", "git_branch", "create_branch",
                 "git_diff_summary", "git_status_full"],
        handler="skill:git_workflow",
        status="working",
        tags=["dev", "skill"],
    ),
    Capability(
        name="idea_capture",
        description="Capture a feature idea and turn it into a structured dev plan",
        intents=["capture_idea", "create_feature_plan", "plan_feature"],
        handler="skill:idea_capture",
        status="working",
        tags=["dev", "skill"],
    ),
    Capability(
        name="flutter_tester",
        description="Test or automate a Flutter/web app via Playwright",
        intents=["test_flutter_app", "test_the_app", "run_app_test",
                 "test_login_flow", "test_signup", "test_feature",
                 "automate_task", "automate_app", "fill_form",
                 "navigate_app", "use_the_app", "do_in_app"],
        handler="skill:flutter_tester",
        status="working",
        test="skills/flutter_tester.py",
        dependencies=["playwright", "running dev server"],
        tags=["dev", "skill", "browser"],
    ),

    # ── Goals & Workflows ──────────────────────────────────────────────────
    Capability(
        name="create_goal",
        description="Create a new OKR-style goal",
        intents=["create_goal"],
        handler="_handle_create_goal",
        status="working",
        tags=["goals"],
    ),
    Capability(
        name="list_goals",
        description="List active goals with health scores",
        intents=["list_goals"],
        handler="_handle_list_goals",
        status="working",
        tags=["goals"],
    ),
    Capability(
        name="update_goal",
        description="Update progress on a goal",
        intents=["update_goal"],
        handler="_handle_update_goal",
        status="working",
        tags=["goals"],
    ),
    Capability(
        name="run_workflow",
        description="Execute a named automation workflow",
        intents=["run_workflow"],
        handler="_handle_run_workflow",
        status="working",
        tags=["workflows"],
    ),
    Capability(
        name="list_workflows",
        description="List all configured workflows",
        intents=["list_workflows"],
        handler="_handle_list_workflows",
        status="working",
        tags=["workflows"],
    ),

    # ── Learning & Memory ──────────────────────────────────────────────────
    Capability(
        name="learn_from_youtube",
        description="Extract knowledge from a YouTube video URL",
        intents=["learn_from_youtube"],
        handler="_handle_learn_from_youtube",
        status="working",
        tags=["learning"],
    ),
    Capability(
        name="learn_this",
        description="Save a piece of knowledge to long-term memory",
        intents=["learn_this", "remember_this", "save_knowledge"],
        handler="_handle_learn_this",
        status="working",
        tags=["learning"],
    ),
    Capability(
        name="daily_report",
        description="Generate a daily activity report from session logs",
        intents=["daily_report", "what_did_you_do", "session_report"],
        handler="_handle_daily_report",
        status="working",
        tags=["reporting"],
    ),
    Capability(
        name="export_conversation",
        description="Export the current conversation to a file",
        intents=["export_conversation"],
        handler="_handle_export_conversation",
        status="working",
        tags=["reporting"],
    ),

    # ── Sam control ────────────────────────────────────────────────────────
    Capability(
        name="capabilities",
        description="Tell the user what Sam can do",
        intents=["capabilities"],
        handler="_handle_capabilities",
        status="working",
        tags=["sam"],
    ),
    Capability(
        name="list_skills",
        description="List all loaded Sam skills",
        intents=["list_skills"],
        handler="_handle_list_skills",
        status="working",
        tags=["sam"],
    ),
    Capability(
        name="invoke_skill",
        description="Manually activate a specific skill by name",
        intents=["invoke_skill"],
        handler="_handle_invoke_skill",
        status="working",
        tags=["sam"],
    ),
    Capability(
        name="switch_to_cloud",
        description="Switch Sam's LLM to cloud (OpenAI GPT-4o-mini)",
        intents=["switch_to_cloud", "use_cloud", "cloud_model"],
        handler="_handle_switch_model",
        status="working",
        tags=["sam"],
    ),
    Capability(
        name="switch_to_local",
        description="Switch Sam's LLM to local (Ollama)",
        intents=["switch_to_local", "use_local", "local_model"],
        handler="_handle_switch_model",
        status="working",
        tags=["sam"],
    ),
    Capability(
        name="confirm_action",
        description="Confirm a pending action Sam is waiting to execute",
        intents=["confirm_action", "confirm_yes", "yes", "proceed",
                 "go_ahead", "apply_it", "do_it"],
        handler="_handle_confirm_action",
        status="working",
        tags=["sam"],
    ),
    Capability(
        name="cancel_action",
        description="Cancel a pending action",
        intents=["cancel_action", "cancel_no", "no", "stop_it", "dont_do_it"],
        handler="_handle_cancel_action",
        status="working",
        tags=["sam"],
    ),
    Capability(
        name="silence_sam",
        description="Mute Sam's voice output",
        intents=["silence_sam", "shut_up", "be_quiet", "stop_talking", "mute"],
        handler="_handle_silence_sam",
        status="working",
        tags=["sam"],
    ),
    Capability(
        name="wake_sam",
        description="Unmute Sam and restore voice output",
        intents=["wake_sam", "you_can_talk", "unmute"],
        handler="_handle_wake_sam",
        status="working",
        tags=["sam"],
    ),
    Capability(
        name="meeting_notes_start",
        description="Start silent meeting mode and begin taking notes",
        intents=["meeting_notes_start", "take_notes", "start_notes"],
        handler="_handle_meeting_notes_start",
        status="working",
        tags=["sam", "meetings"],
    ),
    Capability(
        name="meeting_notes_stop",
        description="Stop meeting mode and stop taking notes",
        intents=["meeting_notes_stop", "stop_notes", "end_meeting"],
        handler="_handle_meeting_notes_stop",
        status="working",
        tags=["sam", "meetings"],
    ),
    Capability(
        name="personality_feedback",
        description="Give Sam feedback on response style (too long, too technical, etc.)",
        intents=["personality_feedback"],
        handler="_handle_personality_feedback",
        status="working",
        tags=["sam"],
    ),
    Capability(
        name="add_to_whitelist",
        description="Add a process to the protected list (won't be auto-killed)",
        intents=["add_to_whitelist"],
        handler="_handle_add_to_whitelist",
        status="working",
        tags=["system"],
    ),

    # ── Autonomous agents ──────────────────────────────────────────────────
    Capability(
        name="proactive_reasoner",
        description="Inner-voice loop: every 5 min asks LLM if Sam should say or do anything proactively",
        intents=[],
        handler="",
        status="working",
        tags=["agents", "system"],
        dependencies=["ollama"],
    ),
    Capability(
        name="tool_forge",
        description="Auto-builds new action handlers for unknown intents; gated by config/forge.json",
        intents=[],
        handler="",
        status="wip",
        tags=["agents", "system"],
        dependencies=["ollama"],
    ),
]


# ── Index structures ──────────────────────────────────────────────────────────

# intent string → Capability (O(1) lookup for dispatcher)
INTENT_MAP: dict[str, Capability] = {
    intent: cap
    for cap in REGISTRY
    for intent in cap.intents
}


def get_capability(intent: str) -> Capability | None:
    """Return the Capability for an intent string, or None."""
    return INTENT_MAP.get(intent)


def list_by_status(status: Status) -> list[Capability]:
    return [c for c in REGISTRY if c.status == status]


def list_by_tag(tag: str) -> list[Capability]:
    return [c for c in REGISTRY if tag in c.tags]


def get_prompt_intents() -> str:
    """Generate the INTENTS section for core/prompt.txt from the registry.
    Skips 'planned' capabilities — they're not wired yet.
    """
    seen: set[str] = set()
    lines: list[str] = []
    for cap in REGISTRY:
        if cap.status == "planned":
            continue
        for intent in cap.intents:
            if intent not in seen:
                seen.add(intent)
                lines.append(f"- {intent}")
    return "\n".join(lines)


def summary() -> str:
    """Quick text summary of registry health — useful for voice/dashboard."""
    total = len(REGISTRY)
    by_status: dict[str, int] = {}
    for cap in REGISTRY:
        by_status[cap.status] = by_status.get(cap.status, 0) + 1
    parts = [f"{v} {k}" for k, v in sorted(by_status.items())]
    return f"{total} capabilities: {', '.join(parts)}"
