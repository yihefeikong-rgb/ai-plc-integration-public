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
	@echo "启动阶段1：运行态基础"
	cd mcp-servers/opcua-mcp && python server.py

phase2:
	@echo "启动阶段2：控制闭环"
	docker-compose up -d influxdb grafana
	@echo "InfluxDB: http://localhost:8086"
	@echo "Grafana:  http://localhost:3000"

phase3:
	@echo "启动阶段3：西门子工程态"
	@echo "确保 TIA Portal V17+ 已安装并配置 Openness"
	cd mcp-servers/tia-mcp && python tia_mcp_host.py

sim:
	@echo "启动 OpenPLC 仿真..."
	docker-compose --profile simulation up -d
	@echo "OpenPLC: http://localhost:8080 (openplc/openplc)"

llm:
	@echo "启动本地 LLM..."
	docker-compose --profile llm up -d
	@echo "Ollama API: http://localhost:11434"
	@echo "运行: ollama pull qwen3:30b"

test:
	@echo "运行测试..."
	cd tests && python -m pytest -v

clean:
	@echo "清理所有容器..."
	docker-compose down -v
	docker-compose --profile simulation down -v
	docker-compose --profile llm down -v
