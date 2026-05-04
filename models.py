from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime
import uuid

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, default="queued") # queued, generating, rendering, assembling, completed, failed
    num_frames = Column(Integer, default=100)
    num_balls = Column(Integer, default=5)
    priority = Column(Float, default=1.0)
    lambda_value = Column(Float, default=0.6)  # user speed vs system efficiency
    render_chunk_size = Column(Integer, default=20)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    tasks = relationship("Task", back_populates="job")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"))
    task_type = Column(String) # generation, render, assembly
    status = Column(String, default="pending") # pending, assigned, completed, failed
    worker_id = Column(String, nullable=True)

    # Dependency tracking for the DAG
    depends_on_task_id = Column(String, nullable=True)  # parent task ID

    # Render specific fields
    start_frame = Column(Integer, nullable=True)
    end_frame = Column(Integer, nullable=True)

    # Scheduling scoring variables
    priority = Column(Float, default=1.0)
    est_time = Column(Float, default=10.0)
    data_cost = Column(Float, default=1.0)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    assigned_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    job = relationship("Job", back_populates="tasks")

class Worker(Base):
    __tablename__ = "workers"
    id = Column(String, primary_key=True, index=True)
    worker_type = Column(String, default="generation")  # generation, render, assembly
    status = Column(String, default="idle")  # idle, busy, offline
    current_task_id = Column(String, nullable=True)
    capacity = Column(Float, default=1.0)
    last_heartbeat = Column(DateTime, default=datetime.datetime.utcnow)
    registered_at = Column(DateTime, default=datetime.datetime.utcnow)
