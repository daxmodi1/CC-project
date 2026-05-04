import time
import requests
import os
import cv2
import uuid
import config

API_URL = os.getenv("API_URL", "http://localhost:8000")
WORKER_ID = os.getenv("WORKER_ID", f"asm-{uuid.uuid4().hex[:8]}")


def register_worker():
    """Register this assembly worker with the orchestrator API."""
    while True:
        try:
            resp = requests.post(f"{API_URL}/workers/register", json={
                "worker_id": WORKER_ID,
                "worker_type": "assembly",
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


def run_assembly_worker():
    print(f"Starting Assembly Worker {WORKER_ID} (Polling API)...")
    register_worker()
    s3 = config.get_s3_client()
    assembly_dir = os.path.join(config.LOCAL_STORAGE_DIR, "tmp", "assembly")
    os.makedirs(assembly_dir, exist_ok=True)

    while True:
        try:
            send_heartbeat("idle")

            response = requests.get(f"{API_URL}/tasks/next", params={
                "worker_id": WORKER_ID,
                "task_type": "assembly",
            })

            if response.status_code == 200:
                data = response.json()
                task = data.get("task")

                if task and task["task_type"] == "assembly":
                    task_id = task["task_id"]
                    job_id = task["job_id"]

                    print(f"Assigned Assembly Task {task_id} for Job {job_id}")
                    send_heartbeat("busy", task_id)

                    # 1. Download all frames from shared storage
                    prefix = f"{job_id}/frames/"
                    response = s3.list_objects_v2(Bucket=config.S3_BUCKET_NAME, Prefix=prefix)

                    if "Contents" not in response:
                        print("No frames found!")
                        requests.post(f"{API_URL}/tasks/{task_id}/complete")
                        continue

                    frames = sorted([obj["Key"] for obj in response["Contents"]])
                    local_frames = []

                    print(f"Downloading {len(frames)} frames for assembly...")
                    for key in frames:
                        local_path = os.path.join(assembly_dir, os.path.basename(key))
                        s3.download_file(config.S3_BUCKET_NAME, key, local_path)
                        local_frames.append(local_path)

                    if not local_frames:
                        continue

                    # 2. Stitch into MP4 using OpenCV
                    print("Stitching frames into video...")
                    first_frame = cv2.imread(local_frames[0])
                    height, width, layers = first_frame.shape

                    video_path = os.path.join(assembly_dir, f"{job_id}.mp4")
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    video = cv2.VideoWriter(video_path, fourcc, 24.0, (width, height))

                    for frame_path in local_frames:
                        img = cv2.imread(frame_path)
                        video.write(img)

                    cv2.destroyAllWindows()
                    video.release()

                    # 3. Upload to shared storage
                    print("Uploading final video to shared storage...")
                    s3.upload_file(
                        Filename=video_path,
                        Bucket=config.S3_BUCKET_NAME,
                        Key=f"{job_id}/final_animation.mp4",
                        ExtraArgs={"ContentType": "video/mp4"},
                    )

                    # 4. Clean up temp files
                    os.remove(video_path)
                    for frame_path in local_frames:
                        os.remove(frame_path)

                    # Report completion → marks job as completed
                    requests.post(f"{API_URL}/tasks/{task_id}/complete")
                    print(f"Completed Assembly Task {task_id}")
                    send_heartbeat("idle")

                elif task:
                    time.sleep(2)

            time.sleep(2)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_assembly_worker()
