# 동적 그리드 — 가로 내비게이션(Tab 행 넘김 / Home / End) & 스크롤

동적 그리드는 컬럼이 많아 가로 스크롤이 길게 생긴다. 이 문서는 그 상황에서의 **키보드 가로 이동과 스크롤 동기화**를 정리한다. [셀렉트 셀 최종 개선 가이드](dynamic-grid-select-cell-final-guide.md)의 키 디스패처(`defaultColDef.suppressKeyboardEvent`) 위에 Tab 행 넘김·Home·End를 얹은 내용이다.

> 이 문서는 실제 구현을 일반화한 **독립 샘플 가이드**다. 식별자·경로·필드명은 모두 예시(sample/custom)로 치환되어 있으며, 그대로 복사해 다른 화면에 적용할 수 있다.

> 대상 스택: ag-grid **v35.2.1** / React 18.2 / antd 5.21. 아래 동작·수치는 모두 하네스로 실측 확인했다.

대상 파일: `frontend/src/pages/SampleGrid/constants/gridColumnDefs.jsx`

컬럼 구성(좌→우): `__leg`(행 라벨, 고정) · `rslt1`(고정1, 고정) · `rslt2`(고정2, 고정) · `col_*`(동적, 가로 스크롤 영역).

---

## 1. 원하는 동작

| 입력 | 기대 |
| --- | --- |
| 행 **마지막 컬럼에서 Tab** | **다음 행의 최좌측 컬럼**으로 이동 + 가로 스크롤 **좌측 끝**으로 |
| **Home** | 그 행의 **최좌측 컬럼**으로 이동 + 스크롤 좌측 끝 |
| **End** | 그 행의 **마지막 컬럼**으로 이동 + 스크롤 우측 |
| 첫 컬럼에서 **Shift+Tab** | 이전 행의 마지막 컬럼 + 스크롤 우측 |

**"최좌측 컬럼" 정의는 소스에서 선택 가능**해야 한다.
- `firstDynamic` — 고정1/고정2(고정)를 제외한 **첫 동적 컬럼(`col_*`)** ← 기본
- `rslt1` — 고정1 컬럼

## 2. 근본 원인 (수정 전, 실측)

- **Tab 행 넘김**: 마지막 컬럼에서 Tab → `columns[0]`(= `__leg`, 고정 라벨 컬럼)으로 감. `__leg`는 좌측 고정이라 **가로 스크롤이 그대로**(우측에 머묾). → `col_601`(첫 동적)로 가고 스크롤도 좌측으로 와야 한다.
- **Home**: ag-grid 기본 Home → 첫 컬럼(`__leg`, 고정) → **스크롤 안 움직임**.
- **`setFocusedCell`은 가로 스크롤을 따라오지 않는다.** 실측: 우측 끝 컬럼으로 `setFocusedCell` 해도 `getHorizontalPixelRange().left`가 그대로 → 셀이 뷰포트 밖이면 렌더조차 안 됨. **스크롤 동기화는 `ensureColumnVisible`로 명시해야 한다.**
- **End**: ag-grid 기본으로도 마지막 컬럼 이동 + 스크롤은 됐지만, 포커스 행이 튀는 경우가 관측되어 명시 처리로 통일.

## 3. 구현

### 3.1 최좌측 컬럼 정의(설정)

```js
// 행의 최좌측(Home / Tab 행 넘김) 이동 대상. 클라이언트 요구에 따라 이 값만 바꾼다.
//  - 'firstDynamic' : 고정1/고정2(좌측 고정) 를 제외한 첫 동적 컬럼(col_*)  ← 기본
//  - 'rslt1'        : 고정1 컬럼
const LEFTMOST_COLUMN_MODE = 'firstDynamic';

function leftmostColumn(api) {
  const columns = api.getAllDisplayedColumns();
  if (LEFTMOST_COLUMN_MODE === 'rslt1') {
    return columns.find(col => col.getColId() === 'rslt1') ?? columns[0];
  }
  return (
    columns.find(col => col.getColId().startsWith('col_')) ??
    columns.find(col => col.getColId() === 'rslt1') ??
    columns[0]
  );
}
```

### 3.2 포커스 이동 + 스크롤 동기화

```js
// setFocusedCell 은 가로 스크롤을 따라오지 않으므로(실측), ensureColumnVisible 로 스크롤을 맞춘다.
function focusCell(api, rowIndex, colId) {
  api.clearFocusedCell();
  api.setFocusedCell(rowIndex, colId);
  api.ensureColumnVisible(colId); // position 'auto': 필요한 만큼만 스크롤(오른쪽 이동 시 최소, 최좌측 이동 시 0까지)
}
```

### 3.3 Tab / Home / End

