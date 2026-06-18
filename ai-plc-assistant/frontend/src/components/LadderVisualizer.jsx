import { useEffect, useRef } from 'react'

const CHAR_W = 8.4   // monospace char width (px @ 11px font)
const CHAR_H = 18    // line height
const PAD = 12       // padding around the diagram
const RAIL_W = 4     // power rail width

/**
 * Parse ASCII ladder code into a character grid for SVG rendering.
 * Returns { lines: string[], grid: string[][] }
 */
function parseCode(code) {
  const lines = code.split('\n')
  const maxLen = Math.max(...lines.map(l => l.length), 1)
  const grid = lines.map(line => [...line.padEnd(maxLen)])
  return { lines, grid, width: maxLen, height: lines.length }
}

/**
 * Detect elements at a grid position.
 * Returns { type, colSpan } or null.
 */
function detectElement(grid, row, col) {
  const c = grid[row]?.[col]
  if (!c) return null

  // Normally-open contact: | |
  if (c === '|' && grid[row]?.[col + 1] === ' ' && grid[row]?.[col + 2] === '|') {
    return { type: 'normally_open', colSpan: 3, label: '' }
  }
  // Normally-closed contact: |/|
  if (c === '|' && grid[row]?.[col + 1] === '/' && grid[row]?.[col + 2] === '|') {
    return { type: 'normally_closed', colSpan: 3, label: '' }
  }
  // Coil: ( )
  if (c === '(' && grid[row]?.[col + 1] === ' ' && grid[row]?.[col + 2] === ')') {
    return { type: 'coil', colSpan: 3 }
  }
  // Coil set: (S)
  if (c === '(' && grid[row]?.[col + 1] === 'S' && grid[row]?.[col + 2] === ')') {
    return { type: 'coil_set', colSpan: 3 }
  }
  // Coil reset: (R)
  if (c === '(' && grid[row]?.[col + 1] === 'R' && grid[row]?.[col + 2] === ')') {
    return { type: 'coil_reset', colSpan: 3 }
  }
  // Timer/CTU coil: ( TON )
  if (c === '(' && grid[row]?.[col + 2] && grid[row]?.[col + 2] !== ')') {
    const endParen = grid[row].indexOf(')', col + 1)
    if (endParen > col + 1) {
      return { type: 'coil', colSpan: endParen - col + 1 }
    }
  }
  // Junction: +
  if (c === '+') {
    return { type: 'junction', colSpan: 1 }
  }
  // Horizontal wire: -, =
  if (c === '-' || c === '=') {
    // Skip if part of a contact or coil already matched
    if (col > 0 && (grid[row]?.[col - 1] === '|' || grid[row]?.[col - 1] === '(')) return null
    return { type: 'wire_h', colSpan: 1 }
  }
  // Vertical wire: |
  if (c === '|') {
    // Skip if part of a contact
    if (grid[row]?.[col + 1] === ' ' && grid[row]?.[col + 2] === '|') return null  // normally_open start
    if (grid[row]?.[col + 1] === '/' && grid[row]?.[col + 2] === '|') return null    // normally_closed start
    if (grid[row]?.[col - 1] === ' ' && grid[row]?.[col - 2] === '|') return null     // normally_open end
    if (grid[row]?.[col - 1] === '/' && grid[row]?.[col - 2] === '|') return null     // normally_closed end
    if (grid[row]?.[col - 1] === ')' || grid[row]?.[col + 1] === '(') return null    // near coils
    return { type: 'wire_v', colSpan: 1 }
  }

  return null
}

/**
 * Element coloring
 */
const ELEMENT_COLORS = {
  normally_open: { fill: '#4fc3f7', stroke: '#29b6f6', text: '#e0e0e0' },
  normally_closed: { fill: '#ffb74d', stroke: '#ffa726', text: '#e0e0e0' },
  coil: { fill: '#81c784', stroke: '#66bb6a', text: '#1a1a2e' },
  coil_set: { fill: '#4db6ac', stroke: '#26a69a', text: '#1a1a2e' },
  coil_reset: { fill: '#ef5350', stroke: '#e53935', text: '#1a1a2e' },
  wire_h: { fill: '#616161', stroke: '#757575' },
  wire_v: { fill: '#616161', stroke: '#757575' },
  junction: { fill: '#bdbdbd', stroke: '#9e9e9e' },
}

