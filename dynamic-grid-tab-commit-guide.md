# 동적 그리드 — Tab/Home/End 이동 시 편집값 커밋(IME 유실) 수정

텍스트 셀을 편집하던 중 Tab(또는 Home/End)으로 이동하면 셀 선택은 옮겨지는데 **입력하던 값이 셀에 커밋되지 않고 유실**되던 문제를 다룬다. [가로 내비게이션 가이드](dynamic-grid-horizontal-nav-guide.md)의 `handleTab`/`handleHome`/`handleEnd` 가 편집 종료 시 값을 잃던 원인과 수정이다.

> 이 문서는 실제 구현을 일반화한 **독립 샘플 가이드**다. 식별자·경로·필드명은 모두 예시(sample/custom)로 치환되어 있으며, 그대로 복사해 다른 화면에 적용할 수 있다.

> 대상 스택: ag-grid **v35.2.1** / React 18.2 / antd 5.21. 아래 진단·수치는 모두 하네스로 실측 확인했다.

대상 파일: `frontend/src/pages/SampleGrid/constants/gridColumnDefs.jsx`

---

## 1. 증상

```
| 텍스트셀(입력중..) | ... |
```
텍스트 셀에 값을 입력하던 중 **Tab** → 다음 셀로 포커스는 정상 이동하지만, **입력 중이던 값이 셀에 들어가지 않는다**(빈 값). 특히 한글(IME 조합) 입력에서 재현된다.

## 2. 근본 원인

`handleTab`/`handleHome`/`handleEnd` 는 이동 전에 `api.stopEditing(false)`(커밋) 을 호출했다. `false` 는 "취소 안 함 = 커밋"이 맞다. 그런데도 값이 유실됐다.

**원인은 stopEditing 이 커밋하는 '값의 출처'다.** ag-grid 기본 텍스트 편집기(`agTextCellEditor`)는 값을 **편집기 내부 상태**로 들고 있고(`input` 이벤트로 갱신), `stopEditing` 은 그 **내부 값**을 커밋한다 — **라이브 `<input>` DOM 값을 읽는 게 아니다.**

실측으로 확정:

| 시나리오 | stopEditing(false) 후 커밋값 |
| --- | --- |
| `<input>` 값 세팅 **+ `input` 이벤트 발생** 후 Tab | 정상 커밋됨 |
| `<input>` 값 세팅 **후 `input` 이벤트 없이** Tab | **빈 값**(유실) |

→ 편집기 내부 상태가 라이브 DOM 값과 어긋난 순간 stopEditing 하면 값이 날아간다. 이게 실사용에서 터지는 대표 경로가 **IME(한글) 조합**이다.

- 한글 입력은 조합 중 `input` 이벤트가 `isComposing=true` 로 흐르고, 최종 확정은 `compositionend` 시점이다.
- 조합이 끝나기 전(또는 마지막 입력이 편집기 내부 상태에 반영되기 전)에 Tab 을 누르면, 편집기 내부 값은 아직 비어 있거나 이전 값이라 그대로 커밋 → 조합 중이던 글자가 통째로 유실된다.
- 영문/ASCII 를 천천히 치면 각 `input` 이 즉시 반영돼 잘 되는 것처럼 보여, 문제가 한글에서만 도드라진다.

## 3. 수정 — 라이브 DOM 값을 직접 읽어 커밋

편집기 내부 값에 의존하지 말고, **화면에 보이는 `<input>`/`<textarea>` 의 현재 값**을 직접 읽어 `node.setDataValue` 로 확정한 뒤 편집기를 닫는다.

