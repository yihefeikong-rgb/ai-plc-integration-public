FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY edge-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY edge-gateway/src/ ./edge-gateway/src/
COPY edge-gateway/config/ ./edge-gateway/config/

# 外部依赖模块（app.py 通过 sys.path 引用）
COPY mcp_common/ ./mcp_common/
COPY safety/ ./safety/
COPY mcp-servers/plc-mcp-bridge/s7_adapter.py ./mcp-servers/plc-mcp-bridge/s7_adapter.py

ENV PYTHONPATH=/app

# 非 root 用户运行
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/edge-gateway

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import sys; sys.exit(0)" || exit 1

CMD ["python", "-m", "src.app"]
