"""
=====================================================================
  config.py — 중앙 설정 관리
=====================================================================

[역할]
  모든 설정값을 한 곳에서 관리합니다.
  새 프로젝트에 적용할 때 이 파일의 값만 수정하면 됩니다.

[설정 항목]
  - 앱 메타데이터 (이름, 버전)
  - 로컬 서버 설정 (호스트, 포트)
  - 원격 서버 설정 (결과를 전송할 URL)
  - 로그 설정 (경로, 포맷)
  - CORS 설정

=====================================================================
"""
import os
import sys
from pathlib import Path

# ───────────────────────── 앱 메타데이터 ─────────────────────────
APP_NAME = "Local Agent Template"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "로컬 PC에서 실행되는 에이전트 서비스 템플릿"

# ───────────────────────── 로컬 서버 설정 ─────────────────────────
# FastAPI + Uvicorn이 바인딩할 주소와 포트
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 8000

# ──────────────────── 원격 서버 설정 (선택사항) ────────────────────
# 작업 결과를 원격 서버로 전송할 때 사용
# None이면 결과 전송을 건너뜁니다
REMOTE_SERVER_URL = None  # 예: "https://myapp.example.com/api/agent/result"
REMOTE_API_KEY = None     # 예: "Bearer your-api-key-here"

# ───────────────────────── 배치 파일 실행 설정 ─────────────────────────
# TEST_BAT_PATH
#   - agent가 "요청되었습니다."를 먼저 응답한 뒤 백그라운드에서 실행할 배치 파일입니다.
#   - 이 배치 파일은 실제 업무 Python 엔트리포인트(run-pack.py)를 호출합니다.
TEST_BAT_PATH = r"C:\Projects\test.bat"

# TEST_CALLBACK_URL
#   - Python 업무가 끝나 agent의 /api/bat/test/complete로 완료를 알려오면,
#     agent가 최종 결과를 다시 전달할 sample backend callback API입니다.
TEST_CALLBACK_URL = "http://127.0.0.1:8080/api/agent-test/callback"

# ───────────────────────── 로그 설정 ─────────────────────────────
def get_log_dir() -> Path:
    """
    로그 디렉토리 경로를 반환합니다.

    Windows: %LOCALAPPDATA%/LocalAgent/logs
    macOS/Linux: ~/.local-agent/logs
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", str(Path.home()))
        log_dir = Path(base) / "LocalAgent" / "logs"
    else:
        log_dir = Path.home() / ".local-agent" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


LOG_DIR = get_log_dir()
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# ───────────────────────── CORS 설정 ─────────────────────────────
# 어떤 웹앱에서 이 로컬 서버에 접근할 수 있는지 설정
# "*"는 모든 출처 허용 (로컬 서비스이므로 보안 이슈 없음)
# 특정 도메인만 허용하려면 리스트로 변경:
#   CORS_ORIGINS = ["https://myapp.example.com", "http://localhost:5173"]
CORS_ORIGINS = ["*"]
