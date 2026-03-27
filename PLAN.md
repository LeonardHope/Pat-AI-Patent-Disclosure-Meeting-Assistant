# Disclosure Meeting Assistant — Implementation Plan

## Context

Patent attorneys need to extract complete technical details during inventor disclosure meetings to draft strong applications. Missing details means follow-up meetings or weak applications. This app provides **live, real-time suggestions** to the patent attorney during the meeting — telling them what to ask before the conversation moves on.

This is NOT a transcription tool or meeting recorder. Transcripts are ephemeral (memory only, discarded after the meeting). The entire value is in the live suggestion experience.

**Key constraints:**
- Invention disclosures are confidential — fully local/private by default (bundled local LLM)
- Distributed as a native macOS `.app` — install via `.dmg` drag-and-drop, zero terminal usage
- No custom audio drivers — uses macOS ScreenCaptureKit (13+) or AudioProcessTap (14.2+)
- Speed is critical — suggestions must appear within ~15 seconds of relevant speech
- Recording consent disclaimer in settings (users are attorneys who understand consent requirements)

---

## Architecture: Tauri v2 + React + Python Sidecar

```
┌──────────────────────────────────────────────────────────────────┐
│                    Tauri v2 App Shell (Rust)                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              React Frontend (WebKit WebView)               │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │  │
│  │  │  Transcript   │  │  Suggestions │  │  Settings /    │  │  │
│  │  │  Panel        │  │  (max 5)     │  │  Doc Upload    │  │  │
│  │  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  │  │
│  └─────────┼──────────────────┼──────────────────┼───────────┘  │
│            │                  │                   │              │
│  ┌─────────┴──────────────────┴──────────────────┴───────────┐  │
│  │              Tauri IPC (commands + events)                 │  │
│  └─────────┬──────────────────────────────────────────────┬──┘  │
│            │                                              │     │
│  ┌─────────┴───────────┐                    ┌─────────────┴──┐  │
│  │  Python Sidecar     │                    │  Swift Audio   │  │
│  │  (bundled binary)   │                    │  Helper        │  │
│  │                     │                    │  (bundled)     │  │
│  │  - FastAPI server   │                    │                │  │
│  │  - Whisper (Metal)  │  subprocess PCM    │  ScreenCapture │  │
│  │  - Silero VAD       │<───────────────────│  Kit -> stdout │  │
│  │  - llama-cpp-python │                    │                │  │
│  │  - Claude API (opt) │                    └────────────────┘  │
│  │  - Doc parsing      │                                        │
│  └─────────────────────┘                                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| App shell | Tauri v2 (Rust) | Native .app, ~5MB, .dmg distribution |
| Frontend | React + TypeScript + Vite + TailwindCSS | Rich ecosystem, familiar |
| Audio capture | Swift CLI using ScreenCaptureKit | No drivers, captures any app's audio |
| Microphone | `sounddevice` (Python) | Simple, reliable |
| VAD | Silero VAD (ONNX Runtime) | Lightweight (~30MB vs ~200MB+ for torch) |
| Transcription | whisper.cpp via `pywhispercpp` | Metal on Apple Silicon, large-v3-turbo |
| Local LLM (default) | `llama-cpp-python` with Metal | Bundled, zero setup, no Ollama needed |
| Local LLM (advanced) | Ollama (optional) | For power users with custom setups |
| Cloud LLM (optional) | Anthropic Claude API | Best reasoning when privacy allows |
| Backend | FastAPI (inside sidecar) | WebSocket + REST, async Python |
| State mgmt | Zustand (frontend) | Minimal boilerplate |
| Packaging | Tauri bundler + PyInstaller | Single .dmg |

### Hardware Budget (32GB M-series Mac)

| Component | RAM | Notes |
|-----------|-----|-------|
| Whisper large-v3-turbo | ~2 GB | Metal GPU |
| llama-cpp-python + Qwen 2.5 14B Q4_K_M | ~9 GB | Metal GPU |
| Python sidecar + ONNX VAD | ~0.5 GB | CPU |
| Tauri app + WebKit | ~0.1 GB | Native WebView |
| macOS + other apps | ~8 GB | |
| **Headroom** | **~12 GB** | |

---

## Audio Capture

### Two Independent Streams

The app captures **two separate audio streams**, transcribed independently:

1. **System audio (REMOTE)** — the remote party's voice, captured via ScreenCaptureKit or AudioProcessTap
2. **Microphone (LOCAL)** — the attorney's voice, captured via sounddevice

These are NEVER mixed. Each stream goes through its own VAD → Whisper pipeline. Transcript segments are labeled `REMOTE` or `LOCAL`. Both provide context to the LLM.

This avoids echo/duplication when the user is on speakers, and gives free speaker separation.

### ScreenCaptureKit (macOS 13+)

- Captures audio at the system mixer level, before it reaches the output device
- Works with headphones, speakers, any output configuration
- Can filter to a **specific app** (Zoom, Teams, etc.) — avoids capturing notification sounds
- Requires Screen Recording permission (one-time OS prompt)
- Implementation: Swift CLI that outputs 16kHz 16-bit mono PCM to stdout
- Gotcha: must also configure a minimal display capture (1x1px at 1fps) to enable audio

### AudioProcessTap (macOS 14.2+, preferred when available)

- Dedicated audio tap API, no screen capture workaround needed
- Can tap audio from specific processes
- No Screen Recording permission needed (just audio permission)
- Cleaner implementation

**Strategy:** Use AudioProcessTap on 14.2+, ScreenCaptureKit fallback on 13.0-14.1. Minimum requirement: macOS 13.0 (Ventura).

### App-Specific Audio Selection

On "Start Meeting", the app lists running audio-capable applications (from `SCShareableContent.current`). The user picks which app is their meeting. Fallback: "All System Audio".

---

## Suggestion Engine

### Core Design Principles

1. **Speed over completeness** — a good suggestion now beats a perfect suggestion 30 seconds from now
2. **Focused, not overwhelming** — max N suggestions visible (default 5, configurable 3-7)
3. **Dynamic, not cumulative** — each LLM call returns a fresh ranked set; stale/answered suggestions auto-dismiss
4. **The #1 suggestion is always the most urgent thing to ask right now**

### Suggestion UX: Smart Ranked List (v1)

Up to N suggestions displayed, ranked by urgency. Each LLM call returns an updated set:
- New suggestions added based on recent transcript
- Suggestions that were addressed in conversation are removed
- Remaining suggestions reordered by relevance to current topic
- The list stays fresh and focused

**Future alternative (v2, after testing):** Single spotlight + collapsed queue — one prominent "ask this now" with a smaller queue below.

### Suggestion Categories

| Category | Description |
|----------|-------------|
| `ENABLEMENT` | Missing details for a PHOSITA to reproduce the invention |
| `BEST_MODE` | Preferred embodiment not yet disclosed |
| `WRITTEN_DESCRIPTION` | Insufficient detail to demonstrate possession |
| `CLAIM_ELEMENT` | A potential claim feature emerging |
| `PRIOR_ART` | Opportunity to differentiate from existing approaches |
| `TECHNICAL_DETAIL` | Specific parameters, algorithms, or configurations needed |
| `FOLLOW_UP` | General clarification needed |

### Latency Budget (~15 seconds total)

| Stage | Time | Notes |
|-------|------|-------|
| Speech → VAD → buffer | ~1s | 500ms silence threshold triggers segment |
| Whisper transcription | ~1s | 3-5s audio chunk on Metal |
| Debounce wait | ~8s | Resets on new segments; bypassed by keyword triggers |
| LLM inference | ~6s | 14B at ~25 tok/s, ~150 tokens for 5 suggestions |
| **Total** | **~16s** | Keyword triggers reduce to ~8s |

### Debouncing Strategy

- **8-second timer** after each new transcript segment (resets on new segments)
- **Immediate trigger** on 3+ second speech pauses
- **Keyword triggers** (bypass debounce): "the way it works", "what's different", "the key innovation", "the problem we're solving"
- **Rate limit**: max once per 8 seconds
- **Skip if unchanged**: no new transcript = no call

### GPU Contention: Whisper vs LLM

Both use Metal. Whisper gets priority (latency-sensitive). LLM inference happens during natural conversation pauses. In practice, Whisper processes a chunk in ~0.3-0.5s, leaving ample GPU headroom. If contention arises, add a simple mutex.

### Context Window Management

Each LLM call includes:
- System prompt (~800 tokens) — patent prosecution expertise
- Pre-meeting document context (~2,000 tokens) — uploaded disclosure materials
- Rolling transcript window (~3,000 tokens) — last ~8 minutes, both LOCAL and REMOTE
- Current visible suggestions (~300 tokens) — for the LLM to update/remove stale ones
- **Total: ~6,100 tokens** — well within Qwen 2.5 14B's 32K context

The LLM returns a JSON array of up to N ranked suggestions. Each has: category, priority, the question to ask, and brief context for why.

---

## LLM Provider Architecture

### Unified Interface

```python
class LLMClient(Protocol):
    async def get_suggestions(self, messages: list[dict]) -> AsyncIterator[str]: ...

