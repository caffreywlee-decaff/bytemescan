"""광고 표현 ↔ 식약처 보고 효능 대조. 순수 함수 — 네트워크 없음. 회귀 시험 대상.

verdict:
  MATCH         (신고번호로 확정한 제품의) 보고 효능 범위 안에 광고가 말한 기능성이 있다
  MISMATCH      확정한 제품을 찾았고 효능 정보도 있는데, 그 기능성으로는 보고돼 있지 않다
  UNVERIFIABLE  확정한 제품의 공개 명부 행에 효능 정보가 비어 판정할 수 없다
  NOT_FOUND     그 이름(또는 번호)의 보고 제품을 공개 명부에서 못 찾았다
  REVIEW        사람이 봐야 한다 — (a) 광고 표현이 기능성 범주로 매핑되지 않거나
                (b) 상품명만으로 찾아 제품을 확정하지 못했다(needs="report_no", 후보마다 임시 판정 provisional)

🔴 확정 판정(MATCH · MISMATCH · UNVERIFIABLE)은 신고번호로 제품을 고정했을 때만 낸다(confirmed=True).
   상품명은 식별자가 아니다 — 같은 이름의 다른 신고가 있다. 상품명만으로 찾은 행은 후보로만 보여 주고
   REVIEW 로 돌려준다. (2026-10-15 카프 «신고번호로 하고»)
페이지/상세 이미지 판독·오탐 제거는 하지 않는다 — 그건 공개 데이터 밖의 일이다.
"""

from .categories import claim_to_category, registered_categories, has_efficacy_info


def _digits(x) -> str:
    return "".join(ch for ch in str(x or "") if ch.isdigit())


def select_by_report_no(rows: list[dict], report_no) -> list[dict]:
    """보고번호(COSMETIC_REPORT_SEQ) 또는 접수번호(DEPT_RECEIPT_NO) 또는 심사 품목번호(ITEM_SEQ)가 같은 행만."""
    want = _digits(report_no)
    if not want:
        return []
    return [r for r in rows if want in (_digits(r.get("REPORT_NO")), _digits(r.get("RECEIPT_NO")))]


def row_evidence(category: str, r: dict) -> dict:
    doc = r.get("EE_DOC_DATA") or ""
    info = has_efficacy_info(r.get("EE_NAME"), r.get("SPF"), doc)
    cats = registered_categories(r.get("EE_NAME"), r.get("SPF"), doc)
    hit = category in cats
    provisional = "MATCH" if hit else ("UNVERIFIABLE" if not info else "MISMATCH")
    return {
        "source": r.get("source"),
        "report_no": r.get("REPORT_NO"),
        "receipt_no": r.get("RECEIPT_NO"),
        "item_name": r.get("ITEM_NAME"),
        "company": r.get("ENTP_NAME"),
        "report_date": r.get("REPORT_DATE"),
        "ee_name": r.get("EE_NAME"),
        "spf": r.get("SPF"),
        "has_efficacy_info": info,
        "canceled": (r.get("CANCEL_APPROVAL_YN") in ("Y", "y")),
        "registered_categories": cats,
        "covers_claim": hit,
        "provisional": provisional,
    }


def compare_claim(claim: str, product_rows: list[dict], confirmed: bool = False) -> dict:
    """claim 과 보고 행들을 대조. confirmed=True 는 호출자가 신고번호로 행을 고정했다는 뜻 — 그때만 확정 판정.

    product_rows: [{source, REPORT_NO, RECEIPT_NO, ITEM_NAME, ENTP_NAME, EE_NAME, SPF, EE_DOC_DATA, REPORT_DATE, CANCEL_APPROVAL_YN}, ...]
    """
    category = claim_to_category(claim)
    if category is None:
        return {"verdict": "REVIEW", "claim": claim, "category": None,
                "reason": "광고 표현이 기능성화장품 효능 범주로 매핑되지 않음 — 사람이 확인", "evidence": []}
    if not product_rows:
        return {"verdict": "NOT_FOUND", "claim": claim, "category": category,
                "reason": "그 이름(또는 번호)의 기능성화장품 보고 제품을 공개 명부에서 찾지 못함", "evidence": []}

    evidence = [row_evidence(category, r) for r in product_rows]

    if not confirmed:
        return {
            "verdict": "REVIEW",
            "needs": "report_no",
            "claim": claim,
            "category": category,
            "reason": (f"상품명으로 찾은 후보 {len(evidence)}건 — 상품명은 식별자가 아니라 확정하지 않음. "
                       "후보의 report_no 로 다시 물으면 확정 판정(MATCH/MISMATCH/UNVERIFIABLE)을 냄"),
            "identity_warning": "상품명으로 찾은 행이라 동일 제품 보장 안 됨(같은 이름 다른 신고 가능)",
            "candidates": evidence,
            "evidence": [],
        }

    any_match = any(e["covers_claim"] for e in evidence)
    any_info = any(e["has_efficacy_info"] for e in evidence)
    if any_match:
        verdict, reason = "MATCH", f"보고 효능에 '{category}'가 있음"
    elif not any_info:
        verdict, reason = "UNVERIFIABLE", "제품은 찾았으나 공개 명부 행에 효능 정보가 비어 판정 불가 — 라벨·보고서로 확인 필요"
    else:
        verdict, reason = "MISMATCH", f"제품은 찾았고 효능 정보도 있으나 '{category}'로 보고된 범위가 아님"
    return {"verdict": verdict, "claim": claim, "category": category, "reason": reason,
            "confirmed_by": "report_no", "evidence": evidence}
