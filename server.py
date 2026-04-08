"""
=====================================================================
  server.py - FastAPI 서버 (API 라우터 + 실시간 로그 뷰어)
=====================================================================

[역할]
  HTTP API를 통해 외부 요청을 받아 worker에게 전달하고 결과를 반환합니다.
  또한 개발 편의를 위한 실시간 로그 뷰어 페이지를 제공합니다.

[데이터 흐름]
  ┌──────────┐   HTTP 요청    ┌───────────┐  함수 호출  ┌──────────┐
  │  웹앱     │ ────────────→ │ server.py │ ─────────→ │ worker.py│
  │ (원격)   │ ←──────────── │ (FastAPI) │ ←───────── │ (로직)   │
  └──────────┘   HTTP 응답    └───────────┘  결과 반환   └──────────┘

[엔드포인트 목록]
  GET  /              → 헬스체크 (서비스 상태)
  POST /api/task      → 작업 요청 처리
  GET  /api/task/sample → 샘플 요청/응답 확인
  GET  /api/test      → 테스트 요청 실행 (더미 데이터로)
  GET  /logs/view     → 실시간 로그 뷰어 (HTML 페이지)
  GET  /logs/entries  → 로그 데이터 JSON API
  DELETE /logs        → 로그 버퍼 초기화
  GET  /docs          → Swagger API 문서 (FastAPI 자동 생성)

[기술 해설: FastAPI]
  FastAPI는 Python의 비동기 웹 프레임워크입니다.
  - Pydantic 모델로 자동 유효성 검사
  - /docs 경로에 Swagger UI 자동 생성
  - async/await로 비동기 처리 (동시 요청 가능)
  - 타입 힌트로 자동 문서화

=====================================================================
"""
import time
import json
import logging
import httpx

from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import config
from models import HealthResponse, TaskRequest, TaskResponse
import worker
import log_manager

logger = logging.getLogger(__name__)


# ╔═══════════════════════════════════════════════════════════════╗
# ║  1. FastAPI 앱 생성                                            ║
# ║                                                               ║
# ║  [기술 해설: FastAPI 인스턴스]                                    ║
# ║  FastAPI()는 ASGI 앱 객체를 생성합니다.                           ║
# ║  이 객체에 라우트(엔드포인트)와 미들웨어를 등록합니다.                ║
# ║  Uvicorn이 이 객체를 받아서 HTTP 서버로 실행합니다.                 ║
# ╚═══════════════════════════════════════════════════════════════╝

app = FastAPI(
    title=config.APP_NAME,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION,
    docs_url="/docs",       # Swagger UI 경로
    redoc_url="/redoc",     # ReDoc 문서 경로
)

# 서버 시작 시각 (uptime 계산용)
_start_time: float = 0.0


# ╔═══════════════════════════════════════════════════════════════╗
# ║  2. 미들웨어 설정                                               ║
# ║                                                               ║
# ║  [기술 해설: 미들웨어(Middleware)]                                ║
# ║  미들웨어는 모든 요청/응답을 가로채는 "중간 처리기"입니다.             ║
# ║  요청이 엔드포인트에 도달하기 전/후에 공통 처리를 합니다.              ║
# ║  실행 순서: 요청 → 미들웨어A → 미들웨어B → 엔드포인트               ║
# ║            응답 ← 미들웨어A ← 미들웨어B ← 엔드포인트               ║
# ╚═══════════════════════════════════════════════════════════════╝

# ──────── 2-1. CORS 미들웨어 ────────
# [기술 해설: CORS (Cross-Origin Resource Sharing)]
# 브라우저의 '동일 출처 정책'으로 인해, 다른 도메인의 웹앱에서
# 이 로컬 서버로 요청하면 기본적으로 차단됩니다.
# CORS 미들웨어가 응답에 허용 헤더를 추가하여 이를 해제합니다.
# 참고: https://developer.mozilla.org/ko/docs/Web/HTTP/CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,  # 허용할 웹앱 도메인
    allow_credentials=True,
    allow_methods=["*"],    # 모든 HTTP 메서드 허용
    allow_headers=["*"],    # 모든 헤더 허용
)


