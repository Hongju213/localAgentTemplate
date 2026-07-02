# 동적 그리드 — 셀렉트 셀 키보드·마우스·컬럼폭 최종 개선

동적 그리드의 공통코드 셀렉트('02') 셀에 대한 **완성본** 가이드다. 마우스 클릭, 키보드(Enter/Space/방향키/Tab), 컬럼 폭 자동 맞춤을 하나의 일관된 설계로 정리한다.

> 이 문서는 실제 구현을 일반화한 **독립 샘플 가이드**다. 식별자·경로·필드명은 모두 예시(sample/custom)로 치환되어 있으며, 그대로 복사해 다른 화면에 적용할 수 있다.

> 이 문서는 이전 [Tab 스킵 수정 가이드](dynamic-grid-tab-navigation-guide.md)의 `editable:true + no-op cellEditor` 방식을 **대체**한다. 그 방식은 Tab은 고쳤지만 마우스 클릭·방향키에서 회귀를 유발했다(아래 §1). 최종 설계는 셀렉트 컬럼을 `editable:false`로 유지하면서 Tab을 별도로 처리한다.

> 대상 스택: ag-grid **v35.2.1** / React 18.2 / antd 5.21. 아래 동작·수치는 모두 하네스로 실측 확인했다.

관련 파일:

```
frontend/src/pages/SampleGrid/
├─ constants/gridColumnDefs.jsx        ← 통합 키 디스패처 + 셀렉트 minWidth + 컬럼 정의
└─ components/
   ├─ CustomSelectCell.jsx             ← 네이티브 select 렌더러(변경 없음: 선택 후 셀 포커스 복귀 포함)
   └─ CustomFileButton.jsx             ← 파일 렌더러 + 컴포넌트 등록 맵
```

---

## 1. 증상 4가지와 근본 원인

| # | 증상 | 근본 원인 |
| --- | --- | --- |
| 1 | 셀렉트 클릭 시 드롭다운이 순간 열렸다 곧 닫힘 | `editable:true` + no-op editor 로 바꾼 것의 회귀. 셀렉트 컬럼은 `editable:false`(렌더러 전담)여야 마우스 동작이 안정적이다. |
| 2 | 드롭다운을 열고 ↓는 되는데 ↑ 누르면 목록이 아니라 **셀 선택이 위로 이동**하고 드롭다운이 닫힘(포커스 상실) | 셀렉트 컬럼의 키 핸들러가 방향키에 `false`를 반환 → `<select>`가 포커스를 가진(드롭다운 열린) 상태에서도 ag-grid가 방향키를 가로채 셀을 이동시키고 select를 blur 시킴. |
| 3 | 헤더가 짧고 옵션이 길 때, 긴 옵션을 선택하면 셀 안에서 `긴항목…`으로 잘림 | 닫힌 `<select>`는 선택값 하나만 렌더하므로 `autoSizeStrategy(fitCellContents)`가 "가질 수 있는 최장 옵션" 폭을 알 수 없다. `width:100%` select 는 셀 폭을 그대로 따라가므로 컬럼이 넓어지지 않는다. |
| 4 | (해결됨) 텍스트 편집 중 Tab → 다음이 셀렉트여도 셀 선택이 정상 이동 | 유지해야 할 정상 동작. |

**핵심 통찰(bug 2):** ag-grid는 셀 내부 `<select>`가 DOM 포커스를 갖고 있어도, 그 위에서 올라온 keydown을 **grid 루트에서 잡아 셀 내비게이션으로 처리**한다. 실측: row2 셀렉트가 포커스인 상태에서 ArrowUp → `focused: col_502@0`(셀이 위 행으로 이동), `activeElement`가 `<select>`에서 `.ag-cell`(DIV)로 바뀜 = select blur = 드롭다운 닫힘.

**핵심 통찰(bug 4 유지 조건):** ag-grid는 "편집 중 Tab"일 때 `editable:false` 컬럼을 건너뛰고 다음 `editable` 컬럼에서 곧바로 편집을 시작한다. 그래서 셀렉트를 `editable:false`로 되돌리면 이 스킵이 되살아난다 → Tab을 **직접** 처리해야 한다.

---

## 2. 최종 설계

세 원인을 하나의 일관된 구조로 해결한다.