class LlamaCppClient(LLMClient):     # Bundled, zero setup (default)
class OllamaClient(LLMClient):       # Optional, for power users
class ClaudeClient(LLMClient):       # Optional, requires API key
```

### Model Management

- Models stored in `~/Library/Application Support/Disclosure Meeting Assistant/models/`
- First-run wizard auto-detects RAM and recommends model size:
  - 16GB Mac → 7B model (~3GB download)
  - 32GB Mac → 14B model (~8GB download)
  - 64GB+ Mac → 32B model (~18GB download)
- Whisper model also auto-downloaded on first run (~1.5GB)
- Progress bar during download

### Bundled vs Ollama vs Claude

| Feature | Bundled (default) | Ollama | Claude API |
|---------|-------------------|--------|------------|
| Setup required | None | Install Ollama + pull model | API key |
| Privacy | Fully local | Fully local | Cloud |
| Offline capable | Yes | Yes | No |

---

## Document Ingestion (Pre-Call)

Users upload disclosure materials before the meeting to give the LLM context.

### Supported Formats
- PDF (via `pymupdf`)
- DOCX (via `python-docx`)
- PPTX (via `python-pptx`)
- Plain text / Markdown

### Processing
1. **Parse** — extract raw text
2. **Chunk** — split into ~500-token segments with 50-token overlap
3. **Pre-call analysis** — LLM generates a summary + identifies key technical elements
4. **During call** — most relevant chunks included in each LLM prompt (keyword overlap with recent transcript)

No vector database — documents are small enough to fit in context directly.

---

## Post-Meeting Summary

When the attorney clicks "End Meeting":

1. **Generate summary** from in-memory transcript (single LLM call):
   - Invention summary
   - Key technical elements / potential claim elements
   - Enablement gaps (what still needs detail)
   - Best mode gaps
   - Prior art differentiation points
   - Prioritized follow-up items
2. **Display summary** in the app with option to export (Markdown / DOCX)
3. **Discard transcript** from memory — only the generated summary persists if exported

---

## Data & Privacy

- **No telemetry or analytics** — zero outbound network calls unless Claude API is explicitly enabled
- **Transcripts are ephemeral** — memory only, discarded when meeting ends (after optional summary)
- **No meeting history** — each session is independent
- **Settings stored locally** in `~/Library/Application Support/`
- **Document uploads** processed in memory, not persisted
- **Recording consent disclaimer** available in settings

---

## User Experience

### First Launch

1. Download `.dmg`, drag to Applications
2. Launch app
3. **First-run wizard**:
   - Grant Screen Recording permission (app opens System Settings)
   - Auto-detect RAM, recommend and download LLM model
   - Auto-download Whisper model
   - Progress bar, can run in background
4. Ready — no terminal, no Homebrew, no Python

### Meeting Flow

1. Open the app
2. **(Optional)** Upload disclosure documents for pre-call context
3. Click "Start Meeting" — pick which app to capture audio from
4. Live transcript flows in the left panel (ephemeral, for reference during meeting)
5. Up to 5 suggestions in the right panel, auto-updating as conversation evolves
6. Click "End Meeting" — summary generated, transcript discarded
7. Export summary if desired

### Settings

- LLM provider: Bundled (default) / Ollama / Claude API
- Model selection (auto-detected by RAM or manual)
- Ollama host/model (advanced)
- Claude API key and model (if cloud enabled)
- Max suggestions displayed (default 5, range 3-7)
- Suggestion update frequency (default 8s)
- Microphone selection
- Recording consent disclaimer toggle

---

## Project Structure

```
disclosure-meeting-assistant/
├── PLAN.md
├── .gitignore
│
├── src-tauri/                        # Tauri v2 Rust backend
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── capabilities/
│   ├── icons/
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs
│   │   └── commands/
│   │       ├── mod.rs
│   │       ├── meeting.rs            # Start/stop meeting
│   │       ├── settings.rs           # Settings CRUD
│   │       ├── documents.rs          # Document upload
│   │       └── models.rs             # Model download/management
│   └── binaries/
│       └── audio-helper-aarch64-apple-darwin
│
├── audio-helper/                     # Swift ScreenCaptureKit source
│   ├── Package.swift
│   └── Sources/AudioCapture/
│       └── main.swift
│
├── sidecar/                          # Python sidecar (bundled via PyInstaller)
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── main.py                       # Entry point: starts FastAPI server
│   ├── config.py
│   │
│   ├── audio/
│   │   ├── capture.py                # Swift helper subprocess (REMOTE stream)
│   │   ├── microphone.py             # sounddevice mic (LOCAL stream)
│   │   ├── vad.py                    # Silero VAD (ONNX Runtime)
│   │   └── buffer.py                 # Speech segment accumulator
│   │
│   ├── transcription/
│   │   ├── engine.py                 # pywhispercpp + model loading
│   │   └── segment.py               # TranscriptSegment dataclass
│   │
│   ├── ai/
│   │   ├── llm_client.py            # Unified LLM protocol
│   │   ├── llamacpp_client.py        # Bundled llama-cpp-python
│   │   ├── ollama_client.py          # Ollama (optional)
│   │   ├── claude_client.py          # Claude API (optional)
│   │   ├── context_builder.py        # Prompt assembly + token budgeting
│   │   ├── suggestion_loop.py        # Debounce, trigger, rate limit
│   │   └── prompts/
│   │       ├── system_prompt.py      # Patent expert system prompt
│   │       ├── summary_prompt.py     # Post-meeting summary
│   │       └── document_analysis.py  # Pre-call document analysis
│   │
│   ├── documents/
│   │   ├── parser.py                 # PDF, DOCX, PPTX parsing
│   │   └── chunker.py               # Token-aware text chunking
│   │
│   ├── meeting/
│   │   ├── session.py                # In-memory meeting state
│   │   └── summary.py               # Post-meeting summary generation
│   │
│   └── server.py                     # FastAPI + WebSocket endpoints
│
├── src/                              # React frontend
│   ├── App.tsx
│   ├── main.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useTranscript.ts
│   │   └── useSuggestions.ts
│   ├── components/
│   │   ├── Layout.tsx
│   │   ├── TranscriptPanel.tsx
│   │   ├── SuggestionPanel.tsx
│   │   ├── SuggestionCard.tsx
│   │   ├── DocumentUpload.tsx
│   │   ├── PreCallSetup.tsx
│   │   ├── SettingsPanel.tsx
│   │   ├── MeetingControls.tsx
│   │   ├── FirstRunWizard.tsx
│   │   ├── ModelDownload.tsx
│   │   └── PostMeetingSummary.tsx
│   ├── stores/
│   │   └── meetingStore.ts
│   └── types/
│       └── index.ts
│
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
│
├── scripts/
│   ├── build-audio-helper.sh
│   ├── build-sidecar.sh
│   └── dev.sh
│
└── tests/
    ├── test_audio_capture.py
    ├── test_vad.py
    ├── test_transcription.py
    ├── test_context_builder.py
    └── test_suggestion_loop.py