```js
// Tab / Shift+Tab: 정확히 한 칸 이동. 행 경계에서만 랩.
function handleTab(params) {
  const { api, column, node, event } = params;
  const columns = api.getAllDisplayedColumns();
  const index = columns.findIndex(col => col.getColId() === column.getColId());
  if (index === -1) return false;

  event.preventDefault();
  api.stopEditing(false);

  let rowIndex = node.rowIndex;
  let targetColId;

  if (!event.shiftKey && index >= columns.length - 1) {
    rowIndex += 1;                                  // 마지막 + Tab → 다음 행
    targetColId = leftmostColumn(api).getColId();   //             최좌측(설정)
  } else if (event.shiftKey && index <= 0) {
    rowIndex -= 1;                                  // 첫 컬럼 + Shift+Tab → 이전 행
    targetColId = columns[columns.length - 1].getColId(); //          마지막 컬럼
  } else {
    targetColId = columns[event.shiftKey ? index - 1 : index + 1].getColId();
  }

  if (rowIndex < 0 || rowIndex >= api.getDisplayedRowCount()) return true; // 그리드 밖
  focusCell(api, rowIndex, targetColId);
  return true;
}

function handleHome(params) {
  const { api, node, event } = params;
  event.preventDefault();
  api.stopEditing(false);
  focusCell(api, node.rowIndex, leftmostColumn(api).getColId());
  return true;
}

function handleEnd(params) {
  const { api, node, event } = params;
  event.preventDefault();
  api.stopEditing(false);
  const columns = api.getAllDisplayedColumns();
  focusCell(api, node.rowIndex, columns[columns.length - 1].getColId());
  return true;
}
```

### 3.4 디스패처 — 열린 드롭다운과의 충돌 방지

Home/End는 **드롭다운이 열려 있을 때(=`<select>`가 DOM 포커스)** 는 셀을 옮기면 안 된다(네이티브 select가 첫/마지막 옵션으로 점프해야 함). 그래서 "select 포커스" 분기를 **가장 먼저** 두고, 그 경우 Tab 만 셀 이동으로 가로채고 나머지 키는 네이티브 select에 위임한다.

```js
function customSuppressKeyboard(params) {
  const event = params.event;
  if (!event || event.type !== 'keydown') return false;
  const renderer = params.colDef?.cellRenderer;

  // (1) 드롭다운 열림(<select> 포커스): 네이티브 select 가 키(↑/↓/Home/End/타입어헤드) 소유. Tab 만 셀 이동.
  if (renderer === 'customSelectRenderer') {
    const select = findCellSelect(event);
    if (select && document.activeElement === select) {
      return event.key === 'Tab' ? handleTab(params) : true;
    }
  }

  // (2) 셀 포커스 상태 내비게이션
  if (event.key === 'Tab') return handleTab(params);
  if (event.key === 'Home') return handleHome(params);
  if (event.key === 'End') return handleEnd(params);

  // (3) 셀 종류별 오픈/액션 키
  if (renderer === 'customSelectRenderer') return handleSelectOpen(params);
  if (renderer === 'customFileButtonRenderer') return handleFileKeys(params);
  return false;
}
```

## 4. 실측 검증 결과 (하네스, 동적 컬럼 10개 + 가로 스크롤)

컬럼: `__leg · rslt1 · rslt2 · col_601 … col_610`, 가로 스크롤 범위 left 0~780.

| 시나리오 | 결과 |
| --- | --- |
| `col_610@0` 에서 Tab | `col_601@1`(다음 행 첫 동적) + 스크롤 `left 780 → 0` |
| 우측 스크롤 상태에서 Home | `col_601`(같은 행 첫 동적) + 스크롤 `→ 0` |
| End | `col_610`(같은 행 마지막) + 스크롤 우측, **행 유지** |
| `__leg@1` 에서 Shift+Tab | `col_610@0`(이전 행 마지막) + 스크롤 우측 |
| `col_601@1` 에서 Shift+Tab | `rslt2@1`(정상 좌측 이동, 랩 아님) |
| 행 내 Tab 연속(col_601→607) | 셀이 우측 뷰포트를 벗어나는 순간부터 스크롤이 따라옴(최소 스크롤) |
| 드롭다운 열린 상태에서 Home | 셀 이동 없음(`col_602@0` 유지), `defaultPrevented=false` → 네이티브 select 가 처리 |

## 5. 함정 노트

- **`setFocusedCell`은 가로 스크롤을 동기화하지 않는다.** 반드시 `ensureColumnVisible(colId)`를 함께 호출한다. `position` 기본값 `'auto'`가 "오른쪽 이동 시 최소 스크롤 / 최좌측 이동 시 0까지"를 모두 자연스럽게 처리한다.
- **고정(pinned) 컬럼으로 포커스를 옮기면 가로 스크롤은 그대로다.** Tab 행 넘김/Home 목적지가 `__leg`(고정)면 스크롤이 안 움직인 것처럼 보인다 → 목적지를 첫 **동적** 컬럼으로 잡아야 스크롤이 좌측으로 온다.
- **Home/End는 드롭다운 열림 상태와 충돌한다.** `<select>`가 포커스일 땐 네이티브 select가 Home/End(첫/마지막 옵션)를 처리하도록, 디스패처에서 select-포커스 분기를 최우선에 두고 Tab 외 키를 위임한다.
- **최좌측 정의는 `LEFTMOST_COLUMN_MODE` 한 값으로 전환**한다(`'firstDynamic'` ↔ `'rslt1'`). Tab 행 넘김과 Home이 같은 정의를 공유한다.
