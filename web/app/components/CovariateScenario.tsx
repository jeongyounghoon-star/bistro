"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ForecastBundle, ForecastPoint, SeriesForecast } from "./types";

interface PredictorState {
  enabled: boolean;
  endValue: number;
}

interface ScenarioRow {
  date: string;
  baseline: number;
  adjusted: number;
}

const TARGET_FALLBACKS = ["kr_cpi_yoy", "bok_cpi", "kospi"];
const PREDICTOR_FALLBACKS = [
  "kr_policy_rate",
  "bok_base_rate",
  "usdkrw",
  "ktb_3y",
  "bok_unemployment",
  "kospi",
];

const CHART = {
  grid: "#dee1e6",
  baseline: "#0052ff",
  adjusted: "#0046ad",
  tick: "#5b616e",
  tooltipBg: "#ffffff",
  tooltipBorder: "#dee1e6",
};

function formatValue(value: number | undefined, unit: string, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "-";
  if (unit === "pt" || unit === "index") digits = 1;
  return value.toLocaleString("ko-KR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function lastHistory(series: SeriesForecast): number {
  return series.history[series.history.length - 1]?.value ?? 0;
}

function forecastEnd(series: SeriesForecast): number {
  return series.forecast[series.forecast.length - 1]?.median ?? lastHistory(series);
}

function latestForecast(series: SeriesForecast, index: number): ForecastPoint {
  return series.forecast[Math.min(index, series.forecast.length - 1)];
}

function valueStep(series: SeriesForecast): number {
  if (series.unit === "%" || series.unit === "KRW/USD") return 0.1;
  if (series.unit === "pt" || series.unit === "index") return 1;
  return 100;
}

function valueRange(series: SeriesForecast): [number, number] {
  const values = [
    ...series.history.slice(-36).map((point) => point.value),
    ...series.forecast.map((point) => point.median),
  ].filter((value) => Number.isFinite(value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, Math.abs(max) * 0.08, 1);
  return [min - span * 0.35, max + span * 0.35];
}

function historyScale(series: SeriesForecast): number {
  const values = series.history.slice(-60).map((point) => point.value);
  if (values.length < 2) return Math.max(Math.abs(lastHistory(series)) * 0.05, 1);
  const deltas = values.slice(1).map((value, index) => Math.abs(value - values[index]));
  const sorted = deltas.filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  const p75 = sorted[Math.floor(sorted.length * 0.75)] ?? 0;
  return Math.max(p75 * 6, Math.abs(lastHistory(series)) * 0.04, 0.25);
}

function directionFor(target: SeriesForecast, predictor: SeriesForecast): number {
  const key = `${target.id}:${predictor.id}`;
  const explicit: Record<string, number> = {
    "kr_cpi_yoy:kr_policy_rate": -1,
    "kr_cpi_yoy:bok_base_rate": -1,
    "kr_cpi_yoy:usdkrw": 1,
    "kr_cpi_yoy:ktb_3y": -0.7,
    "kr_cpi_yoy:bok_unemployment": -0.7,
    "bok_cpi:kr_policy_rate": -1,
    "bok_cpi:bok_base_rate": -1,
    "bok_cpi:usdkrw": 1,
    "kospi:kr_policy_rate": -1,
    "kospi:bok_base_rate": -1,
    "kospi:usdkrw": -0.6,
    "usdkrw:kr_policy_rate": -0.6,
    "usdkrw:kospi": -0.6,
  };
  return explicit[key] ?? 0.45;
}

function buildInitialPredictors(bundle: ForecastBundle, targetId: string): Record<string, PredictorState> {
  const candidates = bundle.series.filter((series) => series.id !== targetId);
  const preferred = PREDICTOR_FALLBACKS.filter((id) => id !== targetId);
  const ids = [
    ...preferred.filter((id) => candidates.some((series) => series.id === id)),
    ...candidates.map((series) => series.id).filter((id) => !preferred.includes(id)),
  ];

  return Object.fromEntries(
    ids.map((id, index) => {
      const series = bundle.series.find((item) => item.id === id);
      return [
        id,
        {
          enabled: index < 5,
          endValue: series ? forecastEnd(series) : 0,
        },
      ];
    }),
  );
}

function applyScenario(
  target: SeriesForecast,
  predictors: SeriesForecast[],
  predictorState: Record<string, PredictorState>,
): ScenarioRow[] {
  const targetScale = historyScale(target);

  return target.forecast.map((point, index) => {
    const progress = (index + 1) / target.forecast.length;
    const adjustment = predictors.reduce((sum, predictor) => {
      const state = predictorState[predictor.id];
      if (!state?.enabled) return sum;
      const baselinePoint = latestForecast(predictor, index);
      const baselineEnd = forecastEnd(predictor);
      const scenarioValue = baselinePoint.median + (state.endValue - baselineEnd) * progress;
      const normalizedDelta = (scenarioValue - baselinePoint.median) / historyScale(predictor);
      return sum + normalizedDelta * targetScale * directionFor(target, predictor) * 0.32;
    }, 0);

    return {
      date: point.date,
      baseline: point.median,
      adjusted: point.median + adjustment,
    };
  });
}

function defaultTargetId(bundle: ForecastBundle): string {
  return TARGET_FALLBACKS.find((id) => bundle.series.some((series) => series.id === id)) ?? bundle.series[0]?.id ?? "";
}

export default function CovariateScenario({ bundle }: { bundle: ForecastBundle }) {
  const [targetId, setTargetId] = useState(() => defaultTargetId(bundle));
  const [predictorState, setPredictorState] = useState<Record<string, PredictorState>>(() =>
    buildInitialPredictors(bundle, targetId),
  );

  const target = useMemo(
    () => bundle.series.find((series) => series.id === targetId) ?? bundle.series[0],
    [bundle.series, targetId],
  );

  const predictors = useMemo(
    () => bundle.series.filter((series) => series.id !== target.id),
    [bundle.series, target.id],
  );

  const rows = useMemo(
    () => applyScenario(target, predictors, predictorState),
    [predictorState, predictors, target],
  );

  const activeCount = predictors.filter((series) => predictorState[series.id]?.enabled).length;
  const latestActual = target.history[target.history.length - 1];
  const first = rows[0];
  const end = rows[rows.length - 1];
  const endDelta = end ? end.adjusted - end.baseline : 0;

  function changeTarget(nextTargetId: string) {
    setTargetId(nextTargetId);
    setPredictorState(buildInitialPredictors(bundle, nextTargetId));
  }

  function updatePredictor(id: string, patch: Partial<PredictorState>) {
    setPredictorState((current) => ({
      ...current,
      [id]: {
        enabled: current[id]?.enabled ?? false,
        endValue: current[id]?.endValue ?? 0,
        ...patch,
      },
    }));
  }

  function resetScenario() {
    setPredictorState(buildInitialPredictors(bundle, target.id));
  }

  return (
    <section className="scenario-section" aria-labelledby="scenario-title">
      <div className="bento-card scenario-hero">
        <div>
          <span className="eyebrow">Covariate Scenario</span>
          <h2 id="scenario-title">추가 변수 기반 예측</h2>
          <div className="scenario-hero-meta" aria-label="scenario metadata">
            <span>{target.forecast.length}개월</span>
            <span>변수 {activeCount}개</span>
            <span>{target.unit}</span>
          </div>
        </div>

        <div className="scenario-summary-grid" aria-label="scenario summary">
          <div className="scenario-summary-tile">
            <span>목표</span>
            <strong>{target.title}</strong>
          </div>
          <div className="scenario-summary-tile">
            <span>최근 실측</span>
            <strong>{formatValue(latestActual?.value, target.unit)}</strong>
            <small>{latestActual?.date ?? "-"}</small>
          </div>
          <div className="scenario-summary-tile">
            <span>예측 시작</span>
            <strong>{formatValue(first?.baseline, target.unit)}</strong>
            <small>{first?.date ?? "-"}</small>
          </div>
          <div className="scenario-summary-tile delta">
            <span>최종월 변화</span>
            <strong>
              {endDelta >= 0 ? "+" : ""}
              {formatValue(endDelta, target.unit)}
            </strong>
            <small>{target.unit === "%" ? "%p" : target.unit}</small>
          </div>
        </div>
      </div>

      <div className="scenario-shell">
        <div className="scenario-chart bento-card">
          <div className="scenario-chart-top">
            <label className="scenario-select">
              <span>목표 지표</span>
              <select value={target.id} onChange={(event) => changeTarget(event.target.value)}>
                {bundle.series.map((series) => (
                  <option key={series.id} value={series.id}>
                    {series.title}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="reset-button" onClick={resetScenario}>
              초기화
            </button>
          </div>

          <div className="scenario-chart-frame">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rows} margin={{ top: 12, right: 18, left: 4, bottom: 0 }}>
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
                  tickFormatter={(value: number) => formatValue(value, target.unit)}
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
                  formatter={(value: number, name: string) => [formatValue(value, target.unit), name]}
                />
                <Legend wrapperStyle={{ color: CHART.tick, fontSize: 11 }} />
                <Line
                  type="monotone"
                  dataKey="baseline"
                  stroke={CHART.baseline}
                  dot={false}
                  strokeWidth={2}
                  name="BISTRO 기준선"
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="adjusted"
                  stroke={CHART.adjusted}
                  dot={false}
                  strokeWidth={2.4}
                  name="공변량 조정"
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="scenario-controls" aria-label="covariate controls">
          {predictors.map((predictor) => {
            const state = predictorState[predictor.id] ?? {
              enabled: false,
              endValue: forecastEnd(predictor),
            };
            const [min, max] = valueRange(predictor);
            const step = valueStep(predictor);
            const baseline = forecastEnd(predictor);

            return (
              <div className="predictor-control bento-card" key={predictor.id}>
                <div className="predictor-head">
                  <label className="switch-row" aria-label={`${predictor.title} 사용 여부`}>
                    <input
                      type="checkbox"
                      checked={state.enabled}
                      onChange={(event) =>
                        updatePredictor(predictor.id, { enabled: event.target.checked })
                      }
                    />
                    <span className="toggle-track" aria-hidden="true" />
                    <span>{predictor.title}</span>
                  </label>
                  <small>{predictor.unit}</small>
                </div>

                <div className="predictor-values">
                  <span>기준 {formatValue(baseline, predictor.unit)}</span>
                  <strong>{formatValue(state.endValue, predictor.unit)}</strong>
                </div>

                <input
                  className="range-input"
                  type="range"
                  min={min}
                  max={max}
                  step={step}
                  value={state.endValue}
                  disabled={!state.enabled}
                  onChange={(event) =>
                    updatePredictor(predictor.id, { endValue: Number(event.target.value) })
                  }
                  aria-label={`${predictor.title} 조정값`}
                />
                <input
                  className="number-input"
                  type="number"
                  step={step}
                  value={Number(state.endValue.toFixed(4))}
                  disabled={!state.enabled}
                  onChange={(event) =>
                    updatePredictor(predictor.id, { endValue: Number(event.target.value) })
                  }
                  aria-label={`${predictor.title} 숫자 입력`}
                />
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
