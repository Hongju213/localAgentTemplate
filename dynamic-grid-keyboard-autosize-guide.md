# 동적 그리드 — 키보드 조작 & 동적 헤더 폭 자동 맞춤 가이드

이 문서는 [동적 그리드 셀렉트 셀 구현 가이드](dynamic-grid-select-cell-guide.md)의 **후속편**이다.
셀렉트 셀(네이티브 `<select>` 렌더러) 위에 두 가지를 더 얹은 내용을 다룬다.

1. **키보드 조작(엑셀 유사):** 방향키/Tab 로 셀을 옮기고, Enter/Space 로 드롭다운·파일첨부창을 열고, 선택 후 다시 셀 이동으로 복귀.
2. **동적 헤더 폭 자동 맞춤:** 상위 선택값마다 컬럼(헤더 문자열)이 바뀌는데, 그 길이에 딱 맞게 폭이 잡혀 `…` 로 잘리지 않도록.

> 이 문서는 실제 구현을 일반화한 **독립 샘플 가이드**다. 식별자·경로·필드명은 모두 예시(sample/custom)로 치환되어 있으며,
> 그대로 복사해 다른 화면에 적용할 수 있다.

> 대상 스택: ag-grid **v35.2.1** / React 18.2 / antd 5.21. 아래 수치·동작은 모두 하네스로 실측 확인했다.

관련 파일:

```
frontend/src/
├─ components/Grid.jsx                                   ← 공통 그리드(CustomUI.Grid). autoSize 시 sizeColumnsToFit 스킵
└─ pages/SampleGrid/
   ├─ index.jsx                                          ← 편집전환 refresh + 동적컬럼 재-autosize 이펙트
   ├─ components/CustomSelectCell.jsx                    ← 선택 후 셀 포커스 복귀
   └─ constants/gridColumnDefs.jsx                       ← suppressKeyboardEvent 2종 + autoSizeStrategy
```

---

# Part 1. 키보드 조작 (엑셀 유사)

## 1.1 원하는 UX 흐름

```
방향키(상하좌우)로 셀 이동
   → Enter 또는 Space
        · '02' 셀렉트 셀 : 드롭다운 오픈
        · '01' 텍스트 셀 : 입력(편집) 모드  (ag-grid 기본 동작, 이미 됨)
        · '03' 파일 셀   : 첨부창(파일 다이얼로그) 오픈
   → (드롭다운) 상/하로 옵션 고른 뒤 Enter → 값이 셀에 세팅
   → 다시 방향키로 셀 이동  또는  Tab 으로 다음 항목
   → Enter → 오픈 → 선택 → Tab → … 반복
```

## 1.2 왜 Enter/Space 로 드롭다운이 안 열렸나 (근본 원인)

ag-grid 는 키보드로 셀을 이동할 때 **셀 컨테이너(`.ag-cell` div)에 포커스**를 둔다. 셀 안의 `<select>` 에 두지 않는다.
그래서 Enter/Space 키 이벤트는 ag-grid 의 셀 키 핸들러로 가는데, '02' 컬럼은 `editable:false` 인 **렌더러 셀**이라
ag-grid 가 기본적으로 아무 것도 하지 않는다 → 네이티브 `<select>` 는 키를 받지 못하니 열리지 않는다.

> 마우스 클릭이 잘 됐던 이유: 클릭은 `<select>` DOM 이 직접 받기 때문. 키보드는 포커스가 셀에 있어 select 로 전달되지 않는다.

**해결 방향:** 키 이벤트를 **셀 레벨에서 가로채(intercept)**, 셀 내부의 `<select>`(또는 첨부 액션)를 프로그램적으로 실행한다.
이 후크가 ag-grid 의 **`colDef.suppressKeyboardEvent`** 다.

## 1.3 `suppressKeyboardEvent` — 무엇이고 왜 이걸 쓰나

- ag-grid 는 포커스된 셀에서 keydown 이 발생하면, 그 컬럼의 `suppressKeyboardEvent(params)` 를 먼저 호출한다.
- **`true` 반환** → "이 키에 대한 ag-grid 기본 처리를 하지 마라"(억제). 우리가 원하는 side-effect(드롭다운 열기)를 여기서 수행하고 true 를 돌려주면, ag-grid 의 기본 동작(예: Space = 페이지 스크롤/행 선택 토글)을 막을 수 있다.
- **`false` 반환** → ag-grid 가 평소대로 처리(방향키 이동, Tab 이동, 텍스트셀 Enter 편집 등). → **네비게이션은 그대로 유지된다.**

