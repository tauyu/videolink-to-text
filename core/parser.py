import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Optional
import yt_dlp

from core.models import VideoMetadata, Chapter

def parse_time_str_to_seconds(time_str: str) -> float:
    """Converts strings like '01:23', '1:23:45', '00:01:23.456' to seconds."""
    parts = time_str.strip().split(":")
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    elif len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0

def extract_chapters_from_text(text: str, total_duration: float) -> List[Chapter]:
    """
    Extract timestamps from description or text.
    Matches lines like:
    00:00 简介
    01:23 第一部分：什么是深度学习
    01:23:45 总结
    """
    if not text:
        return []
    
    pattern = re.compile(r'(?:^|\n)\s*(?:\[|\()?(\d{1,2}:\d{2}(?::\d{2})?)(?:\]|\))?\s*[-–—:]?\s*(.+?)(?=\r?\n|$)', re.MULTILINE)
    matches = pattern.findall(text)
    
    if len(matches) < 2:
        return []

    raw_chapters = []
    for time_str, title in matches:
        title = title.strip()
        sec = parse_time_str_to_seconds(time_str)
        if title:
            raw_chapters.append((sec, title))

    raw_chapters.sort(key=lambda x: x[0])
    
    # Construct Chapter objects with start and end times
    chapters = []
    for i in range(len(raw_chapters)):
        start_sec, title = raw_chapters[i]
        if i + 1 < len(raw_chapters):
            end_sec = raw_chapters[i + 1][0]
        else:
            end_sec = total_duration if total_duration > start_sec else start_sec + 60.0
        
        if end_sec > start_sec:
            chapters.append(Chapter(title=title, start_time=start_sec, end_time=end_sec))

    return chapters

def parse_local_video(file_path: str) -> VideoMetadata:
    p = Path(file_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Use ffprobe to get duration, format, chapters, and streams
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-show_chapters",
        str(p)
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
    except Exception as e:
        # Fallback if ffprobe fails or is not found
        data = {}

    format_info = data.get("format", {})
    duration = float(format_info.get("duration", 0.0))
    title = p.stem
    tags = format_info.get("tags", {})
    if "title" in tags:
        title = tags["title"]

    # Check for embedded subtitle streams
    streams = data.get("streams", [])
    has_subtitles = any(s.get("codec_type") == "subtitle" for s in streams)

    # Check chapters
    raw_chapters = data.get("chapters", [])
    chapters = []
    for ch in raw_chapters:
        ch_title = ch.get("tags", {}).get("title", f"Chapter {ch.get('id', '')}")
        start_t = float(ch.get("start_time", 0.0))
        end_t = float(ch.get("end_time", duration))
        chapters.append(Chapter(title=ch_title, start_time=start_t, end_time=end_t))

    return VideoMetadata(
        id=p.stem,
        title=title,
        source_url_or_path=str(p),
        source_type="local",
        duration=duration,
        chapters=chapters,
        has_subtitles=has_subtitles,
        description=""
    )

def parse_online_video(url: str, cache_dir: Path) -> VideoMetadata:
    source_type = "youtube" if "youtu" in url.lower() else ("bilibili" if "bilibili" in url.lower() else "online")
    
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError(f"Failed to fetch metadata for URL: {url}")

    title = info.get("title", "Untitled")
    duration = float(info.get("duration", 0.0) or 0.0)
    video_id = info.get("id", "video")
    thumbnail = info.get("thumbnail")
    description = info.get("description", "")

    # Extract chapters from yt-dlp metadata
    chapters = []
    raw_chapters = info.get("chapters") or []
    if raw_chapters:
        for ch in raw_chapters:
            chapters.append(Chapter(
                title=ch.get("title", "Segment"),
                start_time=float(ch.get("start_time", 0.0)),
                end_time=float(ch.get("end_time", duration))
            ))
    else:
        # If no built-in chapters, try parsing timestamps from description
        chapters = extract_chapters_from_text(description, duration)

    # Check for subtitles (both manual and auto-captions)
    subs = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}
    
    # Priority for Chinese/English subtitles
    preferred_langs = ["zh-Hans", "zh-CN", "zh", "zh-TW", "zh-Hant", "en"]
    detected_lang = None
    has_subtitles = False

    for lang in preferred_langs:
        if lang in subs:
            detected_lang = lang
            has_subtitles = True
            break
    if not has_subtitles:
        for lang in preferred_langs:
            if lang in auto_subs:
                detected_lang = lang
                has_subtitles = True
                break
    if not has_subtitles and (subs or auto_subs):
        # Pick the first available
        all_langs = list(subs.keys()) + list(auto_subs.keys())
        if all_langs:
            detected_lang = all_langs[0]
            has_subtitles = True

    return VideoMetadata(
        id=video_id,
        title=title,
        source_url_or_path=url,
        source_type=source_type,
        duration=duration,
        thumbnail=thumbnail,
        chapters=chapters,
        has_subtitles=has_subtitles,
        subtitle_lang=detected_lang,
        description=description
    )

def parse_video_source(source: str, cache_dir: Path) -> VideoMetadata:
    """Entrypoint to parse either a local file or online URL."""
    s = source.strip().strip('"').strip("'")
    if os.path.exists(s) or Path(s).is_file():
        return parse_local_video(s)
    elif s.startswith("http://") or s.startswith("https://"):
        return parse_online_video(s, cache_dir)
    else:
        # Try checking if it's a relative path
        local_p = Path(s).resolve()
        if local_p.exists():
            return parse_local_video(str(local_p))
        raise ValueError(f"Invalid input: '{source}' is neither an existing file nor a valid URL.")
