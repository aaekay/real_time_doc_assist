# Start Recording Flow (Under The Hood)

This document traces what happens in the codebase when a user clicks **Start Recording** in the UI.

## Scope

- Start point: `frontend/src/components/StatusBar.tsx:67`
- End point: realtime UI updates from backend messages (`transcript`, `suggestions`, `consult`, `encounter_state`, `status`)

## Preconditions Before Click

1. The WebSocket must be connected, otherwise the button is disabled.
- Code: `frontend/src/components/StatusBar.tsx:68`
- Connection state comes from `useWebSocket`.
- Code: `frontend/src/hooks/useWebSocket.ts:30`

2. Backend must expose `/ws` and accept connections.
- Code: `backend/main.py:154`

3. MedASR should be loaded at backend startup for transcription to work.
- Startup loading path: `backend/main.py:67`
- Runtime error path if not loaded: `backend/websocket_handler.py:184`

## Step-By-Step Runtime Flow

1. User clicks **Start Recording**.
- UI button calls `onStartRecording`.
- Code: `frontend/src/components/StatusBar.tsx:67`

2. `App` wires `onStartRecording` to `start` from `useAudioCapture`.
- Code: `frontend/src/App.tsx:55`
- Hook binding: `frontend/src/App.tsx:25`

3. `useAudioCapture.start()` requests microphone permission and audio stream.
- `getUserMedia` constraints: mono, 16kHz target, echo cancellation, noise suppression.
- Code: `frontend/src/hooks/useAudioCapture.ts:29`

4. Frontend audio graph is initialized.
- `AudioContext({ sampleRate: 16000 })`
- `MediaStreamAudioSourceNode` from mic stream
- `ScriptProcessorNode(4096, 1, 1)` (about 256 ms per callback at 16kHz)
- Code: `frontend/src/hooks/useAudioCapture.ts:39`

5. On each `onaudioprocess` callback:
- Browser gives Float32 PCM samples.
- Samples are converted to PCM16 (`Int16Array`) and sent upstream as raw bytes.
- Code: `frontend/src/hooks/useAudioCapture.ts:49`

6. Audio bytes are sent over WebSocket as **binary frames**.
- `onAudioChunk` calls `sendAudio`.
- `sendAudio` does `ws.send(data)` when socket is open.
- Code: `frontend/src/hooks/useWebSocket.ts:126`

7. Backend `/ws` receives each binary frame.
- Main loop: `handle_websocket`.
- Code: `backend/websocket_handler.py:150`

8. Backend appends raw PCM16 to rolling `AudioBuffer`.
- `audio_buffer.add_pcm16(...)`
- Code: `backend/websocket_handler.py:176`
- Buffer logic: `backend/asr/audio_buffer.py:30`

9. Chunk release rule:
- No transcription until buffer reaches `audio_chunk_min_seconds` (default `2.0s`).
- Uses overlap between chunks (`audio_overlap_seconds`, default `0.5s`) to preserve continuity.
- Config: `backend/config.py:35`
- Chunking behavior: `backend/asr/audio_buffer.py:35`

10. Transcription with MedASR starts once a chunk is ready.
- Code: `backend/websocket_handler.py:182`
- Transcriber function: `backend/asr/medasr_transcriber.py:160`

11. MedASR text post-processing:
- Cleans control tokens and whitespace.
- Removes duplicated words caused by audio overlap with previous chunk.
- Code: `backend/asr/medasr_transcriber.py:75`
- Overlap dedup: `backend/asr/medasr_transcriber.py:82`

12. If text is non-empty, backend appends to session transcript and sends `transcript` message.
- Append: `encounter.append_transcript(text)`
- Emit payload includes both incremental text and full transcript.
- Code: `backend/websocket_handler.py:217`

13. Periodic MedGemma pipeline launch:
- Runs on a fixed interval gate (`pipeline_debounce_seconds`, default `5.0s`).
- Also ensures only one pipeline task runs at a time.
- Runs only when transcript has changed since the previous pipeline run.
- Config: `backend/config.py:39`
- Gate: `backend/websocket_handler.py:227`

14. MedGemma pipeline stages (`_run_medgemma_pipeline`):
- Stage 1: structured extraction of encounter state.
  - Code: `backend/websocket_handler.py:77`
  - Extractor: `backend/medgemma/structured_extraction.py:14`
- Stage 2 and 3 in parallel:
  - Question generation: `backend/medgemma/question_generator.py:14`
  - Consult assessment: `backend/medgemma/consult_advisor.py:14`
  - Parallel call: `backend/websocket_handler.py:92`
