# 동적 그리드 — 셀렉트 셀 키보드 값 선택(Space 확정): pick 모드 + 값 사이클

동적 그리드의 공통코드 셀렉트('02') 셀에서 **키보드로 옵션을 고르고 Space(또는 Enter)로 확정**하는 방식을 정리한다. [셀렉트 셀 최종 개선 가이드](dynamic-grid-select-cell-final-guide.md)의 키보드 부분(네이티브 OS 드롭다운 열기 + Enter 확정)을 **대체**한다.

> 대상 스택: ag-grid **v35.2.1** / React 18.2 / antd 5.21. 아래 동작·수치는 모두 하네스로 실측 확인했다.

대상 파일: `frontend/src/pages/SampleGrid/constants/gridColumnDefs.jsx`

---

## 1. 배경 — 왜 네이티브 OS 드롭다운으로는 Space 확정이 안 되나

기존 키보드 방식은 Enter로 네이티브 `<select>`의 OS 드롭다운을 열고(`showPicker`), ↑/↓ 로 목록을 이동, Enter로 확정하는 것이었다. 여기서 **Space 확정**을 붙이려다 두 가지 벽에 부딪힌다.

1. **열린 OS 드롭다운의 하이라이트는 JS로 노출되지 않는다.** ↑/↓ 로 항목을 하이라이트해도 `select.value` 는 **확정(Enter/클릭) 전까지 갱신되지 않는다**(빈 문자열). 그래서 Space 시점에 `select.value` 를 읽어 커밋해도 `""` 만 들어간다(= 아무 것도 선택 안 됨).
2. **Space는 네이티브 select의 '토글' 키다.** keydown에 열리고 keyup에 닫혀, `showPicker`로 연 드롭다운이 Space keyup에서 곧바로 닫혀 깜빡인다.
3. 게다가 **재발사(합성 Enter dispatch)로 우회**하면, 그 합성 keydown이 grid 루트로 버블링되어 `suppressKeyboardEvent` 를 재진입시켜 **무한 재귀(Maximum call stack size exceeded)** 가 나고, 합성 이벤트(`isTrusted:false`)는 애초에 네이티브 확정을 유발하지 못한다.

**결론:** 네이티브 OS 드롭다운의 키보드 동작은 불투명하고 우회가 불가능하다. 그래서 **드롭다운을 열지 않고, 방향키로 값을 우리가 직접 사이클**해서 Space/Enter로 확정하는 방식(pick 모드)으로 전환한다. 값을 우리가 소유하므로 `select.value` 불투명성에 의존하지 않는다.

---

## 2. 설계 개요 (pick 모드 + 값 사이클)

- **pick 모드:** 셀렉트 셀에서 Enter/Space 를 누르면 "값 선택 모드"에 진입한다. 이때 **`<select>` 에 포커스를 주지 않고 셀 포커스를 유지한다.**
  - **왜 select 를 포커스하지 않나(핵심):** `<select>` 가 DOM 포커스를 가지면 ag-grid 는 방향키에 대해 `suppressKeyboardEvent` 를 **호출하지 않는다**(폼 컨트롤에 위임). 그러면 우리가 ↑/↓ 를 가로챌 수 없다(실측). **셀 포커스를 유지하면 모든 키가 `suppressKeyboardEvent` 로 들어와** 우리가 완전히 제어할 수 있다.
- **pick 모드 중:** ↑/↓ 는 `codes` 순서(`['', ...cdId]`)로 값을 **직접 사이클**하고 `setDataValue` 로 즉시 커밋한다(셀에 값이 바로 보임). Enter/Space/Escape 는 확정·종료, Tab/Home/End/←/→ 는 pick 해제 후 일반 이동.
- **pick 모드 밖:** ↑/↓ 는 평소대로 **행 이동**(ag-grid 기본). → 행 내비게이션이 보존된다.
- **해제:** 포커스가 다른 셀로 바뀌면(`onCellFocused`) 자동 해제한다.
- **마우스:** 렌더러의 네이티브 `<select>` 는 그대로라, **클릭 시 네이티브 OS 드롭다운이 열려** 선택할 수 있다(마우스 경로 무변경).

**트레이드오프:** 키보드 경로에는 팝업 목록이 뜨지 않는다(값이 셀에서 바로 바뀌며 보임). Escape 는 사이클로 이미 커밋된 값을 되돌리지 않고 pick 만 종료한다.

---

## 3. 구현 — `constants/gridColumnDefs.jsx`

### 3.1 pick 모드 상태

