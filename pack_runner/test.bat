@echo off
chcp 65001 >nul 2>&1

REM test.bat
REM - agent가 백그라운드에서 실행하는 Windows 배치 파일입니다.
REM - 입력은 INPUT_JSON 환경변수로 들어오며, 완료 통지는 run-pack.py가 처리합니다.
REM - 이 파일은 Python 업무 엔트리포인트를 호출하고 종료 코드만 agent 로그에 남깁니다.

echo ========================
echo     [테스트] 에이전트 테스트
echo ========================
echo.
echo 받아온 json 데이터는?
echo %INPUT_JSON%
echo.
echo run-pack.py를 호출합니다.
python "C:\Projects\run-pack.py"
set EXIT_CODE=%ERRORLEVEL%
echo.
echo run-pack.py 종료 코드: %EXIT_CODE%
echo ========================
exit /b %EXIT_CODE%
