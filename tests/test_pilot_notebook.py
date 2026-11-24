"""Check notebook helpers with synthetic WAVs; never download ASR models/data."""

import ast
import contextlib
import copy
import hashlib
import io
import json
import math
import os
import sys
import tempfile
import types
import unicodedata
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf
from jiwer import cer, wer

NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "01_dataset_and_whisper_test.ipynb"
NOTEBOOK = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
CELLS = {cell["id"]: "".join(cell["source"]) for cell in NOTEBOOK["cells"]}
COLUMNS = ast.literal_eval(ast.parse(CELLS["dataset-load"]).body[0].value)


def execute(cell_id, namespace):
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(CELLS[cell_id], f"{NOTEBOOK_PATH}:{cell_id}", "exec"), namespace)


def wav_row(number=1, waveform=None, sample_rate=16000):
    if waveform is None:
        waveform = np.full(1600, number / 10, dtype=np.float32)
    audio_file = io.BytesIO()
    sf.write(audio_file, waveform, sample_rate, format="WAV", subtype="FLOAT")
    duration = len(waveform) / sample_rate
    return {
        "audio": {"bytes": audio_file.getvalue()}, "transcription": f"शब्द school {number}",
        "transcription_devanagari": f"शब्द स्कुल {number}",
        "transcription_romanized": f"shabda school {number}",
        "cmi": 33.33, "speech_type": "cs", "speaker_id": "fixture-channel",
        "video_id": f"fixture-video-{number}", "start_ms": 0,
        "end_ms": round(duration * 1000), "duration_s": duration,
    }


class FakeConfig(types.SimpleNamespace):
    def to_dict(self):
        return copy.deepcopy(vars(self))


class TokenRow:
    def __init__(self, values):
        self.values = values

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self.values[:]


class Tokens:
    def __init__(self, values):
        self.values = values

    def __getitem__(self, index):
        if index != 0:
            raise IndexError(index)
        return TokenRow(self.values)


class Features(dict):
    def to(self, *args, **kwargs):
        return self


class FakeProcessor:
    tokenizer = types.SimpleNamespace(eos_token_id=99)

    def __call__(self, audio, **kwargs):
        return Features(marker=round(float(audio[0]) * 10))

    def batch_decode(self, sequences, **kwargs):
        marker = sequences.values[4]
        if sequences.values[1] == 1001 and marker == 2:
            return [""]
        return [f"शब्द school {marker}"]


class FakeModel:
    def __init__(self):
        self.calls = []

    def generate(self, *, generation_config, marker, return_dict_in_generate, **kwargs):
        if not return_dict_in_generate:
            raise AssertionError("Full generation output is needed to inspect prefix/EOS tokens.")
        self.calls.append(copy.deepcopy(generation_config.to_dict()))
        language = 1002 if generation_config.language == "ne" else 1001
        values = [10, language, 20, 30, marker]
        if marker != 3:
            values.append(99)
        generation_config.language = "mutated-by-generation"
        return types.SimpleNamespace(sequences=Tokens(values))


