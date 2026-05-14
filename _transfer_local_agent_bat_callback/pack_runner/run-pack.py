# coding=utf-8
"""
run-pack.py

Windows batch file이 호출하는 Python 업무 엔트리포인트입니다.

입력:
  - INPUT_JSON: agent가 최초 요청 정보를 담아 넘기는 JSON 문자열
  - AGENT_COMPLETE_URL: 업무 완료 후 호출할 agent 완료 API
  - PACK_JSON(optional): 사용할 pack JSON 경로

출력:
  - stdout: 실행 단계 로그
  - HTTP callback: Router.execute()가 agent 완료 API로 최종 결과를 POST합니다.
"""
from router.route import Router


MODE = 0  # Generic Mode
# MODE = 1  # Deb. Mode
# MODE = 2  # Dev. Mode
# MODE = 3  # Test Mode


router = Router(mode=MODE)
router.write_header()
router.load_pack()
router.enroll()
# router.validate()
# router.get_user_input()
router.execute()