```js
// 셀렉트('02') 셀에서 Enter/Space 로 '값 선택 모드(pick)' 진입. 그 셀에서 ↑/↓ 는 셀 이동이 아니라
// 옵션 값을 사이클한다. 이때 <select> 에 포커스를 주지 '않고' 셀 포커스를 유지한다.
//   → <select> 가 포커스면 ag-grid 가 방향키에 suppressKeyboardEvent 를 호출하지 않아(폼 컨트롤 위임)
//     ↑/↓ 를 가로챌 수 없다(실측). 셀 포커스를 유지하면 모든 키를 우리가 제어할 수 있다.
// 포커스가 다른 셀로 바뀌면(onCellFocused) 해제한다.
let pickModeCellId = null;
const cellIdOf = (node, column) => `${node?.id}:${column?.getColId?.()}`;
export const resetSelectPickMode = () => {
  pickModeCellId = null;
};
```

### 3.2 값 사이클

```js
// pick 모드에서 ↑/↓ 로 값을 '직접' 바꾼다.
//  - 현재 값은 데이터 모델(api.getCellValue)에서 읽는다. ← 네이티브 OS 드롭다운의 select.value 는
//    확정 전까지 갱신되지 않아(빈 값) 신뢰할 수 없으므로, 우리가 소유한 데이터 모델 값을 기준으로 한다.
//  - codes 순서(['' , ...cdId])로 이전/다음을 계산해 setDataValue 로 즉시 커밋(셀에 값 표시).
//  - 셀 포커스는 그대로 유지되므로(우리는 <select> 를 포커스하지 않음) 연속 사이클이 가능하다.
function cycleSelectValue(params, direction) {
  const codes = params.colDef?.cellRendererParams?.codes ?? [];
  const values = ['', ...codes.map(code => code.cdId)];
  // ag-grid v35 는 api.getValue 가 없다(제거됨) → api.getCellValue 를 쓴다.
  const current = params.api.getCellValue({ rowNode: params.node, colKey: params.column }) ?? '';
  let index = values.indexOf(current);
  if (index < 0) {
    index = 0;
  }
  index = Math.max(0, Math.min(values.length - 1, index + direction)); // 양 끝은 클램프(랩 없음)
  params.event.preventDefault();
  params.node.setDataValue(params.column.getColId(), values[index]);
}
```

### 3.3 디스패처 (`defaultColDef.suppressKeyboardEvent`)

```js
function customSuppressKeyboard(params) {
  const event = params.event;
  if (!event || event.type !== 'keydown') return false;
  const renderer = params.colDef?.cellRenderer;

  // (1) pick 모드: 이 셀에서 Enter/Space 로 진입한 상태. 셀 포커스 유지.
  if (renderer === 'customSelectRenderer' && pickModeCellId === cellIdOf(params.node, params.column)) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      cycleSelectValue(params, event.key === 'ArrowDown' ? 1 : -1);
      return true;
    }
    if (event.key === 'Enter' || event.key === ' ' || event.code === 'Space' || event.key === 'Escape') {
      event.preventDefault();
      pickModeCellId = null;      // 확정/종료 (값은 사이클에서 이미 커밋됨) → Space 로도 '선택' 완료
      return true;
    }
    pickModeCellId = null;        // Tab/Home/End/←/→ : pick 해제 후 아래 일반 처리로 흐름
  }

  // (2) 셀 포커스 상태의 내비게이션 키(전 컬럼 공통)
  if (event.key === 'Tab') return handleTab(params);
  if (event.key === 'Home') return handleHome(params);
  if (event.key === 'End') return handleEnd(params);

  // (3) 셀 종류별 오픈/액션 키
  if (renderer === 'customSelectRenderer') {
    // Enter/Space → pick 모드 진입(셀 포커스 유지, <select> 는 포커스하지 않음).
    // ↑/↓ 는 여기서 가로채지 않으므로(아래 return false) pick 모드 밖에서는 행 이동이 유지된다.
    if (event.key === 'Enter' || event.key === ' ' || event.code === 'Space') {
      event.preventDefault();
      pickModeCellId = cellIdOf(params.node, params.column);
      return true;
    }
    return false; // ↑/↓/←/→ → ag-grid 셀 이동(행/열 내비게이션)
  }
  if (renderer === 'customFileButtonRenderer') return handleFileKeys(params);
  return false;
}
```

### 3.4 그리드 옵션 — pick 해제 훅

