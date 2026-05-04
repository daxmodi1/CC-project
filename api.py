from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import datetime
from typing import Optional

import models
import config
from database import SessionLocal, engine, get_db
from fastapi.middleware.cors import CORSMiddleware

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cloud Animation Smart Orchestrator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {
        "service": "Cloud Animation Smart Orchestrator API",
        "status": "ok",
        "docs": "/docs"
    }


# ─── Request / Response Models ────────────────────────────────────────────────

class JobRequest(BaseModel):
    num_frames: int = 60
    num_balls: int = 5
    render_chunk_size: int = 20
    priority: float = 1.0
    lambda_value: float = 0.6  # user speed vs system efficiency


class WorkerRegisterRequest(BaseModel):
    worker_id: str
    worker_type: str  # generation, render, assembly
    capacity: float = 1.0


class WorkerHeartbeatRequest(BaseModel):
    worker_id: str
    status: str = "idle"
    current_task_id: Optional[str] = None


# ─── Scheduling weights ──────────────────────────────────────────────────────

W1, W2, W3 = 10.0, 0.5, 2.0


def compute_score(task, lambda_value: float = 0.6) -> float:
    """
    Scoring formula from the paper:
      score = w1 * priority - w2 * est_time - w3 * data_cost
    Adjusted by lambda: higher lambda favours system efficiency (lower
    individual priority weight), lower lambda favours user speed.
    """
    adjusted_w1 = W1 * (1.0 - lambda_value + 0.5)
    adjusted_w2 = W2 * (lambda_value + 0.5)
    return (adjusted_w1 * task.priority) - (adjusted_w2 * task.est_time) - (W3 * task.data_cost)


# ─── Helper paths ─────────────────────────────────────────────────────────────

def _job_frame_dir(job_id: str) -> str:
    return config.get_local_storage_path(f"{job_id}/frames")


def _job_video_path(job_id: str) -> str:
    return config.get_local_storage_path(f"{job_id}/final_animation.mp4")


def _job_script_path(job_id: str) -> str:
    return config.get_local_storage_path(f"{job_id}/script.json")


# ─── Job endpoints ────────────────────────────────────────────────────────────

