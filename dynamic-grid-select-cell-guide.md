# 동적 그리드 — 셀렉트 셀(공통코드 '02' 타입) 구현 가이드

샘플 등록 화면(`샘플 관리 > 등록/작성`)의 **동적 정보 그리드**는
상위 선택값에 딸린 컬럼 정의(`customColumns`)를 읽어 **런타임에 컬럼을 동적으로 생성**한다.
각 컬럼은 공통코드 `colTypCd` 값에 따라 셀의 편집 UI가 달라진다.

| `colTypCd` | 의미 | 셀 UI |
| --- | --- | --- |
| `01` | 텍스트 | 일반 텍스트 편집 셀 |
| `02` | 공통코드 셀렉트 | **네이티브 `<select>` 드롭다운** (이 문서의 주제) |
| `03` | 파일 | 첨부/다운로드 버튼 렌더러 |

이 문서는 그중 **'02' 셀렉트 셀**을 어떻게 구현했는지, 왜 그렇게 구현했는지,
그리고 전체 코드가 어떻게 맞물려 도는지를 처음부터 끝까지 상세히 기록한다.

> 이 문서는 실제 구현을 일반화한 **독립 샘플 가이드**다. 식별자·경로·필드명은 모두 예시(sample/custom)로 치환되어 있으며,
> 그대로 복사해 다른 화면에 적용할 수 있다.

---

## 1. 요구사항과, 그 요구사항이 왜 까다로웠나

### 1.1 요구사항

1. **셀에 포커스가 없던 상태에서도**, '02' 셀렉트 셀을 **한 번 클릭하면 곧바로 드롭다운이 열려야 한다.** (최우선)
2. 드롭다운에서 항목을 고르면 **그 값이 셀에 즉시 반영(입력)되어야 한다.**
3. 위 1, 2가 **동시에** 만족되어야 한다.

### 1.2 처음 접근(agSelectCellEditor)이 왜 실패했나

기존 구현은 ag-grid 내장 편집기 `agSelectCellEditor`를 썼다.

```jsx
// (구) gridColumnDefs.jsx — 문제가 된 구현
if (column.colTypCd === '02' && column.applyCommonCd) {
  const codes = getCodesByGroup?.(column.applyCommonCd) || [];
  const codeNameById = Object.fromEntries(codes.map(c => [c.cdId, c.cdNm]));
  return {
    ...baseColumn,
    editable,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: { values: ['', ...codes.map(c => c.cdId)] },
    valueFormatter: p => (p.value ? (codeNameById[p.value] ?? p.value) : '')
  };
}
```

`gridOptions` 에는 `singleClickEdit: false`, `stopEditingWhenCellsLoseFocus: true` 가 걸려 있었다.

ag-grid의 **편집기(cell editor)** 는 "편집 모드"라는 별도 상태에 들어가야 화면에 나타난다.

- `singleClickEdit: false` → **더블클릭**(또는 Enter/F2)을 해야 편집 모드 진입. 한 번 클릭으로는 아무 일도 안 일어난다.
- `singleClickEdit: true` 로 바꿔도 → 한 번 클릭에 편집 모드로는 들어가지만, `agSelectCellEditor`는 **편집 시작 시 드롭다운을 자동으로 열어주지 않는다.** 열려면 셀렉트를 한 번 더 클릭해야 한다. (자동 오픈 옵션이 없다.)

즉 편집기 방식으로는 "**한 번 클릭 → 곧바로 드롭다운 오픈**"이 구조적으로 안 된다.
그래서 커스텀 렌더러/편집기로 우회를 시도하면, 이번엔 **선택한 값이 셀에 안 들어가는** 문제(값 반영 경로가 끊김)로 넘어가면서
"둘 중 하나만 겨우 되는" 교착에 빠졌던 것이다.

> **실측(ag-grid v35.2.1):** 셀에 합성 mousedown/click, 그리고 dblclick 을 쏴도 `agSelectCellEditor` 는
> 드롭다운을 열지 않았다. `singleClickEdit`/편집기 조합으로는 요구사항 1을 만족할 수 없음을 확인.

