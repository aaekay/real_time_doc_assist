import unittest

from backend.asr.medasr_transcriber import _patch_lasr_feature_extractor_compat


class _DummyFeatureExtractorNoCenter:
    def _torch_extract_fbank_features(self, waveform, device="cpu"):
        return ("ok", waveform, device)


class _DummyFeatureExtractorWithCenter:
    def _torch_extract_fbank_features(self, waveform, device="cpu", center=True):
        return ("ok", waveform, device, center)


class MedAsrCompatTests(unittest.TestCase):
    def test_patches_when_center_missing(self) -> None:
        fe = _DummyFeatureExtractorNoCenter()
        patched = _patch_lasr_feature_extractor_compat(fe)
        self.assertTrue(patched)
        out = fe._torch_extract_fbank_features("wave", "cpu", True)
        self.assertEqual(out, ("ok", "wave", "cpu"))

    def test_skips_when_center_already_present(self) -> None:
        fe = _DummyFeatureExtractorWithCenter()
        patched = _patch_lasr_feature_extractor_compat(fe)
        self.assertFalse(patched)
        out = fe._torch_extract_fbank_features("wave", "cpu", False)
        self.assertEqual(out, ("ok", "wave", "cpu", False))


if __name__ == "__main__":
    unittest.main()
