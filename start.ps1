$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    throw "Execute .\setup.ps1 antes de iniciar."
}

if (-not $env:FFMPEG_PATH) {
    $ffmpegLink = Get-Item -LiteralPath "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ffmpeg.exe" -ErrorAction SilentlyContinue
    if ($ffmpegLink -and $ffmpegLink.Target) { $env:FFMPEG_PATH = $ffmpegLink.Target }
}
if (-not $env:FFPROBE_PATH) {
    $ffprobeLink = Get-Item -LiteralPath "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ffprobe.exe" -ErrorAction SilentlyContinue
    if ($ffprobeLink -and $ffprobeLink.Target) { $env:FFPROBE_PATH = $ffprobeLink.Target }
}

Start-Process "http://127.0.0.1:8770"
& ".\.venv\Scripts\python.exe" run_app.py
