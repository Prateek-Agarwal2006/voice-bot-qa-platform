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

export interface Recording {
  recording_id: string;
  status: string;
  ingestion_source: string;
  source_url: string | null;
  judge_model: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export const URL_PROVIDERS: { label: string; value: string }[] = [
  { label: "Direct URL", value: "direct" },
  { label: "Google Drive", value: "google_drive" },
];

export const JUDGE_MODEL_PRESETS: Record<string, string[]> = {
  OpenAI: ["gpt-4o-mini", "gpt-4o"],
  Anthropic: ["anthropic/claude-sonnet-4-6", "anthropic/claude-opus-4-8"],
  Google: ["gemini/gemini-2.0-flash", "gemini/gemini-2.5-pro"],
  Vertex: [
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

export function fetchJob(recordingId: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${recordingId}`);
}
