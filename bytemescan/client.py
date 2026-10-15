"""식약처 공개 API 얇은 클라이언트 (data.go.kr). 쓰는 사람이 자기 키를 넣는다.

- 키: 환경변수 DATA_GO_KR_KEY (data.go.kr 에서 무료 발급, 해당 서비스 '활용신청').
- 공개 서비스만 부른다. 우리 스냅샷·내부 데이터 안 씀.
  · 기능성화장품 보고품목  FtnltCosmRptPrdlstInfoService01/getRptPrdlstInq01 (item_name 부분일치)
  · 건강기능식품 품목제조신고 HtfsInfoService03/getHtfsItem01 (Prduct 부분일치)
"""

import os
import requests

BASE = "https://apis.data.go.kr"
TIMEOUT = 40


class MfdsKeyMissing(RuntimeError):
    pass


def _key() -> str:
    k = os.environ.get("DATA_GO_KR_KEY")
    if not k:
        raise MfdsKeyMissing(
            "환경변수 DATA_GO_KR_KEY 가 없습니다. data.go.kr 에서 무료 키를 받아 해당 서비스를 "
            "'활용신청'한 뒤 DATA_GO_KR_KEY 로 넣어 주세요(.env 또는 환경변수)."
        )
    return k


def _get(svc: str, op: str, extra: dict, rows: int = 100) -> dict:
    url = f"{BASE}/{svc}/{op}"
    params = {"serviceKey": _key(), "pageNo": 1, "numOfRows": rows, "type": "json", **extra}
    r = requests.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
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
            last = {"endpoint": "HtfsInfoService03", "op": "getHtfsItem01", "error": str(e), "items": []}
    return last or {"items": []}
