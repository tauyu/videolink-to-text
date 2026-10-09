import asyncio
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Callable
from pydantic import BaseModel

from config import AppConfig, load_config
from core.models import VideoMetadata, TranscriptionResult, SubtitleSegment
from core.parser import parse_video_source
from core.subtitle import extract_subtitles
from core.audio import extract_or_download_audio
from core.asr import transcribe_audio
from core.segmenter import segment_text_by_chapters
from core.exporter import export_all_formats, generate_markdown, generate_srt

class TaskItem(BaseModel):
    id: str
    source: str
    title: str = "等待解析..."
    source_type: str = "unknown"
    duration: float = 0.0
    status: str = "queued"  # queued, parsing, extracting_sub, transcribing_asr, formatting, completed, error
    progress: float = 0.0
    step_desc: str = "队列排队中"
    error_message: Optional[str] = None
    created_at: float = 0.0
    completed_at: Optional[float] = None
    output_files: Dict[str, str] = {}
    markdown_content: Optional[str] = None

class QueueManager:
    def __init__(self):
        self.tasks: Dict[str, TaskItem] = {}
        self.task_order: List[str] = []
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = True
        self._listeners: List[Callable[[dict], None]] = []
        
        # Start background worker loop
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def add_listener(self, callback: Callable[[dict], None]):
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[dict], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def broadcast_event(self, event_type: str, data: dict):
        msg = {"type": event_type, "data": data}
        for cb in list(self._listeners):
            try:
                cb(msg)
            except Exception:
                pass

    def add_task(self, source: str) -> TaskItem:
        task_id = str(uuid.uuid4())[:8]
        source_clean = source.strip().strip('"').strip("'")
        
        # Detect basic type
        src_type = "local" if (not source_clean.startswith("http://") and not source_clean.startswith("https://")) else (
            "bilibili" if "bilibili" in source_clean else ("youtube" if "youtu" in source_clean else "online")
        )

        task = TaskItem(
            id=task_id,
            source=source_clean,
            title=Path(source_clean).stem if src_type == "local" else source_clean,
            source_type=src_type,
            status="queued",
            progress=0.0,
            step_desc="排队中...",
            created_at=time.time()
        )

        with self._lock:
            self.tasks[task_id] = task
            self.task_order.append(task_id)

        self.broadcast_event("task_added", task.model_dump())
        return task

    def add_batch(self, sources: List[str]) -> List[TaskItem]:
        created = []
        for s in sources:
            if s.strip():
                created.append(self.add_task(s.strip()))
        return created

    def get_all_tasks(self) -> List[TaskItem]:
        with self._lock:
            return [self.tasks[tid] for tid in self.task_order if tid in self.tasks]

    def get_task(self, task_id: str) -> Optional[TaskItem]:
        with self._lock:
            return self.tasks.get(task_id)

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                if task_id in self.task_order:
                    self.task_order.remove(task_id)
                self.broadcast_event("task_deleted", {"id": task_id})
                return True
        return False

    def clear_completed(self):
        with self._lock:
            to_remove = [tid for tid in self.task_order if self.tasks[tid].status in ("completed", "error")]
            for tid in to_remove:
                del self.tasks[tid]
                self.task_order.remove(tid)
        self.broadcast_event("queue_cleared", {})

    def _update_task(self, task_id: str, **kwargs):
        dump = None
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                for k, v in kwargs.items():
                    setattr(task, k, v)
                dump = task.model_dump()
        if dump is not None:
            self.broadcast_event("task_updated", dump)

    def _worker_loop(self):
        while self._running:
            # Pick next queued task
            next_task_id = None
            with self._lock:
                for tid in self.task_order:
                    if self.tasks[tid].status == "queued":
                        next_task_id = tid
                        break

            if next_task_id:
                self._process_task(next_task_id)
            else:
                time.sleep(1.0)

    def _process_task(self, task_id: str):
        cfg = load_config()
        cache_dir = cfg.get_cache_dir()
        model_dir = cfg.get_model_dir()
        output_dir = cfg.get_output_dir()

        task = self.get_task(task_id)
        if not task:
            return

        temp_audio_path: Optional[Path] = None

        try:
            # Step 1: Parse metadata & chapters
            self._update_task(task_id, status="parsing", progress=5.0, step_desc="正在解析视频元数据与章节...")
            meta = parse_video_source(task.source, cache_dir)
            self._update_task(
                task_id,
                title=meta.title,
                duration=meta.duration,
                source_type=meta.source_type,
                progress=15.0
            )

            segments: Optional[List[SubtitleSegment]] = None
            method = "subtitle"

            # Step 2: Try extracting platform/container soft subtitles
            if meta.has_subtitles:
                self._update_task(task_id, status="extracting_sub", progress=25.0, step_desc="检测到原片字幕，正在直接拉取...")
                segments = extract_subtitles(meta, cache_dir)
                if segments:
                    self._update_task(task_id, progress=60.0, step_desc=f"已成功拉取 {len(segments)} 条原生字幕")

            # Step 3: If no subtitles or extraction failed, fallback to ASR transcription
            if not segments:
                method = "asr"
                self._update_task(task_id, status="transcribing_asr", progress=30.0, step_desc="无字幕轨，正在准备抽音听写...")
                
                # Audio extraction
                def on_audio_progress(pct, desc):
                    overall = 30.0 + (pct * 0.15)  # 30% to 45%
                    self._update_task(task_id, progress=overall, step_desc=desc)

                temp_audio_path = extract_or_download_audio(meta, cache_dir, on_progress=on_audio_progress)

                # Faster-Whisper ASR
                def on_asr_progress(pct, desc):
                    overall = 45.0 + (pct * 0.45)  # 45% to 90%
                    self._update_task(task_id, progress=overall, step_desc=desc)

                segments = transcribe_audio(
                    audio_path=temp_audio_path,
                    duration=meta.duration,
                    model_size=cfg.model_size,
                    model_dir=model_dir,
                    device=cfg.device,
                    compute_type=cfg.compute_type,
                    on_progress=on_asr_progress
                )

            # Step 4: Video segmentation & formatting
            self._update_task(task_id, status="formatting", progress=92.0, step_desc="正在根据章节分段聚类文本...")
            sections = segment_text_by_chapters(segments, meta.chapters, meta.duration)

            # Generate full texts
            full_text = "\n\n".join([sec.text for sec in sections if sec.text])
            result = TranscriptionResult(
                metadata=meta,
                method=method,
                sections=sections,
                full_text=full_text,
                markdown="",
                srt=""
            )
            result.markdown = generate_markdown(result)
            all_segs = []
            for sec in sections:
                all_segs.extend(sec.segments)
            result.srt = generate_srt(all_segs)

            # Step 5: Export all formats
            self._update_task(task_id, progress=97.0, step_desc="正在导出结果文件到指定目录...")
            exported = export_all_formats(result, output_dir, export_timeline=cfg.export_timeline_transcript)

            # Completed!
            self._update_task(
                task_id,
                status="completed",
                progress=100.0,
                step_desc=f"已完成 ({'原片字幕' if method == 'subtitle' else 'ASR听写'})",
                completed_at=time.time(),
                output_files={k: str(v) for k, v in exported.items()},
                markdown_content=result.markdown
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._update_task(
                task_id,
                status="error",
                error_message=str(e),
                step_desc=f"处理失败: {str(e)[:100]}"
            )
        finally:
            # Clean up temporary audio file in cache
            if temp_audio_path and temp_audio_path.exists():
                try:
                    temp_audio_path.unlink(missing_ok=True)
                except Exception:
                    pass

# Singleton instance
global_queue = QueueManager()
