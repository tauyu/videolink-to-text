import os
import subprocess
from pathlib import Path
from typing import Callable, Optional
import yt_dlp

from core.models import VideoMetadata

def extract_audio_from_local(file_path: str, output_wav: Path) -> Path:
    """Extracts 16kHz mono WAV audio from local video file using ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-i", file_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_wav)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    if not output_wav.exists() or output_wav.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg failed to extract audio to {output_wav}")
    return output_wav

def download_audio_from_online(
    url: str,
    output_wav: Path,
    cache_dir: Path,
    on_progress: Optional[Callable[[float, str], None]] = None
) -> Path:
    """Downloads audio-only stream from YouTube/Bilibili and converts to 16kHz mono WAV."""
    temp_base = cache_dir / f"download_{output_wav.stem}"

    def ydl_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total) * 100
            speed = d.get('_speed_str', '')
            if on_progress:
                on_progress(percent, f"下载音频中: {percent:.1f}% ({speed})")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(temp_base) + '.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'postprocessor_args': [
            '-ar', '16000',
            '-ac', '1',
        ],
        'progress_hooks': [ydl_hook],
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Find the resulting wav file
    expected_wav = temp_base.with_suffix(".wav")
    if expected_wav.exists():
        if expected_wav != output_wav:
            expected_wav.replace(output_wav)
        return output_wav
    
    # Check if another extension was generated
    for f in cache_dir.glob(f"download_{output_wav.stem}.*"):
        if f.suffix.lower() == ".wav":
            f.replace(output_wav)
            return output_wav

    raise RuntimeError("Audio download/conversion failed, output wav file not found.")

def extract_or_download_audio(
    metadata: VideoMetadata,
    cache_dir: Path,
    on_progress: Optional[Callable[[float, str], None]] = None
) -> Path:
    """Entrypoint to extract audio into cache_dir as 16kHz mono WAV."""
    output_wav = cache_dir / f"audio_{metadata.id}.wav"
    if output_wav.exists() and output_wav.stat().st_size > 0:
        return output_wav

    if metadata.source_type == "local":
        if on_progress:
            on_progress(10.0, "正在提取本地视频音轨...")
        return extract_audio_from_local(metadata.source_url_or_path, output_wav)
    else:
        if on_progress:
            on_progress(5.0, "正在连接并拉取在线音频流...")
        return download_audio_from_online(metadata.source_url_or_path, output_wav, cache_dir, on_progress)
