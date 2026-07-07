import { useEffect, useState } from "react";
import {
  fetchConversation,
  fetchScores,
  type Conversation,
  type DimensionScore,
  type Evaluation,
} from "./api";

const DIMENSION_ORDER = [
  "task_success",
  "conversation_quality",
  "response_alignment",
  "user_disappointment",
  "response_latency",
  "dead_air",
  "interruptions",
];

function scoreColor(score: number): string {
  if (score >= 8) return "var(--success)";
  if (score >= 5) return "var(--warning)";
  return "var(--danger)";
}

function ScoreCard({ dimKey, dim }: { dimKey: string; dim: DimensionScore }) {
  const [expanded, setExpanded] = useState(false);
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
        <span
          className="chip"
          style={{ color: dim.success ? "var(--success)" : "var(--danger)", fontSize: "0.7rem", padding: "3px 8px" }}
        >
          {dim.success ? "Pass" : "Fail"}
        </span>
      </div>

      <div className="score-bar-track mb-2">
        <div className="score-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>

      <button
        type="button"
        className="btn btn-link p-0 small text-secondary"
        style={{ fontSize: "0.75rem", textDecoration: "none" }}
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? "Hide rationale ▲" : "Show rationale ▼"}
      </button>
      {expanded && (
        <p className="small text-secondary mt-2 mb-0" style={{ lineHeight: 1.55 }}>
          {dim.rationale || "No rationale provided."}
        </p>
      )}
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

interface Props {
  recordingId: string;
}

export function EvaluationDetail({ recordingId }: Props) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([fetchConversation(recordingId), fetchScores(recordingId)])
      .then(([conv, ev]) => { setConversation(conv); setEvaluation(ev); })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load detail"))
      .finally(() => setLoading(false));
  }, [recordingId]);

  if (loading) {
    return (
      <div className="text-center py-4">
        <div className="spinner-ring mx-auto" />
      </div>
    );
  }

  if (error) {
    return <div className="alert alert-danger border-0 py-2">{error}</div>;
  }

  const orderedDims = DIMENSION_ORDER.filter((k) => evaluation?.dimensions[k]);

  return (
    <div className="eval-detail">
      {evaluation && (
        <div className="mb-4">
          <p className="section-label mb-2">Judge scores</p>
          <div className="d-flex gap-2 flex-wrap mb-3">
            <span className="chip chip-accent">{evaluation.judge_model}</span>
            <span className="chip">{new Date(evaluation.evaluated_at).toLocaleString()}</span>
          </div>
          <div className="score-grid">
            {orderedDims.map((key) => (
              <ScoreCard key={key} dimKey={key} dim={evaluation.dimensions[key]} />
            ))}
          </div>
        </div>
      )}

      {conversation && <TranscriptPanel conversation={conversation} />}
    </div>
  );
}
