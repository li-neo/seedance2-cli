import unittest


def _m(p: str, kind: str):
    # 仅用于测试 _select_mode：不依赖真实文件存在
    return PIPELINE.Material(local_path=p, kind=kind)


import importlib.util
from pathlib import Path
import sys

PIPELINE_PATH = Path(__file__).resolve().parents[1] / "pipeline.py"
spec = importlib.util.spec_from_file_location("seedance_pipeline_pipeline", str(PIPELINE_PATH))
PIPELINE = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = PIPELINE  # 让 dataclass 能从 sys.modules 找到当前模块
spec.loader.exec_module(PIPELINE)


class TestAutoModeSelect(unittest.TestCase):
    def test_t2v_no_materials(self):
        self.assertEqual(PIPELINE._select_mode([]), "t2v")

    def test_i2v_single_image(self):
        self.assertEqual(PIPELINE._select_mode([_m("a.png", "image")]), "i2v")

    def test_fl2v_two_images(self):
        self.assertEqual(PIPELINE._select_mode([_m("a.png", "image"), _m("b.jpg", "image")]), "fl2v")

    def test_multi_i2v_three_images(self):
        self.assertEqual(
            PIPELINE._select_mode([_m("a.png", "image"), _m("b.jpg", "image"), _m("c.webp", "image")]),
            "multi_i2v",
        )

    def test_multimodal_ref2v_single_video_only(self):
        self.assertEqual(PIPELINE._select_mode([_m("a.mp4", "video")]), "multimodal_ref2v")

    def test_multimodal_ref2v_video_plus_image(self):
        self.assertEqual(PIPELINE._select_mode([_m("a.mp4", "video"), _m("b.png", "image")]), "multimodal_ref2v")

    def test_multimodal_ref2v_two_videos(self):
        self.assertEqual(PIPELINE._select_mode([_m("a.mp4", "video"), _m("b.mov", "video")]), "multimodal_ref2v")

    def test_multimodal_ref2v_audio_only(self):
        self.assertEqual(PIPELINE._select_mode([_m("a.mp3", "audio")]), "multimodal_ref2v")

    def test_multimodal_ref2v_image_plus_audio(self):
        self.assertEqual(PIPELINE._select_mode([_m("a.png", "image"), _m("b.wav", "audio")]), "multimodal_ref2v")

    def test_multimodal_ref2v_video_plus_audio(self):
        self.assertEqual(PIPELINE._select_mode([_m("a.mp4", "video"), _m("b.wav", "audio")]), "multimodal_ref2v")


class TestKindFromPath(unittest.TestCase):
    def test_kind_from_path(self):
        cases = [
            ("a.png", "image"),
            ("a.JPG", "image"),
            ("a.mp4", "video"),
            ("a.MOV", "video"),
            ("a.wav", "audio"),
            ("a.MP3", "audio"),
        ]
        for p, want in cases:
            with self.subTest(p=p):
                self.assertEqual(PIPELINE._kind_from_path(p), want)

    def test_kind_from_path_unsupported(self):
        with self.assertRaises(ValueError):
            PIPELINE._kind_from_path("a.txt")


if __name__ == "__main__":
    unittest.main()