### 1.3 왜 antd `<Select>` 렌더러도 잘 안 됐나

셀 안에 antd `<Select>` 를 렌더한 시도도 잘 안 됐던 이유:

- antd Select는 `div` 기반 위젯이고 **드롭다운을 body 포털에 그린다.**
- ag-grid 셀은 자체 `mousedown` 핸들러로 포커스/레인지 선택을 처리하는데, 이게 antd Select의 첫 클릭과 충돌해 **두 번 클릭해야 열리거나**,
- 포털로 빠진 옵션을 클릭하면 ag-grid가 "셀 바깥 클릭"으로 간주해 편집을 종료/blur 시켜 **값이 유실**되기 쉽다.

---

## 2. 채택한 해결책 — "편집기"가 아니라 "상시 렌더러 + 네이티브 select"

핵심 아이디어는 **편집 모드를 아예 쓰지 않는 것**이다.

- '02' 컬럼을 `editable: false` 로 두고, 대신 **셀 렌더러**로 **네이티브 `<select>` 를 항상 그려 둔다.**
- 네이티브 `<select>` 는 브라우저/OS가 드롭다운을 직접 그린다. 그래서:
  - **한 번 클릭 = 즉시 드롭다운 오픈** (요구사항 1). 편집 모드 진입이 필요 없다.
  - 포털/오버레이 이슈가 없다 (OS가 렌더링).
- 값 반영은 `onChange` 에서 `node.setDataValue(...)` 로 처리 → **valueSetter 호출 + `onCellValueChanged` 발생** (요구사항 2).

여기에 두 가지 "함정 방지" 장치가 붙는다.

1. **`onMouseDown`/`onClick` 에서 `stopPropagation`** — ag-grid 셀의 mousedown 핸들러가 첫 클릭을 가로채(preventDefault/포커스 탈취) 드롭다운 오픈을 막지 못하게 격리. (단, `preventDefault` 는 **호출하지 않는다** → select 고유의 "열기" 기본동작은 유지)
2. **편집↔조회 전환 시 `refreshCells({ force: true })`** — '02' 셀의 colDef는 편집상태와 무관하게 동일해서 ag-grid가 자동으로 다시 그리지 않는다. 렌더러가 최신 `editable` 을 반영하도록 강제 refresh.

> **실측:** 네이티브 `<select>` 위의 mousedown 은 ag-grid에 의해 `preventDefault` 되지 않았고(`defaultPrevented === false`),
> 값 선택 시 `node.data.cols[customColId]` 에 코드ID가 기록되며 `onCellValueChanged`(dirty)가 발생함을 확인.

---

## 3. 관련 파일 한눈에

```
frontend/src/
├─ components/Grid.jsx                                  ← 공통 그리드 (CustomUI.Grid 실체, AgGridReact 래핑)
├─ common/CustomUI.js                                   ← CustomUI.Grid 로 export
└─ pages/SampleGrid/
   ├─ index.jsx                                         ← 화면 컨테이너. 상태/핸들러/그리드 배선
   ├─ components/
   │  ├─ CustomGridSection.jsx                          ← <CustomUI.Grid ...> 실제 사용처
   │  ├─ CustomSelectCell.jsx     ★신규                 ← '02' 셀렉트 렌더러 (네이티브 select)
   │  └─ CustomFileButton.jsx                           ← '03' 파일 렌더러 + 컴포넌트 등록 맵
   ├─ constants/
   │  └─ gridColumnDefs.jsx                             ← 동적 columnDefs 빌더 + gridOptions 빌더
   └─ utils/
      └─ customRowModel.js                              ← 행(row) ↔ 서버 매핑, cols/valIds 구조
```

---

## 4. 데이터 모델 — 셀 값이 어디에 저장되나

동적 그리드의 한 행(row)은 다음 구조다 (`utils/customRowModel.js`).

