# main.py
# FDI 뉴스레터 파이프라인 진입점.
# collect → filter → generate → save(docs/) → rebuild index 순서로 실행한다.

from __future__ import annotations

import html as html_module
import logging
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

if sys.platform == "win32":
    os.environ["PYTHONUTF8"] = "1"
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).parent / "docs"


def _step(name: str):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        log.info("▶ %s 시작", name)
        t0 = time.perf_counter()
        try:
            yield
        except Exception as exc:
            log.error("✗ %s 실패: %s", name, exc)
            raise
        else:
            log.info("✓ %s 완료 (%.1f초)", name, time.perf_counter() - t0)

    return _ctx()


def _cleanup_old_newsletters(keep_date: date) -> None:
    """선택된 날짜 외의 뉴스레터 HTML 파일을 삭제한다."""
    removed = 0
    for f in DOCS_DIR.glob("????-??-??.html"):
        if f.stem != keep_date.isoformat():
            f.unlink()
            removed += 1
    if removed:
        log.info("이전 뉴스레터 %d건 삭제 완료", removed)


def _save_newsletter(html_content: str, today: date) -> Path:
    """docs/YYYY-MM-DD.html 로 저장하고 이전 날짜 파일을 삭제한다."""
    DOCS_DIR.mkdir(exist_ok=True)
    _cleanup_old_newsletters(today)
    out_path = DOCS_DIR / f"{today.isoformat()}.html"
    out_path.write_text(html_content, encoding="utf-8")
    log.info("저장: %s", out_path)
    return out_path


