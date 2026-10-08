import array
import json
import math
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rpa_docs.config import FFMPEG
from rpa_docs.pipeline import (
    analyze, build_preview_plan, create_job_previews, create_package, create_preview,
    extract_evidence, normalize_documentation, parse_timecode, prepare_source,
    preview_ranges_from_moments, probe_duration, probe_media, process, render_preview,
    write_report,
)


def synthetic_video(path, size="320x180", fps=25, audio=False, duration=2, pix_fmt="yuv420p"):
    command = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
               "-i", f"color=c=blue:s={size}:r={fps}:d={duration}"]
    if audio:
        command += ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=44100:duration={duration}"]
    command += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", pix_fmt]
    if audio:
        command += ["-c:a", "aac", "-ac", "1"]
    subprocess.run(command + [str(path)], capture_output=True, check=True)


class PipelineQATests(unittest.TestCase):
    def test_invalid_timecodes_do_not_become_valid_after_padding(self):
        for value in (float("nan"), float("inf"), -2, True, "00:75:00", "00:00:99", "1:2:3:4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_timecode(value)
        self.assertEqual(parse_timecode("90:01.5"), 5401.5)
        self.assertEqual(preview_ranges_from_moments([
            {"start": 30, "end": 29}, {"start": 40, "end": 40},
            {"start": 101, "end": 102}, {"start": float("nan"), "end": 20},
        ], 100), [])

    def test_unrelated_gap_is_not_reinserted(self):
        self.assertEqual(preview_ranges_from_moments([
            {"start": 10, "end": 20}, {"start": 35, "end": 40},
        ], 100), [(6.0, 26.0), (31.0, 46.0)])

    def test_explicit_empty_context_does_not_fall_back_to_visual_frames(self):
        with patch("rpa_docs.pipeline.probe_duration", return_value=100):
            plan = build_preview_plan(Path("video.mp4"), [{"time": 10}], [])
            self.assertFalse(plan["created"])
            self.assertEqual(plan["ranges"], [])
            self.assertEqual(plan["selection_basis"], "contextual_spoken_content")
            self.assertTrue(build_preview_plan(Path("video.mp4"), [{"time": 10}])["created"])

    def test_invalid_capture_interval_fails_before_ffmpeg(self):
        with self.assertRaises(ValueError):
            extract_evidence(Path("unused.mp4"), Path("unused"), interval=0)

    def test_visual_response_does_not_fabricate_first_frame_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "evidence").mkdir()
            (workspace / "evidence" / "frame.jpg").write_bytes(b"synthetic-image")
            response = SimpleNamespace(output_text=json.dumps({"steps": [None, "wrong", {"frame_index": 99}, {"frame_index": "1", "title": "Confirmado"}]}))
            with patch("rpa_docs.pipeline.OpenAI") as client:
                client.return_value.responses.create.return_value = response
                result = analyze([{"index": 1, "time": 10, "image": "frame.jpg"}], [], workspace, "Processo", "operacional")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["frame_index"], 1)

    def test_malformed_documentation_keeps_only_usable_facts_and_exports(self):
        job = {"title": "Teste", "audience": "RPA", "process_context": "Cadastro", "detail_level": "operacional"}
        steps = [{"frame_index": 1, "time": 1, "timecode": "00:00:01", "title": "Abrir", "image": "1.jpg"}]
        document = normalize_documentation({
            "actors": ["incorrect", None, {"name": "Analista", "responsibility": ["nested"]}],
            "scope": {"in_scope": [None, "Cadastro"], "out_of_scope": {}},
            "process_flow": [None, {"title": "Cadastro", "evidence_refs": [1, 99]}],
            "business_rules": [{"rule": "Obrigatório", "evidence_refs": "1"}],
            "open_questions": [None, "Validar responsáveis"],
        }, job, steps)
        self.assertEqual(document["actors"], [{"name": "Analista", "responsibility": ""}])
        self.assertEqual(document["process_flow"][0]["evidence_refs"], [1])
        self.assertEqual(document["business_rules"][0]["evidence_refs"], [])
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            write_report(job, steps, workspace, Path("source.mp4"), document)
            for name in ("relatorio.html", "documentacao-processo.docx", "documentacao-processo.pdf"):
                self.assertGreater((workspace / name).stat().st_size, 100)

    def test_mixed_stack_has_consistent_video_audio_and_timeline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Equipe d'Água"
            sources = root / "input"
            sources.mkdir(parents=True)
            synthetic_video(sources / "01-sem-audio.mp4", size="180x320", fps=25)
            synthetic_video(sources / "02-mono-60fps.mp4", size="640x360", fps=60, audio=True)
            combined, originals = prepare_source(sources, root)
            streams = probe_media(combined)["streams"]
            video = next(item for item in streams if item["codec_type"] == "video")
            audio = next(item for item in streams if item["codec_type"] == "audio")
            self.assertEqual((video["width"], video["height"]), (1280, 720))
            self.assertEqual(video["pix_fmt"], "yuv420p")
            self.assertEqual(audio["channels"], 2)
            self.assertEqual(audio["sample_rate"], "48000")
            self.assertAlmostEqual(probe_duration(combined), sum(probe_duration(item) for item in originals), delta=0.12)
            decoded = subprocess.run([FFMPEG, "-v", "error", "-i", str(combined), "-f", "null", "-"], capture_output=True)
            self.assertEqual(decoded.returncode, 0, decoded.stderr.decode(errors="replace"))
            # Audio remains present in the second source even though the first
            # source is silent; concat used to drop or misalign this track.
            raw = subprocess.run([FFMPEG, "-v", "error", "-ss", "2.5", "-i", str(combined), "-t", "0.3", "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True, check=True)
            samples = array.array("f", raw.stdout)
            self.assertGreater(math.sqrt(sum(value * value for value in samples) / len(samples)), 0.01)

    def test_preview_with_silent_source_is_browser_compatible_and_decodable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "d'Água"
            root.mkdir()
            video = root / "source.mp4"
            synthetic_video(video, duration=4, pix_fmt="yuv444p")
            result = render_preview(video, [(0.5, 1.2), (2.0, 2.7)], root, root / "preview.mp4", root / "cuts.json", "contextual_spoken_content")
            self.assertTrue(result["created"])
            self.assertAlmostEqual(probe_duration(root / "preview.mp4"), 1.4, delta=0.10)
            self.assertEqual(probe_media(root / "preview.mp4")["streams"][0]["pix_fmt"], "yuv420p")

    def test_rebuild_without_selected_speech_removes_old_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "preview-processo.mp4").write_bytes(b"old-preview")
            with patch("rpa_docs.pipeline.probe_duration", return_value=100):
                result = create_preview(Path("unused.mp4"), [{"time": 20}], root, [])
            self.assertFalse(result["created"])
            self.assertFalse((root / "preview-processo.mp4").exists())

    def test_odd_sized_screen_recording_gets_even_preview_dimensions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "odd-screen.mp4"
            subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=321x181:rate=25:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv444p", str(video)], capture_output=True, check=True)
            result = create_preview(video, [], root, [{"start": 0, "end": 2}])
            self.assertTrue(result["created"])
            stream = probe_media(root / "preview-processo.mp4")["streams"][0]
            self.assertEqual(stream["width"] % 2, 0)
            self.assertEqual(stream["height"] % 2, 0)

    def test_many_audio_cuts_do_not_accumulate_encoder_padding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "source.mp4"
            synthetic_video(video, duration=10, audio=True)
            ranges = [(index, index + 0.5) for index in range(8)]
            result = render_preview(video, ranges, root, root / "preview.mp4", root / "cuts.json", "contextual_spoken_content")
            self.assertAlmostEqual(probe_duration(root / "preview.mp4"), result["duration"], delta=0.12)

    def test_cross_source_short_fragment_is_kept_with_its_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = [root / "a.mp4", root / "b.mp4"]
            for path in paths:
                synthetic_video(path)
            plan = {"created": True, "duration": 1, "ranges": [{"start": 1.5, "end": 2.5}], "selection_basis": "contextual_spoken_content", "moments": []}
            with patch("rpa_docs.pipeline.build_preview_plan", return_value=plan):
                _, previews = create_job_previews(root / "combined.mp4", paths, [], root, [])
            self.assertTrue(all(item["created"] for item in previews))
            self.assertAlmostEqual(previews[0]["duration"], 0.5, delta=0.05)
            self.assertAlmostEqual(previews[1]["duration"], 0.5, delta=0.05)
            second_script = json.loads((root / "roteiros" / "002-b-cortes.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(second_script["global_offset"], 2.0, delta=0.05)
            self.assertEqual(second_script["source_name"], "b.mp4")

    def test_package_includes_only_current_preview_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "previews").mkdir()
            (root / "previews" / "old.mp4").write_bytes(b"obsolete")
            (root / "previews" / "current.mp4").write_bytes(b"current")
            (root / "preview-processo.mp4").write_bytes(b"obsolete-combined")
            (root / "roteiro-cortes.json").write_text(json.dumps({"previews": [{"created": True, "file": "previews/current.mp4"}]}), encoding="utf-8")
            (root / "relatorio.html").write_text("Current report", encoding="utf-8")
            create_package(root)
            self.assertFalse((root / "entrega-completa.zip.tmp").exists())
            with zipfile.ZipFile(root / "entrega-completa.zip") as package:
                self.assertIn("previews/current.mp4", package.namelist())
                self.assertNotIn("previews/old.mp4", package.namelist())
                self.assertNotIn("preview-processo.mp4", package.namelist())

    def test_no_transcript_never_claims_contextual_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = {"limitations": [], "preview_moments": [{"start": 1, "end": 10}], "process_flow": []}
            with patch("rpa_docs.pipeline.prepare_source", return_value=(Path("video.mp4"), [Path("video.mp4")])), patch("rpa_docs.pipeline.extract_evidence", return_value=[]), patch("rpa_docs.pipeline.transcribe", return_value=[]), patch("rpa_docs.pipeline.analyze", return_value=[]), patch("rpa_docs.pipeline.synthesize_documentation", return_value=document), patch("rpa_docs.pipeline.create_job_previews", return_value=({"created": False}, [])) as previews, patch("rpa_docs.pipeline.write_report"), patch("rpa_docs.pipeline.create_package"):
                result = process({"source_path": "video.mp4", "process_context": "Cadastro", "detail_level": "operacional"}, root, lambda *args: None)
            self.assertEqual(previews.call_args.args[-1], [])
            self.assertTrue(result["warnings"])
            self.assertTrue(document["limitations"])


if __name__ == "__main__":
    unittest.main()