# ──────── 2-2. Private Network Access 미들웨어 ────────
# [기술 해설: Private Network Access]
# Chrome 브라우저는 외부 HTTPS 사이트에서 localhost(사설 네트워크)로의
# 요청을 추가로 제한합니다. 이 미들웨어가 허용 헤더를 추가합니다.
# 참고: https://developer.chrome.com/blog/private-network-access-preflight
@app.middleware("http")
async def private_network_access(request: Request, call_next):
    response = await call_next(request)
    if request.headers.get("access-control-request-private-network") == "true":
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


# ──────── 2-3. 요청 로깅 미들웨어 ────────
# 모든 API 요청의 메서드, 경로, 상태코드, 소요시간을 기록합니다.
# 로그 뷰어에서 "어떤 요청이 들어왔는지" 실시간 확인 가능합니다.
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000

    # /logs/ 경로는 로그 폴링이므로 로깅 제외 (무한 로그 방지)
    if not request.url.path.startswith("/logs"):
        logger.info(
            f"[HTTP] {request.method} {request.url.path}"
            f" -> {response.status_code} ({elapsed:.0f}ms)"
        )

    return response


# ╔═══════════════════════════════════════════════════════════════╗
# ║  3. 서버 생명주기 (Lifecycle)                                    ║
# ║                                                               ║
# ║  [기술 해설: on_event]                                          ║
# ║  FastAPI는 ASGI 앱의 생명주기 훅을 제공합니다.                     ║
# ║  startup: 서버가 요청을 받기 시작하기 전에 실행                     ║
# ║  shutdown: 서버가 종료될 때 실행                                  ║
# ║  무거운 리소스(DB, 브라우저 등)의 초기화/정리에 사용합니다.            ║
# ╚═══════════════════════════════════════════════════════════════╝

@app.on_event("startup")
async def on_startup():
    global _start_time
    _start_time = time.time()

    logger.info("=" * 50)
    logger.info(f"  {config.APP_NAME} v{config.APP_VERSION}")
    logger.info(f"  Server:    http://{config.LOCAL_HOST}:{config.LOCAL_PORT}")
    logger.info(f"  API Docs:  http://{config.LOCAL_HOST}:{config.LOCAL_PORT}/docs")
    logger.info(f"  Log Viewer: http://{config.LOCAL_HOST}:{config.LOCAL_PORT}/logs/view")
    logger.info("=" * 50)

    # 워커 초기화
    await worker.initialize()


@app.on_event("shutdown")
async def on_shutdown():
    await worker.cleanup()
    logger.info("Server stopped")


# ╔═══════════════════════════════════════════════════════════════╗
# ║  4. API 엔드포인트                                              ║
# ╚═══════════════════════════════════════════════════════════════╝

# ──────── 4-1. 헬스체크 ────────
@app.get("/", response_model=HealthResponse, summary="Health Check")
async def health_check():
    """서비스 상태를 확인합니다. 웹앱이 주기적으로 호출하여 연결 상태를 표시합니다."""
    return HealthResponse(
        service=config.APP_NAME,
        status="running",
        version=config.APP_VERSION,
        uptime_seconds=round(time.time() - _start_time, 2),
    )


# ──────── 4-2. 작업 처리 (핵심) ────────
@app.post("/api/task", response_model=TaskResponse, summary="Execute Task")
async def execute_task(request: TaskRequest):
    """
    작업 요청을 받아 worker에게 위임하고 결과를 반환합니다.

    데이터 흐름:
      Step 1: 이 함수가 TaskRequest를 수신
      Step 2: worker.process_task()가 실제 작업 수행
      Step 3: 워커가 TaskResponse를 반환
      Step 4: (선택) 원격 서버에 결과 전송
      Step 5: 웹앱에 응답 반환
    """
    logger.info(f"[TASK] Request received: type={request.task_type}")

    # Step 2: 워커에게 작업 위임
    response = await worker.process_task(request)

    # Step 4: (선택) 원격 서버에 결과 전송
    if response.success and config.REMOTE_SERVER_URL:
        await _send_result_to_remote(response)

    logger.info(
        f"[TASK] Response: success={response.success}, "
        f"items={response.total_count}, time={response.elapsed_ms}ms"
    )
    return response


