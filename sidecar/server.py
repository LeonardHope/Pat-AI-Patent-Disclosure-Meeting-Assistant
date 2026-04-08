"""FastAPI server with WebSocket for real-time transcript and suggestions.

The server manages the audio pipeline, transcription, and LLM suggestion
loop. The frontend connects via WebSocket to receive live updates.
"""

import asyncio
import json
import logging
import threading
import time
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from audio.capture import SystemAudioCapture
from audio.microphone import MicrophoneCapture
from audio.vad import VADSegmenter, get_vad_model
from ai.claude_client import AnthropicLLMClient
from ai.suggestion_loop import SuggestionLoop
from config import Settings, MODELS_DIR, AUDIO_HELPER_DIR
from meeting.session import MeetingSession, MeetingState, Suggestion
from transcription.engine import WhisperEngine
from transcription.segment import TranscriptSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
settings = Settings.load()
session = MeetingSession()
whisper: WhisperEngine | None = None
remote_capture: SystemAudioCapture | None = None
local_capture: MicrophoneCapture | None = None
remote_vad: VADSegmenter | None = None
local_vad: VADSegmenter | None = None
connected_clients: set[WebSocket] = set()
suggestion_loop: SuggestionLoop | None = None
_event_loop: asyncio.AbstractEventLoop | None = None


# Audio monitor state (for VU meters on setup screen)
_monitor_remote: SystemAudioCapture | None = None
_monitor_local: MicrophoneCapture | None = None
_monitor_running = False


async def broadcast(message: dict) -> None:
    """Send a message to all connected WebSocket clients."""
    if not connected_clients:
        return
    text = json.dumps(message)
    disconnected = set()
    for ws in connected_clients:
        try:
            await ws.send_text(text)
        except Exception:
            disconnected.add(ws)
    for ws in disconnected:
        connected_clients.discard(ws)


def broadcast_sync(message: dict) -> None:
    """Thread-safe broadcast from non-async code."""
    if _event_loop is not None and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast(message), _event_loop)


def on_suggestions_update(suggestions: list[Suggestion]) -> None:
    """Called when the suggestion loop produces new suggestions."""
    msg = {
        "type": "suggestions_update",
        "data": [_suggestion_dict(s) for s in suggestions]
    }
    # Try async broadcast first (if called from event loop), fall back to sync
    try:
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(broadcast(msg))
    except RuntimeError:
        broadcast_sync(msg)


def on_transcript_segment(segment: TranscriptSegment) -> None:
    """Called when a new transcript segment is ready."""
    session.add_segment(segment)
    # Notify suggestion loop of new content
    if suggestion_loop:
        suggestion_loop.on_new_segment(segment.text)
    broadcast_sync({
        "type": "transcript_segment",
        "data": {
            "id": segment.id,
            "text": segment.text,
            "speaker": segment.speaker,
            "timestamp": segment.timestamp,
            "duration": segment.duration,
            "is_final": segment.is_final,
        }
    })


def transcribe_segment(audio: np.ndarray, speaker: str) -> None:
    """Transcribe an audio segment and broadcast the result."""
    if whisper is None or session.state != MeetingState.ACTIVE:
        return
    timestamp = time.monotonic() - session.start_time
    seg = whisper.transcribe(audio, speaker=speaker, timestamp=timestamp)
    if seg and seg.text.strip():
        on_transcript_segment(seg)


def on_remote_chunk(chunk: np.ndarray) -> None:
    if remote_vad is None or session.state != MeetingState.ACTIVE:
        return
    segments = remote_vad.process_chunk(chunk)
    for segment in segments:
        threading.Thread(
            target=transcribe_segment, args=(segment, "REMOTE"), daemon=True
        ).start()


