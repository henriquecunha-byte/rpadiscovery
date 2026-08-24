from __future__ import annotations

import base64
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
    included = ["relatorio.html", "relatorio.json", "transcricao.json", "preview-processo.mp4", "transcricao-aviso.txt"]
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in included:
            path = workspace / name
            if path.exists():
                compression = zipfile.ZIP_STORED if path.suffix.lower() == ".mp4" else zipfile.ZIP_DEFLATED
                archive.write(path, arcname=name, compress_type=compression)
        for path in sorted((workspace / "evidence").glob("*.jpg")):
            archive.write(path, arcname=f"evidence/{path.name}", compress_type=zipfile.ZIP_STORED)


def write_report(job: dict, steps: list[dict], workspace: Path, video: Path):
    report = {"title": job["title"], "source": str(video), "audience": job["audience"], "context": job["process_context"], "steps": steps}
    (workspace / "relatorio.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    safe = lambda value: escape(str(value or ""))
    cards = "".join(f'''<article><img src="evidence/{safe(step['image'])}" alt="Evidência da etapa"><div><span>{safe(step['timecode'])} · {safe(step.get('system') or 'Sistema não identificado')}</span><h2>{safe(step.get('title') or 'Etapa')}</h2><p>{safe(step.get('action'))}</p><dl><dt>Controle ou campo</dt><dd>{safe(step.get('field_or_control') or 'Não identificado')}</dd><dt>Evidência</dt><dd>{safe(step.get('evidence'))}</dd><dt>Fala relacionada</dt><dd>{safe(step.get('transcript') or 'Sem fala detectada neste trecho.')}</dd></dl></div></article>''' for step in steps)
    preview = '<section class="preview"><h2>Preview do processo</h2><p>Trechos usados como evidência, preservando o contexto de cada ação.</p><video controls preload="metadata" src="preview-processo.mp4"></video></section>' if (workspace / "preview-processo.mp4").exists() else ""
    html = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{safe(job['title'])}</title><style>body{{font:15px/1.5 Arial;margin:0;background:#f3f5f7;color:#17202a}}header{{padding:42px max(5vw,24px);background:#102d46;color:white}}main{{max-width:1100px;margin:30px auto;padding:0 20px}}.preview{{background:#102d46;color:white;padding:20px;border-radius:14px}}video{{display:block;width:100%;max-height:620px;margin-top:14px;background:#000;border-radius:9px}}article{{display:grid;grid-template-columns:45% 1fr;gap:24px;background:white;margin:18px 0;padding:18px;border-radius:14px;box-shadow:0 4px 20px #1231}}img{{width:100%;border-radius:8px;border:1px solid #ccd4dc}}span,dt{{color:#547086;font-size:12px;font-weight:bold}}h2{{margin:5px 0}}dl{{display:grid;grid-template-columns:130px 1fr;gap:7px 12px}}dd{{margin:0}}@media(max-width:750px){{article{{grid-template-columns:1fr}}}}</style></head><body><header><small>DOCUMENTAÇÃO PÓS-DISCOVERY DE RPA</small><h1>{safe(job['title'])}</h1><p>{safe(job['process_context'])}</p></header><main>{preview}{cards or '<p>Nenhuma etapa foi identificada.</p>'}</main></body></html>'''
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
    progress(78, "Montando o preview com os trechos relevantes")
    preview = create_preview(video, steps, workspace)
    progress(92, "Montando a documentação e o pacote completo")
    write_report(job, steps, workspace, video)
    create_package(workspace)
    return {"video": str(video), "source_files": [str(item) for item in source_videos], "source_count": len(source_videos), "evidence_count": len(evidence), "transcript_segments": len(transcript), "step_count": len(steps), "preview": preview}