# ──────── 4-3. 테스트 요청 (개발 도구) ────────
@app.get("/api/test", summary="Run Test Request")
async def run_test():
    """
    더미 데이터로 테스트 요청을 실행합니다.

    [용도]
    트레이 메뉴의 "Test Request" 또는 브라우저에서 직접 호출하여
    로그 뷰어에서 전체 데이터 흐름을 확인할 수 있습니다.

    [데이터 흐름]
    GET /api/test
      -> 내부에서 POST /api/task 로직과 동일하게 처리
      -> 로그 뷰어에서 요청/처리/응답 전 과정 확인 가능
    """
    logger.info("[TEST] === Test request triggered ===")

    # 테스트용 더미 요청 생성
    test_request = TaskRequest(
        task_type="test",
        input_data={"items": ["Hello", "World", "Test"]},
        options={"max_count": 3},
    )

    logger.info(f"[TEST] Input: {json.dumps(test_request.model_dump(), ensure_ascii=False)}")

    # 실제 작업 실행
    response = await worker.process_task(test_request)

    logger.info(f"[TEST] Output: success={response.success}, count={response.total_count}")
    logger.info("[TEST] === Test completed ===")

    return {
        "test": "completed",
        "request": test_request.model_dump(),
        "response": response.model_dump(),
    }


# ──────── 4-4. 샘플 확인 ────────
@app.get("/api/task/sample", summary="Sample Request/Response")
async def get_sample():
    """POST /api/task에 보낼 샘플 요청과 예상 응답 형태를 확인합니다."""
    return {
        "info": "POST /api/task with this body:",
        "sample_request": {
            "task_type": "process",
            "input_data": {"items": ["apple", "banana", "grape"]},
            "options": {"max_count": 10}
        },
    }


# ╔═══════════════════════════════════════════════════════════════╗
# ║  5. 실시간 로그 뷰어                                            ║
# ║                                                               ║
# ║  [기술 해설]                                                    ║
# ║  브라우저에서 로그를 실시간으로 볼 수 있는 웹 페이지입니다.            ║
# ║  JavaScript가 500ms마다 /logs/entries를 폴링하여 새 로그를        ║
# ║  화면에 추가합니다. SSE나 WebSocket 없이 단순 폴링으로 구현하여      ║
# ║  코드를 간결하게 유지합니다.                                       ║
# ╚═══════════════════════════════════════════════════════════════╝

@app.get("/logs/entries", summary="Get Log Entries (JSON)")
async def get_log_entries(
    after_id: int = Query(0, description="Return logs after this ID"),
    level: str = Query(None, description="Filter by level: INFO, WARNING, ERROR"),
):
    """로그 버퍼에서 엔트리를 JSON으로 반환합니다."""
    return log_manager.get_logs(after_id=after_id, level=level)


@app.delete("/logs", summary="Clear Logs")
async def clear_logs():
    """로그 버퍼를 초기화합니다."""
    log_manager.clear_logs()
    logger.info("[LOGS] Buffer cleared")
    return {"status": "cleared"}


@app.get("/logs/view", response_class=HTMLResponse, summary="Log Viewer (Web UI)")
async def log_viewer_page():
    """
    실시간 로그 뷰어 HTML 페이지를 반환합니다.

    [기능]
    - 500ms마다 새 로그를 자동으로 가져와 표시
    - 로그 레벨별 색상 (INFO=초록, WARNING=노랑, ERROR=빨강)
    - 레벨 필터링, 로그 검색, 자동 스크롤
    - Test Request 버튼으로 테스트 발사 가능
    - Clear 버튼으로 로그 초기화

    [기술 해설: HTMLResponse]
    FastAPI는 response_class=HTMLResponse를 지정하면
    문자열을 HTML로 반환합니다. (기본은 JSON)
    """
    return _LOG_VIEWER_HTML


# ╔═══════════════════════════════════════════════════════════════╗
# ║  6. 원격 서버 결과 전송 (선택사항)                                 ║
# ║                                                               ║
# ║  [기술 해설: httpx.AsyncClient]                                 ║
# ║  httpx는 Python의 비동기 HTTP 클라이언트입니다.                    ║
# ║  async with로 사용하면 연결이 자동으로 정리됩니다.                   ║
# ╚═══════════════════════════════════════════════════════════════╝

