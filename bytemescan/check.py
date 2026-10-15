"""공개 API 조회 + 대조를 잇는 상위 함수. (client = 네트워크, compare = 순수 판정)

기능성화장품은 '보고' 또는 '심사' 중 한쪽에 등록된다. 그래서 둘 다 공개 조회해 합친다.
- 보고 명부: 효능 칸이 자주 빔(약 1/4만 채움, 2026-10-13 실측) · 번호 = COSMETIC_REPORT_SEQ(보고번호), DEPT_RECEIPT_NO(접수번호)
- 심사 명부: 효능효과 본문이 대부분 채워 있음 · 번호 = ITEM_SEQ(심사 품목번호)
둘 다 공개 데이터(data.go.kr)다. 비공개 스냅샷·수집 파이프라인은 쓰지 않는다.
🔴 확정 판정은 report_no 를 줬을 때만. 상품명만 주면 후보(report_no 포함)를 REVIEW 로 돌려준다.
"""

from . import client
from .compare import compare_claim, select_by_report_no
from .categories import registered_categories, ee_text


def _normalize(r: dict, source: str) -> dict:
    """보고/심사 행을 공통 형태로. 번호 칸은 명부마다 이름이 다르다."""
    return {
        "source": source,  # "보고" | "심사"
        "REPORT_NO": (r.get("COSMETIC_REPORT_SEQ") if source == "보고" else r.get("ITEM_SEQ")),
        "RECEIPT_NO": r.get("DEPT_RECEIPT_NO") if source == "보고" else None,
        "ITEM_NAME": r.get("ITEM_NAME"),
        "ENTP_NAME": r.get("ENTP_NAME"),
        "EE_NAME": r.get("EE_NAME"),
        "SPF": r.get("SPF"),
        "EE_DOC_DATA": r.get("EE_DOC_DATA") or "",
        "REPORT_DATE": r.get("REPORT_DATE") or r.get("ITEM_PERMIT_DATE"),
        "CANCEL_APPROVAL_YN": r.get("CANCEL_APPROVAL_YN"),
        "MANUF_COUNTRY_NAME": r.get("MANUF_COUNTRY_NAME"),
    }


def _fetch_all(item_name: str, rows: int) -> tuple[list[dict], list[str]]:
    """보고 + 심사 를 합쳐 공통 형태 행 목록으로. endpoints 도 돌려준다."""
    merged, endpoints = [], []
    for fn, src in ((client.search_functional_cosmetics_reported, "보고"),
                    (client.search_functional_cosmetics_screened, "심사")):
        try:
            res = fn(item_name, rows)
            endpoints.append(res.get("endpoint"))
            merged.extend(_normalize(r, src) for r in res.get("items", []))
        except Exception as e:  # noqa: BLE001 — 한쪽이 막혀도 다른 쪽 결과는 쓴다
            endpoints.append(f"{src} ERROR: {client.redact(e)}")   # 키가 섞인 문구가 밖으로 못 나가게(E-094)
    return merged, endpoints


def lookup_cosmetic(item_name: str, rows: int = 100) -> dict:
    """상품명으로 보고+심사 행을 찾아, 각 행의 번호와 보고 효능 범주를 붙여 돌려준다. 확정 판정은 여기서 받은 report_no 로."""
    merged, endpoints = _fetch_all(item_name, rows)
    out = []
    for r in merged:
        out.append({
            "source": r["source"],
            "report_no": r["REPORT_NO"],
            "report_no_kind": "보고번호" if r["source"] == "보고" else "심사 품목번호",
            "receipt_no": r["RECEIPT_NO"],
            "item_name": r["ITEM_NAME"],
            "company": r["ENTP_NAME"],
            "report_date": r["REPORT_DATE"],
            "ee_name": r["EE_NAME"],
            "efficacy_text": ee_text(r["EE_DOC_DATA"])[:200] or None,
            "spf": r["SPF"],
            "canceled": (r["CANCEL_APPROVAL_YN"] in ("Y", "y")),
            "registered_categories": registered_categories(r["EE_NAME"], r["SPF"], r["EE_DOC_DATA"]),
        })
    return {"query": item_name, "endpoints": endpoints, "returned": len(out), "items": out}


def check_cosmetic_claim(item_name: str, claim: str, rows: int = 100, report_no=None) -> dict:
    """상품명 + 광고 표현 (+ report_no) → 판정.
    report_no 가 있으면 그 번호의 행만 대조해 확정 판정(MATCH/MISMATCH/UNVERIFIABLE).
    없으면 상품명으로 찾은 후보와 후보별 임시 판정을 REVIEW 로 돌려준다(needs="report_no")."""
    merged, endpoints = _fetch_all(item_name, rows)
    if report_no:
        picked = select_by_report_no(merged, report_no)
        if not picked:
            verdict = {"verdict": "NOT_FOUND", "claim": claim, "category": None,
                       "reason": f"상품명 '{item_name}' 검색 결과 안에 번호 {report_no} 가 없음 — 상품명을 넓히거나 lookup 으로 번호를 확인",
                       "evidence": []}
        else:
            verdict = compare_claim(claim, picked, confirmed=True)
            verdict["report_no"] = str(report_no)
    else:
        verdict = compare_claim(claim, merged, confirmed=False)
    verdict["endpoints"] = endpoints
    verdict["note"] = (
        "공개 식약처 기능성화장품 보고+심사 명부 대조. 위법 판정 아님 — '공식 보고와 다름'까지. "
        "확정 판정은 report_no 로 제품을 고정했을 때만. 상세 이미지·오탐 제거는 하지 않음."
    )
    return verdict
