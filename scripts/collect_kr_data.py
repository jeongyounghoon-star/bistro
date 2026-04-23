"""CLI: collect Korean financial/macro series into data/kr/ as CSVs.

Usage:
    python scripts/collect_kr_data.py               # all sources
    python scripts/collect_kr_data.py --naver-only
    python scripts/collect_kr_data.py --datagokr-only
    python scripts/collect_kr_data.py --pages 200   # limit Naver paging
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kr_data import bok, datagokr, naver_finance
from kr_data.common import kr_data_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Korean data into data/kr/")
    parser.add_argument("--naver-only", action="store_true")
    parser.add_argument("--datagokr-only", action="store_true")
    parser.add_argument("--bok-only", action="store_true")
    parser.add_argument("--pages", type=int, default=400, help="Naver max pages per series")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    only_flags = [args.naver_only, args.datagokr_only, args.bok_only]
    if sum(only_flags) > 1:
        parser.error("--*-only flags are mutually exclusive")
    run_naver = args.naver_only or not any(only_flags)
    run_datagokr = args.datagokr_only or not any(only_flags)
    run_bok = args.bok_only or not any(only_flags)

    out = {"output_dir": str(kr_data_dir()), "sources": {}}

    if run_naver:
        out["sources"]["naver"] = naver_finance.collect_all(pages=args.pages)
    if run_datagokr:
        out["sources"]["datagokr"] = datagokr.collect_all()
    if run_bok:
        out["sources"]["bok"] = bok.collect_all()

    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
