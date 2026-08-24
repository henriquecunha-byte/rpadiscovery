from pathlib import Path
import os
import shutil

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA_DIR = ROOT / "data"
JOBS_DIR = ROOT / "jobs"
CACHE_DIR = ROOT / "cache"
STATIC_DIR = Path(__file__).resolve().parent / "static"
DATABASE = DATA_DIR / "rpa_docs.sqlite3"
for directory in (DATA_DIR, JOBS_DIR, CACHE_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def executable(name: str, environment_name: str) -> str:
    configured = os.getenv(environment_name, "").strip()
    winget_link = Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / f"{name}.exe"
    try:
        winget_available = winget_link.exists()
    except OSError:
        winget_available = False
    discovered = configured or shutil.which(name) or (str(winget_link) if winget_available else name)
    path = Path(discovered)
    try:
        return str(path.resolve(strict=True))
    except (OSError, RuntimeError):
        return discovered


FFMPEG = executable("ffmpeg", "FFMPEG_PATH")
FFPROBE = executable("ffprobe", "FFPROBE_PATH")