async def _send_result_to_remote(response: TaskResponse):
    """작업 결과를 원격 서버에 전송합니다."""
    try:
        headers = {"Content-Type": "application/json"}
        if config.REMOTE_API_KEY:
            headers["Authorization"] = config.REMOTE_API_KEY

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                config.REMOTE_SERVER_URL,
                json=response.model_dump(),
                headers=headers,
            )
            logger.info(f"[REMOTE] Sent to remote: status={resp.status_code}")

    except Exception as e:
        logger.warning(f"[REMOTE] Send failed (ignored): {e}")


# ╔═══════════════════════════════════════════════════════════════╗
# ║  7. 로그 뷰어 HTML (임베디드)                                    ║
# ║                                                               ║
# ║  별도 HTML 파일 없이 Python 문자열로 관리합니다.                    ║
# ║  이렇게 하면 단일 .py 파일만으로 로그 뷰어가 동작합니다.             ║
# ╚═══════════════════════════════════════════════════════════════╝

_LOG_VIEWER_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Log Viewer - """ + config.APP_NAME + """</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: #1a1a2e; color: #e0e0e0;
    font-family: 'Cascadia Code','Consolas','Courier New', monospace;
    font-size: 13px; height: 100vh; display: flex; flex-direction: column;
  }

  /* 상단 툴바 */
  .toolbar {
    background: #16213e; padding: 10px 16px;
    display: flex; align-items: center; gap: 10px;
    border-bottom: 1px solid #0f3460; flex-shrink: 0;
  }
  .toolbar h1 {
    font-size: 15px; font-weight: 600; color: #e94560;
    margin-right: auto;
  }
  .toolbar button {
    padding: 6px 14px; border: 1px solid #0f3460; border-radius: 6px;
    background: #0f3460; color: #e0e0e0; cursor: pointer;
    font-size: 12px; font-family: inherit; transition: all 0.2s;
  }
  .toolbar button:hover { background: #e94560; border-color: #e94560; }
  .toolbar button.active { background: #e94560; border-color: #e94560; }
  .toolbar select, .toolbar input {
    padding: 5px 8px; border: 1px solid #0f3460; border-radius: 6px;
    background: #1a1a2e; color: #e0e0e0; font-size: 12px;
    font-family: inherit;
  }
  .toolbar input { width: 180px; }

  /* 상태 표시 */
  .status {
    display: flex; align-items: center; gap: 6px;
    font-size: 11px; color: #888;
  }
  .status .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #52c41a; animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%,100% { opacity: 1; } 50% { opacity: 0.4; }
  }

  /* 로그 영역 */
  #log-container {
    flex: 1; overflow-y: auto; padding: 8px 16px;
    scroll-behavior: smooth;
  }

  /* 개별 로그 라인 */
  .log-line {
    padding: 3px 0; display: flex; gap: 10px; line-height: 1.5;
    border-bottom: 1px solid rgba(255,255,255,0.03);
    animation: fadeIn 0.3s ease;
  }
  @keyframes fadeIn { from { opacity:0; transform:translateY(-4px); } to { opacity:1; } }

  .log-time { color: #666; min-width: 85px; flex-shrink: 0; }
  .log-level {
    min-width: 60px; flex-shrink: 0; font-weight: 700;
    padding: 0 6px; border-radius: 3px; text-align: center;
  }
  .log-module { color: #7c8daf; min-width: 80px; flex-shrink: 0; }
  .log-msg { color: #ddd; word-break: break-all; }

  /* 레벨별 색상 */
  .level-INFO    .log-level { color: #52c41a; background: rgba(82,196,26,0.1); }
  .level-WARNING .log-level { color: #faad14; background: rgba(250,173,20,0.1); }
  .level-ERROR   .log-level { color: #ff4d4f; background: rgba(255,77,79,0.15); }
  .level-ERROR   .log-msg   { color: #ff6b6b; }

  /* 태그 강조 */
  .tag-HTTP { color: #69b1ff; font-weight: 600; }
  .tag-TASK { color: #b37feb; font-weight: 600; }
  .tag-TEST { color: #ff85c0; font-weight: 600; }

  /* 빈 상태 */
  .empty {
    text-align: center; color: #555; padding: 60px 0; font-size: 14px;
  }

  /* 하단 상태바 */
  .statusbar {
    background: #16213e; padding: 6px 16px;
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid #0f3460; flex-shrink: 0;
    font-size: 11px; color: #666;
  }
</style>
</head>
<body>

<div class="toolbar">
  <h1>""" + config.APP_NAME + """ - Log Viewer</h1>
  <div class="status"><div class="dot"></div> Live</div>

  <select id="levelFilter" onchange="applyFilter()">
    <option value="">All Levels</option>
    <option value="INFO">INFO</option>
    <option value="WARNING">WARNING</option>
    <option value="ERROR">ERROR</option>
  </select>

  <input type="text" id="searchInput" placeholder="Search..." oninput="applySearch()">

  <button onclick="runTest()" title="Send a test request to see the full data flow">
    Test Request
  </button>
  <button onclick="clearLogs()">Clear</button>
  <button id="scrollBtn" class="active" onclick="toggleScroll()">Auto-scroll</button>
</div>

<div id="log-container">
  <div class="empty" id="empty-msg">Waiting for logs...</div>
</div>

<div class="statusbar">
  <span id="stats">0 entries</span>
  <span>Polling every 500ms | <a href="/docs" style="color:#69b1ff;">Swagger Docs</a></span>
</div>

<script>
let lastId = 0;
let autoScroll = true;
let allEntries = [];

// 태그별 색상 강조
function highlightTags(msg) {
  return msg
    .replace(/\\[(HTTP|TASK|TEST|REMOTE|LOGS)\\]/g,
      '<span class="tag-$1">[$1]</span>');
}

// 로그 라인 HTML 생성
function renderLine(entry) {
  return '<div class="log-line level-' + entry.level + '" data-msg="'
    + entry.message.toLowerCase() + '">'
    + '<span class="log-time">' + entry.timestamp + '</span>'
    + '<span class="log-level">' + entry.level + '</span>'
    + '<span class="log-module">' + entry.module + '</span>'
    + '<span class="log-msg">' + highlightTags(esc(entry.message)) + '</span>'
    + '</div>';
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// 새 로그 가져오기 (폴링)
async function fetchLogs() {
  try {
    const level = document.getElementById('levelFilter').value;
    let url = '/logs/entries?after_id=' + lastId;
    if (level) url += '&level=' + level;

    const resp = await fetch(url);
    const entries = await resp.json();

    if (entries.length > 0) {
      document.getElementById('empty-msg')?.remove();
      const container = document.getElementById('log-container');

      entries.forEach(e => {
        allEntries.push(e);
        const div = document.createElement('div');
        div.innerHTML = renderLine(e);
        container.appendChild(div.firstChild);
        lastId = e.id;
      });

      if (autoScroll) {
        container.scrollTop = container.scrollHeight;
      }

      applySearch();
      document.getElementById('stats').textContent = allEntries.length + ' entries';
    }
  } catch (e) { /* server not ready yet */ }
}

// 테스트 요청 발사
async function runTest() {
  try { await fetch('/api/test'); }
  catch(e) { console.error(e); }
}

// 로그 초기화
async function clearLogs() {
  await fetch('/logs', { method: 'DELETE' });
  document.getElementById('log-container').innerHTML =
    '<div class="empty" id="empty-msg">Cleared. Waiting for logs...</div>';
  allEntries = [];
  lastId = 0;
  document.getElementById('stats').textContent = '0 entries';
}

// 레벨 필터 (서버측)
function applyFilter() {
  document.getElementById('log-container').innerHTML =
    '<div class="empty" id="empty-msg">Reloading...</div>';
  allEntries = [];
  lastId = 0;
}

// 텍스트 검색 (클라이언트측)
function applySearch() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  document.querySelectorAll('.log-line').forEach(el => {
    el.style.display = !q || el.dataset.msg.includes(q) ? '' : 'none';
  });
}

// 자동 스크롤 토글
function toggleScroll() {
  autoScroll = !autoScroll;
  const btn = document.getElementById('scrollBtn');
  btn.classList.toggle('active', autoScroll);
}

// 500ms마다 폴링
setInterval(fetchLogs, 500);
fetchLogs();
</script>
</body>
</html>"""
