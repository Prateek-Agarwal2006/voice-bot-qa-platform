import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ErrorBar,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Sample } from "./api";

interface Props {
  samples: Sample[];
}

interface ChartRow {
  name: string;
  avg: number;
  p50: number;
  p95: number;
  errorHigh: number;
  fill: string;
}

function barColor(ms: number): string {
  if (ms <= 200) return "#34d399";
  if (ms <= 500) return "#38bdf8";
  if (ms <= 1000) return "#fbbf24";
  return "#f87171";
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { payload: ChartRow }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tooltip p-3 rounded-3 border">
      <div className="fw-semibold mb-2">{label}</div>
      <div className="small d-grid gap-1 mono">
        <span>Avg: {row.avg.toFixed(1)} ms</span>
        <span>p50: {row.p50.toFixed(1)} ms</span>
        <span>p95: {row.p95.toFixed(1)} ms</span>
      </div>
    </div>
  );
}

export function LatencyChart({ samples }: Props) {
  const data = useMemo(
    () =>
      samples.map((sample) => {
        const avg = sample.avg_ms ?? 0;
        return {
          name: sample.target_label,
          avg,
          p50: sample.p50_ms ?? 0,
          p95: sample.p95_ms ?? 0,
          errorHigh: sample.avg_ms && sample.max_ms ? sample.max_ms - sample.avg_ms : 0,
          fill: barColor(avg),
        };
      }),
    [samples],
  );

  if (samples.length === 0) {
    return <p className="text-secondary mb-0">No samples to chart.</p>;
  }

  return (
    <div className="chart-panel chart-wrap">
      <ResponsiveContainer width="100%" height={360}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
          <defs>
            <linearGradient id="barGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ffffff" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#ffffff" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="4 4" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            angle={-24}
            textAnchor="end"
            height={64}
            interval={0}
          />
          <YAxis
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickFormatter={(value) => `${value}ms`}
            width={52}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(56, 189, 248, 0.06)" }} />
          <Bar dataKey="avg" radius={[8, 8, 0, 0]} maxBarSize={48}>
            {data.map((entry) => (
              <Cell key={entry.name} fill={entry.fill} />
            ))}
            <ErrorBar dataKey="errorHigh" direction="y" width={3} stroke="#f97316" strokeWidth={2} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
