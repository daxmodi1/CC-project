import { useEffect, useState, useCallback } from 'react'
import { useStore } from './store'

/* ═══════════════════════════════════════════════════════════════════════════
   1. JOB SUBMISSION PANEL
   ═══════════════════════════════════════════════════════════════════════════ */
function JobSubmission() {
  const { submitJob, loading } = useStore()
  const [frames, setFrames] = useState(60)
  const [balls, setBalls] = useState(5)
  const [chunk, setChunk] = useState(20)
  const [priority, setPriority] = useState(1.0)
  const [lambda, setLambda] = useState(0.6)

  const handleSubmit = (e) => {
    e.preventDefault()
    submitJob(frames, balls, chunk, priority, lambda)
  }

  return (
    <div className="glass-card p-5 fade-in">
      <div className="section-title">
        <span className="dot" style={{ background: 'var(--accent-amber)' }} />
        1 · Job Submission
      </div>
      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
          <div>
            <label className="form-label">Frames</label>
            <input type="number" className="form-input" value={frames}
              onChange={e => setFrames(+e.target.value)} min={10} max={300} />
          </div>
          <div>
            <label className="form-label">Balls</label>
            <input type="number" className="form-input" value={balls}
              onChange={e => setBalls(+e.target.value)} min={1} max={20} />
          </div>
          <div>
            <label className="form-label">Chunk Size</label>
            <input type="number" className="form-input" value={chunk}
              onChange={e => setChunk(+e.target.value)} min={5} max={100} />
          </div>
          <div>
            <label className="form-label">Priority</label>
            <input type="number" className="form-input" value={priority}
              onChange={e => setPriority(+e.target.value)} min={0.1} max={5} step={0.1} />
          </div>
          <div className="col-span-2 sm:col-span-1">
            <label className="form-label">Lambda (λ) — Speed vs Efficiency</label>
            <div className="flex items-center gap-2">
              <span className="text-[0.6rem] text-amber-400">User</span>
              <input type="range" className="flex-1 accent-blue-500" value={lambda}
                onChange={e => setLambda(+e.target.value)} min={0} max={1} step={0.1} />
              <span className="text-[0.6rem] text-cyan-400">System</span>
            </div>
            <div className="text-center text-xs text-gray-400 mt-1 font-mono">λ = {lambda}</div>
          </div>
        </div>
        <button type="submit" className="submit-btn" disabled={loading}>
          {loading ? 'Submitting…' : '⚡ Submit Animation Job'}
        </button>
      </form>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   2. TASK GRAPH / DAG
   ═══════════════════════════════════════════════════════════════════════════ */
function DagNode({ type, status, label }) {
  const icons = { generation: 'GEN', render: 'REN', assembly: 'ASM' }
  return (
    <div className="dag-node">
      <div className={`dag-node-box ${status}`}>{icons[type] || '?'}</div>
      <div className="dag-node-label">{label}</div>
    </div>
  )
}

function TaskDag({ jobId }) {
  const dag = useStore(s => s.dagData[jobId])
  if (!dag || !dag.nodes || dag.nodes.length === 0) {
    return <div className="text-xs text-gray-500 p-3">No tasks yet — waiting for orchestration</div>
  }

  const gen = dag.nodes.filter(n => n.task_type === 'generation')
  const renders = dag.nodes.filter(n => n.task_type === 'render')
  const asm = dag.nodes.filter(n => n.task_type === 'assembly')

  return (
    <div className="dag-container">
      {/* Generation */}
      {gen.map(n => (
        <DagNode key={n.id} type="generation" status={n.status}
          label={`Gen${n.worker_id ? `\n${n.worker_id.slice(0,10)}` : ''}`} />
      ))}

      {renders.length > 0 && <div className="dag-arrow">→</div>}

      {/* Render chunks */}
      <div className="flex flex-wrap gap-1 items-start">
        {renders.map(n => (
          <DagNode key={n.id} type="render" status={n.status}
            label={`F${n.start_frame}-${n.end_frame}`} />
        ))}
      </div>

      {asm.length > 0 && <div className="dag-arrow">→</div>}

      {/* Assembly */}
      {asm.map(n => (
        <DagNode key={n.id} type="assembly" status={n.status}
          label={`Assemble${n.worker_id ? `\n${n.worker_id.slice(0,10)}` : ''}`} />
      ))}
    </div>
  )
}

function TaskDagPanel() {
  const jobs = useStore(s => s.jobs)
  const [selectedJob, setSelectedJob] = useState(null)

  // Auto-select the latest active or first job
  useEffect(() => {
    if (jobs.length > 0 && !selectedJob) {
      const active = jobs.find(j => j.status !== 'completed') || jobs[0]
      setSelectedJob(active.id)
    }
  }, [jobs, selectedJob])

  return (
    <div className="glass-card p-5 fade-in">
      <div className="section-title">
        <span className="dot" style={{ background: 'var(--accent-blue)' }} />
        2 · Task Graph / DAG
      </div>

      {jobs.length === 0 ? (
        <div className="text-xs text-gray-500 py-4 text-center">Submit a job to see the task DAG</div>
      ) : (
        <>
          <div className="flex gap-2 mb-3 overflow-x-auto pb-1">
            {jobs.map(j => (
              <button key={j.id}
                className={`text-[0.65rem] font-mono px-3 py-1 rounded-md border transition-all whitespace-nowrap
                  ${selectedJob === j.id
                    ? 'border-blue-500 bg-blue-500/10 text-blue-300'
                    : 'border-gray-700 text-gray-500 hover:text-gray-300'}`}
                onClick={() => setSelectedJob(j.id)}>
                {j.id.slice(0, 8)}… <span className="capitalize ml-1 opacity-70">{j.status}</span>
              </button>
            ))}
          </div>
          <div className="text-[0.6rem] text-gray-500 mb-2">
            Dependencies: <span className="text-gray-400">Generation → Render Chunks → Assembly</span>
          </div>
          {selectedJob && <TaskDag jobId={selectedJob} />}
        </>
      )}
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   3. WORKER POOL
   ═══════════════════════════════════════════════════════════════════════════ */
function WorkerPool() {
  const workers = useStore(s => s.workers)

  const byType = {
    generation: workers.filter(w => w.worker_type === 'generation'),
    render: workers.filter(w => w.worker_type === 'render'),
    assembly: workers.filter(w => w.worker_type === 'assembly'),
  }

  const WorkerCard = ({ w }) => (
    <div className={`worker-badge ${w.status}`}>
      <div className={`worker-dot ${w.status}`} />
      <div className="flex-1 min-w-0">
        <div className="font-semibold truncate">{w.id}</div>
        <div className="text-[0.6rem] text-gray-500">
          {w.status === 'busy' && w.current_task_id
            ? `→ ${w.current_task_id.slice(0, 8)}…`
            : w.status}
        </div>
      </div>
      <span className={`type-badge ${w.worker_type}`}>{w.worker_type.slice(0, 3)}</span>
    </div>
  )

  return (
    <div className="glass-card p-5 fade-in">
      <div className="section-title">
        <span className="dot" style={{ background: 'var(--accent-green)' }} />
        3 · Worker Pool
        <span className="ml-auto text-[0.6rem] font-normal text-gray-500">
          {workers.length} worker{workers.length !== 1 ? 's' : ''} registered
        </span>
      </div>
      {workers.length === 0 ? (
        <div className="text-xs text-gray-500 py-4 text-center">
          No workers registered — start workers to see them here
        </div>
      ) : (
        <div className="space-y-4">
          {Object.entries(byType).map(([type, list]) => list.length > 0 && (
            <div key={type}>
              <div className="text-[0.6rem] uppercase tracking-wider text-gray-500 mb-2 flex items-center gap-2">
                <span className={`type-badge ${type}`}>{type}</span>
                <span>{list.length} instance{list.length !== 1 ? 's' : ''}</span>
              </div>
              <div className="grid gap-2">
                {list.map(w => <WorkerCard key={w.id} w={w} />)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   4. SCHEDULER VIEW
   ═══════════════════════════════════════════════════════════════════════════ */
function SchedulerView() {
  const pd = useStore(s => s.pendingTasks)
  const tasks = pd.pending_tasks || []
  const maxScore = tasks.length > 0 ? Math.max(...tasks.map(t => t.score), 1) : 1

  return (
    <div className="glass-card p-5 fade-in">
      <div className="section-title">
        <span className="dot" style={{ background: 'var(--accent-cyan)' }} />
        4 · Scheduler View
      </div>

      {/* Formula */}
      <div className="formula-box mb-4">
        <div className="text-[0.6rem] text-gray-400 mb-1">Scoring Formula:</div>
        {pd.formula || 'score = w1×priority - w2×est_time - w3×data_cost'}
        <div className="text-[0.55rem] text-gray-500 mt-1">
          Weights: w1={pd.weights?.w1 || '—'}, w2={pd.weights?.w2 || '—'}, w3={pd.weights?.w3 || '—'}
        </div>
      </div>

      {/* Pending tasks table */}
      {tasks.length === 0 ? (
        <div className="text-xs text-gray-500 py-3 text-center">
          No pending tasks — all tasks are assigned or completed
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div className="sched-row header">
            <div>Type</div>
            <div>Task ID</div>
            <div>Priority</div>
            <div>Est Time</div>
            <div>Data Cost</div>
            <div>Score</div>
          </div>
          {tasks.map((t, i) => (
            <div key={t.task_id} className="sched-row">
              <div><span className={`type-badge ${t.task_type}`}>{t.task_type.slice(0, 3)}</span></div>
              <div className="truncate text-gray-300" title={t.task_id}>{t.task_id.slice(0, 12)}…</div>
              <div className="text-amber-400">{t.priority}</div>
              <div className="text-gray-400">{t.est_time}s</div>
              <div className="text-gray-400">{t.data_cost}</div>
              <div>
                <span className={`font-semibold ${i === 0 ? 'text-cyan-400' : 'text-gray-300'}`}>
                  {t.score}
                </span>
                <div className="score-bar mt-1">
                  <div className="score-bar-fill" style={{ width: `${Math.max(0, (t.score / maxScore) * 100)}%` }} />
                </div>
              </div>
            </div>
          ))}
          {tasks.length > 0 && (
            <div className="mt-2 text-[0.6rem] text-cyan-400/70">
              ▸ Next pick: <span className="font-semibold text-cyan-300">{tasks[0].task_id.slice(0, 12)}…</span>
              {' '}(highest score {tasks[0].score})
            </div>
          )}
        </div>
      )}
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   5. SHARED STORAGE
   ═══════════════════════════════════════════════════════════════════════════ */
function SharedStorage() {
  const jobs = useStore(s => s.jobs)
  const storageData = useStore(s => s.storageData)

  return (
    <div className="glass-card p-5 fade-in">
      <div className="section-title">
        <span className="dot" style={{ background: 'var(--accent-purple)' }} />
        5 · Shared Storage
      </div>
      {jobs.length === 0 ? (
        <div className="text-xs text-gray-500 py-4 text-center">No jobs yet</div>
      ) : (
        <div className="space-y-3 max-h-64 overflow-y-auto">
          {jobs.map(job => {
            const sd = storageData[job.id] || {}
            return (
              <div key={job.id} className="p-3 rounded-lg border border-gray-800 bg-gray-900/40">
                <div className="text-[0.65rem] font-mono text-gray-400 mb-2 truncate">
                  Job {job.id.slice(0, 8)}…
                </div>
                <div className="space-y-1">
                  <div className="storage-step">
                    <div className={`storage-icon ${sd.script_generated ? 'done' : 'waiting'}`}>
                      {sd.script_generated ? '✓' : '○'}
                    </div>
                    <div>
                      <div className="text-xs text-gray-300">Script Generated</div>
                      <div className="text-[0.6rem] text-gray-500">
                        {sd.script_generated ? 'script.json ready' : 'Waiting for generation worker'}
                      </div>
                    </div>
                  </div>
                  <div className="storage-step">
                    <div className={`storage-icon ${(sd.frames_rendered || 0) > 0 ? 'done' : 'waiting'}`}>
                      {(sd.frames_rendered || 0) > 0 ? '✓' : '○'}
                    </div>
                    <div className="flex-1">
                      <div className="text-xs text-gray-300">Frames Rendered</div>
                      <div className="text-[0.6rem] text-gray-500">
                        {sd.frames_rendered || 0} / {job.frames} PNG files
                      </div>
                      <div className="progress-bar mt-1">
                        <div className="progress-fill bg-blue-500"
                          style={{ width: `${job.frames > 0 ? ((sd.frames_rendered || 0) / job.frames) * 100 : 0}%` }} />
                      </div>
                    </div>
                  </div>
                  <div className="storage-step">
                    <div className={`storage-icon ${sd.video_ready ? 'done' : 'waiting'}`}>
                      {sd.video_ready ? '✓' : '○'}
                    </div>
                    <div>
                      <div className="text-xs text-gray-300">Final MP4</div>
                      <div className="text-[0.6rem] text-gray-500">
                        {sd.video_ready ? (
                          <a href={job.video_url} target="_blank" rel="noreferrer"
                            className="text-blue-400 hover:text-blue-300">Download video ↗</a>
                        ) : 'Waiting for assembly'}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   6. METRICS
   ═══════════════════════════════════════════════════════════════════════════ */
function Metrics() {
  const stats = useStore(s => s.stats)

  const metrics = [
    { label: 'Total Jobs', value: stats.total_jobs ?? 0, color: 'var(--accent-blue)' },
    { label: 'Active Jobs', value: stats.active_jobs ?? 0, color: 'var(--accent-amber)' },
    { label: 'Completed', value: stats.completed_jobs ?? 0, color: 'var(--accent-green)' },
    { label: 'Rendered Frames', value: stats.total_rendered_frames ?? 0, color: 'var(--accent-cyan)' },
    { label: 'Pending Tasks', value: stats.pending_tasks ?? 0, color: 'var(--accent-rose)' },
    { label: 'Assigned Tasks', value: stats.assigned_tasks ?? 0, color: 'var(--accent-blue)' },
    { label: 'Tasks Done', value: stats.completed_tasks ?? 0, color: 'var(--accent-green)' },
    { label: 'Avg Time (s)', value: stats.avg_completion_time ?? '—', color: 'var(--accent-purple)' },
  ]

  return (
    <div className="glass-card p-5 fade-in">
      <div className="section-title">
        <span className="dot" style={{ background: 'var(--accent-rose)' }} />
        6 · Metrics
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {metrics.map(m => (
          <div key={m.label} className="metric-card">
            <div className="metric-value" style={{ color: m.color }}>{m.value}</div>
            <div className="metric-label">{m.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   ACTIVE JOBS LIST (compact)
   ═══════════════════════════════════════════════════════════════════════════ */
function AnimationPreview({ job }) {
  const [frameIndex, setFrameIndex] = useState(0)
  const visibleFrames = Math.max(0, job.rendered_frames || 0)

  useEffect(() => { setFrameIndex(0) }, [job.id])

  useEffect(() => {
    if (!job.frame_url || visibleFrames < 2) return
    const timer = setInterval(() => setFrameIndex(c => (c + 1) % visibleFrames), 80)
    return () => clearInterval(timer)
  }, [job.frame_url, visibleFrames])

  if (job.frame_url && visibleFrames > 0) {
    const idx = Math.min(frameIndex, visibleFrames - 1)
    const src = job.frame_url.replace('{frame_index}', String(idx))
    return <img src={`${src}?v=${visibleFrames}`} alt={`Frame ${idx}`} className="h-full w-full object-cover" />
  }
  return <div className="text-[0.6rem] text-gray-600 flex items-center justify-center h-full">Waiting…</div>
}

function ActiveJobs() {
  const jobs = useStore(s => s.jobs)

  const getStatusColor = (s) => {
    const m = {
      queued: 'bg-gray-500', generating: 'bg-amber-500 animate-pulse',
      rendering: 'bg-blue-500 animate-pulse', assembling: 'bg-purple-500 animate-pulse',
      completed: 'bg-green-500', failed: 'bg-red-500',
    }
    return m[s] || 'bg-gray-500'
  }

  const getProgress = (j) => {
    if (j.status === 'completed') return 100
    if (!j.frames) return 0
    if (j.status === 'generating') return 10
    if (j.status === 'assembling') return 95
    return Math.min(90, Math.round(((j.rendered_frames || 0) / j.frames) * 90))
  }

  if (jobs.length === 0) return null

  return (
    <div className="glass-card p-5 fade-in">
      <div className="section-title">
        <span className="dot" style={{ background: 'var(--text-secondary)' }} />
        Active Jobs
      </div>
      <div className="space-y-3">
        {jobs.map(job => (
          <div key={job.id}
            className="grid md:grid-cols-[160px_1fr] gap-4 p-3 rounded-lg border border-gray-800 bg-gray-900/30 hover:border-gray-700 transition-colors">
            <div className="aspect-video bg-gray-950 rounded-md border border-gray-800 overflow-hidden flex items-center justify-center">
              <AnimationPreview job={job} />
            </div>
            <div className="flex flex-col justify-between gap-2 min-w-0">
              <div className="flex justify-between items-start gap-2">
                <div className="min-w-0">
                  <p className="text-[0.6rem] text-gray-500 font-mono truncate">{job.id}</p>
                  <p className="text-sm font-medium text-gray-200">
                    {job.frames}f · {job.balls} balls · chunk={job.render_chunk_size} · pri={job.priority} · λ={job.lambda_value}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs capitalize text-gray-400">{job.status}</span>
                  <div className={`h-2.5 w-2.5 rounded-full ${getStatusColor(job.status)}`} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-[0.6rem] text-gray-500 mb-1">
                  <span>{job.rendered_frames || 0}/{job.frames} frames</span>
                  <span>{job.tasks_completed}/{job.tasks_total} tasks</span>
                  {job.completion_time && <span className="text-green-400">{job.completion_time.toFixed(1)}s</span>}
                </div>
                <div className="progress-bar">
                  <div className="progress-fill bg-gradient-to-r from-blue-500 to-purple-500"
                    style={{ width: `${getProgress(job)}%` }} />
                </div>
                {job.video_url && (
                  <a href={job.video_url} target="_blank" rel="noreferrer"
                    className="inline-flex mt-2 text-xs text-blue-400 hover:text-blue-300">
                    ▶ Open MP4 output
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════
   MAIN APP
   ═══════════════════════════════════════════════════════════════════════════ */
function App() {
  const pollAll = useStore(s => s.pollAll)

  useEffect(() => {
    pollAll()
    const interval = setInterval(pollAll, 2000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6">
      {/* Header */}
      <header className="mb-6 pb-4 border-b border-gray-800">
        <h1 className="text-2xl sm:text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400">
          Cloud Collaborative Animation
        </h1>
        <p className="text-gray-500 text-xs mt-1 tracking-wide">
          Distributed Smart Orchestrator — Task DAG · Worker Pool · Scheduler Scoring · Shared Storage
        </p>
      </header>

      {/* 6-panel dashboard grid */}
      <div className="grid lg:grid-cols-2 gap-5">
        {/* Left column */}
        <div className="space-y-5">
          <JobSubmission />
          <TaskDagPanel />
          <SchedulerView />
        </div>
        {/* Right column */}
        <div className="space-y-5">
          <WorkerPool />
          <SharedStorage />
          <Metrics />
        </div>
      </div>

      {/* Active jobs list — full width below */}
      <div className="mt-5">
        <ActiveJobs />
      </div>
    </div>
  )
}

export default App
