# project:gen-plc-block — 根据描述生成西门子 PLC 块

## 任务
根据自然语言描述，生成西门子 LAD（梯形图）块 → CartGen → TIA Portal 导入 → 编译。

## 参数
- BLOCK_NAME：英文驼峰命名（如 PumpControl）
- DESCRIPTION：控制逻辑中文描述（如"水泵高液位启动低液位停止"）
- BLOCK_NUMBER：块编号（默认 500）

## 工作流程

### 1. 读取上下文
- READ mcp-servers/tia-mcp/generate_custom.py（找到 DESCRIPTION 和 BLOCK_NAME，修改它们）
- READ mcp-servers/tia-mcp/ladder_renderer.py（可选：SVG 预览用）

### 2. 安全规则（代码生成时必须遵守）
- **不使用 parallelElements**（CartGen 不支持并联分支）
- 自保持用 Set/Reset 模式代替并联
- 所有输出必须有急停互锁（串联 iStop normally_closed）
- 正转/反转必须互锁
- 过载保护串联 iOverload normally_closed
- 变量命名：iXxx（输入）、oXxx（输出）、mXxx（中间）

### 3. 运行生成
- RUN python mcp-servers/tia-mcp/generate_custom.py

### 4. 编译验证
- RUN python -c "import sys; sys.path.insert(0,'mcp-servers/tia-mcp'); from test_full_flow import test_import_and_compile; test_import_and_compile()"

### 5. 返回结果
返回生成的块名称、网络数、编译状态（State/Errors/Warnings）。