@app.post("/jobs/")
def submit_job(request: JobRequest, db: Session = Depends(get_db)):
    """
    Submits a new animation job.
    Only creates the job record and the initial **generation** task.
    Workers pull tasks from /tasks/next — no local pipeline is launched.
    """
    job = models.Job(
        num_frames=request.num_frames,
        num_balls=request.num_balls,
        render_chunk_size=request.render_chunk_size,
        priority=request.priority,
        lambda_value=request.lambda_value,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Create the initial generation task
    gen_task = models.Task(
        job_id=job.id,
        task_type="generation",
        priority=request.priority + 0.5,  # slightly higher to unlock rendering
        est_time=15.0,
        data_cost=0.5,
    )
    db.add(gen_task)
    db.commit()

    return {
        "job_id": job.id,
        "status": job.status,
        "generation_task_id": gen_task.id,
        "message": "Job queued. Workers will pull tasks from /tasks/next.",
    }


@app.get("/jobs/")
def list_jobs(db: Session = Depends(get_db)):
    """Returns all jobs with rich detail for the dashboard."""
    jobs = db.query(models.Job).order_by(models.Job.created_at.desc()).all()
    response = []
    for job in jobs:
        tasks = db.query(models.Task).filter(models.Task.job_id == job.id).all()
        completed_tasks = sum(1 for t in tasks if t.status == "completed")
        rendered_frames = 0
        frame_dir = _job_frame_dir(job.id)
        if os.path.exists(frame_dir):
            rendered_frames = len([n for n in os.listdir(frame_dir) if n.endswith(".png")])

        # Compute completion time
        completion_time = None
        if job.completed_at and job.created_at:
            completion_time = (job.completed_at - job.created_at).total_seconds()

        response.append({
            "id": job.id,
            "status": job.status,
            "frames": job.num_frames,
            "balls": job.num_balls,
            "priority": job.priority,
            "lambda_value": job.lambda_value,
            "render_chunk_size": job.render_chunk_size,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "completion_time": completion_time,
            "tasks_total": len(tasks),
            "tasks_completed": completed_tasks,
            "rendered_frames": rendered_frames,
            "preview_url": f"/jobs/{job.id}/preview" if rendered_frames else None,
            "frame_url": f"/jobs/{job.id}/frames/{{frame_index}}" if rendered_frames else None,
            "video_url": f"/jobs/{job.id}/video" if os.path.exists(_job_video_path(job.id)) else None,
        })
    return response


@app.get("/jobs/{job_id}/preview")
def get_job_preview(job_id: str):
    frame_dir = _job_frame_dir(job_id)
    if not os.path.exists(frame_dir):
        raise HTTPException(status_code=404, detail="No preview frames found")

    frames = sorted(n for n in os.listdir(frame_dir) if n.endswith(".png"))
    if not frames:
        raise HTTPException(status_code=404, detail="No preview frames found")
    return FileResponse(os.path.join(frame_dir, frames[-1]), media_type="image/png")


@app.get("/jobs/{job_id}/frames/{frame_index}")
def get_job_frame(job_id: str, frame_index: int):
    frame_path = os.path.join(_job_frame_dir(job_id), f"frame_{frame_index:04d}.png")
    if not os.path.exists(frame_path):
        raise HTTPException(status_code=404, detail="Frame not found")
    return FileResponse(frame_path, media_type="image/png")


@app.get("/jobs/{job_id}/video")
def get_job_video(job_id: str):
    video_path = _job_video_path(job_id)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video is not ready")
    return FileResponse(video_path, media_type="video/mp4", filename=f"{job_id}.mp4")


# ─── DAG endpoint ─────────────────────────────────────────────────────────────

@app.get("/jobs/{job_id}/dag")
def get_job_dag(job_id: str, db: Session = Depends(get_db)):
    """
    Returns the task dependency graph (DAG) for a job.
    Each node includes its id, type, status, worker, and parent.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    tasks = db.query(models.Task).filter(models.Task.job_id == job_id).all()
    nodes = []
    edges = []

    for t in tasks:
        nodes.append({
            "id": t.id,
            "task_type": t.task_type,
            "status": t.status,
            "worker_id": t.worker_id,
            "start_frame": t.start_frame,
            "end_frame": t.end_frame,
            "depends_on": t.depends_on_task_id,
        })
        if t.depends_on_task_id:
            edges.append({"from": t.depends_on_task_id, "to": t.id})

    return {"job_id": job_id, "status": job.status, "nodes": nodes, "edges": edges}


# ─── Shared Storage endpoint ──────────────────────────────────────────────────

@app.get("/storage/{job_id}")
def get_storage_status(job_id: str, db: Session = Depends(get_db)):
    """
    Returns the shared storage state for a job:
    whether the script is generated, how many frames exist, and if the MP4 is ready.
    """
    script_exists = os.path.exists(_job_script_path(job_id))
    frame_dir = _job_frame_dir(job_id)
    frame_count = 0
    if os.path.exists(frame_dir):
        frame_count = len([n for n in os.listdir(frame_dir) if n.endswith(".png")])
    video_ready = os.path.exists(_job_video_path(job_id))

    return {
        "job_id": job_id,
        "script_generated": script_exists,
        "frames_rendered": frame_count,
        "video_ready": video_ready,
    }


# ─── Stats / Metrics endpoint ─────────────────────────────────────────────────

@app.get("/stats/")
def get_stats(db: Session = Depends(get_db)):
    jobs = db.query(models.Job).all()
    tasks = db.query(models.Task).all()

    total_rendered_frames = 0
    for job in jobs:
        fd = _job_frame_dir(job.id)
        if os.path.exists(fd):
            total_rendered_frames += len([n for n in os.listdir(fd) if n.endswith(".png")])

    completion_times = []
    for job in jobs:
        if job.completed_at and job.created_at:
            completion_times.append((job.completed_at - job.created_at).total_seconds())

    avg_completion = sum(completion_times) / len(completion_times) if completion_times else 0

    return {
        "total_jobs": len(jobs),
        "completed_jobs": sum(1 for j in jobs if j.status == "completed"),
        "active_jobs": sum(1 for j in jobs if j.status in ("queued", "generating", "rendering", "assembling")),
        "failed_jobs": sum(1 for j in jobs if j.status == "failed"),
        "total_tasks": len(tasks),
        "pending_tasks": sum(1 for t in tasks if t.status == "pending"),
        "assigned_tasks": sum(1 for t in tasks if t.status == "assigned"),
        "completed_tasks": sum(1 for t in tasks if t.status == "completed"),
        "total_rendered_frames": total_rendered_frames,
        "avg_completion_time": round(avg_completion, 2),
    }


# ─── Worker registration & heartbeat ──────────────────────────────────────────

@app.post("/workers/register")
def register_worker(req: WorkerRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(models.Worker).filter(models.Worker.id == req.worker_id).first()
    if existing:
        existing.status = "idle"
        existing.worker_type = req.worker_type
        existing.capacity = req.capacity
        existing.last_heartbeat = datetime.datetime.utcnow()
        db.commit()
        return {"message": "Worker re-registered", "worker_id": req.worker_id}

    worker = models.Worker(
        id=req.worker_id,
        worker_type=req.worker_type,
        capacity=req.capacity,
    )
    db.add(worker)
    db.commit()
    return {"message": "Worker registered", "worker_id": req.worker_id}


@app.post("/workers/heartbeat")
def worker_heartbeat(req: WorkerHeartbeatRequest, db: Session = Depends(get_db)):
    worker = db.query(models.Worker).filter(models.Worker.id == req.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not registered")

    worker.status = req.status
    worker.current_task_id = req.current_task_id
    worker.last_heartbeat = datetime.datetime.utcnow()
    db.commit()
    return {"message": "Heartbeat received"}


@app.get("/workers/")
def list_workers(db: Session = Depends(get_db)):
    """Returns all registered workers and their status."""
    workers = db.query(models.Worker).all()
    result = []
    for w in workers:
        result.append({
            "id": w.id,
            "worker_type": w.worker_type,
            "status": w.status,
            "current_task_id": w.current_task_id,
            "capacity": w.capacity,
            "last_heartbeat": w.last_heartbeat,
            "registered_at": w.registered_at,
        })
    return result


# ─── Scheduler / Task endpoints ───────────────────────────────────────────────

@app.get("/tasks/pending")
def get_pending_tasks(db: Session = Depends(get_db)):
    """
    Returns all pending tasks sorted by score — exposes the scheduler's reasoning.
    """
    pending = db.query(models.Task).filter(models.Task.status == "pending").all()
    scored = []
    for t in pending:
        job = db.query(models.Job).filter(models.Job.id == t.job_id).first()
        lam = job.lambda_value if job else 0.6
        score = compute_score(t, lam)
        scored.append({
            "task_id": t.id,
            "job_id": t.job_id,
            "task_type": t.task_type,
            "priority": t.priority,
            "est_time": t.est_time,
            "data_cost": t.data_cost,
            "score": round(score, 3),
            "depends_on": t.depends_on_task_id,
            "start_frame": t.start_frame,
            "end_frame": t.end_frame,
            "formula": f"({W1}×(1-λ+0.5))×{t.priority} - ({W2}×(λ+0.5))×{t.est_time} - {W3}×{t.data_cost}",
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {
        "weights": {"w1": W1, "w2": W2, "w3": W3},
        "formula": "score = w1×(1-λ+0.5) × priority - w2×(λ+0.5) × est_time - w3 × data_cost",
        "pending_tasks": scored,
    }


@app.get("/tasks/next")
def get_next_task(worker_id: str, task_type: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Smart Scheduler Endpoint.
    Finds the best pending task using the scoring function.
    """
    query = db.query(models.Task).filter(models.Task.status == "pending")
    if task_type:
        query = query.filter(models.Task.task_type == task_type)
    pending_tasks = query.all()

    if not pending_tasks:
        return {"task": None}

    best_task = None
    highest_score = -float('inf')

    for task in pending_tasks:
        job = db.query(models.Job).filter(models.Job.id == task.job_id).first()
        lam = job.lambda_value if job else 0.6
        score = compute_score(task, lam)
        if score > highest_score:
            highest_score = score
            best_task = task

    if best_task:
        best_task.status = "assigned"
        best_task.worker_id = worker_id
        best_task.assigned_at = datetime.datetime.utcnow()

        # Update Job status
        job = db.query(models.Job).filter(models.Job.id == best_task.job_id).first()
        if best_task.task_type == "generation" and job.status == "queued":
            job.status = "generating"
        elif best_task.task_type == "render" and job.status in ("queued", "generating"):
            job.status = "rendering"
        elif best_task.task_type == "assembly":
            job.status = "assembling"

        # Update worker status
        worker = db.query(models.Worker).filter(models.Worker.id == worker_id).first()
        if worker:
            worker.status = "busy"
            worker.current_task_id = best_task.id

        db.commit()

        return {
            "task": {
                "task_id": best_task.id,
                "job_id": best_task.job_id,
                "task_type": best_task.task_type,
                "start_frame": best_task.start_frame,
                "end_frame": best_task.end_frame,
                "num_frames": job.num_frames,
                "num_balls": job.num_balls,
                "score": round(highest_score, 3),
            }
        }

    return {"task": None}


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: str, db: Session = Depends(get_db)):
    """
    Worker reports a task is completed. We then spawn dependent tasks.
    Dependencies:
      generation → N render chunks (each depends_on generation)
      all render chunks done → 1 assembly task (depends_on each render chunk)
      assembly done → job completed
    """
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "completed"
    task.completed_at = datetime.datetime.utcnow()
    job = db.query(models.Job).filter(models.Job.id == task.job_id).first()

    # Release the worker
    if task.worker_id:
        worker = db.query(models.Worker).filter(models.Worker.id == task.worker_id).first()
        if worker:
            worker.status = "idle"
            worker.current_task_id = None

    # ── Task Dependencies ────────────────────────────────────────────
    if task.task_type == "generation":
        # Spawn render tasks — each depends on this generation task
        chunk_size = job.render_chunk_size or 20
        for start_idx in range(0, job.num_frames, chunk_size):
            end_idx = min(start_idx + chunk_size - 1, job.num_frames - 1)
            render_task = models.Task(
                job_id=job.id,
                task_type="render",
                start_frame=start_idx,
                end_frame=end_idx,
                depends_on_task_id=task.id,  # DAG edge: gen -> render chunk
                priority=job.priority,
                est_time=max(1.0, (end_idx - start_idx + 1) * 2.0),
                data_cost=2.0,
            )
            db.add(render_task)
        job.status = "rendering"

    elif task.task_type == "render":
        # Check if ALL render tasks for this job are completed
        all_renders = db.query(models.Task).filter(
            models.Task.job_id == job.id,
            models.Task.task_type == "render",
        ).all()

        if all(r.status == "completed" for r in all_renders):
            # Spawn assembly task — depends on render tasks
            assembly_task = models.Task(
                job_id=job.id,
                task_type="assembly",
                depends_on_task_id=task.id,  # last render chunk as parent
                priority=job.priority + 1.0,  # high priority to finish
                est_time=10.0,
                data_cost=5.0,
            )
            db.add(assembly_task)

    elif task.task_type == "assembly":
        job.status = "completed"
        job.completed_at = datetime.datetime.utcnow()

    db.commit()
    return {"status": "success", "task_type": task.task_type}


# Run with: uvicorn api:app --reload
