import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.main import _looks_like_local_model_dir


class MainMedasrSourceTests(unittest.TestCase):
    def test_rejects_missing_directory(self) -> None:
        self.assertFalse(_looks_like_local_model_dir(Path("/tmp/does-not-exist-opd-medasr")))

    def test_accepts_basic_local_dir_without_auto_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.json").write_text(json.dumps({"architectures": ["AnyModel"]}))
            (root / "model.safetensors").write_text("stub")
            with patch("transformers.AutoProcessor.from_pretrained", return_value=object()):
                self.assertTrue(_looks_like_local_model_dir(root))

    def test_rejects_auto_map_without_python_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.json").write_text(json.dumps({"auto_map": {"AutoProcessor": "processing_x.Proc"}}))
            (root / "model.safetensors").write_text("stub")
            self.assertFalse(_looks_like_local_model_dir(root))

    def test_accepts_auto_map_with_python_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.json").write_text(json.dumps({"auto_map": {"AutoProcessor": "processing_x.Proc"}}))
            (root / "model.safetensors").write_text("stub")
            (root / "processing_x.py").write_text("class Proc: pass\n")
            with patch("transformers.AutoProcessor.from_pretrained", return_value=object()):
                self.assertTrue(_looks_like_local_model_dir(root))


if __name__ == "__main__":
    unittest.main()
