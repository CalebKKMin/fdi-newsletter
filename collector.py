# collector.py
# RSS 피드를 수집하고 오늘 날짜 기사만 반환한다.
# 각 기사는 title / url / date / summary / source 키를 가진 dict 로 표현한다.

from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime, timezone
from typing import TypedDict

import feedparser

from config import MAX_ARTICLES_PER_FEED, RSS_FEEDS

log = logging.getLogger(__name__)


class Article(TypedDict):
    title: str
    url: str
    date: date
    summary: str
    source: str


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _parse_date(entry: feedparser.FeedParserDict) -> date | None:
    """feedparser 엔트리에서 발행일을 추출한다. 파싱 실패 시 None."""
    # feedparser 가 time.struct_time 으로 변환한 필드를 우선 사용
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t is not None:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).date()
            except (ValueError, TypeError):
                continue
    return None


def _extract_source(feed: feedparser.FeedParserDict) -> str:
    """피드 메타에서 출처 이름을 추출한다."""
    return feed.feed.get("title", "Unknown")


def _clean_text(raw: str) -> str:
    """HTML 태그와 엔티티를 제거하고 공백을 정리한다."""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _summary(entry: feedparser.FeedParserDict) -> str:
    """기사 본문 앞 200자를 반환한다."""
    raw = (
        entry.get("content", [{}])[0].get("value", "")
        or entry.get("summary", "")
        or entry.get("description", "")
    )
    return _clean_text(raw)[:200]


# ── 공개 API ──────────────────────────────────────────────────────────────────

def fetch_feed(feed_url: str) -> list[Article]:
    """단일 RSS 피드를 파싱해 오늘 날짜 Article 목록을 반환한다.
    수집 실패 또는 파싱 오류 시 빈 리스트를 반환하고 로그를 남긴다.
    """
    try:
        feed = feedparser.parse(feed_url)
    except Exception as exc:
        log.warning("피드 요청 실패 [%s]: %s", feed_url, exc)
        return []

    if feed.bozo and not feed.entries:
        log.warning("피드 파싱 오류 [%s]: %s", feed_url, feed.bozo_exception)
        return []

    source = _extract_source(feed)
    today = date.today()
    articles: list[Article] = []

    for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
        pub_date = _parse_date(entry)
        if pub_date is None:
            log.debug("발행일 없음, 건너뜀: %s", entry.get("title", ""))
            continue
        if pub_date != today:
            continue

        url = entry.get("link", "").strip()
        title = _clean_text(entry.get("title", ""))
        if not url or not title:
            continue

        articles.append(
            Article(
                title=title,
                url=url,
                date=pub_date,
                summary=_summary(entry),
                source=source,
            )
        )

    log.info("[%s] 오늘 기사 %d건 수집", source, len(articles))
    return articles


def collect_all() -> list[Article]:
    """RSS_FEEDS 의 모든 피드를 수집한다.
    중복 URL 을 제거하고 발행일 내림차순(기사 제목 오름차순)으로 정렬해 반환한다.
    """
    seen_urls: set[str] = set()
    all_articles: list[Article] = []

    for url in RSS_FEEDS:
        for article in fetch_feed(url):
            if article["url"] in seen_urls:
                continue
            seen_urls.add(article["url"])
            all_articles.append(article)

    all_articles.sort(key=lambda a: (a["date"], a["title"]), reverse=True)
    log.info("총 %d건 수집 (중복 제거 후)", len(all_articles))
    return all_articles


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    articles = collect_all()
    print(f"\n수집된 기사: {len(articles)}건")
    for a in articles:
        print(f"  [{a['source']}] {a['title']}")
        print(f"    {a['url']}")
        print(f"    {a['summary'][:80]}...")
