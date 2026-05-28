# newsletter.py
# 필터링된 기사 목록을 받아 GitHub Pages 용 standalone HTML 페이지를 생성한다.

from __future__ import annotations

import html
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from config import NEWSLETTER_SUBJECT_PREFIX, RSS_FEEDS

# ── 디자인 상수 ───────────────────────────────────────────────────────────────
_COLOR_PRIMARY = "#1a5276"       # 남색 헤더·링크
_COLOR_ACCENT  = "#2e86c1"       # 섹션 구분선
_COLOR_BG      = "#f4f6f7"       # 전체 배경
_COLOR_CARD    = "#ffffff"       # 카드 배경
_COLOR_BORDER  = "#d5d8dc"       # 테이블 테두리
_COLOR_META    = "#717d7e"       # 출처·날짜 등 보조 텍스트
_COLOR_SUMMARY = "#2c3e50"       # 본문 텍스트
_FONT          = "Arial, 'Helvetica Neue', Helvetica, sans-serif"
_MAX_WIDTH     = "640px"

# 피드 URL → 출처 이름 역매핑 (푸터용)
_FEED_SOURCES: list[str] = [url.split("/")[2] for url in RSS_FEEDS]


# ── 공개 API ──────────────────────────────────────────────────────────────────

def build_html(articles: list[dict[str, Any]], today: date | None = None) -> str:
    """기사 목록을 받아 standalone HTML 페이지를 반환한다."""
    d = today or date.today()
    date_str = f"{d.year}년 {d.month:02d}월 {d.day:02d}일"
    title = f"FDI 뉴스레터 — {date_str}"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts: list[str] = []
    parts.append(_html_head(title))
    parts.append(_header(date_str))
    parts.append(_summary_bar(len(articles)))

    if articles:
        parts.append(_article_sections(articles))
    else:
        parts.append(_empty_state())

    parts.append(_footer(now_str))
    parts.append(_html_tail())

    return "".join(parts)


# ── HTML 조각 빌더 ────────────────────────────────────────────────────────────

def _html_head(title: str = "FDI 뉴스레터") -> str:
    return (
        '<!DOCTYPE html>'
        '<html lang="ko">'
        '<head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="X-UA-Compatible" content="IE=edge">'
        f'<title>{html.escape(title)}</title>'
        '</head>'
        f'<body style="margin:0;padding:0;background:{_COLOR_BG};'
        f'font-family:{_FONT};font-size:14px;color:{_COLOR_SUMMARY};">'
        # 목록으로 돌아가기 네비게이션 바
        f'<div style="background:#ffffff;border-bottom:1px solid {_COLOR_BORDER};padding:10px 20px;">'
        f'<a href="index.html" style="color:{_COLOR_PRIMARY};text-decoration:none;'
        f'font-size:13px;font-weight:600;">← 목록으로</a>'
        '</div>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{_COLOR_BG};">'
        '<tr><td align="center" style="padding:24px 16px;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:{_MAX_WIDTH};width:100%;">'
    )


def _html_tail() -> str:
    return (
        '</table>'   # inner
        '</td></tr>'
        '</table>'   # outer
        '</body></html>'
    )


def _header(date_str: str) -> str:
    return (
        '<tr><td>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{_COLOR_PRIMARY};border-radius:8px 8px 0 0;">'
        '<tr>'
        '<td style="padding:28px 32px;">'
        f'<p style="margin:0 0 4px 0;font-size:11px;color:rgba(255,255,255,0.7);'
        f'letter-spacing:1.5px;text-transform:uppercase;">DAILY BRIEFING</p>'
        f'<h1 style="margin:0;font-size:22px;font-weight:700;color:#ffffff;'
        f'line-height:1.3;">FDI 뉴스레터</h1>'
        f'<p style="margin:6px 0 0 0;font-size:13px;color:rgba(255,255,255,0.85);">'
        f'{date_str}</p>'
        '</td>'
        '</tr>'
        '</table>'
        '</td></tr>'
    )


def _summary_bar(count: int) -> str:
    msg = (
        f"오늘의 FDI 관련 뉴스 <strong>{count}건</strong>"
        if count
        else "오늘의 FDI 관련 기사가 없습니다"
    )
    return (
        '<tr><td>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{_COLOR_CARD};border-left:4px solid {_COLOR_ACCENT};">'
        '<tr>'
        f'<td style="padding:14px 28px;font-size:14px;color:{_COLOR_PRIMARY};'
        f'font-weight:600;">{msg}</td>'
        '</tr>'
        '</table>'
        '</td></tr>'
        # 구분 여백
        f'<tr><td style="height:2px;background:{_COLOR_BORDER};"></td></tr>'
    )


def _article_sections(articles: list[dict[str, Any]]) -> str:
    # 출처별로 그룹핑 (입력 순서 보존)
    by_source: dict[str, list] = defaultdict(list)
    for a in articles:
        by_source[a["source"]].append(a)

    parts: list[str] = []
    for source, group in by_source.items():
        parts.append(_section_header(source, len(group)))
        for i, article in enumerate(group):
            parts.append(_article_row(article, last=(i == len(group) - 1)))
        parts.append(_section_spacer())

    return "".join(parts)