class PilotNotebookTests(unittest.TestCase):
    def setUp(self):
        self.played = []
        self.ns = {
            "np": np, "sf": sf, "math": math, "hashlib": hashlib, "io": io,
            "unicodedata": unicodedata, "wer": wer, "cer": cer, "copy": copy,
            "json": json, "columns": COLUMNS, "Audio": lambda audio, rate: (audio.copy(), rate),
            "display": self.played.append,
        }
        execute("settings", self.ns)
        execute("scoring-selfchecks", self.ns)
        execute("audio-helpers", self.ns)

    def inference_namespace(self):
        self.ns["selected_rows"] = [wav_row(number) for number in range(1, 6)]
        execute("audio-inspection", self.ns)
        self.ns.update(
            processor=FakeProcessor(), model=FakeModel(), DEVICE="test-device", DTYPE="float16",
            torch=types.SimpleNamespace(
                inference_mode=contextlib.nullcontext, __version__="test",
                version=types.SimpleNamespace(cuda="test"),
                cuda=types.SimpleNamespace(get_device_name=lambda index: "test GPU"),
            ),
            base_generation=FakeConfig(
                language="inherited-language", forced_decoder_ids=[[1, 1001]],
                lang_to_id={"<|hi|>": 1001, "<|ne|>": 1002},
            ),
            id_to_language={1001: "<|hi|>", 1002: "<|ne|>"},
        )
        execute("whisper-comparison", self.ns)
        execute("pilot-summary", self.ns)
        return self.ns

    def test_notebook_is_clean_and_each_code_cell_has_a_topic(self):
        self.assertEqual(len({cell["id"] for cell in NOTEBOOK["cells"]}), len(NOTEBOOK["cells"]))
        for index, cell in enumerate(NOTEBOOK["cells"]):
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])
                self.assertTrue("".join(NOTEBOOK["cells"][index - 1]["source"]).startswith("### "))
                source = "\n".join(line for line in "".join(cell["source"]).splitlines() if not line.startswith("%pip "))
                compile(source, f"cell{index}", "exec")

    def test_normalization_preserves_script_and_composes_unicode(self):
        normalize = self.ns["normalize_text"]
        self.assertEqual(normalize("  नेपालमा १२ school छन्। "), "नेपालमा 12 school छन्")
        self.assertEqual(normalize("cafe\u0301"), "café")
        self.assertNotEqual(normalize("school"), normalize("स्कुल"))
        self.assertEqual(normalize(""), "")

    def test_real_wav_downmix_keeps_metadata_and_dtype(self):
        stereo = np.column_stack([np.full(1600, 0.1), np.full(1600, 0.3)])
        row = wav_row(waveform=stereo)
        clip = self.ns["prepare_clip"](row)
        self.assertEqual(clip["audio"].shape, (1600,))
        self.assertEqual(clip["audio"].dtype, np.float32)
        np.testing.assert_allclose(clip["audio"], 0.2, atol=1e-6)
        self.assertEqual(clip["identity"]["source_channels"], 2)
        self.assertEqual(clip["identity"]["transcription"], row["transcription"])
        self.assertEqual(clip["identity"]["clip_id"], "validation/fixture-video-1/0-100")

    def test_invalid_reference_cmi_identity_duration_and_audio_are_rejected(self):
        cases = [
            {"transcription": "  "}, {"cmi": float("nan")}, {"cmi": 51},
            {"video_id": ""}, {"start_ms": None}, {"end_ms": 0},
            {"end_ms": 200}, {"duration_s": None}, {"duration_s": 2}, {"audio": {"bytes": b""}},
        ]
        for change in cases:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.ns["prepare_clip"]({**wav_row(), **change})
        for row in [
            wav_row(sample_rate=8000),
            wav_row(waveform=np.zeros(0, dtype=np.float32)),
            wav_row(waveform=np.full(1600, np.nan, dtype=np.float32)),
        ]:
            with self.subTest(audio=row["duration_s"]):
                with self.assertRaises(ValueError):
                    self.ns["prepare_clip"](row)

    def test_duplicate_audio_is_not_silently_evaluated_twice(self):
        self.ns["selected_rows"] = [wav_row(), {**wav_row(), "video_id": "different-id"}]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            execute("audio-inspection", self.ns)

    def test_sample_three_replay_uses_its_own_audio_and_reference(self):
        self.ns["selected_rows"] = [wav_row(number) for number in range(1, 6)]
        execute("audio-inspection", self.ns)
        execute("selected-audio", self.ns)
        self.assertIn("fixture-video-3", self.ns["selected_clip"]["identity"]["clip_id"])
        np.testing.assert_allclose(self.played[-1][0], 0.3, atol=1e-6)
        self.ns["SAMPLE_NUMBER"] = 0
        with self.assertRaises(ValueError):
            execute("selected-audio", self.ns)

    def test_modes_are_isolated_empty_predictions_are_scored_and_reruns_reset(self):
        namespace = self.inference_namespace()
        self.assertEqual(len(namespace["predictions"]), 10)
        empty = next(row for row in namespace["predictions"] if row["mode"] == "auto" and not row["hypothesis"])
        self.assertEqual(empty["wer"], 1.0)
        self.assertEqual(namespace["summary"]["auto"]["clips"], 5)
        self.assertEqual(namespace["summary"]["forced_ne"]["outputs_without_eos"], 1)
        self.assertEqual(namespace["predictions"][0]["language_token"], "<|hi|>")
        calls = namespace["model"].calls
        self.assertEqual([call["language"] for call in calls], [None] * 5 + ["ne"] * 5)
        self.assertTrue(all(call["forced_decoder_ids"] is None for call in calls))
        execute("whisper-comparison", namespace)
        execute("pilot-summary", namespace)
        self.assertEqual(len(namespace["predictions"]), 10)
        namespace["predictions"][0]["clip_id"] = "wrong-clip"
        with self.assertRaisesRegex(ValueError, "same unique"):
            execute("pilot-summary", namespace)

    def test_export_contains_results_and_environment_without_audio(self):
        namespace = self.inference_namespace()
        namespace.update(
            sys=sys, platform=types.SimpleNamespace(platform=lambda: "test platform"),
            datetime=datetime, timezone=timezone, Path=Path, zipfile=zipfile,
            subprocess=types.SimpleNamespace(check_output=lambda *args, **kwargs: "test environment\n"),
            unfiltered_preview=[wav_row()], SAMPLE_NUMBER=3,
        )
        downloads = []
        google = types.ModuleType("google")
        colab = types.ModuleType("google.colab")
        colab.files = types.SimpleNamespace(download=downloads.append)
        google.colab = colab
        previous_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary, patch.dict(sys.modules, {"google": google, "google.colab": colab}):
            try:
                os.chdir(temporary)
                execute("export", namespace)
                with zipfile.ZipFile(namespace["archive_path"]) as archive:
                    self.assertEqual(set(archive.namelist()), {"results.json", "environment.txt"})
                    results = json.loads(archive.read("results.json"))
                self.assertEqual(len(results["manifest"]), 5)
                self.assertEqual(len(results["predictions"]), 10)
                self.assertTrue(results["generation_overrides"]["return_dict_in_generate"])
                self.assertIn("transcription_devanagari", results["manifest"][0])
                self.assertNotIn("audio", results["manifest"][0])
                self.assertEqual(len(downloads), 1)
            finally:
                os.chdir(previous_directory)


if __name__ == "__main__":
    unittest.main()
