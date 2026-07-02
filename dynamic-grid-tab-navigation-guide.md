# 동적 그리드 — Tab 편집중 포커스 스킵 버그 수정 가이드

이 문서는 [동적 그리드 키보드 조작 & 헤더 폭 자동 맞춤 가이드](dynamic-grid-keyboard-autosize-guide.md)의 **후속편**이다.
편집 중 Tab을 눌렀을 때 `editable:false`인 셀렉트('02')/파일('03') 컬럼이 통째로 건너뛰어지는 버그를 다룬다.

> 이 문서는 실제 구현을 일반화한 **독립 샘플 가이드**다. 식별자·경로·필드명은 모두 예시(sample/custom)로 치환되어 있으며,
> 그대로 복사해 다른 화면에 적용할 수 있다.

> 대상 스택: ag-grid **v35.2.1** / React 18.2 / antd 5.21. 아래 진단·수치는 모두 하네스로 실측 확인했다.

관련 파일:

```
frontend/src/pages/SampleGrid/
├─ constants/gridColumnDefs.jsx          ← '02'/'03' 컬럼: editable + cellEditor 추가
└─ components/CustomNoopCellEditor.jsx   ← 신규. no-op 편집기(즉시 stopEditing)
```

---

## 1. 버그 증상

```
| 텍스트A(편집중..) | 셀렉트B | 셀렉트C | 텍스트D |
```

A를 편집하던 중 **Tab**을 누르면:

```
| 텍스트A | 셀렉트B | 셀렉트C | 텍스트D(편집중..) |
```

B, C를 완전히 건너뛰고 **D가 곧바로 편집모드로 진입**해버린다. 원하는 동작은:

```
| 텍스트A | 셀렉트B(Cell Selected) | 셀렉트C | 텍스트D |
```

즉 **B가 선택(포커스)만 되고, 거기서 Enter를 누르면 드롭박스가 열리는** 식으로 한 칸씩 정상 이동해야 한다.

## 2. 근본 원인 — ag-grid 자체의 기본 동작

ag-grid는 **셀이 편집 중일 때 Tab을 누르면**, 화면상 바로 다음 셀로 가는 게 아니라 **`colDef.editable`이 `true`인 다음 컬럼을 찾을 때까지 건너뛰면서**, 찾은 그 컬럼에서 **곧바로 편집을 시작**한다. `editable:false`인 컬럼(지금의 '02'/'03')은 이 탐색 대상에서 아예 제외된다.

> 이것은 우리가 추가한 `suppressKeyboardEvent`나 커스텀 렌더러 때문이 아니라 **ag-grid 순정 동작**이다. Enter/Space 키(방향키·Tab 아님)만 가로채는 `suppressKeyboardEvent`는 Tab 자체엔 관여하지 않는다.

**대조군 검증으로 확정:** '02' 컬럼만 임시로 `editable:true`(렌더러 없는 순수 텍스트)로 바꿔서 같은 시나리오를 재현하면, Tab이 **바로 다음 셀에 정확히 착지**한다. `editable:false` 하나가 원인 전부라는 뜻.

## 3. 시도했지만 안 통한 방법 — `tabToNextCell`

ag-grid는 "다음 셀이 뭔지"를 직접 계산해서 리턴할 수 있는 `gridOptions.tabToNextCell(params)` 콜백을 제공한다. 이걸로 "항상 화면상 바로 다음 셀"을 리턴하도록 구현해봤지만 **여전히 스킵됐다.**

계측해보니 Tab 한 번에 이 콜백이 **3번 연속 호출**됐다(B→C→D 순서로). 즉 ag-grid는:

1. `tabToNextCell` 호출 → B 리턴
2. B가 `editable:false` → 결과를 버리고 `previousCellPosition`을 B로 갱신해 **다시 호출**
3. `tabToNextCell` 호출 → C 리턴
4. C도 `editable:false` → 다시 호출
5. `tabToNextCell` 호출 → D 리턴 → D는 `editable:true` → **여기서 편집 시작**

`tabToNextCell`로는 "다음 셀 후보"만 바꿀 수 있을 뿐, **"editable 아니면 계속 건너뛴다"는 상위 필터링 로직 자체는 끌 수 없다.** 이 방법은 기각.

