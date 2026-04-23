"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SeriesForecast } from "./types";

interface Row {
  date: string;
  history?: number;
  median?: number;
  band?: [number, number];
}

function buildRows(series: SeriesForecast): Row[] {
  const map = new Map<string, Row>();
  for (const h of series.history) {
    map.set(h.date, { date: h.date, history: h.value });
  }
  for (const f of series.forecast) {
    const row = map.get(f.date) ?? { date: f.date };
    row.median = f.median;
    row.band = [f.lo, f.hi];
    map.set(f.date, row);
  }
  return Array.from(map.values()).sort((a, b) => (a.date < b.date ? -1 : 1));
}

function fmt(v: number | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("ko-KR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

export default function SeriesCard({ series }: { series: SeriesForecast }) {
  const rows = buildRows(series);
  const last = series.history[series.history.length - 1];
  const first = series.forecast[0];
  const end = series.forecast[series.forecast.length - 1];
  const changePct =
    last && end ? ((end.median - last.value) / Math.abs(last.value)) * 100 : null;

  return (
    <div className="card">
      <div>
        <h3>{series.title}</h3>
        <div className="sub">
          <span>단위: {series.unit}</span>
          {series.tags.map((t) => (
            <span key={t} className="tag">#{t}</span>
          ))}
        </div>
      </div>

      <div className="stat-row">
        <span>현재: <b>{fmt(last?.value)}</b> ({last?.date ?? "—"})</span>
        <span>
          {series.forecast_start} 예측:{" "}
          <b>{fmt(first?.median)}</b>
        </span>
        <span>
          {end?.date} 예측:{" "}
          <b>{fmt(end?.median)}</b>
          {changePct != null && (
            <>
              {" "}
              <span style={{ color: changePct >= 0 ? "var(--good)" : "var(--danger)" }}>
                ({changePct >= 0 ? "+" : ""}
                {fmt(changePct, 1)}%)
              </span>
            </>
          )}
        </span>
      </div>

      <div className="chart">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`band-${series.id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#7aa7ff" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#7aa7ff" stopOpacity={0.06} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#243063" strokeDasharray="2 3" />
            <XAxis
              dataKey="date"
              tick={{ fill: "#95a0c9", fontSize: 11 }}
              interval="preserveStartEnd"
              minTickGap={32}
            />
            <YAxis
              tick={{ fill: "#95a0c9", fontSize: 11 }}
              domain={["auto", "auto"]}
              width={56}
            />
            <Tooltip
              contentStyle={{
                background: "#111735",
                border: "1px solid #243063",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "#e6e9f5" }}
              formatter={(v: number | [number, number], name: string) => {
                if (Array.isArray(v))
                  return [`${fmt(v[0])} ~ ${fmt(v[1])}`, "80% 밴드"];
                return [fmt(v), name];
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11, color: "#95a0c9" }} />
            <ReferenceLine
              x={series.forecast_start}
              stroke="#7aa7ff"
              strokeDasharray="4 4"
              label={{ value: "예측 시작", fill: "#7aa7ff", fontSize: 10, position: "top" }}
            />
            <Area
              type="monotone"
              dataKey="band"
              stroke="none"
              fill={`url(#band-${series.id})`}
              name="80% 밴드"
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="history"
              stroke="#e6e9f5"
              dot={false}
              strokeWidth={1.6}
              name="실적"
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="median"
              stroke="#7aa7ff"
              dot={false}
              strokeWidth={1.8}
              strokeDasharray="5 4"
              name="BISTRO (median)"
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {series.note && (
        <div className="sub" style={{ fontSize: 11 }}>※ {series.note}</div>
      )}
    </div>
  );
}
