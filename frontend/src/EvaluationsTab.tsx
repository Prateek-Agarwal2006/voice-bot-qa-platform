import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { JobStageTimeline } from "./JobStageTimeline";
import { fetchJob, fetchRecordings, type Recording } from "./api";
import { STATUS_LABEL, timelineFromApiStages } from "./jobStages";

const TERMINAL = new Set(["done", "failed"]);

function statusColor(status: string): string {
  if (status === "done") return "var(--success)";
  if (status === "failed") return "var(--danger)";
  return "var(--warning)";
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className="chip" style={{ color: statusColor(status), padding: "2px 10px", fontSize: "0.72rem" }}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function shortId(id: string) {
  return id.slice(0, 8) + "…";
}

function shortUrl(url: string | null) {
  if (!url) return "—";
  try {
    const u = new URL(url);
    const path = u.pathname.split("/").pop() ?? u.pathname;
    return path.length > 32 ? path.slice(0, 32) + "…" : path;
  } catch {
    return url.length > 40 ? url.slice(0, 40) + "…" : url;
  }
}

function sourceLabel(rec: Recording): string {
  if (rec.ingestion_source === "upload" && rec.source_filename) {
    return `Upload: ${rec.source_filename}`;
  }
  return shortUrl(rec.source_url);
}

const STATUS_FILTERS = ["all", "done", "failed", "pending", "evaluating"];

export function EvaluationsTab() {
  const navigate = useNavigate();
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const status = statusFilter === "all" ? undefined : statusFilter;
      const data = await fetchRecordings(status);
      setRecordings(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load evaluations");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter]);

  useEffect(() => { void load(); }, [load]);

  const activeKey = recordings
    .filter((rec) => !TERMINAL.has(rec.status))
    .map((rec) => rec.recording_id)
    .sort()
    .join(",");

  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    const activeIds = activeKey ? activeKey.split(",") : [];
    if (activeIds.length === 0) return;

    pollRef.current = setInterval(async () => {
      try {
        const updates = await Promise.all(
          activeIds.map(async (id) => {
            try {
              return await fetchJob(id);
            } catch {
              return null;
            }
          }),
        );

        setRecordings((prev) =>
          prev.map((rec) => {
            const latest = updates.find((u) => u?.recording_id === rec.recording_id);
            if (!latest) return rec;
            return {
              ...rec,
              status: latest.status,
              error_message: latest.error_message,
              stages: latest.stages ?? rec.stages,
            };
          }),
        );
      } catch {
        // keep last known state
      }
    }, 3000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [activeKey]);

  if (loading) {
    return (
      <div className="glass-card p-4 text-center">
        <div className="spinner-ring mx-auto mb-3" />
        <p className="text-secondary mb-0">Loading evaluations…</p>
      </div>
    );
  }

  return (
    <div className="glass-card p-4">
      <div className="d-flex flex-wrap justify-content-between align-items-center gap-3 mb-4">
        <div>
          <h2 className="h5 mb-1">Voice Bot Evaluation</h2>
          <p className="text-secondary small mb-0">Browse submitted recordings and their evaluation stages.</p>
        </div>
        <div className="d-flex align-items-center gap-2">
          <select
            className="form-select form-select-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ minWidth: 130 }}
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s} value={s}>{s === "all" ? "All statuses" : (STATUS_LABEL[s] ?? s)}</option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            onClick={() => void load(true)}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
          <button
            type="button"
            className="btn btn-sm btn-run text-white"
            onClick={() => navigate("/evaluations/upload")}
          >
            Upload
          </button>
        </div>
      </div>

      {error && <div className="alert alert-danger border-0 py-2 mb-4">{error}</div>}

      {recordings.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🎙</div>
          <h3 className="h5 mb-2">No recordings yet</h3>
          <p className="text-secondary mb-3 mx-auto" style={{ maxWidth: 380 }}>
            Upload a recording URL or audio file to start evaluation.
          </p>
          <button
            type="button"
            className="btn btn-run text-white"
            onClick={() => navigate("/evaluations/upload")}
          >
            Upload recording
          </button>
        </div>
      ) : (
        <div className="eval-list">
          {recordings.map((rec) => {
            const steps = timelineFromApiStages(rec.stages);

            return (
              <Fragment key={rec.recording_id}>
                <div className="eval-card">
                  <div className="eval-card-header-static">
                    <div className="eval-card-meta">
                      <span className="mono small">{shortId(rec.recording_id)}</span>
                      <StatusBadge status={rec.status} />
                      <span className="small text-secondary">{sourceLabel(rec)}</span>
                    </div>
                    <div className="eval-card-aside">
                      <span className="small text-secondary">
                        {new Date(rec.created_at).toLocaleString()}
                      </span>
                      <Link
                        to={`/evaluations/${rec.recording_id}`}
                        className="btn btn-sm btn-outline-secondary"
                      >
                        Open
                      </Link>
                    </div>
                  </div>

                  {steps.length > 0 && (
                    <div className="eval-card-stages px-3 pb-3">
                      <JobStageTimeline
                        steps={steps}
                        recordingId={rec.recording_id}
                        judgeModel={rec.judge_model}
                      />
                    </div>
                  )}
                </div>
              </Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
}
