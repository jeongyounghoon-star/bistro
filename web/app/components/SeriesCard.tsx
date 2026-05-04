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

interface SeriesCardProps {
  series: SeriesForecast;
  index: number;
}

const CHART = {
  grid: "#dee1e6",
  history: "#0a0b0d",
  median: "#0052ff",
  band: "#0052ff",
  forecastLine: "#0046ad",
  tick: "#5b616e",
  tooltipBg: "#ffffff",
  tooltipBorder: "#dee1e6",
};

function buildRows(series: SeriesForecast): Row[] {
  const map = new Map<string, Row>();
  for (const point of series.history) {
    map.set(point.date, { date: point.date, history: point.value });
  }
  for (const point of series.forecast) {
    const row = map.get(point.date) ?? { date: point.date };
    row.median = point.median;
    row.band = [point.lo, point.hi];
    map.set(point.date, row);
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

function fmtValue(v: number | undefined, unit: string): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (unit === "%" || unit === "KRW/USD") return fmt(v, 2);
  if (unit === "pt" || unit === "index") return fmt(v, 1);
  return v.toLocaleString("ko-KR", {
    notation: Math.abs(v) >= 1_000_000 ? "compact" : "standard",
    maximumFractionDigits: Math.abs(v) >= 1_000 ? 1 : 2,
  });
}

function inferSource(series: SeriesForecast): string {
  if (series.note?.startsWith("BIS")) return "BIS";
  if (series.note?.startsWith("ECOS")) return "ECOS";
  if (series.id.startsWith("bok_")) return "ECOS";
  if (
    series.id === "kospi" ||
    series.id === "usdkrw" ||
    series.id === "ktb_3y" ||
    series.id === "corp_aa_3y" ||
    series.id === "cd_91"
  ) {
    return "Naver Finance";
  }
  return "Local";
}

function frequencyLabel(series: SeriesForecast): string {
  return series.frequency === "Q" ? "분기" : "월간";
}

function trendLabel(changePct: number | null): string {
  if (changePct == null) return "데이터 없음";
  if (Math.abs(changePct) < 0.05) return "변동 없음";
  return changePct > 0 ? "상승" : "하락";
}

export default function SeriesCard({ series, index }: SeriesCardProps) {
  const rows = buildRows(series);
  const last = series.history[series.history.length - 1];
  const first = series.forecast[0];
  const end = series.forecast[series.forecast.length - 1];
  const changePct =
    last && end && last.value !== 0
      ? ((end.median - last.value) / Math.abs(last.value)) * 100
      : null;
  const source = inferSource(series);
  const trend = trendLabel(changePct);
  const trendClass =
    changePct == null || Math.abs(changePct) < 0.05
      ? "neutral"
      : changePct > 0
        ? "positive"
        : "negative";
  const cardClass = `bento-card series-card ${index % 5 === 0 ? "series-card-wide" : ""}`;

  return (
    <article className={cardClass} aria-label={`${series.title} 예측 카드`}>
      <div className="series-card-top">
        <div>
          <span className="series-kicker">{source}</span>
          <h3>{series.title}</h3>
          <div className="series-meta">
            <span>{frequencyLabel(series)}</span>
            <span>단위 {series.unit}</span>
            <span>{series.forecast_start}부터 전망</span>
          </div>
        </div>
        <div className="tag-row">
          {series.tags.map((tag) => (
            <span key={tag} className="tag">
              {tag}
            </span>
          ))}
        </div>
      </div>

      <div className="series-stats">
        <div className="series-stat">
          <span>최근 실측</span>
          <strong>{fmtValue(last?.value, series.unit)}</strong>
          <small>{last?.date ?? "—"}</small>
        </div>
        <div className="series-stat">
          <span>예측 시작</span>
          <strong>{fmtValue(first?.median, series.unit)}</strong>
          <small>{series.forecast_start}</small>
        </div>
        <div className="series-stat">
          <span>마지막 전망</span>
          <strong>{fmtValue(end?.median, series.unit)}</strong>
          <small>{end?.date ?? "—"}</small>
        </div>
        <div className={`series-stat trend-stat ${trendClass}`}>
          <span>현재 대비</span>
          <strong>
            {changePct == null ? "—" : `${changePct >= 0 ? "+" : ""}${fmt(changePct, 1)}%`}
          </strong>
          <small>{trend}</small>
        </div>
      </div>

      <div className="chart-frame">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 12, right: 14, left: 2, bottom: 0 }}>
            <defs>
              <linearGradient id={`band-${series.id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CHART.band} stopOpacity={0.28} />
                <stop offset="100%" stopColor={CHART.band} stopOpacity={0.04} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="2 6" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: CHART.tick, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={34}
            />
            <YAxis
              tick={{ fill: CHART.tick, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              domain={["auto", "auto"]}
              tickFormatter={(value: number) => fmtValue(value, series.unit)}
              width={58}
            />
            <Tooltip
              contentStyle={{
                background: CHART.tooltipBg,
                border: `1px solid ${CHART.tooltipBorder}`,
                borderRadius: 12,
                boxShadow: "0 4px 12px rgba(0, 0, 0, 0.04)",
                color: "#0a0b0d",
                fontSize: 12,
              }}
              labelStyle={{ color: "#0a0b0d", fontWeight: 400 }}
              formatter={(value: number | [number, number], name: string) => {
                if (Array.isArray(value)) {
                  return [
                    `${fmtValue(value[0], series.unit)} ~ ${fmtValue(value[1], series.unit)}`,
                    "80% 구간",
                  ];
                }
                return [fmtValue(value, series.unit), name];
              }}
            />
            <Legend wrapperStyle={{ color: CHART.tick, fontSize: 11 }} />
            <ReferenceLine
              x={series.forecast_start}
              stroke={CHART.forecastLine}
              strokeDasharray="4 4"
              label={{
                value: "예측 시작",
                fill: CHART.forecastLine,
                fontSize: 10,
                position: "top",
              }}
            />
            <Area
              type="monotone"
              dataKey="band"
              stroke="none"
              fill={`url(#band-${series.id})`}
              name="80% 구간"
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="history"
              stroke={CHART.history}
              dot={false}
              strokeWidth={1.9}
              name="실측"
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="median"
              stroke={CHART.median}
              dot={false}
              strokeWidth={2}
              strokeDasharray="5 4"
              name="BISTRO 중앙값"
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {series.note && <p className="series-note">데이터 메모: {series.note}</p>}
    </article>
  );
}
