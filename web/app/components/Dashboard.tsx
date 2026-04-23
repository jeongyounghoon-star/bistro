"use client";

import { useMemo, useState } from "react";
import SeriesCard from "./SeriesCard";
import type { ForecastBundle } from "./types";

export default function Dashboard({ bundle }: { bundle: ForecastBundle }) {
  const allTags = useMemo(() => {
    const s = new Set<string>();
    bundle.series.forEach((x) => x.tags.forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [bundle]);

  const [activeTag, setActiveTag] = useState<string | null>(null);

  const visible = activeTag
    ? bundle.series.filter((s) => s.tags.includes(activeTag))
    : bundle.series;

  return (
    <>
      <div className="toolbar">
        <button
          className={`chip ${activeTag === null ? "active" : ""}`}
          onClick={() => setActiveTag(null)}
        >
          전체
        </button>
        {allTags.map((tag) => (
          <button
            key={tag}
            className={`chip ${activeTag === tag ? "active" : ""}`}
            onClick={() => setActiveTag(tag)}
          >
            {tag}
          </button>
        ))}
      </div>

      <div className="grid">
        {visible.map((s) => (
          <SeriesCard key={s.id} series={s} />
        ))}
      </div>
    </>
  );
}
