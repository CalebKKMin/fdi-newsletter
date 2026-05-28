# config.py
# 프로젝트 전체에서 사용하는 설정값을 한 곳에서 관리한다.

import os
from dotenv import load_dotenv

load_dotenv()

# ── Anthropic ──────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

# ── RSS 피드 목록 ──────────────────────────────────────────
RSS_FEEDS: list[str] = [
    "https://www.mk.co.kr/rss/30000001/",       # 매일경제
    "https://www.hankyung.com/feed/all-news",   # 한국경제
    "https://biz.chosun.com/rss/",              # 조선비즈
    "https://www.yna.co.kr/rss/economy.xml",    # 연합뉴스 경제
]

# ── 수집 옵션 ──────────────────────────────────────────────
MAX_ARTICLES_PER_FEED: int = int(os.getenv("MAX_ARTICLES_PER_FEED", "20"))

# ── 필터 옵션 ──────────────────────────────────────────────
BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10"))

# ── 뉴스레터 제목 접두사 ───────────────────────────────────
NEWSLETTER_SUBJECT_PREFIX: str = "[FDI 뉴스레터]"
