"use client";

import { useMemo, useState } from "react";
import CovariateScenario from "./CovariateScenario";
import SeriesCard from "./SeriesCard";
import type { ForecastBundle } from "./types";

type DashboardTab = "baseline" | "covariate";

export default function Dashboard({ bundle }: { bundle: ForecastBundle }) {
  const allTags = useMemo(() => {
    const tags = new Set<string>();
    bundle.series.forEach((series) => series.tags.forEach((tag) => tags.add(tag)));
    return Array.from(tags).sort((a, b) => a.localeCompare(b, "ko-KR"));
  }, [bundle.series]);

  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [activeTab, setActiveTab] = useState<DashboardTab>("baseline");

  const visible = useMemo(() => {
    const loweredQuery = query.trim().toLowerCase();

    return bundle.series.filter((series) => {
      const matchesTag = activeTag ? series.tags.includes(activeTag) : true;
      const matchesQuery =
        loweredQuery.length === 0 ||
        series.title.toLowerCase().includes(loweredQuery) ||
        series.unit.toLowerCase().includes(loweredQuery) ||
        series.tags.some((tag) => tag.toLowerCase().includes(loweredQuery)) ||
        (series.note ?? "").toLowerCase().includes(loweredQuery);

      return matchesTag && matchesQuery;
    });
  }, [activeTag, bundle.series, query]);

  const trimmedQuery = query.trim();

  return (
    <section className="dashboard-section" aria-labelledby="dashboard-tabs-title">
      <div className="bento-card dashboard-tabs-card">
        <div>
          <span className="eyebrow">Forecast Workspace</span>
          <h2 id="dashboard-tabs-title">예측 워크스페이스</h2>
          <div className="workspace-meta" aria-label="forecast workspace metadata">
            <span>{bundle.series.length}개 지표</span>
            <span>{bundle.horizon_months}개월 전망</span>
            <span>{bundle.model}</span>
          </div>
        </div>
        <div className="tab-list" role="tablist" aria-label="forecast views">
          <button
            type="button"
            role="tab"
            className={`tab-button ${activeTab === "baseline" ? "active" : ""}`}
            aria-selected={activeTab === "baseline"}
            aria-controls="baseline-panel"
            id="baseline-tab"
            onClick={() => setActiveTab("baseline")}
          >
            기준 예측
          </button>
          <button
            type="button"
            role="tab"
            className={`tab-button ${activeTab === "covariate" ? "active" : ""}`}
            aria-selected={activeTab === "covariate"}
            aria-controls="covariate-panel"
            id="covariate-tab"
            onClick={() => setActiveTab("covariate")}
          >
            공변량 예측
          </button>
        </div>
      </div>

      {activeTab === "baseline" ? (
        <div
          id="baseline-panel"
          role="tabpanel"
          aria-labelledby="baseline-tab"
          className="tab-panel"
        >
          <div className="section-heading">
            <div>
              <span className="eyebrow">Forecast Cards</span>
              <h2 id="series-title">시계열 예측 보드</h2>
            </div>
            <p>
              {visible.length}/{bundle.series.length}개 표시
              {activeTag ? ` · ${activeTag}` : ""}
              {trimmedQuery ? ` · ${trimmedQuery}` : ""}
            </p>
          </div>

          <div className="bento-card toolbar-shell">
            <label className="search">
              <span className="sr-only">시계열 검색</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="지표명, 태그, 단위, 메모 검색"
                aria-label="지표명, 태그, 단위, 메모 검색"
              />
            </label>

            <div className="toolbar" aria-label="series tag filters">
              <button
                type="button"
                className={`chip ${activeTag === null ? "active" : ""}`}
                onClick={() => setActiveTag(null)}
                aria-pressed={activeTag === null}
              >
                전체
              </button>
              {allTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  className={`chip ${activeTag === tag ? "active" : ""}`}
                  onClick={() => setActiveTag(tag)}
                  aria-pressed={activeTag === tag}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          <div className="series-grid">
            {visible.map((series, index) => (
              <SeriesCard key={series.id} series={series} index={index} />
            ))}

            {visible.length === 0 && (
              <div className="bento-card empty">
                선택한 조건에 맞는 시계열이 없습니다.
              </div>
            )}
          </div>
        </div>
      ) : (
        <div
          id="covariate-panel"
          role="tabpanel"
          aria-labelledby="covariate-tab"
          className="tab-panel"
        >
          <CovariateScenario bundle={bundle} />
        </div>
      )}
    </section>
  );
}