1. **셀렉트/파일 컬럼은 `editable:false`** (렌더러가 상호작용 전담) → bug 1 회귀 제거. 부수적으로 Delete/붙여넣기 등 편집셀 부작용도 원천 차단.
2. **키 처리를 `defaultColDef.suppressKeyboardEvent` 하나의 디스패처로 통합** →
   - **Tab/Shift+Tab**: 편집 여부와 무관하게 정확히 한 칸 이동(스킵 없음). → bug 4 유지.
   - **셀렉트 셀**: `<select>`가 포커스면 모든 키를 네이티브 select에 위임(ag-grid 억제), 셀만 포커스면 Enter/Space로 열고 방향키는 셀 이동. → bug 2 해결.
   - **파일 셀**: Enter/Space로 첨부창.
3. **셀렉트 컬럼 `minWidth`를 최장 옵션 텍스트 폭으로 설정**(canvas 실측) → bug 3 해결.

> `colDef.suppressKeyboardEvent`는 `defaultColDef`를 덮어쓰므로, 컬럼별로 나눠 달지 않고 하나를 `defaultColDef`에 걸어 셀 종류(`cellRenderer`)로 분기한다. 이렇게 하면 텍스트·고정 컬럼까지 Tab 처리가 공통 적용된다.

---

## 3. 구현 — `constants/gridColumnDefs.jsx`

### 3.1 키 디스패처 (전 컬럼 공통)

```js
const isEnterOrSpace = event =>
  event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar' || event.code === 'Space';

// 셀 DOM 안의 네이티브 select 를 찾는다. 조회(뷰)모드면 span 이라 null.
const findCellSelect = event => {
  const cell = event.target?.closest?.('.ag-cell') ?? event.target;
  return cell?.querySelector?.('select.custom-select-cell') ?? null;
};

// Tab / Shift+Tab: 편집 여부와 무관하게 '정확히 한 칸' 이동(editable:false 셀도 스킵 안 함).
function handleTab(params) {
  const { api, column, node, event } = params;
  const columns = api.getAllDisplayedColumns();
  const index = columns.findIndex(col => col.getColId() === column.getColId());
  if (index === -1) return false;

  let nextIndex = event.shiftKey ? index - 1 : index + 1;
  let rowIndex = node.rowIndex;

  if (nextIndex >= columns.length) { nextIndex = 0; rowIndex += 1; }        // 행 경계 → 다음 행 첫 칸
  else if (nextIndex < 0) { nextIndex = columns.length - 1; rowIndex -= 1; } // → 이전 행 끝 칸

  event.preventDefault();
  api.stopEditing(false); // 편집 중이었다면 커밋

  if (rowIndex < 0 || rowIndex >= api.getDisplayedRowCount()) return true;   // 그리드 밖: 이동 안 함(스킵만 억제)

  api.clearFocusedCell();
  api.setFocusedCell(rowIndex, columns[nextIndex].getColId());
  return true;
}

// 셀렉트('02') 셀 키 처리.
function handleSelectKeys(params) {
  const event = params.event;
  const select = findCellSelect(event);
  if (!select) return false; // 조회모드(span) → ag-grid 기본

  // <select> 가 DOM 포커스를 가진 동안(=드롭다운 열림/활성)엔 모든 키를 네이티브 select 가 소유.
  // (preventDefault 하지 않음 → 방향키/Enter/타입어헤드를 select 가 처리, ag-grid 내비게이션만 억제)
  if (document.activeElement === select) return true;

  // 닫힌(셀만 포커스) 상태: Enter/Space → 드롭다운 오픈. 방향키 → ag-grid 셀 이동.
  if (isEnterOrSpace(event)) {
    event.preventDefault();
    select.focus();
    if (typeof select.showPicker === 'function') {
      try { select.showPicker(); } catch { /* user activation 실패 시 focus 폴백 */ }
    }
    return true;
  }
  return false;
}

// 파일('03') 셀 키 처리: 편집모드에서 Enter/Space → 첨부창.
function handleFileKeys(params) {
  const event = params.event;
  if (!isEnterOrSpace(event)) return false;
  if (!params.context?.editable) return false;
  event.preventDefault();
  const customCol = params.colDef?.cellRendererParams?.customCol;
  params.context?.onAttachFile?.(params.node?.data, customCol);
  return true;
}

// 전 컬럼 공통 디스패처
function customSuppressKeyboard(params) {
  const event = params.event;
  if (!event || event.type !== 'keydown') return false;
  if (event.key === 'Tab') return handleTab(params);

  const renderer = params.colDef?.cellRenderer;
  if (renderer === 'customSelectRenderer') return handleSelectKeys(params);
  if (renderer === 'customFileButtonRenderer') return handleFileKeys(params);
  return false;
}
```

