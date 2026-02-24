import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from threading import Lock
from typing import Any
from uuid import uuid4

from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)

from backend.config import settings

_client: AsyncOpenAI | None = None
_semaphore: asyncio.Semaphore | None = None
logger = logging.getLogger(__name__)
_log_write_lock = Lock()


def get_semaphore() -> asyncio.Semaphore:
    """Lazy-init semaphore for concurrent MedGemma call control."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.medgemma_max_concurrent_calls)
    return _semaphore


def _medgemma_log_path() -> Path:
    log_path = Path(settings.medgemma_log_path)
    if log_path.is_absolute():
        return log_path
    project_root = Path(__file__).resolve().parents[2]
    return project_root / log_path


def _append_medgemma_log(record: dict) -> None:
    if not settings.medgemma_log_enabled:
        return

    path = _medgemma_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with _log_write_lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        logger.exception("Failed to write MedGemma request log.")


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.medgemma_base_url,
            api_key=settings.medgemma_api_key,
            timeout=settings.medgemma_request_timeout_seconds,
            max_retries=0,
        )
    return _client


def _read_json_body(raw_response: Any) -> dict[str, Any] | None:
    try:
        body = raw_response.http_response.json()
    except Exception:
        return None
    return body if isinstance(body, dict) else None


def _is_model_loading_event(body: dict[str, Any] | None) -> bool:
    if body is None:
        return False
    if body.get("object") == "model.load":
        return True
    status = body.get("status")
    return isinstance(status, str) and status.lower() in {"loading", "spinning_up"}


def _resolve_retry_after_seconds(body: dict[str, Any] | None, headers: Any) -> float:
    if body is not None:
        retry_after = body.get("retry_after_seconds")
        if isinstance(retry_after, (int, float)) and retry_after > 0:
            return float(retry_after)
        if isinstance(retry_after, str):
            try:
                parsed = float(retry_after)
                if parsed > 0:
                    return parsed
            except ValueError:
                pass

    if headers is not None:
        retry_after_header = headers.get("retry-after")
        if retry_after_header:
            try:
                parsed_header = float(retry_after_header)
                if parsed_header > 0:
                    return parsed_header
            except ValueError:
                pass

    return max(0.1, settings.medgemma_retry_backoff_seconds)


async def chat_completion(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
    call_type: str = "unspecified",
) -> str:
    """Send a chat completion request to MedGemma via OpenAI-compatible server."""
    client = get_client()
    retries = max(0, settings.medgemma_max_retries)
    last_error: Exception | None = None
    resolved_max_tokens = max_tokens or settings.medgemma_max_tokens
    resolved_temperature = (
        temperature if temperature is not None else settings.medgemma_temperature
    )
    call_id = str(uuid4())
    call_started_at = datetime.now(timezone.utc).isoformat()

    async with get_semaphore():
        for attempt in range(retries + 1):
            request_started = time.perf_counter()
            try:
                raw_response = await client.chat.completions.with_raw_response.create(
                    model=settings.medgemma_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=resolved_max_tokens,
                    temperature=resolved_temperature,
                )
                if raw_response.status_code == 202:
                    response_body = _read_json_body(raw_response)
                    retry_after_seconds = _resolve_retry_after_seconds(
                        response_body,
                        raw_response.headers,
                    )
                    elapsed_ms = int((time.perf_counter() - request_started) * 1000)

                    if _is_model_loading_event(response_body):
                        _append_medgemma_log(
                            {
                                "ts_utc": datetime.now(timezone.utc).isoformat(),
                                "call_started_at_utc": call_started_at,
                                "call_id": call_id,
                                "call_type": call_type,
                                "attempt": attempt + 1,
                                "max_attempts": retries + 1,
                                "base_url": settings.medgemma_base_url,
                                "model": settings.medgemma_model,
                                "max_tokens": resolved_max_tokens,
                                "temperature": resolved_temperature,
                                "system_prompt": system_prompt,
                                "user_prompt": user_prompt,
                                "output": response_body,
                                "latency_ms": elapsed_ms,
                                "success": False,
                                "error_type": "ModelLoading",
                                "error_message": "Model loading in progress.",
                            }
                        )

                        if attempt >= retries:
                            last_error = RuntimeError(
                                "MedGemma service reported model loading state for all retries. "
                                "Ensure the requested model is available and try again."
                            )
                            break

                        logger.warning(
                            "MedGemma model is loading; retry %s/%s in %.2fs",
                            attempt + 1,
                            retries + 1,
                            retry_after_seconds,
                        )
                        await asyncio.sleep(retry_after_seconds)
                        continue

                    _append_medgemma_log(
                        {
                            "ts_utc": datetime.now(timezone.utc).isoformat(),
                            "call_started_at_utc": call_started_at,
                            "call_id": call_id,
                            "call_type": call_type,
                            "attempt": attempt + 1,
                            "max_attempts": retries + 1,
                            "base_url": settings.medgemma_base_url,
                            "model": settings.medgemma_model,
                            "max_tokens": resolved_max_tokens,
                            "temperature": resolved_temperature,
                            "system_prompt": system_prompt,
                            "user_prompt": user_prompt,
                            "output": response_body,
                            "latency_ms": elapsed_ms,
                            "success": False,
                            "error_type": "Unexpected202",
                            "error_message": "Received HTTP 202 without model loading metadata.",
                        }
                    )
                    last_error = RuntimeError(
                        "MedGemma returned HTTP 202 but no model-loading payload was present."
                    )
                    if attempt >= retries:
                        break
                    await asyncio.sleep(settings.medgemma_retry_backoff_seconds)
                    continue

                response = raw_response.parse()
                output = response.choices[0].message.content or ""
                elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                _append_medgemma_log(
                    {
                        "ts_utc": datetime.now(timezone.utc).isoformat(),
                        "call_started_at_utc": call_started_at,
                        "call_id": call_id,
                        "call_type": call_type,
                        "attempt": attempt + 1,
                        "max_attempts": retries + 1,
                        "base_url": settings.medgemma_base_url,
                        "model": settings.medgemma_model,
                        "max_tokens": resolved_max_tokens,
                        "temperature": resolved_temperature,
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                        "output": output,
                        "latency_ms": elapsed_ms,
                        "success": True,
                        "error_type": None,
                        "error_message": None,
                    }
                )
                return output
            except APIResponseValidationError as exc:
                elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                body = exc.body if isinstance(exc.body, dict) else None
                if exc.status_code == 202 and _is_model_loading_event(body):
                    retry_after_seconds = _resolve_retry_after_seconds(body, exc.response.headers)
                    _append_medgemma_log(
                        {
                            "ts_utc": datetime.now(timezone.utc).isoformat(),
                            "call_started_at_utc": call_started_at,
                            "call_id": call_id,
                            "call_type": call_type,
                            "attempt": attempt + 1,
                            "max_attempts": retries + 1,
                            "base_url": settings.medgemma_base_url,
                            "model": settings.medgemma_model,
                            "max_tokens": resolved_max_tokens,
                            "temperature": resolved_temperature,
                            "system_prompt": system_prompt,
                            "user_prompt": user_prompt,
                            "output": body,
                            "latency_ms": elapsed_ms,
                            "success": False,
                            "error_type": "ModelLoading",
                            "error_message": "Model loading in progress.",
                        }
                    )
                    if attempt >= retries:
                        last_error = RuntimeError(
                            "MedGemma service reported model loading state for all retries. "
                            "Ensure the requested model is available and try again."
                        )
                        break
                    logger.warning(
                        "MedGemma response validation during loading; retry %s/%s in %.2fs",
                        attempt + 1,
                        retries + 1,
                        retry_after_seconds,
                    )
                    await asyncio.sleep(retry_after_seconds)
                    continue

                _append_medgemma_log(
                    {
                        "ts_utc": datetime.now(timezone.utc).isoformat(),
                        "call_started_at_utc": call_started_at,
                        "call_id": call_id,
                        "call_type": call_type,
                        "attempt": attempt + 1,
                        "max_attempts": retries + 1,
                        "base_url": settings.medgemma_base_url,
                        "model": settings.medgemma_model,
                        "max_tokens": resolved_max_tokens,
                        "temperature": resolved_temperature,
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                        "output": None,
                        "latency_ms": elapsed_ms,
                        "success": False,
                        "error_type": exc.__class__.__name__,
                        "error_message": str(exc),
                    }
                )
                last_error = exc
                if attempt >= retries:
                    break
                backoff = settings.medgemma_retry_backoff_seconds * (2**attempt)
                logger.warning(
                    "MedGemma response parse failed (%s). retry %s/%s in %.2fs",
                    exc.__class__.__name__,
                    attempt + 1,
                    retries + 1,
                    backoff,
                )
                await asyncio.sleep(backoff)
            except NotFoundError as exc:
                elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                _append_medgemma_log(
                    {
                        "ts_utc": datetime.now(timezone.utc).isoformat(),
                        "call_started_at_utc": call_started_at,
                        "call_id": call_id,
                        "call_type": call_type,
                        "attempt": attempt + 1,
                        "max_attempts": retries + 1,
                        "base_url": settings.medgemma_base_url,
                        "model": settings.medgemma_model,
                        "max_tokens": resolved_max_tokens,
                        "temperature": resolved_temperature,
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                        "output": None,
                        "latency_ms": elapsed_ms,
                        "success": False,
                        "error_type": exc.__class__.__name__,
                        "error_message": str(exc),
                    }
                )
                base = settings.medgemma_base_url.rstrip("/")
                endpoint = f"{base}/chat/completions"
                raise RuntimeError(
                    f"MedGemma endpoint not found (404) at {endpoint}. "
                    "This usually means OPD_MEDGEMMA_BASE_URL points to the wrong service/port "
                    "or the external LLM API service is not running."
                ) from exc
            except (
                APIConnectionError,
                APITimeoutError,
                InternalServerError,
                RateLimitError,
            ) as exc:
                elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                _append_medgemma_log(
                    {
                        "ts_utc": datetime.now(timezone.utc).isoformat(),
                        "call_started_at_utc": call_started_at,
                        "call_id": call_id,
                        "call_type": call_type,
                        "attempt": attempt + 1,
                        "max_attempts": retries + 1,
                        "base_url": settings.medgemma_base_url,
                        "model": settings.medgemma_model,
                        "max_tokens": resolved_max_tokens,
                        "temperature": resolved_temperature,
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                        "output": None,
                        "latency_ms": elapsed_ms,
                        "success": False,
                        "error_type": exc.__class__.__name__,
                        "error_message": str(exc),
                    }
                )
                last_error = exc
                if attempt >= retries:
                    break
                backoff = settings.medgemma_retry_backoff_seconds * (2**attempt)
                logger.warning(
                    "MedGemma request failed (%s). retry %s/%s in %.2fs",
                    exc.__class__.__name__,
                    attempt + 1,
                    retries + 1,
                    backoff,
                )
                await asyncio.sleep(backoff)

    assert last_error is not None
    raise last_error
