import sys
sys.stdout.reconfigure(encoding='utf-8')
from fastapi.testclient import TestClient
from web.app import app

def test_api():
    client = TestClient(app)

    print("--- [1] Testing GET / ---")
    res = client.get("/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert "VideoLink-to-Text" in res.text
    print("GET / passed!")

    print("--- [2] Testing GET /api/config ---")
    res = client.get("/api/config")
    assert res.status_code == 200
    cfg_data = res.json()
    print("Resolved paths:", cfg_data["resolved_paths"])
    assert "C:\\" not in cfg_data["resolved_paths"]["model_dir"]
    print("GET /api/config passed!")

    print("--- [3] Testing POST /api/tasks ---")
    res = client.post("/api/tasks", json={
        "sources": [
            "https://www.bilibili.com/video/BV1xx411c7mD",
            "F:\\test_video.mp4"
        ]
    })
    assert res.status_code == 200
    tasks = res.json()
    assert len(tasks) == 2
    print(f"Added {len(tasks)} tasks: {[t['id'] for t in tasks]}")

    print("--- [4] Testing GET /api/tasks ---")
    res = client.get("/api/tasks")
    assert res.status_code == 200
    all_tasks = res.json()
    assert len(all_tasks) >= 2
    print(f"Total tasks in queue: {len(all_tasks)}")

    print("ALL API TESTS PASSED!")

if __name__ == "__main__":
    test_api()