def _section_header(source: str, count: int) -> str:
    esc = html.escape(source)
    return (
        '<tr><td>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{_COLOR_CARD};">'
        '<tr>'
        f'<td style="padding:16px 28px 8px 28px;border-top:3px solid {_COLOR_PRIMARY};">'
        f'<span style="font-size:12px;font-weight:700;color:{_COLOR_PRIMARY};'
        f'letter-spacing:0.5px;text-transform:uppercase;">{esc}</span>'
        f'<span style="margin-left:8px;font-size:11px;color:{_COLOR_META};">'
        f'{count}건</span>'
        '</td>'
        '</tr>'
        '</table>'
        '</td></tr>'
    )


def _article_row(article: dict[str, Any], *, last: bool) -> str:
    title   = html.escape(article.get("title", ""))
    url     = html.escape(article.get("url", "#"))
    summary = html.escape(article.get("summary", ""))
    reason  = html.escape(article.get("reason", ""))

    border_bottom = (
        "" if last
        else f"border-bottom:1px solid {_COLOR_BORDER};"
    )

    summary_block = ""
    if summary:
        summary_block = (
            f'<p style="margin:4px 0 0 0;font-size:12px;color:{_COLOR_META};">'
            f'{summary}</p>'
        )

    reason_block = ""
    if reason:
        reason_block = (
            f'<p style="margin:3px 0 0 0;font-size:11px;color:{_COLOR_ACCENT};">'
            f'▸ {reason}</p>'
        )

    return (
        '<tr><td>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{_COLOR_CARD};">'
        '<tr>'
        f'<td style="padding:12px 28px;{border_bottom}">'
        f'<a href="{url}" target="_blank" '
        f'style="font-size:14px;font-weight:600;color:{_COLOR_PRIMARY};'
        f'text-decoration:none;line-height:1.4;">{title}</a>'
        f'{summary_block}'
        f'{reason_block}'
        '</td>'
        '</tr>'
        '</table>'
        '</td></tr>'
    )


def _section_spacer() -> str:
    return f'<tr><td style="height:12px;background:{_COLOR_BG};"></td></tr>'


def _empty_state() -> str:
    return (
        '<tr><td>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{_COLOR_CARD};">'
        '<tr>'
        '<td align="center" style="padding:48px 32px;">'
        f'<p style="margin:0;font-size:32px;">📭</p>'
        f'<p style="margin:12px 0 0 0;font-size:15px;color:{_COLOR_META};">'
        '오늘의 FDI 관련 기사가 없습니다.</p>'
        f'<p style="margin:6px 0 0 0;font-size:12px;color:{_COLOR_BORDER};">'
        '내일 다시 확인해 주세요.</p>'
        '</td>'
        '</tr>'
        '</table>'
        '</td></tr>'
    )


def _footer(now_str: str) -> str:
    sources = html.escape(", ".join(_FEED_SOURCES))
    return (
        f'<tr><td style="height:12px;background:{_COLOR_BG};"></td></tr>'
        '<tr><td>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{_COLOR_CARD};border-radius:0 0 8px 8px;'
        f'border-top:1px solid {_COLOR_BORDER};">'
        '<tr>'
        f'<td style="padding:16px 28px;">'
        f'<p style="margin:0;font-size:11px;color:{_COLOR_META};">'
        f'생성: {html.escape(now_str)}</p>'
        f'<p style="margin:4px 0 0 0;font-size:11px;color:{_COLOR_META};">'
        f'수집 출처: {sources}</p>'
        '</td>'
        '</tr>'
        '</table>'
        '</td></tr>'
    )


# ── 단독 실행: 브라우저 미리보기 ───────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import tempfile
    import webbrowser

    sample: list[dict[str, Any]] = [
        {
            "title": "삼성전자, 미국 텍사스에 반도체 공장 20조 원 추가 투자",
            "url": "https://example.com/1",
            "summary": "삼성전자가 미국 텍사스 테일러 공장에 20조 원 규모의 추가 투자를 결정했다.",
            "source": "매일경제",
            "reason": "국내 기업의 해외 직접투자(그린필드) 사례",
        },
        {
            "title": "산업부, 외국인 투자유치 인센티브 확대 방안 발표",
            "url": "https://example.com/2",
            "summary": "산업통상자원부가 외국 기업 국내 투자 인센티브를 대폭 확대하는 방안을 발표했다.",
            "source": "연합뉴스 경제",
            "reason": "투자 유치 정책 변경 관련 산업부 발표",
        },
        {
            "title": "KOTRA, 올해 외국인 직접투자 역대 최고치 전망",
            "url": "https://example.com/3",
            "summary": "코트라가 올해 외국인 직접투자 규모가 역대 최고치를 기록할 것으로 전망했다.",
            "source": "연합뉴스 경제",
            "reason": "코트라 FDI 통계 및 전망 발표",
        },
        {
            "title": "현대차, 인도네시아 합작공장 설립 MOU 체결",
            "url": "https://example.com/4",
            "summary": "현대자동차가 인도네시아 기업과 EV 합작공장 설립을 위한 MOU를 체결했다.",
            "source": "한국경제",
            "reason": "국내 기업의 해외 합작 직접투자",
        },
    ]

    # 기사 없는 경우도 테스트
    if "--empty" in sys.argv:
        sample = []

    html_body = build_html(sample)
    print(f"HTML 길이: {len(html_body):,} bytes")

    # HTML 미리보기 (브라우저 열기)
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(html_body)
        tmp_path = f.name

    print(f"\n브라우저 미리보기: {tmp_path}")
    webbrowser.open(f"file:///{tmp_path}")