### 3.2 셀렉트 컬럼 최소 폭 (bug 3)

```js
let measureCanvas;
const measureTextWidth = (text, font) => {
  if (typeof document === 'undefined') return (text?.length ?? 0) * 9; // 비브라우저 폴백
  if (!measureCanvas) measureCanvas = document.createElement('canvas');
  const ctx = measureCanvas.getContext('2d');
  ctx.font = font;
  return ctx.measureText(text ?? '').width;
};

const selectColumnMinWidth = codes => {
  const font = '14px "Malgun Gothic", -apple-system, "Segoe UI", Roboto, "Noto Sans KR", sans-serif';
  const longest = codes.reduce((max, code) => Math.max(max, measureTextWidth(code.cdNm, font)), 0);
  return Math.max(90, Math.ceil(longest) + 48); // 좌우 패딩 + select 화살표 여유
};
```

### 3.3 컬럼 정의 (해당 분기만)

```js
// '03' 파일
if (column.colTypCd === '03') {
  return {
    ...baseColumn, width: 210,
    editable: false,
    cellRenderer: 'customFileButtonRenderer',
    cellRendererParams: { customCol: column }
  };
}

// '02' 공통코드 셀렉트
if (column.colTypCd === '02' && column.applyCommonCd) {
  const codes = getCodesByGroup?.(column.applyCommonCd) || [];
  const codeNameById = Object.fromEntries(codes.map(code => [code.cdId, code.cdNm]));
  return {
    ...baseColumn,
    editable: false,                          // 렌더러 전담(마우스/키 편집 진입 차단). Tab 은 handleTab 담당.
    minWidth: selectColumnMinWidth(codes),    // 최장 옵션이 닫힌 select 에서 안 잘리게
    cellRenderer: 'customSelectRenderer',
    cellRendererParams: { codes, editable },  // editable=조회/편집 토글 → 렌더러가 select/텍스트 전환
    valueFormatter: params => (params.value ? (codeNameById[params.value] ?? params.value) : '')
  };
}
```

### 3.4 그리드 옵션

```js
export function buildCustomGridOptions({ editable, onAttachFile, onDownloadFile, onDirty }) {
  return {
    components: CUSTOM_GRID_COMPONENTS,
    context: { editable, onAttachFile, onDownloadFile },
    autoSizeStrategy: { type: 'fitCellContents' },
    // 전 컬럼 공통 키 처리(Tab 한 칸 이동 + 셀렉트/파일 Enter + 열린 select 키 위임)
    defaultColDef: { filter: false, sortable: false, suppressKeyboardEvent: customSuppressKeyboard },
    getRowId: params => String(params.data._rid),
    onCellValueChanged: onDirty,
    rowSelection: { mode: 'singleRow', checkboxes: false, enableClickSelection: true },
    singleClickEdit: false,
    stopEditingWhenCellsLoseFocus: true
  };
}
```

> `CustomSelectCell.jsx`의 `onChange`는 선택 확정 후 `params.api.setFocusedCell(...)`로 **포커스를 셀로 복귀**시킨다(기존 유지). 이것이 "선택 → 방향키/Tab로 다음 이동"을 이어준다.

---

## 4. 키보드 흐름 (열림 → 목록 이동 → 선택 → 이동)

```
[셀만 포커스(닫힘)] '02' 셀
   │
   │  Enter / Space → customSuppressKeyboard → handleSelectKeys(닫힘 분기)
   │     · event.preventDefault()
   │     · select.focus() + select.showPicker()
   │     · return true
   ▼
[<select> 포커스, 드롭다운 열림]
   │
   │  ↑ / ↓ → handleSelectKeys( document.activeElement === select ) → return true
   │     · ag-grid 내비게이션 억제(셀 이동 안 함)   ← bug 2 해결
   │     · preventDefault 안 함 → 네이티브 select 가 목록 이동
   │
   │  Enter(확정) → 마찬가지 위임 → 네이티브 select change
   ▼
CustomSelectCell.onChange
   · setDataValue → cols[customColId] 기록 (+ onDirty)
   · setFocusedCell → 포커스 셀로 복귀( <select> blur )
   ▼
[셀만 포커스(닫힘)]  ← 방향키=셀 이동,  Tab=handleTab(한 칸 이동),  Enter=다시 열기
```

