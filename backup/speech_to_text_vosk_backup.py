import sounddevice as sd
import vosk
import queue
import sys
import json
import threading
import time
from pathlib import Path
from shared_state import is_sam_speaking

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()

MODEL_PATH = BASE_DIR / "vosk-model-small-en-us-0.15"

model = vosk.Model(str(MODEL_PATH))

q = queue.Queue()
stop_listening_flag = threading.Event()

def callback(indata, frames, time_info, status):
    if status:
        print(status, file=sys.stderr)
    if is_sam_speaking.is_set():
        return  # Don't collect audio while Sam is speaking
    q.put(bytes(indata))

def record_voice(prompt="🎙 I'm listening, sir..."):
    """
    Blocking call, returns the first recognized sentence.
    """
    # 🚫 DO NOT LISTEN WHILE SAM IS SPEAKING
    while is_sam_speaking.is_set():
        time.sleep(0.1)
    
    print(prompt)
    
    # Clear the queue from any old audio data
    while not q.empty():
        try:
            q.get_nowait()
        except queue.Empty:
            break
    
    rec = vosk.KaldiRecognizer(model, 16000)
    rec.SetMaxAlternatives(0)
    rec.SetWords(False)
    
    start_time = time.time()
    timeout_seconds = 30  # 30 second timeout
    silence_threshold = 3  # 3 seconds of silence after speech
    last_speech_time = None
    
    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                           channels=1, callback=callback):
        while not stop_listening_flag.is_set():
            # Check for overall timeout
            if time.time() - start_time > timeout_seconds:
                print("⏱️ Timeout reached")
                break
                
            try:
                data = q.get(timeout=0.1)
            except queue.Empty:
                # Check for silence timeout after speech detected
                if last_speech_time and (time.time() - last_speech_time > silence_threshold):
                    # Get final result
                    final_result = json.loads(rec.FinalResult())
                    text = final_result.get("text", "")
                    if text.strip():
                        print("👤 You:", text)
                        return text
                    break
                continue
            
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text.strip():
                    print("👤 You:", text)
                    return text
            else:
                # Check partial results to detect when user is speaking
                partial = json.loads(rec.PartialResult())
                if partial.get("partial", "").strip():
                    last_speech_time = time.time()
    
    # Get any final result
    final_result = json.loads(rec.FinalResult())
    text = final_result.get("text", "")
    if text.strip():
        print("👤 You:", text)
        return text
        
    return ""
