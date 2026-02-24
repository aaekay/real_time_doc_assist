"""FastAPI application: WebSocket endpoint, CORS, model loading."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.websocket_handler import handle_websocket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _resolve_repo_path(path_value: str) -> Path:
    """Resolve relative config paths against repo root."""
    p = Path(path_value)
    if p.is_absolute():
        return p
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / p


def _looks_like_local_model_dir(model_dir: Path) -> bool:
    """Check whether a local model directory appears usable."""
    if not model_dir.is_dir():
        return False
    has_config = (model_dir / "config.json").is_file()
    has_weights = any(
        (model_dir / name).exists()
        for name in ("model.safetensors", "pytorch_model.bin", "model.safetensors.index.json")
    )
    if not (has_config and has_weights):
        return False

    # If config relies on custom remote code (`auto_map`), local snapshot must include .py code.
    try:
        config_data = json.loads((model_dir / "config.json").read_text())
    except Exception:
        return False

    if config_data.get("auto_map") and not any(model_dir.glob("*.py")):
        return False

    # Final sanity check: processor must be instantiable strictly from local files.
    try:
        from transformers import AutoProcessor

        AutoProcessor.from_pretrained(
            str(model_dir),
            trust_remote_code=True,
            local_files_only=True,
        )
    except Exception:
        return False

    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup."""
    app.state.medasr_ready = False
    app.state.medasr_source = None
    app.state.medasr_error = None

    logger.info("Loading MedASR model...")
    from backend.asr.medasr_transcriber import load_medasr

    if settings.hf_token:
        os.environ["HF_TOKEN"] = settings.hf_token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = settings.hf_token

    cache_root = _resolve_repo_path(settings.model_cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_root / "hf_home"))
    os.environ.setdefault(
        "HUGGINGFACE_HUB_CACHE",
        str(cache_root / "hub"),
    )
    os.environ.setdefault(
        "TRANSFORMERS_CACHE",
        str(cache_root / "transformers"),
    )

    medasr_local_path = _resolve_repo_path(settings.medasr_local_dir)
    medasr_sources: list[str] = []

    if _looks_like_local_model_dir(medasr_local_path):
        medasr_sources.append(str(medasr_local_path))
    else:
        logger.info("Local MedASR directory not usable at %s", medasr_local_path)

    if settings.medasr_model_id not in medasr_sources:
        medasr_sources.append(settings.medasr_model_id)

    last_error: Exception | None = None
    for medasr_source in medasr_sources:
        try:
            load_medasr(
                model_id=medasr_source,
                device=settings.medasr_device,
                hf_token=settings.hf_token,
            )
            app.state.medasr_ready = True
            app.state.medasr_source = medasr_source
            app.state.medasr_error = None
            logger.info("MedASR ready from source: %s", medasr_source)
            break
        except Exception as e:
            last_error = e
            logger.warning("MedASR load failed from %s: %s", medasr_source, e)
            logger.debug("MedASR load traceback for source %s", medasr_source, exc_info=True)

    if not app.state.medasr_ready:
        app.state.medasr_error = str(last_error) if last_error else "Unknown MedASR load error"
        logger.warning(
            "MedASR unavailable after trying %s. Transcription will not work.",
            medasr_sources,
        )

    logger.info(
        "MedGemma configured at: %s (model: %s)",
        settings.medgemma_base_url,
        settings.medgemma_model,
    )
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="OPD Question Copilot",
    description="Real-time clinical interview assistant using MedASR + MedGemma",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await handle_websocket(websocket)


@app.get("/health")
async def health():
    return {
        "status": "ok" if bool(getattr(app.state, "medasr_ready", False)) else "degraded",
        "model": settings.medgemma_model,
        "medasr_ready": bool(getattr(app.state, "medasr_ready", False)),
        "medasr_source": getattr(app.state, "medasr_source", None),
        "medasr_error": getattr(app.state, "medasr_error", None),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