즉 우리는 **Enter/Space 일 때만 true** 를 반환하고, 나머지 키(방향키·Tab 등)는 전부 `false` 를 반환해 ag-grid 에 맡긴다.

## 1.4 구현 — `constants/gridColumnDefs.jsx`

### (a) '02' 셀렉트 셀: Enter/Space → 드롭다운 오픈

```js
// Enter/Space 로 네이티브 select 드롭다운을 연다.
// ag-grid 는 셀 탐색 중 셀(.ag-cell)에 포커스를 두고 keydown 을 처리하므로, 그 이벤트를 가로채
// 셀 내부의 <select> 를 프로그램적으로 오픈한다. suppressKeyboardEvent 가 true 를 반환하면
// ag-grid 기본 키 처리(Space 스크롤/선택 토글 등)를 억제한다.
function openNativeSelectOnKeyboard(params) {
  const event = params.event;
  if (!event || event.type !== 'keydown') return false;

  const isEnter = event.key === 'Enter';
  const isSpace = event.key === ' ' || event.key === 'Spacebar' || event.code === 'Space';
  if (!isEnter && !isSpace) return false;                     // 방향키/Tab → ag-grid 에 위임

  const cell = event.target?.closest?.('.ag-cell') ?? event.target;
  const select = cell?.querySelector?.('select.custom-select-cell'); // 조회모드면 select 없음 → 통과
  if (!select) return false;

  event.preventDefault();                                     // Space 스크롤/선택토글 억제
  select.focus();
  if (typeof select.showPicker === 'function') {
    try { select.showPicker(); } catch { /* user-activation 필요 실패 시 focus 폴백 */ }
  }
  return true;                                                // ag-grid 기본 처리 억제
}
```

`'02'` colDef 에 연결:

```js
return {
  ...baseColumn,
  editable: false,
  cellRenderer: 'customSelectRenderer',
  cellRendererParams: { codes, editable },
  suppressKeyboardEvent: openNativeSelectOnKeyboard,   // ★ Enter/Space 로 드롭다운
  valueFormatter: ...
};
```

### (b) '03' 파일 셀: Enter/Space → 첨부창 오픈

같은 패턴. 다만 열 것은 select 가 아니라 첨부 액션(`context.onAttachFile`)이다. 컬럼별 대상이 다르므로 **팩토리**로 만든다.

```js
// Enter/Space 로 파일 첨부창(첨부 버튼과 동일 동작)을 연다. 편집모드에서만 동작.
function makeFileAttachKeyHandler(column) {
  return params => {
    const event = params.event;
    if (!event || event.type !== 'keydown') return false;

    const isEnter = event.key === 'Enter';
    const isSpace = event.key === ' ' || event.key === 'Spacebar' || event.code === 'Space';
    if (!isEnter && !isSpace) return false;
    if (!params.context?.editable) return false;              // 조회모드는 기본 처리에 위임

    event.preventDefault();
    params.context?.onAttachFile?.(params.node?.data, column);
    return true;
  };
}
```

`'03'` colDef 에 연결:

```js
return {
  ...baseColumn, width: 210, editable: false,
  cellRenderer: 'customFileButtonRenderer',
  cellRendererParams: { customCol: column },
  suppressKeyboardEvent: makeFileAttachKeyHandler(column)   // ★ Enter/Space 로 첨부창
};
```

## 1.5 구현 — `components/CustomSelectCell.jsx` (선택 후 셀 포커스 복귀)

드롭다운에서 옵션을 고르면 `change` 가 나고, 이 때 포커스는 `<select>` 에 남는다.
그 상태로 방향키를 누르면 **셀 이동이 아니라 select 값이 바뀌어 버린다.** 그래서 선택 확정 직후 **포커스를 그리드 셀로 되돌린다.**

```js
const handleChange = event => {
  // valueSetter 호출 + onCellValueChanged(onDirty) 발생
  params.node.setDataValue(params.column.getColId(), event.target.value);
  // 선택 확정 후 그리드 셀로 포커스 복귀 → 방향키/Tab 셀 이동이 다시 동작(엑셀 유사)
  params.api?.setFocusedCell(params.node.rowIndex, params.column.getColId());
};
```

이 한 줄(`setFocusedCell`)이 "선택 → 방향키/Tab 이동" 을 자연스럽게 이어준다.

## 1.6 전체 키보드 시퀀스

