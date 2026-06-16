# AI 接入 PLC 项目 — 常用命令

.PHONY: help setup phase1 phase2 phase3 test clean

help:
	@echo "AI 接入 PLC 项目命令"
	@echo ""
	@echo "  make setup      初始化项目环境"
	@echo "  make phase1     启动阶段1：运行态基础"
	@echo "  make phase2     启动阶段2：控制闭环"
	@echo "  make phase3     启动阶段3：西门子工程态"
	@echo "  make sim        启动 OpenPLC 仿真环境"
	@echo "  make llm        启动本地 LLM (Ollama)"
	@echo "  make test       运行测试"
	@echo "  make clean      清理所有容器"
	@echo ""

setup:
	@echo "初始化项目..."
	mkdir -p mcp-servers/opcua-mcp
	mkdir -p mcp-servers/mitsubishi-mcp
	mkdir -p mcp-servers/tia-mcp
	mkdir -p mcp-servers/robot-mcp
	mkdir -p edge-gateway/src
	mkdir -p edge-gateway/config
	mkdir -p plc-code-templates/siemens-scl
	mkdir -p safety
	mkdir -p tests/integration
	@echo "目录结构创建完成"

phase1:
	@echo "启动阶段1：运行态基础（S7 协议）"
	@echo ""
	@echo "  MCP 服务（给 Claude Code 用）:"
	@echo "    cd mcp-servers/plc-mcp-bridge && python server.py"
	@echo ""
	@echo "  测试连接:"
	@echo "    python verify_phase2.py --all"
	@echo ""
	@echo "  OPC UA 备选方案:"
	@echo "    cd mcp-servers/opcua-mcp && python server.py"

phase2:
	@echo "启动阶段2：控制闭环（边缘网关 + InfluxDB）"
	docker-compose --profile monitoring up -d influxdb grafana
	@echo "InfluxDB: http://localhost:8086"
	@echo "Grafana: http://localhost:3000 (admin/your-password)"
	@echo ""
	@echo "启动 AI 控制循环:"
	@echo "  python -m edge_gateway.src.app"

phase3:
	@echo "启动阶段3：西门子工程态"
	@echo "确保 TIA Portal V18 已安装并配置 Openness"
	cd mcp-servers/tia-mcp && python server.py

sim:
	@echo "启动 OpenPLC 仿真..."
	docker-compose --profile simulation up -d
	@echo "OpenPLC: http://localhost:8080 (openplc/openplc)"

llm:
	@echo "本地 LLM (Ollama) 未部署 — 如需安装请参考:"
	@echo "  https://ollama.com/download"
	@echo "  ollama pull qwen3:7b"
	@echo "  ollama serve"

build-v18:
	@echo "编译 TiaWorker (V18)..."
	cd mcp-servers/tia-mcp/TiaWorker && dotnet build -p:TiaVersion=V18
	@echo "✅ TiaWorker V18 编译完成"

build-v21:
	@echo "编译 TiaWorker (V21)..."
	cd mcp-servers/tia-mcp/TiaWorker && dotnet build -p:TiaVersion=V21
	@echo "✅ TiaWorker V21 编译完成"

build: build-v18
	@echo "默认编译 V18 版本。使用 'make build-v21' 编译 V21 版本。"

test:
	@echo "运行测试..."
	@echo ""
	@echo "  # PLC MCP Bridge 测试（78 项）"
	@echo "  python -m pytest mcp-servers/plc-mcp-bridge/tests/ -v"
	@echo ""
	@echo "  # Safety 测试（21 项）"
	@echo "  python -m pytest tests/test_safety_validator.py tests/test_safety_audit.py -v"
	@echo ""
	@echo "  # Phase 2 验证（20 项，含真实 S7 连接需 --all）"
	@echo "  python verify_phase2.py"

clean:
	@echo "清理所有容器..."
	docker-compose down -v
	docker-compose --profile simulation down -v
	docker-compose --profile llm down -v
