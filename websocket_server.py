import asyncio
import websockets
import json
import queue
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
        self._transcript_queue: queue.Queue = queue.Queue()   # buffers every transcript
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
                    
                    if data.get("type") == "wake_word":
                        # Legacy path — kept for safety
                        logger.info("Wake word detected (legacy event) — acknowledging")
                        self._transcript_queue.put("__hmm__")

                    elif data.get("type") == "transcript":
                        if data.get("isFinal"):
                            text = data.get("text", "")
                            self._transcript_queue.put(text)
                            logger.info(f"Final transcript received: '{text}'")
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
            
    def get_transcription(self, timeout=60):
        """Block until a transcript arrives from the speech client.
        Uses a queue so transcripts that arrive during LLM processing are
        never lost — they wait in the buffer until we're ready to consume.
        """
        try:
            text = self._transcript_queue.get(timeout=timeout)
            logger.debug(f"Consumed transcript from queue: '{text}'")
            # Peek for a short fragment continuation within 800ms.
            # The browser Web Speech API can split one utterance into two
            # isFinal events at number/punctuation boundaries
            # (e.g. "Set an alarm for one." then "17.").
            try:
                extra = self._transcript_queue.get(timeout=0.8)
                if len(extra.split()) <= 4:
                    text = text.rstrip(" .,;:") + " " + extra.strip()
                    logger.debug(f"Fragment merged. Final: '{text}'")
                else:
                    # Too long to be a continuation — put it back for the next turn.
                    self._transcript_queue.put(extra)
            except queue.Empty:
                pass
            return text
        except queue.Empty:
            logger.warning("Transcription timeout — no speech detected")
            return ""

    def clear_transcript_queue(self):
        """Drain any stale transcripts (e.g. phantom captures during Sam's TTS)."""
        cleared = 0
        while not self._transcript_queue.empty():
            try:
                self._transcript_queue.get_nowait()
                cleared += 1
            except queue.Empty:
                break
        if cleared:
            logger.debug(f"Cleared {cleared} stale transcript(s) from queue")

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
