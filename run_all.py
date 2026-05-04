"""
Convenience launcher — starts the API server and all workers in one process.
Run:  python run_all.py
"""
import subprocess
import sys
import os
import time
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    env = os.environ.copy()
    env["API_URL"] = env.get("API_URL", "http://localhost:8000")
    python = sys.executable

    # Delete the old database so schema changes take effect
    db_path = os.path.join(BASE_DIR, "animation_lab.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        print("[launcher] Removed old database for schema migration.")

    processes = []

    # 1. Start API server
    api_proc = subprocess.Popen(
        [python, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=BASE_DIR,
        env=env,
    )
    processes.append(("API", api_proc))
    print("[launcher] API server starting on :8000")
    time.sleep(2)  # let the API come up

    # 2. Generation worker (1 instance)
    gen_env = {**env, "WORKER_ID": "gen-worker-01"}
    gen_proc = subprocess.Popen(
        [python, "generation_worker.py"],
        cwd=BASE_DIR,
        env=gen_env,
    )
    processes.append(("Generation Worker", gen_proc))

    # 3. Render workers (3 instances)
    for i in range(1, 4):
        ren_env = {**env, "WORKER_ID": f"ren-worker-{i:02d}"}
        ren_proc = subprocess.Popen(
            [python, "render_worker.py"],
            cwd=BASE_DIR,
            env=ren_env,
        )
        processes.append((f"Render Worker {i}", ren_proc))

    # 4. Assembly worker (1 instance)
    asm_env = {**env, "WORKER_ID": "asm-worker-01"}
    asm_proc = subprocess.Popen(
        [python, "assembly_worker.py"],
        cwd=BASE_DIR,
        env=asm_env,
    )
    processes.append(("Assembly Worker", asm_proc))

    print(f"[launcher] Started {len(processes)} processes:")
    for name, proc in processes:
        print(f"  - {name} (PID {proc.pid})")
    print("[launcher] Press Ctrl+C to stop all.")

    try:
        while True:
            for name, proc in processes:
                retcode = proc.poll()
                if retcode is not None:
                    print(f"[launcher] {name} exited with code {retcode}")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n[launcher] Shutting down all processes...")
        for name, proc in processes:
            proc.terminate()
        for name, proc in processes:
            proc.wait(timeout=5)
        print("[launcher] All processes stopped.")


if __name__ == "__main__":
    main()
