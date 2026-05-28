# filter.py
# FDI 관련성 필터. ANTHROPIC_API_KEY 가 설정된 경우 Claude API 를 사용하고,
# 없으면 키워드 기반 필터로 자동 대체한다.

from __future__ import annotations

import json
import logging
from itertools import islice
from typing import Any

from collector import Article
from config import ANTHROPIC_API_KEY, BATCH_SIZE, CLAUDE_MODEL

log = logging.getLogger(__name__)

# ── 키워드 필터 설정 ──────────────────────────────────────────────────────────

_FDI_KEYWORDS = [
    "외국인직접투자", "FDI", "외자", "외국인투자",
    "투자유치", "투자 유치", "그린필드", "현지법인", "합작법인",
    "리쇼어링", "니어쇼어링", "공급망 재편",
    "코트라", "KOTRA", "투자진흥원", "산업통상자원부",
    "경제특구", "자유무역지대",
]

_EXCLUDE_KEYWORDS = [
    "주식", "채권", "펀드", "환율", "금리", "코스피", "코스닥",
    "부동산", "아파트", "분양",
]


def _keyword_filter(articles: list[Article]) -> list[dict[str, Any]]:
    """키워드 매칭으로 FDI 관련 기사를 선별한다."""
    results: list[dict[str, Any]] = []
    for article in articles:
        text = f"{article['title']} {article.get('summary', '')}".lower()
        if any(kw.lower() in text for kw in _EXCLUDE_KEYWORDS):
            continue
        matched = [kw for kw in _FDI_KEYWORDS if kw.lower() in text]
        if matched:
            results.append({
                **article,
                "is_fdi": True,
                "reason": f"키워드 매칭: {', '.join(matched[:3])}",
                "summary": article["title"][:50],
            })
    log.info("키워드 필터: FDI 관련 기사 %d건 선별 완료", len(results))
    return results

# 시스템 프롬프트 — 캐시 대상 (요청마다 동일하므로 ephemeral 캐싱 적용)
_SYSTEM_PROMPT = """\
당신은 FDI(외국인직접투자) 전문 뉴스 큐레이터입니다.
주어진 기사 목록을 분석해 각 기사가 FDI 관련인지 판단하십시오.

[FDI 관련 판단 기준]
- 외국 기업의 국내 투자 유치 (그린필드 투자, M&A, 합작법인 설립 등)
- 국내 기업의 해외 직접투자 (현지법인 설립, 공장 건설 등)
- 투자 유치 정책·규제 변경 (산업부, 기재부, 투자 인센티브, 경제특구 등)
- 주요국 투자 동향 (미국, 중국, 일본, EU, 중동 등의 대한 투자 또는 한국의 해외 진출)
- 산업부·코트라(KOTRA)·투자진흥원(IPA) 관련 발표 및 통계
- 글로벌 공급망 재편으로 인한 투자 이전, 리쇼어링/니어쇼어링

[FDI 비관련 사례]
- 순수 국내 기업 간 거래 또는 국내 부동산 투자
- 외국인 주식·채권 포트폴리오 투자(간접투자)
- 무역·수출입 뉴스 (투자가 아닌 교역만 다루는 경우)
- 순수 금융·금리·환율·주가 뉴스

[응답 규칙]
1. 반드시 JSON 배열만 출력하십시오. 설명, 마크다운 코드 블록, 기타 텍스트를 절대 포함하지 마십시오.
2. 배열 원소 수는 입력 기사 수와 정확히 일치해야 합니다.
3. summary 는 is_fdi 가 true 인 경우에만 작성하며 50자를 초과하지 마십시오.

[응답 형식]
[
  {
    "index": <기사 번호(0부터 시작)>,
    "is_fdi": <true 또는 false>,
    "reason": "<FDI 판단 근거 한 문장>",
    "summary": "<is_fdi true → 50자 이내 한 줄 요약 / false → 빈 문자열>"
  },
  ...
]
"""


# ── 내부 헬퍼 ──────────────────────────────────────────────────────────────────

