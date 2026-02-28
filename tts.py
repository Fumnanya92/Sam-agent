import io
import threading
import asyncio
import sounddevice as sd
import soundfile as sf
import edge_tts
from shared_state import is_sam_speaking

VOICE = "en-US-AndrewMultilingualNeural"  

RATE = "+0%"     
VOLUME = "+0%"   
PITCH = "+0Hz"   

stop_speaking_flag = threading.Event()

def edge_speak(text: str, ui=None, blocking=False):
    if not text or not text.strip():
        return

    finished_event = threading.Event()

    def _thread():
        is_sam_speaking.set()
        if ui:
            ui.start_speaking()
            ui.set_transcription(text.strip())

        # Tell the speech client to pause while Sam talks
        try:
            from websocket_server import speech_server as _srv
            if _srv:
                _srv.broadcast_command("sam_speaking")
        except Exception:
            pass

        stop_speaking_flag.clear()

        try:
            asyncio.run(_speak_async(text))
        except Exception as e:
            print("EDGE TTS ERROR:", e)
        finally:
            is_sam_speaking.clear()
            if ui:
                ui.stop_speaking()
                ui.clear_transcription()
            # Resume speech client after Sam finishes and enter active conversation mode
            try:
                from websocket_server import speech_server as _srv
                if _srv:
                    _srv.broadcast_command("sam_done")
                    # Slight delay then explicitly signal active mode so the user
                    # can continue the conversation without re-saying "Hey Sam"
                    import time as _time
                    _time.sleep(0.3)
                    _srv.broadcast_command("set_active")
            except Exception:
                pass
            finished_event.set()

    threading.Thread(target=_thread, daemon=True).start()

    if blocking:
        finished_event.wait()

async def _speak_async(text: str):
    communicate = edge_tts.Communicate(
        text=text.strip(),
        voice=VOICE,
        rate=RATE,
        volume=VOLUME,
        pitch=PITCH,
    )

    audio_bytes = io.BytesIO()

    async for chunk in communicate.stream():
        if stop_speaking_flag.is_set():
            return

        if chunk["type"] == "audio":
            audio_bytes.write(chunk["data"])

    audio_bytes.seek(0)

    data, samplerate = sf.read(audio_bytes, dtype="float32")

    channels = data.shape[1] if len(data.shape) > 1 else 1

    with sd.OutputStream(
        samplerate=samplerate,
        channels=channels,
        dtype="float32",
    ) as stream:
        block_size = 1024
        for start in range(0, len(data), block_size):
            if stop_speaking_flag.is_set():
                break
            stream.write(data[start:start + block_size])

def stop_speaking():
    stop_speaking_flag.set()