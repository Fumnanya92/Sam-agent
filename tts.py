import io
import threading
import asyncio
import sounddevice as sd
import soundfile as sf
import edge_tts
from shared_state import is_sam_speaking
from log.logger import get_logger

logger = get_logger("TTS")

# WebSocket TTS streaming — injected by daemon/main.py at startup so Sam's
# voice reaches the browser instead of (only) the server's local speakers.
_ws_event_loop = None       # asyncio loop running the FastAPI daemon
_ws_broadcast_bytes_fn = None  # async (bytes) -> None
_ws_broadcast_fn = None        # async (str, dict) -> None


def set_ws_tts_callbacks(loop, broadcast_bytes_fn, broadcast_fn) -> None:
    """Wire WebSocket audio streaming. Called once at daemon startup."""
    global _ws_event_loop, _ws_broadcast_bytes_fn, _ws_broadcast_fn
    _ws_event_loop = loop
    _ws_broadcast_bytes_fn = broadcast_bytes_fn
    _ws_broadcast_fn = broadcast_fn


def broadcast_to_web(event_type: str, payload: dict) -> None:
    """Fire-and-forget broadcast to connected WebSocket clients (no-op if daemon not wired)."""
    if _ws_broadcast_fn and _ws_event_loop and not _ws_event_loop.is_closed():
        asyncio.run_coroutine_threadsafe(
            _ws_broadcast_fn(event_type, payload),
            _ws_event_loop,
        )


VOICE = "en-US-AndrewMultilingualNeural"

RATE = "+0%"    # e.g. "+20%" faster, "-20%" slower
VOLUME = "+0%"
PITCH = "+0Hz"

# Speed levels — maps user intent to edge-tts rate strings
SPEED_LEVELS = {
    "slow":    "-25%",
    "slower":  "-25%",
    "normal":  "+0%",
    "default": "+0%",
    "fast":    "+25%",
    "faster":  "+25%",
    "very fast": "+50%",
}


def set_speed(level: str) -> str:
    """Change TTS speed. level = 'slow' | 'normal' | 'fast' | 'very fast'.
    Returns a confirmation string."""
    global RATE
    key = level.lower().strip()
    if key in SPEED_LEVELS:
        RATE = SPEED_LEVELS[key]
        return f"Speaking speed set to {level}."
    else:
        # Try raw percentage e.g. "+30%"
        if key.startswith(('+', '-')) and key.endswith('%'):
            RATE = key
            return f"Speaking rate set to {level}."
        return f"I don't know that speed setting. Try slow, normal, or fast."


def set_voice(voice_name: str) -> str:
    """Change TTS voice."""
    global VOICE
    VOICE = voice_name
    return f"Voice changed to {voice_name}."


stop_speaking_flag = threading.Event()

