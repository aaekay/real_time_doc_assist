"""MedASR transcriber: google/medasr CTC model for medical speech-to-text."""

import inspect
import logging
import re
from types import MethodType

import numpy as np
import torch

logger = logging.getLogger(__name__)

_processor = None
_model = None
_device = None
_ctc_decoder = None
_prev_transcript: str = ""


def _medasr_load_error_with_hint(error: Exception) -> RuntimeError:
    """Attach actionable hints to common MedASR load failures."""
    raw = str(error)
    lower = raw.lower()
    hints: list[str] = []

    if "gated repo" in lower or "401" in raw:
        hints.append("HF_TOKEN is missing/invalid or lacks access to google/medasr.")
    if "failed to resolve" in lower or "nameresolutionerror" in lower:
        hints.append("Network/DNS to huggingface.co is unavailable from this environment.")
    if (
        "unrecognized processing class" in lower
        or "lasrtokenizer does not exist" in lower
        or "model type `lasr_ctc`" in lower
    ):
        hints.append(
            "Installed transformers build does not provide LASR classes needed by MedASR "
            "(model was published against transformers 5.x LASR support)."
        )

    hint_suffix = f" Hint: {' '.join(hints)}" if hints else ""
    return RuntimeError(f"Failed to load MedASR ({type(error).__name__}: {raw}).{hint_suffix}")


def _patch_lasr_feature_extractor_compat(feature_extractor: object) -> bool:
    """Patch Lasr feature extractor signature mismatch in some transformers versions.

    In transformers 5.2.0, LasrFeatureExtractor.__call__ passes a `center` positional
    argument to `_torch_extract_fbank_features`, but that method only accepts
    `(waveform, device="cpu")`. This shim adds a compatible method that accepts
    `center` and ignores it.
    """
    method = getattr(feature_extractor, "_torch_extract_fbank_features", None)
    if method is None:
        return False

    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return False

    if "center" in signature.parameters:
        return False

    original_method = method

    def _compat_method(self, waveform, device="cpu", center=True):  # noqa: ARG001
        return original_method(waveform, device=device)

    feature_extractor._torch_extract_fbank_features = MethodType(  # type: ignore[attr-defined]
        _compat_method,
        feature_extractor,
    )
    return True


