import time
import json
import requests
import random
import os
import uuid
import config
from engine import generate_animation_script

API_URL = os.getenv("API_URL", "http://localhost:8000")
WORKER_ID = os.getenv("WORKER_ID", f"gen-{uuid.uuid4().hex[:8]}")

MIN_POLL_INTERVAL = 1
MAX_POLL_INTERVAL = 30


def register_worker():
    """Register this worker with the orchestrator API."""
    while True:
        try:
            resp = requests.post(f"{API_URL}/workers/register", json={
                "worker_id": WORKER_ID,
                "worker_type": "generation",
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


def run_generation_worker():
    print(f"Starting Generation Worker {WORKER_ID} (Polling API)...")
    register_worker()
    s3 = config.get_s3_client()

    poll_interval = MIN_POLL_INTERVAL

    while True:
        try:
            send_heartbeat("idle")

            response = requests.get(f"{API_URL}/tasks/next", params={
                "worker_id": WORKER_ID,
                "task_type": "generation",
            })

            if response.status_code == 200:
                data = response.json()
                task = data.get("task")

                if task and task["task_type"] == "generation":
                    task_id = task["task_id"]
                    job_id = task["job_id"]
                    num_frames = task.get("num_frames", 100)
                    num_balls = task.get("num_balls", 5)

                    print(f"Assigned Generation Task {task_id} for Job {job_id}")
                    poll_interval = MIN_POLL_INTERVAL

                    send_heartbeat("busy", task_id)

                    # Simulate heavy generative AI workload
                    sleep_time = random.uniform(3.0, 8.0)
                    print(f"Simulating AI generation for {sleep_time:.1f}s...")
                    time.sleep(sleep_time)

                    # Generate script
                    script_data = generate_animation_script(job_id, num_frames, num_balls)

                    # Upload to shared storage (S3 / local)
                    s3_key = f"{job_id}/script.json"
                    s3.put_object(
                        Bucket=config.S3_BUCKET_NAME,
                        Key=s3_key,
                        Body=json.dumps(script_data),
                        ContentType="application/json",
                    )

                    # Report completion → triggers render chunk creation
                    requests.post(f"{API_URL}/tasks/{task_id}/complete")
                    print(f"Completed Generation Task {task_id}")
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
    run_generation_worker()
