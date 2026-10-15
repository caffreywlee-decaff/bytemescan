"""MCP 서버. 에이전트(Claude Code·Cursor 등)가 아래 도구를 부른다.

  pip install "mcp[cli]"
  python -m bytemescan.server        # stdio MCP 서버

도구:
  lookup_functional_cosmetic(item_name)                  보고+심사 명부에서 상품명 검색 → 후보(report_no) + 보고 효능 범주
  check_cosmetic_claim(item_name, claim, report_no=None) 광고 표현 ↔ 보고 효능 대조. report_no 없으면 REVIEW(후보), 있으면 확정
"""
from . import check as _check

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # noqa: BLE001
    raise SystemExit(
        "mcp 패키지가 필요합니다: pip install \"mcp[cli]\"  (서버 없이 CLI만 쓰려면 python -m bytemescan.cli)"
    ) from e

mcp = FastMCP("bytemescan")


@mcp.tool()
def lookup_functional_cosmetic(item_name: str, rows: int = 50) -> dict:
    """상품명으로 식약처 기능성화장품 보고·심사 명부를 검색해 후보 목록을 돌려준다. 후보마다 report_no(보고번호 또는
    심사 품목번호)와 보고 효능 범주가 붙는다. 공개 데이터(data.go.kr)만 사용. 상품명은 식별자가 아니므로 동일 제품은 보장하지
    않는다 — 확정하려면 check_cosmetic_claim 에 report_no 를 넘긴다."""
    return _check.lookup_cosmetic(item_name, rows)


@mcp.tool()
def check_cosmetic_claim(item_name: str, claim: str, report_no: str | None = None, rows: int = 100) -> dict:
    """상품명과 광고 표현(예: '미백', '주름개선', '선크림')을 받아 그 제품이 해당 기능성으로 보고돼 있는지 대조한다.
    report_no 가 없으면 상품명 후보와 후보별 임시 판정을 REVIEW(needs=report_no) 로 돌려주고,
    report_no 를 주면 그 제품만 대조해 MATCH / MISMATCH / UNVERIFIABLE 로 확정한다.
    위법 판정이 아니라 '공식 보고와 같은가'까지다."""
    return _check.check_cosmetic_claim(item_name, claim, rows, report_no=report_no)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
