"""
=====================================================================
  worker.py — 실제 작업 로직 (★ 커스터마이즈 포인트)
=====================================================================

[역할]
  외부에서 받은 요청을 **실제로 처리**하는 핵심 로직입니다.
  이 파일만 수정하면 다양한 용도의 로컬 에이전트를 만들 수 있습니다.

[현재 구현]
  더미 데이터를 생성하는 예시입니다.
  실제 프로젝트에서는 이 파일의 내용을 교체하세요.

[커스터마이즈 예시]
  - 웹 크롤링: Playwright/Selenium으로 데이터 수집
  - 파일 변환: 이미지/문서 포맷 변환
  - 머신러닝: 로컬 모델로 추론 실행
  - 시스템 모니터링: PC 상태 수집
  - 데이터 가공: 엑셀/CSV 처리

[데이터 흐름]
  server.py가 요청을 받으면
  → worker.py의 process_task()를 호출
  → 결과를 TaskResponse로 포장하여 반환

=====================================================================
"""
import asyncio
import logging
import time
import random
from typing import Any, Optional, List

from models import TaskRequest, TaskResponse, ResultItem

logger = logging.getLogger(__name__)


# ╔═══════════════════════════════════════════════════════════════╗
# ║  초기화 / 정리 (선택사항)                                       ║
# ║  서버 시작/종료 시 호출됩니다.                                    ║
# ║  리소스(브라우저, DB 연결 등)를 관리할 때 사용합니다.                ║
# ╚═══════════════════════════════════════════════════════════════╝

async def initialize():
    """
    서버 시작 시 호출되는 초기화 함수.

    예시 용도:
      - 브라우저 인스턴스 생성
      - DB 연결 풀 생성
      - ML 모델 로딩
      - 외부 API 인증 토큰 획득
    """
    logger.info("워커 초기화 시작...")

    # ★ 여기에 초기화 로직을 추가하세요
    # 예: global browser
    #     browser = await playwright.chromium.launch(headless=True)

    await asyncio.sleep(0.5)  # 더미: 초기화에 시간이 걸리는 척
    logger.info("[OK] 워커 초기화 완료")


async def cleanup():
    """
    서버 종료 시 호출되는 정리 함수.

    예시 용도:
      - 브라우저 인스턴스 종료
      - DB 연결 해제
      - 임시 파일 정리
    """
    logger.info("워커 정리 중...")

    # ★ 여기에 정리 로직을 추가하세요
    # 예: await browser.close()

    logger.info("[OK] 워커 정리 완료")


# ╔═══════════════════════════════════════════════════════════════╗
# ║  메인 작업 함수 (★ 핵심)                                       ║
# ║  이 함수가 실제 작업을 수행합니다.                                 ║
# ╚═══════════════════════════════════════════════════════════════╝

async def process_task(request: TaskRequest) -> TaskResponse:
    """
    작업 요청을 처리하고 결과를 반환합니다.

    ★ 이 함수를 실제 비즈니스 로직으로 교체하세요.

    현재 구현: 입력 데이터의 각 항목에 더미 점수를 붙여 반환합니다.

    Args:
        request: 웹앱에서 받은 작업 요청

    Returns:
        처리 결과를 담은 TaskResponse
    """
    start_time = time.time()

    try:
        logger.info(f"작업 시작: type={request.task_type}")

        # ──────────────── Step 1: 입력 데이터 파싱 ────────────────
        # 요청에서 처리할 데이터를 추출합니다.
        input_data = request.input_data
        options = request.options or {}

        # 입력이 dict이고 "items" 키가 있으면 리스트로 사용
        if isinstance(input_data, dict) and "items" in input_data:
            items = input_data["items"]
        elif isinstance(input_data, list):
            items = input_data
        else:
            # 단일 값이면 리스트로 감싸기
            items = [input_data]

        max_count = options.get("max_count", len(items))
        items = items[:max_count]

        logger.info(f"  처리할 항목 수: {len(items)}")

        # ──────────────── Step 2: 실제 작업 수행 ─────────────────
        # ★ 이 부분을 실제 로직으로 교체하세요!
        results = await _dummy_process(items, request.task_type)

        # ──────────────── Step 3: 결과 포장 ──────────────────────
        elapsed_ms = (time.time() - start_time) * 1000

        response = TaskResponse(
            success=True,
            task_type=request.task_type,
            total_count=len(results),
            results=results,
            elapsed_ms=round(elapsed_ms, 2),
        )

        logger.info(f"[OK] 작업 완료: {len(results)}개 결과, {elapsed_ms:.1f}ms 소요")
        return response

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(f"[ERROR] 작업 실패: {e}", exc_info=True)

        return TaskResponse(
            success=False,
            task_type=request.task_type,
            total_count=0,
            results=[],
            elapsed_ms=round(elapsed_ms, 2),
            error=str(e),
        )


# ╔═══════════════════════════════════════════════════════════════╗
# ║  더미 처리 함수 (교체 대상)                                      ║
# ║  실제 프로젝트에서는 이 함수를 삭제하고                             ║
# ║  process_task()의 Step 2를 직접 구현하세요.                      ║
# ╚═══════════════════════════════════════════════════════════════╝

async def _dummy_process(items: list, task_type: str) -> List[ResultItem]:
    """
    더미 처리 로직.
    각 항목에 랜덤 점수를 부여하고 가공된 문자열을 반환합니다.

    ★ 이 함수를 실제 로직으로 교체하세요!
    """
    results = []

    for i, item in enumerate(items, start=1):
        # 실제 작업처럼 약간의 딜레이
        await asyncio.sleep(0.1)

        # 더미 결과 생성
        result = ResultItem(
            id=i,
            value=f"{item} → [{task_type}] 처리 완료",
            score=round(random.uniform(0.5, 1.0), 3),
            metadata={
                "original": str(item),
                "task_type": task_type,
                "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        results.append(result)

        logger.info(f"  [{i}/{len(items)}] '{item}' 처리 완료 (score: {result.score})")

    return results
