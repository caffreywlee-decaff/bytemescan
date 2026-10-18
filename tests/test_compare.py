"""순수 대조 로직 회귀 시험 — 네트워크 없음. python -m pytest (또는 이 파일 직접 실행)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bytemescan.compare import compare_claim, select_by_report_no
from bytemescan.categories import claim_to_category, registered_categories, ee_text


def _doc(text):
    return f'<DOC title="효능효과" type="EE"><![CDATA[{text}]]></DOC>'


def _row(name, ee, spf=None, entp="A사", date="20240101", cancel="N", doc="", no="0000000001", receipt=None, source="보고"):
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
    rows = [_row("그린 카밍 패드", "")]
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
    rows = [_row("미백에센스", "미백", no="0000000777")]
    r = compare_claim("미백", rows)
    assert r["verdict"] == "REVIEW"
    assert r["needs"] == "report_no"
    assert r["candidates"][0]["report_no"] == "0000000777"
    assert r["candidates"][0]["provisional"] == "MATCH"
    assert r["identity_warning"]


def test_name_only_multiple_candidates_keep_each_provisional():
    rows = [_row("크림", "미백", no="1"), _row("크림", "", no="2"), _row("크림", "", no="3", doc=_doc("피부의 주름개선에 도움을 준다."))]
    r = compare_claim("미백", rows)
    assert r["verdict"] == "REVIEW"
    assert [c["provisional"] for c in r["candidates"]] == ["MATCH", "UNVERIFIABLE", "MISMATCH"]


def test_select_by_report_no_matches_report_or_receipt_number():
    rows = [_row("크림", "미백", no="0000000001", receipt="000000109034"), _row("크림", "", no="0000000002"),
            _row("크림", "", no="000009334", source="심사")]
    assert [x["REPORT_NO"] for x in select_by_report_no(rows, "0000000002")] == ["0000000002"]
    assert [x["REPORT_NO"] for x in select_by_report_no(rows, "000000109034")] == ["0000000001"]   # 접수번호로도
    assert [x["REPORT_NO"] for x in select_by_report_no(rows, "제000009334호")] == ["000009334"]   # 글자 섞여도 숫자만 본다
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
    rows = [_row("그린 선크림", "", doc=doc, no="000006560", source="심사")]
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


# E-093 회귀 — README 는 «.env 를 읽는다» 고 하는데 client 가 환경변수만 봤다. 환경변수 → cwd .env → 저장소 .env
def test_e093_key_from_env_file():
    import os, tempfile
    from bytemescan.client import read_env_file, _key, MfdsKeyMissing
    assert read_env_file("/nonexistent/.env") == {}
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, ".env")
        with open(p, "w", encoding="utf-8") as f:
            f.write("# 주석\n\nDATA_GO_KR_KEY = 'abc=123'\nOTHER=x\n")
        assert read_env_file(p) == {"DATA_GO_KR_KEY": "abc=123", "OTHER": "x"}
        saved = os.environ.pop("DATA_GO_KR_KEY", None); cwd = os.getcwd()
        try:
            os.chdir(td)
            assert _key() == "abc=123"                     # cwd 의 .env 에서
            os.remove(p)
            try:
                _key()
                raise AssertionError("키 없으면 MfdsKeyMissing 이어야")
            except MfdsKeyMissing:
                pass
            os.environ["DATA_GO_KR_KEY"] = "env-wins"
            assert _key() == "env-wins"                    # 환경변수가 먼저
        finally:
            os.chdir(cwd)
            if saved is None:
                os.environ.pop("DATA_GO_KR_KEY", None)
            else:
                os.environ["DATA_GO_KR_KEY"] = saved


def test_e094_error_message_has_no_key():
    """E-094 회귀: HTTP 403 · 연결 오류 어느 길로 와도 오류 문구 · lookup 결과 어디에도 키가 없다(더미 키 0회)."""
    import os
    import requests
    from bytemescan import check, client
    KEY = "dummy-key-for-harness"
    url = f"https://apis.data.go.kr/1471000/X/getX?serviceKey={KEY}&pageNo=1"
    assert KEY not in client.redact(url) and "serviceKey=***" in client.redact(url)
    assert client.redact(f"a serviceKey={KEY} b") == "a serviceKey=*** b"

    def fake_403(*a, **k):
        r = requests.Response(); r.status_code = 403; r.reason = "Forbidden"; r.url = url
        return r

    def fake_conn(*a, **k):
        raise requests.ConnectionError(f"HTTPSConnectionPool(host='apis.data.go.kr'): Max retries exceeded with url: /x?serviceKey={KEY}")

    saved_get, saved_env = requests.get, os.environ.get("DATA_GO_KR_KEY")
    os.environ["DATA_GO_KR_KEY"] = KEY
    try:
        for fake, want in ((fake_403, "HTTP 403"), (fake_conn, "연결 실패")):
            requests.get = fake
            try:
                client.search_functional_cosmetics_reported("x")
                raise AssertionError("오류가 나야 한다")
            except client.MfdsApiError as e:
                assert KEY not in str(e) and want in str(e), str(e)
            blob = repr(check.lookup_cosmetic("x"))
            assert KEY not in blob and "ERROR" in blob, blob
    finally:
        requests.get = saved_get
        if saved_env is None:
            os.environ.pop("DATA_GO_KR_KEY", None)
        else:
            os.environ["DATA_GO_KR_KEY"] = saved_env


def test_server_class_mcp_v1_and_v2():
    """mcp 1.x(FastMCP) · 2.x(MCPServer) 둘 다 서버 클래스를 찾고, 둘 다 없으면 안내와 함께 끝난다(2026-10-18 mcp 2.3.0 에서 1.x 경로만 찾다 죽음)."""
    import importlib, sys, types
    saved = {k: v for k, v in sys.modules.items() if k == "mcp" or k.startswith("mcp.") or k == "bytemescan.server"}
    def fake(v1: bool, v2: bool):
        for k in list(sys.modules):
            if k == "mcp" or k.startswith("mcp.") or k == "bytemescan.server":
                del sys.modules[k]
        m = types.ModuleType("mcp"); s = types.ModuleType("mcp.server"); m.server = s
        class _S:
            def __init__(self, name): self.name = name; self.tools = []
            def tool(self):
                def deco(f): self.tools.append(f.__name__); return f
                return deco
            def run(self): pass
        sys.modules["mcp"], sys.modules["mcp.server"] = m, s
        if v1:
            f = types.ModuleType("mcp.server.fastmcp"); f.FastMCP = type("FastMCP", (_S,), {}); sys.modules["mcp.server.fastmcp"] = f
        if v2:
            s.MCPServer = type("MCPServer", (_S,), {})
    try:
        for v1, v2, want in ((True, False, "FastMCP"), (False, True, "MCPServer"), (True, True, "FastMCP")):
            fake(v1, v2)
            srv = importlib.import_module("bytemescan.server")
            assert type(srv.mcp).__name__ == want, (v1, v2, type(srv.mcp).__name__)
            assert srv.mcp.tools == ["lookup_functional_cosmetic", "check_cosmetic_claim"], srv.mcp.tools
        fake(False, False)
        try:
            importlib.import_module("bytemescan.server")
            raise AssertionError("mcp 없으면 SystemExit 이어야")
        except SystemExit as e:
            assert "mcp 패키지가 필요합니다" in str(e)
    finally:
        for k in list(sys.modules):
            if k == "mcp" or k.startswith("mcp.") or k == "bytemescan.server":
                del sys.modules[k]
        sys.modules.update(saved)


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
