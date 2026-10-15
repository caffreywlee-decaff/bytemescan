# bytemescan

**한 제품이 식약처에 정말 그 기능성으로 보고돼 있는지, 공개 명부에 대조해 주는 작은 MCP / CLI.**
*A tiny MCP + CLI that checks whether a cosmetic product's claimed function is actually on file with Korea's MFDS public registry.*

> 공개 데이터(data.go.kr)만 씁니다. **위법 판정이 아니라 "공식 보고와 같은가"까지**입니다.
> Uses only public open data. It does **not** judge legality — only whether the claim matches the official report.

---

## 왜 (Why)

광고·상세페이지에는 "미백", "주름개선", "선크림" 같은 기능성 표현이 흔합니다. 그런데 그 제품이 식약처에
**그 기능성으로 보고**돼 있는지는 따로 확인해야 합니다. 식약처가 공개 중인 화장품 행정처분 198건을 세어 보면
137건이 광고 문구 때문이었습니다(2026-10-15, 의약품안전나라 공개 목록). 가장 많은 건 "의약품처럼 보이는 말"(81건)이고
— **이 도구는 그건 보지 않습니다** — 이 도구가 보는 "기능성화장품이 아닌데 기능성처럼 광고한" 경우는 7건입니다.
수는 적어도, 문구 하나로 그 제품의 광고가 대개 2~4개월 멈추는 건 같습니다.

공개 명부는 누구나 볼 수 있지만, data.go.kr 에서 서비스 둘을 신청하고 XML 효능 칸을 파싱해야 답이 나옵니다.
이 도구는 그 입구를 한 줄로 줄입니다 — 상품명과 표현을 받아 보고·심사 명부에 대조해
`MATCH / MISMATCH / UNVERIFIABLE / NOT_FOUND / REVIEW` 로 답하고, 근거 행(번호 · 업소 · 보고 효능)을 같이 돌려줍니다.

**누가 쓰나**: 자기 브랜드 페이지를 점검하는 사람 · 리셀러 문구를 확인하는 담당자 · 에이전트(Claude Code · Cursor)에서
"이 제품 이 효능 보고돼 있어?" 를 바로 묻고 싶은 개발자.

**원칙 하나**: 상품명은 식별자가 아닙니다. 그래서 **확정 판정은 신고번호로만** 냅니다(아래 "판정").

## 설치 (Install)

```bash
git clone https://github.com/caffreywlee-decaff/bytemescan.git && cd bytemescan
pip install -e .                          # CLI 명령 `bytemescan` 이 생깁니다 (어느 폴더에서든)
pip install "mcp[cli]"                    # MCP 서버도 쓸 때
cp .env.example .env                      # DATA_GO_KR_KEY 채우기 — 환경변수 → 현재 폴더 .env → 이 저장소 폴더 .env 순으로 읽습니다
```

