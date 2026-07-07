import { useEffect, useRef, useState } from "react";
import { fetchJob, submitJob, JUDGE_MODEL_PRESETS, URL_PROVIDERS, type JobStatus } from "./api";

const DEFAULT_MODEL = "gpt-4o-mini";

const ALL_MODELS = Object.entries(JUDGE_MODEL_PRESETS).flatMap(([provider, models]) =>
  models.map((m) => ({ label: `${provider} — ${m}`, value: m }))
);

const STATUS_LABEL: Record<string, string> = {
  pending: "Queued",
  downloading: "Downloading audio",
  transcribing: "Transcribing",
  structuring: "Building conversation",
  evaluating: "Evaluating with judge",
  done: "Complete",
  failed: "Failed",
};

const TERMINAL = new Set(["done", "failed"]);

function statusColor(status: string): string {
  if (status === "done") return "var(--success)";
  if (status === "failed") return "var(--danger)";
  return "var(--warning)";
}

function StatusChip({ status }: { status: string }) {
  return (
    <span className="chip" style={{ color: statusColor(status) }}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

export function IngestTab() {
  const [url, setUrl] = useState("");
  const [urlProvider, setUrlProvider] = useState("direct");
  const [judgeModel, setJudgeModel] = useState(DEFAULT_MODEL);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  function stopPoll() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }

  async function handleSubmit() {
    if (!url.trim()) return;
    stopPoll();
    setSubmitting(true);
    setError(null);
    setJob(null);
    try {
      const created = await submitJob(url.trim(), judgeModel, urlProvider);
      setJob(created);
      if (!TERMINAL.has(created.status)) {
        pollRef.current = setInterval(async () => {
          try {
            const latest = await fetchJob(created.recording_id);
            setJob(latest);
            if (TERMINAL.has(latest.status)) stopPoll();
          } catch {
            stopPoll();
          }
        }, 3000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="glass-card p-4">
      <div className="mb-4">
        <h2 className="h5 mb-1">Submit Recording</h2>
        <p className="text-secondary small mb-0">
          Provide a publicly accessible audio URL and choose a judge model. The eval worker will download, transcribe, and score it automatically.
        </p>
      </div>

      <div className="row g-3 mb-4">
        <div className="col-12 col-lg-2">
          <label className="form-label small fw-semibold text-secondary mb-1">
            URL Provider
          </label>
          <select
            className="form-select"
            value={urlProvider}
            onChange={(e) => setUrlProvider(e.target.value)}
            disabled={submitting}
          >
            {URL_PROVIDERS.map(({ label, value }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        <div className="col-12 col-lg-5">
          <label className="form-label small fw-semibold text-secondary mb-1">
            Ingest Link
          </label>
          <input
            type="url"
            className="form-control"
            placeholder="https://example.com/recording.wav"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void handleSubmit(); }}
            disabled={submitting}
          />
        </div>
        <div className="col-12 col-lg-4">
          <label className="form-label small fw-semibold text-secondary mb-1">
            Judge Model
          </label>
          <select
            className="form-select"
            value={judgeModel}
            onChange={(e) => setJudgeModel(e.target.value)}
            disabled={submitting}
          >
            {ALL_MODELS.map(({ label, value }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        <div className="col-12 col-lg-1 d-flex align-items-end">
          <button
            type="button"
            className="btn btn-run text-white w-100"
            onClick={() => void handleSubmit()}
            disabled={submitting || !url.trim()}
          >
            {submitting ? "…" : "Submit"}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger border-0 py-2 mb-4">{error}</div>
      )}

      {job && (
        <div className="stat-tile">
          <div className="d-flex align-items-center gap-2 mb-2">
            {!TERMINAL.has(job.status) && (
              <div className="spinner-ring" style={{ width: 18, height: 18, borderWidth: 2, flexShrink: 0 }} />
            )}
            <StatusChip status={job.status} />
            <span className="chip mono" style={{ fontSize: "0.72rem" }}>{judgeModel}</span>
          </div>
          <div className="mono small text-secondary">{job.recording_id}</div>
          {job.status === "failed" && job.error_message && (
            <div className="small text-danger mt-2">{job.error_message}</div>
          )}
          {job.status === "done" && (
            <div className="small mt-2" style={{ color: "var(--success)" }}>
              Evaluation complete — open the Evaluations tab to view results.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
