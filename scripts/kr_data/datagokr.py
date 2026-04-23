"""data.go.kr (공공데이터포탈) fetchers.

data.go.kr registrations are per-endpoint, so each dataset you want to pull
must be subscribed to on data.go.kr with the same service key. This module
provides a generic caller and a registry of known endpoints. Comment out
endpoints you haven't subscribed to.

Known useful datasets for Korean macro forecasting:
  - 한국수출입은행 환율정보 (daily FX rates, including USD/KRW)
  - 관세청 수출입무역통계 (monthly trade)
  - 통계청 KOSIS 공유서비스 (population, industrial production, CPI, ...)

If a dataset isn't reachable via data.go.kr, fall back to Naver (market data)
or drop your own CSV into data/kr/.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Iterable

import pandas as pd
import requests
import xml.etree.ElementTree as ET

from .common import data_go_kr_key, save_csv

logger = logging.getLogger(__name__)

EXIM_FX_URL = (
    "https://www.koreaexim.go.kr/site/program/financial/exchangeJSON"
)


def fetch_exim_fx(target: str = "USD", days_back: int = 365 * 3) -> pd.DataFrame:
    """Korea Eximbank daily FX reference rate.

    The service is slow (one request per business day), so keep `days_back`
    reasonable. Returns columns [date, rate]. `target` is the counter currency
    (e.g., USD, JPY(100), EUR).
    """
    key = data_go_kr_key()
    rows: list[tuple[str, float]] = []
    today = date.today()
    for i in range(days_back):
        d = today - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        params = {
            "authkey": key,
            "searchdate": d.strftime("%Y%m%d"),
            "data": "AP01",
        }
        try:
            r = requests.get(EXIM_FX_URL, params=params, timeout=10, verify=True)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.debug("EXIM FX %s failed: %s", d, e)
            continue
        for row in data:
            if row.get("cur_unit") == target:
                raw = str(row.get("deal_bas_r", "")).replace(",", "")
                try:
                    rate = float(raw)
                except ValueError:
                    continue
                rows.append((d.strftime("%Y-%m-%d"), rate))
                break
    df = pd.DataFrame(rows, columns=["date", f"fx_{target.lower()}_krw"])
    return df.sort_values("date").drop_duplicates(subset=["date"], keep="last")


def fetch_generic_xml(
    url: str,
    params: dict,
    *,
    row_tag: str,
    date_field: str,
    value_field: str,
    page_param: str = "pageNo",
    per_page_param: str = "numOfRows",
    per_page: int = 1000,
    max_pages: int = 50,
) -> pd.DataFrame:
    """Generic paginated fetcher for XML data.go.kr endpoints.

    Use when a dataset returns a rowset of <item> elements. Supply the tags
    for the row container, the date field, and the value field. This does not
    try to be clever about schemas — data.go.kr schemas vary wildly — so
    customise for each dataset if needed.
    """
    key = data_go_kr_key()
    rows: list[tuple[str, str]] = []
    for page in range(1, max_pages + 1):
        q = dict(params)
        q.setdefault("serviceKey", key)
        q[page_param] = page
        q[per_page_param] = per_page
        r = requests.get(url, params=q, timeout=30)
        r.raise_for_status()
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError as e:
            logger.warning("Non-XML response from %s: %s", url, e)
            break
        items = root.findall(f".//{row_tag}")
        if not items:
            break
        for it in items:
            d = it.findtext(date_field)
            v = it.findtext(value_field)
            if d and v is not None:
                rows.append((d, v))
        if len(items) < per_page:
            break
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["value"] = pd.to_numeric(df["value"].str.replace(",", ""), errors="coerce")
    return df.dropna().sort_values("date").drop_duplicates(subset=["date"], keep="last")


def collect_all() -> dict[str, dict[str, str]]:
    """Run every fetcher you've got credentials for. Extend as you subscribe
    to more data.go.kr endpoints."""
    results: dict[str, dict[str, str]] = {}

    try:
        logger.info("Fetching Eximbank FX (USD)...")
        df = fetch_exim_fx("USD", days_back=365 * 3)
        if not df.empty:
            path = save_csv(
                df,
                "datagokr_usdkrw_d.csv",
                date_col="date",
                value_col="fx_usd_krw",
            )
            monthly = (
                df.assign(date=pd.to_datetime(df["date"]))
                .set_index("date")["fx_usd_krw"]
                .resample("M")
                .last()
                .dropna()
                .rename_axis("date")
                .reset_index(name="fx_usd_krw")
            )
            monthly_path = save_csv(
                monthly,
                "datagokr_usdkrw_m.csv",
                date_col="date",
                value_col="fx_usd_krw",
            )
            results["EXIM_USDKRW"] = {"daily": str(path), "monthly": str(monthly_path)}
        else:
            results["EXIM_USDKRW"] = {"error": "empty response"}
    except Exception as e:
        logger.warning("EXIM FX failed: %s", e)
        results["EXIM_USDKRW"] = {"error": str(e)}

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    import json

    print(json.dumps(collect_all(), indent=2, ensure_ascii=False))