```js
// 행 구조
{
  _rid,        // 로컬 행 식별자 (getRowId 로 사용, 신규/복사 행도 안정 추적)
  rowId,       // 서버 행 PK (신규면 null)
  rowTypCd,    // Row 번호 코드
  rowSeq,
  fixed1, fixed2,
  cols:   { [customColId]: 값(코드ID/텍스트) },  // ← 동적 컬럼 값이 여기 저장됨
  valIds: { [customColId]: valId }              // ← 파일('03') 대상 식별자
}
```

**중요:** 동적 컬럼은 `field` 가 없다. 값이 `data.cols[customColId]` 안에 중첩 저장되므로,
컬럼 정의에서 **`valueGetter`/`valueSetter`** 로 그 중첩 객체를 읽고 쓴다. 셀렉트 렌더러도 이 통로를 그대로 탄다.

---

## 5. 구현 상세 (파일별 전체 코드)

### 5.1 셀렉트 렌더러 — `components/CustomSelectCell.jsx` (신규)

```jsx
import React from 'react';

// 동적 컬럼(colTypCd '02') 공통코드 셀렉트 렌더러.
//
// 설계 의도:
//  - agSelectCellEditor(편집기) 대신 "상시 렌더러"로 네이티브 <select> 를 그린다.
//    → 편집모드 진입(더블클릭/포커스) 없이, 포커스가 없던 상태에서도 단일 클릭으로 즉시 드롭다운이 열린다.
//  - 선택(onChange) 시 node.setDataValue 로 행 데이터(cols[customColId])에 기록한다.
//    → valueSetter 가 호출되고 onCellValueChanged(=onDirty) 가 발생하여 값이 셀에 반영/추적된다.
//  - ag-grid 셀의 mousedown 핸들러가 첫 클릭을 가로채(preventDefault/focus) 드롭다운 오픈을
//    방해하지 못하도록, select 의 mousedown/click 은 stopPropagation 으로 격리한다.
const selectStyle = {
  width: '100%',
  height: '100%',
  border: 'none',
  outline: 'none',
  background: 'transparent',
  padding: '0 4px',
  font: 'inherit',
  color: 'inherit',
  cursor: 'pointer',
  appearance: 'auto'
};

export function CustomSelectCell(params) {
  // editable 은 cellRendererParams 로 주입(편집↔조회 전환 시 셀 refresh 를 유도).
  // 미주입 시 gridOptions.context 로 폴백한다.
  const editable = params.editable ?? params.context?.editable;
  const codes = params.codes || [];
  const value = params.value ?? '';

  // 조회(비편집) 모드: 코드명 텍스트만 표기
  if (!editable) {
    const name = codes.find(code => code.cdId === value)?.cdNm;
    return <span className="custom-select-cell__text">{value ? name ?? value : ''}</span>;
  }

  const handleChange = event => {
    // valueSetter 호출 + onCellValueChanged(onDirty) 발생
    params.node.setDataValue(params.column.getColId(), event.target.value);
  };

  const isolate = event => event.stopPropagation();

  return (
    <select
      className="custom-select-cell"
      style={selectStyle}
      value={value}
      onChange={handleChange}
      onMouseDown={isolate}
      onClick={isolate}
    >
      <option value="">선택</option>
      {codes.map(code => (
        <option key={code.cdId} value={code.cdId}>
          {code.cdNm}
        </option>
      ))}
    </select>
  );
}

export default CustomSelectCell;
```

**렌더러 params 로 무엇이 들어오나** (ag-grid `ICellRendererParams` + 우리가 넣은 값):

| params 필드 | 출처 | 용도 |
| --- | --- | --- |
| `params.value` | 컬럼의 `valueGetter` → `data.cols[customColId]` | `<select value>` 바인딩 (controlled) |
| `params.node` | ag-grid | `setDataValue` 로 값 기록 |
| `params.column` | ag-grid | `getColId()` 로 대상 컬럼 지정 |
| `params.codes` | 컬럼의 `cellRendererParams` | 옵션 목록 `[{cdId, cdNm}]` |
| `params.editable` | 컬럼의 `cellRendererParams` | 편집/조회 분기 |
| `params.context` | `gridOptions.context` | `editable` 폴백 |

