import re
from pathlib import Path
from typing import Dict, List
from core.models import TranscriptionResult, SubtitleSegment
from core.segmenter import format_timestamp

def sanitize_filename(name: str) -> str:
    """Removes illegal characters from filename on Windows."""
    clean = re.sub(r'[\\/*?:"<>|]', '_', name)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:120] if clean else "transcript"

def format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def generate_srt(segments: List[SubtitleSegment]) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_srt_time(seg.start)} --> {format_srt_time(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)

def generate_markdown(result: TranscriptionResult) -> str:
    meta = result.metadata
    lines = [
        f"# {meta.title}",
        "",
        f"- **视频来源**：{meta.source_url_or_path}",
        f"- **总时长**：{format_timestamp(meta.duration)}",
        f"- **转录方式**：{'原片字幕提取' if result.method == 'subtitle' else '语音听写识别 (ASR)'}",
        "",
    ]

    # If multiple chapters exist, output table of contents and subheadings
    if len(result.sections) > 1:
        lines.append("## 目录导览")
        lines.append("")
        for sec in result.sections:
            lines.append(f"- [{format_timestamp(sec.start_time)}] {sec.title}")
        lines.extend(["", "---", ""])

        for sec in result.sections:
            start_str = format_timestamp(sec.start_time)
            end_str = format_timestamp(sec.end_time)
            lines.append(f"### {sec.title} ({start_str} - {end_str})")
            lines.append("")
            if sec.text.strip():
                lines.append(sec.text.strip())
            else:
                lines.append("*(该时间段无对白或文本)*")
            lines.extend(["", ""])
    else:
        lines.extend(["---", "", "## 转录全文", ""])
        single_text = result.sections[0].text.strip() if result.sections else ""
        lines.append(single_text if single_text else "*(该视频无对白或文本)*")
        lines.append("")

    return "\n".join(lines)

def generate_txt(result: TranscriptionResult) -> str:
    meta = result.metadata
    lines = [
        f"【视频标题】{meta.title}",
        f"【来源】{meta.source_url_or_path}",
        f"【时长】{format_timestamp(meta.duration)}",
        "=" * 50,
        ""
    ]

    if len(result.sections) > 1:
        for sec in result.sections:
            start_str = format_timestamp(sec.start_time)
            end_str = format_timestamp(sec.end_time)
            lines.append(f"[{start_str} - {end_str}] {sec.title}")
            lines.append("-" * 40)
            lines.append(sec.text.strip() or "(无对白)")
            lines.extend(["", ""])
    else:
        single_text = result.sections[0].text.strip() if result.sections else ""
        lines.append(single_text or "(无对白)")
        lines.append("")

    return "\n".join(lines)

from core.segmenter import format_timestamp, clean_chinese_text

def generate_timeline_transcript(result: TranscriptionResult) -> str:
    """
    Generates a sentence-by-sentence transcript with timestamps (带时间轴的逐句稿).
    Format:
    [00:01:23] 句子内容
    """
    meta = result.metadata
    lines = [
        f"【视频标题】{meta.title}",
        f"【来源】{meta.source_url_or_path}",
        f"【时长】{format_timestamp(meta.duration)}",
        f"【类型】时间轴逐句对照稿",
        "=" * 50,
        ""
    ]

    if len(result.sections) > 1:
        for sec in result.sections:
            start_str = format_timestamp(sec.start_time)
            end_str = format_timestamp(sec.end_time)
            lines.append(f"### {sec.title} ({start_str} - {end_str})")
            lines.append("-" * 40)
            if sec.segments:
                for seg in sec.segments:
                    text = clean_chinese_text(seg.text)
                    if text:
                        lines.append(f"[{format_timestamp(seg.start)}] {text}")
            else:
                lines.append(sec.text.strip() or "(无对白)")
            lines.extend(["", ""])
    else:
        all_segs = []
        for sec in result.sections:
            all_segs.extend(sec.segments)
        for seg in all_segs:
            text = clean_chinese_text(seg.text)
            if text:
                lines.append(f"[{format_timestamp(seg.start)}] {text}")
        lines.append("")

    return "\n".join(lines)

def export_all_formats(
    result: TranscriptionResult,
    output_dir: Path,
    export_timeline: bool = False
) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_filename(result.metadata.title)

    md_path = output_dir / f"{base_name}.md"
    txt_path = output_dir / f"{base_name}.txt"
    srt_path = output_dir / f"{base_name}.srt"

    md_content = generate_markdown(result)
    txt_content = generate_txt(result)
    
    # Collect all segments
    all_segs = []
    for sec in result.sections:
        all_segs.extend(sec.segments)
    srt_content = generate_srt(all_segs)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt_content)

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    outputs = {
        "md": md_path,
        "txt": txt_path,
        "srt": srt_path
    }

    if export_timeline:
        timeline_path = output_dir / f"{base_name}_时间轴逐句稿.txt"
        timeline_content = generate_timeline_transcript(result)
        with open(timeline_path, "w", encoding="utf-8") as f:
            f.write(timeline_content)
        outputs["timeline"] = timeline_path

    return outputs
