from typing import List, Optional
from pydantic import BaseModel

class Chapter(BaseModel):
    title: str
    start_time: float
    end_time: float

class SubtitleSegment(BaseModel):
    start: float
    end: float
    text: str

class VideoMetadata(BaseModel):
    id: str
    title: str
    source_url_or_path: str
    source_type: str  # 'youtube', 'bilibili', 'local'
    duration: float = 0.0
    thumbnail: Optional[str] = None
    chapters: List[Chapter] = []
    has_subtitles: bool = False
    subtitle_lang: Optional[str] = None
    description: Optional[str] = None

class ChapterSection(BaseModel):
    title: str
    start_time: float
    end_time: float
    text: str
    segments: List[SubtitleSegment] = []

class TranscriptionResult(BaseModel):
    metadata: VideoMetadata
    method: str  # "subtitle" or "asr"
    sections: List[ChapterSection]
    full_text: str
    markdown: str
    srt: str