def _build_user_prompt(batch: list[Article]) -> str:
    """배치 기사 목록을 Claude 에 전달할 텍스트로 변환한다."""
    lines = [f"다음 기사 {len(batch)}건을 분석하십시오:\n"]
    for i, article in enumerate(batch):
        lines.append(f"[{i}] 제목: {article['title']}")
        if article.get("summary"):
            lines.append(f"    요약: {article['summary']}")
        lines.append("")
    return "\n".join(lines)


def _parse_json(raw: str) -> list[dict[str, Any]]:
    """응답 문자열에서 JSON 배열을 추출해 파싱한다."""
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"JSON 배열을 찾을 수 없음: {raw[:200]}")
    return json.loads(raw[start:end])


def _call_claude(client, batch: list[Article]) -> list[dict[str, Any]]:
    """배치 기사를 Claude 에 전달해 FDI 판단 결과 목록을 반환한다."""
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": _build_user_prompt(batch)}],
    )

    raw = response.content[0].text.strip()

    # 캐시 사용 현황 로그 (디버그 레벨)
    u = response.usage
    log.debug(
        "캐시 생성=%d 캐시 읽기=%d 입력=%d 출력=%d",
        getattr(u, "cache_creation_input_tokens", 0),
        getattr(u, "cache_read_input_tokens", 0),
        u.input_tokens,
        u.output_tokens,
    )

    return _parse_json(raw)


def _batched(iterable, n: int):
    """iterable 을 n 개씩 묶어 반환하는 제너레이터."""
    it = iter(iterable)
    while chunk := list(islice(it, n)):
        yield chunk


# ── Claude API 필터 ───────────────────────────────────────────────────────────

def _get_claude_client():
    import anthropic
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── 공개 API ──────────────────────────────────────────────────────────────────

def filter_fdi(articles: list[Article]) -> list[dict[str, Any]]:
    """기사 목록에서 FDI 관련 기사를 선별한다.

    ANTHROPIC_API_KEY 가 설정된 경우 Claude API 로 정밀 분석하고,
    없으면 키워드 필터로 대체한다.
    """
    _key_valid = (
        ANTHROPIC_API_KEY.startswith("sk-ant-")
        and len(ANTHROPIC_API_KEY) >= 40
        and ANTHROPIC_API_KEY.isascii()
    )
    if not _key_valid:
        log.warning("ANTHROPIC_API_KEY 미설정 또는 유효하지 않음 — 키워드 필터로 대체합니다.")
        return _keyword_filter(articles)

    client = _get_claude_client()
    results: list[dict[str, Any]] = []

    for batch_no, batch in enumerate(_batched(articles, BATCH_SIZE), start=1):
        log.info("배치 %d 처리 중 (%d건)...", batch_no, len(batch))
        try:
            judgments = _call_claude(client, batch)
        except Exception as exc:
            log.warning("배치 %d 처리 실패 (건너뜀): %s", batch_no, exc)
            continue

        judgment_map: dict[int, dict] = {j["index"]: j for j in judgments}

        for i, article in enumerate(batch):
            j = judgment_map.get(i)
            if not j:
                log.debug("판단 결과 없음 (index=%d): %s", i, article["title"])
                continue
            if not j.get("is_fdi"):
                continue

            results.append(
                {
                    **article,
                    "is_fdi": True,
                    "reason": j.get("reason", ""),
                    "summary": j.get("summary", ""),
                }
            )

    log.info("FDI 관련 기사 %d건 선별 완료", len(results))
    return results


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    from collector import collect_all

    articles = collect_all()
    if not articles:
        print("수집된 기사가 없습니다.")
        sys.exit(0)

    relevant = filter_fdi(articles)
    print(f"\nFDI 관련 기사: {len(relevant)}/{len(articles)}건")
    for a in relevant:
        print(f"\n  [{a['source']}] {a['title']}")
        print(f"  요약: {a['summary']}")
        print(f"  근거: {a['reason']}")
