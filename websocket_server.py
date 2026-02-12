import asyncio
import websockets
import json
import threading
import webbrowser
import time
from pathlib import Path
from log.logger import get_logger

logger = get_logger("WEBSOCKET_SERVER")

class SpeechWebSocketServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.server = None
        self.connected_clients = set()
        self.current_transcription = ""
        self.transcription_complete = False
        self.loop = None
        self.client_event = threading.Event()
        
    async def handle_client(self, websocket, path=None):
        """Handle WebSocket client connections"""
        self.connected_clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.connected_clients)}")
        self.client_event.set()
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get("type") == "transcript":
                        if data.get("isFinal"):
                            self.current_transcription = data.get("text", "")
                            self.transcription_complete = True
                            logger.info(f"Final transcript received: '{self.current_transcription}'")
                        else:
                            # Interim result - could be used for live updates
                            logger.debug(f"Interim transcript: '{data.get('text', '')}'")
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {message}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected")
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            self.connected_clients.discard(websocket)
            if not self.connected_clients:
                self.client_event.clear()
            
    async def start_server(self):
        """Start the WebSocket server"""
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
        self.server = await websockets.serve(self.handle_client, self.host, self.port)
        logger.info("WebSocket server started successfully")
        
    async def stop_server(self):
        """Stop the WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("WebSocket server stopped")
            
    def get_transcription(self, timeout=30):
        """Get transcription with timeout"""
        self.current_transcription = ""
        self.transcription_complete = False
        
        # Simple time-based waiting without asyncio event loop
        import time
        start_time = time.time()
        
        while not self.transcription_complete:
            if time.time() - start_time > timeout:
                logger.warning("Transcription timeout")
                break
            time.sleep(0.1)  # Simple sleep instead of asyncio.sleep
            
        return self.current_transcription

    def wait_for_client(self, timeout=5):
        """Block until at least one speech client is connected."""
        return self.client_event.wait(timeout)

    async def _broadcast(self, payload):
        if not self.connected_clients:
            return

        message = json.dumps(payload)
        coroutines = []
        for client in list(self.connected_clients):
            coroutines.append(client.send(message))
        if coroutines:
            await asyncio.gather(*coroutines, return_exceptions=True)

    def broadcast_command(self, action, payload=None):
        """Send a control command to every connected speech client."""
        if self.loop is None:
            logger.debug("WebSocket loop not initialized; cannot broadcast command")
            return False

        message = {"type": "command", "action": action}
        if payload is not None:
            message["payload"] = payload

        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(message), self.loop)
            return True
        except Exception as exc:
            logger.error(f"Failed to broadcast '{action}' command: {exc}")
            return False

# Global server instance
speech_server = None
server_thread = None
server_running = False

def start_speech_server():
    """Start the speech WebSocket server in a separate thread (singleton)"""
    global speech_server, server_thread, server_running
    
    if server_running and speech_server:
        logger.info("WebSocket server already running, reusing existing instance")
        return speech_server
        
    if speech_server is None:
        speech_server = SpeechWebSocketServer()
    
    def run_server():
        global server_running
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            speech_server.loop = loop
            loop.run_until_complete(speech_server.start_server())
            server_running = True
            logger.info("WebSocket server started successfully")
            loop.run_forever()
        except OSError as e:
            if "10048" in str(e):  # Port already in use
                logger.warning("WebSocket server port already in use, assuming server is running")
                server_running = True
            else:
                logger.error(f"WebSocket server error: {e}")
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
    
    if not server_running:
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(0.5)  # Give server time to start
        logger.info("Speech WebSocket server thread started")
    
    return speech_server
