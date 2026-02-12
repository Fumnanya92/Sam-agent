"""Embedded speech interface powered by WebView + Web Speech API."""

import os
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser

try:
    import webview
except ImportError:  # pragma: no cover - handled at runtime
    webview = None

from log.logger import get_logger
from websocket_server import start_speech_server

logger = get_logger("SAM_VOICE_UI")

# Global state
server = None
http_server = None
http_port = None
http_thread = None
webview_window = None
webview_thread = None
webview_ready = threading.Event()
BASE_DIR = Path(__file__).parent
SHOW_SPEECH_WINDOW = os.getenv("SAM_SHOW_SPEECH_WINDOW", "1") == "1"  # Default to showing for debugging


class QuietRequestHandler(SimpleHTTPRequestHandler):
    """Serve static files quietly to avoid console noise."""

    def log_message(self, format, *args):  # noqa: A003
        return  # Silence default stdout logging


def start_http_server():
    """Launch a tiny static server to host the speech client HTML."""
    global http_server, http_port, http_thread

    if http_server is not None:
        return http_port

    handler = partial(QuietRequestHandler, directory=str(BASE_DIR))
    http_server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    http_port = http_server.server_address[1]
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()
    logger.info(f"Local speech client server running on http://localhost:{http_port}")
    return http_port


def _find_client_html():
    for candidate in ("speech_client_compact.html", "speech_client.html"):
        html_file = BASE_DIR / candidate
        if html_file.exists():
            return html_file
    return None


def ensure_embedded_window_running(show_window: bool | None = None):
    """Ensure the speech client window thread is running."""
    global webview_thread

    if webview_thread and webview_thread.is_alive():
        return

    webview_ready.clear()
    webview_thread = threading.Thread(
        target=run_embedded_window_loop,
        kwargs={"show_window": show_window},
        daemon=True,
        name="SamSpeechClient",
    )
    webview_thread.start()


def prepare_embedded_window(show_window: bool | None = None):
    """Create the hidden WebView window that hosts the speech client."""
    global webview_window

    if webview is None:
        logger.error("pywebview is not installed; cannot embed speech client")
        return False

    if webview_window is not None:
        return True

    if show_window is None:
        show_window = SHOW_SPEECH_WINDOW

    port = start_http_server()
    html_file = _find_client_html()
    if html_file is None:
        logger.error("Speech client HTML not found.")
        return False

    url = f"http://localhost:{port}/{html_file.name}"

    def _on_loaded():
        logger.info("Embedded speech client loaded")
        if not show_window:
            try:
                webview_window.hide()
            except Exception:
                pass
        webview_ready.set()

    logger.info("Creating embedded speech client window")
    webview_window = webview.create_window(
        "Sam Voice",
        url,
        width=360,
        height=420,
        resizable=False,
        frameless=not show_window,
        hidden=not show_window,
        confirm_close=False,
        on_top=False,
    )
    webview_window.events.loaded += _on_loaded
    return True


def _launch_browser_fallback():
    html_file = _find_client_html()
    if html_file is None:
        logger.error("Cannot locate speech client HTML for fallback mode")
        return False

    port = start_http_server()
    try:
        webbrowser.open(f"http://localhost:{port}/{html_file.name}")
        logger.info("Fallback browser window launched for speech client")
        webview_ready.set()
        return True
    except Exception as exc:
        logger.error(f"Failed to launch fallback browser: {exc}")
        return False


def run_embedded_window_loop(show_window: bool | None = None):
    """Blocking loop that keeps the WebView window alive (main thread)."""
    logger.info("=== STARTING EMBEDDED SPEECH WINDOW ===")
    
    if webview is None:
        logger.error("pywebview missing; using browser fallback for speech client")
        if _launch_browser_fallback():
            logger.info("Browser fallback launched, entering wait loop")
            threading.Event().wait()
        return

    logger.info("pywebview available, preparing embedded window")
    if prepare_embedded_window(show_window):
        logger.info("Starting embedded speech window event loop")
        try:
            logger.info("Calling webview.start()...")
            webview.start(debug=True, gui="edgechromium")
            logger.info("webview.start() completed")
        except Exception as exc:
            logger.error(f"Embedded speech window crashed: {exc}; falling back to browser")
            if _launch_browser_fallback():
                logger.info("Browser fallback launched after webview crash")
                threading.Event().wait()
    else:
        logger.error("Failed to prepare embedded window")


def record_voice():
    """Request a new voice transcription via the embedded speech client."""
    global server

    logger.debug("record_voice() called")

    # Start WebSocket server if not already running (singleton pattern)
    if server is None:
        logger.info("Starting WebSocket server..")
        server = start_speech_server()
        time.sleep(0.3)  # Give server time to start

    logger.debug("Waiting for embedded window readiness...")
    if not webview_ready.wait(timeout=15):
        logger.warning("Speech client window not ready; cannot capture audio")
        return ""

    logger.debug("Waiting for WebSocket client connection...")
    if not server.wait_for_client(timeout=10):
        logger.warning("No embedded speech client connected; cannot record voice")
        return ""

    logger.info("Requesting speech input from embedded client")
    server.broadcast_command("start_listening")

    # Wait for speech input from WebSocket
    try:
        transcription = server.get_transcription(timeout=30)
        if transcription:
            logger.info(f"Speech recognized: '{transcription}'")
            return transcription
        else:
            logger.warning("No speech detected within timeout")
            return ""
    except Exception as e:
        logger.error(f"Speech recognition error: {e}")
        return ""
    finally:
        server.broadcast_command("stop_listening")


def initialize_speech_system():
    """Initialize the speech system"""
    global server
    logger.info("Initializing Sam Voice Interface system")
    server = start_speech_server()
    logger.info("Voice interface system ready")
