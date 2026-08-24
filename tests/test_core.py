import tempfile
import unittest
import subprocess
import zipfile
from pathlib import Path

from rpa_docs.database import Database
from rpa_docs.uploads import extract_video_zip, safe_upload_path
from rpa_docs.drive import extract_folder_id
from rpa_docs.pipeline import create_job_previews, create_package, create_preview, extract_evidence, format_time, parse_timecode, preview_ranges, preview_ranges_from_moments, write_report


class CoreTests(unittest.TestCase):
    def test_job_lifecycle_and_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = Database(root / "test.sqlite3")
            payload = {
                "title": "Cadastro de pedido",
                "source_path": str(root / "discovery.mp4"),
                "process_context": "Fluxo demonstrado pelo usuário-chave.",
                "audience": "Equipe de RPA",
                "detail_level": "operacional",
                "api_approved": True,
                "api_budget_usd": 1.0,
            }
            created = database.create_job("abc123", payload)
            self.assertEqual(created["status"], "QUEUED")
            workspace = root / "job"
            (workspace / "evidence").mkdir(parents=True)
            steps = [{"image": "evidencia-0001.jpg", "time": 65, "timecode": "00:01:05", "title": "Abrir pedido", "action": "Acessa o cadastro.", "system": "ERP", "evidence": "Tela de cadastro visível."}]
            write_report(created, steps, workspace, Path(payload["source_path"]))
            self.assertTrue((workspace / "relatorio.html").exists())
            self.assertTrue((workspace / "relatorio.json").exists())
            self.assertTrue((workspace / "procedimento-operacional.md").exists())
            self.assertTrue((workspace / "requisitos-rpa.md").exists())
            self.assertTrue((workspace / "matriz-evidencias.csv").exists())
            self.assertTrue((workspace / "documentacao-processo.docx").exists())
            report = (workspace / "relatorio.html").read_text(encoding="utf-8")
            self.assertIn("Fluxo operacional consolidado", report)
            self.assertIn("Regras de negócio", report)

    def test_queued_job_can_be_cancelled(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Database(Path(temporary) / "test.sqlite3")
            payload = {"title": "Teste", "source_path": "video.mp4", "process_context": "", "audience": "RPA", "detail_level": "operacional", "api_approved": True, "api_budget_usd": 1.0}
            created = database.create_job("cancel01", payload)
            timing = database.timing(created)
            self.assertEqual(timing["queue_position"], 1)
            self.assertIsNone(timing["remaining_seconds"])
            cancelled = database.request_cancel("cancel01")
            self.assertEqual(cancelled["status"], "CANCELLED")
            retried = database.retry("cancel01")
            self.assertEqual(retried["status"], "QUEUED")
            self.assertIsNone(retried["error"])
            database.request_cancel("cancel01")
            candidates = database.cleanup_candidates()
            self.assertEqual(candidates, ["cancel01"])
            self.assertEqual(database.delete_jobs(candidates), 1)
            self.assertIsNone(database.get_job("cancel01"))

    def test_time_format(self):
        self.assertEqual(format_time(3661), "01:01:01")

    def test_preview_ranges_merge_close_evidence(self):
        steps = [{"time": 10}, {"time": 25}, {"time": 80}]
        self.assertEqual(preview_ranges(steps, 100), [(4.0, 37.0), (74.0, 92.0)])

    def test_spoken_moments_drive_preview_ranges(self):
        moments = [
            {"start": "00:00:10", "end": "00:00:20"},
            {"start": "00:00:22", "end": "00:00:30"},
            {"start": "inválido", "end": "00:01:00"},
        ]
        self.assertEqual(parse_timecode("01:02:03"), 3723)
        self.assertEqual(preview_ranges_from_moments(moments, 100), [(6.0, 36.0)])
        separated = [{"start": "00:00:10", "end": "00:00:20"}, {"start": "00:00:55", "end": "00:01:05"}]
        self.assertEqual(preview_ranges_from_moments(separated, 100), [(6.0, 26.0), (51.0, 71.0)])

    def test_upload_path_preserves_folder_and_blocks_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(safe_upload_path(root, "reuniao/parte-01.mp4"), (root / "reuniao" / "parte-01.mp4").resolve())
            with self.assertRaises(Exception):
                safe_upload_path(root, "../fora.mp4")

    def test_drive_folder_url_is_normalized(self):
        self.assertEqual(extract_folder_id("https://drive.google.com/drive/folders/abc123?usp=sharing"), "abc123")

    def test_zip_extracts_only_videos_and_preserves_folders(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "reunioes.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("parte-1/video.mp4", b"video")
                package.writestr("parte-1/notas.txt", b"ignorar")
            count = extract_video_zip(archive, root / "input")
            self.assertEqual(count, 1)
            self.assertTrue((root / "input" / "reunioes" / "parte-1" / "video.mp4").exists())

    def test_preview_and_zip_delivery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "source.mp4"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=3", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(video)], capture_output=True, check=True)
            result = create_preview(video, [{"time": 1}], root)
            self.assertTrue(result["created"])
            self.assertEqual(result["selection_basis"], "visual_evidence_fallback")
            self.assertTrue((root / "preview-processo.mp4").exists())
            self.assertTrue((root / "roteiro-cortes.json").exists())
            evidence = extract_evidence(video, root / "fast-evidence", interval=1)
            self.assertEqual(len(evidence), 3)
            (root / "relatorio.html").write_text("relatório", encoding="utf-8")
            (root / "relatorio.json").write_text("{}", encoding="utf-8")
            (root / "procedimento-operacional.md").write_text("procedimento", encoding="utf-8")
            (root / "requisitos-rpa.md").write_text("requisitos", encoding="utf-8")
            (root / "matriz-evidencias.csv").write_text("evidencia", encoding="utf-8")
            (root / "documentacao-processo.docx").write_bytes(b"docx")
            (root / "transcricao.json").write_text("[]", encoding="utf-8")
            (root / "evidence").mkdir()
            (root / "evidence" / "evidencia-0001.jpg").write_bytes(b"jpg")
            create_package(root)
            self.assertTrue((root / "entrega-completa.zip").exists())
            with zipfile.ZipFile(root / "entrega-completa.zip") as delivery:
                self.assertEqual(delivery.getinfo("preview-processo.mp4").compress_type, zipfile.ZIP_STORED)
                self.assertEqual(delivery.getinfo("relatorio.json").compress_type, zipfile.ZIP_DEFLATED)
                self.assertIn("procedimento-operacional.md", delivery.namelist())
                self.assertIn("requisitos-rpa.md", delivery.namelist())
                self.assertIn("matriz-evidencias.csv", delivery.namelist())
                self.assertIn("documentacao-processo.docx", delivery.namelist())
                self.assertIn("roteiro-cortes.json", delivery.namelist())

    def test_file_stack_creates_separate_previews(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = []
            for index, color in enumerate(("blue", "green"), 1):
                source = root / f"reuniao-{index}.mp4"
                subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=320x180:d=3", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(source)], capture_output=True, check=True)
                sources.append(source)
            analysis = root / "consolidado.mp4"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=6", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(analysis)], capture_output=True, check=True)
            preview, previews = create_job_previews(analysis, sources, [], root, [{"start": "00:00:01", "end": "00:00:05"}])
            self.assertTrue(preview["created"])
            self.assertEqual(len(previews), 2)
            self.assertTrue(all(item["created"] for item in previews))
            self.assertNotEqual(previews[0]["file"], previews[1]["file"])
            self.assertTrue(all((root / item["file"]).exists() for item in previews))
            self.assertFalse((root / "preview-processo.mp4").exists())
            (root / "relatorio.html").write_text("relatório", encoding="utf-8")
            create_package(root)
            with zipfile.ZipFile(root / "entrega-completa.zip") as delivery:
                for item in previews:
                    self.assertIn(item["file"], delivery.namelist())


if __name__ == "__main__":
    unittest.main()