function svgX(col) { return PAD + RAIL_W + 4 + col * CHAR_W }
function svgY(row) { return PAD + 8 + row * CHAR_H }

function renderElement(ctx, type, row, col, colSpan) {
  const x = svgX(col)
  const y = svgY(row)
  const w = colSpan * CHAR_W
  const colors = ELEMENT_COLORS[type] || ELEMENT_COLORS.wire_h

  switch (type) {
    case 'normally_open': {
      const cx = x + w / 2
      const cy = y
      const size = 7
      return (
        <g key={`no-${row}-${col}`}>
          {/* Left wire */}
          <line x1={x} y1={cy} x2={cx - size} y2={cy} stroke={colors.stroke} strokeWidth={1.5} />
          {/* Contact symbol: open switch */}
          <line x1={cx - size} y1={cy} x2={cx} y2={cy - size} stroke={colors.stroke} strokeWidth={1.5} />
          <line x1={cx} y1={cy - size} x2={cx + size} y2={cy} stroke={colors.stroke} strokeWidth={1.5} />
          {/* Right wire */}
          <line x1={cx + size} y1={cy} x2={x + w} y2={cy} stroke={colors.stroke} strokeWidth={1.5} />
        </g>
      )
    }
    case 'normally_closed': {
      const cx = x + w / 2
      const cy = y
      const size = 7
      return (
        <g key={`nc-${row}-${col}`}>
          <line x1={x} y1={cy} x2={cx - size} y2={cy} stroke={colors.stroke} strokeWidth={1.5} />
          {/* Contact symbol: closed switch */}
          <line x1={cx - size} y1={cy} x2={cx + size} y2={cy} stroke={colors.stroke} strokeWidth={1.5} />
          {/* Diagonal slash */}
          <line x1={cx - size} y1={cy - size + 2} x2={cx + size} y2={cy + size - 2} stroke={colors.stroke} strokeWidth={1.5} />
          <line x1={cx + size} y1={cy} x2={x + w} y2={cy} stroke={colors.stroke} strokeWidth={1.5} />
        </g>
      )
    }
    case 'coil':
    case 'coil_set':
    case 'coil_reset': {
      const cx = x + w / 2
      const cy = y
      const r = 6
      const label = type === 'coil_set' ? 'S' : type === 'coil_reset' ? 'R' : ''
      return (
        <g key={`coil-${row}-${col}`}>
          <line x1={x} y1={cy} x2={cx - r} y2={cy} stroke={colors.stroke} strokeWidth={1.5} />
          <ellipse cx={cx} cy={cy} rx={r} ry={r * 0.65} fill="none" stroke={colors.stroke} strokeWidth={1.5} />
          {label && (
            <text x={cx} y={cy + 3.5} textAnchor="middle" fill={colors.fill} fontSize={8} fontWeight="bold" fontFamily="monospace">
              {label}
            </text>
          )}
          <line x1={cx + r} y1={cy} x2={x + w} y2={cy} stroke={colors.stroke} strokeWidth={1.5} />
        </g>
      )
    }
    case 'junction': {
      return <circle key={`j-${row}-${col}`} cx={x + CHAR_W / 2} cy={y} r={2} fill={colors.fill} />
    }
    case 'wire_h': {
      return null // rendered as background lines
    }
    case 'wire_v': {
      return null // rendered as background lines
    }
    default:
      return null
  }
}

/**
 * Background: draw all wires as a single path for each line
 */
function renderWires(grid) {
  const elements = []
  const cols = grid[0]?.length || 0

  // Horizontal wires per row
  grid.forEach((row, rowIdx) => {
    let hStart = -1
    for (let c = 0; c <= cols; c++) {
      const ch = row[c]
      if (ch === '-' || ch === '=') {
        if (hStart === -1) hStart = c
      } else {
        if (hStart !== -1) {
          // Check if this segment is inside a contact/coil and skip those pixels
          const x1 = svgX(hStart)
          const x2 = svgX(c)
          const y = svgY(rowIdx)
          if (x2 - x1 > 2) {
            elements.push(
              <line key={`hw-${rowIdx}-${hStart}`}
                x1={x1} y1={y} x2={x2} y2={y}
                stroke="#616161" strokeWidth={1.2} />
            )
          }
          hStart = -1
        }
      }
    }
  })

  // Vertical wires per column
  for (let c = 0; c < cols; c++) {
    let vStart = -1
    for (let r = 0; r <= grid.length; r++) {
      const ch = grid[r]?.[c]
      if (ch === '|') {
        if (vStart === -1) vStart = r
      } else {
        if (vStart !== -1) {
          const x = svgX(c) + CHAR_W / 2
          const y1 = svgY(vStart)
          const y2 = svgY(r)
          if (y2 - y1 > 2) {
            elements.push(
              <line key={`vw-${c}-${vStart}`}
                x1={x} y1={y1} x2={x} y2={y2}
                stroke="#616161" strokeWidth={1.2} />
            )
          }
          vStart = -1
        }
      }
    }
  }

  return elements
}

