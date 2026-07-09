import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import { fetchConfig, fetchRuns, type ProbeConfig, type Run } from "./api";

const NAV_TABS = [
  { to: "/latency", label: "Latency Dashboard", match: (path: string) => path.startsWith("/latency") },
  {
    to: "/evaluations",
    label: "Voice Bot Evaluation",
    match: (path: string) => path.startsWith("/evaluations"),
  },
] as const;

type ShellContext = {
  config: ProbeConfig;
  runs: Run[];
  refreshing: boolean;
  refresh: () => void;
  error: string | null;
};

export type { ShellContext };

export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const [config, setConfig] = useState<ProbeConfig | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const [configData, runData] = await Promise.all([fetchConfig(), fetchRuns()]);
      setConfig(configData);
      setRuns(runData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (loading || !config) {
    return (
      <div className="app-shell loading-shell">
        <div className="text-center">
          <div className="spinner-ring mx-auto mb-3" />
          <p className="text-secondary mb-0">{error ?? "Loading dashboard..."}</p>
        </div>
      </div>
    );
  }

  const configHint = config.config_path
    ? config.config_path.split("/").slice(-2).join("/")
    : null;

  const shell: ShellContext = {
    config,
    runs,
    refreshing,
    refresh: () => void loadData(true),
    error,
  };

  return (
    <div className="app-shell">
      <nav className="topbar">
        <div className="container py-3 d-flex align-items-center justify-content-between gap-3">
          <button
            type="button"
            className="brand-home d-flex align-items-center gap-3"
            onClick={() => navigate("/")}
            aria-label="Go to landing page"
          >
            <div className="brand-mark mono">VQ</div>
            <div className="text-start">
              <div className="fw-semibold lh-sm">Voice Bot QA</div>
              <div className="small text-secondary">Latency probe + eval pipeline</div>
            </div>
          </button>
          <div className="d-flex flex-wrap gap-2 justify-content-end">
            <span className="chip chip-accent">{config.config_version}</span>
            {configHint && <span className="chip">{configHint}</span>}
            <span className="chip">{runs.length} runs</span>
            {location.pathname.startsWith("/latency") && (
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary"
                onClick={() => void loadData(true)}
                disabled={refreshing}
              >
                {refreshing ? "Refreshing..." : "Refresh"}
              </button>
            )}
          </div>
        </div>
        <div className="tab-bar container">
          {NAV_TABS.map(({ to, label, match }) => (
            <NavLink
              key={to}
              to={to}
              className={() => `tab-btn ${match(location.pathname) ? "tab-btn-active" : ""}`}
            >
              {label}
            </NavLink>
          ))}
        </div>
      </nav>

      <main className="container py-4 py-lg-5">
        <Outlet context={shell} />
      </main>
    </div>
  );
}