Tab 흐름(편집/비편집 공통): `handleTab`이 현재 컬럼 인덱스 기준 정확히 한 칸(행 경계는 다음/이전 행으로 랩) 이동하고, 편집 중이었다면 `stopEditing(false)`로 커밋한다. `editable:false`인 셀렉트/파일 셀도 스킵되지 않는다.

---

## 5. 버그 → 해결 매핑

| 버그 | 해결 지점 |
| --- | --- |
| 1. 클릭 시 열렸다 닫힘 | 셀렉트 컬럼 `editable:false` 복귀(no-op editor 제거) → 클릭이 편집을 시작하지 않아 refresh/닫힘 없음 |
| 2. ↑ 시 셀 이동·포커스 상실 | `handleSelectKeys`: `document.activeElement === select`면 `return true`로 ag-grid 방향키 처리 억제, 네이티브 select가 목록 이동 소유 |
| 3. 긴 옵션 잘림 | `selectColumnMinWidth(codes)`로 컬럼 `minWidth`를 최장 옵션 폭으로 확보 |
| 4. Tab 한 칸 이동 유지 | `handleTab`을 `defaultColDef.suppressKeyboardEvent`로 전 컬럼 공통 적용(editable:false여도 스킵 없음) |

---

## 6. 실측 검증 결과 (하네스, 실제 소스 구동)

배치 `[A(text) · B(select) · C(select) · D(text) · F(file)]`, 옵션에 매우 긴 항목 포함.

| 항목 | 결과 |
| --- | --- |
| Tab 체인: A(편집중)+Tab → B → C → D → F | 각 단계 `focused` 한 칸씩 이동, `editing: []`(자동편집 없음), 스킵 없음 |
| Enter로 드롭다운 오픈 | `activeElement === select`, `enterPrevented: true` |
| select 포커스 상태 ↑/↓ | `focused` 불변(셀 이동 없음), select 포커스 유지 — **bug 2 해결** |
| 선택 확정(change) 후 | `activeElement`가 `.ag-cell`로 복귀, 이후 ↑ → 셀이 위 행으로 이동(내비 정상 복귀) |
| 실제 마우스 클릭(editable:false) | `editing: []`, select 포커스 유지, DOM 유지 — **bug 1 회귀 없음** |
| 긴 옵션 컬럼 폭 / 선택값 | 컬럼 `398px`, 선택값 `scrollWidth === clientWidth`(잘림 없음) — **bug 3 해결** |
| 파일 셀 Enter / Space | `onAttachFile` 호출 |
| 조회모드 | `hasSelect: false`(span, 코드명 표시), `colDef.editable: false`, Delete로 값 안 지워짐 |

---

## 7. 함정 노트

- ag-grid는 셀 내부 위젯이 포커스여도 keydown을 grid 루트에서 잡는다. **열린 네이티브 select의 방향키를 지키려면** `document.activeElement === select`일 때 `suppressKeyboardEvent`가 `true`를 반환해 ag-grid 내비게이션을 억제해야 한다(단 `preventDefault`는 하지 말 것 — select가 처리하도록).
- 셀렉트 셀은 `editable:false`가 정답이다. `editable:true`로 만들면 마우스 클릭이 불안정해지고(회귀) Delete/붙여넣기 부작용이 열린다. Tab 스킵은 `editable`로 풀지 말고 `suppressKeyboardEvent`의 `handleTab`으로 직접 이동시켜라.
- `suppressKeyboardEvent`는 **편집 중에도 호출**되며 `true` 반환 시 ag-grid 기본(편집 중 Tab 스킵 포함)을 억제한다 — 이걸로 Tab을 완전히 제어한다.
- 닫힌 `<select>`(width:100%)는 `fitCellContents`로 옵션 폭을 알 수 없다. 최장 옵션 폭을 **canvas로 실측**해 `minWidth`로 잡아야 잘림을 막는다.
- `showPicker()`는 Chromium 121+ 필요(폴백: focus 후 Enter 재입력 시 오픈).
