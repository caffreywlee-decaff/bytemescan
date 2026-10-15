"""기능성화장품 효능 범주와 광고 표현 매핑 — 전부 공개 고시 기준.

- CANON: 기능성화장품으로 보고/심사되는 효능 범주(화장품법 시행규칙 제2조).
- CLAIM_SYNONYMS: 광고·페이지에서 흔한 표현 → 범주. 여기 없는 말은 "범주로 매핑 안 됨"(REVIEW)이지
  MISMATCH 가 아니다. 억지로 판정하지 않는다.
- EE_MARKERS: 식약처 기능성화장품 보고 명부의 EE_NAME 에서 범주를 읽는 키워드.

판단은 전부 이 표 + compare.py 의 규칙으로만. LLM 판단 없음. 회귀 시험 tests/test_compare.py.
"""

# 기능성화장품 효능 범주 (canonical)
MIBAEK = "미백"
WRINKLE = "주름개선"
UV = "자외선차단"
HAIR_LOSS = "탈모증상완화"
ACNE = "여드름완화"
DYE = "염모"
HAIR_REMOVAL = "제모"
STRETCH = "튼살완화"

CANON = [MIBAEK, WRINKLE, UV, HAIR_LOSS, ACNE, DYE, HAIR_REMOVAL, STRETCH]

# 광고/페이지 표현 → 범주. 소문자·공백제거 후 부분일치.
CLAIM_SYNONYMS = {
    "미백": MIBAEK, "화이트닝": MIBAEK, "브라이트닝": MIBAEK, "whitening": MIBAEK, "brightening": MIBAEK,
    "주름개선": WRINKLE, "주름": WRINKLE, "링클": WRINKLE, "wrinkle": WRINKLE, "antiwrinkle": WRINKLE,
    "자외선차단": UV, "자외선": UV, "선크림": UV, "선스틱": UV, "선블록": UV, "spf": UV, "uv차단": UV, "sunscreen": UV,
    "탈모": HAIR_LOSS, "탈모증상완화": HAIR_LOSS,
    "여드름": ACNE, "여드름성": ACNE,
    "염모": DYE, "염색": DYE,
    "제모": HAIR_REMOVAL,
    "튼살": STRETCH,
}

# EE_NAME 안에서 범주를 읽는 키워드 (byteme function_index.EE_TO_CAT 와 같은 기준)
EE_MARKERS = {
    "미백": MIBAEK,
    "주름개선": WRINKLE,
    "자외선": UV,
    "탈모": HAIR_LOSS,
    "여드름": ACNE,
    "염모": DYE,
    "제모": HAIR_REMOVAL,
    "튼살": STRETCH,
}


def _norm(s: str) -> str:
    return (s or "").lower().replace(" ", "")


def claim_to_category(claim: str) -> str | None:
    """광고 표현 → 기능성 범주. 매핑 안 되면 None (기능성 범주가 아닌 말)."""
    n = _norm(claim)
    for word, cat in CLAIM_SYNONYMS.items():
        if word in n:
            return cat
    return None


import re


def ee_text(ee_doc_data: str) -> str:
    """EE_DOC_DATA(효능효과 XML)의 CDATA 본문만 뽑는다. 예: '피부의 미백에 도움을 준다.'"""
    if not ee_doc_data:
        return ""
    cdata = re.findall(r"<!\[CDATA\[(.*?)\]\]>", ee_doc_data, re.S)
    if cdata:
        return " ".join(c.strip() for c in cdata)
    # CDATA 가 없으면 태그만 벗겨 본문 추정
    return re.sub(r"<[^>]+>", " ", ee_doc_data).strip()


def has_efficacy_info(ee_name: str, spf=None, ee_doc_data: str = "") -> bool:
    """이 행에 효능을 판정할 재료가 하나라도 있나(EE_NAME·효능효과 본문·SPF)."""
    return bool((ee_name or "").strip()) or bool(ee_text(ee_doc_data)) or _has_spf(spf)


def registered_categories(ee_name: str, spf=None, ee_doc_data: str = "") -> list[str]:
    """EE_NAME + 효능효과 본문(EE_DOC_DATA) + SPF → 이 제품이 보고된 효능 범주 목록."""
    # 🔴 본문도 claim 처럼 공백을 지우고 댄다 — 심사 명부 본문은 «주름 개선» 처럼 띄어 쓰여 마커 «주름개선» 이 안 걸렸다(E-088, 하네스 V-035 라이브 반례 201206560)
    blob = _norm(f"{ee_name or ''} {ee_text(ee_doc_data)}")
    cats = []
    for marker, cat in EE_MARKERS.items():
        if _norm(marker) in blob and cat not in cats:
            cats.append(cat)
    if _has_spf(spf) and UV not in cats:
        cats.append(UV)
    return cats


def _has_spf(spf) -> bool:
    if spf is None:
        return False
    s = str(spf).strip()
    return s not in ("", "None", "0")
