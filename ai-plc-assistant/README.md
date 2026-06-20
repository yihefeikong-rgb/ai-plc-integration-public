# AI PLC Assistant

工业自动化 AI 工作台 — 本地运行、多模型支持、PLC 编程辅助。

## 项目结构

```
ai-plc-assistant/
├── frontend/              # Electron + React + TailwindCSS
│   ├── electron/          # Electron 主进程
│   ├── src/               # React 源码
│   │   ├── components/    # UI 组件
│   │   ├── App.jsx        # 主应用
│   │   └── main.jsx       # 入口
│   ├── package.json
│   └── vite.config.js
├── backend/               # Python FastAPI
│   ├── routes/            # API 路由
│   ├── main.py            # 服务入口
│   └── config.py          # 配置
└── README.md
```

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
python main.py
# 服务运行在 http://127.0.0.1:8005
```

### 前端

```bash
cd frontend
npm install
npm run dev
# Vite 运行在 http://localhost:5173
# Electron 自动启动
```

## 布局

```
┌───────────────────────────────────────────────────┐
│ 标题栏                                            │
├──────┬────────────────────────┬───────────────────┤
│      │                        │                   │
│ 左侧 │       AI 聊天区         │   右侧上下文面板   │
│ 项目  │                        │   上下文/IO表/搜索 │
│ 知识库│                        │                   │
│ 模型  │                        │                   │
├──────┴────────────────────────┴───────────────────┤
│ 底部日志面板 (API调用 / Token / 错误)               │
└───────────────────────────────────────────────────┘
```

## V1.0 功能

- [x] 三栏布局：项目列表 / AI聊天 / 上下文面板
- [x] 多模型切换（OpenAI / Claude / Kimi / DeepSeek / OpenRouter）
- [x] 底部日志面板
- [x] 模型 API 接入
- [x] 本地知识库 (RAG)
- [x] PLC 工程搜索
- [x] Prompt 模板管理
- [x] 梯形图生成