```
[셀 포커스] '02' 셀   ── Enter/Space ─▶ suppressKeyboardEvent(openNativeSelectOnKeyboard)
                                          · event.preventDefault()
                                          · select.focus() + select.showPicker()
                                          · return true (ag-grid 기본 억제)
                                          ▼
                                     [OS] 네이티브 드롭다운 오픈
                                          ▼
                          상/하 옵션 선택 → Enter 확정 → <select> change
                                          ▼
                          CustomSelectCell.onChange
                                          · setDataValue → cols[customColId] 기록 (+ onDirty)
                                          · setFocusedCell → 포커스 셀로 복귀
                                          ▼
[셀 포커스] 복귀 ── 방향키(셀 이동) 또는 Tab(다음 셀) ──▶ 다음 '02' 셀 ── Enter … 반복
```

## 1.7 네비게이션이 안 깨지는 이유

`suppressKeyboardEvent` 는 **Enter/Space 이고 대상 셀에 select/첨부가 있을 때만 `true`**, 그 외 모든 키(방향키·Tab·문자 등)는 `false` 를 반환한다.
`false` 면 ag-grid 가 평소대로 처리하므로 방향키 이동·Tab 이동·텍스트셀 Enter 편집은 **그대로 유지**된다.
(실측: ArrowRight 입력 시 다음 컬럼으로 정상 이동 확인.)

## 1.8 주의 — `showPicker()` 브라우저 요건

`HTMLSelectElement.showPicker()` 로 네이티브 옵션 목록을 **한 번에** 연다. 지원: **Chromium 121+**.
그보다 낮은 브라우저에서는 `try/catch` 로 폴백되어 첫 Enter 는 select 에 **포커스만** 주고, **Enter 를 한 번 더** 누르면 열린다
(포커스된 네이티브 select 는 Enter/Space/Alt+Down 으로 열림). 사내 브라우저 버전이 낮다면 폴백 UX 를 감안할 것.

---

# Part 2. 동적 헤더 폭 자동 맞춤 (autosize)

## 2.1 문제 — 왜 헤더가 `…` 로 잘렸나

공통 그리드(`Grid.jsx`)는 `onGridReady` 에서 **무조건 `api.sizeColumnsToFit()`** 을 호출했다.
`sizeColumnsToFit` 은 **뷰포트 폭에 맞춰 컬럼을 균등 분배**하는 동작이라, 동적 컬럼이 여러 개면 각 컬럼이 내용과 무관하게
비슷한 폭으로 눌리고 → **긴 헤더가 잘린다(`…`).**

> 실측(수정 전): 1000px 폭에 컬럼들이 각 192px 로 균등 분배 → 헤더 `이것은매우…항목명칭`(필요폭 258)이 client 160 으로 **잘림(truncated=true).**

## 2.2 해결 — `fitCellContents` 전략 + 조건부 스킵 + 동적 재조정

세 조각이 함께 동작한다.

### (a) 공통 그리드가 autoSize 를 방해하지 않도록 — `components/Grid.jsx`

`autoSizeStrategy` 를 지정한 그리드에서는 `sizeColumnsToFit()` 로 폭을 덮어쓰지 않는다. (옵트인이라 다른 화면 영향 없음.)

```js
const handleGridReady = event => {
  onGridReady?.(event);

  // autoSizeStrategy(콘텐츠 맞춤 폭)를 지정한 그리드는 sizeColumnsToFit 으로 폭을 덮어쓰지 않는다.
  // (덮어쓰면 헤더가 잘리거나 균등분배되어 fit-to-content 가 무효가 된다.)
  if (!gridOptions.autoSizeStrategy) {
    event.api.sizeColumnsToFit();
  }

  if (!isLoading) {
    event.api.setGridOption?.('loading', false);
  }
};
```

### (b) 동적 그리드가 콘텐츠 맞춤을 선언 — `buildCustomGridOptions`

```js
export function buildCustomGridOptions(...) {
  return {
    components: CUSTOM_GRID_COMPONENTS,
    context: { editable, onAttachFile, onDownloadFile },
    // 동적 헤더/셀 내용에 딱 맞게 컬럼 폭 자동 조정(헤더 잘림 '…' 방지).
    // skipHeader 기본 false → 헤더 텍스트 폭도 측정에 포함된다.
    autoSizeStrategy: { type: 'fitCellContents' },
    ...
  };
}
```

