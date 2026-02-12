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
def process_speech(audio_data):
    """Process recorded audio and return recognized text"""
    if not model:
        logger.error("Vosk model not available")
        return ""
    
    try:
        logger.info(f"Processing audio data: {len(audio_data)} samples")
        
        # Convert audio data to the format Vosk expects
        audio_bytes = (audio_data * 32768).astype(np.int16).tobytes()
        logger.info(f"Converted to bytes: {len(audio_bytes)} bytes")
        
        # Create recognizer
        rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        
        # Process audio
        if rec.AcceptWaveform(audio_bytes):
            result = json.loads(rec.Result())
            text = result.get('text', '')
            logger.info(f"Final recognition result: '{text}'")
            return text
        else:
            # Get partial result
            partial = json.loads(rec.PartialResult())
            text = partial.get('partial', '')
            logger.info(f"Partial recognition result: '{text}'")
            return text
            
    except Exception as e:
        logger.error(f"Speech recognition error: {e}")
        return ""


# -----------------------------
# UI
# -----------------------------
def record_voice():
    global running, recording_buffer, speech_detected, audio_level
    
    logger.info("Starting Sam speech recognition window")
    
    running = True
    recording_buffer = []
    speech_detected = False
    result_text = ""

    root = tk.Tk()
    root.title("Sam")
    root.geometry("500x300")
    root.overrideredirect(True)  # remove window frame
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)  # for fade-in

    # Center
    root.geometry("+{}+{}".format(
        int(root.winfo_screenwidth()/2 - 250),
        int(root.winfo_screenheight()/2 - 150)
    ))

    canvas = tk.Canvas(root, width=500, height=300, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # -----------------------------
    # Gradient Background
    # -----------------------------
    def draw_gradient():
        for i in range(300):
            r = int(10 + (0 * i / 300))
            g = int(40 + (100 * i / 300))
            b = int(120 + (135 * i / 300))
            color = f"#{r:02x}{g:02x}{b:02x}"
            canvas.create_line(0, i, 500, i, fill=color)

    draw_gradient()

    # Rounded corners illusion
    canvas.create_oval(-50, -50, 100, 100, fill="#0a2a5f", outline="")
    canvas.create_oval(400, -50, 550, 100, fill="#0a2a5f", outline="")
    canvas.create_oval(-50, 200, 100, 350, fill="#1a4fa3", outline="")
    canvas.create_oval(400, 200, 550, 350, fill="#1a4fa3", outline="")

    # Title
    canvas.create_text(
        250, 50,
        text="🎤 Speak to Sam",
        fill="white",
        font=("Segoe UI", 20, "bold")
    )

    # Status
    status_text = canvas.create_text(
        250, 260,
        text="Listening...",
        fill="#cccccc",
        font=("Segoe UI", 14)
    )

    # Text display for recognized speech
    recognized_text = canvas.create_text(
        250, 200,
        text="",
        fill="#00ffff",
        font=("Segoe UI", 12),
        width=450,
        anchor="center"
    )

    # -----------------------------
    # Speech Processing Thread
    # -----------------------------
    silence_counter = 0
    processing_speech = False
    has_spoken = False  # Track if user has spoken
    
    def check_for_speech_end():
        global recording_buffer
        nonlocal silence_counter, processing_speech, result_text, has_spoken
        
        # Track when speech starts
        if speech_detected and not has_spoken:
            has_spoken = True
            logger.info(f"Speech detected! Audio level: {audio_level}")
        
        if has_spoken and not processing_speech:
            # Check for silence (end of speech)
            if audio_level < 2:  # Increased silence threshold
                silence_counter += 1
                logger.info(f"Silence detected. Counter: {silence_counter}/20")
                
                if silence_counter > 20:  # About 2 seconds of silence
                    processing_speech = True
                    canvas.itemconfig(status_text, text="Processing speech...")
                    logger.info(f"Processing speech. Buffer size: {len(recording_buffer)}")
                    
                    # Process the recorded audio
                    if recording_buffer:
                        audio_array = np.array(recording_buffer)
                        recognized = process_speech(audio_array)
                        
                        if recognized.strip():
                            result_text = recognized.strip()
                            canvas.itemconfig(recognized_text, text=f'"{result_text}"')
                            canvas.itemconfig(status_text, text="Click to send...")
                            logger.info(f"Speech recognized: {result_text}")
                        else:
                            canvas.itemconfig(status_text, text="No speech detected. Try again...")
                            logger.warning("No speech recognized from audio buffer")
                            # Reset for another try
                            processing_speech = False
                            silence_counter = 0
                            has_spoken = False
                            # Clear the global recording buffer in-place to avoid re-binding
                            try:
                                recording_buffer.clear()
                            except Exception:
                                recording_buffer = []
            else:
                if silence_counter > 0:
                    logger.info(f"Speech continues. Audio level: {audio_level}")
                silence_counter = 0
        
        if running and not result_text:
            root.after(100, check_for_speech_end)
    
    # Start speech monitoring
    check_for_speech_end()

    # -----------------------------
    # Animated Waveform
    # -----------------------------
    def animate_wave():
        if not running:
            return
        
        try:
            canvas.delete("wave")
            center_y = 150

            for x in range(0, 500, 10):
                amplitude = audio_level * 1.5
                y = center_y + np.sin(x/30) * amplitude
                
                # Color changes based on speech detection
                color = "#00ffff" if not speech_detected else "#00ff00"
                
                canvas.create_line(
                    x, center_y,
                    x, y,
                    fill=color,
                    width=2,
                    tags="wave"
                )

            if running:
                root.after(30, animate_wave)
        except Exception as e:
            logger.error(f"Animation error: {e}")

    animate_wave()

    # -----------------------------
    # Mic Stream
    # -----------------------------
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=1,
        callback=audio_callback,
        dtype=np.float32
    )
    stream.start()

    # -----------------------------
    # Fade In
    # -----------------------------
    def fade_in(alpha=0):
        alpha += 0.05
        if alpha <= 1 and running:
            root.attributes("-alpha", alpha)
            root.after(30, lambda: fade_in(alpha))

    fade_in()

    # -----------------------------
    # Close on click (only if we have result or user clicks)
    # -----------------------------
    def close():
        global running
        running = False
        try:
            stream.stop()
            stream.close()
        except:
            pass
        root.destroy()

    def on_click(e):
        if result_text or not speech_detected:
            close()

    root.bind("<Button-1>", on_click)
    
    # ESC key to close
    def on_escape(e):
        close()
    
    root.bind("<Escape>", on_escape)
    root.focus_set()

    try:
        root.mainloop()
    except Exception as e:
        logger.error(f"Error in UI loop: {e}")
    
    logger.info(f"Sam window closed. Result: '{result_text}'")
    
    if result_text.strip():
        logger.info(f"Returning recognized text to Sam: '{result_text}'")
    else:
        logger.warning("No speech recognized, returning empty string")
    
    return result_text
