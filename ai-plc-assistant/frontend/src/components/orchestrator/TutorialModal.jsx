// 编排管理教程弹窗 + 内部子组件
import { HelpCircle } from 'lucide-react'

function Section({ title, icon, children }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-text-primary mb-2">{icon} {title}</h3>
      <div className="text-text-secondary leading-relaxed">{children}</div>
    </div>
  )
}

function ToolCard({ server, count, desc }) {
  return (
    <div className="bg-ide-bg border border-ide-border rounded p-2">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-text-primary font-medium">{server}</span>
        <span className="text-2xs text-accent">{count} 工具</span>
      </div>
      <div className="text-2xs text-text-dim">{desc}</div>
    </div>
  )
}

function Step({ num, title, children }) {
  return (
    <div className="flex gap-2">
      <span className="w-5 h-5 rounded-full bg-accent/20 text-accent text-2xs flex items-center justify-center shrink-0 mt-0.5">{num}</span>
      <div>
        <div className="font-medium text-text-primary mb-0.5">{title}</div>
        <div className="text-text-dim leading-relaxed">{children}</div>
      </div>
    </div>
  )
}

export default function TutorialModal({ onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90" onClick={onClose}>
      <div className="bg-ide-sidebar border border-ide-border rounded-lg shadow-2xl w-[680px] max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="sticky top-0 bg-ide-sidebar border-b border-ide-border px-5 py-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-bright flex items-center gap-2">
            <HelpCircle size={18} className="text-accent" /> 编排管理教程
          </h2>
          <button onClick={onClose} className="text-text-dim hover:text-text-primary text-lg">✕</button>
        </div>

        <div className="px-5 py-4 space-y-6 text-xs">
          {/* 什么是编排层 */}
          <Section title="什么是编排层？" icon="🎯">
            <p>编排层（Orchestrator）是 AI PLC Assistant 的<strong>自动化中枢</strong>。它把多个工业协议服务器（S7、Modbus、TIA Portal、机器人等）串联起来，按预设的顺序自动执行操作。</p>
            <p className="mt-2">类比：就像工厂的流水线，每个工位做一件事，但整个流水线自动化运行。编排层就是这条流水线的控制中心。</p>
          </Section>

          {/* 工作流 */}
          <Section title="工作流是什么？" icon="🔀">
            <p><strong>工作流</strong> = 一组按顺序执行的工具调用。每个工作流解决一个完整的工业场景。</p>
            <div className="mt-2 bg-ide-bg border border-ide-border rounded p-3 space-y-1 font-mono text-text-secondary">
              <div className="text-accent">示例：robot_pick_place（机器人取放）</div>
              <div>1. get_status → 检查机器人状态</div>
              <div>2. go_home → 回原点</div>
              <div>3. control_conveyor → 启动传送带</div>
              <div>4. pick_item → 拾取工件</div>
              <div>5. control_conveyor → 传送带移动</div>
              <div>6. place_item → 放置工件</div>
              <div>7. go_home → 回原点</div>
            </div>
            <p className="mt-2 text-text-dim">内置工作流由 Python 代码定义，自定义工作流可通过可视化编辑器自由组合工具创建。</p>
          </Section>

          {/* 工具 */}
          <Section title="工具是什么？" icon="🔧">
            <p><strong>工具</strong> = 来自 MCP 服务器的单个操作能力。每个工具做一件具体的事。</p>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <ToolCard server="PLC 桥接" count="65" desc="S7 读写、TIA 工程操作、PLCSIM" />
              <ToolCard server="TIA Portal" count="15" desc="编译、下载、导入SCL、创建块" />
              <ToolCard server="机器人" count="7" desc="取放、回原点、传送带控制" />
              <ToolCard server="Modbus" count="6" desc="线圈/寄存器读写、设备扫描" />
              <ToolCard server="三菱" count="3" desc="MC 协议读写" />
            </div>
          </Section>

          {/* 如何创建 */}
          <Section title="如何创建自定义工作流？" icon="✏️">
            <ol className="list-decimal list-inside space-y-2">
              <li>点击<strong>「新建工作流」</strong>按钮</li>
              <li>输入工作流名称（英文标识符，如 <code className="bg-ide-bg px-1 rounded text-accent">my_conveyor</code>）</li>
              <li>点击<strong>「添加步骤」</strong>，选择服务器和工具，填写参数</li>
              <li>重复添加步骤，组成完整的操作序列</li>
              <li>点击<strong>「保存」</strong>保存工作流，或点击<strong>「执行测试」</strong>立即运行</li>
            </ol>
            <p className="mt-2 text-text-dim">保存后，自定义工作流会出现在左侧工作流列表中，带「自定义」标签，可随时编辑或删除。</p>
          </Section>

          {/* 如何连接真实设备 */}
          <Section title="如何连接真实工业设备？" icon="🔌">
            <div className="space-y-3">
              <Step num={1} title="确保 MCP 服务器在运行">
                每个工业协议对应一个 MCP 服务器进程。启动后端时，编排层会自动连接 <code className="bg-ide-bg px-1 rounded text-accent">server_configs.py</code> 中配置的服务器。
              </Step>
              <Step num={2} title="S7 PLC 连接">
                通过 <code className="bg-ide-bg px-1 rounded text-accent">plc-mcp-bridge</code> 连接西门子 PLC。支持 TCP/IP 和 PLCSIM 仿真。使用 <code className="bg-ide-bg px-1 rounded text-accent">s7_connect</code> 工具建立连接。
              </Step>
              <Step num={3} title="TIA Portal 连接">
                需要安装 TIA Portal V21 + Openness API。通过 <code className="bg-ide-bg px-1 rounded text-accent">tia-mcp</code> 服务器操作 TIA 项目（创建、编译、下载）。
              </Step>
              <Step num={4} title="机器人连接">
                通过 <code className="bg-ide-bg px-1 rounded text-accent">robot-mcp</code> 连接。支持模拟模式（<code className="bg-ide-bg px-1 rounded text-accent">ROBOT_BACKEND=simulated</code>）和真实 Factory I/O 场景。
              </Step>
              <Step num={5} title="验证连接">
                在编排面板中查看「已连接服务器」数量。绿色表示已连接，红色表示未连接。工具列表中可看到所有可用工具。
              </Step>
            </div>
          </Section>

          {/* 安全 */}
          <Section title="安全机制" icon="🛡️">
            <p>编排层内置<strong>安全门（SafetyGate）</strong>机制：</p>
            <ul className="list-disc list-inside space-y-1 mt-2">
              <li>所有写入操作（write/apply/download/compile/create/delete）自动经过安全校验</li>
              <li>10 条互锁规则（温度、急停、压力、角度等）</li>
              <li>写入操作被拒绝时，工作流会中止并报错</li>
              <li>所有操作记录审计日志（HMAC 链式哈希）</li>
            </ul>
          </Section>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-ide-sidebar border-t border-ide-border px-5 py-3 flex justify-end">
          <button onClick={onClose}
            className="px-4 py-1.5 text-xs bg-accent text-white rounded hover:bg-accent-hover transition-colors">
            知道了
          </button>
        </div>
      </div>
    </div>
  )
}
