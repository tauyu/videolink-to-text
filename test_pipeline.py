import os
import subprocess
from pathlib import Path
from config import apply_environment_isolation, load_config
from core.models import VideoMetadata, Chapter, SubtitleSegment, TranscriptionResult
from core.segmenter import segment_text_by_chapters
from core.exporter import export_all_formats

def test_full_pipeline():
    cfg = apply_environment_isolation()
    test_output_dir = cfg.get_cache_dir() / "test_outputs"
    test_output_dir.mkdir(parents=True, exist_ok=True)

    print("--- [1] Testing Video Chapter Parsing & Alignment ---")
    mock_chapters = [
        Chapter(title="第一部分：导论与背景", start_time=0.0, end_time=15.0),
        Chapter(title="第二部分：核心概念解析", start_time=15.0, end_time=30.0)
    ]

    mock_segments = [
        SubtitleSegment(start=1.0, end=4.5, text="欢迎大家收看本期视频，今天我们来深入探讨大模型。"),
        SubtitleSegment(start=5.0, end=10.0, text="在过去的两年中，Transformer 架构彻底改变了人工智能的发展路线。"),
        SubtitleSegment(start=16.0, end=20.0, text="首先我们来看第一条核心概念：自注意力机制。"),
        SubtitleSegment(start=21.0, end=28.0, text="所谓 Self-Attention，本质上是计算序列内每一个 token 与其他 token 的相关度权重。")
    ]

    meta = VideoMetadata(
        id="test_demo_01",
        title="测试视频：AI核心技术深度拆解",
        source_url_or_path="https://www.bilibili.com/video/BVdemo123",
        source_type="bilibili",
        duration=30.0,
        chapters=mock_chapters,
        has_subtitles=True
    )

    sections = segment_text_by_chapters(mock_segments, mock_chapters, 30.0)
    assert len(sections) == 2, f"Expected 2 sections, got {len(sections)}"
    print(f"Sections created: {len(sections)}")
    for s in sections:
        print(f"  - [{s.start_time} - {s.end_time}] {s.title}: {s.text[:30]}...")

    print("\n--- [2] Testing Exporters (Markdown, TXT, SRT) ---")
    result = TranscriptionResult(
        metadata=meta,
        method="subtitle",
        sections=sections,
        full_text="\n\n".join([s.text for s in sections]),
        markdown="",
        srt=""
    )

    exported = export_all_formats(result, test_output_dir)
    print("Exported files:")
    for k, v in exported.items():
        print(f"  {k}: {v} (Exists: {v.exists()}, Size: {v.stat().st_size} bytes)")
        assert v.exists() and v.stat().st_size > 0, f"File {v} should exist and have content"

    # Read markdown content
    md_content = exported["md"].read_text(encoding="utf-8")
    print("\n--- [3] Markdown Preview Sample ---")
    print(md_content[:400] + "...\n")

    print("ALL PIPELINE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_full_pipeline()