## 4. 해결책 — `editable:true` + no-op `cellEditor`

핵심 아이디어: **ag-grid에게는 "이 컬럼도 편집 가능하다"고 알려주되(Tab이 여기서 멈추게), 실제로 편집 UI가 뜨는 건 즉시 취소시킨다.**

- '02'/'03' 컬럼을 `editable`(바깥쪽 조회/편집 모드 파라미터, **하드코딩 true 아님** — 이유는 §4.3)로 설정.
- `cellEditor`에 **mount되자마자 즉시 `stopEditing()`을 호출하는 no-op 컴포넌트**를 지정.
- 기존의 `cellRenderer`(네이티브 select / 파일 버튼)와 `suppressKeyboardEvent`(Enter/Space 핸들러)는 **그대로 유지** — 아무것도 안 건드림.

### 4.1 신규 파일 — `components/CustomNoopCellEditor.jsx`

```jsx
import { useEffect } from 'react';

// 동적 셀렉트('02')/파일('03') 컬럼용 no-op 편집기.
//
// 이 컬럼들은 editable:true 로 두어야 ag-grid 가 "편집 중 Tab" 탐색에서 다음 정지 지점으로
// 인식한다(editable:false 컬럼은 ag-grid 가 건너뛰고 그 다음 editable 컬럼에서 곧바로 편집을
// 시작해버림 — Tab 스킵 버그의 원인). 하지만 이 컬럼들의 실제 상호작용은 항상 렌더러
// (customSelectRenderer/customFileButtonRenderer)가 전담하므로, ag-grid 의 기본 편집 UI가 뜨는 걸
// 원치 않는다. 그래서 mount 되자마자 즉시 stopEditing 을 호출해 편집을 취소하고, 셀은 렌더러
// 화면으로 곧바로 복귀시킨다 — 결과적으로 "포커스/선택만 이동, 편집 UI는 뜨지 않음" 상태가 된다.
function CustomNoopCellEditor(params) {
  useEffect(() => {
    params.stopEditing();
  }, [params]);

  return null;
}

export default CustomNoopCellEditor;
```

### 4.2 컴포넌트 등록 — `components/CustomFileButton.jsx`

```jsx
import CustomNoopCellEditor from './CustomNoopCellEditor.jsx';
// ...

export const CUSTOM_GRID_COMPONENTS = {
  customFileButtonRenderer: CustomFileButton,
  customSelectRenderer: CustomSelectCell,
  customNoopEditor: CustomNoopCellEditor   // ★ 신규
};
```

### 4.3 컬럼 정의 — `constants/gridColumnDefs.jsx`

'02', '03' 두 분기 모두 동일한 패턴을 적용:

```js
if (column.colTypCd === '02' && column.applyCommonCd) {
  const codes = getCodesByGroup?.(column.applyCommonCd) || [];
  const codeNameById = Object.fromEntries(codes.map(code => [code.cdId, code.cdNm]));

  return {
    ...baseColumn,
    // editable + no-op 편집기 조합: ag-grid 는 "편집 중 Tab" 탐색 시 editable:false 컬럼을
    // 건너뛰고 그 다음 editable 컬럼에서 곧바로 편집을 시작해버린다(Tab 스킵 버그). editable:true 로
    // 두면 이 셀이 Tab 정지 지점이 되고, customNoopEditor 가 mount 즉시 stopEditing 을 호출해 실제
    // 편집 UI는 뜨지 않은 채 렌더러(select) 화면으로 곧바로 복귀한다. 마우스 클릭/더블클릭은
    // 렌더러의 mousedown/click stopPropagation 이 애초에 ag-grid 편집시작 자체를 못 보게 막으므로
    // 이 편집기는 Tab 착지 시에만(그리고 suppressKeyboardEvent 가 못 막은 Enter 시에만) 마운트된다.
    // (하드코딩 true 가 아니라 바깥쪽 editable 을 그대로 씀 — 조회모드에서는 false 가 되어
    // Delete/붙여넣기 등 편집 가능 컬럼에만 열리는 ag-grid 기본 상호작용이 함께 막힌다.)
    editable,
    cellEditor: 'customNoopEditor',
    cellRenderer: 'customSelectRenderer',
    cellRendererParams: { codes, editable },
    suppressKeyboardEvent: openNativeSelectOnKeyboard,
    valueFormatter: params => (params.value ? (codeNameById[params.value] ?? params.value) : '')
  };
}
```

