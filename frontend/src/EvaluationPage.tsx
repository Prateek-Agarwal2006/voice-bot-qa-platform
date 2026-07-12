import { Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  evaluationMeta,
  fetchConversation,
  fetchJob,
  fetchScores,
  type Conversation,
  type DimensionScore,
  type Evaluation,
  type JobStatus,
} from "./api";
import { JobStageTimeline } from "./JobStageTimeline";
import { timelineFromApiStages } from "./jobStages";

const DIMENSION_ORDER = [
  "task_success",
  "call_outcome",
  "response_alignment",
  "faithfulness",
  "conversation_quality",
  "conversation_progression",
  "user_disappointment",
  "sentiment_trajectory",
  "response_latency",
  "dead_air",
  "interruptions",
];

function scoreColor(score: number): string {
  if (score >= 8) return "var(--success)";
  if (score >= 5) return "var(--warning)";
  return "var(--danger)";
}

const OUTCOME_COLOR: Record<string, string> = {
  resolved: "var(--success)",
  escalated: "var(--warning)",
};

function ViolationList({ dim }: { dim: DimensionScore }) {
  if (!dim.violations || dim.violations.length === 0) return null;
  return (
    <>
      <p className="section-label mb-1 mt-3">Violations</p>
      <ul className="small text-secondary mb-0 ps-3" style={{ lineHeight: 1.55 }}>
        {dim.violations.map((v, i) => (
          <li key={i}>
            <span className="mono">{v.type}</span>
            {v.turn_index != null && <> — turn [{v.turn_index}]</>}
            {v.quote && <> — “{v.quote}”</>}
          </li>
        ))}
      </ul>
    </>
  );
}

function OutcomeCard({ dimKey, dim }: { dimKey: string; dim: DimensionScore }) {
  const outcome = dim.outcome ?? "unknown";
  const color = OUTCOME_COLOR[outcome] ?? "var(--danger)";
  return (
    <div className="stat-tile score-card">
      <div className="d-flex justify-content-between align-items-start mb-2">
        <div>
          <div className="label mb-1">{dim.name || dimKey}</div>
          <div className="value" style={{ color, fontSize: "1.1rem" }}>
            {outcome.replace(/_/g, " ")}
          </div>
        </div>
        <span className="chip" style={{ fontSize: "0.7rem", padding: "3px 8px" }}>Outcome</span>
      </div>

      <p className="section-label mb-1">Reasoning</p>
      <p className="small text-secondary mb-0" style={{ lineHeight: 1.55 }}>
        {dim.rationale || "No rationale provided."}
      </p>
      <ViolationList dim={dim} />
    </div>
  );
}

function ScoreCard({ dimKey, dim }: { dimKey: string; dim: DimensionScore }) {
  if (dim.outcome) {
    return <OutcomeCard dimKey={dimKey} dim={dim} />;
  }

  const display = dim.judge_score ?? dim.score * (dim.judge_score_max ?? 10);
  const max = dim.judge_score_max ?? 10;
  const pct = Math.min(100, (display / max) * 100);
  const color = scoreColor(display);

  return (
    <div className="stat-tile score-card">
      <div className="d-flex justify-content-between align-items-start mb-2">
        <div>
          <div className="label mb-1">{dim.name || dimKey}</div>
          <div className="value mono" style={{ color, fontSize: "1.1rem" }}>
            {display.toFixed(1)}
            <span className="text-secondary" style={{ fontSize: "0.75rem", fontWeight: 400 }}>
              /{max}
            </span>
          </div>
        </div>
        <div className="d-flex gap-1">
          {dim.metric === "deterministic" && (
            <span className="chip" style={{ fontSize: "0.7rem", padding: "3px 8px" }}>Computed</span>
          )}
          <span
            className="chip"
            style={{ color: dim.success ? "var(--success)" : "var(--danger)", fontSize: "0.7rem", padding: "3px 8px" }}
          >
            {dim.success ? "Pass" : "Fail"}
          </span>
        </div>
      </div>

      <div className="score-bar-track mb-3">
        <div className="score-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>

      <p className="section-label mb-1">Reasoning</p>
      <p className="small text-secondary mb-0" style={{ lineHeight: 1.55 }}>
        {dim.rationale || "No rationale provided."}
      </p>
      <ViolationList dim={dim} />
    </div>
  );
}