- `type: 'fitCellContents'` → 각 컬럼을 **셀 내용 + 헤더**에 맞춰 폭 산정.
- `skipHeader` 기본값 `false` → **헤더 텍스트 폭이 측정에 포함**되어, 긴 헤더도 잘리지 않는다.
- 이 옵션은 `Grid.jsx` 의 `{...restGridOptions}` 스프레드를 통해 `AgGridReact` 로 그대로 전달된다.

### (c) 동적 컬럼 교체/리네이밍 시 재조정 — `SampleGrid/index.jsx`

`autoSizeStrategy` 는 **최초 렌더에만** 적용된다. 상위 선택값을 바꿔 컬럼 세트가 통째로 교체되거나, 같은 컬럼의
헤더 이름만 바뀌어도 다시 맞춰줘야 한다.

```js
// 상위 선택값이 바뀌어 동적 컬럼 세트가 교체되면 헤더/셀 내용에 맞춰 폭 재조정(헤더 '…' 잘림 방지).
// autoSizeStrategy 는 최초 렌더에만 적용되므로 컬럼 변경 시 명시적으로 다시 맞춘다.
// rAF 를 2중으로 거는 이유: 컬럼 개수/colId 는 그대로고 헤더 문자열(colNm)만 바뀌는 경우
// (같은 상위 선택값의 컬럼명을 관리화면에서 수정한 뒤 재조회 등), ag-grid 가 새 헤더 텍스트를
// 실제 DOM에 반영하기 '전' 프레임에 폭을 측정해버리는 레이스가 실측으로 확인됨 — 프레임을
// 하나 더 기다리면 안정적으로 새 텍스트 기준 폭이 잡힌다.
useEffect(() => {
  let raf2;
  const raf1 = requestAnimationFrame(() => {
    raf2 = requestAnimationFrame(() => gridRef.current?.api?.autoSizeAllColumns());
  });
  return () => {
    cancelAnimationFrame(raf1);
    if (raf2) cancelAnimationFrame(raf2);
  };
}, [customColumns]);
```

- `autoSizeAllColumns()` 는 `skipHeader` 기본 false → **헤더 포함**해서 전 컬럼 재조정.
- **왜 rAF 가 두 번인가:** 컬럼 세트가 통째로 바뀌는 경우(다른 상위 선택값)는 단일 rAF 로도 충분했지만,
  **컬럼 개수/`colId` 는 그대로고 헤더 문자열만 바뀌는 경우**를 실측했더니 단일 rAF 는 **실패**했다
  (헤더 텍스트는 갱신됐는데 폭은 이전 값 그대로 남아 **잘림 발생**). ag-grid 가 `columnDefs` prop 변경을
  받아 헤더 셀 텍스트를 실제 DOM에 반영하는 시점이 리액트 커밋 다음 프레임이라, 첫 rAF 시점엔 아직
  구 텍스트 기준으로 측정돼버리는 레이스였다. 프레임을 하나 더 기다리면(`raf` 안에서 `raf` 를 또 예약)
  안정적으로 새 텍스트 기준 폭이 잡힌다. (3회 연속 토글 재현 테스트로 안정성 확인.)

## 2.3 실측 검증 결과

| 상황 | 헤더 | 필요폭(scroll) | 실제 client | 잘림 |
| --- | --- | --- | --- | --- |
| 수정 전(sizeColumnsToFit) | `이것은매우…항목명칭` | 258 | 160 | **잘림** |
| 수정 후(fitCellContents) | `이것은매우…항목명칭` | 258 | 258 (col 310) | 없음 |
| 수정 후 | `등급` | 26 | 26 (col 114) | 없음 |
| 컬럼 세트 교체 후 | `아주아주…테스트` | 296 | 296 (col 349) | 없음 |
| 컬럼 세트 교체 후 | `중간길이헤더컬럼` | 103 | 103 (col 156) | 없음 |
| 헤더 텍스트만 변경(단일 rAF) | `이것은완전히…변경되었습니다` | 348 | 58 (col 90) | **잘림** |
| 헤더 텍스트만 변경(더블 rAF) | `이것은완전히…변경되었습니다` | 348 | 348 (col 400) | 없음 |
| 헤더 텍스트만 변경 → 다시 짧게(더블 rAF) | `짧` | 13 | 13 (col 90) | 없음 |

→ 컬럼 **개수가 바뀌는 경우**와 **텍스트만 바뀌는 경우** 모두, 더블 rAF 적용 후 전부 `label.scrollWidth === label.clientWidth`(잘림 없음). 성장/축소 양방향 및 3회 연속 토글에서 안정적으로 재현됨.

