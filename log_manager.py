"""
=====================================================================
  log_manager.py - 실시간 로그 관리 모듈
=====================================================================

[역할]
  모든 로그 메시지를 메모리 버퍼에 저장하여, 웹 기반 로그 뷰어에서
  실시간으로 조회할 수 있게 합니다.

[기술 해설]
  Python의 logging 모듈은 '핸들러(Handler)' 패턴을 사용합니다.
  로그가 발생하면 등록된 모든 핸들러에게 메시지가 전달됩니다.

  기본 핸들러: FileHandler(파일), StreamHandler(콘솔)
  우리가 추가: BufferHandler(메모리 deque) ← 이것이 이 모듈

  이 버퍼에 쌓인 로그를 FastAPI 엔드포인트(/logs)로 노출하면,
  브라우저에서 실시간 로그 뷰어를 만들 수 있습니다.

[데이터 흐름]
  logger.info("메시지")
    -> FileHandler   -> 파일에 기록
    -> StreamHandler  -> 콘솔에 출력
    -> BufferHandler  -> 메모리 deque에 저장
                            -> GET /logs/entries -> JSON으로 반환
                            -> GET /logs/view    -> 웹 뷰어에서 표시

=====================================================================
"""
import logging
import threading
from collections import deque
from datetime import datetime
from typing import List, Optional

import config


# ╔═══════════════════════════════════════════════════════════════╗
# ║  로그 엔트리 구조                                               ║
# ║  각 로그 메시지를 딕셔너리로 저장합니다.                            ║
# ╚═══════════════════════════════════════════════════════════════╝

# 최대 보관할 로그 수 (메모리 절약)
MAX_LOG_ENTRIES = 500

# 스레드 안전한 deque (여러 스레드에서 동시에 로그가 발생할 수 있음)
_log_buffer: deque = deque(maxlen=MAX_LOG_ENTRIES)
_lock = threading.Lock()

# 로그 ID 카운터 (클라이언트가 새 로그만 가져갈 수 있도록)
_log_counter = 0


# ╔═══════════════════════════════════════════════════════════════╗
# ║  커스텀 로깅 핸들러                                              ║
# ║                                                               ║
# ║  [기술 해설: logging.Handler]                                   ║
# ║  Python의 logging.Handler를 상속하여 emit() 메서드를 오버라이드   ║
# ║  하면, 모든 로그 메시지가 이 핸들러를 통과합니다.                    ║
# ║  우리는 emit()에서 로그를 deque에 저장합니다.                      ║
# ╚═══════════════════════════════════════════════════════════════╝

class BufferHandler(logging.Handler):
    """
    로그 메시지를 메모리 버퍼(deque)에 저장하는 핸들러.

    [작동 방식]
    1. logging.info("메시지") 호출
    2. Python logging 프레임워크가 등록된 모든 핸들러의 emit() 호출
    3. 이 핸들러의 emit()이 호출됨
    4. 로그 레코드를 딕셔너리로 변환하여 deque에 추가
    """

    def emit(self, record: logging.LogRecord):
        """
        로그 레코드를 버퍼에 저장합니다.

        Args:
            record: Python logging이 전달하는 로그 레코드 객체
                    - record.levelname: "INFO", "WARNING", "ERROR" 등
                    - record.name: 로거 이름 (모듈명)
                    - record.getMessage(): 포맷된 메시지
        """
        global _log_counter

        try:
            with _lock:
                _log_counter += 1
                entry = {
                    "id": _log_counter,
                    "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    "level": record.levelname,       # INFO, WARNING, ERROR
                    "module": record.name,            # server, worker 등
                    "message": record.getMessage(),   # 실제 메시지
                }
                _log_buffer.append(entry)
        except Exception:
            pass  # 로그 핸들러 자체에서 에러가 나면 무시


# ╔═══════════════════════════════════════════════════════════════╗
# ║  로그 조회 API                                                  ║
# ║  server.py의 엔드포인트에서 이 함수들을 호출합니다.                  ║
# ╚═══════════════════════════════════════════════════════════════╝

def get_logs(after_id: int = 0, level: Optional[str] = None) -> List[dict]:
    """
    버퍼에서 로그 엔트리를 조회합니다.

    Args:
        after_id: 이 ID 이후의 로그만 반환 (폴링 시 중복 방지)
        level: 특정 레벨만 필터링 (예: "ERROR")

    Returns:
        로그 엔트리 딕셔너리 리스트

    [사용 예시]
      get_logs()                 -> 전체 로그
      get_logs(after_id=50)      -> 50번 이후 새 로그만
      get_logs(level="ERROR")    -> 에러만
    """
    with _lock:
        entries = list(_log_buffer)

    # ID 필터
    if after_id > 0:
        entries = [e for e in entries if e["id"] > after_id]

    # 레벨 필터
    if level:
        entries = [e for e in entries if e["level"] == level.upper()]

    return entries


def clear_logs():
    """버퍼의 로그를 모두 삭제합니다."""
    with _lock:
        _log_buffer.clear()


# ╔═══════════════════════════════════════════════════════════════╗
# ║  로깅 시스템 초기 설정                                           ║
# ║  앱 시작 시 한 번 호출하여 BufferHandler를 등록합니다.              ║
# ╚═══════════════════════════════════════════════════════════════╝

def setup_logging():
    """
    전체 로깅 시스템을 설정합니다.

    [설정되는 핸들러 3개]
    1. FileHandler    - 일별 로그 파일에 기록
    2. StreamHandler  - 콘솔(터미널)에 출력
    3. BufferHandler  - 메모리 버퍼에 저장 (웹 로그 뷰어용)

    [호출 시점]
    main.py 또는 tray_app.py의 최상단에서 호출합니다.
    logging.basicConfig() 대신 이 함수를 사용합니다.
    """
    import sys

    log_file = config.LOG_DIR / f"agent_{datetime.now():%Y%m%d}.log"

    # 루트 로거에 핸들러 등록
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 기존 핸들러 제거 (중복 방지)
    root.handlers.clear()

    # 포맷터 (모든 핸들러가 공유)
    formatter = logging.Formatter(config.LOG_FORMAT)

    # 1. 파일 핸들러
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # 2. 콘솔 핸들러
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    root.addHandler(sh)

    # 3. 버퍼 핸들러 (웹 로그 뷰어용)
    bh = BufferHandler()
    bh.setFormatter(formatter)
    root.addHandler(bh)