```js
// 편집 중인 셀의 값을 '확실히' 커밋하고 편집을 종료한다.
// ag-grid 기본 텍스트 편집기는 값을 내부 상태(‘input’ 이벤트로 갱신)로만 들고 있고, stopEditing 은
// 그 내부 값을 커밋한다 — 라이브 <input> DOM 값을 읽는 게 아니다. 그래서 IME(한글) 조합 중이거나
// 마지막 입력이 내부 상태에 반영되기 전에 Tab/Home/End 로 stopEditing 하면 값이 유실된다.
function commitEditingCell(params) {
  const { api, column, node, event } = params;
  if (!api.getEditingCells().length) {
    return;
  }
  const field = event?.target?.closest?.('.ag-cell')?.querySelector?.('input, textarea');
  if (field) {
    api.stopEditing(true);                              // 편집기 닫기(내부 스테일 값 커밋 방지)
    node.setDataValue(column.getColId(), field.value); // 화면에 보이는 라이브 값으로 확정
  } else {
    api.stopEditing(false);                             // 텍스트 입력이 아니면 기본 커밋
  }
}
```

그리고 세 내비게이션 핸들러에서 `api.stopEditing(false)` 대신 이 함수를 호출한다.

```js
function handleTab(params) {
  const { api, column, node, event } = params;
  const columns = api.getAllDisplayedColumns();
  const index = columns.findIndex(col => col.getColId() === column.getColId());
  if (index === -1) return false;

  event.preventDefault();
  commitEditingCell(params); // ← api.stopEditing(false) 에서 교체
  // ... (행 경계 계산 + focusCell 이동)
}

function handleHome(params) {
  const { api, node, event } = params;
  event.preventDefault();
  commitEditingCell(params); // ← 교체
  focusCell(api, node.rowIndex, leftmostColumn(api).getColId());
  return true;
}

function handleEnd(params) {
  const { api, node, event } = params;
  event.preventDefault();
  commitEditingCell(params); // ← 교체
  const columns = api.getAllDisplayedColumns();
  focusCell(api, node.rowIndex, columns[columns.length - 1].getColId());
  return true;
}
```

### 왜 `stopEditing(true)` + `setDataValue` 인가

- `stopEditing(true)`(취소) 로 편집기를 먼저 닫아 **편집기 내부의 스테일 값이 커밋되는 경로를 차단**한다.
- 이어서 `node.setDataValue(colId, field.value)` 로 **라이브 DOM 값**을 직접 기록한다. 이 호출은 컬럼의 `valueSetter`(동적 '01' 컬럼) 또는 `field`(고정 컬럼) 양쪽 모두에 정상 반영되고, `onCellValueChanged`(= dirty 추적)도 발생한다.
- `field` 가 없으면(텍스트 편집기가 아닌 경우) 기존대로 `stopEditing(false)` 로 둔다. 방어적 폴백.

## 4. 실측 검증 결과 (하네스)

| 시나리오 | 결과 |
| --- | --- |
| `input` 이벤트 없이 값만('한글값') 세팅 후 Tab (IME 유사·재현) | **'한글값' 커밋됨**, 셀 표시 '한글값', 포커스 다음 셀 이동 |
| 정상 입력('WITHEVENT' + input 이벤트) 후 Tab | 커밋됨, `onCellValueChanged`(dirty) 발생, 포커스 이동 |
| 고정 컬럼(field 기반) 편집 후 Tab | 커밋됨(셀 표시/데이터 일치), 포커스 이동 |
| 앱 마운트/컴파일 | 에러 없음 |

## 5. 함정 노트

- **`stopEditing(false)` 는 편집기 '내부 값'을 커밋하지, 라이브 DOM 값을 커밋하지 않는다.** 내부 값이 최신이 아닐 수 있는 순간(IME 조합, 커스텀 편집기의 지연 반영 등)에 stopEditing 하면 값이 유실된다.
- **IME(한글) 입력은 조합 종료 전 값이 편집기 내부 상태에 없을 수 있다.** ASCII 로만 테스트하면 놓치기 쉬우니, 이런 그리드는 반드시 한글 입력 + Tab 으로 검증한다.
- **직접 커밋 시 `stopEditing(true)`(취소) 로 편집기를 닫고 `setDataValue` 로 기록**해 이중/스테일 커밋을 피한다. `setDataValue` 는 `valueSetter`/`field` 양쪽에 동작하고 dirty 이벤트도 발생시킨다.
