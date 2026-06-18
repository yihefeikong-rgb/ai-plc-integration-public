# 当前开发状态 — 2026-06-18

> 最后更新：2026-06-18 18:00
> 此文件记录此刻的准确状态，供新 AI 工程师接手参考。

---

## 一、正在开发的功能

无。当前处于**功能封冻**状态，准备从 Claude Code 迁移到 Reasonix。

## 二、最近完成的任务

| 时间 | 任务 | 提交 |
|------|------|------|
| 2026-06-18 | SCL模板中文标题 + 知识库文件名修复 | 934daca |
| 2026-06-18 | 侧栏模板标签改名(提示词模板/SCL代码模板) | df07a26 |
| 2026-06-18 | SCL代码模板弹窗 + 知识库分组默认折叠 | 99ac49d |
| 2026-06-18 | .gitignore 放开 data/*.json，模板库16篇 | 53e8dc9 |
| 2026-06-18 | 模板库16篇 + SCL模板文件API | 1d316cf |
| 2026-06-17 | 电梯/停车场/HVAC SCL模板文件写入 | 未提交（新文件） |
| 2026-06-17 | LadderTemplateModal 梯形图模板弹窗 | 未提交（新文件） |
| 2026-06-17 | Prompt模板扩充到 22 个 | 未提交 |
| 2026-06-16 | 全局5维度审查修复5个CRITICAL | 父项目 |

## 三、当前卡住的问题

### P1: 梯形图 SVG 可视化
- **现象**: 梯形图输出是 ASCII 符号和结构化文本，无图形展示
- **根因**: 仅实现了文本生成和导出，没做前端 SVG 渲染
- **方案**: 已有 LadderProgram 数据结构（networks/rows/elements），前端根据数据渲染 SVG
- **阻碍**: 无

### P1: Electron 打包未验证
- **现象**: `npm run dist` 配置了 NSIS 打包但从未实际运行
- **风险**: 路径、依赖、权限问题可能在打包时暴露
- **阻碍**: 无（直接运行 `npm run dist` 测试即可）

### P1: 零测试覆盖率
- **现象**: AI PLC Assistant 无任何测试文件
- **根因**: 开发初期赶功能，测试被延后
- **风险**: 不敢重构、无法回退、发布质量不可控
- **阻碍**: 需要先装 pytest 依赖、建 test 目录

### P2: RAG 中文检索差
- **现象**: 中文文档搜索准确率低于英文
- **根因**: all-MiniLM-L6-v2 对中文支持差
- **方案**: 换 BAAI/bge-m3 并重建索引
- **阻碍**: 需要下载新模型（~500MB），重建索引可能需要 15-30 分钟

### P2: 工程搜索中文不分词
- **现象**: FTS5 unicode61 对 CJK 不处理，中文搜索走 LIKE
- **阻碍**: 需要引入 jieba 分词器 + 自定义 FTS5 tokenize

### P3: TiaCommander 过期
- **现象**: 闭源 Beta 版许可证 2026-06-19 到期
- **状态**: 已用自研 TiaWorker 替代，覆盖 90% 功能

## 四、已完成的功能清单

### ✅ 100% - AI 对话系统
- 5 模型供应商（DeepSeek/OpenAI/Kimi/Claude/自定义）
- SSE 流式输出（前后端全链路）
- 模型自动切换
- PLC 系统 Prompt
- RAG 增强（ChromaDB）
- 对话持久化（SQLite）

### ✅ 100% - 专用工作台
- 梯形图生成（自然语言 → LLM → 结构化 → 导出）
- 代码解析（分析 PLC 代码结构）
- IO 表生成（设备描述 → IO 分配表）
- 故障诊断（描述 + 错误码 → 诊断报告）

### ✅ 100% - 知识库
- PDF/DOCX/TXT 导入
- 自动分块（500字/100字重叠）
- 向量搜索（Cosine + 阈值过滤）
- 文档管理（列表/删除/统计）

### ✅ 95% - 代码生成
- SCL 源码导出
- PLCopen XML 导出
- CSV 标签表/HMI/报警/JSON 导出
- ❌ 缺少 SVG 可视化

### ✅ 100% - Prompt 模板系统
- 22 个内置模板（含 6 个新增）
- 变量系统 + 默认值
- 分类管理
- CRUD

### ✅ 100% - SCL 代码模板
- 22 个 SCL 源码文件（含中文名模板）
- 前端 CodeTemplateModal 弹窗
- IO 表自动解析

### ✅ 100% - 梯形图 LAD 模板
- 20 个 JSON 梯形图模板
- 前端 LadderTemplateModal 弹窗
- 结构化文本化展示

### ✅ 100% - UI
- PLC IDE 风格（VSCode Dark 配色）
- 四区域布局（Toolbar/Sidebar/Workspace/Log）
- Tab 系统
- Dashboard 欢迎页
- 侧栏分组折叠
- 模型选择器
- 日志面板

### ✅ 100% - 设置
- 5 供应商配置（API Key / Base URL / 模型）
- 测试连接 + 延迟显示
- API Key 遮盖

### ✅ 100% - 项目管理
- CRUD + 最近打开
- 工程导入（.ap18/.zip → 解压 → FTS5 索引）

## 五、当前分支与提交

```bash
分支: master
最新提交: 934daca feat: SCL模板中文标题 + 知识库文件名修复 + 路径bug修复
未提交文件:
  - ai-plc-assistant/frontend/src/components/LadderTemplateModal.jsx
  - plc-code-templates/siemens-scl/停车场管理系统.{md,scl}
  - plc-code-templates/siemens-scl/楼宇自控HVAC系统.{md,scl}
  - plc-code-templates/siemens-scl/电梯控制系统.{md,scl}
  - research_output_1.txt, research_output_2.txt
  - research_result_1.txt, research_result_2.txt
  - research_report.md
```

## 六、文件修改统计

```bash
# 最近修改最多的后端文件
backend/routes/knowledge.py          # 多次调整（代码模板/文件名修复/分组）
backend/data/prompts.json            # 从 11 → 16 → 22 个模板

# 最近修改最多的前端文件
frontend/src/App.jsx                 # 接入多个弹窗
frontend/src/api.js                  # 新增模板 API
frontend/src/components/Sidebar.jsx  # 分组折叠/标签改名
frontend/src/components/CodeTemplateModal.jsx  # 新建
frontend/src/components/LadderTemplateModal.jsx # 新建

# 配置文件
.gitignore                           # 放开 data/*.json
start.bat                            # 启动脚本调整
```
