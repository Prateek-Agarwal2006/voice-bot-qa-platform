import type { StageEvent } from "./api";

export const STATUS_LABEL: Record<string, string> = {
  pending: "Queued",
  downloading: "Downloading audio",
  transcribing: "Transcribing",
  structuring: "Building conversation",
  evaluating: "Evaluating with judge",
  done: "Complete",
  failed: "Failed",
};

export type StageState = "completed" | "active" | "failed" | "upcoming";

export type TimelineStep = {
  key: string;
  label: string;
  state: StageState;
  detail?: string | null;
  at?: string | null;
};

/** Map durable API stage events into the timeline UI model. */
export function timelineFromApiStages(stages: StageEvent[] | undefined | null): TimelineStep[] {
  if (!stages || stages.length === 0) return [];
  return stages.map((s, index) => ({
    key: `${s.stage}-${index}`,
    label: s.label || STATUS_LABEL[s.stage] || s.stage,
    state: (s.state as StageState) || "completed",
    detail: s.detail,
    at: s.at || null,
  }));
}
