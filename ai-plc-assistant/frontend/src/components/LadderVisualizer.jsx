/**
 * LadderVisualizer V2 — 从结构化 LadderModel 渲染梯形图
 *
 * 输入: networks (从后端 structured.networks 取得)
 *   network.rungs[].elements[] — Contact/Coil/Timer/Counter/Branch 等
 *
 * 不解析 ASCII。所有数据由后端 ascii_parser.py 解析后传入。
 */

const COLORS = {
  contact_no:  { border: '#4fc3f7', bg: 'rgba(79,195,247,0.08)', text: '#4fc3f7' },
  contact_nc:  { border: '#ffb74d', bg: 'rgba(255,183,77,0.08)', text: '#ffb74d' },
  coil:        { border: '#81c784', bg: 'rgba(129,199,132,0.10)', text: '#81c784' },
  coil_set:    { border: '#4db6ac', bg: 'rgba(77,182,172,0.10)', text: '#4db6ac' },
  coil_reset:  { border: '#ef5350', bg: 'rgba(239,83,80,0.10)',  text: '#ef5350' },
  timer:       { border: '#ce93d8', bg: 'rgba(206,147,216,0.08)', text: '#ce93d8' },
  counter:     { border: '#ce93d8', bg: 'rgba(206,147,216,0.08)', text: '#ce93d8' },
  move:        { border: '#ffd54f', bg: 'rgba(255,213,79,0.08)', text: '#ffd54f' },
  comparator:  { border: '#ffd54f', bg: 'rgba(255,213,79,0.08)', text: '#ffd54f' },
  block_call:  { border: '#90a4ae', bg: 'rgba(144,164,174,0.08)', text: '#90a4ae' },
  wire:        '#555',
  rail:        '#666',
}

function Wire() {
  return <div style={{ flex: '0 0 20px', borderBottom: `2px solid ${COLORS.wire}`, alignSelf: 'center' }} />
}

function Rail() {
  return <div style={{ width: 3, backgroundColor: COLORS.rail, alignSelf: 'stretch', borderRadius: 1 }} />
}

function ElementBox({ label, sublabel, colors, rounded }) {
  return (
    <div style={{
      display: 'inline-flex', flexDirection: 'column', alignItems: 'center',
      border: `1.5px solid ${colors.border}`, backgroundColor: colors.bg,
      borderRadius: rounded ? 12 : 3,
      padding: '2px 10px', fontSize: 11, fontFamily: 'monospace',
      color: colors.text, whiteSpace: 'nowrap', lineHeight: 1.4,
    }}>
      <span>{label}</span>
      {sublabel && <span style={{ fontSize: 9, opacity: 0.7 }}>{sublabel}</span>}
    </div>
  )
}

function RenderElement({ elem }) {
  if (!elem || !elem.type) return null

  switch (elem.type) {
    case 'contact':
      return (
        <ElementBox
          label={`${elem.normally_closed ? '/ ' : ''}${elem.name}`}
          colors={elem.normally_closed ? COLORS.contact_nc : COLORS.contact_no}
        />
      )
    case 'coil':
      return (
        <ElementBox
          label={`${elem.kind === 'set' ? 'S ' : elem.kind === 'reset' ? 'R ' : ''}${elem.name}`}
          colors={elem.kind === 'set' ? COLORS.coil_set : elem.kind === 'reset' ? COLORS.coil_reset : COLORS.coil}
          rounded
        />
      )
    case 'timer':
      return <ElementBox label={`${elem.timer_type} ${elem.name}`} sublabel={`PT=${elem.pt}`} colors={COLORS.timer} />
    case 'counter':
      return <ElementBox label={`${elem.counter_type} ${elem.name}`} sublabel={`PV=${elem.pv}`} colors={COLORS.counter} />
    case 'move':
      return <ElementBox label={`MOVE`} sublabel={`${elem.source} → ${elem.target}`} colors={COLORS.move} />
    case 'comparator':
      return <ElementBox label={`CMP ${elem.op}`} sublabel={`${elem.a} ${elem.b}`} colors={COLORS.comparator} />
    case 'block_call':
      return <ElementBox label={`${elem.block_type} ${elem.name}`} colors={COLORS.block_call} />
    default:
      return <span style={{ color: '#999', fontSize: 10 }}>[?]</span>
  }
}

function RenderPath({ elements }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
      {elements.map((elem, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
          {i > 0 && <Wire />}
          <RenderElement elem={elem} />
        </div>
      ))}
    </div>
  )
}

function RenderBranch({ branch }) {
  const paths = branch.paths || []
  if (paths.length === 0) return null

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 4,
      borderLeft: `2px solid ${COLORS.wire}`,
      borderRight: `2px solid ${COLORS.wire}`,
      padding: '4px 0', margin: '0 2px',
    }}>
      {paths.map((path, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center',
          paddingLeft: 6, paddingRight: 6,
        }}>
          <RenderPath elements={path} />
        </div>
      ))}
    </div>
  )
}

function RenderRung({ rung }) {
  const elements = rung.elements || []

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 0,
      padding: '6px 8px', minHeight: 36,
    }}>
      <Rail />
      <Wire />
      {elements.map((elem, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
          {i > 0 && <Wire />}
          {elem.type === 'branch'
            ? <RenderBranch branch={elem} />
            : <RenderElement elem={elem} />
          }
        </div>
      ))}
      <Wire />
      <Rail />
    </div>
  )
}

export default function LadderVisualizer({ networks }) {
  if (!networks || networks.length === 0) {
    return <div style={{ color: '#999', fontSize: 12, padding: 16 }}>无梯形图数据</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {networks.map((net, ni) => (
        <div key={ni}>
          <div style={{
            fontSize: 11, color: '#90a4ae', marginBottom: 4,
            fontFamily: 'monospace',
          }}>
            Network {net.number}{net.title ? `: ${net.title}` : ''}
          </div>

          <div style={{
            backgroundColor: '#1a1a2e', borderRadius: 4,
            border: '1px solid #333', overflow: 'hidden',
          }}>
            {(net.rungs || []).map((rung, ri) => (
              <div key={ri} style={{
                borderBottom: ri < (net.rungs?.length || 0) - 1 ? '1px solid #2a2a3e' : 'none',
              }}>
                <RenderRung rung={rung} />
              </div>
            ))}

            {!net.rungs?.length && net.code && (
              <pre style={{
                padding: '6px 12px', margin: 0, fontSize: 11,
                fontFamily: 'monospace', color: '#b0b0b0',
                whiteSpace: 'pre-wrap',
              }}>{net.code}</pre>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
