import os
from pathlib import Path
from typing import Callable, List, Optional
from faster_whisper import WhisperModel

from core.models import SubtitleSegment

# Global model cache to avoid reloading model on every task
_LOADED_MODEL: Optional[WhisperModel] = None
_LOADED_MODEL_KEY: Optional[str] = None

def get_asr_model(
    model_size: str,
    model_dir: Path,
    device: str = "cuda",
    compute_type: str = "float16"
) -> WhisperModel:
    global _LOADED_MODEL, _LOADED_MODEL_KEY

    model_dir.mkdir(parents=True, exist_ok=True)
    key = f"{model_size}_{device}_{compute_type}_{str(model_dir)}"

    if _LOADED_MODEL is not None and _LOADED_MODEL_KEY == key:
        return _LOADED_MODEL

    print(f"[ASR] Loading Faster-Whisper model '{model_size}' (device={device}, compute_type={compute_type}, dir={model_dir})...")
    try:
        model = WhisperModel(
            model_size_or_path=model_size,
            device=device,
            compute_type=compute_type,
            download_root=str(model_dir)
        )
    except Exception as e:
        if device == "cuda":
            print(f"[ASR] CUDA load failed ({e}), falling back to CPU (int8)...")
            model = WhisperModel(
                model_size_or_path=model_size,
                device="cpu",
                compute_type="int8",
                download_root=str(model_dir)
            )
            key = f"{model_size}_cpu_int8_{str(model_dir)}"
        else:
            raise e

    _LOADED_MODEL = model
    _LOADED_MODEL_KEY = key
    return _LOADED_MODEL

def transcribe_audio(
    audio_path: Path,
    duration: float,
    model_size: str,
    model_dir: Path,
    device: str = "cuda",
    compute_type: str = "float16",
    on_progress: Optional[Callable[[float, str], None]] = None
) -> List[SubtitleSegment]:
    """Transcribes audio file using faster-whisper and returns SubtitleSegments with timestamps."""
    model = get_asr_model(model_size, model_dir, device, compute_type)

    if on_progress:
        on_progress(0.0, "开始语音转写 (ASR)...")

    # Initial prompt to guide Whisper towards standard Chinese punctuation and avoid space breaks
    chinese_prompt = "以下是普通话的内容，请使用标准的简体中文与规范的中文标点符号（逗号、句号、感叹号、问号等），切勿遗漏标点或使用空格分句。"

    # Transcribe with VAD filter to reduce silence hallucination
    segments_gen, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        task="transcribe",
        initial_prompt=chinese_prompt
    )

    total_dur = duration if duration > 0 else info.duration
    if total_dur <= 0:
        total_dur = 1.0

    results: List[SubtitleSegment] = []
    
    for seg in segments_gen:
        text = seg.text.strip()
        if text:
            results.append(SubtitleSegment(start=seg.start, end=seg.end, text=text))
            pct = min(99.0, (seg.end / total_dur) * 100)
            if on_progress:
                on_progress(pct, f"听写转录中: {pct:.1f}% [{seg.end:.0f}s / {total_dur:.0f}s]")

    if on_progress:
        on_progress(100.0, "语音转写完成")

    return results