**왜 controlled `<select>` 인가:** `value={params.value}` 로 묶었기 때문에, 사용자가 항목을 고르면
`onChange` → `setDataValue` → **ag-grid가 셀을 refresh** → 렌더러가 새 `params.value`(= 방금 저장된 코드ID)로 다시 그려진다.
즉 데이터 모델이 실제로 갱신됐을 때만 select 표시값이 유지된다. (모델이 안 바뀌면 select가 '선택'으로 되돌아가므로, 값 반영 여부를 눈으로 검증 가능.)

### 5.2 동적 컬럼 빌더 — `constants/gridColumnDefs.jsx`

```jsx
import { CUSTOM_GRID_COMPONENTS } from '../components/CustomFileButton.jsx';

// 동적 그리드 컬럼 정의.
// 고정1/고정2 는 좌측 고정, 이후 상위 선택값별 동적 컬럼을 colTypCd 에 따라 렌더링한다.
//  - '01' 텍스트 입력 / '02' 공통코드 셀렉트 / '03' 파일 첨부 버튼
export function buildCustomColumnDefs(customColumns = [], getCodesByGroup, editable = true) {
  const staticColumns = [
    { headerName: '구분', colId: '__row', pinned: 'left', width: 92, editable: false,
      sortable: false, filter: false, cellClass: 'custom-grid__row',
      valueGetter: p => `Row${p.data?.rowTypCd || String((p.node?.rowIndex ?? 0) + 1).padStart(2, '0')}` },
    { headerName: '고정1', field: 'fixed1', pinned: 'left', width: 140, editable, sortable: false, filter: false },
    { headerName: '고정2', field: 'fixed2', pinned: 'left', width: 140, editable, sortable: false, filter: false }
  ];

  const dynamicColumns = customColumns.map(column => {
    const baseColumn = {
      headerName: column.colNm,
      colId: `col_${column.customColId}`,
      width: 170,
      sortable: false,
      filter: false,
      // 값은 data.cols[customColId] 중첩 객체에 저장 → getter/setter 로 통로 연결
      valueGetter: p => p.data?.cols?.[column.customColId] ?? '',
      valueSetter: p => {
        if (!p.data.cols) p.data.cols = {};
        p.data.cols[column.customColId] = p.newValue;
        return true;
      }
    };

    // '03' 파일 버튼 렌더러
    if (column.colTypCd === '03') {
      return { ...baseColumn, width: 210, editable: false,
        cellRenderer: 'customFileButtonRenderer', cellRendererParams: { customCol: column } };
    }

    // '02' 공통코드 셀렉트 렌더러 (이 문서의 핵심)
    if (column.colTypCd === '02' && column.applyCommonCd) {
      const codes = getCodesByGroup?.(column.applyCommonCd) || [];
      const codeNameById = Object.fromEntries(codes.map(code => [code.cdId, code.cdNm]));

      // 편집기(agSelectCellEditor) 대신 상시 렌더러(네이티브 select)를 사용한다.
      // → 포커스가 없던 상태에서도 단일 클릭으로 드롭다운이 곧바로 열리고, 선택 즉시 셀에 반영된다.
      // editable:false 로 두어 더블클릭/타이핑에 의한 기본 편집 진입을 차단(렌더러가 상호작용을 전담).
      return {
        ...baseColumn,
        editable: false,
        cellRenderer: 'customSelectRenderer',
        // editable 을 cellRendererParams 로 전달하면 편집↔조회 전환 시 colDef 가 바뀌어
        // ag-grid 가 해당 셀을 refresh → 렌더러가 최신 편집상태를 반영한다.
        cellRendererParams: { codes, editable },
        valueFormatter: p => (p.value ? (codeNameById[p.value] ?? p.value) : '')
      };
    }

    // '01' 텍스트
    return { ...baseColumn, editable };
  });

  return [...staticColumns, ...dynamicColumns];
}

// 동적 그리드 옵션 팩토리. 편집 모드/파일 핸들러를 context 로 주입한다.
export function buildCustomGridOptions({ editable, onAttachFile, onDownloadFile, onDirty }) {
  return {
    components: CUSTOM_GRID_COMPONENTS,              // 렌더러 등록 맵
    context: { editable, onAttachFile, onDownloadFile },
    defaultColDef: { filter: false, sortable: false },
    getRowId: params => String(params.data._rid),   // 로컬 _rid 로 행 식별
    onCellValueChanged: onDirty,                     // setDataValue 시 dirty 표시
    rowSelection: { mode: 'singleRow', checkboxes: false, enableClickSelection: true },
    singleClickEdit: false,                          // '01' 텍스트 셀에만 영향 (셀렉트는 렌더러라 무관)
    stopEditingWhenCellsLoseFocus: true
  };
}
```

