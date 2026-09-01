import tempfile
import unittest
import subprocess
import zipfile
from pathlib import Path

from rpa_docs.database import Database
from rpa_docs.uploads import extract_video_zip, safe_upload_path
from rpa_docs.drive import extract_folder_id
from rpa_docs.pipeline import create_job_previews, create_package, create_preview, extract_evidence, fallback_process_prompt, format_time, locate_in_preview, parse_timecode, preview_ranges, preview_ranges_from_moments, write_pdf_document, write_report


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
            self.assertTrue((workspace / "documentacao-processo.pdf").exists())
            report = (workspace / "relatorio.html").read_text(encoding="utf-8")
            self.assertIn('href="documentacao-processo.pdf"', report)
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

    def test_pdf_export_keeps_documentation_sections(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            job = {"title": "Emissão de notas", "audience": "Equipe de RPA", "detail_level": "detalhado"}
            document = {
                "executive_summary": "Consolidação dos contratos e emissão das notas do ciclo.",
                "objective": "Emitir as notas sem divergência de valor.",
                "scope": {"in_scope": ["Contratos ativos"], "out_of_scope": ["Cobrança"]},
                "actors": [{"name": "Analista", "responsibility": "Confere e emite."}],
                "systems": [{"name": "ERP", "purpose": "Emissão fiscal"}],
                "prerequisites": ["Acesso ao módulo fiscal"],
                "inputs": [{"name": "Contratos", "source": "ERP", "required": "Obrigatória"}],
                "outputs": [{"name": "Notas", "destination": "Portal"}],
                "business_rules": [{"rule": "Sem reajuste não fatura.", "evidence_refs": [1]}],
                "process_flow": [{"sequence": 1, "title": "Abrir contratos", "description": "Filtra os ativos.", "actor": "Analista", "system": "ERP", "input": "Competência", "output": "Lista", "decision_or_exception": "", "evidence_refs": [1]}],
                "exceptions": [], "risks_and_controls": [], "open_questions": [],
                "automation_opportunities": [], "limitations": ["Somente fatos observáveis."],
            }
            path = write_pdf_document(job, document, workspace)
            self.assertEqual(path, workspace / "documentacao-processo.pdf")
            self.assertTrue(path.exists())
            content = path.read_bytes()
            self.assertTrue(content.startswith(b"%PDF-"))
            self.assertGreater(len(content), 2000)

    def test_prompt_fallback_declares_subject_and_cut_rule(self):
        prompt = fallback_process_prompt({
            "title": "Faturamento de contratos",
            "audience": "Equipe fiscal",
            "detail_level": "detalhado",
            "process_context": "",
            "sources": ["reuniao-1.mp4", "reuniao-2.mp4"],
        })
        first_line = prompt.splitlines()[0]
        self.assertTrue(first_line.startswith("Assunto do discovery:"))
        self.assertIn("Faturamento de contratos", first_line)
        self.assertIn("reuniao-2.mp4", prompt)
        self.assertIn("Equipe fiscal", prompt)
        self.assertIn("Descarte", prompt)
        written = fallback_process_prompt({"title": "Genérico", "process_context": "Somente o case Trevo"})
        self.assertIn("Somente o case Trevo", written.splitlines()[0])

    def test_evidence_maps_to_the_cut_where_it_is_spoken(self):
        previews = [
            {"created": True, "file": "previews/001-a-preview.mp4", "source_name": "a.mp4", "global_offset": 0,
             "ranges": [{"start": 100.0, "end": 160.0}, {"start": 300.0, "end": 360.0}]},
            {"created": True, "file": "previews/002-b-preview.mp4", "source_name": "b.mp4", "global_offset": 600.0,
             "ranges": [{"start": 40.0, "end": 100.0}]},
        ]
        # primeiro corte: o instante 130 fica 30s depois do início do corte, e o preview começa nele
        first = locate_in_preview(previews, 130.0)
        self.assertEqual(first["file"], "previews/001-a-preview.mp4")
        self.assertEqual(first["play_from"], 22.0)
        self.assertEqual(first["play_to"], 60.0)
        self.assertEqual((first["cut_start"], first["cut_end"]), (100.0, 160.0))
        # segundo corte do mesmo arquivo: o tempo acumulado do corte anterior entra na conta
        second = locate_in_preview(previews, 310.0)
        self.assertEqual(second["play_from"], 62.0)
        self.assertEqual(second["play_to"], 120.0)
        # o lead-in nunca ultrapassa o início do corte
        self.assertEqual(locate_in_preview(previews, 101.0)["play_from"], 0.0)
        # segunda gravação da pilha: o deslocamento global é descontado
        third = locate_in_preview(previews, 700.0)
        self.assertEqual(third["file"], "previews/002-b-preview.mp4")
        self.assertEqual(third["source_name"], "b.mp4")
        self.assertEqual(third["play_from"], 52.0)
        # instantes fora dos cortes não recebem vídeo
        self.assertIsNone(locate_in_preview(previews, 200.0))
        self.assertIsNone(locate_in_preview(previews, 5000.0))
        self.assertIsNone(locate_in_preview(previews, None))
        self.assertIsNone(locate_in_preview(None, 130.0))
        self.assertIsNone(locate_in_preview([{"created": False, "file": None, "ranges": []}], 130.0))

    def test_report_evidence_plays_the_spoken_cut(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "evidence").mkdir()
            job = {"title": "Cadastro", "source_path": "video.mp4", "process_context": "", "audience": "RPA", "detail_level": "operacional"}
            steps = [
                {"frame_index": 1, "image": "evidencia-0001.jpg", "time": 130, "timecode": "00:02:10", "title": "Abrir pedido", "action": "Acessa o cadastro.", "system": "ERP", "evidence": "Tela visível."},
                {"frame_index": 2, "image": "evidencia-0002.jpg", "time": 200, "timecode": "00:03:20", "title": "Conferir saldo", "action": "Confere o saldo.", "system": "ERP", "evidence": "Saldo visível."},
            ]
            previews = [{"created": True, "file": "previews/001-a-preview.mp4", "source_name": "a.mp4",
                         "ranges": [{"start": 100.0, "end": 160.0}]}]
            write_report(job, steps, workspace, Path("video.mp4"), None, previews)
            report = (workspace / "relatorio.html").read_text(encoding="utf-8")
            self.assertIn('poster="evidence/evidencia-0001.jpg"', report)
            self.assertIn('src="previews/001-a-preview.mp4#t=22.0,60.0"', report)
            self.assertIn("Corte 00:01:40–00:02:40 · a.mp4", report)
            self.assertIn("Momento fora dos cortes do preview", report)
            self.assertIn('<img src="evidence/evidencia-0002.jpg"', report)

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
            (root / "documentacao-processo.pdf").write_bytes(b"%PDF-1.4")
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
                self.assertIn("documentacao-processo.pdf", delivery.namelist())
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