**키**: [data.go.kr](https://www.data.go.kr) 에서 무료 발급 → 아래 **두 서비스**를 "활용신청" → 받은 키를
`DATA_GO_KR_KEY` 환경변수(또는 `.env`)에 넣습니다. 키는 **쓰는 사람 것**입니다(이 저장소엔 없음). 오류 문구에도 키를 찍지 않습니다(URL 의 `serviceKey=` 값은 가립니다).
- 기능성화장품 **보고품목** `FtnltCosmRptPrdlstInfoService01`
- 기능성화장품 **심사품목** `FtnltCosmSrngPrdlstInfoService05` ← 효능 칸이 대부분 채워 있어 꼭 같이

> 기능성화장품은 '보고' 또는 '심사' 중 한쪽에 등록됩니다. 그래서 이 도구는 **둘 다 조회해 합칩니다.**

## 쓰는 순서 (How it works, in 3 steps)

1. **찾기** — 상품명으로 후보를 받습니다. 후보마다 `report_no`(보고번호 또는 심사 품목번호) · 업소 · 보고 효능 범주가 붙습니다.
2. **고르기** — 업소명 · 보고일 · 효능으로 내 제품이 어느 행인지 고릅니다. (판매 페이지에는 보통 번호가 없어 이 단계는 사람이 합니다.)
3. **확정** — 그 `report_no` 로 표현을 대조하면 `MATCH / MISMATCH / UNVERIFIABLE` 가 나옵니다. 번호 없이 물으면 1번의 후보 목록을 `REVIEW` 로 돌려줍니다.

## CLI

```bash
# 1. 보고+심사 명부에서 상품명 검색 (+ 각 행의 report_no · 보고 효능 범주)
bytemescan lookup "선스틱"                                   # (pip install -e . 전이면: python3 -m bytemescan.cli lookup "선스틱")

# 2·3. 상품명 + 광고 표현 대조
bytemescan check "<lookup 에서 고른 상품명>" "미백"                        # → REVIEW: 후보 목록 + report_no + 임시 판정
bytemescan check "<lookup 에서 고른 상품명>" "미백" --no <lookup의 report_no>   # → MATCH (확정)
bytemescan check "<lookup 에서 고른 상품명>" "주름개선" --no <같은 번호>       # → MISMATCH (확정)
```

출력은 JSON 입니다 — `verdict` · `reason` · `evidence`(또는 `candidates`) · 조회한 `endpoints` 가 들어 있어 그대로 근거로 남길 수 있습니다.

## MCP 로 쓰기 (Claude Code · Claude Desktop · Cursor)

서버는 stdio 로 뜹니다. 키는 서버를 띄우는 쪽 환경변수(또는 이 폴더의 `.env`)에서 읽습니다.

**Claude Code** — 한 줄로 등록:
```bash
claude mcp add bytemescan -e DATA_GO_KR_KEY=여기에_키 -- python3 -m bytemescan.server
# 이 저장소 폴더 밖에서 등록하려면 pip install -e . 를 먼저 하거나, -- 뒤를 절대 경로의 python3 으로. 윈도우는 python3 대신 python
```

**Claude Desktop · Cursor** — 설정 파일(`claude_desktop_config.json` / `.cursor/mcp.json`)에:
```json
{
  "mcpServers": {
    "bytemescan": {
      "command": "python3",
      "args": ["-m", "bytemescan.server"],
      "env": { "DATA_GO_KR_KEY": "여기에_키" }
    }
  }
}
```

등록되면 에이전트가 쓰는 도구 둘:
- `lookup_functional_cosmetic(item_name)` — 보고+심사 명부 검색 → 후보(`report_no`) + 보고 효능 범주
- `check_cosmetic_claim(item_name, claim, report_no=None)` — 표현 ↔ 보고 효능 대조. `report_no` 없으면 후보를 `REVIEW` 로, 있으면 확정

이렇게 물으면 됩니다:
- *"○○ 미백 에센스가 미백으로 보고돼 있어?"* → 에이전트가 `lookup` 으로 후보를 보여 주고, 당신이 고른 번호로 `check` 를 다시 부릅니다.
- *"이 선스틱 자외선차단 보고 있어? 번호는 <lookup 에서 고른 report_no>야"* → 바로 확정 판정.

직접 띄워 보기: `python3 -m bytemescan.server` (윈도우는 `python`)

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
- **판매 페이지에는 보통 보고번호가 없습니다.** 그래서 `report_no` 는 `lookup` 후보 중 당신이 고른 번호인 경우가 대부분입니다. «확정» 은 그 선택을 고정하고 그 제품의 공개 명부 행만 대조했다는 뜻이지, 그 페이지의 제품이 그 번호라는 것을 도구가 증명했다는 뜻이 아닙니다.
- **효능 정보가 비어 있는 행이 있습니다.** 보고 명부는 효능이 세 칸(EE_NAME · SPF/PA · EE_DOC_DATA)에 흩어져 있고, 셋 다 빈 행이 약 5%입니다(2026-09-21 스냅샷 195,799행 기준). 그럴 땐 `MISMATCH` 로 단정하지 않고 `UNVERIFIABLE` 로 돌려줍니다 — 라벨·보고서로 확인하세요.
- 페이지/상세 이미지 판독(OCR), 여러 판매처에서 같은 제품 묶기, 오탐 제거, 건기식·의약외품 정밀 대조는 **하지 않습니다.** 공개 데이터 조회의 얇은 겉면입니다.
- 위법 여부를 판단하지 않습니다. `MISMATCH` ≠ 위법.

## 테스트

```bash
python3 tests/test_compare.py    # 순수 판정 로직(네트워크 없음) — 아무것도 더 깔 필요 없음
pip install -e ".[dev]" && python3 -m pytest tests -q   # 같은 시험을 pytest 로 (pytest 가 같이 깔림)
```

## Quick start (English)

```bash
git clone https://github.com/caffreywlee-decaff/bytemescan.git && cd bytemescan
pip install -e . && pip install "mcp[cli]"
export DATA_GO_KR_KEY=...        # free key from data.go.kr; request the two MFDS "functional cosmetics" services (reported + screened)

bytemescan lookup "sun stick"                                   # candidates with report_no
bytemescan check "<product name>" "whitening" --no <report_no>   # MATCH / MISMATCH / UNVERIFIABLE
claude mcp add bytemescan -e DATA_GO_KR_KEY=... -- python3 -m bytemescan.server  # use it from Claude Code
```

A product name is not an identifier, so a name-only check returns `REVIEW` with candidates; a verdict is only final once you pass a `report_no`. The tool checks the public registry only. It does not judge legality.

## 만든 곳 (About)

[Lambency](https://lambency-data.github.io/)(데이터 · AI 컨설팅)가 만들었습니다. 판매 페이지 전체를 판매처까지 읽고 사진 속 글자까지 대조하는 일은
[BYTEME 판매 페이지 건강검진](https://lambency-data.github.io/byteme/)에서 합니다 — 이 도구는 그 일의 공개 데이터 입구만 떼어 낸 것입니다.
문의 caffrey.w.lee@gmail.com

## 라이선스

MIT.
