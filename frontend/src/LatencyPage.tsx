import { useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import type { ShellContext } from "./AppShell";
import { LatencyChart } from "./LatencyChart";
import type { Sample } from "./api";

type ResultsView = "chart" | "table";

function formatMs(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value.toFixed(1)} ms`;
}

function latencyClass(ms: number | null | undefined): string {
  if (ms == null) return "";
  if (ms <= 200) return "latency-good";
  if (ms <= 500) return "";
  if (ms <= 1000) return "latency-mid";
  return "latency-bad";
}

function summarizeRun(samples: Sample[]) {
  const withAvg = samples.filter((s) => s.avg_ms != null);
  const success = samples.reduce((sum, s) => sum + s.success_count, 0);
  const total = samples.reduce((sum, s) => sum + s.total_count, 0);
  const fastest = withAvg.reduce<Sample | null>(
    (best, s) => (!best || (s.p50_ms ?? Infinity) < (best.p50_ms ?? Infinity) ? s : best),
    null,
  );
  const slowest = withAvg.reduce<Sample | null>(
    (worst, s) => (!worst || (s.p50_ms ?? 0) > (worst.p50_ms ?? 0) ? s : worst),
    null,
  );
  const avgOfAvgs =
    withAvg.length > 0
      ? withAvg.reduce((sum, s) => sum + (s.avg_ms ?? 0), 0) / withAvg.length
      : null;

  return { success, total, fastest, slowest, avgOfAvgs };
}

export function LatencyPage() {
  const { runs, error } = useOutletContext<ShellContext>();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [resultsView, setResultsView] = useState<ResultsView>("chart");

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? runs[0] ?? null,
    [runs, selectedRunId],
  );

  const runSummary = useMemo(
    () => (selectedRun ? summarizeRun(selectedRun.samples) : null),
    [selectedRun],
  );

  return (
    <>
      <header className="mb-4 pb-2">
        <p className="section-label mb-2">Cross-region measurement</p>
        <h1 className="hero-title display-6 mb-3">Compare time-to-first-byte across your prods</h1>
        <p className="text-secondary mb-0 col-lg-8">
          Probe workers collect latency on a schedule and export results to the central store. This
          dashboard is read-only: browse the latest and historical runs per source region and model.
        </p>
      </header>

      {error && (
        <div className="alert alert-danger py-2 border-0 mb-4" role="alert">
          {error}
        </div>
      )}

      <div className="glass-card p-4">
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-3 mb-4">
          <div>
            <h2 className="h5 mb-1">Results</h2>
            <p className="text-secondary small mb-0">Toggle chart or table view for the selected run</p>
          </div>
          <div className="d-flex flex-wrap align-items-center gap-2">
            <div className="btn-group view-toggle" role="group" aria-label="Results view">
              <button
                type="button"
                className={`btn btn-sm ${resultsView === "chart" ? "btn-primary" : "btn-outline-secondary"}`}
                onClick={() => setResultsView("chart")}
                aria-pressed={resultsView === "chart"}
              >
                Chart
              </button>
              <button
                type="button"
                className={`btn btn-sm ${resultsView === "table" ? "btn-primary" : "btn-outline-secondary"}`}
                onClick={() => setResultsView("table")}
                aria-pressed={resultsView === "table"}
              >
                Table
              </button>
            </div>
            <select
              className="form-select form-select-sm"
              style={{ minWidth: "280px" }}
              value={selectedRun?.id ?? ""}
              onChange={(event) => setSelectedRunId(event.target.value)}
            >
              {runs.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.model_label} · {run.source_label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {selectedRun && runSummary ? (
          <>
            <div className="row g-3 mb-4">
              <div className="col-sm-6 col-xl-3">
                <div className="stat-tile h-100">
                  <div className="label">Mean TTFB</div>
                  <div className={`value mono ${latencyClass(runSummary.avgOfAvgs)}`}>
                    {formatMs(runSummary.avgOfAvgs)}
                  </div>
                  <div className="hint">Across {selectedRun.samples.length} targets</div>
                </div>
              </div>
              <div className="col-sm-6 col-xl-3">
                <div className="stat-tile h-100">
                  <div className="label">Fastest (p50)</div>
                  <div className={`value mono ${latencyClass(runSummary.fastest?.p50_ms)}`}>
                    {formatMs(runSummary.fastest?.p50_ms)}
                  </div>
                  <div className="hint text-truncate">{runSummary.fastest?.target_label ?? "—"}</div>
                </div>
              </div>
              <div className="col-sm-6 col-xl-3">
                <div className="stat-tile h-100">
                  <div className="label">Slowest (p50)</div>
                  <div className={`value mono ${latencyClass(runSummary.slowest?.p50_ms)}`}>
                    {formatMs(runSummary.slowest?.p50_ms)}
                  </div>
                  <div className="hint text-truncate">{runSummary.slowest?.target_label ?? "—"}</div>
                </div>
              </div>
              <div className="col-sm-6 col-xl-3">
                <div className="stat-tile h-100">
                  <div className="label">Success rate</div>
                  <div className="value mono">
                    {runSummary.total > 0
                      ? `${Math.round((runSummary.success / runSummary.total) * 100)}%`
                      : "—"}
                  </div>
                  <div className="hint">
                    {runSummary.success}/{runSummary.total} calls
                  </div>
                </div>
              </div>
            </div>

            <div className="d-flex flex-wrap gap-2 mb-3">
              <span className="chip">{new Date(selectedRun.created_at).toLocaleString()}</span>
              <span className="chip">N = {selectedRun.n}</span>
              <span className="chip">Timeout {selectedRun.timeout_ms} ms</span>
              <span className="chip">{selectedRun.source_label}</span>
            </div>

            {resultsView === "chart" ? (
              <LatencyChart samples={selectedRun.samples} />
            ) : (
              <div className="table-responsive rounded-3 border" style={{ borderColor: "rgba(148,163,184,0.12)" }}>
                <table className="table results-table align-middle mb-0">
                  <thead>
                    <tr>
                      <th>Target</th>
                      <th>Avg</th>
                      <th>p50</th>
                      <th>p95</th>
                      <th>Min</th>
                      <th>Max</th>
                      <th>Success</th>
                      <th>Errors</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRun.samples.map((sample) => (
                      <tr key={sample.target_region}>
                        <td className="fw-medium">{sample.target_label}</td>
                        <td className={`mono ${latencyClass(sample.avg_ms)}`}>{formatMs(sample.avg_ms)}</td>
                        <td className={`mono ${latencyClass(sample.p50_ms)}`}>{formatMs(sample.p50_ms)}</td>
                        <td className={`mono ${latencyClass(sample.p95_ms)}`}>{formatMs(sample.p95_ms)}</td>
                        <td className="mono">{formatMs(sample.min_ms)}</td>
                        <td className="mono">{formatMs(sample.max_ms)}</td>
                        <td className="mono">
                          {sample.success_count}/{sample.total_count}
                        </td>
                        <td className="small text-secondary">
                          {Object.keys(sample.errors).length === 0
                            ? "—"
                            : Object.entries(sample.errors)
                                .map(([kind, count]) => `${kind}: ${count}`)
                                .join(", ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">⚡</div>
            <h3 className="h5 mb-2">No measurements yet</h3>
            <p className="text-secondary mb-0 mx-auto" style={{ maxWidth: "420px" }}>
              Scheduled probe workers will appear here once they export their first collection cycle.
              Wait for the next collect interval, then refresh.
            </p>
          </div>
        )}
      </div>
    </>
  );
}