function TranscriptPanel({ conversation }: { conversation: Conversation }) {
  return (
    <div>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <h3 className="h6 mb-0">Transcript</h3>
        <span className="chip">{conversation.turn_count} turns</span>
      </div>
      <div className="transcript-scroll">
        {conversation.turns.map((turn, i) => {
          const isBot = turn.speaker?.toLowerCase().includes("bot") || turn.channel_index === 0;
          return (
            <div key={i} className={`turn-bubble ${isBot ? "turn-bot" : "turn-customer"}`}>
              <div className="turn-meta">
                <span className="turn-speaker">{turn.speaker ?? (isBot ? "Voice Bot" : "Customer")}</span>
                {turn.start != null && turn.end != null && (
                  <span className="turn-time mono">
                    {turn.start.toFixed(1)}s – {turn.end.toFixed(1)}s
                  </span>
                )}
              </div>
              <div className="turn-text">{turn.text}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function EvaluationPage() {
  const { recordingId = "" } = useParams();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!recordingId) return;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchConversation(recordingId).catch(() => null),
      fetchScores(recordingId).catch(() => null),
      fetchJob(recordingId).catch(() => null),
    ])
      .then(([conv, ev, jobStatus]) => {
        setConversation(conv);
        setEvaluation(ev);
        setJob(jobStatus);
        if (!conv && !ev && !jobStatus) {
          setError("Evaluation not found");
        }
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load detail"))
      .finally(() => setLoading(false));
  }, [recordingId]);

  if (loading) {
    return (
      <div className="glass-card p-4 text-center">
        <div className="spinner-ring mx-auto mb-3" />
        <p className="text-secondary mb-0">Loading evaluation…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card p-4">
        <div className="alert alert-danger border-0 py-2 mb-3">{error}</div>
        <Link to="/evaluations" className="btn btn-sm btn-outline-secondary">
          Back to Voice Bot Evaluation
        </Link>
      </div>
    );
  }

  const orderedDims = DIMENSION_ORDER.filter((k) => evaluation?.dimensions[k]);
  const stages = timelineFromApiStages(job?.stages);
  const meta = evaluationMeta(evaluation);
  const confidence = meta?.transcript_confidence;

  return (
    <div className="glass-card p-4">
      <div className="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-4">
        <div>
          <p className="section-label mb-2">Evaluation detail</p>
          <h1 className="h4 mb-1">Recording scores & reasoning</h1>
          <p className="mono small text-secondary mb-0">{recordingId}</p>
        </div>
        <Link to="/evaluations" className="btn btn-sm btn-outline-secondary">
          Back to Voice Bot Evaluation
        </Link>
      </div>

      <div className="mb-4">
        <JobStageTimeline
          steps={stages}
          recordingId={recordingId}
          judgeModel={evaluation?.judge_model ?? undefined}
        />
      </div>

      {evaluation && (
        <div className="mb-4">
          <p className="section-label mb-2">Judge scores</p>
          <div className="d-flex gap-2 flex-wrap mb-3">
            <span className="chip chip-accent">{evaluation.judge_model}</span>
            <span className="chip">{new Date(evaluation.evaluated_at).toLocaleString()}</span>
            {confidence?.level === "low" && (
              <span className="chip" style={{ color: "var(--warning)" }} title="Scribe language_probability below threshold — scores may be less reliable">
                Low transcript confidence
                {confidence.language_probability != null &&
                  ` (${Math.round(confidence.language_probability * 100)}%)`}
              </span>
            )}
          </div>
          <div className="score-grid">
            {orderedDims.map((key) => (
              <ScoreCard key={key} dimKey={key} dim={evaluation.dimensions[key]} />
            ))}
          </div>
        </div>
      )}

      {!evaluation && job?.status === "failed" && (
        <div className="alert alert-danger border-0 py-2 mb-4">
          {job.error_message ?? "Evaluation failed — no scores available."}
          {conversation && (
            <div className="small mt-2 mb-0" style={{ color: "#fecaca" }}>
              Transcript was saved before the failure — scroll down to review it.
            </div>
          )}
        </div>
      )}

      {conversation && (
        <div className="mb-2">
          {!evaluation && job?.status === "failed" && (
            <p className="section-label mb-2">Transcript (available despite judge failure)</p>
          )}
          <TranscriptPanel conversation={conversation} />
        </div>
      )}

      {!conversation && job?.status === "failed" && (
        <p className="small text-secondary mb-0">
          No transcript was saved — the job failed before structuring completed.
        </p>
      )}
    </div>
  );
}
