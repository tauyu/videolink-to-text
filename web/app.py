import os
import sys
import asyncio
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from config import AppConfig, load_config, save_config, apply_environment_isolation, APP_DIR
from queue_manager import global_queue, TaskItem

app = FastAPI(title="VideoLink-to-Text")

# Apply environment isolation on startup
apply_environment_isolation()

STATIC_DIR = APP_DIR / "web" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

class AddTasksRequest(BaseModel):
    sources: List[str]

class ConfigUpdateRequest(BaseModel):
    output_dir: str
    cache_dir: str
    model_dir: str
    model_size: str
    device: str
    compute_type: str
    export_timeline_transcript: bool = False

class OpenFolderRequest(BaseModel):
    path: Optional[str] = None

# Connected WebSocket clients
connected_clients: List[WebSocket] = []

def ws_broadcast(msg: dict):
    # Bridge sync queue worker to async websocket
    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        pass
    
    if loop and loop.is_running():
        for client in list(connected_clients):
            asyncio.run_coroutine_threadsafe(client.send_json(msg), loop)

# Register listener to global queue
global_queue.add_listener(ws_broadcast)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        # Send initial full state
        tasks = [t.model_dump() for t in global_queue.get_all_tasks()]
        await websocket.send_json({"type": "init", "data": tasks})
        while True:
            # Keep alive & listen for client ping
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

@app.get("/api/tasks")
def list_tasks():
    return [t.model_dump() for t in global_queue.get_all_tasks()]

@app.post("/api/tasks")
def add_tasks(req: AddTasksRequest):
    valid_sources = [s.strip() for s in req.sources if s.strip()]
    if not valid_sources:
        raise HTTPException(status_code=400, detail="未提供有效的视频链接或路径")
    tasks = global_queue.add_batch(valid_sources)
    return [t.model_dump() for t in tasks]

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    success = global_queue.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"status": "ok"}

@app.post("/api/tasks/clear")
def clear_tasks():
    global_queue.clear_completed()
    return {"status": "ok"}

@app.get("/api/config")
def get_config():
    cfg = load_config()
    return {
        "config": cfg.model_dump(),
        "resolved_paths": {
            "output_dir": str(cfg.get_output_dir()),
            "cache_dir": str(cfg.get_cache_dir()),
            "model_dir": str(cfg.get_model_dir()),
        }
    }

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    cfg = AppConfig(**req.model_dump())
    save_config(cfg)
    apply_environment_isolation(cfg)
    return {
        "status": "ok",
        "config": cfg.model_dump(),
        "resolved_paths": {
            "output_dir": str(cfg.get_output_dir()),
            "cache_dir": str(cfg.get_cache_dir()),
            "model_dir": str(cfg.get_model_dir()),
        }
    }

@app.post("/api/open-folder")
def open_folder(req: OpenFolderRequest):
    """Opens folder in Windows Explorer."""
    cfg = load_config()
    target_path = Path(req.path) if req.path else cfg.get_output_dir()
    target_path.mkdir(parents=True, exist_ok=True)
    abs_path = str(target_path.resolve())

    if sys.platform == "win32":
        try:
            import subprocess
            # Launch explorer directly with the folder path
            subprocess.Popen(f'explorer.exe "{abs_path}"', shell=True)
            return {"status": "ok", "path": abs_path}
        except Exception:
            try:
                os.startfile(abs_path)
                return {"status": "ok", "path": abs_path}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    return {"status": "unsupported_platform", "path": abs_path}

@app.get("/api/download/{task_id}/{file_format}")
def download_result(task_id: str, file_format: str):
    task = global_queue.get_task(task_id)
    if not task or not task.output_files:
        raise HTTPException(status_code=404, detail="文件不存在或尚未转录完成")

    file_path = task.output_files.get(file_format)
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail=f"未找到 {file_format} 格式结果")

    return FileResponse(
        path=file_path,
        filename=Path(file_path).name,
        media_type="application/octet-stream"
    )

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>VideoLink-to-Text Server is running!</h1>")
