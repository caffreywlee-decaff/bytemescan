"""CLI.

  python3 -m bytemescan.cli lookup "토너"                                        # 후보 + report_no
  python3 -m bytemescan.cli check "<lookup 에서 고른 상품명>" "미백"                 # 상품명만 → REVIEW(후보 · 임시 판정)
  python3 -m bytemescan.cli check "<lookup 에서 고른 상품명>" "미백" --no <report_no>   # 번호로 확정
"""
import argparse
import json
import sys

from . import check as _check
from .client import MfdsKeyMissing


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bytemescan", description="식약처 공개 명부에 화장품 기능성 주장 대조 — 확정은 신고번호로만")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("lookup", help="보고+심사 명부에서 상품명 검색 (각 행의 report_no · 보고 효능 범주)")
    p1.add_argument("item_name")
    p1.add_argument("--rows", type=int, default=50)

    p2 = sub.add_parser("check", help="상품명 + 광고 표현 → 판정. --no 를 주면 확정, 없으면 후보를 REVIEW 로")
    p2.add_argument("item_name")
    p2.add_argument("claim")
    p2.add_argument("--no", dest="report_no", default=None, help="보고번호 · 접수번호 · 심사 품목번호 (lookup 결과의 report_no)")
    p2.add_argument("--rows", type=int, default=100)

    a = ap.parse_args(argv)
    try:
        if a.cmd == "lookup":
            out = _check.lookup_cosmetic(a.item_name, a.rows)
        else:
            out = _check.check_cosmetic_claim(a.item_name, a.claim, a.rows, report_no=a.report_no)
    except MfdsKeyMissing as e:
        print(str(e), file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