## 2.4 주의 사항

- **`minWidth` 하한:** `Grid.jsx` 의 `defaultColDef.minWidth: 90` 때문에 아주 짧은 헤더 컬럼(예: `A`, `짧`)은 90px 이하로는 안 줄어든다(잘림은 없음). 더 촘촘히 붙이려면 동적 그리드 쪽 `defaultColDef.minWidth` 를 낮추면 된다.
- **뷰포트를 꽉 채우지 않을 수 있음:** 콘텐츠 합계가 그리드보다 좁으면 오른쪽에 여백이 생긴다(= 균등분배를 포기한 대가). 요구사항이 "내용 맞춤" 이므로 의도된 동작이다.
- **다른 화면 영향 없음:** `Grid.jsx` 변경은 `autoSizeStrategy` 를 준 그리드에서만 `sizeColumnsToFit` 을 스킵한다. 다른 화면(일반 목록 그리드 등)은 `autoSizeStrategy` 가 없어 기존대로 `sizeColumnsToFit` 이 동작한다.

---

# Part 3. 검증 방법 (독립 하네스)

백엔드 없이 키보드/autosize 만 격리 검증하려면, 실제 빌더/`CustomUI.Grid` 를 쓰는 하네스를 임시로 띄운다(커밋하지 않음).

- 목(mock) `customColumns` 에 **헤더 길이를 제각각**(짧음/중간/아주 긴 것)으로 넣고, 셀렉트('02')·파일('03') 컬럼을 섞는다.
- `onGridReady` 에서 `window.__gridApi = event.api` 노출.

**키보드 검증**
1. `api.setFocusedCell(0, 'col_XXX')` 로 '02' 셀 포커스 → `KeyboardEvent('keydown', {key:'Enter'})` 디스패치 → `showPicker` 호출 + `event.defaultPrevented === true` 확인.
2. `change` 발생 시 `cols[id]` 기록 + `setFocusedCell` 호출(포커스 복귀) 확인.
3. '03' 셀에서 Enter/Space → `onAttachFile` 호출 확인.
4. ArrowRight → `getFocusedCell()` 이 다음 컬럼으로 이동(네비게이션 유지) 확인.

**autosize 검증**
- 각 `.ag-header-cell-text` 의 `scrollWidth` vs `clientWidth` 를 비교해 `잘림 = scrollWidth > clientWidth` 로 측정.
- 컬럼 세트를 런타임에 교체한 뒤에도 전부 `잘림 = false` 인지 확인.
- **컬럼 개수/`colId` 는 그대로 두고 헤더 문자열만 바꾼 케이스**를 별도로 검증. 단일 rAF 로는
  재현적으로 잘림이 발생했고, 더블 rAF 로 교체 후 3회 연속 토글(성장→축소→성장)에서 매번 잘림 없음을 확인.

> 본 구현은 위 하네스로 v35.2.1/React18.2/antd5.21 에서 Part1·Part2 항목을 모두 통과 확인했다.

---

# 함정 노트 (요약)

- ag-grid 는 셀 탐색 중 **`.ag-cell` 에 포커스**를 둔다(셀 내부 위젯이 아님). 렌더러 셀에서 키로 뭔가 열려면 `suppressKeyboardEvent` 로 셀 레벨에서 가로채라.
- `suppressKeyboardEvent` 는 처리한 키에만 `true`, 나머지는 반드시 `false` → 방향키/Tab 네비게이션 보존.
- 위젯에서 값 선택 후 **`setFocusedCell` 로 포커스를 셀로 되돌려야** 방향키/Tab 이동이 이어진다.
- `sizeColumnsToFit`(균등분배)와 `fitCellContents`(내용맞춤)는 **상충**한다. 콘텐츠 맞춤을 원하면 `sizeColumnsToFit` 을 스킵하라.
- `autoSizeStrategy` 는 최초 렌더 전용 → **동적 컬럼 변경 시 `autoSizeAllColumns()` 를 다시 호출**.
- **rAF 는 한 번이 아니라 두 번(double rAF)** 걸어라. 컬럼 개수가 바뀌는 경우는 단일 rAF 로도 됐지만,
  **헤더 문자열만 바뀌는 경우는 단일 rAF 가 실측으로 실패**했다(구 텍스트 기준으로 측정해버림). 프레임을
  하나 더 기다려야 새 헤더 텍스트가 DOM에 반영된 뒤 측정된다.
- `showPicker()` 는 Chromium 121+ 필요(폴백 있음).