def on_local_chunk(chunk: np.ndarray) -> None:
    if local_vad is None or session.state != MeetingState.ACTIVE:
        return
    segments = local_vad.process_chunk(chunk)
    for segment in segments:
        threading.Thread(
            target=transcribe_segment, args=(segment, "LOCAL"), daemon=True
        ).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup."""
    global whisper, _event_loop
    _event_loop = asyncio.get_event_loop()
    logger.info("Loading Whisper model...")
    model_path = MODELS_DIR / settings.whisper_model
    whisper = WhisperEngine(model_path=model_path)
    logger.info("Whisper model loaded")
    logger.info("Loading VAD model...")
    get_vad_model()  # Pre-load and cache
    logger.info("VAD model loaded")
    yield
    logger.info("Shutting down")
    stop_meeting()


app = FastAPI(title="Disclosure Meeting Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- WebSocket ----

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info(f"Client connected ({len(connected_clients)} total)")

    # Send current state
    await ws.send_text(json.dumps({
        "type": "meeting_status",
        "data": {"state": session.state.value}
    }))

    # Send existing suggestions
    if session.suggestions:
        await ws.send_text(json.dumps({
            "type": "suggestions_update",
            "data": [_suggestion_dict(s) for s in session.suggestions]
        }))

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            await handle_ws_message(ws, msg)
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(ws)
        logger.info(f"Client disconnected ({len(connected_clients)} total)")


async def handle_ws_message(ws: WebSocket, msg: dict) -> None:
    """Handle incoming WebSocket messages from the frontend."""
    msg_type = msg.get("type")

    if msg_type == "start_meeting":
        # Run in thread to avoid blocking event loop (audio setup is synchronous)
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: start_meeting(
                app_bundle_id=msg.get("app_bundle_id"),
                mic_device=msg.get("mic_device"),
            )
        )
        await broadcast({
            "type": "meeting_status",
            "data": {"state": session.state.value}
        })

    elif msg_type == "stop_meeting":
        stop_meeting()
        await broadcast({
            "type": "meeting_status",
            "data": {"state": session.state.value}
        })

    elif msg_type == "generate_summary":
        # Send "generating" status so UI shows feedback
        await ws.send_text(json.dumps({
            "type": "summary_status",
            "data": {"status": "generating"}
        }))

        transcript_text = session.get_transcript_text()
        if not transcript_text:
            await ws.send_text(json.dumps({
                "type": "summary",
                "data": {"markdown": "No transcript was captured during this meeting."}
            }))
        else:
            from meeting.summary import generate_summary_sync
            llm_client = _create_llm_client()
            summary = await asyncio.get_event_loop().run_in_executor(
                None, lambda: generate_summary_sync(session, llm_client)
            )
            await ws.send_text(json.dumps({
                "type": "summary",
                "data": {"markdown": summary}
            }))

        session.discard()
        await broadcast({
            "type": "meeting_status",
            "data": {"state": session.state.value}
        })

    elif msg_type == "start_audio_monitor":
        pass  # Disabled — was causing Swift process accumulation and crashes

    elif msg_type == "stop_audio_monitor":
        stop_audio_monitor()

    elif msg_type == "reset":
        session.discard()
        await broadcast({
            "type": "meeting_status",
            "data": {"state": session.state.value}
        })

    elif msg_type == "update_settings":
        data = msg.get("data", {})
        if "llm" in data:
            settings.llm = settings.llm.model_copy(update=data["llm"])
        if "suggestions" in data:
            settings.suggestions = settings.suggestions.model_copy(update=data["suggestions"])


# ---- Meeting lifecycle ----


# ---- Audio Monitor (VU meters for setup screen) ----

def start_audio_monitor(app_bundle_id: str | None = None, mic_device: int | None = None, mic_enabled: bool = False) -> None:
    global _monitor_remote, _monitor_local, _monitor_running

    stop_audio_monitor()  # Clean up any existing monitor

    _monitor_running = True
    # Track recent RMS levels
    remote_levels: list[float] = []
    local_levels: list[float] = []

    import math

    def on_remote_level(chunk: np.ndarray) -> None:
        if not _monitor_running:
            return
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        remote_levels.append(rms)
        if len(remote_levels) >= 10:  # ~300ms worth of 30ms chunks
            avg = sum(remote_levels) / len(remote_levels)
            remote_levels.clear()
            # Convert to dB-like scale (0-1 range)
            level = min(1.0, max(0.0, (math.log10(max(avg, 1e-7)) + 3) / 3))
            broadcast_sync({
                "type": "audio_level",
                "data": {"source": "remote", "level": round(level, 3)}
            })

    def on_local_level(chunk: np.ndarray) -> None:
        if not _monitor_running:
            return
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        local_levels.append(rms)
        if len(local_levels) >= 10:
            avg = sum(local_levels) / len(local_levels)
            local_levels.clear()
            level = min(1.0, max(0.0, (math.log10(max(avg, 1e-7)) + 3) / 3))
            broadcast_sync({
                "type": "audio_level",
                "data": {"source": "local", "level": round(level, 3)}
            })

    _monitor_remote = SystemAudioCapture(
        on_audio_chunk=on_remote_level,
        helper_dir=AUDIO_HELPER_DIR,
        app_bundle_id=app_bundle_id,
    )
    _monitor_remote.start()

    if mic_enabled:
        _monitor_local = MicrophoneCapture(
            on_audio_chunk=on_local_level,
            device=mic_device,
        )
        _monitor_local.start()

    logger.info("Audio monitor started")


def stop_audio_monitor() -> None:
    global _monitor_remote, _monitor_local, _monitor_running

    _monitor_running = False
    if _monitor_remote:
        _monitor_remote.stop()
        _monitor_remote = None
    if _monitor_local:
        _monitor_local.stop()
        _monitor_local = None
    import time
    time.sleep(0.5)  # Give processes time to die


def _create_llm_client():
    """Create LLM client — same Anthropic SDK for both local and cloud."""
    if settings.llm.provider == "claude" and settings.llm.claude_api_key:
        return AnthropicLLMClient(
            base_url="https://api.anthropic.com",
            api_key=settings.llm.claude_api_key,
            model=settings.llm.claude_model,
        )
    else:
        # Default: LM Studio (local, Anthropic-compatible endpoint)
        return AnthropicLLMClient(
            base_url=settings.llm.lmstudio_base_url,
            api_key="lmstudio",
            model=settings.llm.lmstudio_model,
        )


def start_meeting(app_bundle_id: str | None = None, mic_device: int | None = None) -> None:
    global remote_capture, local_capture, remote_vad, local_vad, suggestion_loop

    if session.state == MeetingState.ACTIVE:
        return

    stop_audio_monitor()  # Stop VU meters before starting meeting capture

    logger.info("Starting meeting...")
    session.start()

    remote_vad = VADSegmenter()
    remote_capture = SystemAudioCapture(
        on_audio_chunk=on_remote_chunk,
        helper_dir=AUDIO_HELPER_DIR,
        app_bundle_id=app_bundle_id,
    )
    remote_capture.start()

    if settings.audio.capture_microphone:
        local_vad = VADSegmenter()
        local_capture = MicrophoneCapture(
            on_audio_chunk=on_local_chunk,
            device=mic_device,
        )
        local_capture.start()
        logger.info("Microphone capture enabled")
    else:
        local_vad = None
        local_capture = None
        logger.info("Microphone capture disabled (system audio only)")

    # Start suggestion loop in background (LLM loading can be slow)
    async def _start_suggestions():
        global suggestion_loop
        try:
            llm_client = await asyncio.get_event_loop().run_in_executor(None, _create_llm_client)
            suggestion_loop = SuggestionLoop(
                session=session,
                llm_client=llm_client,
                on_suggestions_update=on_suggestions_update,
                debounce_seconds=settings.suggestions.debounce_seconds,
                min_interval_seconds=settings.suggestions.min_interval_seconds,
                max_suggestions=settings.suggestions.max_suggestions,
            )
            suggestion_loop.start()
            logger.info("Suggestion loop active")
        except Exception as e:
            logger.warning(f"LLM not available, suggestions disabled: {e}")
            suggestion_loop = None

    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(_start_suggestions(), _event_loop)

    logger.info("Meeting started — capturing audio")


def stop_meeting() -> None:
    global remote_capture, local_capture, remote_vad, local_vad, suggestion_loop

    if session.state != MeetingState.ACTIVE:
        return

    logger.info("Stopping meeting...")

    if suggestion_loop:
        suggestion_loop.stop()
        suggestion_loop = None

    if remote_capture:
        remote_capture.stop()
        remote_capture = None
    if local_capture:
        local_capture.stop()
        local_capture = None

    # Flush remaining audio
    if remote_vad:
        for segment in remote_vad.flush():
            transcribe_segment(segment, "REMOTE")
        remote_vad = None
    if local_vad:
        for segment in local_vad.flush():
            transcribe_segment(segment, "LOCAL")
        local_vad = None

    session.end()
    logger.info("Meeting ended")


# ---- REST endpoints ----

@app.get("/api/status")
async def get_status():
    return {
        "state": session.state.value,
        "transcript_segments": len(session.transcript),
        "suggestions": len(session.suggestions),
        "documents": len(session.document_names),
    }


@app.get("/api/devices")
async def get_devices():
    from audio.microphone import MicrophoneCapture
    from audio.capture import SystemAudioCapture
    return {
        "microphones": MicrophoneCapture.list_devices(),
        "apps": SystemAudioCapture.list_apps(),
    }


@app.post("/api/documents/analyze")
async def analyze_documents():
    """Analyze uploaded documents and return top 3 pre-meeting questions."""
    if not session.document_texts:
        return {"error": "No documents uploaded"}

    from ai.prompts.document_analysis import DOCUMENT_ANALYSIS_PROMPT

    # Keep docs short for fast CPU inference (~5s at 4K chars vs ~60s at 20K)
    max_chars_per_doc = 4000 // max(len(session.document_texts), 1)
    doc_context = "\n\n".join(
        f"### {name}\n{text[:max_chars_per_doc]}"
        for name, text in zip(session.document_names, session.document_texts)
    )

    messages = [
        {"role": "system", "content": DOCUMENT_ANALYSIS_PROMPT},
        {"role": "user", "content": doc_context},
    ]

    try:
        llm_client = _create_llm_client()
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: llm_client.generate_sync(messages)
        )

        # Parse JSON from response — LLMs often produce invalid JSON or thinking text
        import json as jsonlib
        import re
        text = response.strip()
        # Strip Qwen 3.5 thinking text (everything before the first { or [)
        first_brace = text.find("{")
        first_bracket = text.find("[")
        if first_brace > 0 or first_bracket > 0:
            start_pos = min(p for p in [first_brace, first_bracket] if p >= 0)
            text = text[start_pos:]
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            json_text = text[start:end]
            # Fix common LLM JSON errors
            json_text = re.sub(r',\s*}', '}', json_text)  # trailing comma before }
            json_text = re.sub(r',\s*]', ']', json_text)  # trailing comma before ]
            try:
                return jsonlib.loads(json_text)
            except jsonlib.JSONDecodeError:
                # Last resort: try to extract fields manually
                summary = ""
                m = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', json_text)
                if m:
                    summary = m.group(1)
                questions = []
                for qm in re.finditer(r'"question"\s*:\s*"((?:[^"\\]|\\.)*)"', json_text):
                    rm = re.search(r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"', json_text[qm.end():qm.end()+500])
                    questions.append({
                        "question": qm.group(1),
                        "reason": rm.group(1) if rm else ""
                    })
                if summary or questions:
                    return {"summary": summary, "top_questions": questions[:3]}
        return {"error": "Failed to parse LLM response"}
    except Exception as e:
        logger.error(f"Document analysis failed: {e}")
        return {"error": str(e)}


def _sync_generate(client, messages):
    """Synchronous wrapper for LLM generate (for run_in_executor)."""
    import asyncio
    result = client.generate(messages)
    if asyncio.iscoroutine(result):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(result)
        finally:
            loop.close()
    return result


@app.delete("/api/documents")
async def clear_documents():
    """Clear all uploaded documents from the session."""
    session.document_names.clear()
    session.document_texts.clear()
    return {"status": "cleared"}


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    from documents.parser import parse_document
    content = await file.read()
    filename = file.filename or "untitled"

    # Check file size limit (10MB)
    if len(content) > 10 * 1024 * 1024:
        return {"error": "File too large. Maximum 10MB per document."}

    text = parse_document(content, filename)

    # Check total document context won't overflow LLM
    total_chars = sum(len(t) for t in session.document_texts) + len(text)
    provider = settings.llm.provider
    if provider == "claude":
        max_chars = 200000  # Claude has ~200K token context
    else:
        max_chars = 60000  # Local models truncate to fit; allow larger uploads

    if total_chars > max_chars:
        return {
            "error": f"Total document text ({total_chars:,} chars) exceeds the {provider} model's capacity ({max_chars:,} chars). Try shorter documents or switch to Claude API for larger context.",
            "total_chars": total_chars,
            "max_chars": max_chars,
        }

    session.document_names.append(filename)
    session.document_texts.append(text)

    # Auto-extract technical vocabulary for Whisper from uploaded documents
    if whisper:
        import re
        # Only extract technical terms and acronyms, keep lowercase
        acronyms = set(re.findall(r'\b[A-Z]{2,}\b', text))  # GPU, CPU, GUI, etc.
        # Extract multi-word technical terms
        tech_terms = set()
        for term in ["data center", "rack", "server", "deployment", "validation",
                      "constraint", "component", "workload", "cooling", "power supply",
                      "shelf", "switch", "historical data", "predictive", "assembly"]:
            if term.lower() in text.lower():
                tech_terms.add(term)
        all_terms = sorted(acronyms | tech_terms)[:30]
        if all_terms:
            vocab = ", ".join(all_terms)
            whisper.set_vocab_prompt(vocab)
            logger.info(f"Whisper vocab: {vocab}")

    return {
        "filename": filename,
        "size": len(content),
        "text_length": len(text),
        "total_chars": total_chars,
        "max_chars": max_chars,
    }


@app.post("/api/summary")
async def generate_meeting_summary():
    """Generate post-meeting summary (only available when meeting has ended)."""
    if session.state != MeetingState.ENDED:
        return {"error": "Meeting must be ended first"}
    from meeting.summary import generate_summary
    llm_client = _create_llm_client()
    summary = await generate_summary(session, llm_client)
    session.discard()
    return {"markdown": summary}



@app.get("/api/prompt")
async def get_system_prompt():
    from ai.prompts.system_prompt import SYSTEM_PROMPT
    return {"prompt": SYSTEM_PROMPT}


@app.post("/api/prompt")
async def set_system_prompt(data: dict):
    import ai.prompts.system_prompt as sp
    sp.SYSTEM_PROMPT = data.get("prompt", sp.SYSTEM_PROMPT)
    return {"prompt": sp.SYSTEM_PROMPT}


@app.get("/api/llm/status")
async def llm_status():
    """Check if the LLM endpoint is reachable."""
    client = _create_llm_client()
    available = client.is_available()
    return {
        "available": available,
        "provider": settings.llm.provider,
        "base_url": settings.llm.lmstudio_base_url if settings.llm.provider == "lmstudio" else "https://api.anthropic.com",
    }


@app.get("/api/settings")
async def get_settings():
    return settings.model_dump()


@app.post("/api/settings")
async def update_settings(data: dict):
    if "llm" in data:
        settings.llm = settings.llm.model_copy(update=data["llm"])
    if "suggestions" in data:
        settings.suggestions = settings.suggestions.model_copy(update=data["suggestions"])
    if "audio" in data:
        settings.audio = settings.audio.model_copy(update=data["audio"])
    settings.save()
    return settings.model_dump()


# ---- Helpers ----

def _suggestion_dict(s: Suggestion) -> dict:
    return {
        "id": s.id,
        "category": s.category,
        "priority": s.priority,
        "suggestion": s.suggestion,
        "context": s.context,
        "timestamp": s.timestamp,
    }
