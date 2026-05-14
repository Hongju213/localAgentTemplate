# coding=utf-8
"""
router.route

실제 업무 실행기를 흉내 내는 테스트용 Router 구현입니다.
운영 코드에서는 이 클래스가 pack 검증, 사용자 입력 수집, task 실행,
결과 정리 같은 실제 업무 단계를 담당하게 됩니다.
"""
import json
import os
import time
from pathlib import Path


class Router:
    """
    pack 기반 업무 실행 흐름을 한 곳에 모은 조정자입니다.

    입력:
      - mode: Generic/Deb/Dev/Test 같은 실행 모드
      - INPUT_JSON 환경변수: sample -> agent -> bat을 거쳐 넘어온 원 요청 정보
      - AGENT_COMPLETE_URL 환경변수: 완료 후 agent로 되돌려 보낼 URL
      - PACK_JSON 환경변수: pack JSON 파일 경로, 없으면 C:\Projects\Agent\test-pack.json 사용

    출력:
      - execute()가 끝나면 agent 완료 API로 결과 JSON을 POST합니다.
    """
    def __init__(self, mode=0):
        self.mode = mode
        self.input_json = os.environ.get("INPUT_JSON", "{}")
        self.agent_complete_url = os.environ.get("AGENT_COMPLETE_URL")
        self.pack_path = Path(os.environ.get("PACK_JSON", r"C:\Projects\Agent\test-pack.json"))
        self.payload = {}
        self.pack = {}
        self.tasks = []

    def write_header(self):
        """실행 시작을 알아보기 쉽도록 콘솔 로그 헤더를 출력합니다."""
        print("========================")
        print("    [테스트] Python pack runner")
        print("========================")
        print(f"MODE={self.mode}")

    def load_pack(self):
        """
        pack JSON과 최초 요청 payload를 읽습니다.

        pack JSON:
          - Pack: pack 이름/버전/설명 같은 메타데이터
          - Tasks: 실행할 task 정의 목록

        INPUT_JSON:
          - agent가 만든 job_id, method, query/body, sample callback URL 등을 담고 있습니다.
        """
        print(f"Load pack: {self.pack_path}")
        if self.pack_path.exists():
            self.pack = json.loads(self.pack_path.read_text(encoding="utf-8"))
        else:
            self.pack = {
                "Pack": {
                    "name": "test-pack",
                    "version": "0.1.0",
                    "description": "Generated fallback pack",
                },
                "Tasks": {},
            }

        self.payload = json.loads(self.input_json)
        print("Input JSON:")
        print(json.dumps(self.payload, ensure_ascii=False, indent=2))

    def enroll(self):
        """
        pack의 Tasks 블록을 실행 목록으로 등록합니다.

        현재는 테스트 껍데기라 task 이름만 모읍니다.
        실제 구현에서는 task별 클래스 생성, 의존성 정리, 실행 순서 계산 등이 들어갑니다.
        """
        task_map = self.pack.get("Tasks", {})
        self.tasks = list(task_map.keys())
        print(f"Enrolled tasks: {', '.join(self.tasks) if self.tasks else '(none)'}")

    def execute(self):
        """
        등록된 task를 실행합니다.

        현재 테스트 버전:
          - 실제 업무 대신 10초 대기
          - 완료 후 _notify_agent()로 agent에 결과 통지
        """
        print("Execute tasks: waiting 10 seconds...")
        time.sleep(10)
        print("Tasks finished.")
        self._notify_agent()

    def _notify_agent(self):
        """
        업무 완료 결과를 agent로 되돌려 보냅니다.

        입력:
          - self.payload: 최초 요청 정보
          - self.pack/self.tasks: Python runner가 처리한 pack 정보

        출력:
          - POST {AGENT_COMPLETE_URL}
          - agent는 이 payload를 sample backend callback API로 다시 전달합니다.
        """
        if not self.agent_complete_url:
            print("AGENT_COMPLETE_URL is empty. Skip callback.")
            return

        completion = {
            **self.payload,
            "python_runner": "run-pack.py",
            "pack": self.pack.get("Pack", {}),
            "tasks": self.tasks,
            "result": {
                "success": True,
                "message": "Python pack completed.",
            },
        }

        try:
            import urllib.request

            data = json.dumps(completion, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(
                self.agent_complete_url,
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                print(f"Agent callback status: {response.status}")
                print(f"Agent callback body: {response_body}")
        except Exception as exc:
            print(f"Agent callback failed: {exc}")
