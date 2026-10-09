import os
import re
import glob
import subprocess
from pathlib import Path
from typing import List, Optional
import webvtt
import yt_dlp

from core.models import VideoMetadata, SubtitleSegment

def clean_vtt_text(text: str) -> str:
    """Removes HTML-like tags (e.g. <c>, </c>, <v Speaker>) and duplicate spaces."""
    cleaned = re.sub(r'<[^>]+>', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def parse_vtt_or_srt(file_path: Path) -> List[SubtitleSegment]:
    segments = []
    try:
        # webvtt can parse VTT files
        for caption in webvtt.read(str(file_path)):
            text = clean_vtt_text(caption.text)
            if not text:
                continue
            # Parse start and end times
            start = caption.start_in_seconds
            end = caption.end_in_seconds
            segments.append(SubtitleSegment(start=start, end=end, text=text))
    except Exception as e:
        # Fallback basic srt/vtt parser if webvtt fails
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        
        time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})')
        cur_start, cur_end = None, None
        cur_text = []

        def to_sec(ts):
            ts = ts.replace(',', '.')
            h, m, s = ts.split(':')
            return int(h) * 3600 + int(m) * 60 + float(s)

        for line in lines:
            line = line.strip()
            match = time_pattern.search(line)
            if match:
                if cur_start is not None and cur_text:
                    txt = clean_vtt_text(" ".join(cur_text))
                    if txt:
                        segments.append(SubtitleSegment(start=cur_start, end=cur_end, text=txt))
                cur_start = to_sec(match.group(1))
                cur_end = to_sec(match.group(2))
                cur_text = []
            elif cur_start is not None and line and not line.isdigit():
                cur_text.append(line)

        if cur_start is not None and cur_text:
            txt = clean_vtt_text(" ".join(cur_text))
            if txt:
                segments.append(SubtitleSegment(start=cur_start, end=cur_end, text=txt))

    # Deduplicate consecutive identical segments (common in YouTube auto captions)
    deduped = []
    for seg in segments:
        if deduped and deduped[-1].text == seg.text:
            # Extend end time
            deduped[-1].end = max(deduped[-1].end, seg.end)
        else:
            deduped.append(seg)
    return deduped

def extract_online_subtitles(url: str, metadata: VideoMetadata, cache_dir: Path) -> Optional[List[SubtitleSegment]]:
    """Downloads subtitles for YouTube/Bilibili using yt-dlp without downloading video."""
    sub_lang = metadata.subtitle_lang or "zh-Hans,zh,en"
    output_template = str(cache_dir / f"sub_{metadata.id}.%(ext)s")

    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': [lang.strip() for lang in sub_lang.split(',')],
        'subtitlesformat': 'vtt/srt/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except Exception as e:
            print(f"[Subtitle] yt-dlp subtitle download failed: {e}")
            return None

    # Search for downloaded subtitle file in cache_dir
    found_files = list(cache_dir.glob(f"sub_{metadata.id}.*"))
    valid_sub_files = [f for f in found_files if f.suffix.lower() in [".vtt", ".srt"]]
    
    if not valid_sub_files:
        return None

    sub_file = valid_sub_files[0]
    try:
        segments = parse_vtt_or_srt(sub_file)
        return segments
    finally:
        # Clean up temporary subtitle files
        for f in found_files:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

def extract_local_subtitles(file_path: str, metadata: VideoMetadata, cache_dir: Path) -> Optional[List[SubtitleSegment]]:
    """Extracts soft subtitle track from local video container."""
    output_srt = cache_dir / f"local_sub_{metadata.id}.srt"
    cmd = [
        "ffmpeg", "-y",
        "-i", file_path,
        "-map", "0:s:0",
        "-c:s", "srt",
        str(output_srt)
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if output_srt.exists() and output_srt.stat().st_size > 0:
            segments = parse_vtt_or_srt(output_srt)
            return segments
    except Exception as e:
        print(f"[Subtitle] No soft subtitle extracted from local file: {e}")
    finally:
        output_srt.unlink(missing_ok=True)
    return None

def extract_subtitles(metadata: VideoMetadata, cache_dir: Path) -> Optional[List[SubtitleSegment]]:
    if not metadata.has_subtitles:
        return None
    
    if metadata.source_type == "local":
        return extract_local_subtitles(metadata.source_url_or_path, metadata, cache_dir)
    else:
        return extract_online_subtitles(metadata.source_url_or_path, metadata, cache_dir)
