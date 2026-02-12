"""
Real-time Web Speech API via WebSocket
Connects to browser-based speech recognition for instant transcription
"""

import webbrowser
import threading
import time
from pathlib import Path
from log.logger import get_logger
from websocket_server import start_speech_server

logger = get_logger("WEBSOCKET_SPEECH")

# Global server instance
server = None


def record_voice():
    """Start WebSocket server and browser for real-time speech recognition"""
    global server
    
    logger.info("Starting Web Speech API session")
    
    # Start WebSocket server
    if server is None:
        logger.info("Starting WebSocket server...")
        server = start_speech_server()
        # Give server time to start
        time.sleep(1)
    
    # Open browser with speech client
    html_file = Path(__file__).parent / "speech_client.html"
    if not html_file.exists():
        logger.error(f"Speech client HTML not found: {html_file}")
        return ""
    
    # Open the HTML file in the default browser
    try:
        webbrowser.open(f"file:///{html_file.absolute()}")
        logger.info("Opened speech recognition interface in browser")
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")
        return ""
    
    # Wait for transcription from the WebSocket server
    logger.info("Waiting for speech input...")
    transcription = server.get_transcription(timeout=30)
    
    if transcription:
        logger.info(f"Received transcription: '{transcription}'")
    else:
        logger.info("No transcription received (timeout or silence)")
    
    return transcription


def initialize_speech_system():
    """Initialize the WebSocket speech system"""
    global server
    
    logger.info("Initializing Web Speech API system")
    server = start_speech_server()
    logger.info("WebSocket speech system ready")