**포인트**
- `editable: false` (셀렉트 컬럼) → 더블클릭/타이핑에 의한 기본 편집 진입이 없어 렌더러가 상호작용을 100% 전담.
- `cellRendererParams: { codes, editable }` → 옵션 목록과 편집상태를 렌더러에 직접 주입. `editable` 을 여기 넣는 이유는 §6.2 참고.
- `onCellValueChanged: onDirty` → 렌더러의 `setDataValue` 가 이 이벤트를 발생시켜 "변경됨" 상태로 이어진다.

### 5.3 컴포넌트 등록 맵 — `components/CustomFileButton.jsx`

ag-grid는 `cellRenderer: '문자열키'` 로 렌더러를 참조한다. 그 키→컴포넌트 매핑이 `components` 옵션이다.

```jsx
import { CustomSelectCell } from './CustomSelectCell.jsx';
// ... (CustomFileButton 컴포넌트 정의)

// ag-grid 컴포넌트 등록 맵 (gridOptions.components 로 전달)
export const CUSTOM_GRID_COMPONENTS = {
  customFileButtonRenderer: CustomFileButton,
  customSelectRenderer: CustomSelectCell   // ★ '02' 셀렉트 렌더러 등록
};
```

이 맵이 `buildCustomGridOptions` 의 `components` 로 넘어가고, 컬럼 정의의 `cellRenderer: 'customSelectRenderer'` 가 이 키를 찾는다.

### 5.4 공통 그리드 — `components/Grid.jsx` (= `CustomUI.Grid`)

`CustomUI.Grid` 는 `AgGridReact` 를 얇게 래핑한 공통 컴포넌트다. 동적 그리드가 넘긴 `gridOptions` 는
여기서 **분해되어 AgGridReact 로 전달**된다. 셀렉트 셀과 관련해 알아야 할 부분만 발췌:

```jsx
const Grid = forwardRef(function Grid({ list, columnDefs, gridOptions = {}, ... }, ref) {
  // gridOptions 에서 일부를 꺼내고 나머지(components, context, onCellValueChanged,
  // singleClickEdit, stopEditingWhenCellsLoseFocus, onGridReady 등)는 그대로 스프레드
  const { defaultColDef, onGridReady, getRowId, rowSelection, ...restGridOptions } = gridOptions;

  const handleGridReady = event => {
    onGridReady?.(event);
    event.api.sizeColumnsToFit();
    if (!isLoading) event.api.setGridOption?.('loading', false);
  };

  return (
    <div className="common-grid__body ag-theme-quartz">
      <AgGridReact
        ref={ref}                         // ← 화면에서 gridRef 로 api 접근 (refreshCells 등)
        {...restGridOptions}              // ← components / context / onCellValueChanged / singleClickEdit ...
        rowData={safeList}
        columnDefs={safeColumnDefs}
        defaultColDef={{ sortable: true, resizable: true, filter: true, minWidth: 90, ...defaultColDef }}
        rowSelection={rowSelection ?? { mode: 'singleRow', checkboxes: false, enableClickSelection: true }}
        theme="legacy"                    // ← quartz CSS 를 직접 import 해서 쓰는 legacy 테마 모드
        getRowId={getRowId ?? (p => String(p.data.id))}
        onGridReady={handleGridReady}
      />
    </div>
  );
});
```

