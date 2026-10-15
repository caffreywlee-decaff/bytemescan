"""식약처 공개 API 얇은 클라이언트 (data.go.kr). 쓰는 사람이 자기 키를 넣는다.

- 키: 환경변수 DATA_GO_KR_KEY (data.go.kr 에서 무료 발급, 해당 서비스 '활용신청').
- 공개 서비스만 부른다. 우리 스냅샷·내부 데이터 안 씀.
  · 기능성화장품 보고품목  FtnltCosmRptPrdlstInfoService01/getRptPrdlstInq01 (item_name 부분일치)
  · 건강기능식품 품목제조신고 HtfsInfoService03/getHtfsItem01 (Prduct 부분일치)
"""

import os
import re
from pathlib import Path

import requests

BASE = "https://apis.data.go.kr"
TIMEOUT = 40


class MfdsKeyMissing(RuntimeError):
    pass


class MfdsApiError(RuntimeError):
    """API 호출 실패. 문구에 요청 URL 을 담지 않는다 — data.go.kr 은 키를 쿼리스트링으로 받아 URL = 키다(E-094)."""


_KEY_RE = re.compile(r"(serviceKey=)[^&\s'\"]+", re.I)


def redact(text) -> str:
    """어떤 문구든 `serviceKey=…` 값은 가린다(E-094, 하네스 V-036 실측 — requests 의 403 문구에 쓰는 사람 키가 통째로 찍혔다).
    MCP 로 쓰면 오류 문구가 에이전트 대화·로그에 남으므로, 밖으로 나가는 문자열은 전부 이 함수를 거친다."""
    return _KEY_RE.sub(r"\1***", str(text))


def read_env_file(path) -> dict:
    """`KEY=VALUE` 줄만 읽는 작은 .env 파서(주석 · 빈 줄 · 따옴표 처리, 의존성 없음). 파일이 없으면 {}."""
    out = {}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _key() -> str:
    # 환경변수 → 현재 폴더 .env → 이 저장소 폴더 .env 순. README 가 «.env 를 읽는다» 고 약속하는데 코드가 환경변수만 봤다(E-093, 하네스 V-036 실측).
    k = os.environ.get("DATA_GO_KR_KEY")
    if not k:
        for p in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
            k = read_env_file(p).get("DATA_GO_KR_KEY")
            if k:
                break
    if not k:
        raise MfdsKeyMissing(
            "DATA_GO_KR_KEY 가 없습니다 — 환경변수, 현재 폴더의 .env, 저장소 폴더의 .env 를 차례로 봤습니다. "
            "data.go.kr 에서 무료 키를 받아 두 서비스를 '활용신청'한 뒤 .env 또는 환경변수로 넣어 주세요."
        )
    return k


def _get(svc: str, op: str, extra: dict, rows: int = 100) -> dict:
    url = f"{BASE}/{svc}/{op}"
    params = {"serviceKey": _key(), "pageNo": 1, "numOfRows": rows, "type": "json", **extra}
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.HTTPError as e:   # requests 문구는 «403 … for url: <키 포함 URL>» — 상태코드 · 서비스 이름만 남긴다(E-094)
        resp = e.response
        status, reason = getattr(resp, "status_code", "?"), (getattr(resp, "reason", "") or "")
        raise MfdsApiError(f"{op}: HTTP {status} {reason}".rstrip() + " — data.go.kr 응답(키 · 활용신청 상태를 확인하세요)") from None
    except requests.RequestException as e:   # 연결 오류 문구도 경로 · 쿼리를 품는다
        raise MfdsApiError(f"{op}: 연결 실패 — {type(e).__name__}") from None
    try:
        d = r.json()
    except ValueError:
        raise MfdsApiError(f"{op}: 응답이 JSON 이 아님 — {redact(r.text[:120])}") from None
    body = d.get("body") or {}
    header = d.get("header") or {}
    code = header.get("resultCode")
    if code not in (None, "00"):
        raise RuntimeError(f"{op}: resultCode={code} {header.get('resultMsg')}")
    items = body.get("items") or []
    if isinstance(items, dict):
        items = items.get("item", [])
    if isinstance(items, dict):
        items = [items]
    return {"endpoint": url, "op": op, "total": body.get("totalCount"), "items": items}


def search_functional_cosmetics_reported(item_name: str, rows: int = 100) -> dict:
    """기능성화장품 '보고' 명부에서 상품명 부분일치 검색."""
    return _get(
        "1471000/FtnltCosmRptPrdlstInfoService01", "getRptPrdlstInq01",
        {"item_name": item_name}, rows,
    )


def search_functional_cosmetics_screened(item_name: str, rows: int = 100) -> dict:
    """기능성화장품 '심사' 명부에서 상품명 부분일치 검색.
    보고 명부는 효능 칸이 자주 비지만(약 1/4만 채움) 심사 명부는 대부분 채워 있다(2026-10-13 실측)."""
    return _get(
        "1471057/FtnltCosmSrngPrdlstInfoService05", "getSrngPrdlstInq05",
        {"item_name": item_name}, rows,
    )


# 하위호환 별칭
def search_functional_cosmetics(item_name: str, rows: int = 100) -> dict:
    return search_functional_cosmetics_reported(item_name, rows)


def search_health_functional(product_name: str, rows: int = 100) -> dict:
    """건강기능식품 품목제조신고에서 제품명 부분일치 검색.
    (파라미터명은 서비스 판에 따라 다를 수 있어 Prduct·prduct 둘 다 시도.)"""
    last = None
    for pk in ("Prduct", "prduct"):
        try:
            res = _get("1471000/HtfsInfoService03", "getHtfsItem01", {pk: product_name}, rows)
            if res["items"] or res["total"] not in (None, 0, "0"):
                return res
            last = res
        except Exception as e:  # noqa: BLE001
            last = {"endpoint": "HtfsInfoService03", "op": "getHtfsItem01", "error": redact(e), "items": []}
    return last or {"items": []}
