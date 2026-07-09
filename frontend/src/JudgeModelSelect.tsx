import { useEffect, useId, useMemo, useRef, useState } from "react";

export type JudgeModelOption = {
  label: string;
  value: string;
  provider: string;
};

type Props = {
  options: JudgeModelOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
};

export function JudgeModelSelect({ options, value, onChange, disabled }: Props) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const selected = options.find((o) => o.value === value) ?? null;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        o.value.toLowerCase().includes(q) ||
        o.provider.toLowerCase().includes(q),
    );
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    function onDocMouseDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function openPicker() {
    if (disabled) return;
    setOpen(true);
    setQuery("");
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  function pick(option: JudgeModelOption) {
    onChange(option.value);
    setOpen(false);
    setQuery("");
  }

  return (
    <div className="judge-model-select" ref={rootRef}>
      <button
        type="button"
        className="form-select judge-model-trigger text-start"
        onClick={openPicker}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
      >
        <span className="judge-model-trigger-text">
          {selected ? selected.label : value || "Select judge model"}
        </span>
      </button>

      {open && (
        <div className="judge-model-dropdown" role="presentation">
          <input
            ref={inputRef}
            type="search"
            className="form-control form-control-sm judge-model-search"
            placeholder="Search provider or model…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoComplete="off"
            aria-label="Search judge models"
          />
          <ul id={listId} className="judge-model-list" role="listbox">
            {filtered.length === 0 && (
              <li className="judge-model-empty text-secondary small px-3 py-2">No matches</li>
            )}
            {filtered.map((option) => (
              <li key={`${option.provider}:${option.value}`} role="option" aria-selected={option.value === value}>
                <button
                  type="button"
                  className={`judge-model-option${option.value === value ? " is-active" : ""}`}
                  onClick={() => pick(option)}
                >
                  <span className="judge-model-option-provider">{option.provider}</span>
                  <span className="judge-model-option-id mono">{option.value}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
