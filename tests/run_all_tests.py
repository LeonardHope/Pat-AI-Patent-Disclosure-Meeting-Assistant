"""Run all automated tests for the Disclosure Meeting Assistant.

Usage:
    cd sidecar && uv run python ../tests/run_all_tests.py
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "sidecar"))

passed = 0
failed = 0
warnings = 0


def test(name):
    def decorator(func):
        def wrapper():
            global passed, failed, warnings
            print(f"\n{'='*60}")
            print(f"TEST: {name}")
            print(f"{'='*60}")
            try:
                result = func()
                if result == "warn":
                    warnings += 1
                    print(f"  ⚠ WARNING")
                else:
                    passed += 1
                    print(f"  PASSED")
            except Exception as e:
                failed += 1
                print(f"  FAILED: {e}")
        return wrapper
    return decorator


@test("Module imports")
def test_imports():
    from audio.capture import SystemAudioCapture
    from audio.microphone import MicrophoneCapture
    from audio.vad import VADSegmenter, get_vad_model
    from transcription.engine import WhisperEngine
    from transcription.segment import TranscriptSegment
    from ai.llamacpp_client import LlamaCppClient, MODEL_CONFIGS, recommend_model
    from ai.ollama_client import OllamaClient
    from ai.claude_client import ClaudeClient
    from ai.context_builder import build_suggestion_prompt
    from ai.suggestion_loop import SuggestionLoop
    from documents.parser import parse_document
    from documents.chunker import chunk_text
    from meeting.session import MeetingSession, MeetingState, Suggestion
    from meeting.summary import generate_summary, export_markdown
    from config import Settings
    print("  All modules imported successfully")


@test("Audio capture (REMOTE + LOCAL, 3 seconds)")
def test_audio_capture():
    from audio.capture import SystemAudioCapture
    from audio.microphone import MicrophoneCapture

    remote_chunks, local_chunks = [], []
    rc = SystemAudioCapture(on_audio_chunk=lambda c: remote_chunks.append(c.copy()))
    lc = MicrophoneCapture(on_audio_chunk=lambda c: local_chunks.append(c.copy()))
    rc.start()
    lc.start()
    time.sleep(3)
    rc.stop()
    lc.stop()

    r_audio = np.concatenate(remote_chunks) if remote_chunks else np.array([])
    l_audio = np.concatenate(local_chunks) if local_chunks else np.array([])
    r_rms = float(np.sqrt(np.mean(r_audio**2))) if len(r_audio) > 0 else 0

    print(f"  REMOTE: {len(remote_chunks)} chunks, {len(r_audio)/16000:.1f}s, RMS={r_rms:.4f}")
    print(f"  LOCAL:  {len(local_chunks)} chunks, {len(l_audio)/16000:.1f}s")

    assert len(remote_chunks) > 0, "No REMOTE chunks captured"
    assert len(local_chunks) > 0, "No LOCAL chunks captured"

    if r_rms < 0.01:
        print("  Note: REMOTE audio is silent (VLC may be paused)")
        return "warn"


@test("VAD speech detection")
def test_vad():
    from audio.vad import get_vad_model
    from silero_vad import get_speech_timestamps
    import torch

    model = get_vad_model()

    # Generate speech-like signal (AM noise)
    t = np.linspace(0, 2, 32000)
    signal = (np.random.randn(32000) * 0.3 * np.abs(np.sin(2 * np.pi * 4 * t))).astype(np.float32)

    # Use batch API (which we confirmed works)
    timestamps = get_speech_timestamps(torch.from_numpy(signal), model, sampling_rate=16000, threshold=0.1)
    model.reset_states()
    print(f"  VAD detected {len(timestamps)} segments in synthetic signal")
    # VAD may or may not detect speech in synthetic noise — just verify it runs without error


@test("Whisper transcription")
def test_whisper():
    from transcription.engine import WhisperEngine

    engine = WhisperEngine()

    # Transcribe a short sine wave (should produce empty or minimal output)
    silence = np.zeros(16000, dtype=np.float32)
    result = engine.transcribe(silence, speaker="TEST", timestamp=0.0)
    print(f"  Silence result: {result.text if result else 'None'}")

    # Transcribe noise (should produce something)
    np.random.seed(42)
    noise = np.random.randn(16000 * 3).astype(np.float32) * 0.1
    result2 = engine.transcribe(noise, speaker="TEST", timestamp=0.0)
    print(f"  Noise result: {result2.text[:50] if result2 else 'None'}")
    print("  Whisper runs correctly")


@test("Document parser")
def test_documents():
    from documents.parser import parse_document
    from documents.chunker import chunk_text

    # Plain text
    text = parse_document(b"Test disclosure. Data compression invention.", "test.txt")
    assert "compression" in text

    # Chunking
    long_text = "This is a sentence. " * 200
    chunks = chunk_text(long_text, max_chunk_chars=500, overlap_chars=50)
    assert len(chunks) > 1
    print(f"  Text parsing OK, chunked {len(long_text)} chars into {len(chunks)} chunks")


@test("Context builder")
def test_context_builder():
    from ai.context_builder import build_suggestion_prompt
    from meeting.session import MeetingSession
    from transcription.segment import TranscriptSegment

    session = MeetingSession()
    session.start()
    session.add_segment(TranscriptSegment(text="We built a new compression system.", speaker="REMOTE", timestamp=0))
    session.add_segment(TranscriptSegment(text="How does it work?", speaker="LOCAL", timestamp=3))
    session.document_names.append("disclosure.pdf")
    session.document_texts.append("Novel data compression using streaming algorithm.")

    messages = build_suggestion_prompt(session, max_suggestions=5)
    assert len(messages) == 2
    assert "enablement" in messages[0]["content"].lower()
    assert "compression" in messages[1]["content"].lower()
    assert "disclosure.pdf" in messages[1]["content"]
    print(f"  System prompt: {len(messages[0]['content'])} chars")
    print(f"  User context:  {len(messages[1]['content'])} chars")


@test("Suggestion loop (mock LLM)")
def test_suggestion_loop():
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "test_suggestion_engine.py")],
        capture_output=True, text=True, timeout=30,
        cwd=str(Path(__file__).parent.parent / "sidecar"),
    )
    # Check for PASSED in output
    if "ALL TESTS PASSED" in result.stdout:
        print("  Suggestion engine tests passed")
    else:
        print(result.stdout[-500:] if result.stdout else "")
        print(result.stderr[-500:] if result.stderr else "")
        raise AssertionError("Suggestion engine tests failed")


@test("Meeting session lifecycle")
def test_session():
    from meeting.session import MeetingSession, MeetingState, Suggestion
    from transcription.segment import TranscriptSegment

    s = MeetingSession()
    assert s.state == MeetingState.IDLE

    s.start()
    assert s.state == MeetingState.ACTIVE
    s.add_segment(TranscriptSegment(text="Hello", speaker="REMOTE", timestamp=0))
    assert len(s.transcript) == 1

    s.update_suggestions([Suggestion(id="s1", category="ENABLEMENT", priority="HIGH", suggestion="Ask X", context="Y")])
    assert len(s.suggestions) == 1

    s.end()
    assert s.state == MeetingState.ENDED

    s.discard()
    assert s.state == MeetingState.IDLE
    assert len(s.transcript) == 0
    assert len(s.suggestions) == 0
    print("  Lifecycle: idle -> active -> ended -> idle (discarded)")


@test("LLM model management")
def test_model_management():
    from ai.llamacpp_client import MODEL_CONFIGS, recommend_model, is_model_downloaded

    recommended = recommend_model()
    print(f"  Recommended model: {recommended}")
    assert recommended in MODEL_CONFIGS

    for name, config in MODEL_CONFIGS.items():
        downloaded = is_model_downloaded(name)
        print(f"  {name}: {config['size_gb']}GB, min {config['min_ram_gb']}GB RAM, downloaded={downloaded}")


@test("FastAPI server (REST + WebSocket, 15s meeting)")
def test_server():
    # Kill any existing server
    subprocess.run("lsof -ti:8000 | xargs kill -9", shell=True, capture_output=True)
    time.sleep(1)

    # Start server
    server = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(Path(__file__).parent.parent / "sidecar"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    try:
        # Wait for startup
        for i in range(30):
            if subprocess.run(["curl", "-s", "http://127.0.0.1:8000/api/status"],
                            capture_output=True).returncode == 0:
                break
            time.sleep(1)

        import httpx
        # REST tests
        r = httpx.get("http://127.0.0.1:8000/api/status")
        status = r.json()
        assert status["state"] == "idle", f"Expected idle, got {status['state']}"
        print(f"  REST /api/status: {status}")

        r2 = httpx.get("http://127.0.0.1:8000/api/devices")
        devices = r2.json()
        print(f"  REST /api/devices: {len(devices['microphones'])} mics")

        r3 = httpx.get("http://127.0.0.1:8000/api/models")
        models = r3.json()
        print(f"  REST /api/models: {len(models['models'])} models, recommended={models['recommended']}")

        # WebSocket test with meeting
        import websockets.sync.client as wsc
        ws = wsc.connect("ws://127.0.0.1:8000/ws")

        initial = json.loads(ws.recv(timeout=5))
        assert initial["data"]["state"] == "idle"

        ws.send(json.dumps({"type": "start_meeting"}))
        started = json.loads(ws.recv(timeout=15))
        assert started["data"]["state"] == "active", f"Expected active, got {started}"

        segments = 0
        start = time.time()
        while time.time() - start < 12:
            try:
                msg = json.loads(ws.recv(timeout=2))
                if msg["type"] == "transcript_segment":
                    segments += 1
                    d = msg["data"]
                    if segments <= 3:
                        print(f"  WS [{d['speaker']:6s}] {d['text'][:60]}")
            except TimeoutError:
                pass

        ws.send(json.dumps({"type": "stop_meeting"}))
        try:
            final = json.loads(ws.recv(timeout=5))
            print(f"  Meeting stopped: {final['data']['state']}")
        except:
            pass

        ws.close()
        print(f"  WebSocket segments received: {segments}")

        if segments == 0:
            print("  Note: 0 segments (VLC may be paused or in silent section)")
            return "warn"

    finally:
        server.terminate()
        server.wait(timeout=5)


# ---- Run all tests ----

if __name__ == "__main__":
    tests = [
        test_imports,
        test_audio_capture,
        test_vad,
        test_whisper,
        test_documents,
        test_context_builder,
        test_suggestion_loop,
        test_session,
        test_model_management,
        test_server,
    ]

    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed, {warnings} warnings")
    print(f"{'='*60}")

    if failed > 0:
        sys.exit(1)
