# SVGRendererV2 Design Document — LAD AST V1

## Architecture

```
LadderSpec JSON
       │
       ▼
  lad_ast.py (LadderBlock.from_dict)
       │
       ▼
  LayoutEngine ───→ RenderTree (positioned data objects)
       │
       ▼
  SVGRendererV2 ──→ SVG string
```

## Three-Layer Separation

### 1. AST Layer (`lad_ast.py`)

Already exists. Pure data model — `LadderBlock` → `LadderNetwork` → `LadderRung` → `LadderElement` subclasses.

No rendering concerns. No pixel coordinates.

### 2. Layout Layer (`layout_engine.py` + `render_tree.py`)

**New.** Converts AST → positioned RenderTree.

Responsibilities:
- Column assignment: each non-Branch element gets a column index
- Branch range computation: Branch spans start_col → end_col
- Row assignment: main path = row 0, branch paths = row 1+
- Pixel coordinate computation: col/row → x/y center
- Canvas sizing: width/height from element count + branch structure
- Wire geometry: horizontal spans + vertical branch connections

**Must NOT produce SVG.** Output is pure data (RenderTree dataclasses).

### 3. Render Layer (`svg_renderer_v2.py`)

**New.** Consumes RenderTree → produces SVG string.

Responsibilities:
- Power rails (left/right)
- Network title + rung number
- Wires (horizontal + branch vertical)
- Elements (contacts, coils, boxes)
- Labels (symbol names, addresses)

**Must NOT compute coordinates.** Reads precomputed x/y from RenderTree.

## Coordinate System

### Grid

| Metric | Value |
|--------|-------|
| Column width | 56 px |
| Row height (base) | 52 px |
| Branch row extra gap | 18 px |
| Left rail margin | 80 px |
| Right rail margin | 40 px |
| Top margin | 70 px |
| Network gap | 12 px |

### Element Column Assignment

- Non-Branch elements (Contact, Coil, Timer, Counter, etc.) each occupy one column
- Branch elements partition into:
  - `branch_start_col`: column index of the split point
  - `end_col`: `start_col + max(len(path) for path in branch.paths)`
  - Elements after the Branch continue from `end_col`

### Pixel Formulas

```
x_center(col)    = LEFT_RAIL_MARGIN + col * COLUMN_WIDTH + COLUMN_WIDTH / 2
x_left(col)      = LEFT_RAIL_MARGIN + col * COLUMN_WIDTH
x_right(col)     = LEFT_RAIL_MARGIN + (col + 1) * COLUMN_WIDTH
y_center(row)    = TOP_MARGIN + (row == 0 ? 0 : BRANCH_ROW_GAP) + row * ROW_HEIGHT
canvas_width     = LEFT_RAIL_MARGIN + total_columns * COLUMN_WIDTH + RIGHT_RAIL_MARGIN
canvas_height    = TOP_MARGIN + total_rows * ROW_HEIGHT + branch_count * BRANCH_ROW_GAP + BOTTOM_MARGIN
```

### Branch Drawing

```
Main row:   ───[elem a]──┬──[elem c]──[elem d]──[coil]──
                          │
Branch row:          [elem b]
                          │
Main row cont:     ───────┘
```

- Vertical split line at `branch_start_col` from main row y to branch row y
- Vertical join line at `branch_end_col` back from branch row y to main row y
- Branch row's horizontal wire connects split → join within the branch's column range

## RenderTree Data Model

### `RenderElement`
| Field | Type | Description |
|-------|------|-------------|
| col | int | 0-based column |
| row | int | 0=main, 1+=branch |
| x_center | float | Pixel x center |
| y_center | float | Pixel y center |
| elem_type | str | `contact_no`, `contact_nc`, `coil`, `coil_set`, `coil_reset`, `timer`, `counter`, `comparator`, `math`, `move`, `box` |
| symbol_name | str | Operand name for label |
| address | str | Physical address for sub-label |
| extra | dict | Type-specific data (preset, box_type, inputs, outputs) |

### `RenderBranch`
| Field | Type | Description |
|-------|------|-------------|
| start_col | int | Split column |
| end_col | int | Join column |
| start_x | float | Split pixel x |
| end_x | float | Join pixel x |
| main_row_y | float | Main path y at branch |
| branch_rows | list[int] | Row indices of branch paths |

## Future Extensions (not implemented now)

- **Multi-layer Branch**: Branch inside Branch path (recursive LayoutEngine)
- **Online Editor**: RenderTree → hit-testing → drag-to-move
- **TIA XML Export**: AST → SimaticML XML (via CartGen or direct)
- **SCL Export**: AST → SCL source (structured traversal, not regex)

## TIA Portal Style Reference

- Power rails: thick vertical lines on left and right
- Contacts: `| |` for NO, `|/|` for NC, with symbol name above and address below
- Coils: `( )` ellipse, symbol name centered
- Branches: vertical connectors with T-junctions at split/join points
- Rung numbering: circle badge on left rail
- Colors: dark rails, gray wires, colored elements on dark background mode

## Non-Goals (V1)

- Nested Branch (multi-level) — raise `NotImplementedError`
- Animating power flow (green/red states)
- Drag-and-drop editing
- Export to TIA XML / SCL
