from __future__ import annotations

import base64
import csv
from html import escape
import json
import os
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

from .config import FFMPEG, FFPROBE


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}


def find_videos(source: Path) -> list[Path]:
    if source.is_file() and source.suffix.lower() in VIDEO_EXTENSIONS:
        return [source]
    if source.is_dir():
        candidates = sorted((item for item in source.rglob("*") if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS), key=lambda item: str(item.relative_to(source)).lower())
        if candidates:
            return candidates
    raise ValueError("Nenhuma gravação de vídeo compatível foi encontrada.")


def prepare_source(source: Path, workspace: Path) -> tuple[Path, list[Path]]:
    videos = find_videos(source)
    if len(videos) == 1:
        return videos[0], videos
    normalized_dir = workspace / "fontes-normalizadas"
    normalized_dir.mkdir(exist_ok=True)
    normalized = []
    for index, video in enumerate(videos, 1):
        output = normalized_dir / f"fonte-{index:03d}.mp4"
        completed = subprocess.run([
            FFMPEG, "-y", "-i", str(video), "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart", str(output),
        ], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Não foi possível preparar a gravação {video.name}: {completed.stderr[-800:]}")
        normalized.append(output)
    concat_list = normalized_dir / "concat.txt"
    concat_list.write_text("\n".join(f"file '{item.as_posix()}'" for item in normalized), encoding="utf-8")
    combined = workspace / "gravacao-consolidada.mp4"
    completed = subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", "-movflags", "+faststart", str(combined),
    ], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Não foi possível consolidar as gravações: {completed.stderr[-800:]}")
    return combined, videos


def probe_duration(video: Path) -> float:
    completed = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video)], capture_output=True, text=True, check=True)
    return float(completed.stdout.strip())


