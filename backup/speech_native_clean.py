"""
Sam Voice Interface - Native Window Solution (Clean Version)
Uses tkinter for main window and embedded browser for Web Speech API
"""

import tkinter as tk
import threading
import time
import webbrowser
from pathlib import Path
from log.logger import get_logger
from websocket_server import start_speech_server

logger = get_logger("SAM_NATIVE_VOICE")

class SamNativeVoiceWindow:
    def __init__(self):
        self.root = None
        self.server = None
        self.result = None
        self.window_closed = False
        self.status_var = None
        self.transcript_var = None
        
    def create_window(self):
        """Create native tkinter window"""
        self.root = tk.Tk()
        self.root.title("Sam Voice Interface")
        self.root.geometry("450x320") 
        self.root.configure(bg='#1a3a7a')
        self.root.resizable(True, True)
        self.root.attributes("-topmost", True)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (450 // 2)
        y = (self.root.winfo_screenheight() // 2) - (320 // 2)
        self.root.geometry(f"450x320+{x}+{y}")
        
        # Create UI
        self.create_ui()
        
        # Bind close events
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda e: self.close())
        
        # Start speech recognition in background  
        self.start_speech_recognition()
        
        logger.info("Native voice window created successfully")
        return True
    
    def create_ui(self):
        """Create the UI elements"""
        # Main frame
        main_frame = tk.Frame(self.root, bg='#1a3a7a')
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(
            main_frame,
            text="🎤 Speak to Sam",
            font=("Segoe UI", 24, "bold"),
            bg='#1a3a7a',
            fg='white'
        )
        title_label.pack(pady=(0, 20))
        
        # Status
        self.status_var = tk.StringVar(value="Starting speech recognition...")
        status_label = tk.Label(
            main_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 12),
            bg='#1a3a7a',
            fg='#88aadd'
        )
        status_label.pack(pady=(0, 20))
        
        # Transcript area
        transcript_frame = tk.Frame(main_frame, bg='#0a1a3a', relief='raised', bd=2)
        transcript_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        self.transcript_var = tk.StringVar(value="Your speech will appear here...")
        transcript_label = tk.Label(
            transcript_frame,
            textvariable=self.transcript_var,
            font=("Segoe UI", 11),
            bg='#0a1a3a',
            fg='#00ffaa',
            wraplength=400,
            justify='center'
        )
        transcript_label.pack(expand=True, pady=20, padx=20)
        
        # Close button
        close_btn = tk.Button(
            main_frame,
            text="Close (ESC)",
            command=self.close,
            font=("Segoe UI", 10),
            bg='#ff4444',
            fg='white',
            relief='flat',
            padx=20
        )
        close_btn.pack()
        
    def update_status(self, status):
        """Update status text"""
        try:
            if self.status_var and self.root:
                self.status_var.set(status)
        except:
            pass
    
    def update_transcript(self, text):
        """Update transcript text"""
        try:
            if self.transcript_var and self.root:
                self.transcript_var.set(f'"{text}"')
        except:
            pass
    
    def start_speech_recognition(self):
        """Start speech recognition in background"""
        def start_browser_and_monitor():
            try:
                # Start minimal browser for Web Speech API
                html_file = Path(__file__).parent / "speech_client_compact.html"
                if not html_file.exists():
                    html_file = Path(__file__).parent / "speech_client.html"
                
                if html_file.exists():
                    webbrowser.open(f"file:///{html_file.absolute()}")
                    logger.info("Speech recognition browser started")
                    time.sleep(1)
                    
                    # Update status
                    self.root.after(0, lambda: self.update_status("Listening... Speak now!"))
                    
                    # Monitor for transcription
                    transcription = self.server.get_transcription(timeout=30)
                    
                    if transcription:
                        self.result = transcription
                        self.root.after(0, lambda: self.update_transcript(transcription))
                        self.root.after(0, lambda: self.update_status("Speech received! Click Close or ESC"))
                        logger.info(f"Speech recognized: '{transcription}'")
                        
                        # Auto-close after delay
                        def auto_close():
                            time.sleep(3)
                            self.root.after(0, self.close)
                        threading.Thread(target=auto_close, daemon=True).start()
                    else:
                        self.root.after(0, lambda: self.update_status("No speech detected"))
                        
            except Exception as e:
                logger.error(f"Speech recognition error: {e}")
                self.root.after(0, lambda: self.update_status(f"Error: {e}"))
        
        threading.Thread(target=start_browser_and_monitor, daemon=True).start()
    
    def close(self):
        """Close the window"""
        self.window_closed = True
        if self.root:
            try:
                self.root.quit()
            except:
                pass
            try:
                self.root.destroy()
            except:
                pass
            
    def show(self):
        """Show the window (blocking)"""
        if self.root:
            self.root.mainloop()

def record_voice_native():
    """
    Record voice using native tkinter window with embedded Web Speech API
    """
    logger.info("Starting Sam Native Voice Interface")
    
    # Start WebSocket server (singleton pattern)  
    server = start_speech_server()
    time.sleep(0.3)
    
    # Create native window
    voice_window = SamNativeVoiceWindow()
    voice_window.server = server
    
    if not voice_window.create_window():
        logger.error("Failed to create native voice window")
        return ""
    
    # Show window (blocks until closed)
    voice_window.show()
    
    # Get result
    result = voice_window.result or ""
    logger.info(f"Native voice recording complete. Result: '{result}'")
    
    return result

if __name__ == "__main__":
    # Test the native voice interface
    print("Testing Sam Native Voice Interface...")
    result = record_voice_native()
    print(f"Result: {result}")