def _rebuild_index() -> None:
    """docs/ 의 뉴스레터 파일을 스캔해 index.html 을 재생성한다."""
    DOCS_DIR.mkdir(exist_ok=True)
    files = sorted(DOCS_DIR.glob("????-??-??.html"), reverse=True)

    cards: list[str] = []
    for f in files:
        d = f.stem  # YYYY-MM-DD
        y, m, day = d.split("-")
        label = f"{y}년 {int(m):02d}월 {int(day):02d}일"
        cards.append(
            f'      <a href="{html_module.escape(d)}.html" class="card">'
            f'<span class="date">{html_module.escape(d)}</span>'
            f'<span class="label">{html_module.escape(label)}</span>'
            f'</a>'
        )

    total = len(files)
    cards_html = (
        "\n".join(cards)
        if cards
        else '      <p class="empty">아직 발행된 뉴스레터가 없습니다.</p>'
    )

    # 날짜 선택 시 이동 가능한 날짜 목록 (JS용)
    available_dates_js = ", ".join(f'"{f.stem}"' for f in files)

    index_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>FDI 뉴스레터 아카이브</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Arial,'Helvetica Neue',Helvetica,sans-serif; background: #f4f6f7; color: #2c3e50; }}
    header {{ background: #1a5276; color: #fff; padding: 28px 32px; }}
    header .eyebrow {{ font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; color: rgba(255,255,255,.7); margin-bottom: 4px; }}
    header h1 {{ font-size: 22px; font-weight: 700; }}
    header p {{ font-size: 13px; color: rgba(255,255,255,.85); margin-top: 4px; }}
    .container {{ max-width: 720px; margin: 0 auto; padding: 24px 16px; }}
    .date-picker-bar {{ background: #fff; border: 1px solid #d5d8dc; border-radius: 6px; padding: 16px 20px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
    .date-picker-bar label {{ font-size: 13px; font-weight: 600; color: #1a5276; white-space: nowrap; }}
    .date-picker-bar input[type="date"] {{ border: 1px solid #aab7b8; border-radius: 4px; padding: 6px 10px; font-size: 13px; color: #2c3e50; outline: none; }}
    .date-picker-bar input[type="date"]:focus {{ border-color: #1a5276; }}
    .date-picker-bar button {{ background: #1a5276; color: #fff; border: none; border-radius: 4px; padding: 7px 16px; font-size: 13px; cursor: pointer; white-space: nowrap; }}
    .date-picker-bar button:hover {{ background: #2e86c1; }}
    .date-picker-bar .msg {{ font-size: 12px; color: #e74c3c; display: none; }}
    .summary {{ background: #fff; border-left: 4px solid #2e86c1; padding: 12px 20px; margin-bottom: 20px; font-size: 14px; color: #1a5276; font-weight: 600; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }}
    .card {{ display: block; background: #fff; border: 1px solid #d5d8dc; border-radius: 6px; padding: 14px 16px; text-decoration: none; color: inherit; transition: box-shadow .15s, border-color .15s; }}
    .card:hover {{ border-color: #1a5276; box-shadow: 0 2px 8px rgba(26,82,118,.15); }}
    .card .date {{ display: block; font-size: 13px; font-weight: 700; color: #1a5276; }}
    .card .label {{ display: block; font-size: 11px; color: #717d7e; margin-top: 3px; }}
    .empty {{ color: #717d7e; font-size: 14px; padding: 24px 0; }}
    footer {{ text-align: center; padding: 24px 16px; font-size: 11px; color: #aab7b8; }}
  </style>
</head>
<body>
  <header>
    <div class="eyebrow">DAILY BRIEFING</div>
    <h1>FDI 뉴스레터 아카이브</h1>
    <p>총 {total}개 발행</p>
  </header>
  <div class="container">
    <div class="date-picker-bar">
      <label for="date-pick">날짜 선택</label>
      <input type="date" id="date-pick">
      <button onclick="goToDate()">이동</button>
      <span class="msg" id="date-msg">해당 날짜의 뉴스레터가 없습니다.</span>
    </div>
    <div class="summary">날짜를 선택해 해당 일자의 뉴스레터를 확인하세요.</div>
    <div class="grid">
{cards_html}
    </div>
  </div>
  <footer>자동 생성 · FDI 뉴스레터 파이프라인</footer>
  <script>
    var available = [{available_dates_js}];
    function goToDate() {{
      var d = document.getElementById('date-pick').value;
      var msg = document.getElementById('date-msg');
      if (!d) {{ msg.style.display = 'none'; return; }}
      if (available.indexOf(d) !== -1) {{
        window.location.href = d + '.html';
      }} else {{
        msg.style.display = 'inline';
      }}
    }}
    document.getElementById('date-pick').addEventListener('change', function() {{
      document.getElementById('date-msg').style.display = 'none';
    }});
  </script>
</body>
</html>"""

    (DOCS_DIR / "index.html").write_text(index_html, encoding="utf-8")
    log.info("index.html 재생성 완료 (%d건)", total)


def run() -> None:
    log.info("=" * 50)
    log.info("  FDI 뉴스레터 파이프라인 시작")
    log.info("=" * 50)
    pipeline_start = time.perf_counter()
    raw = os.environ.get("TARGET_DATE", "").strip()
    if raw:
        try:
            today = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            log.error("TARGET_DATE 형식 오류: '%s' (YYYY-MM-DD 형식이어야 합니다)", raw)
            sys.exit(1)
    else:
        today = date.today()
    log.info("  대상 날짜: %s", today.isoformat())

    # ── Step 1: RSS 수집 ──────────────────────────────────
    try:
        with _step("RSS 수집"):
            from collector import collect_all
            articles = collect_all()
    except Exception:
        sys.exit(1)

    if not articles:
        log.warning("수집된 기사가 없습니다. 파이프라인을 종료합니다.")
        _rebuild_index()
        return

    # ── Step 2: FDI 필터링 ────────────────────────────────
    try:
        with _step("FDI 필터링 (Claude API)"):
            from filter import filter_fdi
            relevant = filter_fdi(articles)
    except Exception:
        sys.exit(1)

    # ── Step 3: HTML 생성 ─────────────────────────────────
    try:
        with _step("HTML 생성"):
            from newsletter import build_html
            html_content = build_html(relevant, today)
    except Exception:
        sys.exit(1)

    # ── Step 4: 파일 저장 ─────────────────────────────────
    try:
        with _step("파일 저장"):
            out_path = _save_newsletter(html_content, today)
    except Exception:
        sys.exit(1)

    # ── Step 5: index.html 재생성 ─────────────────────────
    try:
        with _step("index.html 재생성"):
            _rebuild_index()
    except Exception:
        sys.exit(1)

    total_elapsed = time.perf_counter() - pipeline_start
    log.info("=" * 50)
    log.info(
        "  결과: 수집 %d건 → FDI 관련 %d건 → %s",
        len(articles),
        len(relevant),
        out_path.name,
    )
    log.info("  총 소요 시간: %.1f초", total_elapsed)
    log.info("=" * 50)


if __name__ == "__main__":
    run()
