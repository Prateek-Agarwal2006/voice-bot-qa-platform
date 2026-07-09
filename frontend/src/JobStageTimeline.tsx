import type { TimelineStep } from "./jobStages";

type Props = {
  steps: TimelineStep[];
  recordingId?: string;
  judgeModel?: string;
};

function formatTime(iso?: string | null) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return null;
  }
}

export function JobStageTimeline({ steps, recordingId, judgeModel }: Props) {
  if (steps.length === 0) return null;

  return (
    <div className="job-stage-panel">
      {(recordingId || judgeModel) && (
        <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
          {recordingId && <span className="chip mono" style={{ fontSize: "0.72rem" }}>{recordingId}</span>}
          {judgeModel && <span className="chip mono" style={{ fontSize: "0.72rem" }}>{judgeModel}</span>}
        </div>
      )}

      <ol className="job-stage-list">
        {steps.map((step) => {
          const time = formatTime(step.at);
          return (
            <li key={step.key} className={`job-stage-item is-${step.state}`}>
              <div className="job-stage-rail" aria-hidden="true">
                <span className="job-stage-dot">
                  {step.state === "active" && (
                    <span className="spinner-ring job-stage-spinner" />
                  )}
                  {step.state === "completed" && <span className="job-stage-check">✓</span>}
                  {step.state === "failed" && <span className="job-stage-x">!</span>}
                </span>
              </div>
              <div className="job-stage-body">
                <div className="job-stage-title-row">
                  <span className="job-stage-title">{step.label}</span>
                  {time && <span className="job-stage-time mono">{time}</span>}
                </div>
                {step.state === "active" && (
                  <div className="job-stage-hint">In progress…</div>
                )}
                {step.state === "failed" && step.detail && (
                  <div className="job-stage-error">{step.detail}</div>
                )}
                {step.state === "failed" && !step.detail && (
                  <div className="job-stage-error">Failed at this stage</div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