```

---

## Implementation Phases

### Phase 1: Audio Pipeline
**Goal:** Capture two independent audio streams, verify by saving to WAV.

1. Build Swift audio helper using ScreenCaptureKit (with app-selection support)
2. Python capture module: subprocess reads REMOTE PCM from Swift helper stdout
3. Python mic module: sounddevice captures LOCAL stream
4. Save each stream to separate WAV files for verification

**Verify:** Run a Zoom call, confirm REMOTE.wav has the other party's voice, LOCAL.wav has yours.

### Phase 2: Transcription
**Goal:** Two parallel live transcripts (REMOTE + LOCAL) in the terminal.

1. Integrate Silero VAD via ONNX Runtime (not torch — keeps sidecar small)
2. Integrate pywhispercpp with large-v3-turbo (Metal)
3. Two independent pipelines: REMOTE audio → VAD → Whisper, LOCAL audio → VAD → Whisper
4. Test with provided disclosure meeting audio file (playback mode)

**Verify:** See labeled transcript: `[REMOTE] "We developed a new approach..."` / `[LOCAL] "Can you explain..."`

### Phase 3: Tauri App Shell + Basic UI
**Goal:** Native macOS app showing live transcript.

1. Initialize Tauri v2 + React + TypeScript project
2. Tauri commands to manage Python sidecar lifecycle
3. WebSocket from React to Python sidecar
4. TranscriptPanel with auto-scroll, speaker labels
5. MeetingControls: start/stop, audio source picker

**Verify:** Launch .app, start meeting, see dual-speaker transcript in native window.

### Phase 4: Suggestion Engine + LLM Integration
**Goal:** Live patent-specific suggestions during a meeting.

1. `LLMClient` protocol + `LlamaCppClient` implementation
2. Patent-domain system prompt
3. Context builder: system prompt + documents + transcript window + current suggestions
4. Suggestion loop: 8s debounce, keyword triggers, rate limit
5. SuggestionPanel: max 5 ranked cards, auto-updating

**Verify:** Play back disclosure meeting audio, see relevant enablement/claim questions appearing within ~15s.

### Phase 5: Document Upload + Pre-Call Setup
**Goal:** Upload disclosure materials for LLM context.

1. Tauri native file dialog for upload
2. Document parser (PDF, DOCX, PPTX)
3. PreCallSetup UI with drag-and-drop
4. Wire document context into context builder

**Verify:** Upload disclosure form, start meeting playback, confirm suggestions reference document content.

### Phase 6: First-Run Wizard + Model Management
**Goal:** Zero-setup experience for new users.

1. First-run wizard: permissions, RAM detection, model download
2. Model download with progress UI
3. Auto-download Whisper model
4. Settings panel: LLM provider, model, audio config, max suggestions

**Verify:** Delete app data, relaunch, complete wizard, confirm models download and app works.

### Phase 7: Post-Meeting Summary + Polish
**Goal:** Summary generation, export, error handling.

1. Post-meeting summary prompt + LLM call (from in-memory transcript)
2. Summary display + Markdown/DOCX export via native save dialog
3. Transcript discarded from memory after summary
4. Ollama + Claude API client implementations
5. Error handling: audio failures, LLM timeouts, WebSocket reconnect
6. Recording consent disclaimer in settings
7. Battery warning when below 20% during a meeting

**Verify:** End a meeting, get structured report, confirm transcript is gone from memory.

### Phase 8: Packaging + Distribution
**Goal:** Distributable .dmg.

1. PyInstaller build for Python sidecar (target ~80-100MB with ONNX instead of torch)
2. Pre-compile Swift audio helper for arm64
3. Tauri bundler config for .dmg
4. App icons and branding
5. GitHub Actions CI for automated builds

**Verify:** Build .dmg, install on a clean Mac, go through wizard, run meeting end-to-end.

---

## Testing Strategy

- **Playback mode:** Feed a WAV/audio file through the pipeline instead of live audio. The user will provide real disclosure meeting audio for this purpose.
- **Unit tests:** Context builder, suggestion loop debouncing, document parser
- **Integration tests:** Full pipeline from audio file → transcript → suggestions
- **Manual testing:** Real meetings with the playback-verified pipeline

---

## Potential Challenges and Mitigations

| Challenge | Mitigation |
|-----------|-----------|
| ScreenCaptureKit permission denied | Detect empty buffer in 5s, show guidance + open System Settings |
| Whisper latency too high | Fall back to distil-large-v3 or medium.en |
| LLM suggestions too generic | Iterate on system prompt with real meeting audio, add few-shot examples |
| GPU contention (Whisper + LLM) | Whisper gets priority; LLM runs during pauses; add mutex if needed |
| PyInstaller binary too large | Use ONNX Runtime instead of torch for VAD (~30MB vs ~200MB+) |
| Gatekeeper blocks unsigned .app | Right-click → Open; consider Apple Developer ID signing later |
| Model download fails mid-way | HTTP range request resume + checksum verification |
| Suggestions latency >15s | Reduce debounce timer, use smaller model, aggressive keyword triggers |
| MacBook Air thermal throttle | "Low power mode" setting: smaller Whisper model + less frequent LLM calls |