`'03'` 파일 컬럼도 동일하게 `editable` + `cellEditor: 'customNoopEditor'`를 추가한다(코드 생략, 패턴 동일).

**왜 하드코딩 `true`가 아니라 바깥쪽 `editable` 변수인가:** `buildCustomColumnDefs(customColumns, getCodesByGroup, editable)`의 `editable`은 조회/편집 모드 토글값이다. 이걸 그대로 써야 **조회 모드에서는 `editable:false`로 유지**되어, ag-grid가 이 컬럼에 Delete-지우기·붙여넣기 같은 "편집 가능 컬럼 전용" 상호작용을 열어주지 않는다. 하드코딩 `true`로 했다면 조회 모드에서도 Delete로 값이 지워지는 회귀가 생겼을 것(실측으로 확인, §6 참고).

## 5. 왜 이게 통하는가 (시퀀스)

```
[A 편집중] Tab
   │
   ▼
ag-grid: "편집중 Tab → 다음 editable 컬럼 찾기" → B(col_502) 발견(editable:true)
   │
   ▼
B 에서 편집 시작 시도 → cellEditor='customNoopEditor' mount
   │
   ▼
CustomNoopCellEditor.useEffect → params.stopEditing() 즉시 호출
   │
   ▼
편집 UI(기본 텍스트 인풋) 노출 없이 즉시 편집 취소
   │
   ▼
셀은 cellRenderer(customSelectRenderer, 즉 우리 <select>) 화면 그대로 유지
   │
   ▼
[B 포커스됨, 편집 아님 = "Cell Selected"] ← 요구사항 그대로 충족
   │
   ├─ Enter/Space → suppressKeyboardEvent(openNativeSelectOnKeyboard) 가 먼저 가로채서 드롭다운 오픈
   │                (no-op 에디터는 이 경로에선 아예 마운트되지 않음 — 아래 §6 실측)
   │
   └─ Tab(편집 아닌 상태) → 표준 "한 칸 이동" 내비게이션, C(col_503)로 정상 이동
```

## 6. 실측 검증 결과

전체 체인 [A(text) → B(select) → C(select) → D(text)]를 실제 소스(`buildCustomColumnDefs`/`buildCustomGridOptions`)로 구동한 하네스에서 확인.

| 단계 | 확인 항목 | 결과 |
| --- | --- | --- |
| A 편집중 + Tab | `focused` / `editing` | `focused: col_502`, **`editing: []`** (버그 수정 확인) |
| A 편집중 + Tab | B의 select 렌더러 표시 여부 | `selectVisibleAtB: true` (렌더러 그대로 유지) |
| B(선택됨)에서 Enter | `showPicker` 호출 여부 / no-op 에디터 마운트 여부 | `showPicker` 호출됨, **no-op 에디터 마운트 0회**(suppressKeyboardEvent가 먼저 가로챔) |
| B에서 옵션 선택 → Tab | 다음 이동 | `focused: col_503` (정상 한 칸 이동) |
| B, C에 더블클릭 | no-op 에디터 마운트 여부 | **0회** (렌더러의 mousedown/click stopPropagation이 애초에 ag-grid 편집시작을 못 보게 막음) |
| 조회 모드 전환 후 `colDef.editable` | 값 | `false` (바깥쪽 editable 변수를 그대로 반영, 하드코딩 아님) |
| 조회 모드에서 select 컬럼에 Delete 시도 | 값 변화 여부 | **변화 없음**(`valueAfter === valueBefore`), select도 안 보이고 읽기전용 텍스트만 표시 |
| 콘솔 에러 | — | 없음(백엔드 미기동 프록시 에러 제외) |

## 7. 곁다리로 열리는 부수 효과 (편집 모드 한정, 의도된 트레이드오프)

