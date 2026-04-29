"use client";

import { useMemo, useState } from "react";
import SeriesCard from "./SeriesCard";
import type { ForecastBundle } from "./types";

export default function Dashboard({ bundle }: { bundle: ForecastBundle }) {
  const allTags = useMemo(() => {
    const tags = new Set<string>();
    bundle.series.forEach((series) => series.tags.forEach((tag) => tags.add(tag)));
    return Array.from(tags).sort((a, b) => a.localeCompare(b, "ko-KR"));
  }, [bundle.series]);

  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [query, setQuery] = useState("");

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
    <section className="dashboard-section" aria-labelledby="series-title">
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
    </section>
  );
}