def edge_speak(text: str, ui=None, blocking=False, force=False):
    """Speak text aloud.

    force=True bypasses mute and meeting-mode checks (for critical responses).
    In meeting mode (mode='meeting'), Sam sends a Windows notification instead of speaking.
    When muted (is_muted()), Sam is silent.
    """
    if not text or not text.strip():
        return

    # Check mute flag
    from conversation_state import controller
    if not force and controller.is_muted():
        logger.info(f"TTS suppressed (muted): '{text[:60]}'")
        # Write to UI log silently
        if ui:
            ui.write_log(f"AI (silent): {text.strip()}")
        return

    # In meeting mode, use Windows notification instead of speaking
    if not force and controller.get_mode() == "meeting":
        logger.info(f"TTS → notification (meeting mode): '{text[:60]}'")
        try:
            from system.notifier import notify
            notify("Sam", text[:200])
        except Exception:
            pass
        if ui:
            ui.write_log(f"AI (notify): {text.strip()}")
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
                # Flush any transcripts queued BEFORE Sam started speaking
                import time as _flush_time
                _flush_time.sleep(0.15)
                _srv.clear_transcript_queue()
        except Exception:
            pass

        stop_speaking_flag.clear()
        logger.info(f"TTS START: \"{text[:80]}{'...' if len(text) > 80 else ''}\"")

        tts_ok = False
        try:
            asyncio.run(_speak_async(text))
            tts_ok = True
            logger.info("TTS COMPLETE — audio finished playing")
        except Exception as e:
            logger.error(f"TTS FAILED: {e}", exc_info=True)
        finally:
            is_sam_speaking.clear()
            if ui:
                ui.stop_speaking()
                ui.clear_transcription()
            if not tts_ok:
                logger.warning("TTS did not produce audio — Sam's response was text-only")
            # Resume speech client after Sam finishes
            try:
                from websocket_server import speech_server as _srv
                if _srv:
                    _srv.broadcast_command("sam_done")
                    import time as _time
                    # Wait 1.5 s for speaker audio to fully decay before re-activating
                    # the microphone — prevents Sam's own voice from being captured
                    _time.sleep(2.5)
                    _srv.clear_transcript_queue()  # drain any echoes queued during decay
                    _srv.broadcast_command("set_active")
            except Exception:
                pass
            finished_event.set()

    threading.Thread(target=_thread, daemon=True).start()

    if blocking:
        if not finished_event.wait(timeout=25):
            logger.error("TTS TIMEOUT — edge_speak took over 25 s; continuing anyway")

async def _speak_async(text: str):
    communicate = edge_tts.Communicate(
        text=text.strip(),
        voice=VOICE,
        rate=RATE,
        volume=VOLUME,
        pitch=PITCH,
    )

    audio_bytes = io.BytesIO()
    chunk_count = 0

    logger.debug("TTS: streaming audio from edge-tts...")
    # Wrap the stream in a 20s timeout — edge-tts HTTP can hang indefinitely
    try:
        async with asyncio.timeout(20):
            async for chunk in communicate.stream():
                if stop_speaking_flag.is_set():
                    logger.debug("TTS: stop flag set — aborting stream")
                    return
                if chunk["type"] == "audio":
                    audio_bytes.write(chunk["data"])
                    chunk_count += 1
    except asyncio.TimeoutError:
        logger.error("TTS: edge-tts stream timed out after 20s — no audio")
        return

    if chunk_count == 0:
        logger.error("TTS: edge-tts returned zero audio chunks — no audio to play")
        return

    logger.debug(f"TTS: received {chunk_count} audio chunks")

    # ── Daemon mode: stream audio to browser via WebSocket ────────────────────
    if _ws_event_loop is not None and _ws_broadcast_bytes_fn is not None and _ws_broadcast_fn is not None:
        import threading as _thr
        done_evt = _thr.Event()
        audio_bytes.seek(0)
        raw_audio = audio_bytes.read()

        async def _do_ws_broadcast():
            try:
                await _ws_broadcast_fn("tts_start", {"requestId": str(id(done_evt))})
                await _ws_broadcast_bytes_fn(raw_audio)
                await _ws_broadcast_fn("tts_end", {})
            finally:
                done_evt.set()

        asyncio.run_coroutine_threadsafe(_do_ws_broadcast(), _ws_event_loop)
        done_evt.wait(timeout=60)
        logger.debug("TTS: audio sent to browser via WebSocket")
        return  # skip local sounddevice playback

    # ── Standalone mode: play locally via sounddevice ─────────────────────────
    logger.debug("TTS: reading with soundfile for local playback")
    audio_bytes.seek(0)
    data, samplerate = sf.read(audio_bytes, dtype="float32")

    channels = data.shape[1] if len(data.shape) > 1 else 1
    logger.debug(f"TTS: playing audio — samplerate={samplerate}, channels={channels}, samples={len(data)}")

    with sd.OutputStream(
        samplerate=samplerate,
        channels=channels,
        dtype="float32",
    ) as stream:
        block_size = 1024
        for start in range(0, len(data), block_size):
            if stop_speaking_flag.is_set():
                logger.debug("TTS: stop flag set — aborting playback")
                break
            stream.write(data[start:start + block_size])

def stop_speaking():
    stop_speaking_flag.set()