주의할 점 두 가지:
- **`ref` 가 그대로 `AgGridReact` 로 전달**되므로, 화면 컨테이너의 `gridRef.current.api` 로 ag-grid API에 접근할 수 있다. (편집전환 시 `refreshCells` 에 사용)
- `restGridOptions` 스프레드 덕분에 `components`, `context`, `onCellValueChanged`, `singleClickEdit`, `stopEditingWhenCellsLoseFocus`, `onGridReady` 가 **손실 없이** AgGridReact 로 넘어간다. (구조분해로 명시적으로 꺼낸 `defaultColDef/onGridReady/getRowId/rowSelection` 만 별도 처리)

### 5.5 `<CustomUI.Grid>` 사용처 — `components/CustomGridSection.jsx`

이 화면에서 그리드를 실제로 그리는 곳. 순수 프레젠테이션 컴포넌트다.

```jsx
export function CustomGridSection({ gridRef, rows, columnDefs, gridOptions, editable = true,
                                    onCopy, onAdd, onDelete, showHint }) {
  return (
    <div className="sample-page__grid">
      <div className="sample-page__grid-head">
        <Text strong>동적 정보</Text>
        <Space size={8}>
          <Button icon={<CopyOutlined />}   disabled={!editable} onClick={onCopy}>복사</Button>
          <Button icon={<PlusOutlined />}   disabled={!editable} onClick={onAdd}>추가</Button>
          <Button icon={<DeleteOutlined />} danger disabled={!editable} onClick={onDelete}>삭제</Button>
        </Space>
      </div>

      <CustomUI.Grid
        className="antd-table"
        ref={gridRef}                 // ← index.jsx 의 gridRef
        list={rows}                   // ← customRows 상태
        columnDefs={columnDefs}       // ← buildCustomColumnDefs 결과
        gridOptions={gridOptions}     // ← buildCustomGridOptions 결과
        loading={false}
        totalCount={rows.length}
        showPagination={false}
      />

      {showHint && <Text type="secondary">상위 항목을 선택하면 동적 컬럼이 표시됩니다.</Text>}
    </div>
  );
}
```

### 5.6 화면 배선 — `SampleGrid/index.jsx` (핵심 부분만)

```jsx
const gridRef = useRef(null);
const getCodesByGroup = useCodeStore(state => state.getCodesByGroup);
const [editMode, setEditMode] = useState(!initialRecordId);
const [customRows, setCustomRows] = useState([]);
const { data: customColumns = [] } = useCustomColumnsQuery(parentId); // 상위 선택값별 동적 컬럼

// 동적 columnDefs: customColumns / editMode / 공통코드가 바뀌면 재생성
const columnDefs = useMemo(
  () => buildCustomColumnDefs(customColumns, group => getCodesByGroup(group), editMode),
  [customColumns, editMode, getCodesByGroup]
);

// gridOptions: 편집모드/파일핸들러/dirty 콜백 주입
const gridOptions = useMemo(
  () => buildCustomGridOptions({
    editable: editMode,
    onAttachFile: handleAttachFile,
    onDownloadFile: handleDownloadFile,
    onDirty: () => setDirty(true)
  }),
  [editMode, handleAttachFile, handleDownloadFile]
);

// ★ 편집↔조회 전환 시 동적 그리드 셀을 강제 refresh.
//   '02' 셀렉트 컬럼의 colDef 는 편집상태와 무관하게 동일하여 ag-grid 가 자동 refresh 하지 않으므로,
//   렌더러(CustomSelectCell)가 최신 editable 을 반영하도록 여기서 명시적으로 다시 그린다.
useEffect(() => {
  gridRef.current?.api?.refreshCells({ force: true });
}, [editMode]);

// ... JSX
<CustomGridSection
  gridRef={gridRef}
  rows={customRows}
  columnDefs={columnDefs}
  gridOptions={gridOptions}
  editable={editMode}
  onCopy={handleCopyRow}
  onAdd={handleAddRow}
  onDelete={handleDeleteRow}
  showHint={!parentId}
/>
```

**저장 시 값 흐름:** 저장 직전 `gridRef.current?.api?.stopEditing()` 후, `customRows`(각 행의 `cols`)를
`mapRowsToValueList(rows, columns)` 로 payload 의 `rowList[].values[]` 로 변환한다.
셀렉트로 고른 코드ID는 `row.cols[customColId]` 에 들어 있으므로 그대로 서버로 전송된다.

