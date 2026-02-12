"""
Sam Voice Interface - Standalone WebView Window 
Embeds Web Speech API in native window without browser
"""

import webview
import threading
import time
import asyncio
import concurrent.futures
from pathlib import Path
from log.logger import get_logger
from websocket_server import start_speech_server

logger = get_logger("SAM_STANDALONE_VOICE")

class StandaloneSpeechWindow:
    def __init__(self):
        self.window = None
        self.server = None
        self.result = None
        self.window_closed = False
        
    def on_window_loaded(self):
        """Called when the webview window finishes loading"""
        logger.info("Speech window loaded successfully")
        
    def on_window_closing(self):
        """Called when window is about to close"""
        self.window_closed = True
        logger.info("Speech window closing")
        return True  # Allow closing
    
    def get_transcription(self, timeout=30):
        """Monitor WebSocket for transcription"""
        if not self.server:
            logger.error("WebSocket server not available")
            return ""
        
        logger.info("Waiting for speech input...")
        transcription = self.server.get_transcription(timeout=timeout)
        
        if transcription:
            logger.info(f"Transcription received: '{transcription}'")
            self.result = transcription
            
            # Auto-close window after getting result
            if self.window:
                def close_after_delay():
                    time.sleep(1.5)  # Show result briefly
                    try:
                        self.window.destroy()
                    except:
                        pass
                
                threading.Thread(target=close_after_delay, daemon=True).start()
        else:
            logger.warning("No speech detected within timeout")
            self.result = ""
        
        return self.result
    
    def create_window(self):
        """Create standalone webview window"""
        html_file = Path(__file__).parent / "speech_client_compact.html"
        
        if not html_file.exists():
            # Fallback to original if compact doesn't exist
            html_file = Path(__file__).parent / "speech_client.html"
            logger.warning(f"Using fallback HTML: {html_file}")
        
        if not html_file.exists():
            logger.error(f"Speech client HTML not found: {html_file}")
            return False
        
        try:
            # Create small, focused window
            self.window = webview.create_window(
                title="Sam Voice Interface",
                url=str(html_file.absolute()),
                width=450,          # Compact width  
                height=320,         # Compact height
                min_size=(350, 280),
                resizable=True,
                on_top=True,        # Keep window on top
                shadow=True,
                maximized=False,
                minimized=False
            )
            
            logger.info("Standalone speech window created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create window: {e}")
            return False
    
    def show_sync(self):
        """Show the window synchronously (blocking)"""
        try:
            # Start webview - this blocks until window closes
            webview.start(debug=False)
            logger.info("Speech window closed")
            
        except Exception as e:
            logger.error(f"Error running window: {e}")

def record_voice_standalone():
    """
    Main function to record voice using standalone window
    Returns transcribed text or empty string if no speech detected
    This function RUNS IN MAIN THREAD - compatible with webview
    """
    logger.info("Starting Sam Standalone Voice Interface")
    
    # Start WebSocket server if needed (singleton pattern)
    server = start_speech_server()
    time.sleep(0.3)  # Give server time to start
    
    # Create standalone window
    speech_window = StandaloneSpeechWindow()
    speech_window.server = server
    
    if not speech_window.create_window():
        logger.error("Failed to create speech window")
        return ""
    
    # Start transcription monitoring in background
    result_container = {"transcription": ""}
    
    def monitor_speech():
        try:
            transcription = speech_window.get_transcription(timeout=30)
            result_container["transcription"] = transcription
        except Exception as e:
            logger.error(f"Speech monitoring error: {e}")
    
    # Start monitoring in background thread
    monitor_thread = threading.Thread(target=monitor_speech, daemon=True)
    monitor_thread.start()
    
    # Show window (blocks until closed) - MAIN THREAD
    speech_window.show_sync()
    
    # Get result
    result = result_container["transcription"]
    logger.info(f"Voice recording complete. Result: '{result}'")
    
    return result

# Async wrapper for integration with Sam's async architecture 
async def record_voice_async():
    """
    Async wrapper for the standalone voice interface
    This allows proper integration with Sam's async main loop
    """
    logger.info("Starting async voice recording with standalone window")
    
    # Use executor to run the sync function in main thread context
    loop = asyncio.get_event_loop()
    
    try:
        # Run in a thread executor but ensure webview runs on main thread
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = loop.run_in_executor(None, record_voice_standalone)
            result = await future
            return result
    except Exception as e:
        logger.error(f"Async voice recording failed: {e}")
        return ""

# For backwards compatibility
record_voice = record_voice_standalone

if __name__ == "__main__":
    # Test the standalone interface
    print("Testing Sam Standalone Voice Interface...")
    result = record_voice_standalone()
    print(f"Result: {result}")