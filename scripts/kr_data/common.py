"""Shared helpers for the KR data collectors."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


def kr_data_dir() -> Path:
    """Resolve and create the KR CSV output directory."""
    rel = os.environ.get("KR_DATA_DIR", "data/kr")
    path = (REPO_ROOT / rel).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def forecast_json_path() -> Path:
    """Resolve the JSON output path for the web dashboard."""
    rel = os.environ.get("KR_FORECAST_JSON", "web/public/data/forecasts.json")
    path = (REPO_ROOT / rel).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def data_go_kr_key() -> str:
    key = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "DATA_GO_KR_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    return key


def bok_api_key() -> str:
    key = os.environ.get("BOK_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "BOK_API_KEY is not set. Issue an ECOS key at https://ecos.bok.or.kr "
            "and add it to .env."
        )
    return key


def save_csv(df: pd.DataFrame, filename: str, *, date_col: str, value_col: str) -> Path:
    """Write a two-column CSV (unnamed index = date, value) that matches BISTRO's format.

    The BISTRO notebooks read CSVs with `pd.read_csv(path, index_col=0)` and treat
    the first column after the index as the target. So the output format is:
        ,VALUE_COLUMN_NAME
        2020-01,1.23
        ...
    """
    out = df[[date_col, value_col]].dropna().copy()
    out[date_col] = pd.to_datetime(out[date_col]).dt.strftime(_date_fmt(out[date_col]))
    out = out.sort_values(date_col).drop_duplicates(subset=[date_col], keep="last")
    out = out.set_index(date_col)
    out.index.name = ""
    path = kr_data_dir() / filename
    out.to_csv(path)
    return path


def _date_fmt(series: pd.Series) -> str:
    """Monthly data uses YYYY-MM (BIS convention); daily uses YYYY-MM-DD."""
    parsed = pd.to_datetime(series)
    has_day_variation = parsed.dt.day.nunique() > 1
    return "%Y-%m-%d" if has_day_variation else "%Y-%m"
