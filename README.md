# OPD Question Copilot

Real-time clinical interview assistant that listens to OPD doctor-patient conversations and suggests next-best questions using **two HAI-DEF models**: MedASR for medical speech-to-text and MedGemma for clinical reasoning.

Built for the [Google HAI-DEF MedGemma Impact Challenge](https://www.kaggle.com/competitions/hai-def-medgemma-impact-challenge) — Novel Task Prize track.

## Architecture

```
Browser Mic → [WebSocket binary audio] → FastAPI Backend
                                            ├── MedASR (transcription)
                                            ├── MedGemma Role 1: Structured extraction → EncounterState
                                            ├── MedGemma Role 2: Question generation (parallel)
                                            ├── MedGemma Role 3: Consult decision support (parallel)
                                            ├── MedGemma Role 4: Safety filter
                                            └── MedGemma Role 5: SOAP note (on session end)
                                         ↓
                              [WebSocket JSON messages]
                                         ↓
                              React UI (4-panel layout)
```

### Two HAI-DEF Models

| Model | Purpose | Size | Why |
|-------|---------|------|-----|
| **MedASR** (`google/medasr`) | Medical speech-to-text | 105M params | 5x better medical WER vs Whisper (4.6% vs 25.3% on medical dictation) |
| **MedGemma** (`google/medgemma-4b-it`) | Clinical reasoning (5 roles) | 4B params | Structured extraction, question generation, consult assessment, safety filter, SOAP notes |

### Five MedGemma Roles

1. **Structured Extraction** — Transcript → JSON encounter state (symptoms, history, red flags)
2. **Question Generation** — Encounter state → 3-5 priority-ranked next-best questions with rationale
3. **Consult Assessment** — Encounter state → Specialist referral recommendation with urgency
4. **Safety Filter** — Review suggested questions for clinical appropriateness
5. **SOAP Summary** — Full encounter → Structured SOAP note

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- External OpenAI-compatible LLM service running at `http://127.0.0.1:11424` (or set `OPD_MEDGEMMA_BASE_URL`)
- HuggingFace account with access to `google/medasr` (for local ASR model)

### Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/opd-question-copilot.git
cd opd-question-copilot

# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Environment
cp .env.example .env

# Optional but recommended: pre-download MedASR into ./models
./scripts/download_models.sh medasr
```

### Model auth

- Add `HF_TOKEN` to `.env` so Transformers can download gated `google/medasr`.
- Token aliases supported by scripts:
  `HF_TOKEN`, `HUGGING_FACE_HUB_TOKEN`, `HUGGINGFACEHUB_API_TOKEN`, `OPD_HF_TOKEN`.
- `scripts/run_demo.sh` also loads `.env` before starting backend/frontend.
- Download locations are local to this repo:
  - MedASR: `models/medasr`
  - HF cache: `models/hf_cache`
- Base project dependencies use `transformers>=5.2.0` (required by MedASR LASR classes).
- MedGemma reasoning is called through an external OpenAI-compatible API.
- API request/response contract is documented in `api_usage.md`.
- Demographics extraction can be toggled with `OPD_ENABLE_DEMOGRAPHICS_EXTRACTION` (the only extraction toggle).
- Per-role MedGemma cadence can be configured independently:
  `OPD_DEMOGRAPHICS_PIPELINE_DEBOUNCE_SECONDS`,
  `OPD_CHIEF_COMPLAINT_PIPELINE_DEBOUNCE_SECONDS`,
  `OPD_KEYWORDS_PIPELINE_DEBOUNCE_SECONDS`.
  If unset, each falls back to `OPD_PIPELINE_DEBOUNCE_SECONDS`.
- Concurrent MedGemma requests are controlled by `OPD_MEDGEMMA_MAX_CONCURRENT_CALLS`.

### Run

1. Ensure external LLM API service is running (see `api_usage.md`).
2. Start the application:
```bash
./scripts/run_demo.sh
```

Or start individually:
```bash
# Backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload

# Frontend
cd frontend && npm run dev
```

Open http://localhost:5173 and click "Start Recording".

If frontend and backend run on different hosts, set `VITE_WS_URL` for the frontend:
```bash
cd frontend
VITE_WS_URL=ws://localhost:8080/ws npm run dev
```

Both scripts prefer `.venv/bin/python` automatically (fallback to `python` if not present).

### Evaluation

```bash
python evaluation/run_evaluation.py    # Run vignettes through pipeline
python evaluation/score_metrics.py     # Compute metrics
```

## Evaluation Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| **RedFlagCoverage** | ≥ 0.80 | Fraction of gold-standard red-flag questions matched |
| **HistoryCompleteness** | ≥ 0.75 | Fraction of expected history domains covered |
| **QuestionRelevance** | ≥ 0.60 | Fraction of suggestions matching gold-standard questions |
| **ConsultAccuracy** | — | Correct specialty + urgency recommendation |
| **Latency** | p95 < 2.0s | Pipeline inference time |

Evaluated on 10 synthetic clinical vignettes covering: cardiology, pediatrics, neurology, endocrine, respiratory, gastroenterology, orthopedics, psychiatry, dermatology, ENT.

## Project Structure

```
├── backend/
│   ├── main.py                    # FastAPI app
│   ├── config.py                  # Pydantic settings
│   ├── models.py                  # All schemas
│   ├── websocket_handler.py       # Core orchestration
│   ├── asr/
│   │   ├── medasr_transcriber.py  # MedASR CTC transcription
│   │   └── audio_buffer.py        # Rolling PCM16 buffer
│   ├── encounter/
│   │   └── state.py               # Accumulative encounter state
│   └── medgemma/
│       ├── client.py              # Async OpenAI-compatible client
│       ├── json_utils.py          # Shared JSON cleanup helpers
│       ├── prompts.py             # Five prompt templates
│       ├── structured_extraction.py
│       ├── question_generator.py
│       ├── consult_advisor.py
│       ├── safety_filter.py
│       └── summary_generator.py
├── frontend/
│   └── src/
│       ├── App.tsx                # 2x2 grid layout
│       ├── types.ts               # TypeScript types
│       ├── hooks/
│       │   ├── useAudioCapture.ts # Mic → PCM16
│       │   └── useWebSocket.ts    # WS connection
│       └── components/
│           ├── TranscriptPanel.tsx
│           ├── SuggestionPanel.tsx
│           ├── ConsultPanel.tsx
│           ├── SummaryPanel.tsx
│           └── StatusBar.tsx
├── evaluation/
│   ├── vignettes/                 # 10 clinical vignettes
│   ├── run_evaluation.py
│   └── score_metrics.py
├── scripts/
│   ├── run_demo.sh
│   └── download_models.sh
├── api_usage.md
├── requirements.txt
└── .env.example
```

## Safety Boundaries

- All suggested questions pass through a MedGemma safety filter
- Questions are reviewed for clinical appropriateness, cultural sensitivity, and scope
- The system is an **assistant** — it suggests questions, it does not make diagnoses
- No patient data is stored; all processing is session-scoped and in-memory
- Red-flag screening questions are prioritized to minimize missed critical findings

## License

MIT