---

## 6. 전체 코드 흐름 (시퀀스)

### 6.1 셀렉트 셀을 처음 클릭 → 선택 → 셀 반영

```
[사용자] '02' 셀을 한 번 클릭 (셀에 포커스 없던 상태)
   │
   │  셀 안에는 CustomSelectCell 이 이미 <select> 를 렌더해 둔 상태 (편집모드 진입 불필요)
   ▼
[<select> onMouseDown] e.stopPropagation()
   │   → ag-grid 셀의 mousedown 핸들러가 실행되지 않음(포커스 탈취/preventDefault 차단)
   │   → preventDefault 는 호출 안 함 → 브라우저 기본동작(드롭다운 열기)은 그대로 수행
   ▼
[OS] 네이티브 드롭다운 즉시 오픈  ← 요구사항 1 충족
   │
   ▼
[사용자] 항목 선택
   ▼
[<select> onChange] params.node.setDataValue(colId, event.target.value)
   │
   ├─▶ 컬럼 valueSetter 실행 → data.cols[customColId] = 선택한 코드ID   ← 데이터 모델 반영
   │
   ├─▶ ag-grid 'cellValueChanged' 이벤트 → gridOptions.onCellValueChanged = onDirty → setDirty(true)
   │
   └─▶ ag-grid 셀 refresh → CustomSelectCell 재렌더 (params.value = 방금 저장한 코드ID)
          → <select value> 가 그 값으로 유지 (표시상 코드명 노출)          ← 요구사항 2 충족
```

### 6.2 편집 ↔ 조회 모드 전환

```
[사용자] 수정/저장 → setEditMode(true/false)
   │
   ├─▶ columnDefs 재생성 (buildCustomColumnDefs(..., editMode))
   │       → '02' 컬럼 cellRendererParams.editable 값이 바뀜
   │       (단, ag-grid 는 colDef 변경만으로 기존 셀을 자동 refresh 하지 않음 — v35 실측)
   │
   ├─▶ gridOptions 재생성 (context.editable 갱신)
   │
   └─▶ useEffect([editMode]) → gridRef.current.api.refreshCells({ force: true })
           → 모든 셀 강제 재렌더
           → CustomSelectCell 이 최신 editable 로 다시 그림
                - editable=true  → <select> 노출(선택 가능)
                - editable=false → 코드명 텍스트만 노출
```

> **핵심:** `refreshCells({ force: true })` 가 없으면, 편집버튼을 눌러도 셀렉트 셀이 **직전 상태 그대로 멈춰** 있는다.
> (조회→편집인데 텍스트만 보이거나, 편집→조회인데 select가 남아 있음.) colDef 변경만으로는 부족하다는 것이 v35 실측 결과.

---

## 7. "왜 이 조각이 필요한가" 요약 (제거하면 무엇이 깨지나)

| 조각 | 목적 | 제거 시 증상 |
| --- | --- | --- |
| 렌더러 방식(`cellRenderer`) + 네이티브 `<select>` | 편집모드 없이 상시 상호작용 | 편집기 방식이면 한 번 클릭에 드롭다운이 안 열림 |
| `editable: false` (셀렉트 컬럼) | 기본 편집 진입 차단, 렌더러 전담 | 더블클릭 시 기본 편집기가 렌더러 위에 겹쳐 충돌 |
| `onMouseDown` `stopPropagation` (preventDefault 없음) | ag-grid의 첫 클릭 가로채기 차단 + 기본 열기 유지 | 브라우저/타이밍에 따라 첫 클릭에 안 열리고 두 번 눌러야 함 |
| `node.setDataValue(colId, value)` | valueSetter 경유 값 기록 + 변경 이벤트 | 선택해도 `cols[customColId]` 미갱신 → **셀 비어 있음** |
| controlled `value={params.value}` | 모델↔표시 동기화 | 모델 반영 실패가 눈에 안 보이거나, 표시가 튐 |
| `onCellValueChanged: onDirty` | 변경 추적(저장 유도) | 값은 바뀌는데 dirty 안 잡혀 저장 유도가 안 됨 |
| `cellRendererParams: { editable }` + `refreshCells({force:true})` | 편집전환 시 렌더러 상태 갱신 | 편집버튼 눌러도 셀렉트 상태가 안 바뀜 |

