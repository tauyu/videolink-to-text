import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

APP_DIR = Path(__file__).resolve().parent

class AppConfig(BaseModel):
    output_dir: str = "./outputs"
    cache_dir: str = "./cache"
    model_dir: str = "./models"
    model_size: str = "large-v3-turbo"
    device: str = "cuda"  # "cuda" or "cpu"
    compute_type: str = "float16"  # "float16" for GPU, "int8" for CPU
    export_timeline_transcript: bool = False  # 输出带时间轴的逐句稿，默认不开

    def get_output_dir(self) -> Path:
        p = Path(self.output_dir)
        return (APP_DIR / p).resolve() if not p.is_absolute() else p.resolve()

    def get_cache_dir(self) -> Path:
        p = Path(self.cache_dir)
        return (APP_DIR / p).resolve() if not p.is_absolute() else p.resolve()

    def get_model_dir(self) -> Path:
        p = Path(self.model_dir)
        return (APP_DIR / p).resolve() if not p.is_absolute() else p.resolve()

CONFIG_FILE = APP_DIR / "config.json"

def load_config() -> AppConfig:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig(**data)
        except Exception as e:
            print(f"[Config] Error loading config.json: {e}, falling back to defaults.")
    cfg = AppConfig()
    save_config(cfg)
    return cfg

def save_config(cfg: AppConfig):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg.model_dump(), f, indent=2, ensure_ascii=False)

def apply_environment_isolation(cfg: Optional[AppConfig] = None):
    """
    Redirect all temp, Hugging Face and PyTorch caches away from C: drive
    into project-relative portable directories.
    """
    if cfg is None:
        cfg = load_config()

    cache_dir = cfg.get_cache_dir()
    model_dir = cfg.get_model_dir()
    output_dir = cfg.get_output_dir()

    cache_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Hugging Face & CTranslate2 & Torch cache redirect
    os.environ["HF_HOME"] = str(model_dir)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(model_dir)
    os.environ["TORCH_HOME"] = str(model_dir)
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

    # Temp directories redirect
    os.environ["TEMP"] = str(cache_dir)
    os.environ["TMP"] = str(cache_dir)
    os.environ["TMPDIR"] = str(cache_dir)
    tempfile.tempdir = str(cache_dir)

    # Add local bin directory to PATH for ffmpeg/ffprobe if available
    bin_dir = APP_DIR / "bin"
    if bin_dir.exists():
        bin_str = str(bin_dir)
        if bin_str not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")

    # Auto-register NVIDIA CUDA / cuBLAS / cuDNN runtime DLLs on Windows
    if sys.platform == "win32":
        nvidia_dir = APP_DIR / ".venv" / "Lib" / "site-packages" / "nvidia"
        if nvidia_dir.exists():
            for p in nvidia_dir.glob("*/bin"):
                p_str = str(p.resolve())
                if p_str not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = p_str + os.pathsep + os.environ.get("PATH", "")
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(p_str)
                    except Exception:
                        pass

    # Static ffmpeg initialization fallback
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except Exception:
        pass

    return cfg
