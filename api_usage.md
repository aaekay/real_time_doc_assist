# API Usage Guide

This server exposes an OpenAI-compatible API on:

- `http://127.0.0.1:11424`

## 1) Start The Server

```bash
llm-serve
```

## 2) Endpoints

- `GET /healthz`
- `GET /v1/models`
- `POST /v1/chat/completions`

## 3) Chat Completions

### Request Body

- `messages` (required): array of `{ "role": "...", "content": "..." }`
- `role` must be one of: `system`, `user`, `assistant`
- `model` (optional): model ID string
- `stream` (optional, default `false`): set `true` for SSE streaming
- `temperature` (optional): `0.0` to `2.0`
- `top_p` (optional): `>0.0` and `<=1.0`
- `max_tokens` (optional): `1` to `8192`
- `max_completion_tokens` (optional): `1` to `8192` (takes precedence over `max_tokens`)

### Non-Streaming Example (`curl`)

```bash
curl -s http://127.0.0.1:11424/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "messages": [{"role": "user", "content": "Explain cataract surgery in one sentence."}],
    "stream": false
  }'
```

### Streaming Example (`curl`)

```bash
curl -N http://127.0.0.1:11424/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "messages": [{"role": "user", "content": "Count from one to five."}],
    "stream": true
  }'
```

Streaming returns `text/event-stream` lines in `data: ...` format and ends with:

```text
data: [DONE]
```

## 4) Python (OpenAI SDK) Example

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:11424/v1",
    api_key="not-required",  # server does not enforce auth by default
)

resp = client.chat.completions.create(
    model="Qwen/Qwen2.5-7B-Instruct",
    messages=[{"role": "user", "content": "Say hello"}],
    stream=False,
)

print(resp.choices[0].message.content)
```

Streaming with SDK:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:11424/v1", api_key="not-required")

stream = client.chat.completions.create(
    model="Qwen/Qwen2.5-7B-Instruct",
    messages=[{"role": "user", "content": "Write three short bullet points about eye surgery."}],
    stream=True,
)

for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="", flush=True)
print()
```

## 5) Model Loading Behavior (`202`)

With the `transformers` backend and dynamic model switching, a requested model may return `202` while loading:

```json
{
  "object": "model.load",
  "status": "spinning_up",
  "model": "meta-llama/Llama-3.1-8B-Instruct",
  "current_model": "Qwen/Qwen2.5-7B-Instruct",
  "retry_after_seconds": 2,
  "eta_seconds": null
}
```

In this case:

1. Wait for `retry_after_seconds` (or `Retry-After` header).
2. Retry the same `POST /v1/chat/completions` request.

## 6) List Models

```bash
curl -s http://127.0.0.1:11424/v1/models
```

Notes:

- `transformers`: returns allowlisted models (with runtime metadata such as `status`/`loaded`).
- `vllm` / `tensorrt_llm`: returns the single served model.

## 7) Health Check

```bash
curl -s http://127.0.0.1:11424/healthz
```

Useful fields:

- `status` (`ok`, `starting`, `degraded`, or switching-related state)
- `loaded`
- `model_id`
- `inference_backend`
- `queue_depth`
- `switch_in_progress` / `switch_target_model`

## 8) Common Error Codes

- `400`: invalid request, unknown model, prompt too long, or model mismatch
- `409`: runtime not accepting requests or model switch conflict
- `429`: queue full
- `503`: service/runtime not ready
- `504`: inference timeout
- `500`/`502`: internal/upstream runtime failures