---

## 8. 다른 화면에서 재사용하는 법

1. 컬럼 정의에 아래를 지정한다.
   ```js
   {
     colId: 'col_XXX',
     editable: false,
     cellRenderer: 'customSelectRenderer',
     cellRendererParams: { codes /* [{cdId,cdNm}] */, editable /* boolean */ },
     valueGetter: p => p.data?.cols?.[id] ?? '',
     valueSetter: p => { (p.data.cols ??= {})[id] = p.newValue; return true; }
   }
   ```
2. `gridOptions.components` 에 `customSelectRenderer` 가 등록돼 있어야 한다(`CUSTOM_GRID_COMPONENTS`).
3. `gridOptions.onCellValueChanged` 로 dirty/변경 추적을 연결한다.
4. 편집↔조회를 런타임에 토글한다면, 토글 시 `api.refreshCells({ force: true })` 를 호출한다.
5. 값은 `field` 가 아니라 `data.cols[id]` 중첩 구조에 저장하되, `valueGetter/valueSetter` 로 통로만 맞추면 렌더러는 그대로 동작한다.

---

## 9. 검증 방법 (독립 하네스)

백엔드/DB 없이도 이 셀 동작만 격리 검증하려면, 실제 빌더/CustomUI.Grid 를 그대로 쓰는 하네스를 임시로 띄운다.
(개발 검증용이며 저장소에는 커밋하지 않는다.)

- `frontend/sample-harness.html` — `<div id="root">` + `<script type="module" src="/src/_harness/sampleHarness.jsx">`
- `frontend/src/_harness/sampleHarness.jsx` — 실제 `buildCustomColumnDefs`/`buildCustomGridOptions`/`CustomUI.Grid` 에
  목(mock) `customColumns` 와 `getCodesByGroup` 를 주입해 렌더. `onGridReady` 에서 `window.__gridApi = event.api` 로 API를 노출해
  데이터 모델을 직접 읽어 검증한다.

`pnpm dev` 후 `http://localhost:5173/sample-harness.html` 접속. 확인 포인트:

1. `[col-id="col_XXX"] select.custom-select-cell` 이 편집모드 진입 없이 셀에 존재.
2. select 위 `mousedown` 의 `defaultPrevented === false` (드롭다운 오픈 보장).
3. 값 선택 후 `__gridApi.forEachNode(n => n.data.cols[id])` 가 선택 코드ID를 가짐 (셀 반영).
4. `editable` 토글 → `refreshCells` 로 select↔텍스트 전환.

> 본 구현은 위 하네스로 ag-grid **v35.2.1 / React 18.2 / antd 5.21** 환경에서 1~4를 모두 통과 확인했다.

---

## 10. 함정 노트 (다음 사람을 위해)

- **`agSelectCellEditor` 로는 "한 번 클릭에 드롭다운 오픈"이 안 된다.** 편집기는 자동 오픈 옵션이 없다. 렌더러로 가라.
- **antd `<Select>` 를 셀에 직접 넣지 마라.** 포털 드롭다운 + ag-grid 클릭 처리 충돌로 "두 번 클릭" 또는 "값 유실"이 생긴다. 네이티브 `<select>` 가 가장 견고하다.
- **`stopPropagation` 은 하되 `preventDefault` 는 하지 마라.** preventDefault 를 부르면 네이티브 select 의 "열기" 기본동작까지 막혀 버린다.
- **`setValue` 대신 `node.setDataValue(colId, value)` 를 명시적으로 써서** valueSetter 경유 + `cellValueChanged` 발생을 확실히 한다.
- **colDef 만 바꾸면 ag-grid v35는 기존 셀을 다시 그리지 않는다.** 편집전환처럼 런타임 상태가 바뀌면 `refreshCells({ force: true })` 로 강제 refresh.
