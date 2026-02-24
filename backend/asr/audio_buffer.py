"""Rolling audio buffer: accumulates PCM16 chunks, releases when threshold met."""

import numpy as np

from backend.config import settings


class AudioBuffer:
    """Accumulates raw PCM16 audio and yields chunks for transcription."""

    def __init__(
        self,
        sample_rate: int | None = None,
        min_seconds: float | None = None,
        overlap_seconds: float | None = None,
    ) -> None:
        self.sample_rate = sample_rate or settings.audio_sample_rate
        self.min_seconds = min_seconds or settings.audio_chunk_min_seconds
        self.overlap_seconds = overlap_seconds or settings.audio_overlap_seconds
        self._buffer = np.array([], dtype=np.float32)

    @property
    def min_samples(self) -> int:
        return int(self.sample_rate * self.min_seconds)

    @property
    def overlap_samples(self) -> int:
        return int(self.sample_rate * self.overlap_seconds)

    def add_pcm16(self, raw_bytes: bytes) -> None:
        """Add raw PCM16 little-endian bytes to the buffer."""
        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        self._buffer = np.concatenate([self._buffer, samples])

    def get_chunk(self) -> np.ndarray | None:
        """Return a chunk if enough audio has accumulated, else None.

        Keeps an overlap for continuity between transcriptions.
        """
        if len(self._buffer) < self.min_samples:
            return None

        chunk = self._buffer.copy()
        # Keep overlap for the next chunk
        self._buffer = self._buffer[-self.overlap_samples :] if self.overlap_samples > 0 else np.array([], dtype=np.float32)
        return chunk

    def flush(self) -> np.ndarray | None:
        """Return whatever is in the buffer, regardless of size."""
        if len(self._buffer) == 0:
            return None
        chunk = self._buffer.copy()
        self._buffer = np.array([], dtype=np.float32)
        return chunk

    def reset(self) -> None:
        """Clear the buffer."""
        self._buffer = np.array([], dtype=np.float32)
