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

# GitHub 저장소 정보 (index.html JS에서 Actions API 호출에 사용)
GH_OWNER = "CalebKKMin"
GH_REPO = "fdi-newsletter"
GH_WORKFLOW = "daily-newsletter.yml"
GH_BRANCH = "master"


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


def _save_newsletter(html_content: str, today: date) -> Path:
    """docs/YYYY-MM-DD.html 로 저장한다. 기존 파일은 덮어쓴다."""
    DOCS_DIR.mkdir(exist_ok=True)
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
            f'      <a href="{html_module.escape(d)}.html" class="card" target="_blank" rel="noopener">'
            f'<span class="date">{html_module.escape(d)}</span>'
            f'<span class="label">{html_module.escape(label)}</span>'
            f'<span class="open-icon">↗</span>'
            f'</a>'
        )

    total = len(files)
    cards_html = (
        "\n".join(cards)
        if cards
        else '      <p class="empty">아직 발행된 뉴스레터가 없습니다.<br>위에서 날짜를 선택하고 뉴스레터를 생성하세요.</p>'
    )

    available_dates_js = ", ".join(f'"{f.stem}"' for f in files)

    index_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>FDI 뉴스레터 아카이브</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:Arial,'Helvetica Neue',Helvetica,sans-serif;background:#f4f6f7;color:#2c3e50}}
    header{{background:#1a5276;color:#fff;padding:28px 32px}}
    header .eyebrow{{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,.7);margin-bottom:4px}}
    header h1{{font-size:22px;font-weight:700}}
    header p{{font-size:13px;color:rgba(255,255,255,.85);margin-top:4px}}
    .container{{max-width:720px;margin:0 auto;padding:24px 16px}}

    /* 생성 패널 */
    .gen-panel{{background:#fff;border:1px solid #d5d8dc;border-radius:8px;padding:20px;margin-bottom:20px}}
    .gen-panel h2{{font-size:14px;font-weight:700;color:#1a5276;margin-bottom:14px}}
    .gen-row{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
    .gen-row label{{font-size:13px;font-weight:600;color:#555;white-space:nowrap}}
    .gen-row input[type="date"]{{border:1px solid #aab7b8;border-radius:4px;padding:7px 10px;font-size:13px;color:#2c3e50;outline:none;flex:1;min-width:140px}}
    .gen-row input[type="date"]:focus{{border-color:#1a5276}}
    .btn-primary{{background:#1a5276;color:#fff;border:none;border-radius:4px;padding:8px 20px;font-size:13px;cursor:pointer;white-space:nowrap;font-weight:600}}
    .btn-primary:hover{{background:#2e86c1}}
    .btn-primary:disabled{{background:#aab7b8;cursor:not-allowed}}
    .btn-icon{{background:none;border:1px solid #d5d8dc;border-radius:4px;padding:7px 10px;font-size:14px;cursor:pointer;color:#555;line-height:1}}
    .btn-icon:hover{{border-color:#1a5276;color:#1a5276}}

    /* 상태 바 */
    .status-bar{{margin-top:12px;padding:10px 14px;border-radius:4px;font-size:13px;display:none}}
    .status-bar.info{{background:#eaf4fb;color:#1a5276;border-left:3px solid #2e86c1;display:block}}
    .status-bar.success{{background:#eafaf1;color:#1e8449;border-left:3px solid #27ae60;display:block}}
    .status-bar.error{{background:#fdedec;color:#c0392b;border-left:3px solid #e74c3c;display:block}}
    .status-bar a{{color:inherit;font-weight:700}}

    /* 아카이브 */
    .section-title{{font-size:13px;font-weight:700;color:#555;margin-bottom:12px;padding-bottom:6px;border-bottom:1px solid #d5d8dc}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}}
    .card{{display:block;background:#fff;border:1px solid #d5d8dc;border-radius:6px;padding:14px 16px;text-decoration:none;color:inherit;transition:box-shadow .15s,border-color .15s;position:relative}}
    .card:hover{{border-color:#1a5276;box-shadow:0 2px 8px rgba(26,82,118,.15)}}
    .card .date{{display:block;font-size:13px;font-weight:700;color:#1a5276}}
    .card .label{{display:block;font-size:11px;color:#717d7e;margin-top:3px}}
    .card .open-icon{{position:absolute;top:10px;right:10px;font-size:11px;color:#aab7b8}}
    .card:hover .open-icon{{color:#1a5276}}
    .empty{{color:#717d7e;font-size:13px;padding:24px 0;line-height:1.8}}

    /* 모달 */
    .modal-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;z-index:100}}
    .modal{{background:#fff;border-radius:8px;padding:28px;max-width:420px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,.2)}}
    .modal h3{{font-size:16px;font-weight:700;color:#1a5276;margin-bottom:10px}}
    .modal p{{font-size:13px;color:#555;margin-bottom:14px;line-height:1.6}}
    .modal p a{{color:#1a5276}}
    .modal input[type="password"]{{width:100%;border:1px solid #aab7b8;border-radius:4px;padding:8px 12px;font-size:13px;outline:none;margin-bottom:16px}}
    .modal input[type="password"]:focus{{border-color:#1a5276}}
    .modal-actions{{display:flex;gap:10px;justify-content:flex-end}}
    .btn-secondary{{background:#fff;color:#1a5276;border:1px solid #1a5276;border-radius:4px;padding:7px 16px;font-size:13px;cursor:pointer}}
    .btn-secondary:hover{{background:#eaf4fb}}
    .token-status{{font-size:11px;color:#27ae60;margin-bottom:4px;display:none}}

    footer{{text-align:center;padding:24px 16px;font-size:11px;color:#aab7b8}}
  </style>
</head>
<body>
  <header>
    <div class="eyebrow">DAILY BRIEFING</div>
    <h1>FDI 뉴스레터 아카이브</h1>
    <p>총 {total}개 발행</p>
  </header>

  <div class="container">
    <!-- 뉴스레터 생성 패널 -->
    <div class="gen-panel">
      <h2>뉴스레터 생성</h2>
      <div class="gen-row">
        <label for="date-pick">날짜</label>
        <input type="date" id="date-pick">
        <button class="btn-primary" id="gen-btn" onclick="generateNewsletter()">생성</button>
        <button class="btn-icon" onclick="showTokenModal()" title="GitHub 토큰 설정">⚙</button>
      </div>
      <div id="status-bar" class="status-bar"></div>
    </div>

    <!-- 아카이브 목록 -->
    <div class="section-title">발행된 뉴스레터 — {total}개 (날짜 클릭 시 새 창으로 열림)</div>
    <div class="grid">
{cards_html}
    </div>
  </div>

  <!-- GitHub 토큰 설정 모달 -->
  <div id="token-modal" class="modal-overlay" style="display:none" onclick="overlayClick(event)">
    <div class="modal">
      <h3>GitHub 토큰 설정</h3>
      <p>
        뉴스레터 생성을 위해 <strong>workflow</strong> 권한이 있는
        <a href="https://github.com/settings/tokens/new?scopes=workflow" target="_blank" rel="noopener">GitHub Personal Access Token</a>이 필요합니다.<br>
        토큰은 이 브라우저에만 저장되며 외부로 전송되지 않습니다.
      </p>
      <div id="token-saved-msg" class="token-status">✔ 토큰이 저장되어 있습니다.</div>
      <input type="password" id="token-input" placeholder="ghp_xxxxxxxxxxxx">
      <div class="modal-actions">
        <button class="btn-secondary" onclick="hideTokenModal()">취소</button>
        <button class="btn-primary" onclick="saveToken()">저장</button>
      </div>
    </div>
  </div>

  <footer>자동 생성 · FDI 뉴스레터 파이프라인</footer>

  <script>
    var OWNER = "{GH_OWNER}";
    var REPO  = "{GH_REPO}";
    var WORKFLOW = "{GH_WORKFLOW}";
    var BRANCH = "{GH_BRANCH}";
    var available = [{available_dates_js}];

    /* ── 상태 바 ── */
    function setStatus(msg, type) {{
      var el = document.getElementById('status-bar');
      el.innerHTML = msg;
      el.className = 'status-bar ' + (type || '');
    }}

    /* ── 뉴스레터 생성 (GitHub Actions 트리거) ── */
    async function generateNewsletter() {{
      var d = document.getElementById('date-pick').value;
      if (!d) {{ setStatus('날짜를 선택해주세요.', 'error'); return; }}

      var token = localStorage.getItem('gh_token');
      if (!token) {{
        setStatus('GitHub 토큰이 필요합니다. ⚙ 버튼을 눌러 먼저 토큰을 설정하세요.', 'error');
        showTokenModal();
        return;
      }}

      var btn = document.getElementById('gen-btn');
      btn.disabled = true;
      setStatus(d + ' 뉴스레터 생성 요청 중...', 'info');

      try {{
        var res = await fetch(
          'https://api.github.com/repos/' + OWNER + '/' + REPO + '/actions/workflows/' + WORKFLOW + '/dispatches',
          {{
            method: 'POST',
            headers: {{
              'Authorization': 'Bearer ' + token,
              'Accept': 'application/vnd.github.v3+json',
              'Content-Type': 'application/json',
            }},
            body: JSON.stringify({{ ref: BRANCH, inputs: {{ target_date: d }} }})
          }}
        );

        if (res.status === 204) {{
          var newsUrl = d + '.html';
          setStatus(
            '<strong>' + d + '</strong> 뉴스레터 생성이 시작됐습니다. ' +
            '약 2~3분 후 완료되면 <a href="' + newsUrl + '" target="_blank" rel="noopener">여기</a>에서 열거나, ' +
            '이 페이지를 새로고침해 아카이브에서 확인하세요.',
            'success'
          );
        }} else if (res.status === 401) {{
          setStatus('GitHub 토큰이 유효하지 않습니다. ⚙ 버튼으로 토큰을 다시 설정해주세요.', 'error');
          localStorage.removeItem('gh_token');
        }} else {{
          var body = await res.json().catch(function(){{ return {{}}; }});
          setStatus('오류 ' + res.status + ': ' + (body.message || '알 수 없는 오류'), 'error');
        }}
      }} catch (e) {{
        setStatus('요청 실패: ' + e.message, 'error');
      }} finally {{
        btn.disabled = false;
      }}
    }}

    /* ── 토큰 모달 ── */
    function showTokenModal() {{
      var saved = localStorage.getItem('gh_token');
      document.getElementById('token-saved-msg').style.display = saved ? 'block' : 'none';
      document.getElementById('token-input').value = '';
      document.getElementById('token-modal').style.display = 'flex';
    }}
    function hideTokenModal() {{
      document.getElementById('token-modal').style.display = 'none';
    }}
    function overlayClick(e) {{
      if (e.target === document.getElementById('token-modal')) hideTokenModal();
    }}
    function saveToken() {{
      var t = document.getElementById('token-input').value.trim();
      if (!t) {{ return; }}
      localStorage.setItem('gh_token', t);
      hideTokenModal();
      setStatus('토큰이 저장됐습니다. 이제 날짜를 선택하고 생성 버튼을 누르세요.', 'success');
    }}

    /* ── Enter 키로 생성 ── */
    document.getElementById('date-pick').addEventListener('keydown', function(e) {{
      if (e.key === 'Enter') generateNewsletter();
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

    # ── Step 1: RSS 수집 (target_date 기사만) ────────────────
    try:
        with _step("RSS 수집"):
            from collector import collect_all
            articles = collect_all(today)
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
