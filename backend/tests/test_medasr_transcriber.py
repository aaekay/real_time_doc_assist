import unittest

import numpy as np
import torch

from backend.asr import medasr_transcriber


class _DummyModelOutput:
    def __init__(self, logits: torch.Tensor) -> None:
        self.logits = logits


class _DummyModel:
    def __init__(self) -> None:
        self.last_kwargs: dict[str, torch.Tensor] | None = None

    def __call__(self, **kwargs):
        self.last_kwargs = kwargs
        logits = torch.tensor([[[0.1, 0.9]]], dtype=torch.float32)
        return _DummyModelOutput(logits)


class _DummyProcessor:
    def __init__(
        self,
        payload: dict[str, torch.Tensor],
    ) -> None:
        self.payload = payload

    def __call__(self, waveform, sampling_rate, return_tensors, padding):
        return self.payload


class _DummyCtcDecoder:
    """Stub for pyctcdecode beam search decoder."""

    def __init__(self, decoded_text: str = "decoded text") -> None:
        self.decoded_text = decoded_text
        self.last_logits: np.ndarray | None = None

    def decode(self, logits: np.ndarray) -> str:
        self.last_logits = logits
        return self.decoded_text


class MedAsrTranscriberTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_processor = medasr_transcriber._processor
        self.original_model = medasr_transcriber._model
        self.original_device = medasr_transcriber._device
        self.original_ctc_decoder = medasr_transcriber._ctc_decoder
        self.original_prev_transcript = medasr_transcriber._prev_transcript
        medasr_transcriber._device = "cpu"
        medasr_transcriber._prev_transcript = ""

    def tearDown(self) -> None:
        medasr_transcriber._processor = self.original_processor
        medasr_transcriber._model = self.original_model
        medasr_transcriber._device = self.original_device
        medasr_transcriber._ctc_decoder = self.original_ctc_decoder
        medasr_transcriber._prev_transcript = self.original_prev_transcript

    def _setup_mocks(
        self,
        payload: dict[str, torch.Tensor],
        decoded_text: str = "decoded text",
    ) -> tuple[_DummyProcessor, _DummyModel, _DummyCtcDecoder]:
        processor = _DummyProcessor(payload)
        model = _DummyModel()
        decoder = _DummyCtcDecoder(decoded_text)
        medasr_transcriber._processor = processor
        medasr_transcriber._model = model
        medasr_transcriber._ctc_decoder = decoder
        return processor, model, decoder

    def test_transcribe_supports_input_features(self) -> None:
        _, model, _ = self._setup_mocks(
            {
                "input_features": torch.ones((1, 4), dtype=torch.float32),
                "attention_mask": torch.ones((1, 4), dtype=torch.bool),
            }
        )

        out = medasr_transcriber.transcribe(np.zeros(4, dtype=np.float32), 16000)

        self.assertEqual(out, "decoded text")
        self.assertIn("input_features", model.last_kwargs)
        self.assertIn("attention_mask", model.last_kwargs)
        self.assertNotIn("input_values", model.last_kwargs)

    def test_transcribe_supports_input_values(self) -> None:
        _, model, _ = self._setup_mocks(
            {
                "input_values": torch.ones((1, 4), dtype=torch.float32),
                "attention_mask": torch.ones((1, 4), dtype=torch.bool),
            }
        )

        out = medasr_transcriber.transcribe(np.zeros(4, dtype=np.float32), 16000)

        self.assertEqual(out, "decoded text")
        self.assertIn("input_values", model.last_kwargs)
        self.assertIn("attention_mask", model.last_kwargs)
        self.assertNotIn("input_features", model.last_kwargs)

    def test_transcribe_raises_when_audio_tensor_key_missing(self) -> None:
        self._setup_mocks({"attention_mask": torch.ones((1, 4), dtype=torch.bool)})

        with self.assertRaisesRegex(RuntimeError, "missing audio input tensor"):
            medasr_transcriber.transcribe(np.zeros(4, dtype=np.float32), 16000)

    def test_transcribe_cleans_residual_control_tokens(self) -> None:
        self._setup_mocks(
            {"input_features": torch.ones((1, 4), dtype=torch.float32)},
            decoded_text="<epsilon> hello </s> <extra_id_5> world",
        )

        out = medasr_transcriber.transcribe(np.zeros(4, dtype=np.float32), 16000)
        self.assertEqual(out, "hello world")

    def test_transcribe_uses_beam_search_decoder(self) -> None:
        """Verify that transcribe passes logits to the CTC beam search decoder."""
        _, _, decoder = self._setup_mocks(
            {"input_features": torch.ones((1, 4), dtype=torch.float32)},
        )

        medasr_transcriber.transcribe(np.zeros(4, dtype=np.float32), 16000)

        self.assertIsNotNone(decoder.last_logits)
        # Logits should be a 2D numpy array (time, vocab_size)
        self.assertEqual(decoder.last_logits.ndim, 2)

    def test_transcribe_raises_when_not_loaded(self) -> None:
        medasr_transcriber._processor = None
        medasr_transcriber._model = None
        medasr_transcriber._ctc_decoder = None

        with self.assertRaisesRegex(RuntimeError, "MedASR not loaded"):
            medasr_transcriber.transcribe(np.zeros(4, dtype=np.float32), 16000)


if __name__ == "__main__":
    unittest.main()
