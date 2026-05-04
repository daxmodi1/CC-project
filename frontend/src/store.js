import { create } from 'zustand'

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

const withAbsoluteUrls = (job) => ({
  ...job,
  preview_url: job.preview_url ? `${API_URL}${job.preview_url}` : null,
  frame_url: job.frame_url ? `${API_URL}${job.frame_url}` : null,
  video_url: job.video_url ? `${API_URL}${job.video_url}` : null
})

export const useStore = create((set, get) => ({
  // ─── State ──────────────────────────────────────────
  jobs: [],
  workers: [],
  stats: {},
  pendingTasks: { weights: {}, formula: '', pending_tasks: [] },
  dagData: {},       // keyed by job_id
  storageData: {},   // keyed by job_id
  loading: false,
  error: null,

  // ─── Actions ────────────────────────────────────────
  fetchJobs: async () => {
    try {
      const res = await fetch(`${API_URL}/jobs/`);
      if (!res.ok) throw new Error("Failed to fetch jobs");
      const data = await res.json();
      set({ jobs: data.map(withAbsoluteUrls), error: null });
    } catch (err) {
      set({ error: err.message });
    }
  },

  fetchWorkers: async () => {
    try {
      const res = await fetch(`${API_URL}/workers/`);
      if (!res.ok) return;
      set({ workers: await res.json() });
    } catch { /* silent */ }
  },

  fetchStats: async () => {
    try {
      const res = await fetch(`${API_URL}/stats/`);
      if (!res.ok) return;
      set({ stats: await res.json() });
    } catch { /* silent */ }
  },

  fetchPendingTasks: async () => {
    try {
      const res = await fetch(`${API_URL}/tasks/pending`);
      if (!res.ok) return;
      set({ pendingTasks: await res.json() });
    } catch { /* silent */ }
  },

  fetchDag: async (jobId) => {
    try {
      const res = await fetch(`${API_URL}/jobs/${jobId}/dag`);
      if (!res.ok) return;
      const data = await res.json();
      set((s) => ({ dagData: { ...s.dagData, [jobId]: data } }));
    } catch { /* silent */ }
  },

  fetchStorage: async (jobId) => {
    try {
      const res = await fetch(`${API_URL}/storage/${jobId}`);
      if (!res.ok) return;
      const data = await res.json();
      set((s) => ({ storageData: { ...s.storageData, [jobId]: data } }));
    } catch { /* silent */ }
  },

  submitJob: async (numFrames, numBalls, chunkSize, priority, lambda) => {
    set({ loading: true });
    try {
      const res = await fetch(`${API_URL}/jobs/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          num_frames: numFrames,
          num_balls: numBalls,
          render_chunk_size: chunkSize,
          priority: priority,
          lambda_value: lambda,
        }),
      });
      if (!res.ok) throw new Error("Failed to submit job");
      await get().fetchJobs();
      set({ error: null });
    } catch (err) {
      set({ error: err.message });
    } finally {
      set({ loading: false });
    }
  },

  // Poll everything at once
  pollAll: async () => {
    const { fetchJobs, fetchWorkers, fetchStats, fetchPendingTasks } = get();
    await Promise.all([fetchJobs(), fetchWorkers(), fetchStats(), fetchPendingTasks()]);
    // Also refresh dag + storage for each job
    const jobs = get().jobs;
    for (const job of jobs) {
      get().fetchDag(job.id);
      get().fetchStorage(job.id);
    }
  },
}))
