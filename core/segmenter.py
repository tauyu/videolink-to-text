from typing import List
from core.models import Chapter, SubtitleSegment, ChapterSection

def format_timestamp(seconds: float) -> str:
    """Formats seconds into MM:SS or HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

import re

def clean_chinese_text(text: str) -> str:
    """Removes unnatural spaces between Chinese characters while keeping English word spaces."""
    # Remove space between Chinese and Chinese
    text = re.sub(r'([\u4e00-\u9fa5])\s+([\u4e00-\u9fa5])', r'\1\2', text)
    # Remove space before Chinese punctuation
    text = re.sub(r'\s+([，。！？；：、“”‘’（）《》])', r'\1', text)
    return text.strip()

def join_segments_natively(seg_texts: List[str]) -> str:
    """
    Intelligently joins text segments:
    - If the previous segment lacks punctuation and both are Chinese, joins with a comma '，' instead of a space.
    - If ends with punctuation, joins seamlessly without redundant spaces.
    """
    if not seg_texts:
        return ""

    punct_endings = (',', '.', '!', '?', ';', ':', '，', '。', '！', '？', '；', '：', '…', '、')
    res = ""

    for s in seg_texts:
        s = clean_chinese_text(s)
        if not s:
            continue
        if not res:
            res = s
        else:
            prev_char = res[-1]
            first_char = s[0]
            is_prev_zh = '\u4e00' <= prev_char <= '\u9fa5'
            is_next_zh = '\u4e00' <= first_char <= '\u9fa5'

            if prev_char in punct_endings:
                # Ended with punctuation
                res += ("" if is_next_zh else " ") + s
            else:
                # Lacked punctuation at segment break
                if is_prev_zh and is_next_zh:
                    res += "，" + s
                else:
                    res += " " + s

    # Ensure ending with period if it ends like a completed paragraph without punctuation
    if res and res[-1] not in punct_endings and ('\u4e00' <= res[-1] <= '\u9fa5'):
        res += "。"

    return res

def merge_segments_to_paragraphs(segments: List[SubtitleSegment], max_chars: int = 250) -> str:
    """
    Merges subtitle segments into natural, readable paragraphs.
    Breaks paragraphs when sentences end with full stops or after a certain length.
    """
    if not segments:
        return ""

    paragraphs = []
    current_para = []
    current_len = 0

    sentence_endings = ('.', '!', '?', '。', '！', '？', '…')

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        current_para.append(text)
        current_len += len(text)

        # Break paragraph if it ends with punctuation and has accumulated enough characters
        if current_len >= max_chars and text.endswith(sentence_endings):
            paragraphs.append(join_segments_natively(current_para))
            current_para = []
            current_len = 0
        elif current_len >= max_chars * 1.5:
            paragraphs.append(join_segments_natively(current_para))
            current_para = []
            current_len = 0

    if current_para:
        paragraphs.append(join_segments_natively(current_para))

    return "\n\n".join(paragraphs)

DISCOURSE_MARKERS = re.compile(
    r'^(首先|第一点|第一个|第一方面|第一部分|第一节|第一章|'
    r'其次|第二点|第二个|第二方面|第二部分|第二节|第二章|'
    r'再次|第三点|第三个|第三方面|第三部分|第三节|第三章|'
    r'最后|第四点|第四个|第四方面|第四部分|'
    r'接下来|下面我们要讲|接下来我们来看|下面我们来看|紧接着|'
    r'总结一下|总的来说|综上所述|最后总结)'
)

def detect_content_chapters(segments: List[SubtitleSegment], min_interval: float = 75.0) -> List[Chapter]:
    """
    Attempts to detect natural topic transitions based on speech pauses and discourse markers.
    If high-confidence transitions are found (>= 2), returns detected chapters.
    Otherwise returns empty list, meaning the content should NOT be artificially split.
    """
    if not segments or len(segments) < 8:
        return []

    split_points = []
    last_split_time = 0.0

    for i in range(1, len(segments)):
        seg = segments[i]
        prev_seg = segments[i - 1]
        pause = seg.start - prev_seg.end

        # Must have at least min_interval seconds since last split to avoid over-segmentation
        if (seg.start - last_split_time) < min_interval:
            continue

        clean_text = clean_chinese_text(seg.text)
        m = DISCOURSE_MARKERS.match(clean_text)

        # Transition condition: clear discourse marker or significant speech pause (>= 3.0s)
        if m:
            title = clean_text[:28].rstrip('，。！？；： ')
            split_points.append((seg.start, title))
            last_split_time = seg.start
        elif pause >= 3.0 and len(clean_text) >= 6:
            title = clean_text[:28].rstrip('，。！？；： ')
            split_points.append((seg.start, title))
            last_split_time = seg.start

    # Only return chapters if we found meaningful transitions (at least 2 transition points)
    if len(split_points) < 2:
        return []

    chapters: List[Chapter] = []
    total_end = segments[-1].end

    # First section from 0 to first split
    first_split_time, _ = split_points[0]
    if first_split_time > 0:
        chapters.append(Chapter(
            title="开篇引言",
            start_time=0.0,
            end_time=first_split_time
        ))

    for idx, (t, title) in enumerate(split_points):
        next_t = split_points[idx + 1][0] if idx + 1 < len(split_points) else total_end
        chapters.append(Chapter(
            title=title,
            start_time=t,
            end_time=next_t
        ))

    return chapters

def segment_text_by_chapters(
    segments: List[SubtitleSegment],
    chapters: List[Chapter],
    total_duration: float
) -> List[ChapterSection]:
    """
    Aligns subtitle segments to video chapters.
    If no chapters exist, tries content-based topic detection.
    If no topic transition can be confidently identified, keeps as a single coherent text without artificial splitting.
    """
    if not segments:
        return []

    # If no author chapters provided, try detecting content-based topic shifts
    if not chapters:
        detected = detect_content_chapters(segments)
        if detected:
            chapters = detected
        else:
            # Do NOT segment mechanically by time. Return as a single complete text section!
            total_end = total_duration if total_duration > 0 else segments[-1].end
            return [
                ChapterSection(
                    title="转录全文",
                    start_time=0.0,
                    end_time=total_end,
                    text=merge_segments_to_paragraphs(segments),
                    segments=segments
                )
            ]

    sections: List[ChapterSection] = []

    for ch in chapters:
        # Collect all segments whose midpoint or start falls in [ch.start_time, ch.end_time]
        matched_segs = [
            s for s in segments
            if (ch.start_time <= s.start < ch.end_time) or
               (ch.start_time <= (s.start + s.end) / 2 < ch.end_time)
        ]

        para_text = merge_segments_to_paragraphs(matched_segs)
        sections.append(ChapterSection(
            title=ch.title,
            start_time=ch.start_time,
            end_time=ch.end_time,
            text=para_text,
            segments=matched_segs
        ))

    return sections