def _clean_transcription_text(text: str) -> str:
    """Clean residual control tokens and normalize whitespace."""
    cleaned = re.sub(r"</?s>|<epsilon>|<unk>|<extra_id_\d+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _strip_overlap(prev: str, current: str, max_overlap_words: int = 8) -> str:
    """Remove the overlapping prefix of *current* that duplicates the tail of *prev*.

    When audio chunks overlap, MedASR re-transcribes the shared audio segment,
    producing duplicate words at the junction.  This finds the longest suffix of
    *prev* (up to *max_overlap_words*) that matches a prefix of *current* and
    strips it.
    """
    if not prev or not current:
        return current

    prev_words = prev.split()
    cur_words = current.split()

    if not prev_words or not cur_words:
        return current

    # Try matching the last N words of prev against the first N words of current
    tail_len = min(max_overlap_words, len(prev_words), len(cur_words))
    best = 0
    for n in range(1, tail_len + 1):
        if [w.lower() for w in prev_words[-n:]] == [w.lower() for w in cur_words[:n]]:
            best = n

    if best > 0:
        return " ".join(cur_words[best:])
    return current


def load_medasr(
    model_id: str = "google/medasr",
    device: str = "cpu",
    hf_token: str | None = None,
) -> None:
    """Load the MedASR model and processor."""
    global _processor, _model, _device, _ctc_decoder
    import transformers
    from transformers import AutoProcessor, AutoModelForCTC

    has_lasr_tokenizer = hasattr(transformers, "LasrTokenizer")
    has_lasr_feature_extractor = hasattr(transformers, "LasrFeatureExtractor") or hasattr(
        transformers, "LASRFeatureExtractor"
    )
    if not (has_lasr_tokenizer and has_lasr_feature_extractor):
        raise RuntimeError(
            "Installed transformers version does not include LASR classes required by MedASR. "
            f"Found transformers=={transformers.__version__}. "
            "Use a transformers build with LASR support (e.g. >=5.2.0)."
        )

    logger.info("Loading MedASR model: %s on %s", model_id, device)
    auth_kwargs = {"token": hf_token} if hf_token else {}
    try:
        _processor = AutoProcessor.from_pretrained(
            model_id,
            trust_remote_code=True,
            **auth_kwargs,
        )
        _model = AutoModelForCTC.from_pretrained(
            model_id,
            trust_remote_code=True,
            **auth_kwargs,
        )
    except Exception as e:
        raise _medasr_load_error_with_hint(e) from e
    _device = device
    _model.to(_device)
    _model.eval()

    patched = _patch_lasr_feature_extractor_compat(_processor.feature_extractor)
    if patched:
        logger.warning(
            "Applied LasrFeatureExtractor compatibility patch for this transformers version."
        )

    # Build pyctcdecode beam search decoder from the model's vocabulary.
    # The CTC head output dimension may be smaller than the tokenizer vocab
    # (e.g. 512 vs 613), so we size the label list to match the model output.
    from pyctcdecode import build_ctcdecoder

    ctc_head = getattr(_model, "ctc_head", getattr(_model, "lm_head", None))
    if ctc_head is not None and hasattr(ctc_head, "bias") and ctc_head.bias is not None:
        num_classes = ctc_head.bias.shape[0]
    else:
        num_classes = getattr(_model.config, "vocab_size", None)
        if num_classes is None:
            raise RuntimeError("Cannot determine CTC output size from model.")

    vocab = _processor.tokenizer.get_vocab()
    labels = [""] * num_classes
    for token, idx in vocab.items():
        if idx < num_classes:
            labels[idx] = token
    # pyctcdecode expects "" at the CTC blank index (0) — map <epsilon> to "".
    blank_idx = _processor.tokenizer.pad_token_id or 0
    labels[blank_idx] = ""
    _ctc_decoder = build_ctcdecoder(labels=labels)
    logger.info("Built pyctcdecode beam search decoder (%d labels).", num_classes)

    logger.info("MedASR loaded successfully.")


def transcribe(waveform: np.ndarray, sample_rate: int = 16000) -> str:
    """Transcribe a waveform array to text using MedASR.

    Args:
        waveform: 1-D float32 numpy array of audio samples.
        sample_rate: Audio sample rate (MedASR expects 16kHz).

    Returns:
        Transcribed text string.
    """
    if _processor is None or _model is None or _ctc_decoder is None:
        raise RuntimeError("MedASR not loaded. Call load_medasr() first.")

    # Processor expects float32 array
    if waveform.dtype != np.float32:
        waveform = waveform.astype(np.float32)

    inputs = _processor(
        waveform,
        sampling_rate=sample_rate,
        return_tensors="pt",
        padding=True,
    )

    model_inputs = {}
    if "input_values" in inputs:
        model_inputs["input_values"] = inputs["input_values"].to(_device)
    elif "input_features" in inputs:
        model_inputs["input_features"] = inputs["input_features"].to(_device)
    else:
        keys = ", ".join(sorted(inputs.keys()))
        raise RuntimeError(
            "MedASR processor output missing audio input tensor "
            f"(expected 'input_values' or 'input_features', got: {keys or 'none'})"
        )

    if "attention_mask" in inputs:
        model_inputs["attention_mask"] = inputs["attention_mask"].to(_device)

    with torch.no_grad():
        logits = _model(**model_inputs).logits

    logits_np = logits[0].cpu().numpy()  # (time, vocab_size)
    raw_text = _ctc_decoder.decode(logits_np)
    cleaned = _clean_transcription_text(raw_text)

    # Strip words duplicated from the audio overlap with the previous chunk
    global _prev_transcript
    deduped = _strip_overlap(_prev_transcript, cleaned)
    _prev_transcript = cleaned
    return deduped
