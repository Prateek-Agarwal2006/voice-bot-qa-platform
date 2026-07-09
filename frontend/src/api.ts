export interface LLMConfigEntry {
  target_id: string;
  label: string;
  streamEnabled?: boolean;
  group?: string;
  deployment?: string;
  provider?: string;
  llm_config_id?: string;
  partnerId?: number | string;
  useDynamicRouting?: boolean;
  routerUrl?: string;
  client_identifier?: string;
  user?: string;
}

export interface ProbeConfig {
  config_version: string;
  config_path?: string;
  default_n: number;
  default_timeout_ms: number;
  llm_configs: LLMConfigEntry[];
}

export interface RawCallRecord {
  index: number;
  success: boolean;
  ttfb_ms?: number | null;
  error_kind?: string | null;
  error_message?: string | null;
}

export interface Sample {
  target_region: string;
  target_label: string;
  avg_ms: number | null;
  min_ms: number | null;
  p50_ms: number | null;
  p95_ms: number | null;
  max_ms: number | null;
  success_count: number;
  total_count: number;
  errors: Record<string, number>;
  calls: RawCallRecord[];
}

export interface Run {
  id: string;
  created_at: string;
  model: string;
  model_label: string;
  source_region: string;
  source_label: string;
  config_version: string;
  n: number;
  timeout_ms: number;
  samples: Sample[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchConfig(): Promise<ProbeConfig> {
  return request<ProbeConfig>("/api/config");
}

export function fetchRuns(): Promise<Run[]> {
  return request<Run[]>("/api/runs");
}

// ── Eval / Jobs ─────────────────────────────────────────────────────────────

export interface StageEvent {
  stage: string;
  state: string;
  label: string;
  detail?: string | null;
  at: string;
}

export interface Recording {
  recording_id: string;
  status: string;
  ingestion_source: string;
  source_url: string | null;
  source_filename: string | null;
  judge_model: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  stages?: StageEvent[];
}

export const URL_PROVIDERS: { label: string; value: string }[] = [
  { label: "Direct URL", value: "direct" },
  { label: "Google Drive", value: "google_drive" },
];

export const JUDGE_MODEL_PRESETS: Record<string, string[]> = {
  OpenAI: ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
  Anthropic: [
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-opus-4-8",
    "anthropic/claude-haiku-4-5-20251001",
  ],
  Google: [
    "gemini/gemini-2.0-flash",
    "gemini/gemini-2.0-flash-lite",
    "gemini/gemini-2.5-flash",
    "gemini/gemini-2.5-flash-lite",
    "gemini/gemini-2.5-pro",
  ],
  "Vertex Gemini": [
    "vertex_ai/gemini-2.0-flash",
    "vertex_ai/gemini-2.0-flash-lite",
    "vertex_ai/gemini-2.5-flash",
    "vertex_ai/gemini-2.5-flash-lite",
    "vertex_ai/gemini-2.5-pro",
    "vertex_ai/gemini-3-flash-preview",
    "vertex_ai/gemini-3-pro-preview",
    "vertex_ai/gemini-3.1-flash-lite",
    "vertex_ai/gemini-3.1-pro-preview",
    "vertex_ai/gemini-3.5-flash",
  ],
  // Google Cloud / Anthropic Agent Platform IDs (Claude on Vertex).
  // Source: https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai
  // Plus older Model Garden IDs still documented by Google Cloud / LiteLLM.
  "Vertex Claude": [
    // Current / latest
    "vertex_ai/claude-fable-5",
    "vertex_ai/claude-sonnet-5",
    "vertex_ai/claude-opus-4-8",
    "vertex_ai/claude-opus-4-7",
    "vertex_ai/claude-opus-4-6",
    "vertex_ai/claude-sonnet-4-6",
    "vertex_ai/claude-sonnet-4-5@20250929",
    "vertex_ai/claude-opus-4-5@20251101",
    "vertex_ai/claude-haiku-4-5@20251001",
    // Deprecated but still listed on Anthropic Vertex docs
    "vertex_ai/claude-sonnet-4@20250514",
    "vertex_ai/claude-opus-4-1@20250805",
    "vertex_ai/claude-opus-4@20250514",
    "vertex_ai/claude-3-5-haiku@20241022",
    // Retired / legacy Model Garden (may be unavailable in some projects)
    "vertex_ai/claude-3-7-sonnet@20250219",
    "vertex_ai/claude-3-5-sonnet-v2@20241022",
    "vertex_ai/claude-3-5-sonnet@20240620",
    "vertex_ai/claude-3-opus@20240229",
    "vertex_ai/claude-3-sonnet@20240229",
    "vertex_ai/claude-3-haiku@20240307",
  ],
};

export interface Turn {
  speaker: string;
  text: string;
  start?: number | null;
  end?: number | null;
  turn_index?: number | null;
  channel_index?: number | null;
}

export interface Conversation {
  recording_id: string;
  turns: Turn[];
  derived_signals: Record<string, unknown>;
  turn_count: number;
}

export interface DimensionScore {
  score: number;
  score_max: number;
  rationale: string;
  success: boolean;
  metric: string;
  name: string;
  judge_score?: number;
  judge_score_max?: number;
}

export interface Evaluation {
  recording_id: string;
  judge_model: string;
  dimensions: Record<string, DimensionScore>;
  evaluated_at: string;
}

export interface JobStatus {
  recording_id: string;
  status: string;
  error_message: string | null;
  stages?: StageEvent[];
}

export function fetchRecordings(status?: string): Promise<Recording[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<Recording[]>(`/api/evaluations${qs}`);
}

export function fetchConversation(recordingId: string): Promise<Conversation> {
  return request<Conversation>(`/api/evaluations/${recordingId}/conversation`);
}

export function fetchScores(recordingId: string): Promise<Evaluation> {
  return request<Evaluation>(`/api/evaluations/${recordingId}/scores`);
}

export function submitJob(sourceUrl: string, judgeModel: string, urlProvider: string): Promise<JobStatus> {
  return request<JobStatus>("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl, judge_model: judgeModel, url_provider: urlProvider }),
  });
}

export async function submitJobUpload(file: File, judgeModel: string): Promise<JobStatus> {
  const form = new FormData();
  form.append("file", file);
  form.append("judge_model", judgeModel);
  const response = await fetch("/api/jobs/upload", {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<JobStatus>;
}

export function fetchJob(recordingId: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${recordingId}`);
}
