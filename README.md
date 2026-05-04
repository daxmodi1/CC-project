# Cloud Animation Lab Project (PRD Level)

This project demonstrates the core orchestration concepts from the paper *"Cloud-based collaborative animation generation with distributed rendering and resource scheduling"* using native AWS services (S3), Python (FastAPI + OpenCV), and a modern React Frontend.

## Core Features Implemented
- **Smart Database Scheduler**: Replaces simple SQS queueing. Workers poll the API, which dynamically assigns tasks using the paper's scoring equation: `score = w1 * priority - w2 * est_time - w3 * data_cost`.
- **Simulated Heterogeneous Workloads**: Generative tasks pause for random durations (5-15s) and render tasks pause (1-3s per frame) to emulate unpredictable AI GPU compute times.
- **Assembly Worker**: A dedicated worker to stitch `.png` frames into an `.mp4` video.
- **Modern React Dashboard**: Built with Vite, Tailwind CSS, and Zustand.

## 1. Local Setup
1. Clone or download this project.
2. Copy `.env.example` to `.env` and fill in your AWS S3 bucket details and credentials. (SQS is no longer strictly required as we moved to a Database-backed queue).
3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```

## 2. Running the System Locally

**Terminal 1: Start the API & DB**
```bash
uvicorn api:app --reload
```
*This will automatically create the local SQLite database (`animation_lab.db`).*

**Terminal 2: Start the React Frontend**
```bash
cd frontend
npm run dev
```
*Visit `http://localhost:5173` to see your dashboard.*

**Terminal 3, 4, 5: Start the Workers**
```bash
python generation_worker.py
python render_worker.py
python assembly_worker.py
```
*(Tip: Run multiple `render_worker.py` scripts in different terminals to see the load balancing in action!)*

## 3. Deploying to AWS Free Tier:
1. **Database**: Spin up a PostgreSQL instance on AWS RDS Free Tier. Change the `DATABASE_URL` in `.env` to point to it.
2. **Frontend**: Connect your GitHub repo to **Vercel** or **AWS Amplify** to host the React dashboard for free.
3. **Workers & API**: Launch 2-3 EC2 `t2.micro` instances. 
   - Instance A: Run the FastAPI server.
   - Instance B: Run the Generation & Assembly workers.
   - Instance C: Run multiple Render workers.