- Stage 4 safety filter on questions:
  - Code: `backend/medgemma/safety_filter.py:45`
  - Invoked at: `backend/websocket_handler.py:102`
- Dedup against already-marked-as-asked questions:
  - Code: `backend/websocket_handler.py:112`
  - Encounter dedup logic: `backend/encounter/state.py:147`

15. Backend emits pipeline outputs to frontend:
- `encounter_state` (merged state)
  - Code: `backend/websocket_handler.py:88`
- `suggestions` (filtered and deduped questions)
  - Code: `backend/websocket_handler.py:119`
- `consult` only if confidence >= threshold (default `0.7`)
  - Threshold: `backend/config.py:50`
  - Gate: `backend/websocket_handler.py:135`
- `status` with pipeline latency in ms
  - Code: `backend/websocket_handler.py:139`

16. Frontend receives JSON messages and updates UI state.
- Message dispatcher: `frontend/src/hooks/useWebSocket.ts:71`
- `transcript` -> Transcript panel
- `suggestions` -> Suggestion panel
- `consult` -> Consult panel
- `encounter_state` -> Encounter overview panel
- `status.pipeline_latency_ms` -> status bar pipeline latency

## WebSocket Message Types Used During Recording

Defined in backend model enum:
- `transcript`
- `suggestions`
- `consult`
- `encounter_state`
- `status`
- `error`
- Source: `backend/models.py:8`

Frontend mirror types:
- Source: `frontend/src/types.ts:3`

## Related Controls (Important For Session Behavior)

1. **Stop Recording** (client-side audio stop only)
- Stops audio nodes and mic tracks.
- Does not send a control message to backend.
- Code: `frontend/src/hooks/useAudioCapture.ts:69`

2. **End Session**
- App first stops recording, then sends `{ "action": "end_session" }`.
- Code: `frontend/src/App.tsx:28`
- Backend cancels active pipeline and generates SOAP note.
- Code: `backend/websocket_handler.py:254`
- SOAP generator: `backend/medgemma/summary_generator.py:14`

3. **Reset**
- App stops recording and sends `{ "action": "reset" }`.
- Code: `frontend/src/App.tsx:34`
- Frontend immediately clears local state optimistically.
- Code: `frontend/src/hooks/useWebSocket.ts:133`
- Backend resets encounter + audio buffer and sends `session_reset` payload.
- Code: `backend/websocket_handler.py:273`

4. **Mark as asked** in suggestion card
- Sends `{ "action": "question_asked", "question": "..." }`.
- UI sender: `frontend/src/App.tsx:40`
- Backend stores asked question so future suggestions can be filtered.
- Code: `backend/websocket_handler.py:267`

## Operational Notes / Gotchas

1. First transcript is not immediate.
- By default backend waits for ~2s buffered audio before first ASR call.
- Config: `backend/config.py:35`

2. Suggestion updates are cadence-based.
- MedGemma pipeline is interval-gated to about once every ~5s (default).
- Config: `backend/config.py:39`

3. Stale pipeline protection exists.
- `session_epoch` invalidates outputs from old tasks after `reset`/`end_session`.
- Code: `backend/websocket_handler.py:32`
- Staleness checks in pipeline: `backend/websocket_handler.py:72`

4. If MedASR failed at startup, backend sends a one-time actionable error to client and skips ASR work until fixed.
- Code: `backend/websocket_handler.py:184`
- Startup health endpoint includes load status/error.
- Code: `backend/main.py:159`

5. `Stop Recording` does not flush partial (<2s) tail audio on backend.
- Current behavior: tail remains in backend `AudioBuffer` until more audio arrives or reset occurs.
- Buffer code: `backend/asr/audio_buffer.py:48`
- `flush()` exists but is not called in `handle_websocket`.

## Quick Sequence (Condensed)

1. `StatusBar` button click -> `useAudioCapture.start()`
2. Mic stream -> Float32 frames -> PCM16 conversion
3. PCM16 binary frames -> WebSocket `/ws`
4. Backend `AudioBuffer` accumulates -> 2s chunk ready
5. MedASR transcribes -> transcript appended
6. Backend emits `transcript`
7. Periodic MedGemma pipeline runs (extract + questions/consult + safety)
8. Backend emits `encounter_state`, `suggestions`, optional `consult`, and `status.pipeline_latency_ms`
9. Frontend panels re-render from received messages
