"""Test exact clip recovery and precision controls without downloading models."""

import contextlib
import copy
import gc
import hashlib
import io
import json
import math
import ast
import types
import unicodedata
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf
from jiwer import cer, wer

from test_pilot_notebook import CELLS as PILOT_CELLS, FakeConfig, FakeModel, FakeProcessor, wav_row

PATH = Path(__file__).resolve().parents[1] / "notebooks/02_whisper_precision_diagnostic.ipynb"
NOTEBOOK = json.loads(PATH.read_text(encoding="utf-8"))
CELLS = {cell["id"]: "".join(cell["source"]) for cell in NOTEBOOK["cells"]}


def execute(label, namespace):
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(CELLS[label], f"{PATH}:{label}", "exec"), namespace)


class Stream(list):
    def decode(self, enabled):
        assert enabled is False
        return self

    def select_columns(self, columns):
        return self


class DiagnosticTests(unittest.TestCase):
    def test_setup_rejects_stale_hub_modules(self):
        for source in [CELLS['setup'], PILOT_CELLS['imports']]:
            checks = ast.Module(body=[node for node in ast.parse(source).body if isinstance(node, ast.Assert)], type_ignores=[])
            namespace = {
                'version': lambda name: {'huggingface-hub': '0.36.2', 'transformers': '4.57.1'}[name],
                'huggingface_hub': types.SimpleNamespace(__version__='0.36.2'),
                'hub_constants': types.SimpleNamespace(HF_HUB_ENABLE_HF_TRANSFER=False),
            }
            exec(compile(checks, 'environment-check', 'exec'), namespace)
            namespace['hub_constants'] = types.SimpleNamespace()
            with self.assertRaisesRegex(AssertionError, 'Restart'):
                exec(compile(checks, 'environment-check', 'exec'), namespace)
            namespace['huggingface_hub'].__version__ = '1.0.0'
            with self.assertRaisesRegex(AssertionError, 'restart'):
                exec(compile(checks, 'environment-check', 'exec'), namespace)

    def setUp(self):
        self.ns = {
            "np": np, "sf": sf, "math": math, "hashlib": hashlib, "io": io,
            "unicodedata": unicodedata, "wer": wer, "cer": cer, "copy": copy, "json": json,
            "gc": gc, "Audio": lambda audio, rate: None, "display": lambda value: None,
        }
        execute("baseline", self.ns)
        execute("helpers", self.ns)
        self.rows = [wav_row(number) for number in range(1, 6)]
        self.clips = [self.ns["prepare_clip"](row) for row in self.rows]
        self.ns["baseline"] = copy.deepcopy(self.ns["baseline"])
        self.ns["baseline"]["manifest"] = [clip["identity"] for clip in self.clips]
        self.ns["expected_clips"] = {clip["identity"]["clip_id"]: clip["identity"] for clip in self.clips}
        self.ns["load_dataset"] = lambda *args, **kwargs: Stream(reversed(self.rows))

    def test_clean_syntax_and_reused_helpers(self):
        self.assertEqual(len({cell["id"] for cell in NOTEBOOK["cells"]}), len(NOTEBOOK["cells"]))
        for index, cell in enumerate(NOTEBOOK["cells"]):
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])
                self.assertTrue("".join(NOTEBOOK["cells"][index - 1]["source"]).startswith("### "))
                compile("\n".join(line for line in "".join(cell["source"]).splitlines() if not line.startswith("%pip ")), cell["id"], "exec")
        self.assertIn(PILOT_CELLS["audio-helpers"].strip(), CELLS["helpers"])
        self.assertIn(PILOT_CELLS["scoring-selfchecks"].strip(), CELLS["helpers"])

    def test_recovery_preserves_original_order_and_rejects_changed_or_duplicate_audio(self):
        execute("recover-audio", self.ns)
        self.assertEqual([clip["identity"] for clip in self.ns["clips"]], self.ns["baseline"]["manifest"])
        changed = copy.deepcopy(self.rows)
        changed[0]["transcription"] = "a changed reference"
        self.ns["load_dataset"] = lambda *args, **kwargs: Stream(changed)
        with self.assertRaisesRegex(ValueError, "hash or metadata changed"):
            execute("recover-audio", self.ns)
        self.ns["load_dataset"] = lambda *args, **kwargs: Stream(self.rows + [self.rows[0]])
        with self.assertRaisesRegex(ValueError, "duplicate provenance"):
            execute("recover-audio", self.ns)
        self.ns["load_dataset"] = lambda *args, **kwargs: Stream(self.rows[:-1])
        with self.assertRaisesRegex(ValueError, "Missing original"):
            execute("recover-audio", self.ns)

    def test_listening_notes_follow_clip_identity(self):
        self.ns["clips"] = self.clips
        execute("listen", self.ns)
        self.assertNotIn("input(", CELLS["listen"])
        with self.assertRaisesRegex(ValueError, "still needs review"):
            execute("record-listening", self.ns)
        self.ns["reviews"] = [("match", "clear"), ("unsure", "technical term"), ("mismatch", "missing word"), ("match", ""), ("match", "")]
        review_tree = ast.parse(CELLS["record-listening"])
        review_tree.body = review_tree.body[1:]
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(review_tree, "record-listening", "exec"), self.ns)
        checks = self.ns["listening_checks"]
        self.assertEqual([row["clip_id"] for row in checks], list(self.ns["expected_clips"]))
        self.assertEqual(checks[2]["reference_check"], "mismatch")
        self.assertEqual(self.clips[2]["identity"]["transcription"], self.rows[2]["transcription"])

    def test_both_precisions_reload_and_run_identical_modes_and_clips(self):
        execute("recover-audio", self.ns)
        self.ns["listening_checks"] = [{"clip_id": clip["identity"]["clip_id"], "reference_check": "unsure"} for clip in self.clips]
        loaded = []
        downloads = []
        processor_loads = []

        def download_processor(**kwargs):
            downloads.append(kwargs)
            return 'test-processor-snapshot'

        def load_processor(path, **kwargs):
            processor_loads.append((path, kwargs))
            return FakeProcessor()

        class Model(FakeModel):
            def __init__(self, dtype):
                super().__init__()
                self.dtype = dtype
                self.generation_config = FakeConfig(lang_to_id={"<|hi|>": 1001, "<|ne|>": 1002})

            def to(self, device):
                return self

            def eval(self):
                return self

        def load_model(*args, **kwargs):
            model = Model(kwargs["dtype"])
            loaded.append(model)
            return model

        self.ns.update(
            DEVICE="test-device",
            torch=types.SimpleNamespace(
                float16="fp16", float32="fp32", manual_seed=lambda seed: None,
                inference_mode=contextlib.nullcontext,
                cuda=types.SimpleNamespace(empty_cache=lambda: None),
            ),
            snapshot_download=download_processor,
            AutoProcessor=types.SimpleNamespace(from_pretrained=load_processor),
            AutoModelForSpeechSeq2Seq=types.SimpleNamespace(from_pretrained=load_model),
            GenerationConfig=types.SimpleNamespace(from_dict=lambda config: FakeConfig(**copy.deepcopy(config))),
        )
        execute("precision-comparison", self.ns)
        execute("summary", self.ns)
        self.assertEqual([model.dtype for model in loaded], ["fp16", "fp32"])
        self.assertEqual(processor_loads, [('test-processor-snapshot', {'local_files_only': True})])
        self.assertEqual(downloads[0]['revision'], self.ns['MODEL_REVISION'])
        self.assertIn('merges.txt', downloads[0]['allow_patterns'])
        self.assertFalse(any('safetensors' in pattern or pattern == '*' for pattern in downloads[0]['allow_patterns']))
        self.assertEqual(len(self.ns["predictions"]), 20)
        self.assertEqual(set(self.ns["summary"]), {"fp16/auto", "fp16/forced_ne", "fp32/auto", "fp32/forced_ne"})
        self.assertEqual(loaded[0].calls, loaded[1].calls)
        self.assertEqual([call["language"] for call in loaded[0].calls], [None] * 5 + ["ne"] * 5)
        self.assertNotIn("model", self.ns)
        execute("precision-comparison", self.ns)
        self.assertEqual(len(self.ns["predictions"]), 20)
        self.ns["predictions"][0]["clip_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "coverage"):
            execute("summary", self.ns)


if __name__ == "__main__":
    unittest.main()
