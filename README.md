# bytemescan

**한 제품이 식약처에 정말 그 기능성으로 보고돼 있는지, 공개 명부에 대조해 주는 작은 MCP / CLI.**
*A tiny MCP + CLI that checks whether a cosmetic product's claimed function is actually on file with Korea's MFDS public registry.*

> 공개 데이터(data.go.kr)만 씁니다. **위법 판정이 아니라 "공식 보고와 같은가"까지**입니다.
> Uses only public open data. It does **not** judge legality — only whether the claim matches the official report.

---

## 왜 (Why)

광고·상세페이지에는 "미백", "주름개선", "선크림" 같은 기능성 표현이 흔합니다. 그런데 그 제품이 식약처에
**그 기능성으로 보고**돼 있는지는 따로 확인해야 합니다. 이 도구는 상품명과 표현을 받아 공개 명부에 대조해
`MATCH / MISMATCH / UNVERIFIABLE / NOT_FOUND / REVIEW` 로 답합니다.

## 설치 (Install)

```bash
pip install -r requirements.txt          # CLI
pip install "mcp[cli]"                    # MCP 서버도 쓸 때
cp .env.example .env                      # DATA_GO_KR_KEY 채우기
```

**키**: [data.go.kr](https://www.data.go.kr) 에서 무료 발급 → 아래 **두 서비스**를 "활용신청" → 받은 키를
`DATA_GO_KR_KEY` 환경변수(또는 `.env`)에 넣습니다. 키는 **쓰는 사람 것**입니다(이 저장소엔 없음).
- 기능성화장품 **보고품목** `FtnltCosmRptPrdlstInfoService01`
- 기능성화장품 **심사품목** `FtnltCosmSrngPrdlstInfoService05` ← 효능 칸이 대부분 채워 있어 꼭 같이

> 기능성화장품은 '보고' 또는 '심사' 중 한쪽에 등록됩니다. 그래서 이 도구는 **둘 다 조회해 합칩니다.**

## CLI

```bash
# 보고+심사 명부에서 상품명 검색 (+ 각 행의 report_no · 보고 효능 범주)
python -m bytemescan.cli lookup "선스틱"

# 상품명 + 광고 표현 대조
python -m bytemescan.cli check "더히스토리오브후 공진향 미백팩트" "미백"                      # → REVIEW: 후보 목록 + report_no + 임시 판정
python -m bytemescan.cli check "더히스토리오브후 공진향 미백팩트" "미백" --no <lookup의 report_no>   # → MATCH (확정)
python -m bytemescan.cli check "더히스토리오브후 공진향 미백팩트" "주름개선" --no <같은 번호>       # → MISMATCH (확정)
```

## MCP (Claude Code · Cursor 등)

```bash
python -m bytemescan.server     # stdio MCP 서버
```

도구 둘:
- `lookup_functional_cosmetic(item_name)` — 보고+심사 명부 검색 → 후보(`report_no`) + 보고 효능 범주
- `check_cosmetic_claim(item_name, claim, report_no=None)` — 표현 ↔ 보고 효능 대조. `report_no` 없으면 후보를 `REVIEW` 로, 있으면 확정

예: *"이 선스틱이 자외선차단으로 보고돼 있어?"* / *"이 토너 미백 보고 있어?"*

## 판정 (Verdicts)

| | 뜻 |
|---|---|
| `MATCH` | 신고번호로 확정한 제품의 보고 효능 범위 안에 광고한 기능성이 있다 |
| `MISMATCH` | 확정한 제품을 찾았고 효능 정보도 있는데, 그 기능성으로는 보고돼 있지 않다 |
| `UNVERIFIABLE` | 확정한 제품의 공개 명부 행에 효능 칸이 비어 판정할 수 없다 |
| `NOT_FOUND` | 그 이름(또는 그 번호)의 보고 제품을 공개 명부에서 못 찾았다 |
| `REVIEW` | 사람이 봐야 한다 — 표현이 기능성 범주로 매핑되지 않거나(예: "보습"), **상품명만으로 찾아 제품을 확정하지 못했다**(`needs: report_no`, 후보마다 `provisional` 임시 판정) |

> 🔴 **확정 판정(MATCH · MISMATCH · UNVERIFIABLE)은 `report_no` 를 줬을 때만 나옵니다.** 상품명만 주면 후보 목록을 `REVIEW` 로 돌려주고, `lookup` 결과의 `report_no`(보고번호 · 접수번호 · 심사 품목번호)로 다시 물으면 확정합니다. 상품명은 식별자가 아니기 때문입니다.

## 한계 (Limits) — 꼭 읽어 주세요

- **상품명은 식별자가 아닙니다.** 같은 이름의 다른 신고가 있을 수 있어, 상품명만으로는 확정하지 않고 후보를 `REVIEW` 로 돌려줍니다. 확정은 `report_no` 로만.
- **공개 보고 API는 효능 칸이 자주 비어 있습니다.** 그럴 땐 `MISMATCH` 로 단정하지 않고 `UNVERIFIABLE` 로 돌려줍니다 — 라벨·보고서로 확인하세요.
- 페이지/상세 이미지 판독(OCR), 여러 판매처에서 같은 제품 묶기, 오탐 제거, 건기식·의약외품 정밀 대조는 **하지 않습니다.** 공개 데이터 조회의 얇은 겉면입니다.
- 위법 여부를 판단하지 않습니다. `MISMATCH` ≠ 위법.

## 테스트

```bash
python tests/test_compare.py     # 순수 판정 로직(네트워크 없음)
```

## 라이선스

MIT.
