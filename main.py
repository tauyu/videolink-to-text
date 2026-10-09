import os
import sys
import webbrowser
import threading
import time

try:
    if sys.stdout:
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr:
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import uvicorn

from config import load_config, apply_environment_isolation

def open_browser(url: str):
    time.sleep(1.2)
    if sys.platform == "win32":
        try:
            import subprocess
            subprocess.Popen(f'start {url}', shell=True)
            return
        except Exception:
            pass
    try:
        webbrowser.open(url)
    except Exception:
        pass

import socket

def find_available_port(start_port: int = 8765, max_attempts: int = 20) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return start_port

def main():
    cfg = apply_environment_isolation()
    port = find_available_port(8765)
    url = f"http://127.0.0.1:{port}"

    print("=" * 60)
    print(" VideoLink-to-Text 本地控制台正在启动...")
    print(f" - 运行根目录: {os.path.dirname(os.path.abspath(__file__))}")
    print(f" - 结果导出目录: {cfg.get_output_dir()}")
    print(f" - 临时缓存目录: {cfg.get_cache_dir()}")
    print(f" - 模型存储目录: {cfg.get_model_dir()}")
    print(f" - ASR 模型规格: {cfg.model_size} (Device: {cfg.device})")
    print("=" * 60)
    print(f"\n服务已就绪，正在打开浏览器: {url}\n")

    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    uvicorn.run("web.app:app", host="127.0.0.1", port=port, log_level="info")

if __name__ == "__main__":
    main()
