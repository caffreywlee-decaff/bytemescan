"""순수 대조 로직 회귀 시험 — 네트워크 없음. python -m pytest (또는 이 파일 직접 실행)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bytemescan.compare import compare_claim, select_by_report_no
from bytemescan.categories import claim_to_category, registered_categories, ee_text


def _doc(text):
    return f'<DOC title="효능효과" type="EE"><![CDATA[{text}]]></DOC>'


def _row(name, ee, spf=None, entp="A사", date="20240101", cancel="N", doc="", no="2024000001", receipt=None, source="보고"):
    return {"source": source, "REPORT_NO": no, "RECEIPT_NO": receipt, "ITEM_NAME": name, "EE_NAME": ee, "SPF": spf,
            "ENTP_NAME": entp, "REPORT_DATE": date, "CANCEL_APPROVAL_YN": cancel, "EE_DOC_DATA": doc}


def test_claim_mapping():
    assert claim_to_category("미백에 도움") == "미백"
    assert claim_to_category("화이트닝 세럼") == "미백"
    assert claim_to_category("주름 개선") == "주름개선"
    assert claim_to_category("선크림 SPF50") == "자외선차단"
    assert claim_to_category("탈모 완화") == "탈모증상완화"
    # 기능성 범주가 아닌 말 → None (REVIEW 로 빠짐)
    assert claim_to_category("보습") is None
    assert claim_to_category("안티에이징") is None
    assert claim_to_category("진정") is None


def test_registered_from_ee():
    assert registered_categories("미백") == ["미백"]
    assert "자외선차단" in registered_categories("", spf="50")
    assert registered_categories("미백/주름개선") == ["미백", "주름개선"]
    assert registered_categories("") == []


def test_match_confirmed():
    rows = [_row("미백에센스", "미백")]
    r = compare_claim("미백", rows, confirmed=True)
    assert r["verdict"] == "MATCH"
    assert r["confirmed_by"] == "report_no"


def test_efficacy_text_from_ee_doc():
    assert "미백" in ee_text(_doc("피부의 미백에 도움을 준다."))
    assert registered_categories("", None, _doc("피부의 미백에 도움을 준다.")) == ["미백"]


def test_match_from_ee_doc_confirmed():
    rows = [_row("미백에센스", "", doc=_doc("피부의 미백에 도움을 준다."))]
    assert compare_claim("미백", rows, confirmed=True)["verdict"] == "MATCH"


def test_mismatch_when_efficacy_present_but_different_confirmed():
    # 확정한 제품을 찾았고 효능 정보도 있는데(주름개선) 광고는 미백 → MISMATCH
    rows = [_row("리프팅크림", "", doc=_doc("피부의 주름개선에 도움을 준다."))]
    r = compare_claim("미백", rows, confirmed=True)
    assert r["verdict"] == "MISMATCH"
    assert r["category"] == "미백"


def test_unverifiable_when_no_efficacy_info_confirmed():
    # 효능 칸이 전부 비어 판정 불가 (보고 API 흔한 경우) — MISMATCH 로 단정하지 않는다
    rows = [_row("풋귤 카밍 패드", "")]
    r = compare_claim("미백", rows, confirmed=True)
    assert r["verdict"] == "UNVERIFIABLE"


def test_sunscreen_by_spf_confirmed():
    rows = [_row("데일리 선스틱", "", spf="50")]
    r = compare_claim("선크림", rows, confirmed=True)
    assert r["verdict"] == "MATCH"


def test_not_found():
    r = compare_claim("미백", [])
    assert r["verdict"] == "NOT_FOUND"
    assert compare_claim("미백", [], confirmed=True)["verdict"] == "NOT_FOUND"


def test_review_when_unmapped():
    rows = [_row("보습 크림", "")]
    r = compare_claim("보습", rows)
    assert r["verdict"] == "REVIEW"
    assert r["category"] is None


# 🔴 상품명만으로는 확정하지 않는다 (2026-10-15 카프 «신고번호로 하고») — 후보 하나여도 REVIEW
def test_name_only_single_candidate_is_review_not_match():
    rows = [_row("미백에센스", "미백", no="2024000777")]
    r = compare_claim("미백", rows)
    assert r["verdict"] == "REVIEW"
    assert r["needs"] == "report_no"
    assert r["candidates"][0]["report_no"] == "2024000777"
    assert r["candidates"][0]["provisional"] == "MATCH"
    assert r["identity_warning"]


def test_name_only_multiple_candidates_keep_each_provisional():
    rows = [_row("크림", "미백", no="1"), _row("크림", "", no="2"), _row("크림", "", no="3", doc=_doc("피부의 주름개선에 도움을 준다."))]
    r = compare_claim("미백", rows)
    assert r["verdict"] == "REVIEW"
    assert [c["provisional"] for c in r["candidates"]] == ["MATCH", "UNVERIFIABLE", "MISMATCH"]


def test_select_by_report_no_matches_report_or_receipt_number():
    rows = [_row("크림", "미백", no="2024000001", receipt="202400109034"), _row("크림", "", no="2024000002"),
            _row("크림", "", no="200409334", source="심사")]
    assert [x["REPORT_NO"] for x in select_by_report_no(rows, "2024000002")] == ["2024000002"]
    assert [x["REPORT_NO"] for x in select_by_report_no(rows, "202400109034")] == ["2024000001"]   # 접수번호로도
    assert [x["REPORT_NO"] for x in select_by_report_no(rows, "제200409334호")] == ["200409334"]   # 글자 섞여도 숫자만 본다
    assert select_by_report_no(rows, "9999") == []
    assert select_by_report_no(rows, "") == []


def test_confirmed_by_report_no_end_to_end_pure():
    rows = [_row("크림", "미백", no="1"), _row("크림", "", no="2", doc=_doc("피부의 주름개선에 도움을 준다."))]
    assert compare_claim("미백", select_by_report_no(rows, "1"), confirmed=True)["verdict"] == "MATCH"
    assert compare_claim("미백", select_by_report_no(rows, "2"), confirmed=True)["verdict"] == "MISMATCH"
    assert compare_claim("미백", select_by_report_no(rows, "3"), confirmed=True)["verdict"] == "NOT_FOUND"


# E-088 회귀 — 심사 명부 본문은 «주름 개선» 처럼 띄어 쓴다. 마커를 본문에 그대로 대면 주름 쪽이 체계적으로 MISMATCH 가 난다
def test_e088_spaced_efficacy_text_still_registers():
    doc = _doc("피부의 미백에 도움을 준다. 피부의 주름 개선에 도움을 준다.")
    assert registered_categories("", None, doc) == ["미백", "주름개선"]
    rows = [_row("천년비책 선크림", "", doc=doc, no="201206560", source="심사")]
    assert compare_claim("주름 개선", rows, confirmed=True)["verdict"] == "MATCH"
    assert compare_claim("주름개선", rows, confirmed=True)["verdict"] == "MATCH"


def test_e088_ee_name_with_spaces():
    assert registered_categories("미백 / 주름 개선") == ["미백", "주름개선"]
    assert registered_categories("자외선 차단") == ["자외선차단"]


# V-035b 순수 반례 — 본문 공백을 다 지우거나 글자마다 공백을 허용하면 «문제 모공» 의 «제 모» 가 제모가 된다.
# 겹낱말 마커(주름|개선)의 경계에서만 공백을 허용하고, 두 글자 낱말 안에는 허용하지 않는다
def test_marker_does_not_cross_word_boundary():
    assert registered_categories("", None, _doc("피부 문제 모공 관리에 도움을 준다.")) == []
    assert registered_categories("", None, _doc("탈 모 방지")) == []                                   # 두 글자 낱말 안 공백은 마커 아님
    assert registered_categories("", None, _doc("피부의 주름  개선에 도움을 준다.")) == ["주름개선"]   # 겹낱말 경계 공백(둘도) OK
    assert registered_categories("", None, _doc("탈모 증상의 완화에 도움")) == ["탈모증상완화"]


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        try:
            fn(); ok += 1; print("PASS", fn.__name__)
        except Exception:  # noqa: BLE001
            print("FAIL", fn.__name__); traceback.print_exc()
    print(f"\n{ok}/{len(fns)} passed")
    raise SystemExit(0 if ok == len(fns) else 1)
