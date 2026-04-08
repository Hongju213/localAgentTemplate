"""
=====================================================================
  models.py — 데이터 모델 정의 (Pydantic)
=====================================================================

[역할]
  API의 요청(Input)과 응답(Output) 데이터 구조를 정의합니다.
  Pydantic 모델을 사용하므로 자동 유효성 검사 + Swagger 문서 생성이 됩니다.

[데이터 흐름]
  웹앱 → TaskRequest → 로컬 에이전트 처리 → TaskResponse → 웹앱

[커스터마이즈 방법]
  새 프로젝트에서는 이 파일의 모델을 실제 비즈니스 로직에 맞게 수정하세요.
  예시) 크롤링 → CrawlRequest / CrawlResponse
  예시) 이미지 변환 → ImageConvertRequest / ImageConvertResponse

=====================================================================
"""
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ╔═══════════════════════════════════════════════════════════════╗
# ║  1. 헬스체크 응답                                              ║
# ║  GET / 요청 시 반환되는 서비스 상태 정보                          ║
# ╚═══════════════════════════════════════════════════════════════╝

class HealthResponse(BaseModel):
    """서비스 상태 응답"""
    service: str = Field(description="서비스 이름")
    status: str = Field(description="현재 상태 (running / error)")
    version: str = Field(description="서비스 버전")
    uptime_seconds: float = Field(description="서비스 실행 시간 (초)")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "service": "Local Agent Template",
                "status": "running",
                "version": "1.0.0",
                "uptime_seconds": 123.45
            }]
        }
    }


# ╔═══════════════════════════════════════════════════════════════╗
# ║  2. 작업 요청 (Input)                                         ║
# ║  웹앱 → POST /api/task → 로컬 에이전트                         ║
# ╚═══════════════════════════════════════════════════════════════╝

class TaskRequest(BaseModel):
    """
    작업 요청 모델.

    웹앱(또는 외부 클라이언트)이 로컬 에이전트에게 보내는 요청입니다.
    실제 프로젝트에서는 필드를 비즈니스 로직에 맞게 변경하세요.
    """
    task_type: str = Field(
        description="작업 유형. 예: 'process', 'analyze', 'convert'",
        examples=["process"]
    )
    input_data: Any = Field(
        description="작업에 필요한 입력 데이터 (자유 형식)",
        examples=[{"items": ["사과", "바나나", "딸기"]}]
    )
    options: Optional[dict] = Field(
        default=None,
        description="추가 옵션 (선택사항)",
        examples=[{"max_count": 10, "language": "ko"}]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "task_type": "process",
                "input_data": {"items": ["사과", "바나나", "딸기"]},
                "options": {"max_count": 10}
            }]
        }
    }


# ╔═══════════════════════════════════════════════════════════════╗
# ║  3. 작업 결과 항목                                              ║
# ║  개별 결과 데이터 구조                                           ║
# ╚═══════════════════════════════════════════════════════════════╝

class ResultItem(BaseModel):
    """
    개별 결과 항목.

    작업 결과의 각 항목을 표현합니다.
    실제 프로젝트에서는 필드를 비즈니스 로직에 맞게 변경하세요.
    """
    id: int = Field(description="결과 항목 순번")
    value: str = Field(description="결과 값")
    score: Optional[float] = Field(default=None, description="점수 (선택)")
    metadata: Optional[dict] = Field(default=None, description="추가 메타데이터 (선택)")


# ╔═══════════════════════════════════════════════════════════════╗
# ║  4. 작업 응답 (Output)                                         ║
# ║  로컬 에이전트 → 웹앱                                           ║
# ╚═══════════════════════════════════════════════════════════════╝

class TaskResponse(BaseModel):
    """
    작업 응답 모델.

    로컬 에이전트가 작업을 완료한 후 웹앱에 반환하는 응답입니다.
    """
    success: bool = Field(description="작업 성공 여부")
    task_type: str = Field(description="수행된 작업 유형")
    total_count: int = Field(description="결과 항목 수")
    results: List[ResultItem] = Field(description="결과 항목 리스트")
    elapsed_ms: float = Field(description="처리 소요 시간 (밀리초)")
    error: Optional[str] = Field(default=None, description="에러 메시지 (실패 시)")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="처리 완료 시각 (ISO 8601)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "success": True,
                "task_type": "process",
                "total_count": 3,
                "results": [
                    {"id": 1, "value": "사과 → 처리됨", "score": 0.95},
                    {"id": 2, "value": "바나나 → 처리됨", "score": 0.88},
                ],
                "elapsed_ms": 150.5,
                "error": None,
                "timestamp": "2026-04-08T12:00:00"
            }]
        }
    }