```js
export function buildCustomGridOptions({ editable, onAttachFile, onDownloadFile, onDirty }) {
  return {
    components: CUSTOM_GRID_COMPONENTS,
    context: { editable, onAttachFile, onDownloadFile },
    autoSizeStrategy: { type: 'fitCellContents' },
    defaultColDef: { filter: false, sortable: false, suppressKeyboardEvent: customSuppressKeyboard },
    // 포커스가 다른 셀로 바뀌면 pick 모드 해제(마우스 클릭/이동 등으로 빠져나갈 때 상태 정리)
    onCellFocused: resetSelectPickMode,
    getRowId: params => String(params.data._rid),
    onCellValueChanged: onDirty,
    rowSelection: { mode: 'singleRow', checkboxes: false, enableClickSelection: true },
    singleClickEdit: false,
    stopEditingWhenCellsLoseFocus: true
  };
}
```

---

## 4. 상호작용 흐름

```
[셀 포커스] 셀렉트 셀
   │  ↑/↓ → 행 이동(ag-grid 기본)  ← pick 모드 밖에서는 내비게이션 그대로
   │  Enter / Space → pick 모드 진입 (pickModeCellId = 이 셀, <select> 포커스 안 줌)
   ▼
[pick 모드] (셀 포커스 유지)
   │  ↑ / ↓ → cycleSelectValue: codes 순서로 값 사이클 + setDataValue 즉시 커밋(셀에 표시)
   │  Enter / Space → 확정(값은 이미 커밋됨) → pick 종료 → 셀 포커스 유지
   │  Escape → pick 종료(되돌리지 않음)
   │  Tab / Home / End / ← / → → pick 종료 후 일반 내비게이션
   ▼
[셀 포커스] 복귀 → ↑/↓ 는 다시 행 이동
```

마우스: 렌더러의 `<select>` 를 클릭하면 네이티브 OS 드롭다운이 열려 선택 → 렌더러 onChange 가 `setDataValue` 로 커밋(기존과 동일).

---

## 5. 실측 검증 결과 (하네스)

| 시나리오 | 결과 |
| --- | --- |
| pick 밖 + ↑/↓ | 행 이동(`col_x@0 → col_x@1`) — 내비게이션 보존 |
| Enter → pick 진입 | 포커스 셀 유지(`col_x@0`), select 포커스 안 줌 |
| pick + ↓ 연속 | 값 `'' → 01 → 02 → 03 → 03`(끝에서 클램프), 셀에 즉시 표시 |
| pick + ↑ | 이전 값(`03 → 02`) |
| pick + Space | **확정 완료**(값 유지), pick 종료, 이후 ↑/↓ 는 행 이동 |
| pick + Enter | 동일하게 확정·종료 |
| pick + Escape | pick 종료(되돌리지 않음) |
| pick + Tab | pick 종료 + 다음 셀 이동(`col_next@0`) |
| pick 중 다른 셀 포커스 | `onCellFocused` 로 pick 해제 |
| 값 변경 시 | `onCellValueChanged`(dirty) 발생(비동기) → 변경 추적됨 |
| 앱 마운트/컴파일 | 에러 없음 |

---

## 6. 함정 노트

- **`<select>` 를 포커스하지 마라.** 포커스하면 ag-grid 가 방향키에 `suppressKeyboardEvent` 를 호출하지 않아(폼 컨트롤 위임) ↑/↓ 를 가로챌 수 없다. 셀 포커스를 유지한 채 pick 모드 플래그로 제어한다.
- **네이티브 OS 드롭다운의 `select.value` 는 확정 전까지 하이라이트를 반영하지 않는다.** 현재 값은 반드시 데이터 모델(`api.getCellValue`)에서 읽는다.
- **ag-grid v35 에는 `api.getValue` 가 없다(제거됨).** `api.getCellValue({ rowNode, colKey })` 를 쓴다. (구버전 API를 쓰면 예외가 `suppressKeyboardEvent` 안에서 조용히 삼켜져 "아무 것도 안 되는" 증상이 된다.)
- **pick 모드는 상태(모듈 변수)다.** 포커스가 다른 셀로 이동하면 `onCellFocused` 로 반드시 해제해, 다른 셀에서 ↑/↓ 가 행 이동을 유지하도록 한다.
- **`onCellValueChanged`(dirty)는 비동기로 발생한다.** `setDataValue` 직후 동기적으로 확인하면 아직 안 잡히니, 검증 시 한 틱 뒤에 확인한다.
- **Space 를 확정키로 쓰는 대가는 "키보드 팝업 목록 없음"이다.** 값이 셀에서 바로 바뀌며 보이는 것으로 피드백을 대신한다. 팝업 목록과 Space 를 모두 원하면 네이티브 select 가 아니라 커스텀 리스트박스(직접 렌더)로 가야 한다.
