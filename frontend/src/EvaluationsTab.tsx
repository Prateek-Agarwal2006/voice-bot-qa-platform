import { Fragment, useCallback, useEffect, useState } from "react";
import { EvaluationDetail } from "./EvaluationDetail";
import { fetchRecordings, type Recording } from "./api";

const STATUS_LABEL: Record<string, string> = {
  pending: "Queued",
  downloading: "Downloading",
  transcribing: "Transcribing",
  structuring: "Structuring",
  evaluating: "Evaluating",
  done: "Done",
  failed: "Failed",
};

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

const STATUS_FILTERS = ["all", "done", "failed", "pending", "evaluating"];

export function EvaluationsTab() {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

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

  function toggleRow(id: string) {
    setSelectedId((prev) => (prev === id ? null : id));
  }

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
          <h2 className="h5 mb-1">Evaluations</h2>
          <p className="text-secondary small mb-0">Browse submitted recordings and their evaluation status.</p>
        </div>
        <div className="d-flex align-items-center gap-2">
          <select
            className="form-select form-select-sm"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setSelectedId(null); }}
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
        </div>
      </div>

      {error && <div className="alert alert-danger border-0 py-2 mb-4">{error}</div>}

      {recordings.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🎙</div>
          <h3 className="h5 mb-2">No recordings yet</h3>
          <p className="text-secondary mb-0 mx-auto" style={{ maxWidth: 380 }}>
            Submit a recording URL in the Ingest tab to start evaluation.
          </p>
        </div>
      ) : (
        <div className="table-responsive rounded-3 border" style={{ borderColor: "rgba(148,163,184,0.12)" }}>
          <table className="table results-table align-middle mb-0">
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Source</th>
                <th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {recordings.map((rec) => (
                <Fragment key={rec.recording_id}>
                  <tr
                    onClick={() => toggleRow(rec.recording_id)}
                    style={{ cursor: "pointer" }}
                    className={selectedId === rec.recording_id ? "table-row-selected" : ""}
                  >
                    <td className="mono small">{shortId(rec.recording_id)}</td>
                    <td><StatusBadge status={rec.status} /></td>
                    <td className="small text-secondary">{shortUrl(rec.source_url)}</td>
                    <td className="small text-secondary">{new Date(rec.created_at).toLocaleString()}</td>
                  </tr>
                  {selectedId === rec.recording_id && rec.status === "done" && (
                    <tr>
                      <td colSpan={4} className="p-0">
                        <div className="eval-detail-wrapper">
                          <EvaluationDetail recordingId={rec.recording_id} />
                        </div>
                      </td>
                    </tr>
                  )}
                  {selectedId === rec.recording_id && rec.status === "failed" && (
                    <tr>
                      <td colSpan={4}>
                        <div className="small text-danger py-2">
                          {rec.error_message ?? "Evaluation failed — no details available."}
                        </div>
                      </td>
                    </tr>
                  )}
                  {selectedId === rec.recording_id && !["done", "failed"].includes(rec.status) && (
                    <tr>
                      <td colSpan={4}>
                        <div className="small text-secondary py-2">
                          Evaluation in progress — refresh to check for updates.
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
