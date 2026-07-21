// 顶部状态卡片
export default function StatCard({ icon: Icon, label, value, color }) {
  const dotColor = color === 'green' ? 'bg-status-ok' : color === 'red' ? 'bg-status-error' : 'bg-accent'
  return (
    <div className="bg-ide-sidebar border border-ide-border rounded p-4 flex items-center gap-3">
      <div className="relative">
        <Icon size={20} className="text-text-secondary" />
        <span className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${dotColor}`} />
      </div>
      <div>
        <div className="text-lg font-semibold text-text-bright">{value}</div>
        <div className="text-2xs text-text-dim">{label}</div>
      </div>
    </div>
  )
}
