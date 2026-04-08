# Local Agent Template

로컬 PC에서 실행되는 **에이전트 서비스 템플릿**입니다.

시스템 트레이 아이콘으로 백그라운드 실행되며, 웹앱(또는 외부 시스템)의 HTTP 요청을 받아 작업을 수행하고 결과를 반환합니다.

---

## 📋 목차

- [아키텍처](#아키텍처)
- [요구사항 (Prerequisites)](#요구사항-prerequisites)
- [설치 및 실행](#설치-및-실행)
- [파일 구조](#파일-구조)
- [API 엔드포인트](#api-엔드포인트)
- [테스트](#테스트)
- [커스터마이즈 가이드](#커스터마이즈-가이드)
- [빌드 및 배포 (EXE)](#빌드-및-배포-exe)
- [트러블슈팅](#트러블슈팅)

---

## 아키텍처

```
┌─────────────────────────┐         ┌───────────────────────────────────┐
│    웹앱 (원격 서버)       │         │   사용자 PC (localhost:8000)       │
│                         │  HTTP   │                                   │
│  POST /api/task ───────────────→  │  server.py (FastAPI + Uvicorn)    │
│                         │         │    ↓                              │
│  ← TaskResponse ←──────────────── │  worker.py (작업 로직)             │
│                         │         │                                   │
│  GET / (헬스체크) ─────────────→   │  tray_app.py (시스템 트레이)       │
│                         │         │  log_manager.py (실시간 로그)       │
└─────────────────────────┘         └───────────────────────────────────┘
```

### 실행 모드

| 모드 | 진입점 | 용도 |
|------|--------|------|
| **터미널 모드** | `python main.py` | 개발/디버깅 (콘솔에서 직접 실행) |
| **트레이 모드** | `python tray_app.py` | 배포/운영 (시스템 트레이 아이콘으로 백그라운드 실행) |

---

## 요구사항 (Prerequisites)

### 1. 운영체제

| OS | 지원 | 비고 |
|----|:----:|------|
| **Windows 10/11** | ✅ | 기본 타깃. 시스템 트레이, EXE 빌드 모두 지원 |
| macOS | ⚠️ | 터미널 모드 동작. 트레이 아이콘 일부 제한 |
| Linux | ⚠️ | 터미널 모드 동작. 트레이 아이콘은 DE에 따라 다름 |

### 2. Python

| 항목 | 요구사항 |
|------|----------|
| **버전** | **Python 3.9 이상** (권장: **3.11.x**) |
| **다운로드** | https://www.python.org/downloads/ |
| **확인 명령** | `python --version` |

> ⚠️ **설치 시 반드시 "Add Python to PATH" 체크**  
> Windows 설치 마법사 첫 화면에서 하단의 체크박스를 반드시 켜세요.

```bash
# 설치 확인
python --version
# Python 3.11.2  ← 이런 출력이 나와야 합니다

pip --version
# pip 22.3.1 ...  ← pip도 함께 설치됩니다
```

### 3. Python 패키지 의존성

`requirements.txt`에 정의된 패키지들입니다. **가상환경 생성 후 자동 설치됩니다.**

| 패키지 | 최소 버전 | 역할 | 비고 |
|--------|:---------:|------|------|
| **fastapi** | `≥ 0.109.0` | 비동기 웹 프레임워크 (API 서버) | Swagger UI 자동 생성 |
| **uvicorn[standard]** | `≥ 0.25.0` | ASGI 서버 (FastAPI 실행 엔진) | `[standard]`는 watchfiles, httptools 등 포함 |
| **pydantic** | `≥ 2.5.0` | 데이터 유효성 검사 및 모델 정의 | FastAPI와 함께 사용 |
| **httpx** | `≥ 0.27.0` | 비동기 HTTP 클라이언트 | 원격 서버에 결과 전송 시 사용 |
| **pystray** | `≥ 0.19.5` | 시스템 트레이 아이콘 | Windows/macOS 지원 |
| **Pillow** | `≥ 10.2.0` | 이미지 처리 (트레이 아이콘 동적 생성) | pystray의 아이콘 이미지용 |

#### `uvicorn[standard]`가 추가로 설치하는 하위 의존 패키지

| 패키지 | 역할 |
|--------|------|
| httptools | HTTP 파싱 고속화 |
| watchfiles | 파일 변경 감지 (auto-reload) |
| websockets | WebSocket 지원 |
| python-dotenv | `.env` 파일 로드 |
| PyYAML | YAML 설정 지원 |

#### 기타 자동 설치되는 간접 의존 패키지

| 패키지 | 역할 |
|--------|------|
| anyio | 비동기 I/O 호환 레이어 |
| starlette | FastAPI의 기반 프레임워크 |
| click | Uvicorn CLI |
| colorama | Windows 콘솔 색상 (Windows 전용) |
| h11 | HTTP/1.1 프로토콜 구현 |
| httpcore | httpx의 전송 레이어 |
| certifi | SSL 인증서 번들 |
| idna | 국제화 도메인 이름 |
| typing_extensions | 타입 힌트 확장 |
| annotated-types | Pydantic 어노테이션 |
| pydantic_core | Pydantic v2 고속 코어 (Rust) |
| six | Python 2/3 호환 유틸 |

### 4. 빌드 관련 (EXE 배포 시에만 필요)

| 도구 | 버전 | 용도 | 설치 |
|------|------|------|------|
| **PyInstaller** | `≥ 6.0` | Python → EXE 변환 | `pip install pyinstaller` |
| **Inno Setup** | 6.x | 윈도우 인스톨러 생성 (선택) | https://jrsoftware.org/isinfo.php |

> 💡 PyInstaller는 `build/build.bat` 실행 시 자동으로 설치됩니다.

### 5. 네트워크 요구사항

| 항목 | 기본값 | 변경 위치 |
|------|--------|-----------|
| **사용 포트** | `8000` (TCP) | `config.py` → `LOCAL_PORT` |
| **바인딩 주소** | `127.0.0.1` (로컬만) | `config.py` → `LOCAL_HOST` |

> 방화벽에서 포트 `8000`이 차단되어 있어도, `127.0.0.1` (localhost)로만 바인딩하므로 외부 접근은 차단됩니다.

---

## 설치 및 실행

### Step 1: 프로젝트 다운로드

```bash
git clone <repository-url>
cd local-agent-template
```

### Step 2: 가상환경 생성 및 활성화

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (CMD)
venv\Scripts\activate.bat

# macOS / Linux
source venv/bin/activate
```

> ✅ 활성화 성공 시 프롬프트 앞에 `(venv)`가 표시됩니다.
>
> ⚠️ **PowerShell 실행 정책 오류 시:**
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### Step 3: 의존성 설치

```bash
pip install -r requirements.txt
```

설치 확인:
```bash
pip list
```

아래와 유사한 패키지들이 표시되면 정상입니다:
```
fastapi          0.135.3
uvicorn          0.44.0
pydantic         2.12.5
httpx            0.28.1
pystray          0.19.5
Pillow           12.2.0
```

### Step 4: 실행

#### 4-A. 터미널 모드 (개발용)

```bash
python main.py
```

출력 예시:
```
==================================================
  Local Agent Template v1.0.0
  [Terminal Mode]
==================================================

  Server:     http://127.0.0.1:8000
  API Docs:   http://127.0.0.1:8000/docs
  Log Viewer: http://127.0.0.1:8000/logs/view
  Log Dir:    C:\Users\<username>\AppData\Local\LocalAgent\logs

  Press Ctrl+C to stop.
==================================================
```

#### 4-B. 트레이 모드 (배포용)

```bash
python tray_app.py
```

- 시스템 트레이에 파란색 원형 아이콘이 나타남
- 자동으로 브라우저에서 Log Viewer가 열림
- **우클릭 메뉴**: Log Viewer, Test Request, API Docs, Log Folder, Status Check, Quit

### Step 5: 동작 확인

서버 시작 후 아래 URL에 접속:

| URL | 설명 |
|-----|------|
| http://127.0.0.1:8000/ | 헬스체크 (JSON 응답) |
| http://127.0.0.1:8000/docs | Swagger API 문서 (인터랙티브) |
| http://127.0.0.1:8000/redoc | ReDoc API 문서 |
| http://127.0.0.1:8000/logs/view | 실시간 로그 뷰어 (Web UI) |
| http://127.0.0.1:8000/api/test | 테스트 요청 실행 |

---

## 파일 구조

```
local-agent-template/
├── main.py              # 터미널 모드 진입점 (개발용)
├── tray_app.py          # 트레이 모드 진입점 (배포용)
├── server.py            # FastAPI 서버 (API 라우터 + 로그 뷰어 HTML)
├── worker.py            # ★ 실제 작업 로직 (커스터마이즈 포인트)
├── models.py            # Pydantic 요청/응답 모델
├── config.py            # 중앙 설정 관리 (포트, URL, 로그 등)
├── log_manager.py       # 실시간 로그 관리 (메모리 버퍼 + 핸들러)
├── requirements.txt     # Python 패키지 의존성
├── build/
│   ├── build.bat        # PyInstaller EXE 빌드 스크립트
│   └── installer.iss    # Inno Setup 인스톨러 스크립트
└── venv/                # Python 가상환경 (git 제외)
```

| 파일 | 역할 | 수정 필요 |
|------|------|:---------:|
| `config.py` | 앱 이름, 포트, 원격 서버 URL, CORS, 로그 경로 설정 | ✅ |
| `models.py` | 요청(`TaskRequest`)/응답(`TaskResponse`) 데이터 구조 정의 | ✅ |
| `worker.py` | **★ 핵심!** `process_task()` 함수에 실제 비즈니스 로직 구현 | ✅ |
| `server.py` | API 라우터, 미들웨어(CORS, PNA, 로깅), 로그 뷰어 HTML | △ (보통 그대로) |
| `tray_app.py` | 시스템 트레이 GUI, 서버 스레드 관리 | △ (보통 그대로) |
| `log_manager.py` | 로그 버퍼(deque) 관리, 커스텀 핸들러(`BufferHandler`) | ✗ |
| `main.py` | 터미널 모드 Uvicorn 실행 | ✗ |

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/` | 헬스체크 — 서비스 상태, 버전, uptime 반환 |
| `POST` | `/api/task` | **작업 요청 처리** — `TaskRequest` 수신 → `TaskResponse` 반환 |
| `GET` | `/api/task/sample` | 샘플 요청/응답 형태 확인 |
| `GET` | `/api/test` | 더미 데이터로 테스트 요청 실행 |
| `GET` | `/logs/view` | 실시간 로그 뷰어 (HTML Web UI) |
| `GET` | `/logs/entries` | 로그 데이터 JSON API (`after_id`, `level` 파라미터) |
| `DELETE` | `/logs` | 로그 버퍼 초기화 |
| `GET` | `/docs` | Swagger API 문서 (FastAPI 자동 생성) |
| `GET` | `/redoc` | ReDoc API 문서 (FastAPI 자동 생성) |

---

## 테스트

### 헬스체크

```bash
curl http://127.0.0.1:8000/
```

응답 예시:
```json
{
  "service": "Local Agent Template",
  "status": "running",
  "version": "1.0.0",
  "uptime_seconds": 123.45
}
```

### 작업 요청

```bash
curl -X POST http://127.0.0.1:8000/api/task ^
  -H "Content-Type: application/json" ^
  -d "{\"task_type\":\"process\",\"input_data\":{\"items\":[\"사과\",\"바나나\",\"딸기\"]},\"options\":{\"max_count\":10}}"
```

### 브라우저에서 테스트

1. http://127.0.0.1:8000/logs/view 접속 (실시간 로그 뷰어)
2. 상단의 **Test Request** 버튼 클릭
3. 로그 뷰어에서 요청 → 처리 → 응답 전 과정이 실시간 표시
4. 또는 http://127.0.0.1:8000/docs 에서 Swagger UI로 직접 API 호출

---

## 커스터마이즈 가이드

새 프로젝트에 적용할 때 수정이 필요한 파일과 순서:

### 1단계: `config.py` — 기본 설정 변경

```python
APP_NAME = "My Custom Agent"        # 앱 이름
APP_VERSION = "1.0.0"               # 버전
LOCAL_PORT = 8000                   # 서버 포트
REMOTE_SERVER_URL = "https://..."   # 결과 전송 URL (없으면 None)
```

### 2단계: `models.py` — 데이터 모델 수정

비즈니스 로직에 맞게 `TaskRequest`, `TaskResponse`, `ResultItem`을 수정합니다.

### 3단계: `worker.py` — 핵심 로직 구현

`process_task()` 함수를 실제 비즈니스 로직으로 교체합니다.

```python
async def process_task(request: TaskRequest) -> TaskResponse:
    # ★ 여기에 실제 로직을 구현
    # 예: 웹 크롤링, 파일 변환, ML 추론 등
    ...
```

### 4단계: `requirements.txt` — 추가 의존성

필요한 패키지를 추가합니다:
```
# 예시
playwright>=1.40.0
pandas>=2.0.0
```

---

## 빌드 및 배포 (EXE)

### EXE 빌드

```bash
cd build
build.bat
```

빌드 과정:
1. Python 존재 확인
2. 가상환경 생성 및 활성화
3. 의존성 + PyInstaller 설치
4. PyInstaller로 `tray_app.py` → `dist/LocalAgent.exe` 변환
5. 결과 확인

> 📁 출력 경로: `build/dist/LocalAgent.exe`

### 인스톨러 생성 (선택)

1. [Inno Setup](https://jrsoftware.org/isinfo.php) 설치 (v6.x)
2. `build/installer.iss`를 Inno Setup에서 열기
3. 컴파일 → `build/output/Local Agent-Setup.exe` 생성

인스톨러 기능:
- 바탕화면 바로가기 생성 (선택)
- Windows 시작 시 자동 실행 등록 (선택)
- 한국어/영어 지원

---

## 로그 시스템

### 로그 저장 위치

| OS | 경로 |
|----|------|
| Windows | `%LOCALAPPDATA%\LocalAgent\logs\` |
| macOS/Linux | `~/.local-agent/logs/` |

### 로그 파일 형식

일별 로그 파일이 자동 생성됩니다:
```
agent_20260408.log
```

### 로그 핸들러 구조

```
logger.info("메시지")
  → FileHandler     → 파일에 기록 (영구 보존)
  → StreamHandler   → 콘솔에 출력 (개발용)
  → BufferHandler   → 메모리 deque에 저장 (최대 500개)
                          → GET /logs/entries → JSON으로 반환
                          → GET /logs/view    → 웹 뷰어에서 표시
```

---

## 트러블슈팅

### ❌ `python`을 찾을 수 없습니다

**원인:** Python이 PATH에 등록되지 않음  
**해결:**
1. [Python 공식 사이트](https://www.python.org/downloads/)에서 재설치
2. 설치 시 **"Add Python to PATH"** 체크
3. 설치 후 새 터미널 열어서 `python --version` 확인

### ❌ PowerShell에서 `.\venv\Scripts\Activate.ps1` 실행 오류

**원인:** PowerShell 실행 정책이 `Restricted`로 설정됨  
**해결:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### ❌ `pip install` 시 빌드 오류

**원인:** C++ 빌드 도구 없음 (일부 패키지는 네이티브 컴파일 필요)  
**해결:**
1. [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) 설치
2. "C++를 사용한 데스크톱 개발" 워크로드 선택

> 💡 현재 `requirements.txt`의 패키지들은 대부분 사전 컴파일된 wheel로 제공되므로, 일반적으로 빌드 도구는 불필요합니다.

### ❌ 포트 8000 이미 사용 중

**원인:** 다른 프로그램이 포트 8000을 사용 중  
**해결:**
```bash
# 사용 중인 프로세스 확인 (Windows)
netstat -ano | findstr :8000

# config.py에서 포트 변경
LOCAL_PORT = 8001
```

### ❌ 트레이 아이콘이 안 보임

**원인:** Windows 트레이 영역에서 숨김 처리됨  
**해결:** 작업 표시줄 → 숨겨진 아이콘 표시 (∧ 화살표) → Python 아이콘 확인

### ❌ `ModuleNotFoundError: No module named 'pystray'`

**원인:** 가상환경이 활성화되지 않았거나 의존성 미설치  
**해결:**
```bash
# 가상환경 활성화 확인
.\venv\Scripts\Activate.ps1

# 의존성 재설치
pip install -r requirements.txt
```

---

## 기술 스택 요약

| 분류 | 기술 | 버전 |
|------|------|------|
| **언어** | Python | 3.9+ (권장 3.11) |
| **웹 프레임워크** | FastAPI | ≥ 0.109.0 |
| **ASGI 서버** | Uvicorn | ≥ 0.25.0 |
| **데이터 모델** | Pydantic | ≥ 2.5.0 |
| **HTTP 클라이언트** | httpx | ≥ 0.27.0 |
| **시스템 트레이** | pystray | ≥ 0.19.5 |
| **이미지 처리** | Pillow | ≥ 10.2.0 |
| **EXE 빌드** | PyInstaller | ≥ 6.0 (빌드 시에만) |
| **인스톨러** | Inno Setup | 6.x (선택) |

---

## 라이선스

MIT License