`editable:true`가 되면서 ag-grid가 이 컬럼을 "진짜 편집 가능 컬럼"으로 취급해 **편집 모드에서** 아래 두 가지가 추가로 가능해진다. 조회 모드에서는 `editable`이 `false`로 유지되므로 해당 없음(§6에서 확인).

- **Delete/Backspace로 셀 값 지우기.** 이전엔 `editable:false`라 막혀 있었다. 셀렉트를 키보드로 빠르게 초기화할 수 있는 편의 기능으로 볼 수도 있다. 원치 않으면 `suppressKeyboardEvent`에 Delete/Backspace 케이스를 추가해 막으면 된다.
- **클립보드 붙여넣기 / 채우기 핸들(fill-drag)로 값을 직접 쓸 수 있음.** `valueSetter`는 들어오는 값이 실제 공통코드 목록(`codes[].cdId`)에 있는지 검증하지 않으므로, 붙여넣기로 존재하지 않는 코드값이 들어갈 수 있다. 필요하면 `valueSetter`에 코드 유효성 검사를 추가하는 걸 권장한다(이번 수정 범위 밖).

## 8. 검증 방법 (독립 하네스)

백엔드 없이 이 수정만 격리 검증하려면, 실제 `buildCustomColumnDefs`/`buildCustomGridOptions`/`CustomUI.Grid`를 그대로 쓰는 하네스를 임시로 띄운다(커밋하지 않음).

- `[text, select, select, text]` 4컬럼 배치 + 조회/편집 토글 체크박스.
- `api.startEditingCell({rowIndex, colKey})`으로 텍스트 셀 편집 시작 → 실제 `<input>`에 값 세팅 → `Tab` keydown 디스패치 → `api.getFocusedCell()`/`api.getEditingCells()`로 착지 지점과 편집상태 확인.
- 대조군: '02' 컬럼을 임시로 `editable:true`(렌더러 없이)로 패치해서 Tab이 원래도 한 칸씩만 이동하는지 확인 → `editable:false`가 근본원인임을 증명.
- `tabToNextCell` 콜백에 호출 횟수 카운터를 심어 "여러 번 재호출되며 스킵"되는 정황을 직접 확인.
- no-op 에디터에 마운트 카운터를 심어 Enter 경로/더블클릭 경로에서 실제로 마운트되지 않음을 확인.
- 조회 모드에서 `colDef.editable`과 Delete 시도 후 값 변화 여부로 회귀 없음을 확인.

> 본 수정은 위 하네스로 ag-grid v35.2.1/React18.2/antd5.21 환경에서 표 안의 모든 항목을 통과 확인했다.

---

## 함정 노트 (요약)

- ag-grid는 **편집 중 Tab**과 **비편집 상태에서의 Tab**을 다른 로직으로 처리한다. 전자는 `editable:false` 컬럼을 건너뛰고 다음 `editable:true` 컬럼에서 곧바로 편집을 시작한다(순정 동작). 후자는 단순히 한 칸씩 이동한다.
- `tabToNextCell` 콜백은 "다음 셀 후보"만 바꿀 뿐, "editable 아니면 계속 건너뛴다"는 필터 자체는 못 끈다 — 이 버그의 해법이 아니다.
- 해법은 **"editable을 켜되, 실제 편집 UI는 못 뜨게 즉시 취소"** — `cellEditor`를 mount 즉시 `stopEditing()`을 호출하는 no-op 컴포넌트로 지정.
- `editable`은 **하드코딩 `true`가 아니라 조회/편집 모드 변수를 그대로** 써야 조회 모드에서 Delete/붙여넣기 같은 부수효과가 함께 차단된다.
- 이 트릭을 켜면 편집 모드에 한해 Delete-지우기·붙여넣기·채우기핸들이 추가로 열린다 — 원치 않으면 `suppressKeyboardEvent`/`valueSetter`에 가드를 추가.
- 마우스 클릭/더블클릭 경로는 기존 `stopPropagation` 덕분에 이 no-op 에디터가 아예 개입하지 않는다(렌더러가 이미 상호작용을 전담).
