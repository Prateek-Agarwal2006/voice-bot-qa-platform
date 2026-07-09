import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { submitJob, submitJobUpload, JUDGE_MODEL_PRESETS, URL_PROVIDERS } from "./api";
import { JudgeModelSelect, type JudgeModelOption } from "./JudgeModelSelect";

const DEFAULT_MODEL = "gpt-4o-mini";
const ACCEPTED_EXTENSIONS = [".mp3", ".wav", ".m4a"];

const ALL_MODELS: JudgeModelOption[] = Object.entries(JUDGE_MODEL_PRESETS).flatMap(
  ([provider, models]) =>
    models.map((m) => ({
      provider,
      value: m,
      label: `${provider} — ${m}`,
    })),
);

type IngestMode = "url" | "file";

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function IngestTab() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<IngestMode>("url");
  const [url, setUrl] = useState("");
  const [urlProvider, setUrlProvider] = useState("direct");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [judgeModel, setJudgeModel] = useState(DEFAULT_MODEL);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function switchMode(next: IngestMode) {
    setMode(next);
    setError(null);
    if (next === "url") {
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } else {
      setUrl("");
    }
  }

  function handleFileChange(file: File | null) {
    if (!file) {
      setSelectedFile(null);
      return;
    }
    if (!isAcceptedFile(file)) {
      setError(`Unsupported file type. Allowed: ${ACCEPTED_EXTENSIONS.join(", ")}`);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    setError(null);
    setSelectedFile(file);
  }

  async function handleSubmit() {
    if (mode === "url" && !url.trim()) return;
    if (mode === "file" && !selectedFile) return;

    setSubmitting(true);
    setError(null);
    try {
      if (mode === "url") {
        await submitJob(url.trim(), judgeModel, urlProvider);
      } else {
        await submitJobUpload(selectedFile!, judgeModel);
      }
      navigate("/evaluations");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = mode === "url" ? url.trim().length > 0 : selectedFile !== null;

  return (
    <div className="glass-card p-4">
      <div className="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-4">
        <div>
          <h2 className="h5 mb-1">Upload Recording</h2>
          <p className="text-secondary small mb-0">
            Submit a public audio URL or upload an MP3/WAV/M4A file. Audio is used only for transcription and is not kept after the transcript is saved.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-sm btn-outline-secondary"
          onClick={() => navigate("/evaluations")}
        >
          Back to Voice Bot Evaluation
        </button>
      </div>

      <div className="d-flex gap-2 mb-4">
        <button
          type="button"
          className={`btn btn-sm ${mode === "url" ? "btn-run text-white" : "btn-outline-secondary"}`}
          onClick={() => switchMode("url")}
          disabled={submitting}
        >
          URL
        </button>
        <button
          type="button"
          className={`btn btn-sm ${mode === "file" ? "btn-run text-white" : "btn-outline-secondary"}`}
          onClick={() => switchMode("file")}
          disabled={submitting}
        >
          Upload file
        </button>
      </div>

      <div className="row g-3 mb-4">
        {mode === "url" ? (
          <>
            <div className="col-12 col-lg-2">
              <label className="form-label small fw-semibold text-secondary mb-1">
                URL Provider
              </label>
              <select
                className="form-select"
                value={urlProvider}
                onChange={(e) => setUrlProvider(e.target.value)}
                disabled={submitting}
              >
                {URL_PROVIDERS.map(({ label, value }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div className="col-12 col-lg-5">
              <label className="form-label small fw-semibold text-secondary mb-1">
                Audio URL
              </label>
              <input
                type="url"
                className="form-control"
                placeholder="https://example.com/recording.wav"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void handleSubmit(); }}
                disabled={submitting}
              />
            </div>
          </>
        ) : (
          <div className="col-12 col-lg-7">
            <label className="form-label small fw-semibold text-secondary mb-1">
              Audio file
            </label>
            <input
              ref={fileInputRef}
              type="file"
              className="form-control"
              accept={ACCEPTED_EXTENSIONS.join(",")}
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
              disabled={submitting}
            />
            {selectedFile && (
              <p className="small text-secondary mb-0 mt-2">
                Selected: {selectedFile.name}
              </p>
            )}
          </div>
        )}
        <div className="col-12 col-lg-4">
          <label className="form-label small fw-semibold text-secondary mb-1">
            Judge Model
          </label>
          <JudgeModelSelect
            options={ALL_MODELS}
            value={judgeModel}
            onChange={setJudgeModel}
            disabled={submitting}
          />
        </div>
        <div className="col-12 col-lg-1 d-flex align-items-end">
          <button
            type="button"
            className="btn btn-run text-white w-100"
            onClick={() => void handleSubmit()}
            disabled={submitting || !canSubmit}
          >
            {submitting ? "…" : "Upload"}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger border-0 py-2 mb-4">{error}</div>
      )}
    </div>
  );
}