def extract_evidence(video: Path, output: Path, interval: float = 20.0) -> list[dict]:
    duration = probe_duration(video)
    output.mkdir(parents=True, exist_ok=True)
    timestamps = [index * interval for index in range(max(1, int(duration // interval) + 1)) if index * interval < duration]

    def capture(index_and_time: tuple[int, float]) -> dict | None:
        index, timestamp = index_and_time
        filename = f"evidencia-{index:04d}.jpg"
        completed = subprocess.run([
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{timestamp:.3f}",
            "-i", str(video), "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2",
            "-q:v", "3", "-threads", "1", str(output / filename),
        ], capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not (output / filename).exists():
            return None
        return {"index": index, "time": round(timestamp, 3), "image": filename}

    workers = max(2, min(6, (os.cpu_count() or 4) // 2))
    evidence = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="frame") as executor:
        futures = [executor.submit(capture, item) for item in enumerate(timestamps, 1)]
        for future in as_completed(futures):
            item = future.result()
            if item:
                evidence.append(item)
    return sorted(evidence, key=lambda item: item["index"])


def transcribe(video: Path, workspace: Path) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
        model_name = os.getenv("WHISPER_MODEL", "base")
        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=max(2, (os.cpu_count() or 4) - 2),
            num_workers=1,
        )
        segments, _ = model.transcribe(
            str(video),
            language="pt",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            word_timestamps=False,
        )
        result = [{"start": round(item.start, 3), "end": round(item.end, 3), "text": item.text.strip()} for item in segments]
    except Exception as error:
        (workspace / "transcricao-aviso.txt").write_text(f"Transcrição indisponível: {error}", encoding="utf-8")
        result = []
    (workspace / "transcricao.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def nearby_transcript(transcript: list[dict], timestamp: float, radius: float = 18.0) -> str:
    return " ".join(item["text"] for item in transcript if item["end"] >= timestamp - radius and item["start"] <= timestamp + radius)[:1800]


def analyze(evidence: list[dict], transcript: list[dict], workspace: Path, context: str, detail: str) -> list[dict]:
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    batches = [evidence[start:start + 10] for start in range(0, len(evidence), 10)]

    def analyze_batch(batch: list[dict]) -> list[dict]:
        content = [{"type": "input_text", "text": (
            "Analise estes frames de uma gravação de discovery de RPA. Identifique mudanças de tela e ações executadas. "
            "Retorne JSON puro no formato {\"steps\":[{\"frame_index\":1,\"title\":\"...\",\"action\":\"...\","
            "\"system\":\"...\",\"field_or_control\":\"...\",\"evidence\":\"o que no frame sustenta a descrição\","
            "\"uncertainty\":\"\"}]}. Não invente cliques, campos ou valores invisíveis. Consolide frames sem mudança relevante. "
            f"Nível: {detail}. Contexto informado: {context or 'não informado'}."
        )}]
        for item in batch:
            path = workspace / "evidence" / item["image"]
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            content.append({"type": "input_text", "text": f"Frame {item['index']} em {format_time(item['time'])}. Fala próxima: {nearby_transcript(transcript, item['time']) or 'sem fala detectada'}"})
            content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{encoded}", "detail": "low"})
        client = OpenAI()
        response = client.responses.create(model=model, input=[{"role": "user", "content": content}])
        text = response.output_text.strip().removeprefix("```json").removesuffix("```").strip()
        if not text.startswith("{"):
            text = text[text.find("{"):text.rfind("}") + 1]
        payload = json.loads(text)
        batch_steps = []
        for step in payload.get("steps", []):
            frame = next((item for item in batch if item["index"] == step.get("frame_index")), batch[0])
            step |= {"time": frame["time"], "timecode": format_time(frame["time"]), "image": frame["image"], "transcript": nearby_transcript(transcript, frame["time"])}
            batch_steps.append(step)
        return batch_steps

    steps = []
    workers = max(1, min(3, len(batches)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="vision") as executor:
        futures = [executor.submit(analyze_batch, batch) for batch in batches]
        for future in as_completed(futures):
            steps.extend(future.result())
    return sorted(steps, key=lambda item: float(item.get("time", 0)))


def fallback_documentation(job: dict, steps: list[dict], warning: str = "") -> dict:
    systems = sorted({str(step.get("system") or "").strip() for step in steps if str(step.get("system") or "").strip()})
    flow = []
    for sequence, step in enumerate(steps, 1):
        flow.append({
            "sequence": sequence,
            "title": step.get("title") or f"Etapa {sequence}",
            "description": step.get("action") or "Ação não descrita.",
            "actor": "Não identificado",
            "system": step.get("system") or "Não identificado",
            "input": "Não identificado",
            "output": "Não identificado",
            "decision_or_exception": "",
            "evidence_refs": [step.get("frame_index")] if step.get("frame_index") else [],
        })
    limitations = ["A documentação foi montada somente com os fatos observáveis na gravação."]
    if warning:
        limitations.append(f"A síntese automática não pôde ser concluída: {warning}")
    return {
        "executive_summary": job.get("process_context") or f"Processo {job.get('title', '')} documentado a partir da gravação de discovery.",
        "objective": job.get("process_context") or "Objetivo não explicitado na gravação.",
        "scope": {"in_scope": [], "out_of_scope": []},
        "actors": [],
        "systems": [{"name": name, "purpose": "Finalidade não explicitada."} for name in systems],
        "prerequisites": [],
        "inputs": [],
        "outputs": [],
        "business_rules": [],
        "process_flow": flow,
        "exceptions": [],
        "risks_and_controls": [],
        "open_questions": ["Validar com o responsável pelo processo os pontos que não foram explicitados na gravação."],
        "automation_opportunities": [],
        "limitations": limitations,
    }


def normalize_documentation(document, job: dict, steps: list[dict]) -> dict:
    baseline = fallback_documentation(job, steps)
    if not isinstance(document, dict):
        return baseline
    for key in ("executive_summary", "objective"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            document[key] = baseline[key]
    scope = document.get("scope")
    if not isinstance(scope, dict):
        scope = baseline["scope"]
    for key in ("in_scope", "out_of_scope"):
        if not isinstance(scope.get(key), list):
            scope[key] = []
    document["scope"] = scope
    list_fields = (
        "actors", "systems", "prerequisites", "inputs", "outputs", "business_rules",
        "process_flow", "exceptions", "risks_and_controls", "open_questions",
        "automation_opportunities", "limitations",
    )
    for key in list_fields:
        if not isinstance(document.get(key), list):
            document[key] = baseline[key]
    if not document["process_flow"]:
        document["process_flow"] = baseline["process_flow"]
    return document


def synthesize_documentation(job: dict, steps: list[dict], transcript: list[dict], workspace: Path) -> dict:
    transcript_lines = "\n".join(f"[{format_time(item['start'])}] {item['text']}" for item in transcript)
    observed_steps = [{
        "frame_index": item.get("frame_index"),
        "timecode": item.get("timecode"),
        "title": item.get("title"),
        "action": item.get("action"),
        "system": item.get("system"),
        "field_or_control": item.get("field_or_control"),
        "evidence": item.get("evidence"),
        "uncertainty": item.get("uncertainty"),
    } for item in steps]
    prompt = f'''Você é analista de processos e discovery de RPA. Transforme os insumos abaixo em documentação operacional estruturada, e não em resumo de transcrição.

REGRAS DE CONFIABILIDADE
- Use somente fatos demonstrados visualmente, explicitamente falados ou informados no contexto do pedido.
- Não invente regras, responsáveis, integrações, frequências, volumes, credenciais, exceções ou sistemas.
- Quando algo necessário não estiver claro, registre em open_questions ou use "Não identificado".
- Consolide ações de tela em etapas de negócio compreensíveis. A transcrição e os frames são evidências, não a estrutura principal.
- evidence_refs deve conter somente frame_index existentes nos passos observados.
- Diferencie o processo atual de oportunidades futuras de automação.

PEDIDO
Título: {job.get('title', '')}
Contexto informado: {job.get('process_context') or 'Não informado'}
Público: {job.get('audience') or 'Equipe de RPA'}
Nível: {job.get('detail_level') or 'operacional'}

PASSOS OBSERVADOS
{json.dumps(observed_steps, ensure_ascii=False)}

TRANSCRIÇÃO COM TIMECODE
{transcript_lines or 'Transcrição indisponível.'}

Retorne JSON puro exatamente com esta estrutura:
{{
  "executive_summary": "síntese do processo em linguagem de negócio",
  "objective": "resultado que o processo busca produzir",
  "scope": {{"in_scope": ["..."], "out_of_scope": ["..."]}},
  "actors": [{{"name": "...", "responsibility": "..."}}],
  "systems": [{{"name": "...", "purpose": "..."}}],
  "prerequisites": ["..."],
  "inputs": [{{"name": "...", "source": "...", "required": "..."}}],
  "outputs": [{{"name": "...", "destination": "..."}}],
  "business_rules": [{{"rule": "...", "evidence_refs": [1]}}],
  "process_flow": [{{"sequence": 1, "title": "...", "description": "...", "actor": "...", "system": "...", "input": "...", "output": "...", "decision_or_exception": "...", "evidence_refs": [1]}}],
  "exceptions": [{{"scenario": "...", "handling": "...", "status": "confirmado ou a validar"}}],
  "risks_and_controls": [{{"risk": "...", "impact": "...", "control": "..."}}],
  "open_questions": ["..."],
  "automation_opportunities": [{{"opportunity": "...", "benefit": "...", "dependency": "..."}}],
  "limitations": ["..."]
}}'''
    try:
        client = OpenAI()
        response = client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"), input=prompt)
        text = response.output_text.strip().removeprefix("```json").removesuffix("```").strip()
        if not text.startswith("{"):
            text = text[text.find("{"):text.rfind("}") + 1]
        document = json.loads(text)
        baseline = fallback_documentation(job, steps)
        for key, value in baseline.items():
            document.setdefault(key, value)
        return normalize_documentation(document, job, steps)
    except Exception as error:
        (workspace / "documentacao-aviso.txt").write_text(f"Síntese estruturada indisponível: {error}", encoding="utf-8")
        return fallback_documentation(job, steps, str(error))


def format_time(seconds: float) -> str:
    value = max(0, round(seconds))
    return f"{value // 3600:02d}:{(value % 3600) // 60:02d}:{value % 60:02d}"


def preview_ranges(steps: list[dict], duration: float, before: float = 6.0, after: float = 12.0) -> list[tuple[float, float]]:
    ranges = []
    for step in sorted(steps, key=lambda item: float(item.get("time", 0))):
        start = max(0.0, float(step.get("time", 0)) - before)
        end = min(duration, float(step.get("time", 0)) + after)
        if end <= start:
            continue
        if ranges and start <= ranges[-1][1] + 5.0:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
        else:
            ranges.append((start, end))
    return ranges


def create_preview(video: Path, steps: list[dict], workspace: Path) -> dict:
    ranges = preview_ranges(steps, probe_duration(video))
    if not ranges:
        return {"created": False, "duration": 0, "ranges": []}
    segments_dir = workspace / "preview-segments"
    segments_dir.mkdir(exist_ok=True)
    segments = []
    for index, (start, end) in enumerate(ranges, 1):
        segment = segments_dir / f"segment-{index:03d}.mp4"
        completed = subprocess.run([
            FFMPEG, "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(video),
            "-map", "0:v:0", "-map", "0:a?", "-vf", "scale='min(1280,iw)':-2",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "27", "-c:a", "aac",
            "-b:a", "96k", "-movflags", "+faststart", str(segment),
        ], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Não foi possível montar o trecho {index} do preview: {completed.stderr[-800:]}")
        segments.append(segment)
    concat_list = segments_dir / "concat.txt"
    concat_list.write_text("\n".join(f"file '{item.as_posix()}'" for item in segments), encoding="utf-8")
    preview = workspace / "preview-processo.mp4"
    completed = subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", "-movflags", "+faststart", str(preview),
    ], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Não foi possível finalizar o preview: {completed.stderr[-800:]}")
    return {
        "created": True,
        "duration": round(sum(end - start for start, end in ranges), 3),
        "ranges": [{"start": round(start, 3), "end": round(end, 3)} for start, end in ranges],
        "file": preview.name,
    }


def create_package(workspace: Path):
    package = workspace / "entrega-completa.zip"
    included = [
        "relatorio.html", "relatorio.json", "documentacao-processo.json",
        "documentacao-processo.docx", "procedimento-operacional.md", "requisitos-rpa.md", "matriz-evidencias.csv",
        "transcricao.json", "preview-processo.mp4", "transcricao-aviso.txt", "documentacao-aviso.txt",
    ]
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in included:
            path = workspace / name
            if path.exists():
                compression = zipfile.ZIP_STORED if path.suffix.lower() == ".mp4" else zipfile.ZIP_DEFLATED
                archive.write(path, arcname=name, compress_type=compression)
        for path in sorted((workspace / "evidence").glob("*.jpg")):
            archive.write(path, arcname=f"evidence/{path.name}", compress_type=zipfile.ZIP_STORED)


def markdown_value(value) -> str:
    return str(value or "Não identificado").replace("|", "\\|").replace("\n", " ")


def write_docx_document(job: dict, document: dict, workspace: Path):
    try:
        from docx import Document
        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Inches, Pt, RGBColor, Twips
    except ImportError as error:
        (workspace / "documentacao-aviso.txt").write_text(f"Documento Word indisponível: {error}", encoding="utf-8")
        return

    navy = RGBColor(16, 45, 70)
    teal = RGBColor(22, 141, 138)
    muted = RGBColor(84, 112, 134)
    word = Document()
    section = word.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = section.right_margin = section.bottom_margin = section.left_margin = Inches(1)
    section.header_distance = section.footer_distance = Inches(0.492)

    def set_font(run, size=None, color=None, bold=None, italic=None):
        run.font.name = "Calibri"
        run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Calibri")
        run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Calibri")
        if size is not None:
            run.font.size = Pt(size)
        if color is not None:
            run.font.color.rgb = color
        if bold is not None:
            run.bold = bold
        if italic is not None:
            run.italic = italic

    normal = word.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25
    for name, size, color, before, after in (
        ("Heading 1", 16, navy, 18, 10), ("Heading 2", 13, navy, 14, 7), ("Heading 3", 12, muted, 10, 5),
    ):
        style = word.styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.color.rgb = color
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    header = section.header.paragraphs[0]
    header.text = "BTIME · DOCUMENTAÇÃO PÓS-DISCOVERY DE RPA"
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_font(header.runs[0], 8.5, muted, True)
    footer = section.footer.paragraphs[0]
    footer.text = str(job.get("title") or "Documento de processo")
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_font(footer.runs[0], 8.5, muted)

    kicker = word.add_paragraph()
    kicker.paragraph_format.space_before = Pt(48)
    kicker.paragraph_format.space_after = Pt(8)
    set_font(kicker.add_run("DOCUMENTO DE PROCESSO E REQUISITOS PARA RPA"), 9, teal, True)
    title = word.add_paragraph()
    title.paragraph_format.space_after = Pt(10)
    set_font(title.add_run(str(job.get("title") or "Processo")), 28, navy, True)
    subtitle = word.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(22)
    set_font(subtitle.add_run(f"Público: {job.get('audience') or 'Equipe de RPA'}  |  Nível: {job.get('detail_level') or 'operacional'}"), 10.5, muted)
    lead = word.add_paragraph()
    lead.paragraph_format.space_after = Pt(18)
    set_font(lead.add_run(str(document.get("executive_summary") or "Não identificado na gravação.")), 13, navy)
    note = word.add_paragraph()
    set_font(note.add_run("Este documento consolida o processo demonstrado. A transcrição e os prints são evidências de apoio e permanecem separados no pacote."), 9.5, muted, italic=True)
    word.add_page_break()

    def heading(text: str, level: int = 1):
        return word.add_heading(text, level=level)

    def paragraph(text, bold_label: str = ""):
        item = word.add_paragraph()
        if bold_label:
            set_font(item.add_run(bold_label), 11, navy, True)
        item.add_run(str(text or "Não identificado na gravação."))
        return item

    def bullet_items(items: list, empty: str = "Não identificado na gravação."):
        values = items or [empty]
        for value in values:
            item = word.add_paragraph(style="List Bullet")
            item.paragraph_format.left_indent = Inches(0.375)
            item.paragraph_format.first_line_indent = Inches(-0.188)
            item.paragraph_format.space_after = Pt(4)
            item.paragraph_format.line_spacing = 1.25
            item.add_run(str(value))

    def shade_cell(cell, fill: str):
        shading = OxmlElement("w:shd")
        shading.set(qn("w:fill"), fill)
        cell._tc.get_or_add_tcPr().append(shading)

    def ensure_child(parent, tag: str):
        child = parent.find(qn(tag))
        if child is None:
            child = OxmlElement(tag)
            parent.append(child)
        return child

    def apply_table_geometry(table, widths: list[float]):
        widths_dxa = [int(round(width * 1440)) for width in widths]
        widths_dxa[-1] += 9360 - sum(widths_dxa)
        properties = table._tbl.tblPr
        table_width = ensure_child(properties, "w:tblW")
        table_width.set(qn("w:type"), "dxa")
        table_width.set(qn("w:w"), "9360")
        table_indent = ensure_child(properties, "w:tblInd")
        table_indent.set(qn("w:type"), "dxa")
        table_indent.set(qn("w:w"), "120")
        layout = ensure_child(properties, "w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        grid = table._tbl.tblGrid
        for child in list(grid):
            grid.remove(child)
        for width in widths_dxa:
            grid_column = OxmlElement("w:gridCol")
            grid_column.set(qn("w:w"), str(width))
            grid.append(grid_column)
        for column_index, width in enumerate(widths_dxa):
            table.columns[column_index].width = Twips(width)
            for row in table.rows:
                cell = row.cells[column_index]
                cell.width = Twips(width)
                cell_width = ensure_child(cell._tc.get_or_add_tcPr(), "w:tcW")
                cell_width.set(qn("w:type"), "dxa")
                cell_width.set(qn("w:w"), str(width))
                margins = ensure_child(cell._tc.get_or_add_tcPr(), "w:tcMar")
                for side, value in (("top", 80), ("bottom", 80), ("start", 120), ("end", 120)):
                    margin = ensure_child(margins, f"w:{side}")
                    margin.set(qn("w:type"), "dxa")
                    margin.set(qn("w:w"), str(value))

    def data_table(headers: list[str], rows: list[list], widths: list[float]):
        table = word.add_table(rows=1, cols=len(headers))
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        table.autofit = False
        row_properties = table.rows[0]._tr.get_or_add_trPr()
        repeat_header = OxmlElement("w:tblHeader")
        repeat_header.set(qn("w:val"), "true")
        row_properties.append(repeat_header)
        for index, (header_text, width) in enumerate(zip(headers, widths)):
            cell = table.rows[0].cells[index]
            cell.width = Inches(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            shade_cell(cell, "E8EEF5")
            set_font(cell.paragraphs[0].add_run(header_text), 9.5, navy, True)
        for values in rows:
            cells = table.add_row().cells
            for index, (value, width) in enumerate(zip(values, widths)):
                cells[index].width = Inches(width)
                cells[index].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                set_font(cells[index].paragraphs[0].add_run(str(value or "Não identificado")), 9.5, None)
        apply_table_geometry(table, widths)
        word.add_paragraph().paragraph_format.space_after = Pt(2)
        return table

    heading("1. Objetivo")
    paragraph(document.get("objective"))
    heading("2. Escopo")
    heading("Incluído", 2)
    bullet_items(document.get("scope", {}).get("in_scope", []))
    heading("Fora do escopo", 2)
    bullet_items(document.get("scope", {}).get("out_of_scope", []))
    heading("3. Atores e responsabilidades")
    actor_rows = [[item.get("name"), item.get("responsibility")] for item in document.get("actors", [])] or [["Não identificado", "Validar com a área responsável"]]
    data_table(["Ator", "Responsabilidade"], actor_rows, [1.7, 4.8])
    heading("4. Sistemas envolvidos")
    system_rows = [[item.get("name"), item.get("purpose")] for item in document.get("systems", [])] or [["Não identificado", "Validar durante o refinamento"]]
    data_table(["Sistema", "Finalidade no processo"], system_rows, [1.7, 4.8])
    heading("5. Pré-requisitos")
    bullet_items(document.get("prerequisites", []))
    heading("6. Entradas e saídas")
    heading("Entradas", 2)
    input_rows = [[item.get("name"), item.get("source"), item.get("required")] for item in document.get("inputs", [])] or [["Não identificado", "A validar", "A validar"]]
    data_table(["Entrada", "Origem", "Obrigatoriedade"], input_rows, [2.5, 2.4, 1.6])
    heading("Saídas", 2)
    output_rows = [[item.get("name"), item.get("destination")] for item in document.get("outputs", [])] or [["Não identificado", "A validar"]]
    data_table(["Saída", "Destino"], output_rows, [3.25, 3.25])
    heading("7. Fluxo operacional")
    for index, item in enumerate(document.get("process_flow", []), 1):
        heading(f"{item.get('sequence') or index}. {item.get('title') or 'Etapa'}", 2)
        paragraph(item.get("description"))
        paragraph(item.get("actor"), "Responsável: ")
        paragraph(item.get("system"), "Sistema: ")
        paragraph(item.get("input"), "Entrada: ")
        paragraph(item.get("output"), "Saída: ")
        if item.get("decision_or_exception"):
            paragraph(item.get("decision_or_exception"), "Decisão ou exceção: ")
        refs = ", ".join(str(ref) for ref in item.get("evidence_refs", [])) or "sem referência visual direta"
        evidence = word.add_paragraph()
        set_font(evidence.add_run(f"Evidências: {refs}"), 9, muted, italic=True)
    heading("8. Regras de negócio")
    bullet_items([item.get("rule") for item in document.get("business_rules", []) if item.get("rule")], "Nenhuma regra foi explicitada na gravação.")
    heading("9. Exceções e tratamentos")
    for item in document.get("exceptions", []):
        paragraph(item.get("scenario"), "Cenário: ")
        paragraph(item.get("handling"), "Tratamento: ")
        paragraph(item.get("status"), "Status: ")
    if not document.get("exceptions"):
        paragraph("Nenhuma exceção foi explicitada na gravação.")
    heading("10. Riscos e controles")
    for item in document.get("risks_and_controls", []):
        paragraph(item.get("risk"), "Risco: ")
        paragraph(item.get("impact"), "Impacto: ")
        paragraph(item.get("control"), "Controle: ")
    if not document.get("risks_and_controls"):
        paragraph("Nenhum risco ou controle foi explicitado na gravação.")
    heading("11. Oportunidades de automação")
    for item in document.get("automation_opportunities", []):
        heading(item.get("opportunity") or "Oportunidade", 2)
        paragraph(item.get("benefit"), "Benefício: ")
        paragraph(item.get("dependency"), "Dependência: ")
    if not document.get("automation_opportunities"):
        paragraph("Nenhuma oportunidade foi confirmada com os insumos disponíveis.")
    heading("12. Pontos a validar")
    bullet_items(document.get("open_questions", []), "Nenhum ponto adicional registrado.")
    heading("13. Limitações da análise")
    bullet_items(document.get("limitations", []))
    word.save(workspace / "documentacao-processo.docx")


def write_structured_files(job: dict, document: dict, steps: list[dict], workspace: Path):
    def bullets(items: list, empty: str = "Não identificado na gravação.") -> str:
        return "\n".join(f"- {item}" for item in items) if items else f"- {empty}"

    flow_rows = "\n".join(
        f"| {item.get('sequence', index)} | {markdown_value(item.get('title'))} | {markdown_value(item.get('description'))} | {markdown_value(item.get('actor'))} | {markdown_value(item.get('system'))} |"
        for index, item in enumerate(document.get("process_flow", []), 1)
    ) or "| — | Não identificado | — | — | — |"
    procedure = f'''# Procedimento Operacional — {job.get("title", "Processo")}

## Objetivo

{document.get("objective") or "Não identificado na gravação."}

## Visão geral

{document.get("executive_summary") or "Não identificado na gravação."}

## Pré-requisitos

{bullets(document.get("prerequisites", []))}

## Fluxo operacional

| Etapa | Atividade | Como é realizada | Responsável | Sistema |
|---:|---|---|---|---|
{flow_rows}

## Exceções conhecidas

{bullets([f"**{item.get('scenario', 'Cenário')}** — {item.get('handling') or 'Tratamento não identificado'} ({item.get('status') or 'a validar'})" for item in document.get('exceptions', [])])}

## Pontos a validar

{bullets(document.get("open_questions", []), "Nenhum ponto adicional registrado.")}
'''
    (workspace / "procedimento-operacional.md").write_text(procedure, encoding="utf-8")

    actors = bullets([f"**{item.get('name', 'Não identificado')}** — {item.get('responsibility') or 'Responsabilidade não identificada'}" for item in document.get("actors", [])])
    systems = bullets([f"**{item.get('name', 'Não identificado')}** — {item.get('purpose') or 'Finalidade não identificada'}" for item in document.get("systems", [])])
    rules = bullets([item.get("rule") or "Regra não descrita" for item in document.get("business_rules", [])])
    risks = bullets([f"**Risco:** {item.get('risk') or 'Não identificado'} | **Impacto:** {item.get('impact') or 'Não identificado'} | **Controle:** {item.get('control') or 'Não identificado'}" for item in document.get("risks_and_controls", [])])
    opportunities = bullets([f"**{item.get('opportunity', 'Oportunidade')}** — Benefício: {item.get('benefit') or 'a validar'}; dependência: {item.get('dependency') or 'a validar'}" for item in document.get("automation_opportunities", [])])
    requirements = f'''# Requisitos para RPA — {job.get("title", "Processo")}

## Escopo incluído

{bullets(document.get("scope", {}).get("in_scope", []))}

## Fora do escopo

{bullets(document.get("scope", {}).get("out_of_scope", []))}

## Atores e responsabilidades

{actors}

## Sistemas envolvidos

{systems}

## Regras de negócio

{rules}

## Riscos e controles

{risks}

## Oportunidades de automação

{opportunities}

## Dúvidas e dependências para refinamento

{bullets(document.get("open_questions", []))}
'''
    (workspace / "requisitos-rpa.md").write_text(requirements, encoding="utf-8")
    write_docx_document(job, document, workspace)

    with (workspace / "matriz-evidencias.csv").open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file, delimiter=";")
        writer.writerow(["frame_index", "timecode", "etapa_observada", "sistema", "controle_ou_campo", "evidencia", "incerteza", "arquivo", "fala_relacionada"])
        for step in steps:
            writer.writerow([
                step.get("frame_index", ""), step.get("timecode", ""), step.get("title", ""),
                step.get("system", ""), step.get("field_or_control", ""), step.get("evidence", ""),
                step.get("uncertainty", ""), step.get("image", ""), step.get("transcript", ""),
            ])


def write_report(job: dict, steps: list[dict], workspace: Path, video: Path, document: dict | None = None):
    document = normalize_documentation(document or fallback_documentation(job, steps), job, steps)
    report = {
        "title": job["title"], "source": str(video), "audience": job["audience"],
        "context": job["process_context"], "documentation": document, "evidence_steps": steps,
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    (workspace / "relatorio.json").write_text(serialized, encoding="utf-8")
    (workspace / "documentacao-processo.json").write_text(serialized, encoding="utf-8")
    write_structured_files(job, document, steps, workspace)
    safe = lambda value: escape(str(value or ""))

    def list_html(items: list, empty: str = "Não identificado na gravação.") -> str:
        return f"<ul>{''.join(f'<li>{safe(item)}</li>' for item in items)}</ul>" if items else f'<p class="empty">{safe(empty)}</p>'

    evidence_by_ref = {str(step.get("frame_index")): step for step in steps if step.get("frame_index") is not None}

    def evidence_links(refs: list) -> str:
        links = []
        for ref in refs or []:
            step = evidence_by_ref.get(str(ref))
            if step:
                links.append(f'<a class="evidence-ref" href="#evidence-{safe(ref)}">Evidência {safe(ref)} · {safe(step.get("timecode"))}</a>')
        return "".join(links) or '<span class="not-confirmed">Sem referência visual direta</span>'

    flow_cards = "".join(f'''<article class="flow-step"><b>{safe(item.get('sequence') or index)}</b><div><span>{safe(item.get('actor') or 'Responsável não identificado')} · {safe(item.get('system') or 'Sistema não identificado')}</span><h3>{safe(item.get('title') or 'Etapa')}</h3><p>{safe(item.get('description') or 'Descrição não identificada.')}</p><dl><dt>Entrada</dt><dd>{safe(item.get('input') or 'Não identificada')}</dd><dt>Saída</dt><dd>{safe(item.get('output') or 'Não identificada')}</dd><dt>Decisão ou exceção</dt><dd>{safe(item.get('decision_or_exception') or 'Não identificada')}</dd></dl><footer>{evidence_links(item.get('evidence_refs', []))}</footer></div></article>''' for index, item in enumerate(document.get("process_flow", []), 1))

    input_rows = "".join(f"<tr><td>{safe(item.get('name'))}</td><td>{safe(item.get('source') or 'Não identificada')}</td><td>{safe(item.get('required') or 'A validar')}</td></tr>" for item in document.get("inputs", [])) or '<tr><td colspan="3">Não identificado na gravação.</td></tr>'
    output_rows = "".join(f"<tr><td>{safe(item.get('name'))}</td><td>{safe(item.get('destination') or 'Não identificado')}</td></tr>" for item in document.get("outputs", [])) or '<tr><td colspan="2">Não identificado na gravação.</td></tr>'
    rules = "".join(f"<li><p>{safe(item.get('rule'))}</p>{evidence_links(item.get('evidence_refs', []))}</li>" for item in document.get("business_rules", [])) or '<li class="empty">Nenhuma regra foi explicitada.</li>'
    exceptions = "".join(f"<tr><td>{safe(item.get('scenario'))}</td><td>{safe(item.get('handling') or 'Não identificado')}</td><td>{safe(item.get('status') or 'A validar')}</td></tr>" for item in document.get("exceptions", [])) or '<tr><td colspan="3">Nenhuma exceção foi explicitada.</td></tr>'
    risks = "".join(f"<tr><td>{safe(item.get('risk'))}</td><td>{safe(item.get('impact') or 'Não identificado')}</td><td>{safe(item.get('control') or 'Não identificado')}</td></tr>" for item in document.get("risks_and_controls", [])) or '<tr><td colspan="3">Nenhum risco ou controle foi explicitado.</td></tr>'
    actors = "".join(f"<li><strong>{safe(item.get('name'))}</strong><span>{safe(item.get('responsibility') or 'Responsabilidade não identificada')}</span></li>" for item in document.get("actors", [])) or '<li class="empty">Não identificados.</li>'
    systems = "".join(f"<li><strong>{safe(item.get('name'))}</strong><span>{safe(item.get('purpose') or 'Finalidade não identificada')}</span></li>" for item in document.get("systems", [])) or '<li class="empty">Não identificados.</li>'
    opportunities = "".join(f'''<article class="opportunity"><h3>{safe(item.get('opportunity'))}</h3><p><b>Benefício:</b> {safe(item.get('benefit') or 'A validar')}</p><p><b>Dependência:</b> {safe(item.get('dependency') or 'A validar')}</p></article>''' for item in document.get("automation_opportunities", [])) or '<p class="empty">Nenhuma oportunidade foi confirmada com os insumos disponíveis.</p>'
    evidence_cards = "".join(f'''<article class="evidence-card" id="evidence-{safe(step.get('frame_index') or index)}"><img src="evidence/{safe(step['image'])}" alt="Evidência da etapa"><div><span>{safe(step.get('timecode'))} · {safe(step.get('system') or 'Sistema não identificado')}</span><h3>{safe(step.get('title') or 'Etapa observada')}</h3><p>{safe(step.get('action'))}</p><dl><dt>Controle ou campo</dt><dd>{safe(step.get('field_or_control') or 'Não identificado')}</dd><dt>O que comprova</dt><dd>{safe(step.get('evidence'))}</dd></dl><details><summary>Ver fala relacionada</summary><p>{safe(step.get('transcript') or 'Sem fala detectada neste trecho.')}</p></details></div></article>''' for index, step in enumerate(steps, 1))
    preview = '<section class="preview"><h2>Preview do processo</h2><p>Trechos usados como evidência, preservando o contexto de cada ação.</p><video controls preload="metadata" src="preview-processo.mp4"></video><p><a href="preview-processo.mp4" target="_blank">Abrir preview em nova aba</a> · <a href="preview-processo.mp4" download>Baixar preview</a></p></section>' if (workspace / "preview-processo.mp4").exists() else ""
    html = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{safe(job['title'])}</title><style>:root{{--navy:#102d46;--teal:#168d8a;--ink:#172b3a;--muted:#61798a}}*{{box-sizing:border-box}}body{{font:15px/1.55 Arial;margin:0;background:#f3f5f7;color:var(--ink)}}header{{padding:46px max(5vw,24px);background:var(--navy);color:white}}header p{{max-width:850px}}main{{max-width:1120px;margin:30px auto;padding:0 20px}}section{{margin:22px 0}}.panel{{background:white;padding:24px;border-radius:14px;box-shadow:0 4px 20px #1231}}.summary{{font-size:18px;max-width:900px}}.deliverables{{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}}.deliverables a,.preview a,.evidence-ref{{color:var(--teal);font-weight:bold;text-decoration:none}}.deliverables a{{padding:9px 12px;background:#e8f5f4;border-radius:8px}}.preview{{background:var(--navy);color:white;padding:22px;border-radius:14px}}video{{display:block;width:100%;max-height:620px;margin-top:14px;background:#000;border-radius:9px}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.entity-list{{list-style:none;padding:0}}.entity-list li{{display:flex;flex-direction:column;padding:10px 0;border-bottom:1px solid #e1e8ed}}.flow-step{{display:grid;grid-template-columns:48px 1fr;gap:15px;background:white;margin:12px 0;padding:20px;border-radius:12px;border-left:4px solid var(--teal)}}.flow-step>b{{display:grid;place-items:center;width:38px;height:38px;border-radius:50%;background:var(--navy);color:white}}.flow-step footer{{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}}.evidence-ref{{padding:5px 8px;background:#e8f5f4;border-radius:7px;font-size:12px}}.not-confirmed,.empty{{color:var(--muted);font-style:italic}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:11px;text-align:left;border-bottom:1px solid #dce5eb;vertical-align:top}}th{{background:#eaf0f4}}.rules li{{margin:9px 0}}.opportunities{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}.opportunity{{background:#e8f5f4;padding:16px;border-radius:10px}}.evidence-card{{display:grid;grid-template-columns:42% 1fr;gap:22px;background:white;margin:15px 0;padding:18px;border-radius:14px}}.evidence-card img{{width:100%;border-radius:8px;border:1px solid #ccd4dc}}span,dt{{color:#547086;font-size:12px;font-weight:bold}}h2{{margin-top:0}}h3{{margin:5px 0}}dl{{display:grid;grid-template-columns:150px 1fr;gap:7px 12px}}dd{{margin:0}}details{{margin-top:12px}}@media(max-width:760px){{.columns,.evidence-card{{grid-template-columns:1fr}}.flow-step{{grid-template-columns:38px 1fr}}dl{{grid-template-columns:1fr}}}}</style></head><body><header><small>DOCUMENTAÇÃO ESTRUTURADA PÓS-DISCOVERY DE RPA</small><h1>{safe(job['title'])}</h1><p>Público: {safe(job.get('audience'))} · Nível: {safe(job.get('detail_level'))}</p><nav class="deliverables"><a href="documentacao-processo.docx" download>Documento Word editável</a><a href="procedimento-operacional.md" download>Procedimento operacional</a><a href="requisitos-rpa.md" download>Requisitos para RPA</a><a href="matriz-evidencias.csv" download>Matriz de evidências</a><a href="documentacao-processo.json" download>Dados estruturados</a></nav></header><main><section class="panel"><small>VISÃO GERAL</small><h2>Resumo executivo</h2><p class="summary">{safe(document.get('executive_summary'))}</p><h3>Objetivo</h3><p>{safe(document.get('objective'))}</p></section><section class="columns"><div class="panel"><h2>Escopo incluído</h2>{list_html(document.get('scope', {}).get('in_scope', []))}</div><div class="panel"><h2>Fora do escopo</h2>{list_html(document.get('scope', {}).get('out_of_scope', []))}</div></section><section class="columns"><div class="panel"><h2>Atores e responsabilidades</h2><ul class="entity-list">{actors}</ul></div><div class="panel"><h2>Sistemas envolvidos</h2><ul class="entity-list">{systems}</ul></div></section><section class="panel"><h2>Pré-requisitos</h2>{list_html(document.get('prerequisites', []))}</section><section class="columns"><div class="panel"><h2>Entradas</h2><table><thead><tr><th>Entrada</th><th>Origem</th><th>Obrigatoriedade</th></tr></thead><tbody>{input_rows}</tbody></table></div><div class="panel"><h2>Saídas</h2><table><thead><tr><th>Saída</th><th>Destino</th></tr></thead><tbody>{output_rows}</tbody></table></div></section><section><small>PROCESSO ATUAL</small><h2>Fluxo operacional consolidado</h2>{flow_cards or '<p class="empty">Nenhuma etapa foi identificada.</p>'}</section><section class="panel"><h2>Regras de negócio</h2><ol class="rules">{rules}</ol></section><section class="panel"><h2>Exceções e tratamentos</h2><table><thead><tr><th>Cenário</th><th>Tratamento</th><th>Status</th></tr></thead><tbody>{exceptions}</tbody></table></section><section class="panel"><h2>Riscos e controles</h2><table><thead><tr><th>Risco</th><th>Impacto</th><th>Controle</th></tr></thead><tbody>{risks}</tbody></table></section><section><h2>Oportunidades de automação</h2><div class="opportunities">{opportunities}</div></section><section class="columns"><div class="panel"><h2>Pontos a validar</h2>{list_html(document.get('open_questions', []), 'Nenhum ponto adicional registrado.')}</div><div class="panel"><h2>Limitações desta análise</h2>{list_html(document.get('limitations', []))}</div></section>{preview}<section><small>ANEXO DE COMPROVAÇÃO</small><h2>Matriz visual e falas relacionadas</h2><p>As evidências abaixo sustentam a documentação. Elas não substituem o fluxo consolidado acima.</p>{evidence_cards or '<p>Nenhuma evidência visual foi identificada.</p>'}</section></main></body></html>'''
    (workspace / "relatorio.html").write_text(html, encoding="utf-8")


def process(job: dict, workspace: Path, progress):
    progress(5, "Organizando as gravações recebidas")
    video, source_videos = prepare_source(Path(job["source_path"]), workspace)
    progress(10, f"{len(source_videos)} gravação(ões) pronta(s) para análise")
    evidence = extract_evidence(video, workspace / "evidence")
    progress(35, f"{len(evidence)} evidências visuais capturadas")
    transcript = transcribe(video, workspace)
    progress(60, "Cruzando telas e transcrição")
    steps = analyze(evidence, transcript, workspace, job["process_context"], job["detail_level"])
    progress(72, "Estruturando o processo, regras e requisitos de RPA")
    documentation = synthesize_documentation(job, steps, transcript, workspace)
    progress(80, "Montando o preview com os trechos relevantes")
    preview = create_preview(video, steps, workspace)
    progress(92, "Montando a documentação e o pacote completo")
    write_report(job, steps, workspace, video, documentation)
    create_package(workspace)
    return {"video": str(video), "source_files": [str(item) for item in source_videos], "source_count": len(source_videos), "evidence_count": len(evidence), "transcript_segments": len(transcript), "step_count": len(steps), "process_step_count": len(documentation.get("process_flow", [])), "deliverables": ["relatorio.html", "documentacao-processo.docx", "procedimento-operacional.md", "requisitos-rpa.md", "matriz-evidencias.csv", "documentacao-processo.json", "preview-processo.mp4"], "preview": preview}