export default function LadderVisualizer({ code, networkTitle }) {
  const { lines, grid, width, height } = parseCode(code || '')
  const svgWidth = PAD * 2 + RAIL_W * 2 + 8 + width * CHAR_W + 20
  const svgHeight = Math.max(PAD * 2 + height * CHAR_H + 10, 60)

  // Collect SVG elements: first wires (background), then devices (foreground)
  const wireElements = renderWires(grid)
  const deviceElements = []

  // Detect and render devices
  let visited = new Set()
  for (let r = 0; r < grid.length; r++) {
    for (let c = 0; c < grid[r].length; c++) {
      const key = `${r}-${c}`
      if (visited.has(key)) continue

      const el = detectElement(grid, r, c)
      if (el) {
        // Mark visited columns
        for (let i = 0; i < el.colSpan; i++) visited.add(`${r}-${c + i}`)

        const rendered = renderElement(el, el.type, r, c, el.colSpan)
        if (rendered) deviceElements.push(rendered)
      }
    }
  }

  // Render text labels (variable names above elements)
  const textElements = []
  if (lines.length > 1) {
    // Usually the first line(s) contain labels
    for (let r = 0; r < lines.length; r++) {
      const line = lines[r]
      // Match variable names (camelCase or Hungarian notation patterns like bStart, qMotor)
      const varPattern = /[a-zA-Z][a-zA-Z0-9_.]*/g
      let m
      while ((m = varPattern.exec(line)) !== null) {
        const col = m.index
        const name = m[0]
        // Only render labels that look like meaningful identifiers (not just wire chars)
        if (name.length >= 2 && !/^[-+=|/()]+$/.test(name)) {
          textElements.push(
            <text key={`label-${r}-${col}`}
              x={svgX(col) + (m[0].length * CHAR_W) / 2}
              y={svgY(r) - 4}
              textAnchor="middle"
              fill="#9e9e9e"
              fontSize={9}
              fontFamily="monospace"
              fontWeight={500}
            >
              {name}
            </text>
          )
        }
      }
    }
  }

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        className="w-full"
        style={{ minWidth: svgWidth, maxWidth: '100%' }}
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Background */}
        <rect x={0} y={0} width={svgWidth} height={svgHeight} fill="#1a1a2e" rx={4} />

        {/* Power rails */}
        {/* Left rail */}
        <line x1={PAD + RAIL_W / 2} y1={0} x2={PAD + RAIL_W / 2} y2={svgHeight}
          stroke="#4a4a6a" strokeWidth={RAIL_W} />
        {/* Right rail */}
        <line x1={svgWidth - PAD - RAIL_W / 2} y1={0} x2={svgWidth - PAD - RAIL_W / 2} y2={svgHeight}
          stroke="#4a4a6a" strokeWidth={RAIL_W} />

        {/* Network title */}
        {networkTitle && (
          <text x={PAD + RAIL_W + 8} y={PAD - 2}
            fill="#80cbc4" fontSize={10} fontFamily="monospace" fontWeight={600}>
            {networkTitle}
          </text>
        )}

        {/* Wires (background layer) */}
        {wireElements}

        {/* Devices (foreground layer) */}
        {deviceElements}

        {/* Text labels */}
        {textElements}

        {/* Empty state */}
        {!code && (
          <text x={svgWidth / 2} y={svgHeight / 2 + 4}
            textAnchor="middle" fill="#616161" fontSize={11} fontFamily="sans-serif">
            (empty)
          </text>
        )}
      </svg>
    </div>
  )
}
