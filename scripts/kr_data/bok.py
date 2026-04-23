"""한국은행 ECOS Open API fetchers.

ECOS endpoint shape:
    https://ecos.bok.or.kr/api/StatisticSearch/{KEY}/json/kr/{start}/{end}/
        {STAT_CODE}/{CYCLE}/{START_DATE}/{END_DATE}/{ITEM1}/{ITEM2}/...

Cycle codes: A=annual, S=semi, Q=quarter, M=month, SM=semi-month, D=day.
Date format must match the cycle: YYYY for A, YYYYQn for Q, YYYYMM for M,
YYYYMMDD for D.

Series IDs change occasionally. If a fetch returns RESULT.CODE != INFO-000,
ECOS sends back a JSON error — the response is logged and the series is
skipped instead of crashing the whole run.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Iterable

import pandas as pd
import requests

from .common import bok_api_key, save_csv

logger = logging.getLogger(__name__)

ECOS_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"

CYCLE_DATE_FMT = {
    "A": ("%Y", "annual"),
    "Q": (None, "quarter"),
    "M": ("%Y%m", "monthly"),
    "D": ("%Y%m%d", "daily"),
}


def _format_start_end(cycle: str) -> tuple[str, str]:
    today = date.today()
    if cycle == "D":
        return "20000101", today.strftime("%Y%m%d")
    if cycle == "M":
        return "200001", today.strftime("%Y%m")
    if cycle == "Q":
        q = (today.month - 1) // 3 + 1
        return "2000Q1", f"{today.year}Q{q}"
    if cycle == "A":
        return "2000", str(today.year)
    raise ValueError(f"unsupported cycle {cycle!r}")


def fetch_series(
    stat_code: str,
    cycle: str,
    items: Iterable[str],
    *,
    start: str | None = None,
    end: str | None = None,
    page_size: int = 10000,
) -> pd.DataFrame:
    """Fetch one ECOS series. Returns columns [date, value]."""
    key = bok_api_key()
    if start is None or end is None:
        start, end = _format_start_end(cycle)
    item_path = "/".join(i for i in items if i is not None)
    url = (
        f"{ECOS_BASE}/{key}/json/kr/1/{page_size}/"
        f"{stat_code}/{cycle}/{start}/{end}/{item_path}"
    )
    # ECOS occasionally drops connections mid-stream; retry on transport errors.
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            payload = r.json()
            break
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError) as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"ECOS transport failure after retries: {last_err}")
    # Error envelope
    if "RESULT" in payload:
        code = payload["RESULT"].get("CODE")
        msg = payload["RESULT"].get("MESSAGE")
        raise RuntimeError(f"ECOS error {code}: {msg}")
    block = payload.get("StatisticSearch")
    if not block:
        raise RuntimeError(f"ECOS empty response: {payload}")
    rows = block.get("row", [])
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["date", "value"])
    df = df.rename(columns={"TIME": "raw_date", "DATA_VALUE": "value"})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["date"] = _parse_ecos_time(df["raw_date"], cycle)
    return df[["date", "value"]].dropna().sort_values("date").reset_index(drop=True)


def _parse_ecos_time(s: pd.Series, cycle: str) -> pd.Series:
    if cycle == "D":
        return pd.to_datetime(s, format="%Y%m%d", errors="coerce")
    if cycle == "M":
        return pd.to_datetime(s, format="%Y%m", errors="coerce")
    if cycle == "A":
        return pd.to_datetime(s, format="%Y", errors="coerce")
    if cycle == "Q":
        # ECOS quarterly format: YYYYQn or YYYYQn
        def _q(v: str) -> pd.Timestamp:
            year = int(v[:4])
            q = int(v[-1])
            month = (q - 1) * 3 + 1
            return pd.Timestamp(year=year, month=month, day=1)

        return s.map(_q)
    raise ValueError(cycle)


@dataclass(frozen=True)
class BokSeries:
    name: str
    stat_code: str
    cycle: str
    items: tuple[str, ...]
    filename: str
    value_col: str


# Hand-picked, well-known ECOS series.
# Add more by appending; if an item code is wrong ECOS returns INFO-200/300
# and the run continues with the others.
SERIES: list[BokSeries] = [
    BokSeries(
        name="BASE_RATE",
        stat_code="722Y001",
        cycle="D",
        items=("0101000",),
        filename="bok_base_rate_d.csv",
        value_col="base_rate",
    ),
    BokSeries(
        name="CPI_TOTAL",
        stat_code="901Y009",
        cycle="M",
        items=("0",),
        filename="bok_cpi_m.csv",
        value_col="cpi",
    ),
    BokSeries(
        name="UNEMPLOYMENT",
        stat_code="901Y027",
        cycle="M",
        items=("I61BC",),
        filename="bok_unemployment_m.csv",
        value_col="unemployment",
    ),
    BokSeries(
        name="GDP_REAL",
        stat_code="200Y104",
        cycle="Q",
        items=("1400",),
        filename="bok_gdp_real_q.csv",
        value_col="gdp_real",
    ),
    BokSeries(
        name="M2",
        stat_code="161Y005",
        cycle="M",
        items=("BBHS00",),
        filename="bok_m2_m.csv",
        value_col="m2",
    ),
    BokSeries(
        name="EXPORTS",
        stat_code="901Y118",
        cycle="M",
        items=("T002",),
        filename="bok_exports_m.csv",
        value_col="exports",
    ),
    BokSeries(
        name="IMPORTS",
        stat_code="901Y118",
        cycle="M",
        items=("T004",),
        filename="bok_imports_m.csv",
        value_col="imports",
    ),
]


def collect_all() -> dict[str, dict[str, str]]:
    results: dict[str, dict[str, str]] = {}
    try:
        bok_api_key()
    except RuntimeError as e:
        logger.warning("Skipping BOK ECOS: %s", e)
        return {"_skipped": {"reason": str(e)}}

    for s in SERIES:
        try:
            logger.info("ECOS %s (%s/%s/%s)...", s.name, s.stat_code, s.cycle, s.items)
            df = fetch_series(s.stat_code, s.cycle, s.items)
            if df.empty:
                results[s.name] = {"error": "empty"}
                continue
            df = df.rename(columns={"value": s.value_col})
            path = save_csv(df, s.filename, date_col="date", value_col=s.value_col)
            results[s.name] = {"path": str(path), "rows": str(len(df))}
        except Exception as e:
            logger.warning("BOK %s failed: %s", s.name, e)
            results[s.name] = {"error": str(e)}
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    import json

    print(json.dumps(collect_all(), indent=2, ensure_ascii=False))
