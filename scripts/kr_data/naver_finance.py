"""Naver Finance scrapers for Korean market data.

Collects daily-frequency series and aggregates to month-end:
  - KOSPI index
  - USD/KRW spot
  - KTB 3Y and 10Y yields
  - Corporate bond AA- 3Y yield (for corporate spread)
  - CD 91 day
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from io import StringIO
from typing import Callable

import pandas as pd
import requests

from .common import save_csv

logger = logging.getLogger(__name__)

_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


@dataclass(frozen=True)
class NaverSeries:
    name: str
    filename_daily: str
    filename_monthly: str
    fetch: Callable[[int], pd.DataFrame]


def _get(url: str, params: dict | None = None, timeout: int = 15) -> str:
    resp = requests.get(url, params=params, headers=_UA, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "euc-kr"
    return resp.text


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Naver sometimes returns MultiIndex headers (e.g., USD/KRW page).

    Collapse to the deepest level so plain string matching works.
    """
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[-1] if isinstance(c, tuple) else c for c in df.columns]
    return df


def _paged_table(
    url: str,
    pages: int,
    *,
    date_col: str,
    value_cols: tuple[str, ...],
    params_for_page: Callable[[int], dict],
    sleep: float = 0.15,
) -> pd.DataFrame:
    """Scrape a paginated Naver table.

    `value_cols` is an ordered list of acceptable column names — the first one
    present in the parsed table wins. Naver renames columns periodically (the
    interest-rate pages dropped `종가` for `파실 때` in 2024), so accepting
    multiple aliases keeps the scraper resilient.
    """
    frames: list[pd.DataFrame] = []
    chosen_value: str | None = None
    for p in range(1, pages + 1):
        html = _get(url, params=params_for_page(p))
        try:
            tables = pd.read_html(StringIO(html))
        except ValueError:
            continue
        for t in tables:
            t = _flatten_columns(t)
            cols = {str(c).strip() for c in t.columns}
            if date_col not in cols:
                continue
            picked = next((v for v in value_cols if v in cols), None)
            if picked is None:
                continue
            chosen_value = picked
            frames.append(t[[date_col, picked]].dropna().rename(columns={picked: value_cols[0]}))
            break
        time.sleep(sleep)
    if not frames:
        raise RuntimeError(f"No data parsed from {url} (tried value cols {value_cols})")
    out_col = value_cols[0]
    df = pd.concat(frames, ignore_index=True)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df[out_col] = pd.to_numeric(
        df[out_col].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )
    return df.dropna().sort_values(date_col).reset_index(drop=True)


def fetch_kospi(pages: int = 400) -> pd.DataFrame:
    """KOSPI daily closes."""
    return _paged_table(
        "https://finance.naver.com/sise/sise_index_day.naver",
        pages=pages,
        date_col="날짜",
        value_cols=("체결가",),
        params_for_page=lambda p: {"code": "KOSPI", "page": p},
    )


def fetch_usdkrw(pages: int = 400) -> pd.DataFrame:
    """USD/KRW daily (매매기준율)."""
    return _paged_table(
        "https://finance.naver.com/marketindex/exchangeDailyQuote.naver",
        pages=pages,
        date_col="날짜",
        value_cols=("매매기준율",),
        params_for_page=lambda p: {"marketindexCd": "FX_USDKRW", "page": p},
    )


def _interest_fetcher(market_code: str) -> Callable[[int], pd.DataFrame]:
    def _fetch(pages: int = 400) -> pd.DataFrame:
        return _paged_table(
            "https://finance.naver.com/marketindex/interestDailyQuote.naver",
            pages=pages,
            date_col="날짜",
            value_cols=("종가", "파실 때"),
            params_for_page=lambda p: {"marketindexCd": market_code, "page": p},
        )

    return _fetch


fetch_ktb_3y = _interest_fetcher("IRR_GOVT03Y")
fetch_ktb_10y = _interest_fetcher("IRR_GOVT10Y")
fetch_corp_aa_3y = _interest_fetcher("IRR_CORP03Y")
fetch_cd_91 = _interest_fetcher("IRR_CD91")


def _to_monthly(df: pd.DataFrame, date_col: str, value_col: str) -> pd.DataFrame:
    s = df.set_index(date_col)[value_col].astype(float).sort_index()
    monthly = s.resample("M").last().dropna()
    return monthly.rename_axis(date_col).reset_index(name=value_col)


SERIES: list[NaverSeries] = [
    NaverSeries("KOSPI", "naver_kospi_d.csv", "naver_kospi_m.csv", fetch_kospi),
    NaverSeries("USDKRW", "naver_usdkrw_d.csv", "naver_usdkrw_m.csv", fetch_usdkrw),
    NaverSeries("KTB_3Y", "naver_ktb3y_d.csv", "naver_ktb3y_m.csv", fetch_ktb_3y),
    NaverSeries("KTB_10Y", "naver_ktb10y_d.csv", "naver_ktb10y_m.csv", fetch_ktb_10y),
    NaverSeries("CORP_AA_3Y", "naver_corp_aa3y_d.csv", "naver_corp_aa3y_m.csv", fetch_corp_aa_3y),
    NaverSeries("CD_91", "naver_cd91_d.csv", "naver_cd91_m.csv", fetch_cd_91),
]


def collect_all(pages: int = 400) -> dict[str, dict[str, str]]:
    results: dict[str, dict[str, str]] = {}
    for s in SERIES:
        try:
            logger.info("Fetching %s from Naver (pages=%d)...", s.name, pages)
            df = s.fetch(pages)
            daily_col = df.columns[1]
            daily_path = save_csv(df, s.filename_daily, date_col="날짜", value_col=daily_col)
            monthly = _to_monthly(df, "날짜", daily_col)
            monthly_path = save_csv(monthly, s.filename_monthly, date_col="날짜", value_col=daily_col)
            results[s.name] = {"daily": str(daily_path), "monthly": str(monthly_path)}
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", s.name, e)
            results[s.name] = {"error": str(e)}
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    import json

    print(json.dumps(collect_all(), indent=2, ensure_ascii=False))
