import time
import json
import requests
import os
import random
import uuid
import config
from engine import render_frame

API_URL = os.getenv("API_URL", "http://localhost:8000")
WORKER_ID = os.getenv("WORKER_ID", f"ren-{uuid.uuid4().hex[:8]}")

MIN_POLL_INTERVAL = 1
MAX_POLL_INTERVAL = 30


def register_worker():
    """Register this render worker with the orchestrator API."""
    while True:
        try:
            resp = requests.post(f"{API_URL}/workers/register", json={
                "worker_id": WORKER_ID,
                "worker_type": "render",
                "capacity": 1.0,
            })
            if resp.status_code == 200:
                print(f"Registered as {WORKER_ID}")
                return
        except Exception as e:
            print(f"Registration failed: {e}. Retrying in 3s...")
        time.sleep(3)


def send_heartbeat(status="idle", current_task_id=None):
    try:
        requests.post(f"{API_URL}/workers/heartbeat", json={
            "worker_id": WORKER_ID,
            "status": status,
            "current_task_id": current_task_id,
        })
    except Exception:
        pass


def run_render_worker():
    print(f"Starting Render Worker {WORKER_ID} (Polling API)...")
    register_worker()
    s3 = config.get_s3_client()
    render_dir = os.path.join(config.LOCAL_STORAGE_DIR, "tmp", "renders")
    os.makedirs(render_dir, exist_ok=True)

    poll_interval = MIN_POLL_INTERVAL

    while True:
        try:
            send_heartbeat("idle")

            response = requests.get(f"{API_URL}/tasks/next", params={
                "worker_id": WORKER_ID,
                "task_type": "render",
            })

            if response.status_code == 200:
                data = response.json()
                task = data.get("task")

                if task and task["task_type"] == "render":
                    task_id = task["task_id"]
                    job_id = task["job_id"]
                    start_frame = task["start_frame"]
                    end_frame = task["end_frame"]

                    print(f"Assigned Render Task {task_id} for Job {job_id} (Frames {start_frame}-{end_frame})")
                    poll_interval = MIN_POLL_INTERVAL

                    send_heartbeat("busy", task_id)

                    # Download script from shared storage
                    s3_key = f"{job_id}/script.json"
                    s3_res = s3.get_object(Bucket=config.S3_BUCKET_NAME, Key=s3_key)
                    script_data = json.loads(s3_res["Body"].read().decode("utf-8"))

                    for frame_idx in range(start_frame, end_frame + 1):
                        # Simulate rendering delay
                        sleep_time = random.uniform(0.5, 1.5)
                        print(f"  Rendering frame {frame_idx}... ({sleep_time:.1f}s)")
                        time.sleep(sleep_time)

                        local_path = os.path.join(render_dir, f"{job_id}_frame_{frame_idx:04d}.png")
                        render_frame(script_data, frame_idx, local_path)

                        # Upload to shared storage
                        s3_output_key = f"{job_id}/frames/frame_{frame_idx:04d}.png"
                        s3.upload_file(
                            Filename=local_path,
                            Bucket=config.S3_BUCKET_NAME,
                            Key=s3_output_key,
                            ExtraArgs={"ContentType": "image/png"},
                        )
                        os.remove(local_path)

                    # Report completion → may trigger assembly task
                    requests.post(f"{API_URL}/tasks/{task_id}/complete")
                    print(f"Completed Render Task {task_id}")
                    send_heartbeat("idle")
                else:
                    jitter = random.uniform(0.75, 1.25)
                    time.sleep(poll_interval * jitter)
                    poll_interval = min(poll_interval * 2, MAX_POLL_INTERVAL)
            else:
                jitter = random.uniform(0.75, 1.25)
                time.sleep(poll_interval * jitter)
                poll_interval = min(poll_interval * 2, MAX_POLL_INTERVAL)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
            poll_interval = MIN_POLL_INTERVAL


if __name__ == "__main__":
    run_render_worker()
